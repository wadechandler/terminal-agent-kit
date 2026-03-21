"""Tests for AgentManager lifecycle operations."""

from __future__ import annotations

from pathlib import Path

import pytest

from tak.core.agent_manager import (
    AgentManager,
    AgentStatus,
    PermissionPolicy,
    validate_agent_name,
)
from tak.core.session_registry import SessionRegistry
from tak.core.state import StateManager


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
        project = Path("/tmp/myproject")  # noqa: S108
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


class TestAgentManagerRemove:
    async def test_remove_stopped_agent(
        self, agent_manager: AgentManager
    ) -> None:
        await agent_manager.spawn("doomed", "mock")
        await agent_manager.stop("doomed")
        await agent_manager.remove("doomed")
        assert agent_manager.get("doomed") is None

    async def test_remove_running_agent_stops_first(
        self, agent_manager: AgentManager
    ) -> None:
        await agent_manager.spawn("live-one", "mock")
        assert agent_manager.get("live-one") is not None
        await agent_manager.remove("live-one")
        assert agent_manager.get("live-one") is None

    async def test_remove_unknown_raises(
        self, agent_manager: AgentManager
    ) -> None:
        with pytest.raises(ValueError, match="No agent named"):
            await agent_manager.remove("ghost")


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


class TestNameValidation:
    def test_valid_names_accepted(self) -> None:
        for name in ["abc", "my-agent", "agent123", "a" * 50, "cursor-docs"]:
            validate_agent_name(name)  # should not raise

    def test_reserved_names_pass(self) -> None:
        validate_agent_name("_adhoc")  # leading _ is reserved, always passes

    def test_name_too_short_raises(self) -> None:
        with pytest.raises(ValueError, match="Invalid agent name"):
            validate_agent_name("ab")

    def test_name_too_long_raises(self) -> None:
        with pytest.raises(ValueError, match="Invalid agent name"):
            validate_agent_name("a" * 51)

    def test_leading_hyphen_raises(self) -> None:
        with pytest.raises(ValueError, match="Invalid agent name"):
            validate_agent_name("-agent")

    def test_trailing_hyphen_raises(self) -> None:
        with pytest.raises(ValueError, match="Invalid agent name"):
            validate_agent_name("agent-")

    def test_uppercase_raises(self) -> None:
        with pytest.raises(ValueError, match="Invalid agent name"):
            validate_agent_name("MyAgent")

    def test_special_chars_raise(self) -> None:
        with pytest.raises(ValueError, match="Invalid agent name"):
            validate_agent_name("agent@1")

    async def test_spawn_with_invalid_name_raises(
        self, agent_manager: AgentManager
    ) -> None:
        with pytest.raises(ValueError, match="Invalid agent name"):
            await agent_manager.spawn("-bad", "mock")


class TestAgentManagerRename:
    async def test_rename_changes_name(self, agent_manager: AgentManager) -> None:
        await agent_manager.spawn("old-name", "mock")
        handle = await agent_manager.rename("old-name", "new-name")
        assert handle.name == "new-name"
        assert agent_manager.get("new-name") is handle
        assert agent_manager.get("old-name") is None

    async def test_rename_nonexistent_raises(
        self, agent_manager: AgentManager
    ) -> None:
        with pytest.raises(ValueError, match="No agent named"):
            await agent_manager.rename("ghost", "new-name")

    async def test_rename_to_existing_name_raises(
        self, agent_manager: AgentManager
    ) -> None:
        await agent_manager.spawn("agent-a", "mock")
        await agent_manager.spawn("agent-b", "mock")
        with pytest.raises(ValueError, match="already exists"):
            await agent_manager.rename("agent-a", "agent-b")

    async def test_rename_with_invalid_new_name_raises(
        self, agent_manager: AgentManager
    ) -> None:
        await agent_manager.spawn("my-agent", "mock")
        with pytest.raises(ValueError, match="Invalid agent name"):
            await agent_manager.rename("my-agent", "BAD_NAME!")


class TestGetByProvider:
    async def test_get_by_provider_returns_matching(
        self, agent_manager: AgentManager
    ) -> None:
        await agent_manager.spawn("agent-1", "mock")
        await agent_manager.spawn("agent-2", "mock")
        results = agent_manager.get_by_provider("mock")
        assert len(results) == 2
        assert all(h.provider_name == "mock" for h in results)

    async def test_get_by_provider_returns_empty_for_unknown(
        self, agent_manager: AgentManager
    ) -> None:
        await agent_manager.spawn("agent-1", "mock")
        assert agent_manager.get_by_provider("nonexistent") == []

    async def test_get_by_provider_filters_by_provider(
        self, agent_manager: AgentManager, mock_provider: object
    ) -> None:
        # Create a second provider instance of the same type via the fixture type
        second_provider = type(mock_provider)()  # type: ignore[call-arg]
        agent_manager.register_provider("second", second_provider)  # type: ignore[arg-type]

        await agent_manager.spawn("mock-agent", "mock")
        await agent_manager.spawn("second-agent", "second")

        mock_agents = agent_manager.get_by_provider("mock")
        second_agents = agent_manager.get_by_provider("second")

        assert len(mock_agents) == 1
        assert mock_agents[0].name == "mock-agent"
        assert len(second_agents) == 1
        assert second_agents[0].name == "second-agent"


