"""Tests for ACPSessionManager backed by the ACP SDK."""

from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from tak.providers.acp_session import (
    ACPSessionManager,
    ACPSessionState,
    PermissionRequest,
    TakACPClient,
)


def _make_conn_mock() -> AsyncMock:
    """Create a mock ClientSideConnection with standard ACP methods."""
    conn = AsyncMock()
    conn.initialize = AsyncMock(return_value=MagicMock(
        protocol_version=1,
        agent_capabilities=MagicMock(load_session=False),
    ))
    conn.authenticate = AsyncMock(return_value=MagicMock())
    conn.new_session = AsyncMock(return_value=MagicMock(session_id="sess-abc-123"))
    conn.load_session = AsyncMock(return_value=MagicMock(session_id="resumed-sess"))
    conn.prompt = AsyncMock(return_value=MagicMock(stop_reason="end_turn"))
    conn.cancel = AsyncMock()
    conn.close = AsyncMock()
    conn.set_session_model = AsyncMock()
    conn.set_session_mode = AsyncMock()
    return conn


def _make_session(
    conn: AsyncMock | None = None,
    agent_name: str | None = None,
    permission_callback: Any = None,
    ask_question_callback: Any = None,
) -> tuple[ACPSessionManager, AsyncMock, TakACPClient]:
    """Create a session manager with a mock connection."""
    if conn is None:
        conn = _make_conn_mock()
    client = TakACPClient(
        agent_name=agent_name,
        permission_callback=permission_callback,
        ask_question_callback=ask_question_callback,
    )
    session = ACPSessionManager(conn, client, agent_name=agent_name)
    return session, conn, client


class TestInitializeAuthenticateHandshake:
    async def test_initialize_calls_sdk(self) -> None:
        session, conn, _ = _make_session()
        await session.initialize()

        conn.initialize.assert_called_once()
        call_kwargs = conn.initialize.call_args
        assert call_kwargs[1]["protocol_version"] >= 1 or call_kwargs[0][0] >= 1
        assert session.state == ACPSessionState.INITIALIZING

    async def test_authenticate_calls_sdk(self) -> None:
        session, conn, _ = _make_session()
        await session.initialize()
        await session.authenticate()

        conn.authenticate.assert_called_once_with(method_id="cursor_login")
        assert session.state == ACPSessionState.AUTHENTICATED

    async def test_authenticate_custom_method_id(self) -> None:
        session, conn, _ = _make_session()
        await session.initialize()
        await session.authenticate(method_id="env")

        conn.authenticate.assert_called_once_with(method_id="env")

    async def test_new_session_returns_session_id(self) -> None:
        session, _conn, _ = _make_session()
        await session.initialize()
        await session.authenticate()
        sid = await session.new_session(mode="agent")

        assert sid == "sess-abc-123"
        assert session.session_id == "sess-abc-123"
        assert session.state == ACPSessionState.SESSION_ACTIVE

    async def test_new_session_passes_cwd(self) -> None:
        session, conn, _ = _make_session()
        await session.initialize()
        await session.authenticate()
        await session.new_session(cwd="/tmp/proj")  # noqa: S108

        conn.new_session.assert_called_once_with(cwd="/tmp/proj", mcp_servers=[])  # noqa: S108

    async def test_new_session_sets_model(self) -> None:
        session, conn, _ = _make_session()
        await session.initialize()
        await session.authenticate()
        await session.new_session(model="claude-sonnet-4")

        conn.set_session_model.assert_called_once_with(
            model_id="claude-sonnet-4",
            session_id="sess-abc-123",
        )


class TestPromptAndUpdate:
    async def test_prompt_collects_update_chunks(self) -> None:
        session, conn, client = _make_session()
        await session.initialize()
        await session.authenticate()
        await session.new_session()

        async def fake_prompt(**kwargs: Any) -> MagicMock:
            await asyncio.sleep(0.01)
            client._update_chunks.put_nowait("Hello ")
            client._update_chunks.put_nowait("world!")
            await asyncio.sleep(0.01)
            return MagicMock(stop_reason="end_turn")

        conn.prompt = fake_prompt

        result = await session.prompt("Hi")
        assert result == "Hello world!"

    async def test_prompt_streaming_yields_chunks(self) -> None:
        session, conn, client = _make_session()
        await session.initialize()
        await session.authenticate()
        await session.new_session()

        async def fake_prompt(**kwargs: Any) -> MagicMock:
            await asyncio.sleep(0.01)
            client._update_chunks.put_nowait("chunk1")
            client._update_chunks.put_nowait("chunk2")
            await asyncio.sleep(0.01)
            return MagicMock(stop_reason="end_turn")

        conn.prompt = fake_prompt

        chunks = []
        async for chunk in session.prompt_streaming("test"):
            chunks.append(chunk)

        assert chunks == ["chunk1", "chunk2"]

    async def test_prompt_without_session_raises(self) -> None:
        session, _conn, _ = _make_session()
        with pytest.raises(RuntimeError, match="No active session"):
            await session.prompt("test")


