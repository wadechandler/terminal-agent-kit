"""Tests for CursorACPProvider spawn, stop, and list_models.

CursorACPProvider is a thin wrapper around ACPProvider; the asyncio calls
happen in tak.providers.acp, so patches must target that module.
"""

from __future__ import annotations

import asyncio
import json
import os
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from tak.core.agent_manager import AgentHandle, AgentStatus
from tak.providers.cursor_acp import CursorACPProvider


class MockACPStdio:
    """Shared mock for stdin/stdout that auto-responds to the ACP handshake."""

    def __init__(self) -> None:
        self._read_queue: asyncio.Queue[bytes] = asyncio.Queue()
        self.written: list[dict[str, Any]] = []
        self._next_id = 0

    def write(self, data: bytes) -> None:
        for line in data.split(b"\n"):
            line = line.strip()
            if not line:
                continue
            msg = json.loads(line)
            self.written.append(msg)
            self._auto_respond(msg)

    async def drain(self) -> None:
        pass

    def feed_json(self, obj: dict[str, Any]) -> None:
        self._read_queue.put_nowait(json.dumps(obj).encode() + b"\n")

    async def readline(self) -> bytes:
        try:
            return await asyncio.wait_for(self._read_queue.get(), timeout=5.0)
        except TimeoutError:
            return b""

    def _auto_respond(self, msg: dict[str, Any]) -> None:
        req_id = msg.get("id")
        method = msg.get("method", "")

        if method == "initialize":
            self.feed_json({"jsonrpc": "2.0", "id": req_id, "result": {"capabilities": {}}})
        elif method == "authenticate":
            self.feed_json({"jsonrpc": "2.0", "id": req_id, "result": {"ok": True}})
        elif method == "session/new":
            self.feed_json({
                "jsonrpc": "2.0", "id": req_id,
                "result": {"sessionId": "test-session-id"},
            })


class MockACPProcess:
    """A mock subprocess whose stdio auto-responds to the ACP handshake."""

    def __init__(self) -> None:
        self._stdio = MockACPStdio()
        self.stdin = self._stdio
        self.stdout = self._stdio
        self.stderr = MockACPStdio()
        self.returncode: int | None = None
        self._terminated = False

    def terminate(self) -> None:
        self._terminated = True
        self.returncode = -15

    def kill(self) -> None:
        self._terminated = True
        self.returncode = -9

    async def wait(self) -> int:
        self.returncode = self.returncode or 0
        return self.returncode

    @property
    def written(self) -> list[dict[str, Any]]:
        return self._stdio.written


class TestCursorACPProviderSpawn:
    async def test_spawn_builds_correct_command(self) -> None:
        mock_proc = MockACPProcess()

        with patch("tak.providers.acp.asyncio") as mock_asyncio:
            mock_asyncio.create_subprocess_exec = AsyncMock(return_value=mock_proc)
            mock_asyncio.subprocess = asyncio.subprocess

            provider = CursorACPProvider(command="cursor")
            process = await provider.spawn("my-agent", model="claude-sonnet-4")

            call_args = mock_asyncio.create_subprocess_exec.call_args
            cmd = call_args[0]
            assert os.path.basename(cmd[0]) == "cursor"
            assert cmd[1] == "agent"
            assert cmd[2] == "acp"
            assert process is mock_proc

            session_new = next(
                m for m in mock_proc.written if m.get("method") == "session/new"
            )
            assert session_new["params"].get("model") == "claude-sonnet-4"

    async def test_spawn_with_project_path(self) -> None:
        from pathlib import Path

        mock_proc = MockACPProcess()

        with patch("tak.providers.acp.asyncio") as mock_asyncio:
            mock_asyncio.create_subprocess_exec = AsyncMock(return_value=mock_proc)
            mock_asyncio.subprocess = asyncio.subprocess

            provider = CursorACPProvider()
            await provider.spawn(
                "my-agent",
                project_path=Path("/tmp/project"),  # noqa: S108
            )

            session_new = next(
                m for m in mock_proc.written if m.get("method") == "session/new"
            )
            assert session_new["params"].get("cwd") == "/tmp/project"  # noqa: S108

    async def test_spawn_completes_handshake(self) -> None:
        mock_proc = MockACPProcess()

        with patch("tak.providers.acp.asyncio") as mock_asyncio:
            mock_asyncio.create_subprocess_exec = AsyncMock(return_value=mock_proc)
            mock_asyncio.subprocess = asyncio.subprocess

            provider = CursorACPProvider()
            await provider.spawn("test-agent")

            methods = [m["method"] for m in mock_proc.written]
            assert "initialize" in methods
            assert "authenticate" in methods
            assert "session/new" in methods

    async def test_spawn_creates_session_manager(self) -> None:
        mock_proc = MockACPProcess()

        with patch("tak.providers.acp.asyncio") as mock_asyncio:
            mock_asyncio.create_subprocess_exec = AsyncMock(return_value=mock_proc)
            mock_asyncio.subprocess = asyncio.subprocess

            provider = CursorACPProvider()
            await provider.spawn("test-agent")

            session = provider.get_session("test-agent")
            assert session is not None
            assert session.session_id == "test-session-id"


