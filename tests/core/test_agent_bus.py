"""Tests for AgentBus message routing."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from tak.core.agent_bus import AgentBus, BusMessage

if TYPE_CHECKING:
    from tak.core.agent_manager import AgentManager
    from tak.core.session_registry import SessionRegistry
    from tests.conftest import MockProvider


class TestAgentBusRouting:
    async def test_route_to_associated_agent(
        self,
        agent_manager: AgentManager,
        session_registry: SessionRegistry,
        mock_provider: MockProvider,
    ) -> None:
        await agent_manager.spawn("cursor-myapp", "mock")
        session_registry.associate("sess-1", "cursor-myapp")
        bus = AgentBus(agent_manager, session_registry, {"mock": mock_provider})

        message = BusMessage(session_id="sess-1", text="explain this code")
        response = await bus.route(message)

        assert response.text == "mock response"
        assert response.agent_name == "cursor-myapp"
        assert response.session_id == "sess-1"

    async def test_route_to_explicit_agent(
        self,
        agent_manager: AgentManager,
        session_registry: SessionRegistry,
        mock_provider: MockProvider,
    ) -> None:
        await agent_manager.spawn("cursor-myapp", "mock")
        bus = AgentBus(agent_manager, session_registry, {"mock": mock_provider})

        message = BusMessage(
            session_id="sess-1", text="hello", agent_name="cursor-myapp"
        )
        response = await bus.route(message)
        assert response.agent_name == "cursor-myapp"

    async def test_route_no_association_raises(
        self,
        agent_manager: AgentManager,
        session_registry: SessionRegistry,
        mock_provider: MockProvider,
    ) -> None:
        bus = AgentBus(agent_manager, session_registry, {"mock": mock_provider})
        message = BusMessage(session_id="sess-1", text="hello")
        with pytest.raises(ValueError, match="No agent associated"):
            await bus.route(message)

    async def test_route_unknown_agent_raises(
        self,
        agent_manager: AgentManager,
        session_registry: SessionRegistry,
        mock_provider: MockProvider,
    ) -> None:
        session_registry.associate("sess-1", "nonexistent")
        bus = AgentBus(agent_manager, session_registry, {"mock": mock_provider})
        message = BusMessage(session_id="sess-1", text="hello")
        with pytest.raises(ValueError, match="not found"):
            await bus.route(message)

    async def test_provider_receives_correct_message(
        self,
        agent_manager: AgentManager,
        session_registry: SessionRegistry,
        mock_provider: MockProvider,
    ) -> None:
        await agent_manager.spawn("cursor-myapp", "mock")
        session_registry.associate("sess-1", "cursor-myapp")
        bus = AgentBus(agent_manager, session_registry, {"mock": mock_provider})

        await bus.route(BusMessage(session_id="sess-1", text="what is this?"))

        assert len(mock_provider.send_calls) == 1
        assert mock_provider.send_calls[0]["message"] == "what is this?"
        assert mock_provider.send_calls[0]["agent"] == "cursor-myapp"

    async def test_route_passes_cwd_to_provider(
        self,
        agent_manager: AgentManager,
        session_registry: SessionRegistry,
        mock_provider: MockProvider,
    ) -> None:
        await agent_manager.spawn("cursor-myapp", "mock")
        session_registry.associate("sess-1", "cursor-myapp")
        bus = AgentBus(agent_manager, session_registry, {"mock": mock_provider})

        await bus.route(
            BusMessage(session_id="sess-1", text="hi", cwd="/tmp/sub"),  # noqa: S108
        )

        assert mock_provider.send_calls[0]["cwd"] == "/tmp/sub"  # noqa: S108