class TestSessionUpdate:
    async def test_agent_message_chunk_extracts_text(self) -> None:
        from acp.schema import AgentMessageChunk, TextContentBlock

        _, _, client = _make_session()
        update = AgentMessageChunk(
            session_update="agent_message_chunk",
            content=TextContentBlock(type="text", text="hello"),
        )
        await client.session_update(session_id="s1", update=update)

        chunk = client._update_chunks.get_nowait()
        assert chunk == "hello"

    async def test_non_text_update_ignored(self) -> None:
        from acp.schema import AgentThoughtChunk, TextContentBlock

        _, _, client = _make_session()
        update = AgentThoughtChunk(
            session_update="agent_thought_chunk",
            content=TextContentBlock(type="text", text="thinking..."),
        )
        await client.session_update(session_id="s1", update=update)

        assert client._update_chunks.empty()


class TestPermissionCallback:
    async def test_permission_callback_invoked(self) -> None:
        from acp.schema import PermissionOption, ToolCallUpdate

        callback = AsyncMock(return_value="allow-once")
        _, _, client = _make_session(permission_callback=callback)

        tool_call = ToolCallUpdate(
            session_update="tool_call_update",
            tool_call_id="tc-1",
            title="edit_file",
        )
        options = [PermissionOption(
            kind="allow_once",
            name="Allow",
            option_id="opt-1",
        )]

        result = await client.request_permission(
            options=options,
            session_id="s1",
            tool_call=tool_call,
        )

        callback.assert_called_once()
        req: PermissionRequest = callback.call_args[0][0]
        assert req.tool_name == "edit_file"
        assert result.outcome.outcome == "selected"

    async def test_no_callback_auto_rejects(self) -> None:
        from acp.schema import PermissionOption, ToolCallUpdate

        _, _, client = _make_session()

        tool_call = ToolCallUpdate(
            session_update="tool_call_update",
            tool_call_id="tc-1",
            title="run_cmd",
        )
        options = [PermissionOption(kind="allow_once", name="Allow", option_id="opt-1")]

        result = await client.request_permission(
            options=options,
            session_id="s1",
            tool_call=tool_call,
        )

        assert result.outcome.outcome == "cancelled"

    async def test_permission_request_includes_agent_name(self) -> None:
        from acp.schema import PermissionOption, ToolCallUpdate

        callback = AsyncMock(return_value="reject-once")
        _, _, client = _make_session(
            agent_name="my-agent", permission_callback=callback
        )

        tool_call = ToolCallUpdate(
            session_update="tool_call_update",
            tool_call_id="tc-1",
            title="run_cmd",
        )
        options = [PermissionOption(kind="allow_once", name="Allow", option_id="opt-1")]

        await client.request_permission(
            options=options,
            session_id="s1",
            tool_call=tool_call,
        )

        callback.assert_called_once()
        req: PermissionRequest = callback.call_args[0][0]
        assert req.agent_name == "my-agent"


class TestLoadSession:
    async def test_load_session_resumes(self) -> None:
        session, conn, _ = _make_session()
        await session.initialize()
        await session.authenticate()
        sid = await session.load_session("old-sess-id", cwd="/tmp/proj")  # noqa: S108

        assert sid == "old-sess-id"
        assert session.session_id == "old-sess-id"
        assert session.state == ACPSessionState.SESSION_ACTIVE
        conn.load_session.assert_called_once_with(
            cwd="/tmp/proj",  # noqa: S108
            session_id="old-sess-id",
            mcp_servers=[],
        )


class TestCancel:
    async def test_cancel_calls_sdk(self) -> None:
        session, conn, _ = _make_session()
        await session.initialize()
        await session.authenticate()
        await session.new_session()
        await session.cancel()

        conn.cancel.assert_called_once_with(session_id="sess-abc-123")


class TestClose:
    async def test_close_calls_sdk(self) -> None:
        session, conn, _ = _make_session()
        await session.initialize()
        await session.close()

        assert session.state == ACPSessionState.CLOSED
        conn.close.assert_called_once()


class TestCallbackProperties:
    def test_permission_callback_property(self) -> None:
        session, _, _ = _make_session()
        callback = AsyncMock(return_value="allow-once")
        session.permission_callback = callback
        assert session.permission_callback is callback

    def test_ask_question_callback_property(self) -> None:
        session, _, _ = _make_session()
        callback = AsyncMock(return_value="option-a")
        session.ask_question_callback = callback
        assert session.ask_question_callback is callback
