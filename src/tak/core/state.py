"""State persistence for restart recovery.

Writes agent state (running agents, associations, project paths) to
``~/.tak/state.yaml`` so the daemon can restore state after iTerm2 restarts.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

from tak.core.agent_manager import AgentHandle, AgentStatus

DEFAULT_STATE_DIR = Path.home() / ".tak"
STATE_FILE = "state.yaml"

logger = logging.getLogger(__name__)


class StateManager:
    """Persists and restores agent state to disk."""

    def __init__(self, state_dir: Path | None = None) -> None:
        """Initialize with a state directory.

        Args:
            state_dir: Directory for state file; defaults to ``~/.tak``.
        """
        self._state_dir = state_dir or DEFAULT_STATE_DIR
        self._state_file = self._state_dir / STATE_FILE

    def save(
        self,
        agents: list[AgentHandle],
        associations: dict[str, str],
    ) -> None:
        """Persist running agents and associations to disk.

        Only agents with ``RUNNING`` status are persisted.  The state file
        includes agent names, providers, project paths, models, tab
        associations, and a UTC timestamp for debugging.

        Args:
            agents: All known agent handles; non-running ones are excluded.
            associations: Session-ID → agent-name mapping from the registry.
        """
        self._state_dir.mkdir(parents=True, exist_ok=True)

        state: dict[str, Any] = {
            "saved_at": datetime.now(tz=UTC).isoformat(),
            "agents": {
                a.name: {
                    "provider": a.provider_name,
                    "project_path": str(a.project_path) if a.project_path else None,
                    "model": a.model,
                    "status": a.status.value,
                    "tabs": a.associated_tabs,
                    "acp_session_id": a.acp_session_id,
                    "permission_policy": a.permission_policy.value,
                }
                for a in agents
                if a.status == AgentStatus.RUNNING
            },
            "associations": associations,
        }

        with open(self._state_file, "w") as f:
            yaml.dump(state, f, default_flow_style=False)

    def auto_save(
        self,
        agents: list[AgentHandle],
        associations: dict[str, str],
    ) -> None:
        """Save state; intended for automatic saves on every state change.

        Identical to :meth:`save` but semantically signals an automatic,
        event-driven save rather than an explicit user-triggered one.

        Args:
            agents: All known agent handles.
            associations: Session-ID → agent-name mapping.
        """
        self.save(agents, associations)

    def load(self) -> dict[str, Any]:
        """Load persisted state from disk.

        Returns:
            A dict with ``agents`` and ``associations`` keys.  Returns an
            empty structure when the file does not exist or is unreadable.
        """
        if not self._state_file.exists():
            return {"agents": {}, "associations": {}}

        try:
            with open(self._state_file) as f:
                data = yaml.safe_load(f)
            if not isinstance(data, dict):
                logger.warning("State file %s is malformed; ignoring", self._state_file)
                return {"agents": {}, "associations": {}}
            return data
        except Exception as exc:
            logger.warning("Failed to load state from %s: %s", self._state_file, exc)
            return {"agents": {}, "associations": {}}

    @property
    def state_file(self) -> Path:
        """Return the path to the state file (may not exist yet)."""
        return self._state_file

    def clear(self) -> None:
        """Remove the state file."""
        if self._state_file.exists():
            self._state_file.unlink()
