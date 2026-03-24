"""Ad-hoc agent manager for quick questions without a named spawn.

Provides a lightweight "default agent" that is auto-spawned on first use
and optionally stopped after a configurable inactivity period.
"""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

from tak.core.agent_manager import AgentStatus

if TYPE_CHECKING:
    from tak.core.agent_manager import AgentHandle, AgentManager

logger = logging.getLogger(__name__)

ADHOC_NAME = "_adhoc"


class AdHocManager:
    """Manages a lightweight default agent for quick questions.

    The ad-hoc agent is identified by the reserved name ``_adhoc`` and is
    automatically spawned the first time :meth:`ensure_agent` is called.
    After ``auto_stop_after`` seconds of inactivity the agent is stopped
    and will be re-spawned on the next call.
    """

    def __init__(
        self,
        agent_manager: AgentManager,
        provider_name: str = "cursor-acp",
        model: str | None = None,
        auto_stop_after: float = 300.0,
    ) -> None:
        """Create an AdHocManager.

        Args:
            agent_manager: The shared ``AgentManager`` instance.
            provider_name: Provider to use when spawning the ad-hoc agent.
            model: Optional model name to pass to the provider.
            auto_stop_after: Seconds of inactivity before auto-stopping.
                Set to 0 to disable auto-stop.
        """
        self._manager = agent_manager
        self._provider_name = provider_name
        self._model = model
        self._auto_stop_after = auto_stop_after
        self._last_use: float = 0.0
        self._auto_stop_task: asyncio.Task[None] | None = None

    async def ensure_agent(self) -> AgentHandle:
        """Return the ad-hoc agent handle, spawning it if necessary.

        Returns:
            A running ``AgentHandle`` for the ``_adhoc`` agent.

        Raises:
            ValueError: If the provider is not registered with the
                ``AgentManager``.
        """
        handle = self._manager.get(ADHOC_NAME)
        if handle is not None and handle.status == AgentStatus.RUNNING:
            self._touch()
            return handle

        handle = await self._manager.spawn(
            ADHOC_NAME,
            self._provider_name,
            project_path=None,
            model=self._model,
        )
        self._touch()
        self._schedule_auto_stop()
        return handle

    async def ask(
        self,
        query: str,
        *,
        cwd: str | None = None,
        mode: str | None = None,
    ) -> str:
        """Send a question to the ad-hoc agent and return the response.

        Spawns the agent if it is not already running.

        Args:
            query: The question or prompt text.
            cwd: Optional caller working directory for per-prompt context.
            mode: Optional session mode when a new ACP session is created.

        Returns:
            The provider's response string.

        Raises:
            ValueError: If the provider is not registered.
        """
        agent = await self.ensure_agent()
        provider = self._manager.get_provider(self._provider_name)
        if provider is None:
            raise ValueError(f"Provider {self._provider_name!r} not registered")
        response = await provider.send(agent, query, cwd=cwd, mode=mode)
        self._touch()
        return response

    def _touch(self) -> None:
        """Record the current time as the last-use timestamp."""
        loop = asyncio.get_event_loop()
        self._last_use = loop.time()

    def _schedule_auto_stop(self) -> None:
        """Schedule the inactivity auto-stop task."""
        if self._auto_stop_after <= 0:
            return
        if self._auto_stop_task is not None and not self._auto_stop_task.done():
            self._auto_stop_task.cancel()
        self._auto_stop_task = asyncio.create_task(self._auto_stop_loop())

    async def _auto_stop_loop(self) -> None:
        """Periodically check inactivity and stop the agent when idle."""
        while True:
            await asyncio.sleep(self._auto_stop_after)
            loop = asyncio.get_event_loop()
            elapsed = loop.time() - self._last_use
            if elapsed >= self._auto_stop_after:
                handle = self._manager.get(ADHOC_NAME)
                if handle is not None and handle.status == AgentStatus.RUNNING:
                    logger.info(
                        "Ad-hoc agent idle for %.0fs; auto-stopping", elapsed
                    )
                    try:
                        await self._manager.stop(ADHOC_NAME)
                    except Exception as exc:
                        logger.warning("Failed to auto-stop ad-hoc agent: %s", exc)
                break
