#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# @Author: José Sánchez-Gallego (gallegoj@uw.edu)
# @Date: 2019-06-19
# @Filename: camera.py
# @License: BSD 3-clause (http://www.opensource.org/licenses/BSD-3-Clause)
#
# @Last modified by: José Sánchez-Gallego (gallegoj@uw.edu)
# @Last modified time: 2019-10-01 18:24:15

import abc
import asyncio
import logging
import warnings

from .exceptions import BasecamNotImplemented, BasecamUserWarning
from .helpers import LoggerMixIn, Poller
from .notifier import CameraEvent, CameraSystemEvent, EventNotifier
from .utils.configuration import read_yaml_file


class CameraSystem(LoggerMixIn):
    """A base class for the camera system.

    Provides an abstract class for the camera system, including camera
    connection/disconnection event handling, adding and removing cameras, etc.

    While the instance does not handle the loop, it assumes that an event loop
    is running elsewhere, for example via `asyncio.loop.run_forever`.

    Parameters
    ----------
    config : dict or path
        A dictionary with the configuration parameters for the multiple
        cameras that can be present in the system, or the path to a YAML file.
        Refer to the documentation for details on the accepted format.
    logger_name : str
        The name of the logger to use. If not specified, the name of the class
        will be used.
    log_header : str
        A string to be prefixed to each message logged.
    loop
        The asyncio event loop.

    """

    _instance = None

    #: The subclass of `.Camera` to use with this class.
    camera_class = None

    def __new__(cls, *args, **kwargs):

        assert cls.camera_class, 'camera_class must be overriden when subclassing.'
        assert issubclass(cls.camera_class, Camera) and cls.camera_class != Camera, \
            'camera_class must be a subclass of Camera.'

        # Implements singleton
        if not cls._instance:
            cls._instance = object.__new__(cls)
        else:
            cls._instance.log('camera system was already instantiated. '
                              'This will reinitialise it.', logging.WARNING)

        return cls._instance

    def __init__(self, config=None, logger_name=None, log_header=None, loop=None):

        logger_name = logger_name or self.__class__.__name__.upper()
        log_header = log_header or f'[{logger_name.upper()}]: '

        LoggerMixIn.__init__(self, logger_name, log_header=log_header)

        self.config = config
        self.config_file = None

        self.loop = loop or asyncio.get_event_loop()

        #: list: The list of cameras being handled.
        self.cameras = []

        self._camera_poller = None

        #: .EventNotifier: Notifies of `.CameraSystemEvent` and `.CameraEvent` events.
        self.notifier = EventNotifier()

        if config and not isinstance(config, dict):
            self.config_file = config
            self.config = read_yaml_file(self.config)
            self.log(f'read configuration file from {self.config_file}')

        # Custom setup for the camera system.
        self.setup_camera_system()

    def setup_camera_system(self):
        """Setup custom camera system.

        To be overridden by the subclass if needed.

        """

        pass

    def get_camera_config(self, name=None, uid=None):
        """Gets camera parameters from the configuration.

        Parameters
        ----------
        name : str
            The name of the camera.
        uid : str
            The unique identifier of the camera.

        Returns
        -------
        camera_params : `dict`
            A dictionary with the camera parameters. If the camera is not
            present in the configuration, returns a simple dictionary with the
            ``name`` or ``uid``.

        """

        assert name or uid, 'either a name or unique identifier are required.'

        if not self.config:
            warnings.warn('no configuration available. Returning empty '
                          'camera configuration.', BasecamUserWarning)
            return {'name': name or uid, 'uid': uid}

        if name:
            if name not in self.config:
                warnings.warn(f'cannot find configuration for {name!r}.',
                              BasecamUserWarning)
                return {'name': name or uid, 'uid': uid}

            config_params = {'name': name}
            config_params.update(self.config[name])
            return config_params

        if uid:
            for name in self.config:
                if self.config[name]['uid'] == uid:
                    config_params = {'name': name}
                    config_params.update(self.config[name])
                    return config_params

            # No camera with this UID found.
            warnings.warn(f'cannot find configuration for {name!r}.',
                          BasecamUserWarning)
            return {'name': name or uid, 'uid': uid}

    async def start_camera_poller(self, interval=1.):
        """Monitors changes in the camera list.

        Issues calls to `.get_connected_cameras` on an interval and compares
        the connected cameras with those in `.cameras`. New found cameras
        are added and cameras not present are cleanly removed.

        This poller should not be initiated if the camera API already provides
        a framework to detect camera events. In that case the event handler
        should be wrapped to call `.on_camera_connected` and
        `.on_camera_disconnected`.

        Similarly, if you prefer to handle camera connections manually, avoid
        starting this poller.

        Parameters
        ----------
        interval : float
            Interval, in seconds, on which the connected cameras are polled
            for changes.

        """

        if self._camera_poller is None:
            self._camera_poller = Poller(self._check_cameras)

        await self._camera_poller.set_delay(interval)

        self.log('started camera poller.')

        return self

    async def stop_camera_poller(self):
        """Stops the camera poller if it is running."""

        if self._camera_poller.running:
            await self._camera_poller.stop()

    async def _check_cameras(self):
        """Checks the list of connected cameras.

        This is an internal function to be used only by the camera poller.

        """

        try:
            uids = self.get_connected_cameras()
        except BasecamNotImplemented:
            await self.stop_camera_poller()
            self.log('get_connected cameras is not implemented. '
                     'Stopping camera poller.', logging.ERROR)
            return

        # Checks cameras that are handled but not connected.
        to_remove = []
        for camera in self.cameras:
            if camera.uid not in uids and not camera.force:
                self.log('camera with UID {camera.uid!r} ({camera.name}) '
                         'is not connected.', logging.INFO)
                to_remove.append(camera.name)

        for camera_name in to_remove:
            await self.remove_camera(camera_name)

        # Checks cameras that are connected but not yet being handled.
        camera_uids = [camera.uid for camera in self.cameras]
        for uid in uids:
            if uid not in camera_uids:
                self.log('detected new camera with UID {uid!r}.', logging.INFO)
                self.loop.create_task(self.add_camera(uid=uid, use_config=True))

    def get_connected_cameras(self):
        """Lists the connected cameras as reported by the camera system.

        This method should not be confused with `.cameras`, which lists the
        `.Camera` instance currently being handled by the `.CameraSystem`.
        `.get_connected_cameras` returns the cameras that the camera API
        believes are connected at any given time. While both lists are likely
        to match if the camera poller or camera event handling is used, it does
        not need to be the case if cameras are being handled manually.

        Returns
        -------
        connected_cameras : `list`
            A list of unique identifiers of the connected cameras. The unique
            identifiers must match those in the configuration file.

        """

        raise BasecamNotImplemented

    async def add_camera(self, name=None, uid=None, force=False, **kwargs):
        """Adds a new `.Camera` instance to `.cameras`.

        The configuration values (if any) found in the configuration that
        match the ``name`` or ``uid`` of the camera will be used. These
        parameters can be overridden by providing additional keyword values
        for the corresponding parameters.

        Parameters
        ----------
        name : str
            The name of the camera.
        uid : str
            The unique identifier for the camera.
        force : bool
            Forces the camera to stay in the `.CameraSystem` list even if it
            does not appear in the system camera list.
        kwargs
            Other arguments to be passed to `.Camera` during
            initialisation. These parameters override the default configuration
            where applicable.

        Returns
        -------
        camera : `.Camera`
            The new `.Camera` instance.

        """

        assert name or uid, 'either name or uid are required.'

        # This returns the camera parameters or a placeholder dict with the
        # name and uid of the camera, if the camera cannot be found in the
        # configuration or there is no configuration whatsoever.
        camera_params = self.get_camera_config(name=name, uid=uid)
        camera_params.update(kwargs)

        name = camera_params.pop('name')
        if name in [camera.name for camera in self.cameras]:
            self.log('camera {name!r} is already connected.', logging.WARNING)
            return

        self.log(f'adding camera {name!r} with parameters {camera_params!r}')

        camera = self.camera_class(name, self, force=force, **camera_params)

        # If the autoconnect parameter is set, connects the camera.
        connection_params = camera_params.get('connection_params', {})
        if connection_params.get('autoconnect', True):
            await camera.connect()

        self.cameras.append(camera)

        # Notify event
        self.notifier.notify(CameraSystemEvent.CAMERA_CONNECTED, camera_params)

        return camera

    async def remove_camera(self, name=None, uid=None):
        """Removes a camera, cancelling any ongoing process.

        Parameters
        ----------
        name : str
            The name of the camera.
        uid : str
            The unique identifier for the camera.

        """

        for camera in self.cameras:
            if camera.name == name or camera.uid == uid:

                await camera.shutdown()
                self.cameras.remove(camera)

                self.log(f'removed camera {name!r}.')

                # Notify event
                self.notifier.notify(CameraSystemEvent.CAMERA_DISCONNECTED,
                                     {'uid': camera.uid, 'name': camera.name})

                return

        raise ValueError(f'camera {name} is not connected.')

    def on_camera_connected(self, uid):
        """Event handler for a newly connected camera.

        Parameters
        ----------
        uid : str
            The unique identifier for the camera.

        """

        return asyncio.run_coroutine_threadsafe(self.add_camera(uid=uid), self.loop).result()

    def on_camera_disconnected(self, uid):
        """Event handler for a camera that was disconnected.

        Parameters
        ----------
        uid : str
            The unique identifier for the camera.

        """

        return asyncio.run_coroutine_threadsafe(self.remove_camera(uid=uid), self.loop).result()


