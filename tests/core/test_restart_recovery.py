"""Tests for daemon restart recovery logic."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
import yaml

from tak.core.agent_manager import AgentManager, AgentStatus
from tak.core.session_registry import SessionRegistry
from tak.core.state import StateManager
from tak.drivers.iterm2.daemon import _restore_full_state

if TYPE_CHECKING:
    from pathlib import Path


def _write_state(state_manager: StateManager, state: dict) -> None:
    """Helper to write raw state YAML using the public ``state_file`` property."""
    state_file = state_manager.state_file
    state_file.parent.mkdir(parents=True, exist_ok=True)
    with open(state_file, "w") as f:
        yaml.dump(state, f)


@pytest.fixture
def state_manager(tmp_state_dir: Path) -> StateManager:
    return StateManager(state_dir=tmp_state_dir)


@pytest.fixture
def registry() -> SessionRegistry:
    return SessionRegistry()


class TestRestoreFullState:
    async def test_restores_running_agents(
        self,
        agent_manager: AgentManager,
        registry: SessionRegistry,
        state_manager: StateManager,
    ) -> None:
        _write_state(state_manager, {
            "agents": {
                "my-agent": {
                    "provider": "mock",
                    "project_path": None,
                    "model": None,
                    "tabs": [],
                }
            },
            "associations": {},
        })

        await _restore_full_state(agent_manager, registry, state_manager, set())

        handle = agent_manager.get("my-agent")
        assert handle is not None
        assert handle.status == AgentStatus.RUNNING

    async def test_restores_associations_for_live_tabs(
        self,
        agent_manager: AgentManager,
        registry: SessionRegistry,
        state_manager: StateManager,
    ) -> None:
        _write_state(state_manager, {
            "agents": {
                "tab-agent": {
                    "provider": "mock",
                    "project_path": None,
                    "model": None,
                    "tabs": ["sess-alive"],
                }
            },
            "associations": {"sess-alive": "tab-agent", "sess-dead": "tab-agent"},
        })

        await _restore_full_state(
            agent_manager, registry, state_manager, {"sess-alive"}
        )

        assert registry.get_agent("sess-alive") == "tab-agent"
        assert registry.get_agent("sess-dead") is None

    async def test_missing_tab_skipped_gracefully(
        self,
        agent_manager: AgentManager,
        registry: SessionRegistry,
        state_manager: StateManager,
    ) -> None:
        _write_state(state_manager, {
            "agents": {
                "gone-agent": {
                    "provider": "mock",
                    "project_path": None,
                    "model": None,
                    "tabs": ["dead-sess"],
                }
            },
            "associations": {"dead-sess": "gone-agent"},
        })

        # No available sessions → association skipped, agent still restored
        await _restore_full_state(agent_manager, registry, state_manager, set())

        assert agent_manager.get("gone-agent") is not None
        assert registry.get_agent("dead-sess") is None

    async def test_failed_provider_spawn_continues_with_others(
        self,
        agent_manager: AgentManager,
        registry: SessionRegistry,
        state_manager: StateManager,
        mock_provider: object,
    ) -> None:
        fail_calls: list[str] = []

        async def failing_spawn(
            name: str,
            project_path: Path | None = None,
            model: str | None = None,
        ) -> object:
            fail_calls.append(name)
            raise RuntimeError("spawn failed intentionally")

        failing_provider = type(mock_provider)()  # type: ignore[call-arg]
        failing_provider.spawn = failing_spawn  # type: ignore[method-assign,union-attr]
        agent_manager.register_provider("failing", failing_provider)  # type: ignore[arg-type]

        _write_state(state_manager, {
            "agents": {
                "will-fail": {
                    "provider": "failing",
                    "project_path": None,
                    "model": None,
                    "tabs": [],
                },
                "will-succeed": {
                    "provider": "mock",
                    "project_path": None,
                    "model": None,
                    "tabs": [],
                },
            },
            "associations": {},
        })

        # Should not raise despite spawn failure
        await _restore_full_state(agent_manager, registry, state_manager, set())

        assert len(fail_calls) == 1
        fail_handle = agent_manager.get("will-fail")
        assert fail_handle is not None
        assert fail_handle.status == AgentStatus.ERROR

        ok_handle = agent_manager.get("will-succeed")
        assert ok_handle is not None
        assert ok_handle.status == AgentStatus.RUNNING

    async def test_unknown_provider_skips_agent(
        self,
        agent_manager: AgentManager,
        registry: SessionRegistry,
        state_manager: StateManager,
    ) -> None:
        _write_state(state_manager, {
            "agents": {
                "orphan-agent": {
                    "provider": "no-such-provider",
                    "project_path": None,
                    "model": None,
                    "tabs": [],
                }
            },
            "associations": {},
        })

        await _restore_full_state(agent_manager, registry, state_manager, set())

        assert agent_manager.get("orphan-agent") is None

    async def test_state_file_updated_after_recovery(
        self,
        agent_manager: AgentManager,
        registry: SessionRegistry,
        state_manager: StateManager,
    ) -> None:
        _write_state(state_manager, {
            "agents": {
                "persist-agent": {
                    "provider": "mock",
                    "project_path": None,
                    "model": "gpt-4o",
                    "tabs": [],
                }
            },
            "associations": {"dead-tab": "persist-agent"},
        })

        await _restore_full_state(agent_manager, registry, state_manager, set())

        reloaded = state_manager.load()
        # The dead-tab association should NOT be present after recovery
        assert "dead-tab" not in reloaded["associations"]
        # The successfully restored agent should still be present
        assert "persist-agent" in reloaded["agents"]
