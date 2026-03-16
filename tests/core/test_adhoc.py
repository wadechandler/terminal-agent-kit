"""Tests for AdHocManager."""

from __future__ import annotations

import asyncio

import pytest

from tak.core.adhoc import ADHOC_NAME, AdHocManager
from tak.core.agent_manager import AgentManager, AgentStatus


@pytest.fixture
def adhoc_manager(agent_manager: AgentManager) -> AdHocManager:
    return AdHocManager(
        agent_manager=agent_manager,
        provider_name="mock",
        auto_stop_after=300.0,
    )


class TestEnsureAgent:
    async def test_ensure_agent_spawns_on_first_call(
        self, adhoc_manager: AdHocManager, agent_manager: AgentManager
    ) -> None:
        handle = await adhoc_manager.ensure_agent()
        assert handle.name == ADHOC_NAME
        assert handle.status == AgentStatus.RUNNING
        assert agent_manager.get(ADHOC_NAME) is handle

    async def test_ensure_agent_returns_existing_on_second_call(
        self, adhoc_manager: AdHocManager
    ) -> None:
        first = await adhoc_manager.ensure_agent()
        second = await adhoc_manager.ensure_agent()
        assert first is second

    async def test_ensure_agent_respawns_after_stop(
        self, adhoc_manager: AdHocManager, agent_manager: AgentManager
    ) -> None:
        first = await adhoc_manager.ensure_agent()
        await agent_manager.stop(ADHOC_NAME)

        second = await adhoc_manager.ensure_agent()
        assert second is not first
        assert second.status == AgentStatus.RUNNING

    async def test_ensure_agent_uses_configured_provider(
        self, agent_manager: AgentManager
    ) -> None:
        mgr = AdHocManager(agent_manager=agent_manager, provider_name="mock")
        handle = await mgr.ensure_agent()
        assert handle.provider_name == "mock"

    async def test_ensure_agent_uses_configured_model(
        self, agent_manager: AgentManager
    ) -> None:
        mgr = AdHocManager(
            agent_manager=agent_manager,
            provider_name="mock",
            model="claude-sonnet-4",
        )
        handle = await mgr.ensure_agent()
        assert handle.model == "claude-sonnet-4"


class TestAsk:
    async def test_ask_routes_through_provider(
        self,
        adhoc_manager: AdHocManager,
        mock_provider: object,
    ) -> None:
        response = await adhoc_manager.ask("how do I fix this?")
        assert response == "mock response"
        assert hasattr(mock_provider, "send_calls")
        assert len(mock_provider.send_calls) == 1  # type: ignore[union-attr]
        assert mock_provider.send_calls[0]["message"] == "how do I fix this?"  # type: ignore[union-attr]

    async def test_ask_spawns_agent_if_not_running(
        self, adhoc_manager: AdHocManager, agent_manager: AgentManager
    ) -> None:
        assert agent_manager.get(ADHOC_NAME) is None
        await adhoc_manager.ask("question")
        assert agent_manager.get(ADHOC_NAME) is not None

    async def test_ask_with_unknown_provider_raises(
        self, agent_manager: AgentManager
    ) -> None:
        mgr = AdHocManager(
            agent_manager=agent_manager,
            provider_name="no-such-provider",
        )
        with pytest.raises(ValueError, match="Unknown provider"):
            await mgr.ask("question")


class TestAutoStop:
    async def test_auto_stop_after_inactivity(
        self, agent_manager: AgentManager
    ) -> None:
        mgr = AdHocManager(
            agent_manager=agent_manager,
            provider_name="mock",
            auto_stop_after=0.05,  # 50 ms for test speed
        )
        await mgr.ensure_agent()
        assert agent_manager.get(ADHOC_NAME).status == AgentStatus.RUNNING  # type: ignore[union-attr]

        # Wait longer than auto_stop_after
        await asyncio.sleep(0.2)

        handle = agent_manager.get(ADHOC_NAME)
        assert handle is not None
        assert handle.status == AgentStatus.STOPPED

    async def test_auto_stop_disabled_when_zero(
        self, agent_manager: AgentManager
    ) -> None:
        mgr = AdHocManager(
            agent_manager=agent_manager,
            provider_name="mock",
            auto_stop_after=0.0,
        )
        await mgr.ensure_agent()
        assert mgr._auto_stop_task is None
