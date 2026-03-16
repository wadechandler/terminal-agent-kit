"""Tests for ACPSessionManager JSON-RPC lifecycle."""

from __future__ import annotations

import asyncio
import json
from typing import TYPE_CHECKING, Any
from unittest.mock import AsyncMock

if TYPE_CHECKING:
    from collections.abc import Coroutine

import pytest

from tak.providers.acp_session import (
    ACPSessionManager,
    ACPSessionState,
    PermissionRequest,
)

_background_tasks: set[asyncio.Task[Any]] = set()


def _bg(coro: Coroutine[Any, Any, Any]) -> asyncio.Task[Any]:
    """Create a background task and prevent it from being garbage-collected."""
    task = asyncio.create_task(coro)
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)
    return task


class MockStdio:
    """Simulates an async subprocess stdin/stdout for ACP testing.

    Write messages to ``outgoing`` to simulate ACP server responses.
    Read from ``incoming`` to see what the session manager sent.
    """

    def __init__(self) -> None:
        self._read_buffer = asyncio.Queue[bytes]()
        self.incoming: list[dict[str, Any]] = []

    def write(self, data: bytes) -> None:
        for line in data.split(b"\n"):
            line = line.strip()
            if line:
                self.incoming.append(json.loads(line))

    async def drain(self) -> None:
        pass

    def feed_json(self, obj: dict[str, Any]) -> None:
        """Queue a JSON-RPC message to be read by the session manager."""
        self._read_buffer.put_nowait(json.dumps(obj).encode() + b"\n")

    async def readline(self) -> bytes:
        try:
            return await asyncio.wait_for(self._read_buffer.get(), timeout=2.0)
        except TimeoutError:
            return b""


class MockACPProcess:
    """Simulates the subprocess for an ACP agent."""

    def __init__(self) -> None:
        self.stdin = MockStdio()
        self.stdout = MockStdio()
        self.returncode: int | None = None

    def feed_response(self, req_id: int, result: dict[str, Any]) -> None:
        self.stdout.feed_json({"jsonrpc": "2.0", "id": req_id, "result": result})

    def feed_notification(self, method: str, params: dict[str, Any]) -> None:
        self.stdout.feed_json({"jsonrpc": "2.0", "method": method, "params": params})

    def feed_error(self, req_id: int, code: int, message: str) -> None:
        self.stdout.feed_json({
            "jsonrpc": "2.0",
            "id": req_id,
            "error": {"code": code, "message": message},
        })


@pytest.fixture
def mock_process() -> MockACPProcess:
    return MockACPProcess()


@pytest.fixture
def session(mock_process: MockACPProcess) -> ACPSessionManager:
    return ACPSessionManager(mock_process)


class TestInitializeAuthenticateHandshake:
    async def test_initialize_sends_request(
        self, session: ACPSessionManager, mock_process: MockACPProcess
    ) -> None:
        async def respond_after_delay() -> None:
            await asyncio.sleep(0.05)
            mock_process.feed_response(1, {"capabilities": {}})

        _bg(respond_after_delay())
        result = await session.initialize()

        assert result == {"capabilities": {}}
        assert session.state == ACPSessionState.INITIALIZING
        sent = mock_process.stdin.incoming
        assert len(sent) == 1
        assert sent[0]["method"] == "initialize"

    async def test_initialize_sends_protocol_version_and_client_info(
        self, session: ACPSessionManager, mock_process: MockACPProcess
    ) -> None:
        async def respond_after_delay() -> None:
            await asyncio.sleep(0.05)
            mock_process.feed_response(1, {"protocolVersion": 1, "capabilities": {}})

        _bg(respond_after_delay())
        await session.initialize()

        sent = mock_process.stdin.incoming
        params = sent[0]["params"]
        assert params["protocolVersion"] == 1
        assert "clientInfo" in params
        assert params["clientInfo"]["name"] == "tak"
        assert "version" in params["clientInfo"]
        assert "clientCapabilities" in params

    async def test_authenticate_sends_method_id(
        self, session: ACPSessionManager, mock_process: MockACPProcess
    ) -> None:
        async def respond_init() -> None:
            await asyncio.sleep(0.05)
            mock_process.feed_response(1, {"capabilities": {}})

        _bg(respond_init())
        await session.initialize()

        async def respond_auth() -> None:
            await asyncio.sleep(0.05)
            mock_process.feed_response(2, {"authenticated": True})

        _bg(respond_auth())
        result = await session.authenticate()

        assert result == {"authenticated": True}
        assert session.state == ACPSessionState.AUTHENTICATED
        sent = mock_process.stdin.incoming
        assert sent[1]["method"] == "authenticate"
        assert sent[1]["params"]["methodId"] == "cursor_login"

    async def test_new_session_returns_session_id(
        self, session: ACPSessionManager, mock_process: MockACPProcess
    ) -> None:
        async def respond_all() -> None:
            await asyncio.sleep(0.05)
            mock_process.feed_response(1, {"capabilities": {}})
            await asyncio.sleep(0.05)
            mock_process.feed_response(2, {"authenticated": True})
            await asyncio.sleep(0.05)
            mock_process.feed_response(3, {"sessionId": "sess-abc-123"})

        _bg(respond_all())

        await session.initialize()
        await session.authenticate()
        sid = await session.new_session(mode="agent")

        assert sid == "sess-abc-123"
        assert session.session_id == "sess-abc-123"
        assert session.state == ACPSessionState.SESSION_ACTIVE


