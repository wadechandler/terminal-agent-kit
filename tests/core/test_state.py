"""Tests for state persistence and recovery."""

from __future__ import annotations

from pathlib import Path

from tak.core.agent_manager import AgentHandle, AgentStatus
from tak.core.state import StateManager


class TestStatePersistence:
    def test_save_and_load(self, tmp_state_dir: Path) -> None:
        manager = StateManager(state_dir=tmp_state_dir)
        agents = [
            AgentHandle(
                name="cursor-myapp",
                provider_name="cursor-acp",
                project_path=Path("/code/myapp"),
                status=AgentStatus.RUNNING,
                associated_tabs=["sess-1", "sess-2"],
            ),
        ]
        associations = {"sess-1": "cursor-myapp", "sess-2": "cursor-myapp"}

        manager.save(agents, associations)
        loaded = manager.load()

        assert "cursor-myapp" in loaded["agents"]
        agent_data = loaded["agents"]["cursor-myapp"]
        assert agent_data["provider"] == "cursor-acp"
        assert agent_data["project_path"] == "/code/myapp"
        assert loaded["associations"] == associations

    def test_load_nonexistent_returns_empty(self, tmp_state_dir: Path) -> None:
        manager = StateManager(state_dir=tmp_state_dir)
        loaded = manager.load()
        assert loaded == {"agents": {}, "associations": {}}

    def test_stopped_agents_excluded_from_save(self, tmp_state_dir: Path) -> None:
        manager = StateManager(state_dir=tmp_state_dir)
        agents = [
            AgentHandle(
                name="running-agent",
                provider_name="mock",
                project_path=None,
                status=AgentStatus.RUNNING,
            ),
            AgentHandle(
                name="stopped-agent",
                provider_name="mock",
                project_path=None,
                status=AgentStatus.STOPPED,
            ),
        ]
        manager.save(agents, {})
        loaded = manager.load()

        assert "running-agent" in loaded["agents"]
        assert "stopped-agent" not in loaded["agents"]

    def test_clear_removes_state_file(self, tmp_state_dir: Path) -> None:
        manager = StateManager(state_dir=tmp_state_dir)
        agents = [
            AgentHandle(
                name="test", provider_name="mock", project_path=None,
                status=AgentStatus.RUNNING,
            ),
        ]
        manager.save(agents, {})
        assert (tmp_state_dir / "state.yaml").exists()

        manager.clear()
        assert not (tmp_state_dir / "state.yaml").exists()

    def test_save_agent_with_no_project_path(self, tmp_state_dir: Path) -> None:
        manager = StateManager(state_dir=tmp_state_dir)
        agents = [
            AgentHandle(
                name="adhoc",
                provider_name="mock",
                project_path=None,
                status=AgentStatus.RUNNING,
            ),
        ]
        manager.save(agents, {})
        loaded = manager.load()
        assert loaded["agents"]["adhoc"]["project_path"] is None
