"""ACP session manager for JSON-RPC 2.0 over subprocess stdio.

Manages the full ACP lifecycle: initialize, authenticate, session/new,
session/prompt, and handles streamed ``session/update`` notifications
plus ``session/request_permission`` callbacks.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


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


@dataclass
class _PendingRequest:
    """Tracks a JSON-RPC request awaiting a response."""

    method: str
    future: asyncio.Future[dict[str, Any]]


class ACPSessionManager:
    """Manages a JSON-RPC 2.0 ACP session over subprocess stdin/stdout.

    Reads stdout in a background task, dispatching responses to their
    waiting futures and notifications to registered handlers.
    """

    def __init__(
        self,
        process: Any,
        *,
        agent_name: str | None = None,
        permission_callback: PermissionCallback | None = None,
        ask_question_callback: AskQuestionCallback | None = None,
    ) -> None:
        """Create a session manager bound to a subprocess.

        Args:
            process: An ``asyncio.subprocess.Process`` with stdin/stdout pipes.
            agent_name: The user-assigned name for this agent (passed through
                to ``PermissionRequest`` so callbacks know which agent asked).
            permission_callback: Called when the agent requests permission.
            ask_question_callback: Called when the agent asks a question.
        """
        self._process = process
        self._agent_name = agent_name
        self._permission_callback = permission_callback
        self._ask_question_callback = ask_question_callback

        self._request_id: int = 0
        self._pending: dict[int, _PendingRequest] = {}
        self._state = ACPSessionState.DISCONNECTED
        self._session_id: str | None = None
        self._reader_task: asyncio.Task[None] | None = None

        self._update_chunks: asyncio.Queue[str | None] = asyncio.Queue()

        self._notification_handlers: dict[
            str, Callable[..., Awaitable[None]]
        ] = {
            "session/update": self._handle_update,
            "session/request_permission": self._handle_permission_request,
            "cursor/ask_question": self._handle_ask_question,
        }

    @property
    def state(self) -> ACPSessionState:
        """Return current session state."""
        return self._state

    @property
    def session_id(self) -> str | None:
        """Return the active session ID, if any."""
        return self._session_id

    def start_reader(self) -> None:
        """Spawn the background stdout reader task."""
        if self._reader_task is None or self._reader_task.done():
            self._reader_task = asyncio.create_task(self._read_loop())

    async def close(self) -> None:
        """Cancel the reader task and mark the session closed."""
        self._state = ACPSessionState.CLOSED
        if self._reader_task is not None and not self._reader_task.done():
            self._reader_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._reader_task
        for pending in self._pending.values():
            if not pending.future.done():
                pending.future.cancel()
        self._pending.clear()

    async def initialize(self) -> dict[str, Any]:
        """Send the ``initialize`` handshake.

        Returns:
            Server capabilities from the response.
        """
        from tak import __version__

        self._state = ACPSessionState.INITIALIZING
        self.start_reader()
        return await self._send_request("initialize", {
            "protocolVersion": 1,
            "clientInfo": {"name": "tak", "version": __version__},
            "clientCapabilities": {},
        })

    async def authenticate(self, method_id: str = "cursor_login") -> dict[str, Any]:
        """Send the ``authenticate`` request.

        Args:
            method_id: Authentication method identifier.

        Returns:
            The authentication response.
        """
        result = await self._send_request("authenticate", {"methodId": method_id})
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
        params: dict[str, Any] = {"mode": mode, "mcpServers": []}
        if cwd:
            params["cwd"] = cwd
        if model:
            params["model"] = model
        result = await self._send_request("session/new", params)
        self._session_id = result.get("sessionId", "")
        self._state = ACPSessionState.SESSION_ACTIVE
        return self._session_id

    async def load_session(self, session_id: str) -> str:
        """Resume a previous ACP session.

        Args:
            session_id: The session to resume.

        Returns:
            The loaded session ID.
        """
        result = await self._send_request("session/load", {"sessionId": session_id})
        self._session_id = result.get("sessionId", session_id)
        self._state = ACPSessionState.SESSION_ACTIVE
        return self._session_id

    async def prompt(self, text: str) -> str:
        """Send a prompt and collect the full response.

        Blocks until all ``session/update`` chunks have been received.

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
        self._state = ACPSessionState.PROMPTING
        while not self._update_chunks.empty():
            self._update_chunks.get_nowait()

        await self._send_request_no_wait(
            "session/prompt",
            {"prompt": [{"type": "text", "text": text}]},
        )

        while True:
            chunk = await self._update_chunks.get()
            if chunk is None:
                break
            yield chunk

        self._state = ACPSessionState.SESSION_ACTIVE

    async def cancel(self) -> dict[str, Any]:
        """Cancel the current in-flight prompt.

        Returns:
            The cancel response.
        """
        return await self._send_request("session/cancel", {})

    async def _send_request(
        self, method: str, params: dict[str, Any], timeout: float = 60.0
    ) -> dict[str, Any]:
        """Send a JSON-RPC request and wait for the correlated response.

        Args:
            method: The RPC method name.
            params: The request parameters.
            timeout: Seconds to wait for a response.

        Returns:
            The ``result`` dict from the response.

        Raises:
            RuntimeError: On ACP errors or timeouts.
        """
        self._request_id += 1
        req_id = self._request_id

        loop = asyncio.get_running_loop()
        future: asyncio.Future[dict[str, Any]] = loop.create_future()
        self._pending[req_id] = _PendingRequest(method=method, future=future)

        request = {
            "jsonrpc": "2.0",
            "id": req_id,
            "method": method,
            "params": params,
        }
        await self._write_message(request)

        try:
            result = await asyncio.wait_for(future, timeout=timeout)
        except TimeoutError as exc:
            self._pending.pop(req_id, None)
            raise RuntimeError(f"ACP request '{method}' timed out after {timeout}s") from exc

        return result

    async def _send_request_no_wait(self, method: str, params: dict[str, Any]) -> int:
        """Send a request without waiting for a response.

        The response is still correlated when it arrives and placed on the
        update queue (for prompt-style requests where updates come as
        notifications).

        Args:
            method: The RPC method name.
            params: The request parameters.

        Returns:
            The request ID.
        """
        self._request_id += 1
        req_id = self._request_id

        loop = asyncio.get_running_loop()
        future: asyncio.Future[dict[str, Any]] = loop.create_future()
        self._pending[req_id] = _PendingRequest(method=method, future=future)

        future.add_done_callback(lambda f: self._on_prompt_complete(f))

        request = {
            "jsonrpc": "2.0",
            "id": req_id,
            "method": method,
            "params": params,
        }
        await self._write_message(request)
        return req_id

    def _on_prompt_complete(self, future: asyncio.Future[dict[str, Any]]) -> None:
        """Signal end-of-stream when the prompt response arrives."""
        self._update_chunks.put_nowait(None)

    async def _write_message(self, message: dict[str, Any]) -> None:
        """Write a JSON-RPC message to the subprocess stdin."""
        stdin = self._process.stdin
        if stdin is None:
            raise RuntimeError("Process stdin is not available")
        payload = json.dumps(message).encode() + b"\n"
        stdin.write(payload)
        await stdin.drain()

    async def _read_loop(self) -> None:
        """Background task: read stdout lines and dispatch messages."""
        stdout = self._process.stdout
        if stdout is None:
            logger.error("Process stdout is not available; reader exiting")
            return

        try:
            while True:
                line = await stdout.readline()
                if not line:
                    logger.debug("ACP stdout closed")
                    break

                line = line.strip()
                if not line:
                    continue

                try:
                    message = json.loads(line)
                except json.JSONDecodeError:
                    logger.warning("Non-JSON line from ACP stdout: %s", line[:200])
                    continue

                await self._dispatch_message(message)
        except asyncio.CancelledError:
            logger.debug("ACP reader task cancelled")
        except Exception:
            logger.exception("ACP reader loop error")
        finally:
            self._update_chunks.put_nowait(None)
            for pending in self._pending.values():
                if not pending.future.done():
                    pending.future.set_exception(
                        RuntimeError("ACP connection closed unexpectedly")
                    )

    async def _dispatch_message(self, message: dict[str, Any]) -> None:
        """Route a parsed JSON-RPC message to the right handler."""
        if "id" in message and "method" not in message:
            self._handle_response(message)
        elif "method" in message:
            await self._handle_notification(message)
        else:
            logger.warning("Unrecognized ACP message: %s", message)

    def _handle_response(self, message: dict[str, Any]) -> None:
        """Match a response to its pending request future."""
        req_id = message.get("id")
        if req_id is None:
            return

        pending = self._pending.pop(req_id, None)
        if pending is None:
            logger.warning("Response for unknown request ID %s", req_id)
            return

        if "error" in message:
            error = message["error"]
            pending.future.set_exception(
                RuntimeError(
                    f"ACP error {error.get('code', '?')}: {error.get('message', 'unknown')}"
                )
            )
        else:
            result = message.get("result", {})
            pending.future.set_result(result if isinstance(result, dict) else {"value": result})

    async def _handle_notification(self, message: dict[str, Any]) -> None:
        """Dispatch a notification to its registered handler."""
        method = message["method"]
        handler = self._notification_handlers.get(method)
        if handler is not None:
            params = message.get("params", {})
            await handler(params)
        else:
            logger.debug("Unhandled ACP notification: %s", method)

    async def _handle_update(self, params: dict[str, Any]) -> None:
        """Handle ``session/update`` -- extract text and queue it."""
        text = params.get("text", "")
        if not text:
            chunk = params.get("chunk", {})
            text = chunk.get("text", "")
        if text:
            self._update_chunks.put_nowait(text)

        if params.get("finished", False):
            self._update_chunks.put_nowait(None)

    async def _handle_permission_request(self, params: dict[str, Any]) -> None:
        """Handle ``session/request_permission`` from the agent."""
        req = PermissionRequest(
            tool_name=params.get("toolName", params.get("tool", "unknown")),
            description=params.get("description", ""),
            request_id=params.get("id", params.get("requestId", 0)),
            agent_name=self._agent_name,
        )

        if self._permission_callback is not None:
            try:
                decision = await self._permission_callback(req)
            except Exception:
                logger.exception("Permission callback error; rejecting")
                decision = "reject-once"
        else:
            logger.warning("No permission callback; auto-rejecting %s", req.tool_name)
            decision = "reject-once"

        response = {
            "jsonrpc": "2.0",
            "method": "session/permission_response",
            "params": {
                "requestId": req.request_id,
                "decision": decision,
            },
        }
        await self._write_message(response)

    async def _handle_ask_question(self, params: dict[str, Any]) -> None:
        """Handle ``cursor/ask_question`` from the agent."""
        question = params.get("question", "")
        choices = params.get("choices", [])
        request_id = params.get("id", params.get("requestId", 0))

        if self._ask_question_callback is not None:
            try:
                answer = await self._ask_question_callback(question, choices)
            except Exception:
                logger.exception("Ask-question callback error; using first choice")
                answer = choices[0] if choices else ""
        else:
            logger.warning("No ask-question callback; using first choice")
            answer = choices[0] if choices else ""

        response = {
            "jsonrpc": "2.0",
            "method": "cursor/answer_question",
            "params": {
                "requestId": request_id,
                "answer": answer,
            },
        }
        await self._write_message(response)
