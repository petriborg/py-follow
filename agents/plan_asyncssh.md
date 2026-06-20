# AsyncSSH Integration Plan

## Overview
We will integrate `asyncssh` into the `ShellCommand` class to replace the current `ssh` subprocess approach with a proper asynchronous SSH client. The plan covers creating an SSH connection manager, updating command execution, handling alias resolution, and adding tests.

## Files to Modify / Create
| File | Action | Purpose |
|------|--------|---------|
| `src/follow/ssh.py` | **Create** | Provide a connection pool (`get_client`) and cleanup (`close_all`). |
| `src/follow/commands.py` | **Edit** | - Resolve aliases in `local` property (gtail fallback).<br>- Add `async def run(self)` that uses the connection manager for remote commands and `asyncio.create_subprocess_exec` for local commands. |
| `src/follow/engine.py` | **Edit** | - Change `open_file()` to `await file.run()`.
- Adjust type hint for `open_file`.
- Call `ssh.close_all()` on shutdown.
- Add error logging for remote failures. |
| `test/test_commands.py` | **Edit** | - Update expectations for `Tail.shell` to include alias resolution.
- Add tests for `ShellCommand.run()` (local & remote, with/without aliases) using mocks.
- Add tests for the new `ssh` connection manager (connection reuse, cleanup). |

## Detailed Steps
1. **Create `src/follow/ssh.py`**
   ```python
   import asyncssh
   import logging

   _connections: dict[tuple[str | None, str], asyncssh.SSHClient] = {}
   log = logging.getLogger(__name__)

   async def get_client(user: str | None, host: str) -> asyncssh.SSHClient:
       key = (user, host)
       client = _connections.get(key)
       if client is None or client.is_closing():
           log.debug("Connecting to SSH host %s (user=%s)", host, user)
           client = await asyncssh.connect(host, username=user)
           _connections[key] = client
       return client

   async def close_all() -> None:
       for (user, host), client in list(_connections.items()):
           try:
               await client.close()
               log.debug("Closed SSH connection to %s (user=%s)", host, user)
           except Exception as exc:
               log.exception("Error closing SSH client %s@%s: %s", user, host, exc)
       _connections.clear()
   ```

2. **Edit `src/follow/commands.py`**
   - **Alias‑aware `local` property**
   ```python
   @property
   def local(self) -> str:
       # Resolve aliases (e.g., gtail) before the command
       if self.aliases:
           # Build a chain like "command -v gtail || command -v tail"
           alias_chain = ' || '.join(f'command -v {a}' for a in self.aliases)
           # Fallback to the original exec if none of the aliases exist
           exec_part = f'$({alias_chain} || command -v {self.exec})'
           return f"{exec_part} {' '.join(self.args)}"
       # No alias handling needed
       return ' '.join(chain([self.exec], self.args))
   ```
   - **Add `run` method**
   ```python
   import asyncio
   from .ssh import get_client

   async def run(self):
       """Execute the command.

       - If `remote` is set, run via asyncssh (using the alias‑aware ``local`` string).
       - Otherwise, run a local subprocess safely with ``create_subprocess_exec``.
       """
       if self.remote:
           user, host = self.remote
           client = await get_client(user, host)
           # ``local`` already contains any necessary alias resolution and arguments
           return await client.create_process(self.local)
       # Local execution – use exec+args to avoid a shell when not needed
       return await asyncio.create_subprocess_exec(
           self.exec,
           *self.args,
           stdout=asyncio.subprocess.PIPE,
           stderr=asyncio.subprocess.DEVNULL,
       )
   ```

3. **Edit `src/follow/engine.py`**
   - Update abstract signature (optional, just for clarity):
   ```python
   async def open_file(self, file: Any) -> Any:  # Any covers both Process types
   ```
   - Replace the body of `open_file` with:
   ```python
   async def open_file(self, file: Any) -> Any:
       """Open ``file`` for searching using the new ``ShellCommand.run`` method."""
       try:
           proc = await file.run()
           log.debug('open_file(%s) => %r', file, proc)
           return proc
       except Exception as exc:
           # Log the failure but do not raise – the search loop will simply skip this file
           log.exception('Failed to open file %s via SSH: %s', file, exc)
           raise
   ```
   - Ensure the shutdown path closes SSH connections:
   ```python
   async def close(self):
       await super().close()
       # Close any lingering SSH sessions
       from .ssh import close_all
       await close_all()
   ```

4. **Update Tests (`test/test_commands.py`)**
   - Adjust the ``test_shell_cmd`` expectation for a remote ``Tail`` to include the alias fallback:
   ```python
   assert t1.shell == (
       'ssh -l user host "$(command -v gtail || command -v tail) -n 1  /path"'
   )
   ```
   - Add a new test class for ``ShellCommand.run``:
   ```python
   import pytest, asyncio
   from follow.commands import ShellCommand, Tail, Path
   from unittest import mock

   @pytest.mark.asyncio
   async def test_run_local():
       cmd = ShellCommand('echo', ['hello'])
       proc = await cmd.run()
       out = await proc.stdout.read()
       assert out.strip() == b'hello'
       proc.terminate()

   @pytest.mark.asyncio
   async def test_run_remote(monkeypatch):
       # Mock the SSH client manager to avoid real network traffic
       mock_client = mock.AsyncMock()
       mock_proc = mock.AsyncMock()
       mock_client.create_process.return_value = mock_proc
       monkeypatch.setitem(
           sys.modules, 'follow.ssh', mock.MagicMock(get_client=mock.AsyncMock(return_value=mock_client))
       )
       tail = Tail('user@host:/tmp/file')
       proc = await tail.run()
       mock_client.create_process.assert_awaited_once_with(tail.local)
       assert proc is mock_proc
   ```
   - Add tests for the alias‑aware ``local`` property, ensuring the gtail fallback string is correct.

5. **Add a tiny test for the connection manager** (optional but recommended):
   ```python
   import asyncio
   from follow.ssh import get_client, close_all

   @pytest.mark.asyncio
   async def test_connection_pool(monkeypatch):
       # First call creates a connection
       client1 = await get_client('user', 'example.com')
       # Second call reuses the same client
       client2 = await get_client('user', 'example.com')
       assert client1 is client2
       await close_all()
   ```

## Implementation Order
1. Create `src/follow/ssh.py`.
2. Edit `src/follow/commands.py` (alias‑aware ``local`` + ``run``).
3. Update `src/follow/engine.py` to use ``run`` and close SSH connections.
4. Update the test suite accordingly.
5. Run the test suite (`pytest -q`) to ensure everything passes.

---
**Note**: This plan assumes `asyncssh` is already installed (it is a hard dependency in ``pyproject.toml``). If installation is needed, run ``uv sync`` or ``pip install -e .`` before executing the changes.
