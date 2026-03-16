"""Tests for state persistence and recovery."""

from __future__ import annotations

from pathlib import Path

import pytest

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


class TestStateSavesModel:
    def test_save_includes_model(self, tmp_state_dir: Path) -> None:
        manager = StateManager(state_dir=tmp_state_dir)
        agents = [
            AgentHandle(
                name="model-agent",
                provider_name="cursor-acp",
                project_path=None,
                model="claude-sonnet-4",
                status=AgentStatus.RUNNING,
            ),
        ]
        manager.save(agents, {})
        loaded = manager.load()
        assert loaded["agents"]["model-agent"]["model"] == "claude-sonnet-4"

    def test_save_includes_null_model(self, tmp_state_dir: Path) -> None:
        manager = StateManager(state_dir=tmp_state_dir)
        agents = [
            AgentHandle(
                name="no-model-agent",
                provider_name="cursor-acp",
                project_path=None,
                model=None,
                status=AgentStatus.RUNNING,
            ),
        ]
        manager.save(agents, {})
        loaded = manager.load()
        assert loaded["agents"]["no-model-agent"]["model"] is None


class TestStateSavesTimestamp:
    def test_save_includes_timestamp(self, tmp_state_dir: Path) -> None:
        manager = StateManager(state_dir=tmp_state_dir)
        manager.save([], {})
        loaded = manager.load()
        assert "saved_at" in loaded
        assert loaded["saved_at"]  # non-empty string

    def test_timestamp_is_iso_format(self, tmp_state_dir: Path) -> None:
        from datetime import datetime

        manager = StateManager(state_dir=tmp_state_dir)
        manager.save([], {})
        loaded = manager.load()
        ts = loaded["saved_at"]
        # Should be parseable as ISO datetime
        parsed = datetime.fromisoformat(ts)
        assert parsed.tzinfo is not None  # UTC-aware


class TestStateLoadRobustness:
    def test_load_corrupted_file_returns_empty(self, tmp_state_dir: Path) -> None:
        state_file = tmp_state_dir / "state.yaml"
        state_file.write_text(":::not valid yaml:::\n{[}")

        manager = StateManager(state_dir=tmp_state_dir)
        loaded = manager.load()
        assert loaded == {"agents": {}, "associations": {}}

    def test_load_non_dict_yaml_returns_empty(self, tmp_state_dir: Path) -> None:
        state_file = tmp_state_dir / "state.yaml"
        state_file.write_text("- item1\n- item2\n")

        manager = StateManager(state_dir=tmp_state_dir)
        loaded = manager.load()
        assert loaded == {"agents": {}, "associations": {}}

    def test_round_trip_produces_equivalent_state(self, tmp_state_dir: Path) -> None:
        manager = StateManager(state_dir=tmp_state_dir)
        agents = [
            AgentHandle(
                name="round-trip",
                provider_name="cursor-acp",
                project_path=Path("/code/proj"),
                model="claude-opus-4",
                status=AgentStatus.RUNNING,
                associated_tabs=["s1", "s2"],
            ),
        ]
        associations = {"s1": "round-trip", "s2": "round-trip"}

        manager.save(agents, associations)
        loaded = manager.load()

        agent_data = loaded["agents"]["round-trip"]
        assert agent_data["provider"] == "cursor-acp"
        assert agent_data["project_path"] == "/code/proj"
        assert agent_data["model"] == "claude-opus-4"
        assert agent_data["tabs"] == ["s1", "s2"]
        assert loaded["associations"] == associations


class TestAutoSave:
    def test_auto_save_identical_to_save(self, tmp_state_dir: Path) -> None:
        manager = StateManager(state_dir=tmp_state_dir)
        agents = [
            AgentHandle(
                name="auto-agent",
                provider_name="mock",
                project_path=None,
                status=AgentStatus.RUNNING,
            ),
        ]
        manager.auto_save(agents, {})
        loaded = manager.load()
        assert "auto-agent" in loaded["agents"]

    @pytest.mark.parametrize("name", ["auto-agent"])
    def test_auto_save_persists_model(self, tmp_state_dir: Path, name: str) -> None:
        manager = StateManager(state_dir=tmp_state_dir)
        agents = [
            AgentHandle(
                name=name,
                provider_name="mock",
                project_path=None,
                model="gpt-4o",
                status=AgentStatus.RUNNING,
            ),
        ]
        manager.auto_save(agents, {})
        loaded = manager.load()
        assert loaded["agents"][name]["model"] == "gpt-4o"
