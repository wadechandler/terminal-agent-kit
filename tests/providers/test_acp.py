"""Tests for the generic ACPProvider."""

from __future__ import annotations

import asyncio
import json
import os
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from tak.core.agent_manager import AgentHandle, AgentStatus
from tak.providers.acp import ACPProvider
from tak.providers.base import InteractionModel


class MockACPStdio:
    """Mock stdin/stdout that auto-responds to ACP handshake messages."""

    def __init__(self) -> None:
        self._read_queue: asyncio.Queue[bytes] = asyncio.Queue()
        self.written: list[dict[str, Any]] = []

    def write(self, data: bytes) -> None:
        """Capture written bytes and auto-respond to ACP handshake methods."""
        for line in data.split(b"\n"):
            line = line.strip()
            if not line:
                continue
            msg = json.loads(line)
            self.written.append(msg)
            self._auto_respond(msg)

    async def drain(self) -> None:
        """No-op drain."""

    def feed_json(self, obj: dict[str, Any]) -> None:
        """Enqueue a response line for readline() to return."""
        self._read_queue.put_nowait(json.dumps(obj).encode() + b"\n")

    async def readline(self) -> bytes:
        """Return the next queued response line."""
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
                "jsonrpc": "2.0",
                "id": req_id,
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
        """Record termination."""
        self._terminated = True
        self.returncode = -15

    def kill(self) -> None:
        """Record kill."""
        self._terminated = True
        self.returncode = -9

    async def wait(self) -> int:
        """Return exit code."""
        self.returncode = self.returncode or 0
        return self.returncode

    @property
    def written(self) -> list[dict[str, Any]]:
        """All messages written to stdin."""
        return self._stdio.written


class TestACPProviderProperties:
    """Tests for ACPProvider property accessors."""

    def test_name_is_set(self) -> None:
        provider = ACPProvider(name="Test ACP", command=["test-agent", "acp"])
        assert provider.name == "Test ACP"

    def test_protocol_is_json_rpc(self) -> None:
        provider = ACPProvider(name="Test ACP", command=["test-agent", "acp"])
        assert provider.protocol == "json-rpc"

    def test_interaction_model_is_headless(self) -> None:
        provider = ACPProvider(name="Test ACP", command=["test-agent", "acp"])
        assert provider.interaction_model == InteractionModel.HEADLESS


class TestACPProviderSpawn:
    """Tests for ACPProvider.spawn()."""

    async def test_spawn_builds_correct_command(self) -> None:
        mock_proc = MockACPProcess()

        with patch("tak.providers.acp.asyncio") as mock_asyncio:
            mock_asyncio.create_subprocess_exec = AsyncMock(return_value=mock_proc)
            mock_asyncio.subprocess = asyncio.subprocess

            provider = ACPProvider(name="Goose", command=["goose", "acp"])
            process = await provider.spawn("my-agent", model="llama3")

            call_args = mock_asyncio.create_subprocess_exec.call_args
            cmd = call_args[0]
            assert os.path.basename(cmd[0]) == "goose"
            assert cmd[1] == "acp"
            assert process is mock_proc

            session_new = next(
                m for m in mock_proc.written if m.get("method") == "session/new"
            )
            assert session_new["params"].get("model") == "llama3"

    async def test_spawn_with_arbitrary_command(self) -> None:
        mock_proc = MockACPProcess()

        with patch("tak.providers.acp.asyncio") as mock_asyncio:
            mock_asyncio.create_subprocess_exec = AsyncMock(return_value=mock_proc)
            mock_asyncio.subprocess = asyncio.subprocess

            provider = ACPProvider(name="Claude ACP", command=["claude-agent-acp"])
            await provider.spawn("claude-1")

            call_args = mock_asyncio.create_subprocess_exec.call_args
            cmd = call_args[0]
            assert os.path.basename(cmd[0]) == "claude-agent-acp"

    async def test_spawn_with_project_path(self) -> None:
        from pathlib import Path

        mock_proc = MockACPProcess()

        with patch("tak.providers.acp.asyncio") as mock_asyncio:
            mock_asyncio.create_subprocess_exec = AsyncMock(return_value=mock_proc)
            mock_asyncio.subprocess = asyncio.subprocess

            provider = ACPProvider(name="Test", command=["test-acp"])
            await provider.spawn("my-agent", project_path=Path("/tmp/proj"))  # noqa: S108

            session_new = next(
                m for m in mock_proc.written if m.get("method") == "session/new"
            )
            assert session_new["params"].get("cwd") == "/tmp/proj"  # noqa: S108

    async def test_spawn_completes_handshake_with_env_auth(self) -> None:
        mock_proc = MockACPProcess()

        with patch("tak.providers.acp.asyncio") as mock_asyncio:
            mock_asyncio.create_subprocess_exec = AsyncMock(return_value=mock_proc)
            mock_asyncio.subprocess = asyncio.subprocess

            provider = ACPProvider(name="Test", command=["test-acp"], auth_method="env")
            await provider.spawn("test-agent")

            methods = [m["method"] for m in mock_proc.written]
            assert "initialize" in methods
            assert "authenticate" in methods
            assert "session/new" in methods

    async def test_spawn_skips_authenticate_when_auth_none(self) -> None:
        mock_proc = MockACPProcess()

        with patch("tak.providers.acp.asyncio") as mock_asyncio:
            mock_asyncio.create_subprocess_exec = AsyncMock(return_value=mock_proc)
            mock_asyncio.subprocess = asyncio.subprocess

            provider = ACPProvider(name="Test", command=["test-acp"], auth_method="none")
            await provider.spawn("test-agent")

            methods = [m["method"] for m in mock_proc.written]
            assert "initialize" in methods
            assert "authenticate" not in methods
            assert "session/new" in methods

    async def test_spawn_login_auth_sends_cursor_login_method_id(self) -> None:
        mock_proc = MockACPProcess()

        with patch("tak.providers.acp.asyncio") as mock_asyncio:
            mock_asyncio.create_subprocess_exec = AsyncMock(return_value=mock_proc)
            mock_asyncio.subprocess = asyncio.subprocess

            provider = ACPProvider(name="Test", command=["test-acp"], auth_method="login")
            await provider.spawn("test-agent")

            auth_msg = next(
                m for m in mock_proc.written if m.get("method") == "authenticate"
            )
            assert auth_msg["params"]["methodId"] == "cursor_login"

    async def test_spawn_creates_session_manager(self) -> None:
        mock_proc = MockACPProcess()

        with patch("tak.providers.acp.asyncio") as mock_asyncio:
            mock_asyncio.create_subprocess_exec = AsyncMock(return_value=mock_proc)
            mock_asyncio.subprocess = asyncio.subprocess

            provider = ACPProvider(name="Test", command=["test-acp"])
            await provider.spawn("test-agent")

            session = provider.get_session("test-agent")
            assert session is not None
            assert session.session_id == "test-session-id"


