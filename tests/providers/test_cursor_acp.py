"""Tests for CursorACPProvider spawn, stop, and list_models.

CursorACPProvider is a thin wrapper around ACPProvider with Cursor-specific
defaults. Tests verify the command construction and auth method.
"""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from tak.core.agent_manager import AgentHandle, AgentStatus
from tak.providers.cursor_acp import CursorACPProvider


def _mock_spawn_agent_process() -> tuple[Any, AsyncMock, MagicMock]:
    """Create a mock for spawn_agent_process."""
    mock_conn = AsyncMock()
    mock_conn.initialize = AsyncMock(return_value=MagicMock(
        protocol_version=1,
        agent_capabilities=MagicMock(load_session=False),
    ))
    mock_conn.authenticate = AsyncMock(return_value=MagicMock())
    mock_conn.new_session = AsyncMock(return_value=MagicMock(session_id="test-session-id"))
    mock_conn.prompt = AsyncMock(return_value=MagicMock(stop_reason="end_turn"))
    mock_conn.cancel = AsyncMock()
    mock_conn.close = AsyncMock()
    mock_conn.set_session_model = AsyncMock()
    mock_conn.set_session_mode = AsyncMock()

    mock_process = MagicMock()
    mock_process.returncode = None
    mock_process.terminate = MagicMock()
    mock_process.kill = MagicMock()
    mock_process.wait = AsyncMock(return_value=0)

    @asynccontextmanager
    async def fake_spawn(client, cmd, *args, **kwargs):
        yield mock_conn, mock_process

    return fake_spawn, mock_conn, mock_process


class TestCursorACPProviderSpawn:
    async def test_spawn_completes_handshake(self) -> None:
        fake_spawn, mock_conn, _ = _mock_spawn_agent_process()

        with patch("tak.providers.acp.spawn_agent_process", fake_spawn):
            provider = CursorACPProvider()
            await provider.spawn("test-agent")

            mock_conn.initialize.assert_called_once()
            mock_conn.authenticate.assert_called_once_with(method_id="cursor_login")
            mock_conn.new_session.assert_called_once()

    async def test_spawn_creates_session_manager(self) -> None:
        fake_spawn, _mock_conn, _ = _mock_spawn_agent_process()

        with patch("tak.providers.acp.spawn_agent_process", fake_spawn):
            provider = CursorACPProvider()
            await provider.spawn("test-agent")

            session = provider.get_session("test-agent")
            assert session is not None
            assert session.session_id == "test-session-id"

    async def test_spawn_with_project_path(self) -> None:
        from pathlib import Path

        fake_spawn, mock_conn, _ = _mock_spawn_agent_process()

        with patch("tak.providers.acp.spawn_agent_process", fake_spawn):
            provider = CursorACPProvider()
            await provider.spawn(
                "my-agent",
                project_path=Path("/tmp/project"),  # noqa: S108
            )

            mock_conn.new_session.assert_called_once_with(
                cwd="/tmp/project", mcp_servers=[]  # noqa: S108
            )

    async def test_spawn_with_model(self) -> None:
        fake_spawn, mock_conn, _ = _mock_spawn_agent_process()

        with patch("tak.providers.acp.spawn_agent_process", fake_spawn):
            provider = CursorACPProvider(command="cursor")
            await provider.spawn("my-agent", model="claude-sonnet-4")

            mock_conn.set_session_model.assert_called_once_with(
                model_id="claude-sonnet-4",
                session_id="test-session-id",
            )


class TestCursorACPProviderListModels:
    async def test_list_models_parses_output(self) -> None:
        mock_proc = AsyncMock()
        mock_proc.returncode = 0

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

        with patch("tak.providers.acp.asyncio") as mock_asyncio:
            mock_asyncio.create_subprocess_exec = AsyncMock(return_value=mock_proc)
            mock_asyncio.subprocess = asyncio.subprocess
            mock_asyncio.wait_for = AsyncMock(return_value=(b"", b"error"))

            provider = CursorACPProvider()
            models = await provider.list_models()

        assert models == []


class TestCursorACPProviderStop:
    async def test_stop_closes_session(self) -> None:
        fake_spawn, mock_conn, mock_process = _mock_spawn_agent_process()

        with patch("tak.providers.acp.spawn_agent_process", fake_spawn):
            provider = CursorACPProvider()
            await provider.spawn("stop-test")

            handle = AgentHandle(
                name="stop-test",
                provider_name="cursor-acp",
                project_path=None,
                status=AgentStatus.RUNNING,
                process=mock_process,
            )
            await provider.stop(handle)

            mock_conn.close.assert_called_once()
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
