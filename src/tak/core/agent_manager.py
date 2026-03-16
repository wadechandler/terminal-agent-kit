"""Agent lifecycle management.

Handles spawning, stopping, health-checking, and listing agent instances.
Each agent is a managed subprocess with a user-assigned name, a provider
type, and an optional project path.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import asyncio
    from pathlib import Path

    from tak.core.session_registry import SessionRegistry
    from tak.core.state import StateManager
    from tak.providers.base import BaseProvider

logger = logging.getLogger(__name__)

# Reserved names start with underscore (e.g. _adhoc).  All other names must
# match this pattern: 3-50 lowercase alphanumeric + hyphens, no leading /
# trailing hyphens.
_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9-]{1,48}[a-z0-9]$")
_RESERVED_PREFIX = "_"


def validate_agent_name(name: str) -> None:
    """Raise ``ValueError`` if *name* is not a valid user-facing agent name.

    Names must be 3-50 characters, lowercase alphanumeric plus hyphens,
    with no leading or trailing hyphens.  Names that start with ``_`` are
    reserved for internal use and always pass validation.

    Args:
        name: The candidate agent name.

    Raises:
        ValueError: If *name* violates the naming rules.
    """
    if name.startswith(_RESERVED_PREFIX):
        return
    if not _NAME_RE.fullmatch(name):
        raise ValueError(
            f"Invalid agent name {name!r}: must be 3-50 lowercase alphanumeric + hyphens, "
            "no leading/trailing hyphens"
        )


class AgentStatus(Enum):
    """Lifecycle states for managed agents."""

    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"
    STOPPED = "stopped"
    ERROR = "error"


@dataclass
class AgentHandle:
    """Tracks a managed agent instance."""

    name: str
    provider_name: str
    project_path: Path | None
    model: str | None = None
    status: AgentStatus = AgentStatus.STOPPED
    process: asyncio.subprocess.Process | None = None
    associated_tabs: list[str] = field(default_factory=list)


class AgentManager:
    """Manages the lifecycle of agent instances."""

    def __init__(self) -> None:
        """Initialize with empty agent and provider registries."""
        self._agents: dict[str, AgentHandle] = {}
        self._providers: dict[str, BaseProvider] = {}
        self._state_manager: StateManager | None = None
        self._session_registry: SessionRegistry | None = None

    def set_state_manager(
        self,
        state_manager: StateManager,
        session_registry: SessionRegistry,
    ) -> None:
        """Wire up automatic state persistence after every state change.

        Args:
            state_manager: The ``StateManager`` instance to persist to.
            session_registry: Used to snapshot associations on each save.
        """
        self._state_manager = state_manager
        self._session_registry = session_registry

    def _auto_save(self) -> None:
        """Persist current state if a StateManager has been wired up."""
        if self._state_manager is not None and self._session_registry is not None:
            self._state_manager.auto_save(
                self.list_agents(),
                self._session_registry.all_associations(),
            )

    def register_provider(self, name: str, provider: BaseProvider) -> None:
        """Register a named provider for spawning agents."""
        self._providers[name] = provider

    async def spawn(
        self,
        name: str,
        provider_name: str,
        project_path: Path | None = None,
        model: str | None = None,
    ) -> AgentHandle:
        """Spawn a new agent subprocess.

        Args:
            name: User-assigned name for the agent instance.
            provider_name: Registered provider to use.
            project_path: Optional project directory for the agent.
            model: Optional model name (e.g. ``claude-sonnet-4``).

        Returns:
            The ``AgentHandle`` for the new agent.

        Raises:
            ValueError: If the name is invalid, already taken, or the provider
                is unknown.
        """
        validate_agent_name(name)

        if name in self._agents:
            existing = self._agents[name]
            if existing.status not in (AgentStatus.STOPPED, AgentStatus.ERROR):
                raise ValueError(f"Agent '{name}' already exists")

        provider = self._providers.get(provider_name)
        if provider is None:
            raise ValueError(f"Unknown provider: {provider_name}")

        handle = AgentHandle(
            name=name,
            provider_name=provider_name,
            project_path=project_path,
            model=model,
            status=AgentStatus.STARTING,
        )
        self._agents[name] = handle

        try:
            handle.process = await provider.spawn(
                name, project_path=project_path, model=model
            )
            handle.status = AgentStatus.RUNNING
        except Exception:
            handle.status = AgentStatus.ERROR
            raise

        self._auto_save()
        return handle

    async def stop(self, name: str) -> None:
        """Stop a running agent by name.

        Args:
            name: The agent name to stop.

        Raises:
            ValueError: If no agent exists with the given name.
        """
        handle = self._agents.get(name)
        if handle is None:
            raise ValueError(f"No agent named '{name}'")

        handle.status = AgentStatus.STOPPING
        provider = self._providers[handle.provider_name]
        await provider.stop(handle)
        handle.status = AgentStatus.STOPPED
        self._auto_save()

    async def rename(self, old_name: str, new_name: str) -> AgentHandle:
        """Rename an existing agent.

        Args:
            old_name: Current agent name.
            new_name: Desired new name; must pass ``validate_agent_name``.

        Returns:
            The updated ``AgentHandle`` with the new name.

        Raises:
            ValueError: If *old_name* doesn't exist, *new_name* is already
                taken, or *new_name* fails validation.
        """
        validate_agent_name(new_name)

        handle = self._agents.get(old_name)
        if handle is None:
            raise ValueError(f"No agent named '{old_name}'")
        if new_name in self._agents:
            raise ValueError(f"Agent '{new_name}' already exists")

        self._agents.pop(old_name)
        handle.name = new_name
        self._agents[new_name] = handle
        self._auto_save()
        return handle

    async def restore(self, agents_state: dict[str, Any]) -> None:
        """Restore agent handles from persisted state.

        Spawns a provider subprocess for each saved agent.  If one agent
        fails to restore the error is logged and processing continues.

        Args:
            agents_state: Mapping of agent name → state dict as produced
                by ``StateManager.save()``.
        """
        for name, agent_data in agents_state.items():
            provider_name = agent_data.get("provider", "")
            provider = self._providers.get(provider_name)
            if provider is None:
                logger.warning(
                    "Provider %r not registered; cannot restore agent %r",
                    provider_name,
                    name,
                )
                continue

            from pathlib import Path as _Path

            project_path_str = agent_data.get("project_path")
            project_path = _Path(project_path_str) if project_path_str else None
            model: str | None = agent_data.get("model")
            tabs: list[str] = list(agent_data.get("tabs", []))

            handle = AgentHandle(
                name=name,
                provider_name=provider_name,
                project_path=project_path,
                model=model,
                status=AgentStatus.STARTING,
                associated_tabs=tabs,
            )
            self._agents[name] = handle

            try:
                handle.process = await provider.spawn(
                    name, project_path=project_path, model=model
                )
                handle.status = AgentStatus.RUNNING
                logger.info("Restored agent %r (provider=%s)", name, provider_name)
            except Exception as exc:
                logger.error("Failed to restore agent %r: %s", name, exc)
                handle.status = AgentStatus.ERROR

    def get(self, name: str) -> AgentHandle | None:
        """Look up an agent handle by name, or ``None`` if not found."""
        return self._agents.get(name)

    def get_provider(self, name: str) -> BaseProvider | None:
        """Look up a registered provider by name, or ``None`` if not found."""
        return self._providers.get(name)

    def list_agents(self) -> list[AgentHandle]:
        """Return all agent handles regardless of status."""
        return list(self._agents.values())

    def running_agents(self) -> list[AgentHandle]:
        """Return only agents with RUNNING status."""
        return [a for a in self._agents.values() if a.status == AgentStatus.RUNNING]

    def get_by_provider(self, provider_name: str) -> list[AgentHandle]:
        """Return all agents using the given provider.

        Args:
            provider_name: The registered provider name to filter by.

        Returns:
            List of ``AgentHandle`` instances whose ``provider_name`` matches.
        """
        return [a for a in self._agents.values() if a.provider_name == provider_name]