class TestPermissionPolicy:
    async def test_default_policy_is_prompt(
        self, agent_manager: AgentManager
    ) -> None:
        handle = await agent_manager.spawn("test-agent", "mock")
        assert handle.permission_policy == PermissionPolicy.PROMPT

    async def test_spawn_with_custom_policy(
        self, agent_manager: AgentManager
    ) -> None:
        handle = await agent_manager.spawn(
            "yolo-agent", "mock", permission_policy=PermissionPolicy.YOLO
        )
        assert handle.permission_policy == PermissionPolicy.YOLO

    async def test_spawn_with_auto_allow_policy(
        self, agent_manager: AgentManager
    ) -> None:
        handle = await agent_manager.spawn(
            "auto-agent", "mock", permission_policy=PermissionPolicy.AUTO_ALLOW
        )
        assert handle.permission_policy == PermissionPolicy.AUTO_ALLOW

    async def test_spawn_with_reject_policy(
        self, agent_manager: AgentManager
    ) -> None:
        handle = await agent_manager.spawn(
            "reject-agent", "mock", permission_policy=PermissionPolicy.REJECT
        )
        assert handle.permission_policy == PermissionPolicy.REJECT

    def test_permission_policy_values(self) -> None:
        assert PermissionPolicy.PROMPT.value == "prompt"
        assert PermissionPolicy.REJECT.value == "reject"
        assert PermissionPolicy.AUTO_ALLOW.value == "auto-allow"
        assert PermissionPolicy.YOLO.value == "yolo"


class TestStateSaveCallbacks:
    async def test_spawn_triggers_state_save(
        self, agent_manager: AgentManager, tmp_state_dir: Path
    ) -> None:
        state_mgr = StateManager(state_dir=tmp_state_dir)
        registry = SessionRegistry()
        agent_manager.set_state_manager(state_mgr, registry)

        await agent_manager.spawn("my-agent", "mock")

        loaded = state_mgr.load()
        assert "my-agent" in loaded["agents"]

    async def test_stop_triggers_state_save(
        self, agent_manager: AgentManager, tmp_state_dir: Path
    ) -> None:
        state_mgr = StateManager(state_dir=tmp_state_dir)
        registry = SessionRegistry()
        agent_manager.set_state_manager(state_mgr, registry)

        await agent_manager.spawn("my-agent", "mock")
        await agent_manager.stop("my-agent")

        loaded = state_mgr.load()
        # Stopped agents are not persisted
        assert "my-agent" not in loaded["agents"]

    async def test_rename_triggers_state_save(
        self, agent_manager: AgentManager, tmp_state_dir: Path
    ) -> None:
        state_mgr = StateManager(state_dir=tmp_state_dir)
        registry = SessionRegistry()
        agent_manager.set_state_manager(state_mgr, registry)

        await agent_manager.spawn("old-name", "mock")
        await agent_manager.rename("old-name", "new-name")

        loaded = state_mgr.load()
        assert "new-name" in loaded["agents"]
        assert "old-name" not in loaded["agents"]

    async def test_model_id_persisted_in_state(
        self, agent_manager: AgentManager, tmp_state_dir: Path
    ) -> None:
        state_mgr = StateManager(state_dir=tmp_state_dir)
        registry = SessionRegistry()
        agent_manager.set_state_manager(state_mgr, registry)

        handle = await agent_manager.spawn("my-agent", "mock")
        handle.model = "Auto"
        handle.model_id = "default[]"
        agent_manager._auto_save()

        loaded = state_mgr.load()
        agent_data = loaded["agents"]["my-agent"]
        assert agent_data["model"] == "Auto"
        assert agent_data["model_id"] == "default[]"


class TestRestoreModelId:
    async def test_restore_prefers_model_id_over_display_name(
        self, agent_manager: AgentManager, mock_provider: object
    ) -> None:
        agents_state = {
            "test-agent": {
                "provider": "mock",
                "project_path": None,
                "model": "Auto",
                "model_id": "default[]",
                "tabs": [],
                "acp_session_id": None,
                "permission_policy": "prompt",
            },
        }
        await agent_manager.restore(agents_state)

        from tests.conftest import MockProvider

        provider = mock_provider
        assert isinstance(provider, MockProvider)
        assert len(provider.spawn_calls) == 1
        assert provider.spawn_calls[0]["model"] == "default[]"

    async def test_restore_falls_back_to_display_name_when_no_model_id(
        self, agent_manager: AgentManager, mock_provider: object
    ) -> None:
        agents_state = {
            "test-agent": {
                "provider": "mock",
                "project_path": None,
                "model": "Sonnet 4.6",
                "tabs": [],
                "acp_session_id": None,
                "permission_policy": "prompt",
            },
        }
        await agent_manager.restore(agents_state)

        from tests.conftest import MockProvider

        provider = mock_provider
        assert isinstance(provider, MockProvider)
        assert len(provider.spawn_calls) == 1
        assert provider.spawn_calls[0]["model"] == "Sonnet 4.6"

    async def test_restore_handles_none_model_id(
        self, agent_manager: AgentManager, mock_provider: object
    ) -> None:
        agents_state = {
            "test-agent": {
                "provider": "mock",
                "project_path": None,
                "model": None,
                "model_id": None,
                "tabs": [],
                "acp_session_id": None,
                "permission_policy": "prompt",
            },
        }
        await agent_manager.restore(agents_state)

        from tests.conftest import MockProvider

        provider = mock_provider
        assert isinstance(provider, MockProvider)
        assert len(provider.spawn_calls) == 1
        assert provider.spawn_calls[0]["model"] is None