class TestACPProviderListModels:
    """Tests for ACPProvider.list_models()."""

    async def test_list_models_uses_configured_command(self) -> None:
        mock_proc = AsyncMock()
        mock_proc.returncode = 0

        with patch("tak.providers.acp.asyncio") as mock_asyncio:
            mock_asyncio.create_subprocess_exec = AsyncMock(return_value=mock_proc)
            mock_asyncio.subprocess = asyncio.subprocess
            mock_asyncio.wait_for = AsyncMock(return_value=(b"llama3\nmistral\n", b""))

            provider = ACPProvider(
                name="Goose",
                command=["goose", "acp"],
                list_models_command=["goose", "models"],
            )
            models = await provider.list_models()

        assert "llama3" in models
        assert "mistral" in models
        call_args = mock_asyncio.create_subprocess_exec.call_args
        assert os.path.basename(call_args[0][0]) == "goose"
        assert call_args[0][1] == "models"

    async def test_list_models_returns_empty_when_no_command(self) -> None:
        provider = ACPProvider(name="Test", command=["test-acp"])
        models = await provider.list_models()
        assert models == []

    async def test_list_models_returns_empty_on_nonzero_exit(self) -> None:
        mock_proc = AsyncMock()
        mock_proc.returncode = 1

        with patch("tak.providers.acp.asyncio") as mock_asyncio:
            mock_asyncio.create_subprocess_exec = AsyncMock(return_value=mock_proc)
            mock_asyncio.subprocess = asyncio.subprocess
            mock_asyncio.wait_for = AsyncMock(return_value=(b"", b"error"))

            provider = ACPProvider(
                name="Test",
                command=["test-acp"],
                list_models_command=["test-acp", "models"],
            )
            models = await provider.list_models()

        assert models == []


class TestACPProviderStop:
    """Tests for ACPProvider.stop()."""

    async def test_stop_terminates_process(self) -> None:
        mock_proc = MockACPProcess()

        with patch("tak.providers.acp.asyncio") as mock_asyncio:
            mock_asyncio.create_subprocess_exec = AsyncMock(return_value=mock_proc)
            mock_asyncio.subprocess = asyncio.subprocess
            mock_asyncio.wait_for = AsyncMock(return_value=0)

            provider = ACPProvider(name="Test", command=["test-acp"])
            await provider.spawn("stop-test")

            handle = AgentHandle(
                name="stop-test",
                provider_name="test",
                project_path=None,
                status=AgentStatus.RUNNING,
                process=mock_proc,  # type: ignore[arg-type]
            )
            await provider.stop(handle)

            assert mock_proc._terminated
            assert provider.get_session("stop-test") is None

    async def test_stop_with_no_process(self) -> None:
        provider = ACPProvider(name="Test", command=["test-acp"])
        handle = AgentHandle(
            name="ghost",
            provider_name="test",
            project_path=None,
            status=AgentStatus.STOPPED,
            process=None,
        )
        await provider.stop(handle)


class TestACPProviderSend:
    """Tests for ACPProvider.send() error handling."""

    async def test_send_without_session_raises(self) -> None:
        provider = ACPProvider(name="Test", command=["test-acp"])
        handle = AgentHandle(
            name="no-session",
            provider_name="test",
            project_path=None,
            status=AgentStatus.RUNNING,
        )
        with pytest.raises(RuntimeError, match="No ACP session"):
            await provider.send(handle, "hello")
