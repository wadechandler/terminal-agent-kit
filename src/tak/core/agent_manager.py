"""Agent lifecycle management.

Handles spawning, stopping, health-checking, and listing agent instances.
Each agent is a managed subprocess with a user-assigned name, a provider
type, and an optional project path.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from tak.providers.base import BaseProvider


class AgentStatus(Enum):
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"
    STOPPED = "stopped"
    ERROR = "error"


@dataclass
class AgentHandle:
    name: str
    provider_name: str
    project_path: Path | None
    status: AgentStatus = AgentStatus.STOPPED
    process: asyncio.subprocess.Process | None = None
    associated_tabs: list[str] = field(default_factory=list)


class AgentManager:
    """Manages the lifecycle of agent instances."""

    def __init__(self) -> None:
        self._agents: dict[str, AgentHandle] = {}
        self._providers: dict[str, BaseProvider] = {}

    def register_provider(self, name: str, provider: BaseProvider) -> None:
        self._providers[name] = provider

    async def spawn(
        self,
        name: str,
        provider_name: str,
        project_path: Path | None = None,
    ) -> AgentHandle:
        if name in self._agents:
            raise ValueError(f"Agent '{name}' already exists")

        provider = self._providers.get(provider_name)
        if provider is None:
            raise ValueError(f"Unknown provider: {provider_name}")

        handle = AgentHandle(
            name=name,
            provider_name=provider_name,
            project_path=project_path,
            status=AgentStatus.STARTING,
        )
        self._agents[name] = handle

        try:
            handle.process = await provider.spawn(name, project_path)
            handle.status = AgentStatus.RUNNING
        except Exception:
            handle.status = AgentStatus.ERROR
            raise

        return handle

    async def stop(self, name: str) -> None:
        handle = self._agents.get(name)
        if handle is None:
            raise ValueError(f"No agent named '{name}'")

        handle.status = AgentStatus.STOPPING
        provider = self._providers[handle.provider_name]
        await provider.stop(handle)
        handle.status = AgentStatus.STOPPED

    def get(self, name: str) -> AgentHandle | None:
        return self._agents.get(name)

    def list_agents(self) -> list[AgentHandle]:
        return list(self._agents.values())

    def running_agents(self) -> list[AgentHandle]:
        return [a for a in self._agents.values() if a.status == AgentStatus.RUNNING]
