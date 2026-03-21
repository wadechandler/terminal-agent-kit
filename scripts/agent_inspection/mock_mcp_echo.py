#!/usr/bin/env python3
"""Minimal MCP stdio server for ACP inspection testing.

Exposes a single "echo" tool that returns whatever text is sent to it.
Uses Content-Length framing (LSP-style) over stdin/stdout.

Usage:
    python scripts/agent_inspection/mock_mcp_echo.py

The Cursor agent process manages this server's lifecycle via McpServerStdio.
"""

from __future__ import annotations

import json
import logging
import os
import sys

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

_stderr_handler = logging.StreamHandler(sys.stderr)
_stderr_handler.setFormatter(logging.Formatter("%(asctime)s [mock-mcp] %(message)s"))
logger.addHandler(_stderr_handler)

_LOG_FILE = os.environ.get("MCP_ECHO_LOG_FILE")
if _LOG_FILE:
    _file_handler = logging.FileHandler(_LOG_FILE, mode="a")
    _file_handler.setFormatter(
        logging.Formatter("%(asctime)s [mock-mcp] %(levelname)s %(message)s")
    )
    logger.addHandler(_file_handler)

PROTOCOL_VERSION = "2024-11-05"
SERVER_INFO = {"name": "tak-test-echo", "version": "0.1.0"}

ECHO_TOOL = {
    "name": "echo",
    "description": "Echoes back the provided text. For testing MCP tool discovery.",
    "inputSchema": {
        "type": "object",
        "properties": {
            "text": {"type": "string", "description": "Text to echo back"},
        },
        "required": ["text"],
    },
}


def _read_message() -> dict | None:
    """Read a Content-Length framed JSON-RPC message from stdin."""
    header_line = sys.stdin.buffer.readline()
    if not header_line:
        return None

    header = header_line.decode("utf-8").strip()
    if not header.startswith("Content-Length:"):
        logger.warning("Expected Content-Length header, got: %s", header)
        return None

    content_length = int(header.split(":", 1)[1].strip())

    separator = sys.stdin.buffer.readline()
    if separator.strip():
        logger.warning("Expected empty separator line, got: %s", separator)

    body = sys.stdin.buffer.read(content_length)
    if len(body) < content_length:
        return None

    msg = json.loads(body.decode("utf-8"))
    logger.debug("Received: %s", msg.get("method", msg.get("id", "?")))
    return msg


def _send_message(msg: dict) -> None:
    """Write a Content-Length framed JSON-RPC message to stdout."""
    body = json.dumps(msg).encode("utf-8")
    header = f"Content-Length: {len(body)}\r\n\r\n".encode()
    sys.stdout.buffer.write(header + body)
    sys.stdout.buffer.flush()
    logger.debug("Sent response for id=%s", msg.get("id", "notification"))


def _respond(request_id: int | str, result: dict) -> None:
    """Send a JSON-RPC success response."""
    _send_message({"jsonrpc": "2.0", "id": request_id, "result": result})


def _error(request_id: int | str, code: int, message: str) -> None:
    """Send a JSON-RPC error response."""
    _send_message({
        "jsonrpc": "2.0",
        "id": request_id,
        "error": {"code": code, "message": message},
    })


def _handle_initialize(msg: dict) -> None:
    _respond(msg["id"], {
        "protocolVersion": PROTOCOL_VERSION,
        "capabilities": {"tools": {}},
        "serverInfo": SERVER_INFO,
    })


def _handle_tools_list(msg: dict) -> None:
    _respond(msg["id"], {"tools": [ECHO_TOOL]})


def _handle_tools_call(msg: dict) -> None:
    params = msg.get("params", {})
    tool_name = params.get("name", "")
    arguments = params.get("arguments", {})

    if tool_name != "echo":
        _error(msg["id"], -32602, f"Unknown tool: {tool_name}")
        return

    text = arguments.get("text", "")
    _respond(msg["id"], {
        "content": [{"type": "text", "text": f"Echo: {text}"}],
    })


HANDLERS = {
    "initialize": _handle_initialize,
    "tools/list": _handle_tools_list,
    "tools/call": _handle_tools_call,
}

NOTIFICATIONS = {
    "notifications/initialized",
    "notifications/cancelled",
}


def main() -> None:
    """Run the MCP stdio server loop."""
    logger.info("Mock MCP echo server starting (protocol %s)", PROTOCOL_VERSION)

    while True:
        msg = _read_message()
        if msg is None:
            logger.info("stdin closed, shutting down")
            break

        method = msg.get("method", "")
        request_id = msg.get("id")

        if method in NOTIFICATIONS:
            logger.debug("Notification: %s (no response)", method)
            continue

        if request_id is None:
            logger.warning("Non-notification without id: %s", method)
            continue

        handler = HANDLERS.get(method)
        if handler:
            handler(msg)
        else:
            logger.warning("Unhandled method: %s", method)
            _error(request_id, -32601, f"Method not found: {method}")


if __name__ == "__main__":
    main()
