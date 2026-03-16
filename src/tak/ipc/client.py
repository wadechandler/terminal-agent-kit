"""IPC client for the tak CLI to talk to the daemon.

Connects to the daemon's Unix domain socket, sends a request,
and returns the response.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from tak.ipc.protocol import IPCRequest, IPCResponse, read_message

DEFAULT_SOCKET_PATH = Path.home() / ".tak" / "daemon.sock"


async def send_request(
    method: str,
    params: dict[str, Any] | None = None,
    socket_path: Path | None = None,
    timeout: float = 30.0,
) -> IPCResponse:
    """Send a request to the tak daemon and return the response.

    Args:
        method: The IPC method name (e.g. ``list_agents``, ``spawn``).
        params: Optional parameters for the request.
        socket_path: Path to the daemon socket. Defaults to ``~/.tak/daemon.sock``.
        timeout: Seconds to wait for a response.

    Returns:
        The daemon's response.

    Raises:
        ConnectionError: If the daemon is not running.
        TimeoutError: If the daemon does not respond in time.
    """
    sock = socket_path or DEFAULT_SOCKET_PATH

    if not sock.exists():
        raise ConnectionError(
            f"tak daemon is not running (no socket at {sock}). "
            "Start iTerm2 with the tak daemon installed, or run 'tak setup iterm2'."
        )

    reader, writer = await asyncio.open_unix_connection(str(sock))
    try:
        request = IPCRequest(method=method, params=params or {})
        writer.write(request.encode())
        await writer.drain()

        raw = await asyncio.wait_for(read_message(reader), timeout=timeout)
        return IPCResponse.decode(raw)
    finally:
        writer.close()
        await writer.wait_closed()