class TestPromptAndUpdate:
    async def test_prompt_collects_update_chunks(
        self, session: ACPSessionManager, mock_process: MockACPProcess
    ) -> None:
        async def handshake_and_prompt() -> None:
            await asyncio.sleep(0.05)
            mock_process.feed_response(1, {"capabilities": {}})
            await asyncio.sleep(0.05)
            mock_process.feed_response(2, {"authenticated": True})
            await asyncio.sleep(0.05)
            mock_process.feed_response(3, {"sessionId": "s1"})
            await asyncio.sleep(0.05)
            mock_process.feed_notification("session/update", {"text": "Hello "})
            mock_process.feed_notification("session/update", {"text": "world!"})
            await asyncio.sleep(0.05)
            mock_process.feed_response(4, {"done": True})

        _bg(handshake_and_prompt())

        await session.initialize()
        await session.authenticate()
        await session.new_session()

        result = await session.prompt("Hi")
        assert result == "Hello world!"

    async def test_prompt_streaming_yields_chunks(
        self, session: ACPSessionManager, mock_process: MockACPProcess
    ) -> None:
        async def handshake_and_prompt() -> None:
            await asyncio.sleep(0.05)
            mock_process.feed_response(1, {"capabilities": {}})
            await asyncio.sleep(0.05)
            mock_process.feed_response(2, {"authenticated": True})
            await asyncio.sleep(0.05)
            mock_process.feed_response(3, {"sessionId": "s1"})
            await asyncio.sleep(0.05)
            mock_process.feed_notification("session/update", {"text": "chunk1"})
            mock_process.feed_notification("session/update", {"text": "chunk2"})
            await asyncio.sleep(0.05)
            mock_process.feed_response(4, {"done": True})

        _bg(handshake_and_prompt())

        await session.initialize()
        await session.authenticate()
        await session.new_session()

        chunks = []
        async for chunk in session.prompt_streaming("test"):
            chunks.append(chunk)

        assert chunks == ["chunk1", "chunk2"]

    async def test_update_with_chunk_field(
        self, session: ACPSessionManager, mock_process: MockACPProcess
    ) -> None:
        async def handshake_and_prompt() -> None:
            await asyncio.sleep(0.05)
            mock_process.feed_response(1, {"capabilities": {}})
            await asyncio.sleep(0.05)
            mock_process.feed_response(2, {})
            await asyncio.sleep(0.05)
            mock_process.feed_response(3, {"sessionId": "s1"})
            await asyncio.sleep(0.05)
            mock_process.feed_notification(
                "session/update", {"chunk": {"text": "from-chunk"}}
            )
            await asyncio.sleep(0.05)
            mock_process.feed_response(4, {})

        _bg(handshake_and_prompt())

        await session.initialize()
        await session.authenticate()
        await session.new_session()

        result = await session.prompt("test")
        assert result == "from-chunk"


