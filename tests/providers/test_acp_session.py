"""Tests for ACPSessionManager backed by the ACP SDK."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from tak.providers.acp_session import (
    ACPSessionManager,
    ACPSessionState,
    PermissionRequest,
    TakACPClient,
    _resolve_model_id,
    _resolve_model_name,
)


def _model(model_id: str, display_name: str) -> SimpleNamespace:
    return SimpleNamespace(model_id=model_id, name=display_name)


def _mode(mode_id: str, display_name: str) -> SimpleNamespace:
    return SimpleNamespace(id=mode_id, name=display_name)


REALISTIC_MODELS = SimpleNamespace(
    current_model_id="default[]",
    available_models=[
        _model("default[]", "Auto"),
        _model("claude-sonnet-4-6[thinking=true,context=200k,effort=medium]", "Sonnet 4.6"),
        _model("claude-opus-4-6[thinking=true,context=200k,effort=high,fast=false]", "Opus 4.6"),
        _model("gpt-5.4[reasoning=medium,context=272k,fast=false]", "GPT-5.4"),
        _model("gemini-3-flash[]", "Gemini 3 Flash"),
    ],
)

REALISTIC_MODES = SimpleNamespace(
    current_mode_id="agent",
    available_modes=[
        _mode("agent", "Agent"),
        _mode("plan", "Plan"),
        _mode("ask", "Ask"),
    ],
)


def _make_new_session_response(
    session_id: str = "sess-abc-123",
    models: SimpleNamespace | None = REALISTIC_MODELS,
    modes: SimpleNamespace | None = REALISTIC_MODES,
) -> SimpleNamespace:
    """Build a ``NewSessionResponse``-like mock with realistic payloads."""
    return SimpleNamespace(session_id=session_id, models=models, modes=modes)


def _make_conn_mock(
    new_session_response: MagicMock | None = None,
) -> AsyncMock:
    """Create a mock ClientSideConnection with standard ACP methods."""
    if new_session_response is None:
        new_session_response = _make_new_session_response()

    conn = AsyncMock()
    conn.initialize = AsyncMock(return_value=MagicMock(
        protocol_version=1,
        agent_capabilities=MagicMock(load_session=False),
    ))
    conn.authenticate = AsyncMock(return_value=MagicMock())
    conn.new_session = AsyncMock(return_value=new_session_response)
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

    async def test_new_session_resolves_model_name(self) -> None:
        session, _conn, _ = _make_session()
        await session.initialize()
        await session.authenticate()
        await session.new_session()

        assert session.current_model_id == "default[]"
        assert session.current_model_name == "Auto"

    async def test_new_session_with_no_models(self) -> None:
        resp = _make_new_session_response(models=None)
        conn = _make_conn_mock(new_session_response=resp)
        session, _, _ = _make_session(conn=conn)
        await session.initialize()
        await session.authenticate()
        await session.new_session()

        assert session.current_model_id is None
        assert session.current_model_name is None

    async def test_new_session_passes_cwd(self) -> None:
        session, conn, _ = _make_session()
        await session.initialize()
        await session.authenticate()
        await session.new_session(cwd="/tmp/proj")  # noqa: S108

        conn.new_session.assert_called_once_with(cwd="/tmp/proj", mcp_servers=[])  # noqa: S108

    async def test_new_session_sets_model_exact_match(self) -> None:
        session, conn, _ = _make_session()
        await session.initialize()
        await session.authenticate()
        await session.new_session(
            model="claude-sonnet-4-6[thinking=true,context=200k,effort=medium]"
        )

        conn.set_session_model.assert_called_once_with(
            model_id="claude-sonnet-4-6[thinking=true,context=200k,effort=medium]",
            session_id="sess-abc-123",
        )

    async def test_new_session_resolves_bracketless_model(self) -> None:
        session, conn, _ = _make_session()
        await session.initialize()
        await session.authenticate()
        await session.new_session(model="gemini-3-flash")

        conn.set_session_model.assert_called_once_with(
            model_id="gemini-3-flash[]",
            session_id="sess-abc-123",
        )

    async def test_new_session_skips_set_when_model_already_active(self) -> None:
        session, conn, _ = _make_session()
        await session.initialize()
        await session.authenticate()
        await session.new_session(model="default[]")

        conn.set_session_model.assert_not_called()
        assert session.current_model_id == "default[]"
        assert session.current_model_name == "Auto"

    async def test_new_session_skips_set_for_display_name_of_current(self) -> None:
        session, conn, _ = _make_session()
        await session.initialize()
        await session.authenticate()
        await session.new_session(model="Auto")

        conn.set_session_model.assert_not_called()
        assert session.current_model_id == "default[]"

    async def test_new_session_sets_model_for_different_display_name(self) -> None:
        session, conn, _ = _make_session()
        await session.initialize()
        await session.authenticate()
        await session.new_session(model="Sonnet 4.6")

        conn.set_session_model.assert_called_once_with(
            model_id="claude-sonnet-4-6[thinking=true,context=200k,effort=medium]",
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


# Model ID → display name resolution based on real Cursor ACP payloads
# (see docs/research/agents/cursor-acp-behavior/raw_responses.json).

_CURSOR_MODELS: dict[str, str] = {
    "default[]": "Auto",
    "claude-sonnet-4-6[thinking=true,context=200k,effort=medium]": "Sonnet 4.6",
    "claude-opus-4-6[thinking=true,context=200k,effort=high,fast=false]": "Opus 4.6",
    "gpt-5.4[reasoning=medium,context=272k,fast=false]": "GPT-5.4",
    "gemini-3-flash[]": "Gemini 3 Flash",
    "gpt-5.1[reasoning=medium]": "GPT-5.1",
}


class TestResolveModelName:
    """Unit tests for _resolve_model_name()."""

    def test_exact_match(self) -> None:
        assert _resolve_model_name("default[]", _CURSOR_MODELS) == "Auto"

    def test_exact_match_with_params(self) -> None:
        mid = "claude-sonnet-4-6[thinking=true,context=200k,effort=medium]"
        assert _resolve_model_name(mid, _CURSOR_MODELS) == "Sonnet 4.6"

    def test_bracket_stripped_fallback(self) -> None:
        assert _resolve_model_name("default", _CURSOR_MODELS) == "Auto"

    def test_bracket_stripped_complex(self) -> None:
        assert _resolve_model_name("gpt-5.4", _CURSOR_MODELS) == "GPT-5.4"

    def test_case_insensitive_fallback(self) -> None:
        assert _resolve_model_name("DEFAULT[]", _CURSOR_MODELS) == "Auto"

    def test_none_input(self) -> None:
        assert _resolve_model_name(None, _CURSOR_MODELS) is None

    def test_empty_catalog(self) -> None:
        assert _resolve_model_name("default[]", {}) == "default[]"

    def test_unknown_model_returns_raw_id(self) -> None:
        assert _resolve_model_name("nonexistent", _CURSOR_MODELS) == "nonexistent"


class TestResolveModelId:
    """Unit tests for _resolve_model_id()."""

    def test_exact_match(self) -> None:
        assert _resolve_model_id("default[]", _CURSOR_MODELS) == "default[]"

    def test_bracketless_resolves_to_canonical(self) -> None:
        assert _resolve_model_id("default", _CURSOR_MODELS) == "default[]"

    def test_bracketless_with_params(self) -> None:
        result = _resolve_model_id("gpt-5.4", _CURSOR_MODELS)
        assert result == "gpt-5.4[reasoning=medium,context=272k,fast=false]"

    def test_case_insensitive(self) -> None:
        assert _resolve_model_id("DEFAULT[]", _CURSOR_MODELS) == "default[]"

    def test_unknown_returns_unchanged(self) -> None:
        assert _resolve_model_id("fake-model", _CURSOR_MODELS) == "fake-model"

    def test_empty_catalog_returns_unchanged(self) -> None:
        assert _resolve_model_id("gpt-5.4", {}) == "gpt-5.4"

    def test_gemini_bracketless(self) -> None:
        assert _resolve_model_id("gemini-3-flash", _CURSOR_MODELS) == "gemini-3-flash[]"

    def test_display_name_resolves_to_model_id(self) -> None:
        assert _resolve_model_id("Auto", _CURSOR_MODELS) == "default[]"

    def test_display_name_case_insensitive(self) -> None:
        assert _resolve_model_id("auto", _CURSOR_MODELS) == "default[]"

    def test_display_name_with_spaces(self) -> None:
        assert _resolve_model_id("Gemini 3 Flash", _CURSOR_MODELS) == "gemini-3-flash[]"

    def test_display_name_sonnet(self) -> None:
        mid = "claude-sonnet-4-6[thinking=true,context=200k,effort=medium]"
        assert _resolve_model_id("Sonnet 4.6", _CURSOR_MODELS) == mid

    def test_model_id_preferred_over_display_name(self) -> None:
        """When input matches both a model ID key and a display name, the ID wins."""
        models = {"auto[]": "Something", "other[]": "auto[]"}
        assert _resolve_model_id("auto[]", models) == "auto[]"
