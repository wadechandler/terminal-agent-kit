"""Cursor CLI provider via Agent Client Protocol (ACP).

ACP uses JSON-RPC 2.0 over stdio. We spawn `cursor agent acp` as a
subprocess and communicate via stdin/stdout.

Reference: https://cursor.com/docs/cli/acp
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import TYPE_CHECKING, Any

from tak.providers.base import BaseProvider

if TYPE_CHECKING:
    from tak.core.agent_manager import AgentHandle


class CursorACPProvider(BaseProvider):
    """Cursor CLI integration via the Agent Client Protocol."""

    _request_id: int = 0

    @property
    def name(self) -> str:
        return "Cursor (ACP)"

    @property
    def protocol(self) -> str:
        return "json-rpc"

    async def spawn(
        self,
        agent_name: str,
        project_path: Path | None = None,
    ) -> asyncio.subprocess.Process:
        cmd = ["cursor", "agent", "acp"]
        if project_path:
            cmd.extend(["--project", str(project_path)])

        return await asyncio.create_subprocess_exec(
            *cmd,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

    async def send(self, handle: AgentHandle, message: str) -> str:
        if handle.process is None or handle.process.stdin is None:
            raise RuntimeError(f"Agent '{handle.name}' has no active process")

        request = self._build_request("agent/query", {"message": message})
        payload = json.dumps(request).encode() + b"\n"
        handle.process.stdin.write(payload)
        await handle.process.stdin.drain()

        if handle.process.stdout is None:
            raise RuntimeError(f"Agent '{handle.name}' stdout not available")

        response_line = await handle.process.stdout.readline()
        if not response_line:
            raise RuntimeError(f"Agent '{handle.name}' closed stdout unexpectedly")

        response = json.loads(response_line)
        return self._extract_result(response)

    async def stop(self, handle: AgentHandle) -> None:
        if handle.process is None:
            return
        handle.process.terminate()
        try:
            await asyncio.wait_for(handle.process.wait(), timeout=10.0)
        except asyncio.TimeoutError:
            handle.process.kill()
            await handle.process.wait()

    def _build_request(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        self._request_id += 1
        return {
            "jsonrpc": "2.0",
            "id": self._request_id,
            "method": method,
            "params": params,
        }

    def _extract_result(self, response: dict[str, Any]) -> str:
        if "error" in response:
            error = response["error"]
            raise RuntimeError(
                f"ACP error {error.get('code', '?')}: {error.get('message', 'unknown')}"
            )
        result = response.get("result", {})
        if isinstance(result, str):
            return result
        return result.get("text", result.get("message", str(result)))
