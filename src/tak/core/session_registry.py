"""Tab-agent association registry.

Tracks which terminal sessions (tabs) are associated with which agents.
A session can be associated with at most one agent. An agent can have
multiple associated sessions.
"""

from __future__ import annotations


class SessionRegistry:
    """Maps terminal session IDs to agent names."""

    def __init__(self) -> None:
        """Initialize with an empty association map."""
        self._session_to_agent: dict[str, str] = {}

    def associate(self, session_id: str, agent_name: str) -> None:
        """Associate a terminal session with an agent."""
        self._session_to_agent[session_id] = agent_name

    def disassociate(self, session_id: str) -> None:
        """Remove a session's agent association."""
        self._session_to_agent.pop(session_id, None)

    def get_agent(self, session_id: str) -> str | None:
        """Return the agent name for a session, or ``None``."""
        return self._session_to_agent.get(session_id)

    def get_sessions(self, agent_name: str) -> list[str]:
        """Return all session IDs associated with the named agent."""
        return [
            sid for sid, name in self._session_to_agent.items()
            if name == agent_name
        ]

    def all_associations(self) -> dict[str, str]:
        """Return a copy of all session-to-agent mappings."""
        return dict(self._session_to_agent)
