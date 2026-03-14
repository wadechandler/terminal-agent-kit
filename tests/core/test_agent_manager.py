"""Tests for AgentManager lifecycle operations."""

from __future__ import annotations

from pathlib import Path

import pytest

from tak.core.agent_manager import AgentManager, AgentStatus


class TestAgentManagerSpawn:
    async def test_spawn_creates_running_agent(
        self, agent_manager: AgentManager
    ) -> None:
        handle = await agent_manager.spawn("test-agent", "mock")
        assert handle.name == "test-agent"
        assert handle.status == AgentStatus.RUNNING
        assert handle.process is not None

    async def test_spawn_with_project_path(
        self, agent_manager: AgentManager
    ) -> None:
        project = Path("/tmp/myproject")
        handle = await agent_manager.spawn("test-agent", "mock", project_path=project)
        assert handle.project_path == project

    async def test_spawn_duplicate_name_raises(
        self, agent_manager: AgentManager
    ) -> None:
        await agent_manager.spawn("test-agent", "mock")
        with pytest.raises(ValueError, match="already exists"):
            await agent_manager.spawn("test-agent", "mock")

    async def test_spawn_unknown_provider_raises(
        self, agent_manager: AgentManager
    ) -> None:
        with pytest.raises(ValueError, match="Unknown provider"):
            await agent_manager.spawn("test-agent", "nonexistent")


class TestAgentManagerStop:
    async def test_stop_changes_status(
        self, agent_manager: AgentManager
    ) -> None:
        await agent_manager.spawn("test-agent", "mock")
        await agent_manager.stop("test-agent")
        handle = agent_manager.get("test-agent")
        assert handle is not None
        assert handle.status == AgentStatus.STOPPED

    async def test_stop_unknown_agent_raises(
        self, agent_manager: AgentManager
    ) -> None:
        with pytest.raises(ValueError, match="No agent named"):
            await agent_manager.stop("nonexistent")


class TestAgentManagerListing:
    async def test_list_agents_empty(self, agent_manager: AgentManager) -> None:
        assert agent_manager.list_agents() == []

    async def test_list_agents_returns_all(
        self, agent_manager: AgentManager
    ) -> None:
        await agent_manager.spawn("agent-1", "mock")
        await agent_manager.spawn("agent-2", "mock")
        assert len(agent_manager.list_agents()) == 2

    async def test_running_agents_excludes_stopped(
        self, agent_manager: AgentManager
    ) -> None:
        await agent_manager.spawn("agent-1", "mock")
        await agent_manager.spawn("agent-2", "mock")
        await agent_manager.stop("agent-1")
        running = agent_manager.running_agents()
        assert len(running) == 1
        assert running[0].name == "agent-2"

    async def test_get_returns_none_for_unknown(
        self, agent_manager: AgentManager
    ) -> None:
        assert agent_manager.get("nonexistent") is None