class TestPermissionCallback:
    async def test_permission_callback_invoked(
        self, mock_process: MockACPProcess
    ) -> None:
        callback = AsyncMock(return_value="allow-once")
        mgr = ACPSessionManager(mock_process, permission_callback=callback)

        async def handshake_and_permission() -> None:
            await asyncio.sleep(0.05)
            mock_process.feed_response(1, {})
            await asyncio.sleep(0.05)
            mock_process.feed_response(2, {})
            await asyncio.sleep(0.05)
            mock_process.feed_response(3, {"sessionId": "s1"})
            await asyncio.sleep(0.05)
            mock_process.feed_notification(
                "session/request_permission",
                {"toolName": "edit_file", "description": "Edit src/foo.py", "id": 99},
            )
            await asyncio.sleep(0.1)
            mock_process.feed_response(4, {})

        _bg(handshake_and_permission())

        await mgr.initialize()
        await mgr.authenticate()
        await mgr.new_session()
        await mgr.prompt("do something")

        callback.assert_called_once()
        req: PermissionRequest = callback.call_args[0][0]
        assert req.tool_name == "edit_file"
        assert req.description == "Edit src/foo.py"
        assert req.request_id == 99

        permission_responses = [
            m for m in mock_process.stdin.incoming
            if m.get("method") == "session/permission_response"
        ]
        assert len(permission_responses) == 1
        assert permission_responses[0]["params"]["decision"] == "allow-once"

    async def test_no_callback_auto_rejects(
        self, mock_process: MockACPProcess
    ) -> None:
        mgr = ACPSessionManager(mock_process)

        async def handshake_and_permission() -> None:
            await asyncio.sleep(0.05)
            mock_process.feed_response(1, {})
            await asyncio.sleep(0.05)
            mock_process.feed_response(2, {})
            await asyncio.sleep(0.05)
            mock_process.feed_response(3, {"sessionId": "s1"})
            await asyncio.sleep(0.05)
            mock_process.feed_notification(
                "session/request_permission",
                {"toolName": "run_cmd", "description": "Run rm -rf /", "id": 42},
            )
            await asyncio.sleep(0.1)
            mock_process.feed_response(4, {})

        _bg(handshake_and_permission())

        await mgr.initialize()
        await mgr.authenticate()
        await mgr.new_session()
        await mgr.prompt("do it")

        permission_responses = [
            m for m in mock_process.stdin.incoming
            if m.get("method") == "session/permission_response"
        ]
        assert len(permission_responses) == 1
        assert permission_responses[0]["params"]["decision"] == "reject-once"


class TestRequestIdCorrelation:
    async def test_responses_matched_to_correct_future(
        self, session: ACPSessionManager, mock_process: MockACPProcess
    ) -> None:
        async def respond_out_of_order() -> None:
            await asyncio.sleep(0.05)
            mock_process.feed_response(1, {"step": "init"})
            await asyncio.sleep(0.05)
            mock_process.feed_response(2, {"step": "auth"})

        _bg(respond_out_of_order())

        init_result = await session.initialize()
        auth_result = await session.authenticate()

        assert init_result == {"step": "init"}
        assert auth_result == {"step": "auth"}


class TestLoadSession:
    async def test_load_session_resumes(
        self, session: ACPSessionManager, mock_process: MockACPProcess
    ) -> None:
        async def respond_handshake_and_load() -> None:
            await asyncio.sleep(0.05)
            mock_process.feed_response(1, {"capabilities": {}})
            await asyncio.sleep(0.05)
            mock_process.feed_response(2, {})
            await asyncio.sleep(0.05)
            mock_process.feed_response(3, {"sessionId": "resumed-sess"})

        _bg(respond_handshake_and_load())

        await session.initialize()
        await session.authenticate()
        sid = await session.load_session("old-sess-id")

        assert sid == "resumed-sess"
        assert session.session_id == "resumed-sess"
        assert session.state == ACPSessionState.SESSION_ACTIVE

        sent = mock_process.stdin.incoming
        load_msg = sent[2]
        assert load_msg["method"] == "session/load"
        assert load_msg["params"]["sessionId"] == "old-sess-id"


