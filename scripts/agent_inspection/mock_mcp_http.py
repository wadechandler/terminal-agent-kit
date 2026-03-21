#!/usr/bin/env python3
"""HTTP mock MCP server for ACP inspection testing.

Dual-purpose server:
1. POST / -- MCP JSON-RPC endpoint (initialize, tools/list, tools/call)
2. GET /resources/config.txt -- static test resource for ResourceContentBlock tests

Uses stdlib http.server. Importable via start_server() or runnable standalone.

Usage:
    python scripts/agent_inspection/mock_mcp_http.py          # standalone
    from mock_mcp_http import start_server                    # from inspection script
    server, port = start_server()
"""

from __future__ import annotations

import json
import logging
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [mock-mcp-http] %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger(__name__)

PROTOCOL_VERSION = "2024-11-05"
SERVER_INFO = {"name": "tak-test-echo-http", "version": "0.1.0"}

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

RESOURCE_CONFIG = "server.port=9090\nserver.host=0.0.0.0\nlog.level=info\nmax_connections=100\n"


def _handle_initialize(params: dict[str, Any]) -> dict[str, Any]:
    """Handle MCP initialize request."""
    return {
        "protocolVersion": PROTOCOL_VERSION,
        "capabilities": {"tools": {}},
        "serverInfo": SERVER_INFO,
    }


def _handle_tools_list(params: dict[str, Any]) -> dict[str, Any]:
    """Handle MCP tools/list request."""
    return {"tools": [ECHO_TOOL]}


def _handle_tools_call(params: dict[str, Any]) -> dict[str, Any]:
    """Handle MCP tools/call request."""
    tool_name = params.get("name", "")
    arguments = params.get("arguments", {})

    if tool_name != "echo":
        raise ValueError(f"Unknown tool: {tool_name}")

    text = arguments.get("text", "")
    return {"content": [{"type": "text", "text": f"Echo: {text}"}]}


MCP_HANDLERS: dict[str, Any] = {
    "initialize": _handle_initialize,
    "tools/list": _handle_tools_list,
    "tools/call": _handle_tools_call,
}

MCP_NOTIFICATIONS = {"notifications/initialized", "notifications/cancelled"}


class McpHttpHandler(BaseHTTPRequestHandler):
    """HTTP handler for MCP JSON-RPC and static resource serving."""

    def do_POST(self) -> None:
        """Handle MCP JSON-RPC requests."""
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length)

        try:
            msg = json.loads(body.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            self._send_json(400, {
                "jsonrpc": "2.0",
                "id": None,
                "error": {"code": -32700, "message": f"Parse error: {exc}"},
            })
            return

        method = msg.get("method", "")
        request_id = msg.get("id")
        params = msg.get("params", {})

        logger.debug("POST %s method=%s id=%s", self.path, method, request_id)

        if method in MCP_NOTIFICATIONS:
            self._send_json(200, {"jsonrpc": "2.0", "id": request_id, "result": {}})
            return

        handler = MCP_HANDLERS.get(method)
        if not handler:
            self._send_json(200, {
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {"code": -32601, "message": f"Method not found: {method}"},
            })
            return

        try:
            result = handler(params)
            self._send_json(200, {"jsonrpc": "2.0", "id": request_id, "result": result})
        except Exception as exc:
            self._send_json(200, {
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {"code": -32602, "message": str(exc)},
            })

    def do_GET(self) -> None:
        """Serve static test resources."""
        if self.path == "/resources/config.txt":
            logger.info("GET /resources/config.txt")
            body = RESOURCE_CONFIG.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        else:
            self.send_response(404)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(b"Not found\n")

    def _send_json(self, status: int, obj: dict[str, Any]) -> None:
        """Send a JSON response."""
        body = json.dumps(obj).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A002
        """Redirect access logs to our logger."""
        logger.debug(format, *args)


def start_server(host: str = "127.0.0.1", port: int = 0) -> tuple[HTTPServer, int]:
    """Start the HTTP MCP server in a daemon thread.

    Args:
        host: Bind address.
        port: Port (0 = OS-assigned).

    Returns:
        Tuple of (server instance, actual port).
    """
    server = HTTPServer((host, port), McpHttpHandler)
    actual_port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    logger.info("Mock MCP HTTP server listening on %s:%d", host, actual_port)
    return server, actual_port


if __name__ == "__main__":
    srv, p = start_server()
    print(f"Mock MCP HTTP server running on http://127.0.0.1:{p}/", file=sys.stderr)
    print(f"  MCP endpoint: POST http://127.0.0.1:{p}/", file=sys.stderr)
    print(f"  Resource: GET http://127.0.0.1:{p}/resources/config.txt", file=sys.stderr)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        srv.shutdown()
