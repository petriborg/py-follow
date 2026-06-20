# Tests for the async SSH integration in ShellCommand.

import asyncio
from unittest import mock
import pytest

from follow.commands import ShellCommand, Tail, Path


@pytest.mark.asyncio
async def test_local_run():
    cmd = ShellCommand('echo', ['hello'])
    proc = await cmd.run()
    # Read stdout (should output 'hello')
    stdout = await proc.stdout.read()
    assert stdout.strip() == b'hello'
    # proc.terminate()  # No need to explicitly terminate for local test


@pytest.mark.asyncio
async def test_remote_run(monkeypatch):
    # Mock the SSH client and its create_process method
    mock_client = mock.AsyncMock()
    mock_process = mock.AsyncMock()
    mock_client.create_process.return_value = mock_process
    # Patch get_client to return our mock client
    mock_get_client = mock.AsyncMock(return_value=mock_client)
    monkeypatch.setattr('follow.ssh.get_client', mock_get_client)

    # Use Tail which has an alias (gtail) and remote host
    tail = Tail('user@host:/tmp/file')
    proc = await tail.run()
    # Ensure that create_process was called with the alias‑resolved command string
    expected_cmd = tail.local
    mock_client.create_process.assert_awaited_once_with(expected_cmd)
    assert proc is mock_process
