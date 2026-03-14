"""Abstract base for agent providers.

Each provider knows how to spawn, communicate with, and stop a specific
type of agent. Providers are terminal-agnostic -- they deal only with
subprocess management and message passing.
"""

from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod
from pathlib import Path
from typing import TYPE_CHECKING, AsyncIterator

if TYPE_CHECKING:
    from tak.core.agent_manager import AgentHandle


class BaseProvider(ABC):
    """Interface that all agent providers must implement."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable provider name."""

    @property
    @abstractmethod
    def protocol(self) -> str:
        """Protocol identifier (e.g., 'json-rpc', 'stdio', 'http')."""

    @abstractmethod
    async def spawn(
        self,
        agent_name: str,
        project_path: Path | None = None,
    ) -> asyncio.subprocess.Process:
        """Start an agent subprocess. Returns the process handle."""

    @abstractmethod
    async def send(self, handle: AgentHandle, message: str) -> str:
        """Send a message to the agent and return the complete response."""

    async def send_streaming(
        self, handle: AgentHandle, message: str
    ) -> AsyncIterator[str]:
        """Send a message and yield response chunks. Override for streaming support."""
        yield await self.send(handle, message)

    @abstractmethod
    async def stop(self, handle: AgentHandle) -> None:
        """Stop the agent subprocess cleanly."""

    async def health_check(self, handle: AgentHandle) -> bool:
        """Check if the agent is still responsive. Default checks process status."""
        if handle.process is None:
            return False
        return handle.process.returncode is None
