# AsyncSSH connection manager for py-follow
# Provides a simple connection pool keyed by (user, host).
# All connections are kept open for the life of the process and are closed on shutdown.

try:
    import asyncssh
except ImportError as _asyncssh_import_error:
    asyncssh = None
    _import_error = _asyncssh_import_error
from typing import Dict, Tuple
from .util import log


# Global connection cache: (user, host) -> SSHClient
_connections: Dict[Tuple[str | None, str], asyncssh.SSHClient] = {}


async def get_client(user: str | None, host: str) -> asyncssh.SSHClient:
    """Return a cached SSHClient for ``host``/``user`` or create a new one.

    If a cached client exists and is still open, it is reused.
    Otherwise a new connection is created and stored.
    """
    key = (user, host)
    client = _connections.get(key)
    if client is not None and not client.is_closing():
        return client
    # Create a fresh connection; asyncssh will use the default SSH config and key handling.
    log.debug("Establishing new SSH connection to %s (user=%s)", host, user)
    if asyncssh is None:
        raise ImportError('asyncssh is required for remote commands')
    kwargs = {}
    if user:
        kwargs['username'] = user
    client = await asyncssh.connect(host, **kwargs)
    _connections[key] = client
    return client


async def close_all() -> None:
    """Close all cached SSH connections gracefully."""
    for (user, host), client in list(_connections.items()):
        try:
            if client:
                client.close()
                log.debug("Closed SSH connection to %s (user=%s)", host, user)
        except Exception as exc:
            log.exception(
                "Error while closing SSH client for %s@%s: %s", user, host, exc
            )
    _connections.clear()
