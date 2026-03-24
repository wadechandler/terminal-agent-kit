"""Terminal session provider for agents that run in their own TUI.

Agents using this provider (e.g. Claude Code, Goose interactive) run
in their own terminal tab and manage their own user interface.  tak
manages only the process lifecycle; sending messages via the provider
is not supported.
"""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

from tak.providers.base import BaseProvider, InteractionModel

if TYPE_CHECKING:
    from pathlib import Path

    from tak.core.agent_manager import AgentHandle

logger = logging.getLogger(__name__)


class TerminalSessionProvider(BaseProvider):
    """Provider for agents that run in their own terminal tab.

    Manages process lifecycle (spawn and stop) only.  Sending messages
    is not supported -- the user interacts with the agent directly via
    its own TUI.
    """

    def __init__(self, name: str, command: list[str]) -> None:
        """Create a terminal session provider.

        Args:
            name: Human-readable display name.
            command: The full command to launch the agent.
        """
        self._name = name
        self._command = command

    @property
    def name(self) -> str:
        """Return provider display name."""
        return self._name

    @property
    def protocol(self) -> str:
        """Return wire protocol identifier (agent uses its own TUI)."""
        return "terminal"

    @property
    def interaction_model(self) -> InteractionModel:
        """Terminal agents own their own UI; tak manages lifecycle only."""
        return InteractionModel.TERMINAL

    async def spawn(
        self,
        agent_name: str,
        project_path: Path | None = None,
        model: str | None = None,
    ) -> asyncio.subprocess.Process:
        """Spawn the agent subprocess.

        The process inherits no stdio pipes so it can render its own TUI.
        The daemon is responsible for opening a new terminal tab before
        calling ``spawn()``.

        Args:
            agent_name: Name for this agent instance.
            project_path: Optional working directory for the agent process.
            model: Ignored -- model selection is handled inside the agent TUI.

        Returns:
            The subprocess handle.
        """
        logger.info(
            "Spawning terminal agent %s: %s", agent_name, " ".join(self._command)
        )
        return await asyncio.create_subprocess_exec(
            *self._command,
            cwd=str(project_path) if project_path else None,
        )

    async def send(
        self,
        handle: AgentHandle,
        message: str,
        *,
        cwd: str | None = None,
        mode: str | None = None,
    ) -> str:
        """Not supported for terminal agents.

        Args:
            handle: The agent handle (unused).
            message: The message (unused).
            cwd: Unused (ACP-only).
            mode: Unused (ACP-only).

        Raises:
            NotImplementedError: Always -- the user interacts directly via the TUI.
        """
        del cwd, mode
        raise NotImplementedError(
            f"TerminalSessionProvider '{self._name}' does not support send(); "
            "interact with the agent directly in its terminal tab."
        )

    async def stop(self, handle: AgentHandle) -> None:
        """Send SIGTERM to the agent process, with SIGKILL fallback.

        Args:
            handle: The agent to stop.
        """
        if handle.process is None:
            return
        handle.process.terminate()
        try:
            await asyncio.wait_for(handle.process.wait(), timeout=10.0)
        except TimeoutError:
            handle.process.kill()
            await handle.process.wait()
