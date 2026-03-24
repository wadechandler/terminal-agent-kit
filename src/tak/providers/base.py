"""Abstract base for agent providers.

Each provider knows how to spawn, communicate with, and stop a specific
type of agent. Providers are terminal-agnostic -- they deal only with
subprocess management and message passing.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import asyncio
    from collections.abc import AsyncIterator
    from pathlib import Path

    from tak.core.agent_manager import AgentHandle


class InteractionModel(Enum):
    """How the agent interacts with the user.

    HEADLESS: Agent is a subprocess; tak mediates all permission and
        interaction requests (e.g. Cursor via ACP).
    TERMINAL: Agent runs in its own terminal tab with its own TUI;
        tak manages lifecycle only (e.g. Claude Code, Goose).
    """

    HEADLESS = "headless"
    TERMINAL = "terminal"


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

    @property
    def interaction_model(self) -> InteractionModel:
        """How this agent interacts with the user.

        Headless agents need tak to relay permission requests.
        Terminal agents handle their own UI.
        """
        return InteractionModel.HEADLESS

    @abstractmethod
    async def spawn(
        self,
        agent_name: str,
        project_path: Path | None = None,
        model: str | None = None,
    ) -> asyncio.subprocess.Process:
        """Start an agent subprocess.

        Args:
            agent_name: Name for this agent instance.
            project_path: Optional project directory.
            model: Optional model name to use.

        Returns:
            The subprocess handle.
        """

    @abstractmethod
    async def send(
        self,
        handle: AgentHandle,
        message: str,
        *,
        cwd: str | None = None,
        mode: str | None = None,
    ) -> str:
        """Send a message to the agent and return the complete response.

        Args:
            handle: The target agent handle.
            message: User prompt text.
            cwd: Optional caller working directory for context (headless agents).
            mode: Optional session mode when a new ACP session must be created.
        """

    async def send_streaming(
        self,
        handle: AgentHandle,
        message: str,
        *,
        cwd: str | None = None,
        mode: str | None = None,
    ) -> AsyncIterator[str]:
        """Send a message and yield response chunks. Override for streaming support."""
        yield await self.send(handle, message, cwd=cwd, mode=mode)

    @abstractmethod
    async def stop(self, handle: AgentHandle) -> None:
        """Stop the agent subprocess cleanly."""

    async def health_check(self, handle: AgentHandle) -> bool:  # NOSONAR(S7503)
        """Check if the agent is still responsive. Default checks process status.

        Async because subclasses may need network/IPC checks.
        """
        if handle.process is None:
            return False
        return handle.process.returncode is None

    async def list_models(self) -> list[str]:  # NOSONAR(S7503)
        """Return available model names for this provider.

        Default returns an empty list. Override for providers that
        support model selection (e.g. ``cursor agent models``).
        Async because subclasses may query remote APIs.
        """
        return []
