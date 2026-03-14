"""Tab-agent association registry.

Tracks which terminal sessions (tabs) are associated with which agents.
A session can be associated with at most one agent. An agent can have
multiple associated sessions.
"""

from __future__ import annotations


class SessionRegistry:
    """Maps terminal session IDs to agent names."""

    def __init__(self) -> None:
        self._session_to_agent: dict[str, str] = {}

    def associate(self, session_id: str, agent_name: str) -> None:
        self._session_to_agent[session_id] = agent_name

    def disassociate(self, session_id: str) -> None:
        self._session_to_agent.pop(session_id, None)

    def get_agent(self, session_id: str) -> str | None:
        return self._session_to_agent.get(session_id)

    def get_sessions(self, agent_name: str) -> list[str]:
        return [
            sid for sid, name in self._session_to_agent.items()
            if name == agent_name
        ]

    def all_associations(self) -> dict[str, str]:
        return dict(self._session_to_agent)
