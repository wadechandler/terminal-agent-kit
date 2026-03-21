"""Generic ACP provider for any ACP-compliant agent.

ACP (Agent Client Protocol) uses JSON-RPC 2.0 over stdio. This provider
can spawn any ACP-compatible agent binary and manage the full session
lifecycle via the official ``agent-client-protocol`` SDK.

Reference: https://agentclientprotocol.com/protocol
"""

from __future__ import annotations

import asyncio
import logging
import os
import shutil
from contextlib import AsyncExitStack
from typing import TYPE_CHECKING

from acp import spawn_agent_process

from tak.providers.acp_session import (
    ACPSessionManager,
    AskQuestionCallback,
    PermissionCallback,
    TakACPClient,
)
from tak.providers.base import BaseProvider, InteractionModel

if TYPE_CHECKING:
    from collections.abc import AsyncIterator
    from pathlib import Path

    from tak.core.agent_manager import AgentHandle

logger = logging.getLogger(__name__)

_EXTRA_PATH_DIRS = (
    "/usr/local/bin",
    "/opt/homebrew/bin",
    "/opt/homebrew/sbin",
    os.path.expanduser("~/.local/bin"),
)


def _subprocess_env() -> dict[str, str]:
    """Build an environment dict for child processes with a complete PATH.

    When the daemon runs inside iTerm2's bundled Python the inherited PATH
    is minimal (often just ``/usr/bin:/bin``).  This function extends it
    with common macOS locations so that commands like ``cursor`` and
    ``claude`` are found.
    """
    env = os.environ.copy()
    path_parts = env.get("PATH", "").split(os.pathsep)
    for extra in _EXTRA_PATH_DIRS:
        if extra not in path_parts and os.path.isdir(extra):
            path_parts.append(extra)
    env["PATH"] = os.pathsep.join(path_parts)
    return env


