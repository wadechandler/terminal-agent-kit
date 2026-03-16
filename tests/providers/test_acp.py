"""Tests for the generic ACPProvider backed by the ACP SDK."""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from tak.core.agent_manager import AgentHandle, AgentStatus
from tak.providers.acp import ACPProvider
from tak.providers.base import InteractionModel


def _mock_spawn_agent_process() -> tuple[Any, AsyncMock, MagicMock]:
    """Create a mock for spawn_agent_process that returns a mock conn and process."""
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


class TestACPProviderProperties:
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
    async def test_spawn_completes_handshake(self) -> None:
        fake_spawn, mock_conn, mock_process = _mock_spawn_agent_process()

        with patch("tak.providers.acp.spawn_agent_process", fake_spawn):
            provider = ACPProvider(name="Test", command=["test-acp"])
            process = await provider.spawn("test-agent")

            assert process is mock_process
            mock_conn.initialize.assert_called_once()
            mock_conn.authenticate.assert_called_once()
            mock_conn.new_session.assert_called_once()

    async def test_spawn_creates_session_manager(self) -> None:
        fake_spawn, _mock_conn, _ = _mock_spawn_agent_process()

        with patch("tak.providers.acp.spawn_agent_process", fake_spawn):
            provider = ACPProvider(name="Test", command=["test-acp"])
            await provider.spawn("test-agent")

            session = provider.get_session("test-agent")
            assert session is not None
            assert session.session_id == "test-session-id"

    async def test_spawn_with_project_path(self) -> None:
        from pathlib import Path

        fake_spawn, mock_conn, _ = _mock_spawn_agent_process()

        with patch("tak.providers.acp.spawn_agent_process", fake_spawn):
            provider = ACPProvider(name="Test", command=["test-acp"])
            await provider.spawn("my-agent", project_path=Path("/tmp/proj"))  # noqa: S108

            mock_conn.new_session.assert_called_once_with(
                cwd="/tmp/proj", mcp_servers=[]  # noqa: S108
            )

    async def test_spawn_with_model(self) -> None:
        fake_spawn, mock_conn, _ = _mock_spawn_agent_process()

        with patch("tak.providers.acp.spawn_agent_process", fake_spawn):
            provider = ACPProvider(name="Goose", command=["goose", "acp"])
            await provider.spawn("my-agent", model="llama3")

            mock_conn.set_session_model.assert_called_once_with(
                model_id="llama3",
                session_id="test-session-id",
            )

    async def test_spawn_skips_authenticate_when_auth_none(self) -> None:
        fake_spawn, mock_conn, _ = _mock_spawn_agent_process()

        with patch("tak.providers.acp.spawn_agent_process", fake_spawn):
            provider = ACPProvider(name="Test", command=["test-acp"], auth_method="none")
            await provider.spawn("test-agent")

            mock_conn.initialize.assert_called_once()
            mock_conn.authenticate.assert_not_called()
            mock_conn.new_session.assert_called_once()

    async def test_spawn_login_auth_sends_cursor_login(self) -> None:
        fake_spawn, mock_conn, _ = _mock_spawn_agent_process()

        with patch("tak.providers.acp.spawn_agent_process", fake_spawn):
            provider = ACPProvider(name="Test", command=["test-acp"], auth_method="login")
            await provider.spawn("test-agent")

            mock_conn.authenticate.assert_called_once_with(method_id="cursor_login")


class TestACPProviderListModels:
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
    async def test_stop_closes_session_and_stack(self) -> None:
        fake_spawn, mock_conn, mock_process = _mock_spawn_agent_process()

        with patch("tak.providers.acp.spawn_agent_process", fake_spawn):
            provider = ACPProvider(name="Test", command=["test-acp"])
            await provider.spawn("stop-test")

            handle = AgentHandle(
                name="stop-test",
                provider_name="test",
                project_path=None,
                status=AgentStatus.RUNNING,
                process=mock_process,
            )
            await provider.stop(handle)

            mock_conn.close.assert_called_once()
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


class TestACPProviderCallbacks:
    def test_set_permission_callback(self) -> None:
        provider = ACPProvider(name="Test", command=["test-acp"])
        callback = AsyncMock(return_value="allow-always")
        provider.set_permission_callback(callback)
        assert provider._permission_callback is callback

    def test_set_ask_question_callback(self) -> None:
        provider = ACPProvider(name="Test", command=["test-acp"])
        callback = AsyncMock(return_value="option-a")
        provider.set_ask_question_callback(callback)
        assert provider._ask_question_callback is callback