class TestCancel:
    async def test_cancel_sends_request(
        self, session: ACPSessionManager, mock_process: MockACPProcess
    ) -> None:
        async def respond_handshake_and_cancel() -> None:
            await asyncio.sleep(0.05)
            mock_process.feed_response(1, {})
            await asyncio.sleep(0.05)
            mock_process.feed_response(2, {})
            await asyncio.sleep(0.05)
            mock_process.feed_response(3, {"sessionId": "s1"})
            await asyncio.sleep(0.05)
            mock_process.feed_response(4, {"cancelled": True})

        _bg(respond_handshake_and_cancel())

        await session.initialize()
        await session.authenticate()
        await session.new_session()
        result = await session.cancel()

        assert result == {"cancelled": True}
        sent = mock_process.stdin.incoming
        cancel_msg = sent[3]
        assert cancel_msg["method"] == "session/cancel"


class TestFinishedFlag:
    async def test_finished_true_ends_stream(
        self, session: ACPSessionManager, mock_process: MockACPProcess
    ) -> None:
        """When session/update has finished=true, streaming ends without
        needing the prompt response to arrive first."""

        async def handshake_and_finished() -> None:
            await asyncio.sleep(0.05)
            mock_process.feed_response(1, {})
            await asyncio.sleep(0.05)
            mock_process.feed_response(2, {})
            await asyncio.sleep(0.05)
            mock_process.feed_response(3, {"sessionId": "s1"})
            await asyncio.sleep(0.05)
            mock_process.feed_notification("session/update", {"text": "done!"})
            mock_process.feed_notification(
                "session/update", {"text": "", "finished": True}
            )
            await asyncio.sleep(0.1)
            mock_process.feed_response(4, {})

        _bg(handshake_and_finished())

        await session.initialize()
        await session.authenticate()
        await session.new_session()

        chunks = []
        async for chunk in session.prompt_streaming("test"):
            chunks.append(chunk)

        assert chunks == ["done!"]


class TestAgentNameOnPermissionRequest:
    async def test_permission_request_includes_agent_name(
        self, mock_process: MockACPProcess
    ) -> None:
        callback = AsyncMock(return_value="reject-once")
        mgr = ACPSessionManager(
            mock_process, agent_name="my-agent", permission_callback=callback
        )

        async def handshake_and_permission() -> None:
            await asyncio.sleep(0.05)
            mock_process.feed_response(1, {})
            await asyncio.sleep(0.05)
            mock_process.feed_response(2, {})
            await asyncio.sleep(0.05)
            mock_process.feed_response(3, {"sessionId": "s1"})
            await asyncio.sleep(0.05)
            mock_process.feed_notification(
                "session/request_permission",
                {"toolName": "run_cmd", "description": "ls", "id": 7},
            )
            await asyncio.sleep(0.1)
            mock_process.feed_response(4, {})

        _bg(handshake_and_permission())

        await mgr.initialize()
        await mgr.authenticate()
        await mgr.new_session()
        await mgr.prompt("go")

        callback.assert_called_once()
        req: PermissionRequest = callback.call_args[0][0]
        assert req.agent_name == "my-agent"


class TestErrorHandling:
    async def test_acp_error_response_raises(
        self, session: ACPSessionManager, mock_process: MockACPProcess
    ) -> None:
        async def respond_error() -> None:
            await asyncio.sleep(0.05)
            mock_process.feed_error(1, -32600, "Invalid request")

        _bg(respond_error())

        with pytest.raises(RuntimeError, match="ACP error -32600"):
            await session.initialize()

    async def test_close_cancels_reader(
        self, session: ACPSessionManager, mock_process: MockACPProcess
    ) -> None:
        async def respond() -> None:
            await asyncio.sleep(0.05)
            mock_process.feed_response(1, {})

        _bg(respond())
        await session.initialize()

        await session.close()
        assert session.state == ACPSessionState.CLOSED
