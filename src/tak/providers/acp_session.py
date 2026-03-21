"""ACP session manager backed by the ``agent-client-protocol`` SDK.

Wraps :class:`acp.ClientSideConnection` to provide the same high-level
interface (initialize, authenticate, new_session, prompt, cancel) that
the rest of tak expects, while delegating all JSON-RPC framing and
message dispatch to the official SDK.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import re
from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass
from enum import Enum
from typing import Any

from acp import (
    PROTOCOL_VERSION,
    RequestError,
    text_block,
)
from acp.schema import (
    AgentMessageChunk,
    AgentThoughtChunk,
    AllowedOutcome,
    AuthenticateResponse,
    DeniedOutcome,
    InitializeResponse,
    NewSessionResponse,
    PermissionOption,
    RequestPermissionResponse,
    TextContentBlock,
    ToolCallUpdate,
)

logger = logging.getLogger(__name__)


_BRACKET_SUFFIX_RE = re.compile(r"\[.*\]$")


def _resolve_model_name(model_id: str | None, models_by_id: dict[str, str]) -> str | None:
    """Resolve a model ID to its human-readable display name.

    Tries an exact match first, then falls back to bracket-stripped and
    case-insensitive lookups.

    Args:
        model_id: The raw model ID (e.g. ``"default[]"``).
        models_by_id: Mapping of ``model_id`` → ``name`` from the server.

    Returns:
        The display name, or ``None`` if *model_id* is ``None``.
    """
    if model_id is None:
        return None

    if model_id in models_by_id:
        return models_by_id[model_id]

    stripped = _BRACKET_SUFFIX_RE.sub("", model_id)
    for mid, name in models_by_id.items():
        if _BRACKET_SUFFIX_RE.sub("", mid) == stripped:
            return name

    lower = model_id.lower()
    for mid, name in models_by_id.items():
        if mid.lower() == lower:
            return name

    return model_id


def _resolve_model_id(user_input: str, models_by_id: dict[str, str]) -> str:
    """Resolve a user-supplied model string to the canonical model ID.

    Handles the common case where a user passes ``"default"`` instead of
    ``"default[]"``, or ``"claude-sonnet-4"`` without bracket params.
    Also handles the reverse case where a display name like ``"Auto"`` is
    passed instead of the raw model ID ``"default[]"``.

    Args:
        user_input: The model string from the CLI, config, or persisted state.
        models_by_id: Mapping of ``model_id`` → ``name`` from the server.

    Returns:
        The best-matching canonical model ID, or *user_input* unchanged if
        no match is found (the server will reject it with ``-32602``).
    """
    if user_input in models_by_id:
        return user_input

    stripped = _BRACKET_SUFFIX_RE.sub("", user_input)
    for mid in models_by_id:
        if _BRACKET_SUFFIX_RE.sub("", mid) == stripped:
            return mid

    lower = user_input.lower()
    for mid in models_by_id:
        if mid.lower() == lower:
            return mid

    for mid, name in models_by_id.items():
        if name == user_input:
            return mid

    for mid, name in models_by_id.items():
        if name.lower() == lower:
            return mid

    return user_input


class ACPSessionState(Enum):
    """Lifecycle states for an ACP session."""

    DISCONNECTED = "disconnected"
    INITIALIZING = "initializing"
    AUTHENTICATED = "authenticated"
    SESSION_ACTIVE = "session_active"
    PROMPTING = "prompting"
    CLOSED = "closed"


@dataclass
class PermissionRequest:
    """A permission request from the ACP agent."""

    tool_name: str
    description: str
    request_id: int | str
    agent_name: str | None = None


PermissionCallback = Callable[[PermissionRequest], Awaitable[str]]
"""Async callable that returns ``allow-once``, ``reject-once``, or ``allow-always``."""

AskQuestionCallback = Callable[[str, list[str]], Awaitable[str]]
"""Async callable receiving (question, choices) and returning the chosen answer."""


class TakACPClient:
    """Implements the ``acp.Client`` protocol for receiving agent callbacks.

    Receives ``session/update`` notifications and ``request_permission``
    calls from the agent, routing them to tak's callback system.
    """

    def __init__(
        self,
        *,
        agent_name: str | None = None,
        permission_callback: PermissionCallback | None = None,
        ask_question_callback: AskQuestionCallback | None = None,
    ) -> None:
        """Create a client that routes ACP callbacks to tak's callback system.

        Args:
            agent_name: The user-assigned name for this agent.
            permission_callback: Called when the agent requests permission.
            ask_question_callback: Called when the agent asks a question.
        """
        self._agent_name = agent_name
        self._permission_callback = permission_callback
        self._ask_question_callback = ask_question_callback
        self._update_chunks: asyncio.Queue[str | None] = asyncio.Queue()

    async def request_permission(
        self,
        options: list[PermissionOption],
        session_id: str,
        tool_call: ToolCallUpdate,
        **kwargs: Any,
    ) -> RequestPermissionResponse:
        """Handle permission requests from the agent."""
        tool_name = tool_call.title or "unknown"
        description = tool_call.title or ""

        req = PermissionRequest(
            tool_name=tool_name,
            description=description,
            request_id=0,
            agent_name=self._agent_name,
        )

        if self._permission_callback is not None:
            try:
                decision = await self._permission_callback(req)
            except Exception:
                logger.exception("Permission callback error; rejecting")
                decision = "reject-once"
        else:
            logger.warning("No permission callback; auto-rejecting %s", tool_name)
            decision = "reject-once"

        if decision in ("allow-once", "allow-always"):
            option_id = options[0].option_id if options else "allow"
            outcome: AllowedOutcome | DeniedOutcome = AllowedOutcome(
                outcome="selected", option_id=option_id
            )
        else:
            outcome = DeniedOutcome(outcome="cancelled")

        return RequestPermissionResponse(outcome=outcome)

    async def session_update(
        self,
        session_id: str,
        update: Any,
        **kwargs: Any,
    ) -> None:
        """Receive streamed session updates from the agent."""
        text = ""
        if isinstance(update, AgentMessageChunk):
            if isinstance(update.content, TextContentBlock):
                text = update.content.text or ""
        elif isinstance(update, AgentThoughtChunk):
            thought_text = getattr(getattr(update, "content", None), "text", "") or ""
            logger.debug("Agent thinking: %s", thought_text[:80])
        elif isinstance(update, ToolCallUpdate):
            logger.info(
                "Tool call: %s (id=%s)", update.title, update.tool_call_id,
            )
        else:
            update_type = getattr(update, "session_update", type(update).__name__)
            logger.debug("Session update: %s", update_type)

        if text:
            self._update_chunks.put_nowait(text)

    async def write_text_file(self, **kwargs: Any) -> None:
        """No-op: tak does not handle file writes from agents."""

    async def read_text_file(self, **kwargs: Any) -> Any:
        """No-op: tak does not handle file reads from agents."""
        return {"content": ""}

    async def create_terminal(self, **kwargs: Any) -> Any:
        """No-op: tak does not handle terminal creation from agents."""
        return {"terminalId": ""}

    async def terminal_output(self, **kwargs: Any) -> Any:
        """No-op."""
        return {"output": ""}

    async def release_terminal(self, **kwargs: Any) -> None:
        """No-op."""

    async def wait_for_terminal_exit(self, **kwargs: Any) -> Any:
        """No-op."""
        return {"exitCode": 0}

    async def kill_terminal(self, **kwargs: Any) -> None:
        """No-op."""

    async def ext_method(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        """Handle extension methods (e.g. cursor/ask_question)."""
        logger.info("Extension method: %s", method)
        if method == "cursor/ask_question" and self._ask_question_callback is not None:
            question = params.get("question", "")
            choices = params.get("choices", [])
            try:
                answer = await self._ask_question_callback(question, choices)
            except Exception:
                logger.exception("Ask-question callback error; using first choice")
                answer = choices[0] if choices else ""
            return {"answer": answer}
        return {}

    async def ext_notification(self, method: str, params: dict[str, Any]) -> None:
        """Handle extension notifications."""
        logger.debug("Extension notification: %s", method)

    def on_connect(self, conn: Any) -> None:
        """Called when the connection is established."""


class ACPSessionManager:
    """Manages an ACP session via the ``agent-client-protocol`` SDK.

    Wraps a :class:`~acp.client.connection.ClientSideConnection` and
    provides the same interface the rest of tak expects.
    """

    def __init__(
        self,
        conn: Any,
        client: TakACPClient,
        *,
        agent_name: str | None = None,
    ) -> None:
        """Create a session manager bound to an SDK connection.

        Args:
            conn: A ``ClientSideConnection`` from the ACP SDK.
            client: The ``TakACPClient`` receiving callbacks.
            agent_name: The user-assigned name for this agent.
        """
        self._conn = conn
        self._client = client
        self._agent_name = agent_name
        self._state = ACPSessionState.DISCONNECTED
        self._session_id: str | None = None
        self._current_model_id: str | None = None
        self._current_model_name: str | None = None
        self._models_by_id: dict[str, str] = {}

    @property
    def state(self) -> ACPSessionState:
        """Return current session state."""
        return self._state

    @property
    def session_id(self) -> str | None:
        """Return the active session ID, if any."""
        return self._session_id

    @property
    def current_model_id(self) -> str | None:
        """Return the model ID reported by the agent, if known."""
        return self._current_model_id

    @property
    def current_model_name(self) -> str | None:
        """Return the human-readable model name, if known."""
        return self._current_model_name

    @property
    def permission_callback(self) -> PermissionCallback | None:
        """Return the current permission callback."""
        return self._client._permission_callback

    @permission_callback.setter
    def permission_callback(self, callback: PermissionCallback | None) -> None:
        """Set the permission callback."""
        self._client._permission_callback = callback

    @property
    def ask_question_callback(self) -> AskQuestionCallback | None:
        """Return the current ask-question callback."""
        return self._client._ask_question_callback

    @ask_question_callback.setter
    def ask_question_callback(self, callback: AskQuestionCallback | None) -> None:
        """Set the ask-question callback."""
        self._client._ask_question_callback = callback

    async def initialize(self) -> InitializeResponse:
        """Send the ``initialize`` handshake.

        Returns:
            Server capabilities from the response.
        """
        self._state = ACPSessionState.INITIALIZING
        return await self._conn.initialize(protocol_version=PROTOCOL_VERSION)

    async def authenticate(self, method_id: str = "cursor_login") -> AuthenticateResponse:
        """Send the ``authenticate`` request.

        Args:
            method_id: Authentication method identifier.

        Returns:
            The authentication response.
        """
        result = await self._conn.authenticate(method_id=method_id)
        self._state = ACPSessionState.AUTHENTICATED
        return result

    async def new_session(
        self,
        mode: str = "agent",
        cwd: str | None = None,
        model: str | None = None,
    ) -> str:
        """Create a new ACP session.

        Args:
            mode: Session mode -- ``ask``, ``plan``, or ``agent``.
            cwd: Working directory / project path for the session.
            model: Model name to use (e.g. ``claude-sonnet-4``).

        Returns:
            The new session ID.
        """
        effective_cwd = cwd or "."
        result: NewSessionResponse = await self._conn.new_session(
            cwd=effective_cwd,
            mcp_servers=[],
        )
        self._session_id = result.session_id or ""
        self._state = ACPSessionState.SESSION_ACTIVE

        models_by_id: dict[str, str] = {}
        if result.models is not None:
            self._current_model_id = result.models.current_model_id
            models_by_id = {
                m.model_id: m.name for m in result.models.available_models
            }
            self._models_by_id = dict(models_by_id)
            self._current_model_name = _resolve_model_name(
                self._current_model_id, models_by_id
            )
            logger.info(
                "Agent %s: model=%s (id=%s), available=%s",
                self._agent_name or "?",
                self._current_model_name,
                self._current_model_id,
                list(models_by_id.values()),
            )
        else:
            logger.debug(
                "Agent %s: models is None in NewSessionResponse",
                self._agent_name or "?",
            )

        if model and self._session_id:
            resolved_id = _resolve_model_id(model, models_by_id)
            if resolved_id == self._current_model_id:
                logger.debug(
                    "Model %r already active; skipping set_session_model",
                    resolved_id,
                )
            else:
                try:
                    await self._conn.set_session_model(
                        model_id=resolved_id,
                        session_id=self._session_id,
                    )
                    self._current_model_id = resolved_id
                    self._current_model_name = _resolve_model_name(
                        resolved_id, models_by_id
                    )
                except RequestError as exc:
                    if exc.code == -32601:
                        logger.debug(
                            "set_session_model not supported; model param ignored",
                        )
                    else:
                        logger.warning(
                            "Failed to set model %r (resolved=%r): %s (code=%d)",
                            model, resolved_id, exc, exc.code,
                        )
                except Exception:
                    logger.debug(
                        "set_session_model failed unexpectedly", exc_info=True,
                    )

        if mode != "agent" and self._session_id:
            try:
                await self._conn.set_session_mode(
                    mode_id=mode,
                    session_id=self._session_id,
                )
            except (RequestError, Exception):
                logger.debug("set_session_mode not supported; mode param ignored")

        return self._session_id

    async def load_session(self, session_id: str, cwd: str | None = None) -> str:
        """Resume a previous ACP session.

        Args:
            session_id: The session to resume.
            cwd: Working directory for the resumed session.

        Returns:
            The loaded session ID.
        """
        effective_cwd = cwd or "."
        await self._conn.load_session(
            cwd=effective_cwd,
            session_id=session_id,
            mcp_servers=[],
        )
        self._session_id = session_id
        self._state = ACPSessionState.SESSION_ACTIVE
        return self._session_id

    async def prompt(self, text: str) -> str:
        """Send a prompt and collect the full response.

        Blocks until all ``session/update`` chunks have been received
        and the ``PromptResponse`` is returned by the SDK.

        Args:
            text: The user prompt text.

        Returns:
            The concatenated response text.
        """
        chunks: list[str] = []
        async for chunk in self.prompt_streaming(text):
            chunks.append(chunk)
        return "".join(chunks)

    async def prompt_streaming(self, text: str) -> AsyncIterator[str]:
        """Send a prompt and yield response chunks as they arrive.

        Args:
            text: The user prompt text.

        Yields:
            Text chunks from ``session/update`` notifications.
        """
        if not self._session_id:
            raise RuntimeError("No active session; call new_session() first")

        self._state = ACPSessionState.PROMPTING

        while not self._client._update_chunks.empty():
            self._client._update_chunks.get_nowait()

        prompt_task = asyncio.create_task(
            self._conn.prompt(
                prompt=[text_block(text)],
                session_id=self._session_id,
            )
        )

        try:
            while not prompt_task.done():
                try:
                    chunk = await asyncio.wait_for(
                        self._client._update_chunks.get(),
                        timeout=0.1,
                    )
                    if chunk is None:
                        break
                    yield chunk
                except TimeoutError:
                    continue

            while not self._client._update_chunks.empty():
                chunk = self._client._update_chunks.get_nowait()
                if chunk is None:
                    break
                yield chunk

        finally:
            if not prompt_task.done():
                prompt_task.cancel()
                with contextlib.suppress(asyncio.CancelledError, Exception):
                    await prompt_task
            else:
                try:
                    prompt_task.result()
                except Exception:
                    logger.debug("Prompt task raised; response may be incomplete")

            self._state = ACPSessionState.SESSION_ACTIVE

    async def cancel(self) -> None:
        """Cancel the current in-flight prompt."""
        if self._session_id:
            await self._conn.cancel(session_id=self._session_id)

    async def close(self) -> None:
        """Close the SDK connection and mark the session closed."""
        self._state = ACPSessionState.CLOSED
        try:
            await self._conn.close()
        except Exception:
            logger.debug("Error closing ACP connection", exc_info=True)