class Camera(LoggerMixIn, metaclass=abc.ABCMeta):
    """A base class for wrapping a camera API in a standard implementation.

    Instantiating the `.Camera` class does not open the camera and makes
    it ready to be used. To do that, call and await `.connect`.

    Parameters
    ----------
    name : str
        The name of the camera.
    camera_system : `.CameraSystem` instance
        The camera system handling this camera.
    force : bool
        Forces the camera to stay in the `.CameraSystem` list even if it
        does not appear in the system camera list.
    config_params : dict
        Parameters used to define how to connect to the camera, its geometry,
        initialisation parameters, etc. The format of the parameters must
        follow the structure of the configuration file.

    """

    def __init__(self, name, camera_system, force=False, **config_params):

        self.name = name

        self.camera_system = camera_system

        self.connected = False

        self.force = force
        self.config_params = config_params

    async def connect(self, **user_config_params):
        """Connects the camera and performs all the necessary setup.

        Parameters
        ----------
        user_config_params : dict
            A series of keyword arguments that override the configuration
            parameters defined during the object instantiation.

        """

        self.config_params.update(user_config_params)

        await self._connect_internal(**self.config_params)
        self.connected = True

        # Get the same logger as the camera system but uses the UID or name of
        # the camera as prefix for messages from this camera.
        log_header = self.uid or self.name
        LoggerMixIn.__init__(self, self.camera_system.logger.name,
                             log_header=f'[{log_header.upper()}]: ')

        self.log('camera connected.')
        self.camera_system.notifier.notify(CameraEvent.CAMERA_OPEN,
                                           self._get_basic_payload())

        return self

    def _get_basic_payload(self):
        """Returns a dictionary with basic payload for notifying events."""

        return {'uid': self.uid, 'name': self.name}

    @abc.abstractmethod
    async def _connect_internal(self, **config_params):
        """Internal method to connect the camera."""

        pass

    @property
    def _uid(self):
        """Get the unique identifier from the camera (e.g., serial number).

        This method can be internally overridden to return the UID of the
        camera by calling the internal camera firmware.

        """

        return None

    @property
    def uid(self):
        """Returns the unique identifier of the camera.

        Calls `._uid` to get the unique identifier directly from the camera
        firmware. Otherwise, returns the UID from the configuration, or `None`
        if not defined.

        """

        uid_from_camera = self._uid
        uid_from_config = self.config_params.get('uid', None)

        if uid_from_camera and uid_from_config:
            assert uid_from_camera == uid_from_config, 'mismatch between config and camera UID.'
            return uid_from_camera
        elif uid_from_camera:
            return uid_from_camera
        else:
            return uid_from_config

    async def expose(self, exposure_time):
        """Exposes the camera."""

        await self._expose_internal(exposure_time)

    @abc.abstractmethod
    async def _expose_internal(self, exposure_time, shutter=True):
        """Internal method to handle camera exposures."""

        pass

    async def shutdown(self):
        """Shuts down the camera."""

        await self._disconnect_internal()

        self.camera_system.notifier.notify(CameraEvent.CAMERA_CLOSED,
                                           self._get_basic_payload())

    @abc.abstractmethod
    async def _disconnect_internal(self):
        """Internal method to disconnect a camera."""

        pass
