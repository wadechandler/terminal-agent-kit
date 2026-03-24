"""Message routing between terminal tabs and agents.

The AgentBus receives messages from tabs (via the terminal driver), looks up
the tab's associated agent, sends the message to the agent's provider, and
returns the response.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from tak.core.agent_manager import AgentManager
    from tak.core.session_registry import SessionRegistry
    from tak.providers.base import BaseProvider


@dataclass
class BusMessage:
    """Incoming message from a terminal session to an agent."""

    session_id: str
    text: str
    agent_name: str | None = None
    cwd: str | None = None


@dataclass
class BusResponse:
    """Response from an agent back to a terminal session."""

    text: str
    agent_name: str
    session_id: str


class AgentBus:
    """Routes messages from terminal sessions to their associated agents."""

    def __init__(
        self,
        agent_manager: AgentManager,
        session_registry: SessionRegistry,
        providers: dict[str, BaseProvider],
    ) -> None:
        """Create a bus with the given manager, registry, and provider map."""
        self._manager = agent_manager
        self._registry = session_registry
        self._providers = providers

    async def route(self, message: BusMessage) -> BusResponse:
        """Route a message to the associated agent and return the response."""
        agent_name = message.agent_name or self._registry.get_agent(message.session_id)

        if agent_name is None:
            raise ValueError(
                f"No agent associated with session '{message.session_id}' "
                "and no agent_name specified"
            )

        handle = self._manager.get(agent_name)
        if handle is None:
            raise ValueError(f"Agent '{agent_name}' not found")

        provider = self._providers[handle.provider_name]
        response_text = await provider.send(handle, message.text, cwd=message.cwd)

        return BusResponse(
            text=response_text,
            agent_name=agent_name,
            session_id=message.session_id,
        )
