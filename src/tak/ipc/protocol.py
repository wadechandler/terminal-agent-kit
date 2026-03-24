"""IPC message protocol for CLI-to-daemon communication.

Messages are JSON objects with a ``method`` and optional ``params``,
framed as length-prefixed JSON over a Unix domain socket.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from typing import Any, cast


@dataclass
class IPCRequest:
    """A request from the CLI to the daemon."""

    method: str
    params: dict[str, Any] = field(default_factory=dict)
    request_id: int = 0

    def encode(self) -> bytes:
        """Serialize to length-prefixed JSON bytes."""
        payload = json.dumps(asdict(self)).encode()
        header = len(payload).to_bytes(4, byteorder="big")
        return header + payload

    @classmethod
    def decode(cls, data: bytes) -> IPCRequest:
        """Deserialize from JSON bytes (without length prefix)."""
        obj = json.loads(data)
        return cls(
            method=obj["method"],
            params=obj.get("params", {}),
            request_id=obj.get("request_id", 0),
        )


@dataclass
class IPCResponse:
    """A response from the daemon to the CLI."""

    success: bool
    data: Any = None
    error: str | None = None
    request_id: int = 0

    def encode(self) -> bytes:
        """Serialize to length-prefixed JSON bytes."""
        payload = json.dumps(asdict(self)).encode()
        header = len(payload).to_bytes(4, byteorder="big")
        return header + payload

    @classmethod
    def decode(cls, data: bytes) -> IPCResponse:
        """Deserialize from JSON bytes (without length prefix)."""
        obj = json.loads(data)
        return cls(
            success=obj["success"],
            data=obj.get("data"),
            error=obj.get("error"),
            request_id=obj.get("request_id", 0),
        )


async def read_message(reader: Any) -> bytes:
    """Read a length-prefixed message from an asyncio StreamReader.

    Args:
        reader: An ``asyncio.StreamReader`` instance.

    Returns:
        The message payload bytes.

    Raises:
        ConnectionError: If the connection is closed before a full message.
    """
    header = await reader.readexactly(4)
    length = int.from_bytes(header, byteorder="big")
    return cast("bytes", await reader.readexactly(length))


async def write_message(writer: Any, data: bytes) -> None:
    """Write a length-prefixed message to an asyncio StreamWriter.

    Args:
        writer: An ``asyncio.StreamWriter`` instance.
        data: The message payload bytes.
    """
    header = len(data).to_bytes(4, byteorder="big")
    writer.write(header + data)
    await writer.drain()