class ACPProvider(BaseProvider):
    """Generic ACP provider for any ACP-compliant agent.

    Each spawned agent gets its own ``ACPSessionManager`` backed by the
    official ACP SDK, handling the JSON-RPC session lifecycle, streamed
    updates, and permission request relay.

    Args:
        name: Human-readable provider name (e.g. ``"Cursor (ACP)"``).
        command: The full spawn command, e.g. ``["cursor", "agent", "acp"]``
            or ``["goose", "acp"]``.
        auth_method: Authentication method -- ``"env"`` (pass method_id as-is),
            ``"login"`` (maps to ``cursor_login``), or ``"none"`` (skip auth).
        list_models_command: Optional command to enumerate available models.
            When ``None``, :meth:`list_models` returns an empty list.
        permission_callback: Called when the agent requests tool permission.
        ask_question_callback: Called when the agent asks a multiple-choice question.
    """

    def __init__(
        self,
        name: str,
        command: list[str],
        auth_method: str = "env",
        *,
        list_models_command: list[str] | None = None,
        permission_callback: PermissionCallback | None = None,
        ask_question_callback: AskQuestionCallback | None = None,
    ) -> None:
        """Create a generic ACP provider.

        Args:
            name: Human-readable display name.
            command: The full base spawn command.
            auth_method: Authentication method identifier.
            list_models_command: Optional command to enumerate models.
            permission_callback: Called when the agent requests permission.
            ask_question_callback: Called when the agent asks a question.
        """
        self._name = name
        self._command = command
        self._auth_method = auth_method
        self._list_models_command = list_models_command
        self._permission_callback = permission_callback
        self._ask_question_callback = ask_question_callback
        self._sessions: dict[str, ACPSessionManager] = {}
        self._exit_stacks: dict[str, AsyncExitStack] = {}

    @property
    def name(self) -> str:
        """Return provider display name."""
        return self._name

    @property
    def protocol(self) -> str:
        """Return wire protocol."""
        return "json-rpc"

    @property
    def interaction_model(self) -> InteractionModel:
        """ACP agents are headless -- tak relays permissions."""
        return InteractionModel.HEADLESS

    def set_permission_callback(self, callback: PermissionCallback) -> None:
        """Set the permission callback for all future and existing sessions.

        Args:
            callback: Async callable returning a permission decision string.
        """
        self._permission_callback = callback
        for session in self._sessions.values():
            session.permission_callback = callback

    def set_ask_question_callback(self, callback: AskQuestionCallback) -> None:
        """Set the ask-question callback for all future and existing sessions.

        Args:
            callback: Async callable receiving (question, choices).
        """
        self._ask_question_callback = callback
        for session in self._sessions.values():
            session.ask_question_callback = callback

    async def spawn(
        self,
        agent_name: str,
        project_path: Path | None = None,
        model: str | None = None,
        *,
        mode: str = "agent",
        acp_session_id: str | None = None,
    ) -> asyncio.subprocess.Process:
        """Spawn the ACP subprocess and complete the ACP handshake.

        Uses the SDK's ``spawn_agent_process`` to wire stdio and manage
        the connection lifecycle.

        Args:
            agent_name: Name for this agent instance.
            project_path: Optional project directory.
            model: Optional model name (e.g. ``claude-sonnet-4``).
            mode: Session mode -- ``ask``, ``plan``, or ``agent``.
            acp_session_id: Previous session ID to reconnect to via
                ``load_session``.  Falls back to ``new_session`` on failure.

        Returns:
            The subprocess handle.
        """
        cmd = list(self._command)

        logger.info("Spawning ACP agent %s: %s", agent_name, " ".join(cmd))

        env = _subprocess_env()
        resolved = shutil.which(cmd[0], path=env.get("PATH"))
        if resolved:
            cmd[0] = resolved

        client = TakACPClient(
            agent_name=agent_name,
            permission_callback=self._permission_callback,
            ask_question_callback=self._ask_question_callback,
        )

        stack = AsyncExitStack()
        cwd = str(project_path) if project_path else None
        conn, process = await stack.enter_async_context(
            spawn_agent_process(client, cmd[0], *cmd[1:], env=env, cwd=cwd)
        )
        self._exit_stacks[agent_name] = stack

        session = ACPSessionManager(conn, client, agent_name=agent_name)
        self._sessions[agent_name] = session

        await session.initialize()
        if self._auth_method != "none":
            method_id = "cursor_login" if self._auth_method == "login" else self._auth_method
            await session.authenticate(method_id=method_id)

        resumed = False
        if acp_session_id:
            try:
                await session.load_session(acp_session_id, cwd=cwd)
                resumed = True
                logger.info(
                    "ACP agent %s reconnected to session %s",
                    agent_name, acp_session_id,
                )
            except Exception:
                logger.info(
                    "ACP agent %s: load_session(%s) failed; creating new session",
                    agent_name, acp_session_id,
                )

        if not resumed:
            await session.new_session(
                mode=mode,
                cwd=cwd,
                model=model,
            )

        logger.info(
            "ACP agent %s ready (session %s)", agent_name, session.session_id
        )
        return process

    def get_session(self, agent_name: str) -> ACPSessionManager | None:
        """Look up the session manager for a named agent.

        Args:
            agent_name: The agent's user-assigned name.

        Returns:
            The session manager, or ``None`` if not found.
        """
        return self._sessions.get(agent_name)

    async def send(self, handle: AgentHandle, message: str) -> str:
        """Send a prompt via the ACP session and return the full response.

        Args:
            handle: The agent handle.
            message: The user prompt text.

        Returns:
            The full response text.

        Raises:
            RuntimeError: If no ACP session exists for the agent.
        """
        session = self._sessions.get(handle.name)
        if session is None:
            raise RuntimeError(
                f"No ACP session for agent '{handle.name}'. Was spawn() called?"
            )
        return await session.prompt(message)

    async def send_streaming(
        self, handle: AgentHandle, message: str
    ) -> AsyncIterator[str]:
        """Send a prompt and yield response chunks as they stream in.

        Args:
            handle: The agent handle.
            message: The user prompt text.

        Yields:
            Response text chunks.

        Raises:
            RuntimeError: If no ACP session exists for the agent.
        """
        session = self._sessions.get(handle.name)
        if session is None:
            raise RuntimeError(
                f"No ACP session for agent '{handle.name}'. Was spawn() called?"
            )
        async for chunk in session.prompt_streaming(message):
            yield chunk

    async def cancel(self, handle: AgentHandle) -> None:
        """Cancel the current in-flight prompt for an agent.

        Args:
            handle: The agent to cancel.
        """
        session = self._sessions.get(handle.name)
        if session is not None:
            await session.cancel()

    async def stop(self, handle: AgentHandle) -> None:
        """Terminate the ACP subprocess gracefully via the SDK.

        Args:
            handle: The agent to stop.
        """
        session = self._sessions.pop(handle.name, None)
        if session is not None:
            await session.close()

        stack = self._exit_stacks.pop(handle.name, None)
        if stack is not None:
            await stack.aclose()
        elif handle.process is not None:
            handle.process.terminate()
            try:
                await asyncio.wait_for(handle.process.wait(), timeout=10.0)
            except TimeoutError:
                handle.process.kill()
                await handle.process.wait()

    async def list_models(self) -> list[str]:
        """Query the models command for available model names.

        Returns an empty list if no ``list_models_command`` was provided
        or if the command fails.

        Returns:
            A list of model name strings.
        """
        if not self._list_models_command:
            return []
        try:
            env = _subprocess_env()
            lm_cmd = list(self._list_models_command)
            resolved = shutil.which(lm_cmd[0], path=env.get("PATH"))
            if resolved:
                lm_cmd[0] = resolved
            proc = await asyncio.create_subprocess_exec(
                *lm_cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=env,
            )
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=15.0)
            if proc.returncode != 0:
                return []
            return [
                line.strip()
                for line in stdout.decode().splitlines()
                if line.strip()
            ]
        except (FileNotFoundError, TimeoutError):
            return []
