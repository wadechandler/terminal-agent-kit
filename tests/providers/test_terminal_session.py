"""Tests for TerminalSessionProvider."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from tak.core.agent_manager import AgentHandle, AgentStatus
from tak.providers.base import InteractionModel
from tak.providers.terminal_session import TerminalSessionProvider


class TestTerminalSessionProviderProperties:
    """Tests for TerminalSessionProvider property accessors."""

    def test_name_is_set(self) -> None:
        provider = TerminalSessionProvider(name="Claude Code", command=["claude"])
        assert provider.name == "Claude Code"

    def test_protocol_is_terminal(self) -> None:
        provider = TerminalSessionProvider(name="Claude Code", command=["claude"])
        assert provider.protocol == "terminal"

    def test_interaction_model_is_terminal(self) -> None:
        provider = TerminalSessionProvider(name="Claude Code", command=["claude"])
        assert provider.interaction_model == InteractionModel.TERMINAL


class TestTerminalSessionProviderSpawn:
    """Tests for TerminalSessionProvider.spawn()."""

    async def test_spawn_creates_subprocess_with_correct_command(self) -> None:
        mock_proc = MagicMock()
        mock_proc.returncode = None

        with patch("tak.providers.terminal_session.asyncio") as mock_asyncio:
            mock_asyncio.create_subprocess_exec = AsyncMock(return_value=mock_proc)

            provider = TerminalSessionProvider(name="Goose", command=["goose", "run"])
            process = await provider.spawn("my-agent")

            call_args = mock_asyncio.create_subprocess_exec.call_args
            assert call_args[0][0] == "goose"
            assert call_args[0][1] == "run"
            assert process is mock_proc

    async def test_spawn_sets_cwd_from_project_path(self) -> None:
        mock_proc = MagicMock()

        with patch("tak.providers.terminal_session.asyncio") as mock_asyncio:
            mock_asyncio.create_subprocess_exec = AsyncMock(return_value=mock_proc)

            provider = TerminalSessionProvider(name="Claude Code", command=["claude"])
            await provider.spawn("agent", project_path=Path("/tmp/myproject"))  # noqa: S108

            kwargs = mock_asyncio.create_subprocess_exec.call_args[1]
            assert kwargs.get("cwd") == "/tmp/myproject"  # noqa: S108

    async def test_spawn_no_cwd_when_no_project(self) -> None:
        mock_proc = MagicMock()

        with patch("tak.providers.terminal_session.asyncio") as mock_asyncio:
            mock_asyncio.create_subprocess_exec = AsyncMock(return_value=mock_proc)

            provider = TerminalSessionProvider(name="Claude Code", command=["claude"])
            await provider.spawn("agent")

            kwargs = mock_asyncio.create_subprocess_exec.call_args[1]
            assert kwargs.get("cwd") is None

    async def test_spawn_ignores_model(self) -> None:
        """Model is ignored for terminal providers -- model selection is in the TUI."""
        mock_proc = MagicMock()

        with patch("tak.providers.terminal_session.asyncio") as mock_asyncio:
            mock_asyncio.create_subprocess_exec = AsyncMock(return_value=mock_proc)

            provider = TerminalSessionProvider(name="Claude Code", command=["claude"])
            await provider.spawn("agent", model="claude-sonnet-4")

            call_args = mock_asyncio.create_subprocess_exec.call_args
            cmd = list(call_args[0])
            assert "--model" not in cmd


class TestTerminalSessionProviderSend:
    """Tests for TerminalSessionProvider.send()."""

    async def test_send_raises_not_implemented(self) -> None:
        provider = TerminalSessionProvider(name="Claude Code", command=["claude"])
        handle = AgentHandle(
            name="test",
            provider_name="claude-terminal",
            project_path=None,
            status=AgentStatus.RUNNING,
        )
        with pytest.raises(NotImplementedError):
            await provider.send(handle, "hello")

    async def test_send_error_mentions_provider_name(self) -> None:
        provider = TerminalSessionProvider(name="My Terminal Agent", command=["agent"])
        handle = AgentHandle(
            name="test",
            provider_name="my-terminal",
            project_path=None,
            status=AgentStatus.RUNNING,
        )
        with pytest.raises(NotImplementedError, match="My Terminal Agent"):
            await provider.send(handle, "hello")


class TestTerminalSessionProviderStop:
    """Tests for TerminalSessionProvider.stop()."""

    async def test_stop_terminates_process(self) -> None:
        mock_proc = MagicMock()
        mock_proc.returncode = None

        with patch("tak.providers.terminal_session.asyncio") as mock_asyncio:
            mock_asyncio.wait_for = AsyncMock(return_value=0)

            provider = TerminalSessionProvider(name="Claude Code", command=["claude"])
            handle = AgentHandle(
                name="test",
                provider_name="claude-terminal",
                project_path=None,
                status=AgentStatus.RUNNING,
                process=mock_proc,  # type: ignore[arg-type]
            )
            await provider.stop(handle)

            mock_proc.terminate.assert_called_once()

    async def test_stop_kills_on_timeout(self) -> None:
        mock_proc = MagicMock()

        with patch("tak.providers.terminal_session.asyncio") as mock_asyncio:
            mock_asyncio.wait_for = AsyncMock(side_effect=TimeoutError)
            mock_proc.wait = AsyncMock(return_value=0)

            provider = TerminalSessionProvider(name="Claude Code", command=["claude"])
            handle = AgentHandle(
                name="test",
                provider_name="claude-terminal",
                project_path=None,
                status=AgentStatus.RUNNING,
                process=mock_proc,  # type: ignore[arg-type]
            )
            await provider.stop(handle)

            mock_proc.terminate.assert_called_once()
            mock_proc.kill.assert_called_once()

    async def test_stop_with_no_process(self) -> None:
        provider = TerminalSessionProvider(name="Claude Code", command=["claude"])
        handle = AgentHandle(
            name="test",
            provider_name="claude-terminal",
            project_path=None,
            status=AgentStatus.STOPPED,
            process=None,
        )
        await provider.stop(handle)


class TestTerminalSessionProviderHealthCheck:
    """Tests for inherited health_check behaviour."""

    async def test_health_check_false_when_no_process(self) -> None:
        provider = TerminalSessionProvider(name="Claude Code", command=["claude"])
        handle = AgentHandle(
            name="test",
            provider_name="claude-terminal",
            project_path=None,
            status=AgentStatus.STOPPED,
            process=None,
        )
        assert await provider.health_check(handle) is False

    async def test_health_check_true_when_process_running(self) -> None:
        mock_proc = MagicMock()
        mock_proc.returncode = None  # Still running

        provider = TerminalSessionProvider(name="Claude Code", command=["claude"])
        handle = AgentHandle(
            name="test",
            provider_name="claude-terminal",
            project_path=None,
            status=AgentStatus.RUNNING,
            process=mock_proc,  # type: ignore[arg-type]
        )
        assert await provider.health_check(handle) is True

    async def test_list_models_returns_empty(self) -> None:
        provider = TerminalSessionProvider(name="Claude Code", command=["claude"])
        assert await provider.list_models() == []
