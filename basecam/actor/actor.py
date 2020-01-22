#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# @Author: José Sánchez-Gallego (gallegoj@uw.edu)
# @Date: 2019-08-06
# @Filename: actor.py
# @License: BSD 3-clause (http://www.opensource.org/licenses/BSD-3-Clause)

import logging

from clu import BaseActor, JSONActor

from basecam import EventListener
from basecam.exceptions import CameraWarning

from . import commands


__all__ = ['BaseCameraActor', 'CameraActor']


class BaseCameraActor:
    """Base class for a camera CLU-like actor class.

    Expands a `CLU <https://clu.readthedocs.io/en/latest/>`__ actor
    to receive commands, interact with the camera system, and reply to
    the commander. This base class needs to be subclassed along with the
    desired implementation of CLU `~clu.actor.BaseActor`. For example ::

        from clu.actor import AMQPActor

        class MyCameraActor(BaseCameraActor, AMQPActor):
            pass

    Parameters
    ----------
    camera_system : .CameraSystem
        The camera system, already instantiated.
    default_cameras : list of `str`
        A list of camera names or UIDs that define what cameras to use by
        default in most command.
    command_parser : ~clu.parser.CluGroup
        The list of commands to use. It must be a command group deriving from
        `~clu.parser.CluGroup` containing all the commands to use. If
        ``commands=None``, uses the internal command set.
    args,kwars
        Arguments and keyword arguments to be passed to the actor class.

    """

    def __init__(self, camera_system, *args, default_cameras=None,
                 command_parser=None, **kwargs):

        self._check_is_subclass()

        assert camera_system is not None
        self.camera_system = camera_system

        #: An `.EventListener` that can be used to wait or respond to events.
        self.listener = EventListener()
        self.camera_system.notifier.register_listener(self.listener)

        command_parser = command_parser or commands.camera_parser

        super().__init__(*args, parser=command_parser, **kwargs)

        # Add commands that depend on what mixins the base camera has
        # been subclassed with.
        if command_parser == commands.camera_parser:
            self._add_optional_commands()

        self.default_cameras = None
        self.set_default_cameras(default_cameras)

    def _check_is_subclass(self):
        """Checks if the object is a subclass of a CLU actor."""

        error = 'BaseCameraActor must be sub-classed along with a CLU actor class.'
        bases = self.__class__.__bases__

        assert issubclass(self.__class__, BaseCameraActor), error

        # Check that at least one of the bases is a sublass of BaseActor
        for base in bases:
            if issubclass(base, BaseActor):
                return

        raise RuntimeError(error)

    def _add_optional_commands(self):
        """Adds commands and groups based on the mixins present."""

        camera_class = self.camera_system.camera_class

        for mixin in camera_class.__bases__:
            mixin_name = mixin.__name__
            if mixin_name in commands._MIXIN_TO_COMMANDS:
                for command in commands._MIXIN_TO_COMMANDS[mixin_name]:
                    self.command_parser.add_command(command)

    def set_default_cameras(self, cameras=None):
        """Sets the camera(s) that will be used by default.

        These cameras will be used by default when a command is issues without
        the ``--cameras`` flag.

        Parameters
        ----------
        cameras : str or list
            A list of camera names or a string with comma-separated camera
            names. If `None`, no cameras will be considered default and
            commands will fail if they do not specify a camera.

        """

        if cameras is None:
            self.default_cameras = None
            return

        if isinstance(cameras, str):
            self.default_cameras = cameras.split(',')
        elif isinstance(cameras, (list, tuple)):
            self.default_cameras = list(cameras)
        else:
            raise ValueError(f'invalid data type for cameras={cameras!r}')

        connected_cameras = [camera.name for camera in self.camera_system.cameras]
        for camera in self.default_cameras:
            if camera not in connected_cameras:
                self.log.warning(f'camera {camera!r} made default but is not connected.')


class CameraActor(BaseCameraActor, JSONActor):
    """A camera actor that replies with JSONs using `~clu.actor.JSONActor`."""

    pass
