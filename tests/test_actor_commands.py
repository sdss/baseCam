#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# @Author: José Sánchez-Gallego (gallegoj@uw.edu)
# @Date: 2019-10-04
# @Filename: test_actor_commands.py
# @License: BSD 3-clause (http://www.opensource.org/licenses/BSD-3-Clause)

import asyncio

import pytest

from basecam.actor.tools import get_cameras


pytestmark = pytest.mark.asyncio


async def test_list(actor):

    command = await actor.invoke_mock_command('list')

    await asyncio.sleep(1)

    assert command.status.is_done
    assert len(actor.mock_replies) == 2
    assert actor.mock_replies[1]['cameras'] == ['test_camera']


async def test_get_cameras(command):

    assert command.actor.default_cameras == ['test_camera']
    assert command.status == command.flags.READY

    assert get_cameras(command) == command.actor.camera_system.cameras


async def test_get_cameras_no_default(command):

    command.actor.set_default_cameras()
    assert get_cameras(command, fail_command=True) is False


async def test_get_cameras_no_cameras(command):

    command.actor.default_cameras = []
    assert get_cameras(command, cameras=[], fail_command=True) is False
    assert command.status.did_fail


async def test_get_cameras_bad_default(command):

    command.actor.set_default_cameras('bad_camera')
    assert get_cameras(command, fail_command=True) is False
    assert command.status.did_fail


async def test_get_cameras_pass_cameras(command):

    assert get_cameras(command, ['test_camera']) == command.actor.camera_system.cameras


async def test_get_cameras_check(command):

    command.actor.set_default_cameras('test_camera')
    assert command.actor.camera_system.cameras[0].name == 'test_camera'
    command.actor.camera_system.cameras[0].connected = False

    assert get_cameras(command, check_cameras=True, fail_command=True) is False
    assert command.status.did_fail

    command.actor.camera_system.cameras[0].connected = True


async def test_set_default(actor):

    actor.set_default_cameras()

    await actor.invoke_mock_command('set-default test_camera')
    assert actor.default_cameras == ['test_camera']

    actor.set_default_cameras()

    command_result = await actor.invoke_mock_command('set-default bad_camera')
    assert command_result.status.did_fail

    command_result = await actor.invoke_mock_command('set-default -f bad_camera')
    assert command_result.status.is_done
    assert actor.default_cameras == ['bad_camera']

    command_result = await actor.invoke_mock_command('set-default -f sp1 sp2')
    assert command_result.status.is_done
    assert actor.default_cameras == ['sp1', 'sp2']

    command_result = await actor.invoke_mock_command('set-default -f sp1,sp2 sp3')
    assert command_result.status.is_done
    assert actor.default_cameras == ['sp1', 'sp2', 'sp3']


async def test_status(actor):

    command = await actor.invoke_mock_command('status')

    assert command.status.is_done
    assert len(actor.mock_replies) == 3  # Running, status reply, and done reply.
    assert actor.mock_replies[1]['status'] == {'temperature': 25., 'cooler': 10.}


async def test_reconnect(actor):

    command = await actor.invoke_mock_command('reconnect')

    assert command.status.is_done


async def test_reconnect_disconnect_fails(actor):

    actor.camera_system.cameras[0].raise_on_disconnect = True
    command = await actor.invoke_mock_command('reconnect')

    text_in_replies = ['failed to disconnect' in reply['text']
                       for reply in actor.mock_replies if 'text' in reply]

    assert any(text_in_replies)
    assert command.status.is_done


async def test_reconnect_connect_fails(actor):

    actor.camera_system.cameras[0].raise_on_connect = True
    command = await actor.invoke_mock_command('reconnect')

    text_in_replies = ['failed to connect' in reply['text']
                       for reply in actor.mock_replies if 'text' in reply]

    assert any(text_in_replies)
    assert command.status.did_fail