class TestCursorACPProviderListModels:
    async def test_list_models_parses_output(self) -> None:
        mock_proc = AsyncMock()
        mock_proc.returncode = 0
        mock_proc.communicate = AsyncMock(
            return_value=(b"claude-sonnet-4\nclaude-opus-4\ngpt-4o\n", b"")
        )

        with patch("tak.providers.acp.asyncio") as mock_asyncio:
            mock_asyncio.create_subprocess_exec = AsyncMock(return_value=mock_proc)
            mock_asyncio.subprocess = asyncio.subprocess
            mock_asyncio.wait_for = AsyncMock(
                return_value=(b"claude-sonnet-4\nclaude-opus-4\ngpt-4o\n", b"")
            )

            provider = CursorACPProvider(command="cursor")
            models = await provider.list_models()

        assert "claude-sonnet-4" in models
        assert "claude-opus-4" in models
        assert "gpt-4o" in models

    async def test_list_models_returns_empty_on_error(self) -> None:
        mock_proc = AsyncMock()
        mock_proc.returncode = 1
        mock_proc.communicate = AsyncMock(return_value=(b"", b"error"))

        with patch("tak.providers.acp.asyncio") as mock_asyncio:
            mock_asyncio.create_subprocess_exec = AsyncMock(return_value=mock_proc)
            mock_asyncio.subprocess = asyncio.subprocess
            mock_asyncio.wait_for = AsyncMock(return_value=(b"", b"error"))

            provider = CursorACPProvider()
            models = await provider.list_models()

        assert models == []


class TestCursorACPProviderStop:
    async def test_stop_terminates_process(self) -> None:
        mock_proc = MockACPProcess()

        with patch("tak.providers.acp.asyncio") as mock_asyncio:
            mock_asyncio.create_subprocess_exec = AsyncMock(return_value=mock_proc)
            mock_asyncio.subprocess = asyncio.subprocess
            mock_asyncio.wait_for = AsyncMock(return_value=0)

            provider = CursorACPProvider()
            await provider.spawn("stop-test")

            handle = AgentHandle(
                name="stop-test",
                provider_name="cursor-acp",
                project_path=None,
                status=AgentStatus.RUNNING,
                process=mock_proc,  # type: ignore[arg-type]
            )
            await provider.stop(handle)

            assert mock_proc._terminated
            assert provider.get_session("stop-test") is None

    async def test_stop_with_no_process(self) -> None:
        provider = CursorACPProvider()
        handle = AgentHandle(
            name="ghost",
            provider_name="cursor-acp",
            project_path=None,
            status=AgentStatus.STOPPED,
            process=None,
        )
        await provider.stop(handle)


class TestCursorACPProviderCallbacks:
    def test_set_permission_callback(self) -> None:
        provider = CursorACPProvider()
        callback = AsyncMock(return_value="allow-always")
        provider.set_permission_callback(callback)
        assert provider._permission_callback is callback

    def test_set_ask_question_callback(self) -> None:
        provider = CursorACPProvider()
        callback = AsyncMock(return_value="option-a")
        provider.set_ask_question_callback(callback)
        assert provider._ask_question_callback is callback

    async def test_send_without_session_raises(self) -> None:
        provider = CursorACPProvider()
        handle = AgentHandle(
            name="no-session",
            provider_name="cursor-acp",
            project_path=None,
            status=AgentStatus.RUNNING,
        )
        with pytest.raises(RuntimeError, match="No ACP session"):
            await provider.send(handle, "hello")
