"""State persistence for restart recovery.

Writes agent state (running agents, associations, project paths) to
~/.tak/state.yaml so the daemon can restore state after iTerm2 restarts.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from tak.core.agent_manager import AgentHandle, AgentStatus

DEFAULT_STATE_DIR = Path.home() / ".tak"
STATE_FILE = "state.yaml"


class StateManager:
    """Persists and restores agent state to disk."""

    def __init__(self, state_dir: Path | None = None) -> None:
        self._state_dir = state_dir or DEFAULT_STATE_DIR
        self._state_file = self._state_dir / STATE_FILE

    def save(
        self,
        agents: list[AgentHandle],
        associations: dict[str, str],
    ) -> None:
        self._state_dir.mkdir(parents=True, exist_ok=True)

        state: dict[str, Any] = {
            "agents": {
                a.name: {
                    "provider": a.provider_name,
                    "project_path": str(a.project_path) if a.project_path else None,
                    "status": a.status.value,
                    "tabs": a.associated_tabs,
                }
                for a in agents
                if a.status == AgentStatus.RUNNING
            },
            "associations": associations,
        }

        with open(self._state_file, "w") as f:
            yaml.dump(state, f, default_flow_style=False)

    def load(self) -> dict[str, Any]:
        if not self._state_file.exists():
            return {"agents": {}, "associations": {}}

        with open(self._state_file) as f:
            return yaml.safe_load(f) or {"agents": {}, "associations": {}}

    def clear(self) -> None:
        if self._state_file.exists():
            self._state_file.unlink()
