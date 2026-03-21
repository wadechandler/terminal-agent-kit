#!/usr/bin/env python3
"""Cursor ACP Inspection Harness.

Spawns a real Cursor agent via the ACP SDK, exercises the full lifecycle,
and captures all raw responses to JSON + markdown report.

Usage:
    python scripts/agent_inspection/cursor_acp_inspect.py
    python scripts/agent_inspection/cursor_acp_inspect.py --gaps-only --output-suffix _v2
    python scripts/agent_inspection/cursor_acp_inspect.py --v3-only --output-suffix _v3
    python scripts/agent_inspection/cursor_acp_inspect.py --phases 21 --output-suffix _v3b

Reports are written to docs/research/agents/cursor-acp-behavior/.
"""

from __future__ import annotations

import argparse
import asyncio
import base64
import contextlib
import io
import json
import logging
import os
import re
import shutil
import struct
import subprocess
import sys
import tempfile
import time
import traceback
import zlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from acp import PROTOCOL_VERSION, RequestError, spawn_agent_process, text_block
from acp.helpers import image_block
from acp.schema import (
    AgentMessageChunk,
    AgentThoughtChunk,
    AllowedOutcome,
    AvailableCommandsUpdate,
    ConfigOptionUpdate,
    CurrentModeUpdate,
    DeniedOutcome,
    EmbeddedResourceContentBlock,
    HttpMcpServer,
    McpServerStdio,
    PermissionOption,
    RequestPermissionResponse,
    ResourceContentBlock,
    SessionInfoUpdate,
    TextContentBlock,
    TextResourceContents,
    ToolCallProgress,
    ToolCallStart,
    ToolCallUpdate,
    UsageUpdate,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
REPORT_DIR = PROJECT_ROOT / "docs" / "research" / "agents" / "cursor-acp-behavior"

_SECRET_PATTERNS = [
    re.compile(r"sk-[A-Za-z0-9_\-]{20,}"),
    re.compile(r"tok_[A-Za-z0-9_\-]{10,}"),
    re.compile(r"Bearer\s+[A-Za-z0-9_\-\.]{10,}"),
    re.compile(r"key-[A-Za-z0-9_\-]{10,}"),
    re.compile(r"eyJ[A-Za-z0-9_\-]{20,}\.[A-Za-z0-9_\-]{20,}"),  # JWT-like
]

_SECRET_KEYS = {
    "api_key", "apikey", "api-key", "access_token", "accesstoken",
    "secret", "token", "password", "credential", "auth_token",
    "authorization", "cursor_api_key",
}

# Phase numbers for selection
ORIGINAL_PHASES = {1, 2, 3, 4, 5, 6, 7}
GAP_PHASES = {8, 9, 10, 11, 12, 13, 14}
V3_PHASES = {15, 16, 17, 18, 19, 20, 21}
ALL_PHASES = ORIGINAL_PHASES | GAP_PHASES | V3_PHASES


def _sanitize(obj: Any) -> Any:
    """Recursively redact secrets from data before writing to reports."""
    if isinstance(obj, str):
        for pat in _SECRET_PATTERNS:
            obj = pat.sub("[REDACTED]", obj)
        return obj
    if isinstance(obj, dict):
        result = {}
        for k, v in obj.items():
            if k.lower() in _SECRET_KEYS:
                result[k] = "[REDACTED]"
            else:
                result[k] = _sanitize(v)
        return result
    if isinstance(obj, list):
        return [_sanitize(item) for item in obj]
    return obj


def _model_dump(obj: Any) -> Any:
    """Safely convert a pydantic model or arbitrary object to a dict."""
    if obj is None:
        return None
    if hasattr(obj, "model_dump"):
        return obj.model_dump(mode="json", by_alias=True)
    if isinstance(obj, (dict, list, str, int, float, bool)):
        return obj
    return repr(obj)


def _ts() -> float:
    """Monotonic timestamp in seconds."""
    return time.monotonic()


def _wall() -> str:
    """Wall-clock ISO timestamp."""
    return time.strftime("%Y-%m-%dT%H:%M:%S%z")


def _make_tiny_png() -> str:
    """Generate a minimal 8x8 red PNG and return base64-encoded data."""
    width, height = 8, 8

    def _raw_row() -> bytes:
        return b"\x00" + b"\xff\x00\x00" * width

    raw_data = b"".join(_raw_row() for _ in range(height))
    compressed = zlib.compress(raw_data)

    buf = io.BytesIO()
    buf.write(b"\x89PNG\r\n\x1a\n")

    def _write_chunk(chunk_type: bytes, data: bytes) -> None:
        buf.write(struct.pack(">I", len(data)))
        buf.write(chunk_type)
        buf.write(data)
        buf.write(struct.pack(">I", zlib.crc32(chunk_type + data) & 0xFFFFFFFF))

    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    _write_chunk(b"IHDR", ihdr)
    _write_chunk(b"IDAT", compressed)
    _write_chunk(b"IEND", b"")

    return base64.b64encode(buf.getvalue()).decode("ascii")


# ---------------------------------------------------------------------------
# Recording structures
# ---------------------------------------------------------------------------

@dataclass
class UpdateRecord:
    """A single session_update notification."""

    timestamp: float
    wall_clock: str
    update_type: str
    data: dict[str, Any]


@dataclass
class PromptRecord:
    """Full record of a prompt request/response cycle."""

    prompt_text: str
    sent_at: float
    sent_wall: str
    response_stop_reason: str | None = None
    response_at: float | None = None
    response_wall: str | None = None
    duration_s: float | None = None
    updates: list[UpdateRecord] = field(default_factory=list)
    permissions: list[dict[str, Any]] = field(default_factory=list)
    error: str | None = None
    usage: dict[str, Any] | None = None
    response_raw: dict[str, Any] | None = None


@dataclass
class PhaseRecord:
    """Record for a named inspection phase."""

    phase: str
    started_wall: str = ""
    entries: list[dict[str, Any]] = field(default_factory=list)
    error: str | None = None


# ---------------------------------------------------------------------------
# Recording ACP Client
# ---------------------------------------------------------------------------

class RecordingClient:
    """ACP Client that records every callback for inspection."""

    def __init__(self, *, tmpdir: str, permission_mode: str = "allow-always") -> None:
        """Create a recording client bound to a temp workspace."""
        self._tmpdir = tmpdir
        self._permission_mode = permission_mode
        self._updates: list[UpdateRecord] = []
        self._permissions: list[dict[str, Any]] = []
        self._start_time = _ts()
        self._prompt_start: float | None = None
        self._terminals: dict[str, dict[str, Any]] = {}

    @property
    def updates(self) -> list[UpdateRecord]:
        """Return accumulated update records."""
        return self._updates

    @property
    def permissions(self) -> list[dict[str, Any]]:
        """Return accumulated permission records."""
        return self._permissions

    def set_prompt_start(self) -> None:
        """Mark the start of a prompt for per-prompt timestamp offsets."""
        self._prompt_start = _ts()

    def clear_prompt_start(self) -> None:
        """Clear the per-prompt timestamp anchor."""
        self._prompt_start = None

    def clear_updates(self) -> list[UpdateRecord]:
        """Return and clear accumulated updates."""
        result = list(self._updates)
        self._updates = []
        return result

    def clear_permissions(self) -> list[dict[str, Any]]:
        """Return and clear accumulated permission records."""
        result = list(self._permissions)
        self._permissions = []
        return result

    def _record_update(self, update: Any) -> None:
        base = self._prompt_start if self._prompt_start is not None else self._start_time
        update_type = getattr(update, "session_update", type(update).__name__)
        self._updates.append(UpdateRecord(
            timestamp=_ts() - base,
            wall_clock=_wall(),
            update_type=update_type,
            data=_model_dump(update),
        ))

    async def request_permission(
        self,
        options: list[PermissionOption],
        session_id: str,
        tool_call: ToolCallUpdate,
        **kwargs: Any,
    ) -> RequestPermissionResponse:
        """Handle permission requests; records and auto-decides."""
        tool_name = tool_call.title or "unknown"
        base = self._prompt_start if self._prompt_start is not None else self._start_time
        self._permissions.append({
            "timestamp": _ts() - base,
            "wall_clock": _wall(),
            "tool_name": tool_name,
            "tool_call": _model_dump(tool_call),
            "options": [_model_dump(o) for o in options],
            "decision": self._permission_mode,
        })
        logger.info("Permission request: %s -> %s", tool_name, self._permission_mode)

        if self._permission_mode in ("allow-once", "allow-always"):
            option_id = options[0].option_id if options else "allow"
            return RequestPermissionResponse(
                outcome=AllowedOutcome(outcome="selected", option_id=option_id)
            )
        return RequestPermissionResponse(
            outcome=DeniedOutcome(outcome="cancelled")
        )

    async def session_update(
        self,
        session_id: str,
        update: Any,
        **kwargs: Any,
    ) -> None:
        """Record and log each session update notification."""
        self._record_update(update)
        if isinstance(update, AgentMessageChunk):
            if isinstance(update.content, TextContentBlock):
                text = update.content.text or ""
                if text.strip():
                    logger.info("Agent: %s", text[:120])
        elif isinstance(update, AgentThoughtChunk):
            logger.info("Agent thinking...")
        elif isinstance(update, (ToolCallStart, ToolCallProgress)):
            title = getattr(update, "title", None) or ""
            logger.info("Tool: %s", title[:80])
        elif isinstance(update, UsageUpdate):
            cost_str = ""
            if update.cost is not None:
                cost_str = f" cost={update.cost.amount:.4f} {update.cost.currency}"
            logger.info("Usage: size=%s used=%s%s", update.size, update.used, cost_str)
        elif isinstance(update, CurrentModeUpdate):
            logger.info("Mode changed: %s", update.current_mode_id)
        elif isinstance(update, ConfigOptionUpdate):
            logger.info("Config updated: %s", _model_dump(update))
        elif isinstance(update, SessionInfoUpdate):
            logger.info("Session info: title=%s", getattr(update, "title", None))
        elif isinstance(update, AvailableCommandsUpdate):
            logger.info("Available commands updated")
        else:
            update_type = getattr(update, "session_update", type(update).__name__)
            logger.info("Update: %s", update_type)

    async def write_text_file(
        self, content: str, path: str, session_id: str, **kwargs: Any
    ) -> None:
        """Write a file inside the temp workspace."""
        full = os.path.join(self._tmpdir, path.lstrip("/"))
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, "w") as f:
            f.write(content)
        logger.info("write_text_file: %s (%d bytes)", path, len(content))

    async def read_text_file(
        self, path: str, session_id: str, **kwargs: Any
    ) -> Any:
        """Read a file from the temp workspace."""
        full = os.path.join(self._tmpdir, path.lstrip("/"))
        try:
            with open(full) as f:
                content = f.read()
            logger.info("read_text_file: %s (%d bytes)", path, len(content))
            return {"content": content}
        except FileNotFoundError:
            logger.warning("read_text_file: %s not found", path)
            return {"content": ""}

    async def create_terminal(
        self,
        command: str,
        session_id: str,
        args: list[str] | None = None,
        cwd: str | None = None,
        **kwargs: Any,
    ) -> Any:
        """Run a command in a subprocess and record the output."""
        tid = f"term-{len(self._terminals)}"
        effective_cwd = cwd or self._tmpdir
        cmd_parts = [command] + (args or [])
        logger.info("create_terminal: %s (cwd=%s)", " ".join(cmd_parts), effective_cwd)
        try:
            proc = subprocess.run(  # noqa: S603
                cmd_parts,
                capture_output=True,
                text=True,
                timeout=30,
                cwd=effective_cwd,
            )
            self._terminals[tid] = {
                "command": command,
                "args": args,
                "stdout": proc.stdout[:4096],
                "stderr": proc.stderr[:2048],
                "exit_code": proc.returncode,
            }
        except Exception as exc:
            self._terminals[tid] = {
                "command": command,
                "args": args,
                "error": str(exc),
                "exit_code": -1,
            }
        return {"terminalId": tid}

    async def terminal_output(
        self, session_id: str, terminal_id: str, **kwargs: Any
    ) -> Any:
        """Return captured stdout for a terminal."""
        info = self._terminals.get(terminal_id, {})
        return {"output": info.get("stdout", "")}

    async def release_terminal(self, **kwargs: Any) -> None:
        """No-op release."""

    async def wait_for_terminal_exit(
        self, session_id: str, terminal_id: str, **kwargs: Any
    ) -> Any:
        """Return the exit code for a completed terminal."""
        info = self._terminals.get(terminal_id, {})
        return {"exitCode": info.get("exit_code", 0)}

    async def kill_terminal(self, **kwargs: Any) -> None:
        """No-op kill."""

    async def ext_method(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        """Log and return empty for extension methods."""
        logger.info("ext_method: %s", method)
        return {}

    async def ext_notification(self, method: str, params: dict[str, Any]) -> None:
        """Log extension notifications."""
        logger.info("ext_notification: %s", method)

    def on_connect(self, conn: Any) -> None:
        """No-op connection callback."""


# ---------------------------------------------------------------------------
# Seed files
# ---------------------------------------------------------------------------

SEED_FILES = {
    "hello.py": 'print("Hello from Python!")\n',
    "Hello.java": (
        'public class Hello {\n'
        '    public static void main(String[] args) {\n'
        '        System.out.println("Hello from Java!");\n'
        '    }\n'
        '}\n'
    ),
    "hello.js": 'console.log("Hello from JavaScript!");\n',
    "hello.ts": 'const msg: string = "Hello from TypeScript!";\nconsole.log(msg);\n',
    "data.json": json.dumps({"items": [1, 2, 3], "label": "sample"}, indent=2) + "\n",
    "notes.md": "# Notes\n\nThis is a sample markdown file for testing.\n",
}


def _create_seed_files(tmpdir: str) -> None:
    for name, content in SEED_FILES.items():
        path = os.path.join(tmpdir, name)
        with open(path, "w") as f:
            f.write(content)
    logger.info("Created %d seed files in %s", len(SEED_FILES), tmpdir)


# ---------------------------------------------------------------------------
# Prompt helper
# ---------------------------------------------------------------------------

async def _send_prompt(
    conn: Any,
    session_id: str,
    text: str,
    client: RecordingClient,
    *,
    timeout: float = 120.0,
    content_blocks: list[Any] | None = None,
) -> PromptRecord:
    """Send a prompt and record the full response cycle.

    Args:
        conn: ACP connection.
        session_id: Active session ID.
        text: Prompt text (used for logging/recording; ignored if content_blocks set).
        client: Recording client.
        timeout: Max seconds to wait.
        content_blocks: If provided, sent as-is instead of wrapping text.
    """
    record = PromptRecord(
        prompt_text=text,
        sent_at=_ts(),
        sent_wall=_wall(),
    )
    client.set_prompt_start()
    client.clear_updates()
    client.clear_permissions()

    prompt_content = content_blocks if content_blocks is not None else [text_block(text)]

    logger.info(">>> Prompt: %s", text[:100])
    try:
        response = await asyncio.wait_for(
            conn.prompt(
                prompt=prompt_content,
                session_id=session_id,
            ),
            timeout=timeout,
        )
        record.response_at = _ts()
        record.response_wall = _wall()
        record.duration_s = record.response_at - record.sent_at
        record.response_stop_reason = (
            response.stop_reason.value
            if hasattr(response.stop_reason, "value")
            else str(response.stop_reason)
        )
        record.response_raw = _model_dump(response)
        record.usage = _model_dump(getattr(response, "usage", None))
        logger.info(
            "<<< Response: stop_reason=%s, duration=%.1fs",
            record.response_stop_reason, record.duration_s,
        )
        if record.usage:
            logger.info("<<< Usage: %s", record.usage)
    except TimeoutError:
        record.error = f"Timeout after {timeout}s"
        record.response_at = _ts()
        record.duration_s = record.response_at - record.sent_at
        logger.warning("<<< Timeout after %.1fs", record.duration_s)
    except Exception as exc:
        record.error = f"{type(exc).__name__}: {exc}"
        record.response_at = _ts()
        record.duration_s = record.response_at - record.sent_at
        logger.error("<<< Error: %s", record.error)

    record.updates = client.clear_updates()
    record.permissions = client.clear_permissions()
    client.clear_prompt_start()
    return record


def _prompt_record_to_dict(rec: PromptRecord) -> dict[str, Any]:
    """Convert a PromptRecord to a serializable dict."""
    return {
        "prompt_text": rec.prompt_text,
        "sent_wall": rec.sent_wall,
        "response_wall": rec.response_wall,
        "duration_s": rec.duration_s,
        "stop_reason": rec.response_stop_reason,
        "error": rec.error,
        "usage": rec.usage,
        "response_raw": rec.response_raw,
        "update_count": len(rec.updates),
        "updates": [
            {
                "timestamp": u.timestamp,
                "wall_clock": u.wall_clock,
                "type": u.update_type,
                "data": u.data,
            }
            for u in rec.updates
        ],
        "permissions": rec.permissions,
    }


# ---------------------------------------------------------------------------
# Subprocess env (mirrors ACPProvider._subprocess_env)
# ---------------------------------------------------------------------------

def _subprocess_env() -> dict[str, str]:
    """Build subprocess environment with extended PATH."""
    env = os.environ.copy()
    path_parts = env.get("PATH", "").split(os.pathsep)
    for extra in ("/usr/local/bin", "/opt/homebrew/bin", "/opt/homebrew/sbin",
                  os.path.expanduser("~/.local/bin")):
        if extra not in path_parts and os.path.isdir(extra):
            path_parts.append(extra)
    env["PATH"] = os.pathsep.join(path_parts)
    return env


# ---------------------------------------------------------------------------
# Main inspection
# ---------------------------------------------------------------------------

async def run_inspection(*, phases_to_run: set[int] | None = None) -> dict[str, Any]:
    """Run the inspection and return the captured data.

    Args:
        phases_to_run: If set, only run these phase numbers. None = all.
    """
    active = phases_to_run or ALL_PHASES
    results: dict[str, Any] = {
        "run_at": _wall(),
        "phases_requested": sorted(active),
        "phases": {},
    }

    tmpdir = tempfile.mkdtemp(prefix="tak-inspect-")
    logger.info("Temp workspace: %s", tmpdir)
    _create_seed_files(tmpdir)

    env = _subprocess_env()
    cursor_path = shutil.which("cursor", path=env.get("PATH"))
    if not cursor_path:
        logger.error("cursor CLI not found in PATH")
        results["error"] = "cursor CLI not found"
        return results

    cmd = cursor_path
    args = ("agent", "acp")
    logger.info("Spawning: %s %s (cwd=%s)", cmd, " ".join(args), tmpdir)

    client = RecordingClient(tmpdir=tmpdir, permission_mode="allow-always")

    try:
        async with spawn_agent_process(
            client, cmd, *args, env=env, cwd=tmpdir,
        ) as (conn, _process):

            # --- Phase 1 always runs (handshake required) ---
            phase1 = PhaseRecord(phase="handshake", started_wall=_wall())
            logger.info("=== Phase 1: Handshake & Introspection ===")

            try:
                init_resp = await asyncio.wait_for(
                    conn.initialize(protocol_version=PROTOCOL_VERSION),
                    timeout=30.0,
                )
                phase1.entries.append({
                    "call": "initialize",
                    "response": _model_dump(init_resp),
                })
                logger.info("initialize OK")
            except Exception as exc:
                phase1.entries.append({"call": "initialize", "error": str(exc)})
                logger.error("initialize failed: %s", exc)

            try:
                auth_resp = await asyncio.wait_for(
                    conn.authenticate(method_id="cursor_login"),
                    timeout=30.0,
                )
                phase1.entries.append({
                    "call": "authenticate",
                    "response": _model_dump(auth_resp),
                })
                logger.info("authenticate OK")
            except Exception as exc:
                phase1.entries.append({"call": "authenticate", "error": str(exc)})
                logger.error("authenticate failed: %s", exc)

            try:
                session_resp = await asyncio.wait_for(
                    conn.new_session(cwd=tmpdir, mcp_servers=[]),
                    timeout=30.0,
                )
                session_id = session_resp.session_id
                phase1.entries.append({
                    "call": "new_session",
                    "response": _model_dump(session_resp),
                })
                logger.info("new_session OK: session_id=%s", session_id)
            except Exception as exc:
                phase1.entries.append({"call": "new_session", "error": str(exc)})
                logger.error("new_session failed: %s", exc)
                phase1.error = str(exc)
                results["phases"]["handshake"] = _phase_to_dict(phase1)
                return results

            # Extract model/mode/config details
            try:
                if session_resp.models is not None:
                    phase1.entries.append({
                        "detail": "models",
                        "current_model_id": session_resp.models.current_model_id,
                        "available_models": [
                            {"model_id": m.model_id, "name": m.name}
                            for m in session_resp.models.available_models
                        ],
                        "raw": _model_dump(session_resp.models),
                    })
                else:
                    phase1.entries.append({"detail": "models", "value": None})
            except Exception as exc:
                phase1.entries.append({
                    "detail": "models", "error": str(exc),
                    "raw": _model_dump(session_resp.models),
                })

            try:
                if session_resp.modes is not None:
                    phase1.entries.append({
                        "detail": "modes",
                        "current_mode_id": session_resp.modes.current_mode_id,
                        "available_modes": [
                            {"mode_id": m.id, "name": m.name}
                            for m in session_resp.modes.available_modes
                        ],
                        "raw": _model_dump(session_resp.modes),
                    })
                else:
                    phase1.entries.append({"detail": "modes", "value": None})
            except Exception as exc:
                phase1.entries.append({
                    "detail": "modes", "error": str(exc),
                    "raw": _model_dump(session_resp.modes),
                })

            try:
                if session_resp.config_options is not None:
                    phase1.entries.append({
                        "detail": "config_options",
                        "options": [_model_dump(o) for o in session_resp.config_options],
                    })
                else:
                    phase1.entries.append({"detail": "config_options", "value": None})
            except Exception as exc:
                phase1.entries.append({"detail": "config_options", "error": str(exc)})

            if 1 in active:
                try:
                    list_resp = await asyncio.wait_for(
                        conn.list_sessions(cwd=tmpdir), timeout=15.0,
                    )
                    phase1.entries.append({
                        "call": "list_sessions",
                        "response": _model_dump(list_resp),
                    })
                except RequestError as exc:
                    phase1.entries.append({
                        "call": "list_sessions",
                        "error": f"RequestError code={exc.code}: {exc}",
                    })
                except Exception as exc:
                    phase1.entries.append({"call": "list_sessions", "error": str(exc)})

            results["phases"]["handshake"] = _phase_to_dict(phase1)

            # ---------------------------------------------------------------
            # Phase 2: Model & Mode Manipulation
            # ---------------------------------------------------------------
            if 2 in active:
                phase2 = PhaseRecord(phase="model_mode", started_wall=_wall())
                logger.info("=== Phase 2: Model & Mode Manipulation ===")

                if session_resp.models is not None:
                    for m in session_resp.models.available_models:
                        try:
                            resp = await asyncio.wait_for(
                                conn.set_session_model(
                                    model_id=m.model_id, session_id=session_id,
                                ), timeout=15.0,
                            )
                            phase2.entries.append({
                                "call": "set_session_model",
                                "model_id": m.model_id, "model_name": m.name,
                                "success": True, "response": _model_dump(resp),
                            })
                        except Exception as exc:
                            phase2.entries.append({
                                "call": "set_session_model",
                                "model_id": m.model_id, "model_name": m.name,
                                "success": False, "error": str(exc),
                            })

                    for bad_id in ["nonexistent-model", "", "default"]:
                        try:
                            resp = await asyncio.wait_for(
                                conn.set_session_model(
                                    model_id=bad_id, session_id=session_id,
                                ), timeout=10.0,
                            )
                            phase2.entries.append({
                                "call": "set_session_model", "model_id": bad_id,
                                "label": "invalid_model_test", "success": True,
                                "response": _model_dump(resp),
                            })
                        except RequestError as exc:
                            phase2.entries.append({
                                "call": "set_session_model", "model_id": bad_id,
                                "label": "invalid_model_test", "success": False,
                                "error_code": exc.code, "error_message": str(exc),
                            })
                        except Exception as exc:
                            phase2.entries.append({
                                "call": "set_session_model", "model_id": bad_id,
                                "label": "invalid_model_test", "success": False,
                                "error": str(exc),
                            })

                if session_resp.models is not None:
                    default_id = session_resp.models.current_model_id
                    with contextlib.suppress(Exception):
                        await conn.set_session_model(
                            model_id=default_id, session_id=session_id,
                        )

                if session_resp.modes is not None:
                    for m in session_resp.modes.available_modes:
                        try:
                            resp = await asyncio.wait_for(
                                conn.set_session_mode(
                                    mode_id=m.id, session_id=session_id,
                                ), timeout=10.0,
                            )
                            phase2.entries.append({
                                "call": "set_session_mode",
                                "mode_id": m.id, "mode_name": m.name,
                                "success": True, "response": _model_dump(resp),
                            })
                        except Exception as exc:
                            phase2.entries.append({
                                "call": "set_session_mode",
                                "mode_id": m.id, "mode_name": m.name,
                                "success": False, "error": str(exc),
                            })

                    with contextlib.suppress(Exception):
                        await conn.set_session_mode(
                            mode_id="agent", session_id=session_id,
                        )

                results["phases"]["model_mode"] = _phase_to_dict(phase2)

            # ---------------------------------------------------------------
            # Phase 3: Prompts in Temp Workspace
            # ---------------------------------------------------------------
            if 3 in active:
                phase3 = PhaseRecord(phase="prompts", started_wall=_wall())
                logger.info("=== Phase 3: Prompts in Temp Workspace ===")
                for p in [
                    "What files are in the current directory? List them.",
                    "Read hello.py and tell me what it does in one sentence.",
                    "Create a file called greeting.py that prints 'Hello from Cursor'",
                    "Run hello.py and show me the output.",
                ]:
                    rec = await _send_prompt(conn, session_id, p, client)
                    phase3.entries.append(_prompt_record_to_dict(rec))
                results["phases"]["prompts"] = _phase_to_dict(phase3)

            # ---------------------------------------------------------------
            # Phase 4: Permission Modes
            # ---------------------------------------------------------------
            if 4 in active:
                phase4 = PhaseRecord(phase="permissions", started_wall=_wall())
                logger.info("=== Phase 4: Permission Modes ===")
                client._permission_mode = "reject-once"
                rec = await _send_prompt(
                    conn, session_id,
                    "Create a file called should_not_exist.txt with the text 'test'",
                    client,
                )
                phase4.entries.append({"mode": "reject-once", **_prompt_record_to_dict(rec)})
                client._permission_mode = "allow-always"
                results["phases"]["permissions"] = _phase_to_dict(phase4)

            # ---------------------------------------------------------------
            # Phase 5: CWD / Workspace Behavior
            # ---------------------------------------------------------------
            if 5 in active:
                phase5 = PhaseRecord(phase="cwd_behavior", started_wall=_wall())
                logger.info("=== Phase 5: CWD / Workspace Behavior ===")
                rec = await _send_prompt(
                    conn, session_id,
                    "What is your current working directory? "
                    "Print the absolute path and list what files you see.",
                    client,
                )
                phase5.entries.append({"test": "cwd_query", **_prompt_record_to_dict(rec)})
                results["phases"]["cwd_behavior"] = _phase_to_dict(phase5)

            # ---------------------------------------------------------------
            # Phase 6: Streaming / Thinking / Progress
            # ---------------------------------------------------------------
            if 6 in active:
                phase6 = PhaseRecord(phase="streaming", started_wall=_wall())
                logger.info("=== Phase 6: Streaming, Thinking, Progress ===")
                rec = await _send_prompt(
                    conn, session_id,
                    "Create a Python script called fib.py that generates the first "
                    "100 Fibonacci numbers, writes them to fib.json as a JSON array, "
                    "then reads the file back and prints how many numbers are in it.",
                    client, timeout=180.0,
                )
                phase6.entries.append({
                    "test": "long_running_prompt", **_prompt_record_to_dict(rec),
                })
                timeline = _analyze_timeline(rec.updates)
                phase6.entries.append({"test": "timeline_analysis", "analysis": timeline})
                results["phases"]["streaming"] = _phase_to_dict(phase6)

            # ---------------------------------------------------------------
            # Phase 7: Edge Cases & Error Handling
            # ---------------------------------------------------------------
            if 7 in active:
                phase7 = PhaseRecord(phase="edge_cases", started_wall=_wall())
                logger.info("=== Phase 7: Edge Cases & Error Handling ===")

                rec = await _send_prompt(conn, session_id, "", client, timeout=30.0)
                phase7.entries.append({"test": "empty_prompt", **_prompt_record_to_dict(rec)})

                rec = await _send_prompt(
                    conn, session_id, "Write a haiku about programming.",
                    client, timeout=2.0,
                )
                phase7.entries.append({"test": "short_timeout_2s", **_prompt_record_to_dict(rec)})

                if rec.error and "Timeout" in rec.error:
                    try:
                        await asyncio.wait_for(
                            conn.cancel(session_id=session_id), timeout=5.0,
                        )
                        phase7.entries.append({"test": "cancel_after_timeout", "success": True})
                    except Exception as exc:
                        phase7.entries.append({
                            "test": "cancel_after_timeout", "success": False, "error": str(exc),
                        })
                    await asyncio.sleep(2.0)
                    rec = await _send_prompt(
                        conn, session_id, "Say 'recovered' if you can hear me.",
                        client, timeout=30.0,
                    )
                    phase7.entries.append({
                        "test": "recovery_after_timeout", **_prompt_record_to_dict(rec),
                    })

                logger.info("Testing cancel mid-flight...")
                client.clear_updates()
                cancel_record: dict[str, Any] = {"test": "cancel_mid_flight"}
                try:
                    prompt_task = asyncio.create_task(
                        conn.prompt(
                            prompt=[text_block(
                                "Write a detailed essay about the history of computing. "
                                "Make it at least 500 words."
                            )],
                            session_id=session_id,
                        )
                    )
                    await asyncio.sleep(3.0)
                    await conn.cancel(session_id=session_id)
                    try:
                        resp = await asyncio.wait_for(prompt_task, timeout=10.0)
                        cancel_record["stop_reason"] = (
                            resp.stop_reason.value
                            if hasattr(resp.stop_reason, "value")
                            else str(resp.stop_reason)
                        )
                    except TimeoutError:
                        cancel_record["prompt_timed_out_after_cancel"] = True
                    except Exception as exc:
                        cancel_record["prompt_error_after_cancel"] = str(exc)
                    cancel_record["updates_during"] = [
                        {"type": u.update_type, "timestamp": u.timestamp}
                        for u in client.clear_updates()
                    ]
                    cancel_record["success"] = True
                except Exception as exc:
                    cancel_record["success"] = False
                    cancel_record["error"] = str(exc)
                phase7.entries.append(cancel_record)
                results["phases"]["edge_cases"] = _phase_to_dict(phase7)

            # ===============================================================
            # GAP-FILL PHASES (v2)
            # ===============================================================

            # ---------------------------------------------------------------
            # Phase 8: Usage & Cost Tracking
            # ---------------------------------------------------------------
            if 8 in active:
                phase8 = PhaseRecord(phase="usage_tracking", started_wall=_wall())
                logger.info("=== Phase 8: Usage & Cost Tracking ===")

                rec = await _send_prompt(
                    conn, session_id,
                    "Explain the Fibonacci sequence in 3 sentences.",
                    client,
                )
                phase8.entries.append({
                    "test": "short_prompt_usage",
                    **_prompt_record_to_dict(rec),
                })

                usage_updates = [
                    u for u in rec.updates if u.update_type == "usage_update"
                ]
                phase8.entries.append({
                    "test": "usage_update_events",
                    "count": len(usage_updates),
                    "events": [
                        {"timestamp": u.timestamp, "data": u.data}
                        for u in usage_updates
                    ],
                })

                rec2 = await _send_prompt(
                    conn, session_id,
                    "Write a detailed explanation of how quicksort works, "
                    "including the partitioning algorithm, time complexity analysis "
                    "for best, average, and worst cases, and a comparison with mergesort.",
                    client,
                )
                phase8.entries.append({
                    "test": "longer_prompt_usage",
                    **_prompt_record_to_dict(rec2),
                })

                results["phases"]["usage_tracking"] = _phase_to_dict(phase8)

            # ---------------------------------------------------------------
            # Phase 9: set_config_option + Plan Mode Behavior
            # ---------------------------------------------------------------
            if 9 in active:
                phase9 = PhaseRecord(phase="config_option", started_wall=_wall())
                logger.info("=== Phase 9: set_config_option + Plan Mode ===")

                client.clear_updates()
                try:
                    resp = await asyncio.wait_for(
                        conn.set_config_option(
                            config_id="mode", session_id=session_id, value="plan",
                        ), timeout=10.0,
                    )
                    phase9.entries.append({
                        "call": "set_config_option_mode_plan",
                        "success": True, "response": _model_dump(resp),
                        "updates_after": [
                            {"type": u.update_type, "data": u.data}
                            for u in client.clear_updates()
                        ],
                    })
                except Exception as exc:
                    phase9.entries.append({
                        "call": "set_config_option_mode_plan",
                        "success": False, "error": str(exc),
                    })

                rec = await _send_prompt(
                    conn, session_id,
                    "Review the files in the current directory and create a plan "
                    "for adding error handling to hello.py.",
                    client,
                )
                plan_updates = [
                    u for u in rec.updates if u.update_type == "plan"
                ]
                mode_updates = [
                    u for u in rec.updates if u.update_type == "current_mode_update"
                ]
                phase9.entries.append({
                    "test": "plan_mode_prompt",
                    "plan_update_count": len(plan_updates),
                    "mode_update_count": len(mode_updates),
                    "plan_updates": [
                        {"timestamp": u.timestamp, "data": u.data} for u in plan_updates
                    ],
                    **_prompt_record_to_dict(rec),
                })

                client.clear_updates()
                try:
                    resp = await asyncio.wait_for(
                        conn.set_config_option(
                            config_id="mode", session_id=session_id, value="agent",
                        ), timeout=10.0,
                    )
                    phase9.entries.append({
                        "call": "set_config_option_mode_agent",
                        "success": True, "response": _model_dump(resp),
                        "updates_after": [
                            {"type": u.update_type, "data": u.data}
                            for u in client.clear_updates()
                        ],
                    })
                except Exception as exc:
                    phase9.entries.append({
                        "call": "set_config_option_mode_agent",
                        "success": False, "error": str(exc),
                    })

                client.clear_updates()
                try:
                    resp = await asyncio.wait_for(
                        conn.set_config_option(
                            config_id="model", session_id=session_id,
                            value="claude-haiku-4-5[thinking=true]",
                        ), timeout=10.0,
                    )
                    phase9.entries.append({
                        "call": "set_config_option_model_haiku",
                        "success": True, "response": _model_dump(resp),
                        "updates_after": [
                            {"type": u.update_type, "data": u.data}
                            for u in client.clear_updates()
                        ],
                    })
                except Exception as exc:
                    phase9.entries.append({
                        "call": "set_config_option_model_haiku",
                        "success": False, "error": str(exc),
                    })

                with contextlib.suppress(Exception):
                    await conn.set_config_option(
                        config_id="model", session_id=session_id, value="default[]",
                    )

                try:
                    resp = await asyncio.wait_for(
                        conn.set_config_option(
                            config_id="mode", session_id=session_id, value="nonexistent",
                        ), timeout=10.0,
                    )
                    phase9.entries.append({
                        "call": "set_config_option_invalid_mode",
                        "success": True, "response": _model_dump(resp),
                    })
                except RequestError as exc:
                    phase9.entries.append({
                        "call": "set_config_option_invalid_mode",
                        "success": False, "error_code": exc.code,
                        "error_message": str(exc),
                    })
                except Exception as exc:
                    phase9.entries.append({
                        "call": "set_config_option_invalid_mode",
                        "success": False, "error": str(exc),
                    })

                try:
                    resp = await asyncio.wait_for(
                        conn.set_config_option(
                            config_id="bogus", session_id=session_id, value="x",
                        ), timeout=10.0,
                    )
                    phase9.entries.append({
                        "call": "set_config_option_bogus_id",
                        "success": True, "response": _model_dump(resp),
                    })
                except RequestError as exc:
                    phase9.entries.append({
                        "call": "set_config_option_bogus_id",
                        "success": False, "error_code": exc.code,
                        "error_message": str(exc),
                    })
                except Exception as exc:
                    phase9.entries.append({
                        "call": "set_config_option_bogus_id",
                        "success": False, "error": str(exc),
                    })

                results["phases"]["config_option"] = _phase_to_dict(phase9)

            # ---------------------------------------------------------------
            # Phase 10: Permission Rejection
            # ---------------------------------------------------------------
            if 10 in active:
                phase10 = PhaseRecord(phase="permission_rejection", started_wall=_wall())
                logger.info("=== Phase 10: Permission Rejection ===")

                client._permission_mode = "reject-once"

                rec = await _send_prompt(
                    conn, session_id,
                    "Execute the command `python3 -c 'print(42)'` in your terminal "
                    "and tell me the output. You MUST use the terminal tool, "
                    "do not use any other method.",
                    client,
                )
                phase10.entries.append({
                    "test": "forced_terminal_rejected_1",
                    **_prompt_record_to_dict(rec),
                })

                rec2 = await _send_prompt(
                    conn, session_id,
                    "Run `echo hello` in your terminal",
                    client,
                )
                phase10.entries.append({
                    "test": "forced_terminal_rejected_2",
                    **_prompt_record_to_dict(rec2),
                })

                client._permission_mode = "allow-always"
                results["phases"]["permission_rejection"] = _phase_to_dict(phase10)

            # ---------------------------------------------------------------
            # Phase 11: Longer-Running Task
            # ---------------------------------------------------------------
            if 11 in active:
                phase11 = PhaseRecord(phase="long_task", started_wall=_wall())
                logger.info("=== Phase 11: Longer-Running Task ===")

                rec = await _send_prompt(
                    conn, session_id,
                    "Create a Python project with three files: "
                    "(1) models.py with a User dataclass that has name, email, age fields, "
                    "(2) utils.py with a function that validates email format using regex "
                    "and a function that generates a random user, "
                    "(3) main.py that creates 5 random users, validates their emails, "
                    "and writes the valid ones to users.json. "
                    "Then read users.json back and tell me how many valid users were found.",
                    client, timeout=300.0,
                )

                timeline = _analyze_timeline(rec.updates)

                time_to_first = None
                max_gap = 0.0
                if rec.updates:
                    time_to_first = rec.updates[0].timestamp
                    for i in range(1, len(rec.updates)):
                        gap = rec.updates[i].timestamp - rec.updates[i - 1].timestamp
                        if gap > max_gap:
                            max_gap = gap

                tool_call_count = sum(
                    1 for u in rec.updates if u.update_type == "tool_call"
                )

                phase11.entries.append({
                    "test": "multi_file_project",
                    "time_to_first_update_s": time_to_first,
                    "max_gap_between_updates_s": max_gap,
                    "tool_call_count": tool_call_count,
                    "think_respond_work_cycles": len(timeline.get("phases", [])),
                    "timeline": timeline,
                    **_prompt_record_to_dict(rec),
                })

                results["phases"]["long_task"] = _phase_to_dict(phase11)

            # ---------------------------------------------------------------
            # Phase 12: Session Load/Resume
            # ---------------------------------------------------------------
            if 12 in active:
                phase12 = PhaseRecord(phase="session_load", started_wall=_wall())
                logger.info("=== Phase 12: Session Load/Resume ===")

                try:
                    resp = await asyncio.wait_for(
                        conn.load_session(cwd=tmpdir, session_id=session_id),
                        timeout=15.0,
                    )
                    phase12.entries.append({
                        "test": "load_valid_session",
                        "success": True, "response": _model_dump(resp),
                    })
                except RequestError as exc:
                    phase12.entries.append({
                        "test": "load_valid_session",
                        "success": False, "error_code": exc.code,
                        "error_message": str(exc),
                    })
                except Exception as exc:
                    phase12.entries.append({
                        "test": "load_valid_session",
                        "success": False, "error": str(exc),
                    })

                try:
                    resp = await asyncio.wait_for(
                        conn.load_session(
                            cwd=tmpdir, session_id="bogus-session-id-12345",
                        ), timeout=15.0,
                    )
                    phase12.entries.append({
                        "test": "load_bogus_session",
                        "success": True, "response": _model_dump(resp),
                    })
                except RequestError as exc:
                    phase12.entries.append({
                        "test": "load_bogus_session",
                        "success": False, "error_code": exc.code,
                        "error_message": str(exc),
                    })
                except Exception as exc:
                    phase12.entries.append({
                        "test": "load_bogus_session",
                        "success": False, "error": str(exc),
                    })

                results["phases"]["session_load"] = _phase_to_dict(phase12)

            # ---------------------------------------------------------------
            # Phase 13: Image Prompt + Embedded Resource
            # ---------------------------------------------------------------
            if 13 in active:
                phase13 = PhaseRecord(phase="image_and_resource", started_wall=_wall())
                logger.info("=== Phase 13: Image Prompt + Embedded Resource ===")

                png_b64 = _make_tiny_png()

                rec = await _send_prompt(
                    conn, session_id,
                    "Describe this image briefly.",
                    client,
                    content_blocks=[
                        text_block("Describe this image briefly."),
                        image_block(data=png_b64, mime_type="image/png"),
                    ],
                )
                phase13.entries.append({
                    "test": "image_with_text",
                    **_prompt_record_to_dict(rec),
                })

                rec2 = await _send_prompt(
                    conn, session_id,
                    "[image-only prompt]",
                    client,
                    content_blocks=[
                        image_block(data=png_b64, mime_type="image/png"),
                    ],
                )
                phase13.entries.append({
                    "test": "image_only",
                    **_prompt_record_to_dict(rec2),
                })

                embedded = EmbeddedResourceContentBlock(
                    type="resource",
                    resource=TextResourceContents(
                        text="This is a sample config file:\nport=8080\nhost=localhost",
                        uri="file:///config.txt",
                        mime_type="text/plain",
                    ),
                )
                rec3 = await _send_prompt(
                    conn, session_id,
                    "What does this config file contain?",
                    client,
                    content_blocks=[
                        text_block("What does this config file contain?"),
                        embedded,
                    ],
                )
                phase13.entries.append({
                    "test": "embedded_resource",
                    **_prompt_record_to_dict(rec3),
                })

                results["phases"]["image_and_resource"] = _phase_to_dict(phase13)

            # ---------------------------------------------------------------
            # Phase 14: Mock MCP Tool Discovery
            # ---------------------------------------------------------------
            if 14 in active:
                phase14 = PhaseRecord(phase="mcp_discovery", started_wall=_wall())
                logger.info("=== Phase 14: Mock MCP Tool Discovery ===")

                mock_mcp_path = str(Path(__file__).parent / "mock_mcp_echo.py")
                if not os.path.isfile(mock_mcp_path):
                    phase14.entries.append({
                        "test": "mock_mcp_setup",
                        "error": f"mock_mcp_echo.py not found at {mock_mcp_path}",
                    })
                else:
                    mcp_servers = [
                        McpServerStdio(
                            command=sys.executable,
                            args=[mock_mcp_path],
                            env=[],
                            name="tak-test-echo",
                        )
                    ]

                    try:
                        mcp_session_resp = await asyncio.wait_for(
                            conn.new_session(cwd=tmpdir, mcp_servers=mcp_servers),
                            timeout=30.0,
                        )
                        mcp_session_id = mcp_session_resp.session_id
                        phase14.entries.append({
                            "test": "mcp_session_created",
                            "session_id": mcp_session_id,
                            "response": _model_dump(mcp_session_resp),
                        })
                        logger.info(
                            "MCP session created: %s", mcp_session_id,
                        )

                        rec = await _send_prompt(
                            conn, mcp_session_id,
                            "Use the echo tool from the tak-test-echo MCP server "
                            "to echo the text 'hello from tak'. Show me the result.",
                            client,
                        )
                        phase14.entries.append({
                            "test": "mcp_echo_tool_use",
                            **_prompt_record_to_dict(rec),
                        })

                        rec2 = await _send_prompt(
                            conn, mcp_session_id,
                            "What tools do you have available? "
                            "List all of them including any from MCP servers.",
                            client,
                        )
                        phase14.entries.append({
                            "test": "mcp_tool_listing",
                            **_prompt_record_to_dict(rec2),
                        })

                    except Exception as exc:
                        phase14.entries.append({
                            "test": "mcp_session_failed",
                            "error": f"{type(exc).__name__}: {exc}",
                        })
                        logger.error("MCP session failed: %s", exc)

                results["phases"]["mcp_discovery"] = _phase_to_dict(phase14)

            # ===============================================================
            # V3 PHASES
            # ===============================================================

            # HTTP mock MCP server -- shared by phases 16 and 18
            _http_server = None
            _http_port = 0
            if active & {16, 18}:
                try:
                    _scripts_dir = str(Path(__file__).resolve().parent)
                    if _scripts_dir not in sys.path:
                        sys.path.insert(0, _scripts_dir)
                    from mock_mcp_http import start_server as _start_http
                    _http_server, _http_port = _start_http()
                    logger.info("HTTP mock MCP server on port %d", _http_port)
                except Exception as exc:
                    logger.error("Failed to start HTTP mock MCP: %s", exc)

            # ---------------------------------------------------------------
            # Phase 15: Java/TypeScript Compilation
            # ---------------------------------------------------------------
            if 15 in active:
                phase15 = PhaseRecord(phase="java_ts_compile", started_wall=_wall())
                logger.info("=== Phase 15: Java/TypeScript Compilation ===")

                rec = await _send_prompt(
                    conn, session_id,
                    "Compile and run Hello.java using javac and java. "
                    "Show me the output.",
                    client,
                )
                phase15.entries.append({
                    "test": "java_compile_run",
                    **_prompt_record_to_dict(rec),
                })

                rec2 = await _send_prompt(
                    conn, session_id,
                    "Run hello.ts. Try using ts-node, tsx, or compile with "
                    "tsc first. Show me the output.",
                    client,
                )
                phase15.entries.append({
                    "test": "typescript_run",
                    **_prompt_record_to_dict(rec2),
                })

                results["phases"]["java_ts_compile"] = _phase_to_dict(phase15)

            # ---------------------------------------------------------------
            # Phase 16: MCP Tool Discovery via HTTP Transport
            # ---------------------------------------------------------------
            if 16 in active:
                phase16 = PhaseRecord(
                    phase="mcp_http_discovery", started_wall=_wall(),
                )
                logger.info("=== Phase 16: MCP Tool Discovery (HTTP) ===")

                if not _http_server:
                    phase16.entries.append({
                        "test": "http_mcp_setup",
                        "error": "HTTP mock MCP server not running",
                    })
                else:
                    try:
                        mcp_http_session_resp = await asyncio.wait_for(
                            conn.new_session(
                                cwd=tmpdir,
                                mcp_servers=[
                                    HttpMcpServer(
                                        type="http",
                                        name="tak-test-echo-http",
                                        url=f"http://127.0.0.1:{_http_port}/",
                                        headers=[],
                                    )
                                ],
                            ),
                            timeout=30.0,
                        )
                        mcp_http_sid = mcp_http_session_resp.session_id
                        phase16.entries.append({
                            "test": "http_mcp_session_created",
                            "session_id": mcp_http_sid,
                            "response": _model_dump(mcp_http_session_resp),
                        })
                        logger.info(
                            "HTTP MCP session: %s", mcp_http_sid,
                        )

                        rec = await _send_prompt(
                            conn, mcp_http_sid,
                            "Use the echo tool from the tak-test-echo-http "
                            "MCP server to echo 'hello from tak via HTTP'. "
                            "Show the result.",
                            client,
                        )
                        phase16.entries.append({
                            "test": "http_mcp_echo_tool_use",
                            **_prompt_record_to_dict(rec),
                        })

                        rec2 = await _send_prompt(
                            conn, mcp_http_sid,
                            "List all tools you have available, including "
                            "any from MCP servers.",
                            client,
                        )
                        phase16.entries.append({
                            "test": "http_mcp_tool_listing",
                            **_prompt_record_to_dict(rec2),
                        })

                    except Exception as exc:
                        phase16.entries.append({
                            "test": "http_mcp_session_failed",
                            "error": f"{type(exc).__name__}: {exc}",
                        })
                        logger.error("HTTP MCP session failed: %s", exc)

                results["phases"]["mcp_http_discovery"] = _phase_to_dict(phase16)

            # ---------------------------------------------------------------
            # Phase 17: load_session Conversation Recall
            # ---------------------------------------------------------------
            if 17 in active:
                phase17 = PhaseRecord(
                    phase="session_recall", started_wall=_wall(),
                )
                logger.info("=== Phase 17: load_session Conversation Recall ===")

                rec = await _send_prompt(
                    conn, session_id,
                    "I'm going to tell you a code word. Remember it: "
                    "PHOENIX42. Confirm you've noted it.",
                    client,
                )
                phase17.entries.append({
                    "test": "set_code_word",
                    **_prompt_record_to_dict(rec),
                })

                try:
                    load_resp = await asyncio.wait_for(
                        conn.load_session(cwd=tmpdir, session_id=session_id),
                        timeout=15.0,
                    )
                    phase17.entries.append({
                        "test": "load_session_for_recall",
                        "success": True,
                        "response": _model_dump(load_resp),
                    })
                except Exception as exc:
                    phase17.entries.append({
                        "test": "load_session_for_recall",
                        "success": False,
                        "error": f"{type(exc).__name__}: {exc}",
                    })

                rec2 = await _send_prompt(
                    conn, session_id,
                    "What was the code word I told you earlier?",
                    client,
                )
                phase17.entries.append({
                    "test": "recall_code_word",
                    **_prompt_record_to_dict(rec2),
                })

                results["phases"]["session_recall"] = _phase_to_dict(phase17)

            # ---------------------------------------------------------------
            # Phase 18: ResourceContentBlock (URI-based)
            # ---------------------------------------------------------------
            if 18 in active:
                phase18 = PhaseRecord(
                    phase="resource_content_block", started_wall=_wall(),
                )
                logger.info("=== Phase 18: ResourceContentBlock (URI) ===")

                # Test A: file:// URI
                file_uri = f"file://{tmpdir}/hello.py"
                resource_file = ResourceContentBlock(
                    type="resource_link",
                    name="hello.py",
                    uri=file_uri,
                    mime_type="text/x-python",
                    size=len(SEED_FILES["hello.py"]),
                    description="A Python hello world script",
                )
                try:
                    rec = await _send_prompt(
                        conn, session_id,
                        "What does this file do?",
                        client,
                        content_blocks=[
                            text_block("What does this file do?"),
                            resource_file,
                        ],
                    )
                    phase18.entries.append({
                        "test": "resource_link_file_uri",
                        "uri": file_uri,
                        **_prompt_record_to_dict(rec),
                    })
                except Exception as exc:
                    phase18.entries.append({
                        "test": "resource_link_file_uri",
                        "uri": file_uri,
                        "error": f"{type(exc).__name__}: {exc}",
                    })

                # Test B: http:// URI (needs HTTP mock server)
                if _http_server:
                    http_uri = (
                        f"http://127.0.0.1:{_http_port}/resources/config.txt"
                    )
                    resource_http = ResourceContentBlock(
                        type="resource_link",
                        name="config.txt",
                        uri=http_uri,
                        mime_type="text/plain",
                        description="Server configuration file",
                    )
                    try:
                        rec2 = await _send_prompt(
                            conn, session_id,
                            "What settings are in this config?",
                            client,
                            content_blocks=[
                                text_block("What settings are in this config?"),
                                resource_http,
                            ],
                        )
                        phase18.entries.append({
                            "test": "resource_link_http_uri",
                            "uri": http_uri,
                            **_prompt_record_to_dict(rec2),
                        })
                    except Exception as exc:
                        phase18.entries.append({
                            "test": "resource_link_http_uri",
                            "uri": http_uri,
                            "error": f"{type(exc).__name__}: {exc}",
                        })
                else:
                    phase18.entries.append({
                        "test": "resource_link_http_uri",
                        "error": "HTTP mock server not running",
                    })

                # Test C: plain text baseline
                rec3 = await _send_prompt(
                    conn, session_id,
                    "Read hello.py and tell me what it does.",
                    client,
                )
                phase18.entries.append({
                    "test": "text_path_baseline",
                    **_prompt_record_to_dict(rec3),
                })

                results["phases"]["resource_content_block"] = (
                    _phase_to_dict(phase18)
                )

            # Shut down HTTP mock server after phases 16/18
            if _http_server:
                _http_server.shutdown()
                logger.info("HTTP mock MCP server shut down")

            # ---------------------------------------------------------------
            # Phase 19: Agent-Initiated Mode Switching
            # ---------------------------------------------------------------
            if 19 in active:
                phase19 = PhaseRecord(
                    phase="agent_mode_switch", started_wall=_wall(),
                )
                logger.info("=== Phase 19: Agent-Initiated Mode Switching ===")

                client.clear_updates()
                rec = await _send_prompt(
                    conn, session_id,
                    "I need you to first plan your approach, then execute it. "
                    "Create a plan for refactoring hello.py to add command-line "
                    "argument parsing, then implement the plan. Switch between "
                    "plan and agent modes as you see fit.",
                    client, timeout=180.0,
                )

                mode_updates = [
                    u for u in rec.updates
                    if u.update_type == "current_mode_update"
                ]
                plan_updates = [
                    u for u in rec.updates if u.update_type == "plan"
                ]

                phase19.entries.append({
                    "test": "prompted_mode_switch",
                    "mode_update_count": len(mode_updates),
                    "plan_update_count": len(plan_updates),
                    "mode_updates": [
                        {"timestamp": u.timestamp, "data": u.data}
                        for u in mode_updates
                    ],
                    **_prompt_record_to_dict(rec),
                })

                results["phases"]["agent_mode_switch"] = (
                    _phase_to_dict(phase19)
                )

            # ---------------------------------------------------------------
            # Phase 20: Multi-Session Isolation
            # ---------------------------------------------------------------
            if 20 in active:
                phase20 = PhaseRecord(
                    phase="multi_session", started_wall=_wall(),
                )
                logger.info("=== Phase 20: Multi-Session Isolation ===")

                try:
                    sess_a_resp = await asyncio.wait_for(
                        conn.new_session(cwd=tmpdir, mcp_servers=[]),
                        timeout=30.0,
                    )
                    sid_a = sess_a_resp.session_id
                    phase20.entries.append({
                        "test": "create_session_a",
                        "session_id": sid_a,
                        "success": True,
                    })

                    sess_b_resp = await asyncio.wait_for(
                        conn.new_session(cwd=tmpdir, mcp_servers=[]),
                        timeout=30.0,
                    )
                    sid_b = sess_b_resp.session_id
                    phase20.entries.append({
                        "test": "create_session_b",
                        "session_id": sid_b,
                        "success": True,
                    })

                    logger.info(
                        "Session A=%s, Session B=%s", sid_a, sid_b,
                    )

                    rec_a1 = await _send_prompt(
                        conn, sid_a,
                        "Remember this: the secret word for this session "
                        "is ALPHA. Confirm you've noted it.",
                        client,
                    )
                    phase20.entries.append({
                        "test": "set_word_session_a",
                        **_prompt_record_to_dict(rec_a1),
                    })

                    rec_b1 = await _send_prompt(
                        conn, sid_b,
                        "Remember this: the secret word for this session "
                        "is BRAVO. Confirm you've noted it.",
                        client,
                    )
                    phase20.entries.append({
                        "test": "set_word_session_b",
                        **_prompt_record_to_dict(rec_b1),
                    })

                    rec_a2 = await _send_prompt(
                        conn, sid_a,
                        "What is the secret word for this session?",
                        client,
                    )
                    phase20.entries.append({
                        "test": "recall_session_a",
                        **_prompt_record_to_dict(rec_a2),
                    })

                    rec_b2 = await _send_prompt(
                        conn, sid_b,
                        "What is the secret word for this session?",
                        client,
                    )
                    phase20.entries.append({
                        "test": "recall_session_b",
                        **_prompt_record_to_dict(rec_b2),
                    })

                except Exception as exc:
                    phase20.entries.append({
                        "test": "multi_session_failed",
                        "error": f"{type(exc).__name__}: {exc}",
                    })
                    logger.error("Multi-session test failed: %s", exc)

                results["phases"]["multi_session"] = _phase_to_dict(phase20)

        # ---------------------------------------------------------------
        # Phase 21: MCP via .cursor/mcp.json (separate agent process)
        # ---------------------------------------------------------------
        if 21 in active:
            phase21 = PhaseRecord(phase="mcp_config", started_wall=_wall())
            logger.info("=== Phase 21: MCP via .cursor/mcp.json ===")

            _scripts_dir = str(Path(__file__).resolve().parent)
            if _scripts_dir not in sys.path:
                sys.path.insert(0, _scripts_dir)

            http_srv = None
            http_port = 0
            tmpdir2 = tempfile.mkdtemp(prefix="tak-inspect-mcp-")
            try:
                from mock_mcp_http import start_server as _start_http_21

                http_srv, http_port = _start_http_21()
                logger.info("Phase 21 HTTP mock on port %d", http_port)

                mcp_echo_log = os.path.join(tmpdir2, "mcp_echo.log")
                mcp_config = {
                    "mcpServers": {
                        "tak-test-echo": {
                            "type": "stdio",
                            "command": sys.executable,
                            "args": [
                                str(Path(__file__).resolve().parent / "mock_mcp_echo.py"),
                            ],
                            "env": {
                                "MCP_ECHO_LOG_FILE": mcp_echo_log,
                            },
                        },
                        "tak-test-echo-http": {
                            "url": f"http://127.0.0.1:{http_port}/",
                        },
                    },
                }
                logger.info("MCP echo log file: %s", mcp_echo_log)

                import hashlib
                realpath2 = os.path.realpath(tmpdir2)
                slug = re.sub(r"[^A-Za-z0-9]+", "-", realpath2).strip("-")
                approvals = []
                for srv_name, srv_cfg in mcp_config["mcpServers"].items():
                    hash_input = json.dumps(
                        {"path": realpath2, "server": srv_cfg},
                        separators=(",", ":"),
                    )
                    h = hashlib.sha256(hash_input.encode()).hexdigest()[:16]
                    key = f"{srv_name}-{h}"
                    approvals.append(key)
                    logger.info("Approval key: %s (input=%s)", key, hash_input)

                approval_dir = os.path.join(
                    os.path.expanduser("~"), ".cursor", "projects", slug,
                )
                os.makedirs(approval_dir, exist_ok=True)
                approval_path = os.path.join(approval_dir, "mcp-approvals.json")
                with open(approval_path, "w") as f:
                    json.dump(approvals, f)
                logger.info("Wrote MCP approvals: %s", approval_path)

                phase21.entries.append({
                    "test": "mcp_approvals_written",
                    "path": approval_path,
                    "keys": approvals,
                    "slug": slug,
                })

                mcp_dir = os.path.join(tmpdir2, ".cursor")
                os.makedirs(mcp_dir, exist_ok=True)
                mcp_json_path = os.path.join(mcp_dir, "mcp.json")
                with open(mcp_json_path, "w") as f:
                    json.dump(mcp_config, f, indent=2)
                logger.info("Wrote %s", mcp_json_path)

                phase21.entries.append({
                    "test": "mcp_config_written",
                    "path": mcp_json_path,
                    "config": mcp_config,
                })

                _create_seed_files(tmpdir2)

                client2 = RecordingClient(
                    tmpdir=tmpdir2, permission_mode="allow-always",
                )
                async with spawn_agent_process(
                    client2, cmd, *args, env=env, cwd=tmpdir2,
                ) as (conn2, _proc2):
                    init2 = await asyncio.wait_for(
                        conn2.initialize(protocol_version=PROTOCOL_VERSION),
                        timeout=30.0,
                    )
                    phase21.entries.append({
                        "test": "initialize",
                        "response": _model_dump(init2),
                    })

                    await asyncio.wait_for(
                        conn2.authenticate(method_id="cursor_login"),
                        timeout=30.0,
                    )

                    sess2 = await asyncio.wait_for(
                        conn2.new_session(cwd=tmpdir2, mcp_servers=[]),
                        timeout=30.0,
                    )
                    sid2 = sess2.session_id
                    phase21.entries.append({
                        "test": "new_session",
                        "session_id": sid2,
                    })
                    logger.info("Phase 21 session: %s", sid2)

                    rec_list = await _send_prompt(
                        conn2, sid2,
                        "List all tools you have available, including any "
                        "from MCP servers. Be thorough.",
                        client2, timeout=120.0,
                    )
                    phase21.entries.append({
                        "test": "list_tools",
                        **_prompt_record_to_dict(rec_list),
                    })

                    rec_stdio = await _send_prompt(
                        conn2, sid2,
                        "Use the echo tool from tak-test-echo to echo "
                        "'hello from tak'. Show the result.",
                        client2, timeout=120.0,
                    )
                    phase21.entries.append({
                        "test": "mcp_stdio_echo",
                        **_prompt_record_to_dict(rec_stdio),
                    })

                    rec_http = await _send_prompt(
                        conn2, sid2,
                        "Use the echo tool from tak-test-echo-http to echo "
                        "'hello via HTTP'. Show the result.",
                        client2, timeout=120.0,
                    )
                    phase21.entries.append({
                        "test": "mcp_http_echo",
                        **_prompt_record_to_dict(rec_http),
                    })

            except Exception as exc:
                phase21.entries.append({
                    "test": "phase21_failed",
                    "error": f"{type(exc).__name__}: {exc}",
                    "traceback": traceback.format_exc(),
                })
                logger.error("Phase 21 failed: %s", exc, exc_info=True)
            finally:
                if http_srv:
                    http_srv.shutdown()
                    logger.info("Phase 21 HTTP mock shut down")
                try:
                    if os.path.exists(mcp_echo_log):
                        with open(mcp_echo_log) as lf:
                            log_contents = lf.read()
                        logger.info(
                            "MCP echo log (%d bytes):\n%s",
                            len(log_contents), log_contents,
                        )
                        phase21.entries.append({
                            "test": "mcp_echo_server_log",
                            "log": log_contents,
                        })
                    else:
                        logger.info("No MCP echo log file found at %s", mcp_echo_log)
                        phase21.entries.append({
                            "test": "mcp_echo_server_log",
                            "log": None,
                            "note": "Log file not created -- server may not have been started",
                        })
                except Exception as log_exc:
                    logger.warning("Failed to read MCP echo log: %s", log_exc)
                try:
                    shutil.rmtree(tmpdir2)
                    logger.info("Cleaned up %s", tmpdir2)
                except Exception:
                    logger.warning("Failed to clean up %s", tmpdir2)
                try:
                    if os.path.isdir(approval_dir):
                        shutil.rmtree(approval_dir)
                        logger.info("Cleaned up approval dir %s", approval_dir)
                except Exception:
                    logger.warning("Failed to clean up %s", approval_dir)

            results["phases"]["mcp_config"] = _phase_to_dict(phase21)

    except Exception as exc:
        results["fatal_error"] = f"{type(exc).__name__}: {exc}"
        results["traceback"] = traceback.format_exc()
        logger.error("Fatal error: %s", exc, exc_info=True)
    finally:
        try:
            shutil.rmtree(tmpdir)
            logger.info("Cleaned up %s", tmpdir)
        except Exception:
            logger.warning("Failed to clean up %s", tmpdir)

    return results


def _phase_to_dict(phase: PhaseRecord) -> dict[str, Any]:
    """Convert a PhaseRecord to a serializable dict."""
    return {
        "phase": phase.phase,
        "started_wall": phase.started_wall,
        "entries": phase.entries,
        "error": phase.error,
    }


def _analyze_timeline(updates: list[UpdateRecord]) -> dict[str, Any]:
    """Analyze the sequence of updates to extract phase timing."""
    analysis: dict[str, Any] = {
        "total_updates": len(updates),
        "update_types": {},
        "phases": [],
    }

    type_counts: dict[str, int] = {}
    type_first: dict[str, float] = {}
    type_last: dict[str, float] = {}

    for u in updates:
        t = u.update_type
        type_counts[t] = type_counts.get(t, 0) + 1
        if t not in type_first:
            type_first[t] = u.timestamp
        type_last[t] = u.timestamp

    analysis["update_types"] = {
        t: {
            "count": type_counts[t],
            "first_at": type_first[t],
            "last_at": type_last[t],
            "duration_s": type_last[t] - type_first[t],
        }
        for t in sorted(type_counts)
    }

    current_phase = None
    phase_start = 0.0
    for u in updates:
        phase_name = _classify_update_phase(u.update_type)
        if phase_name != current_phase:
            if current_phase is not None:
                analysis["phases"].append({
                    "phase": current_phase,
                    "start": phase_start,
                    "end": u.timestamp,
                    "duration_s": u.timestamp - phase_start,
                })
            current_phase = phase_name
            phase_start = u.timestamp

    if current_phase is not None and updates:
        analysis["phases"].append({
            "phase": current_phase,
            "start": phase_start,
            "end": updates[-1].timestamp,
            "duration_s": updates[-1].timestamp - phase_start,
        })

    return analysis


def _classify_update_phase(update_type: str) -> str:
    """Map an update type string to a human-readable phase name."""
    if "thought" in update_type.lower():
        return "thinking"
    if "tool_call" in update_type.lower():
        return "working"
    if "agent_message" in update_type.lower():
        return "responding"
    if update_type == "plan":
        return "planning"
    if update_type in ("current_mode_update", "config_option_update"):
        return "config_change"
    if update_type == "session_info_update":
        return "session_info"
    if "usage" in update_type.lower():
        return "usage_report"
    if "user_message" in update_type.lower():
        return "user_echo"
    if "available_commands" in update_type.lower():
        return "commands_update"
    return "other"


# ---------------------------------------------------------------------------
# Report generation
# ---------------------------------------------------------------------------

def _generate_report(data: dict[str, Any]) -> str:
    """Generate a human-readable markdown report from captured data."""
    lines: list[str] = []
    lines.append("# Cursor ACP Behavior Report")
    lines.append("")
    lines.append(f"**Generated**: {data.get('run_at', 'unknown')}")
    phases_req = data.get("phases_requested", [])
    if phases_req:
        lines.append(f"**Phases**: {phases_req}")
    lines.append("")

    if data.get("fatal_error"):
        lines.append(f"## Fatal Error\n\n```\n{data['fatal_error']}\n```\n")
        if data.get("traceback"):
            lines.append(f"```\n{data['traceback']}\n```\n")
        return "\n".join(lines)

    phases = data.get("phases", {})

    # --- Phase 1: Handshake ---
    _report_handshake(phases, lines)
    # --- Phase 2: Model & Mode ---
    _report_model_mode(phases, lines)
    # --- Phase 3: Prompts ---
    _report_prompts(phases, lines)
    # --- Phase 4: Permissions ---
    _report_permissions(phases, lines)
    # --- Phase 5: CWD ---
    _report_cwd(phases, lines)
    # --- Phase 6: Streaming ---
    _report_streaming(phases, lines)
    # --- Phase 7: Edge Cases ---
    _report_edge_cases(phases, lines)
    # --- Phase 8: Usage ---
    _report_usage(phases, lines)
    # --- Phase 9: Config Option ---
    _report_config_option(phases, lines)
    # --- Phase 10: Permission Rejection ---
    _report_permission_rejection(phases, lines)
    # --- Phase 11: Long Task ---
    _report_long_task(phases, lines)
    # --- Phase 12: Session Load ---
    _report_session_load(phases, lines)
    # --- Phase 13: Image & Resource ---
    _report_image_resource(phases, lines)
    # --- Phase 14: MCP Discovery ---
    _report_mcp_discovery(phases, lines)
    # --- Phase 15: Java/TS ---
    _report_java_ts(phases, lines)
    # --- Phase 16: MCP HTTP ---
    _report_mcp_http(phases, lines)
    # --- Phase 17: Session Recall ---
    _report_session_recall(phases, lines)
    # --- Phase 18: ResourceContentBlock ---
    _report_resource_content_block(phases, lines)
    # --- Phase 19: Mode Switching ---
    _report_agent_mode_switch(phases, lines)
    # --- Phase 20: Multi-Session ---
    _report_multi_session(phases, lines)
    # --- Phase 21: MCP via .cursor/mcp.json ---
    _report_mcp_config(phases, lines)

    lines.append("## Ideation & Application\n")
    lines.append("See [analysis.md](analysis.md) for full reasoning, discovery, and UX ideation")
    lines.append("derived from this data.\n")

    return "\n".join(lines)


def _report_handshake(phases: dict, lines: list[str]) -> None:
    hs = phases.get("handshake", {})
    if not hs:
        return
    lines.append("## Phase 1: Handshake & Introspection\n")
    for entry in hs.get("entries", []):
        call = entry.get("call", entry.get("detail", ""))
        if call == "initialize":
            lines.append("### initialize\n")
            if entry.get("error"):
                lines.append(f"**Error**: {entry['error']}\n")
            else:
                lines.append(f"```json\n{json.dumps(entry.get('response'), indent=2)}\n```\n")
        elif call == "authenticate":
            lines.append("### authenticate\n")
            lines.append(f"**Error**: {entry['error']}\n" if entry.get("error") else "OK\n")
        elif call == "new_session":
            lines.append("### new_session\n")
            if entry.get("error"):
                lines.append(f"**Error**: {entry['error']}\n")
            else:
                resp = entry.get("response", {})
                lines.append(f"- **session_id**: `{resp.get('sessionId', 'N/A')}`\n")
        elif entry.get("detail") == "models":
            lines.append("### Models\n")
            if "value" in entry and entry["value"] is None:
                lines.append("*models is None in response*\n")
            elif entry.get("error"):
                lines.append(f"**Error**: {entry['error']}\n")
            else:
                lines.append(f"- **current_model_id**: `{entry.get('current_model_id')}`\n")
                lines.append("| model_id | name |")
                lines.append("|----------|------|")
                for m in entry.get("available_models", []):
                    lines.append(f"| `{m['model_id']}` | {m['name']} |")
                lines.append("")
        elif entry.get("detail") == "modes":
            lines.append("### Modes\n")
            if "value" in entry and entry["value"] is None:
                lines.append("*modes is None in response*\n")
            elif entry.get("error"):
                lines.append(f"**Error**: {entry['error']}\n")
            else:
                lines.append(f"- **current_mode_id**: `{entry.get('current_mode_id')}`\n")
                lines.append("| mode_id | name |")
                lines.append("|---------|------|")
                for m in entry.get("available_modes", []):
                    lines.append(f"| `{m['mode_id']}` | {m['name']} |")
                lines.append("")
        elif entry.get("detail") == "config_options":
            lines.append("### Config Options\n")
            if "value" in entry and entry["value"] is None:
                lines.append("*config_options is None in response*\n")
            elif entry.get("error"):
                lines.append(f"**Error**: {entry['error']}\n")
            else:
                lines.append(f"```json\n{json.dumps(entry.get('options'), indent=2)}\n```\n")
        elif call == "list_sessions":
            lines.append("### list_sessions\n")
            if entry.get("error"):
                lines.append(f"**Error**: {entry['error']}\n")
            else:
                lines.append(f"```json\n{json.dumps(entry.get('response'), indent=2)}\n```\n")


def _report_model_mode(phases: dict, lines: list[str]) -> None:
    mm = phases.get("model_mode", {})
    if not mm:
        return
    lines.append("## Phase 2: Model & Mode Manipulation\n")
    for entry in mm.get("entries", []):
        call = entry.get("call", "")
        if call == "set_session_model":
            mid = entry.get("model_id", "?")
            label = entry.get("label", "")
            success = entry.get("success", False)
            if label:
                lines.append(f"- `set_session_model({mid})` [{label}]: "
                             f"{'OK' if success else 'FAILED'}")
            else:
                name = entry.get("model_name", "")
                lines.append(f"- `set_session_model({mid})` ({name}): "
                             f"{'OK' if success else 'FAILED'}")
            if not success:
                err = entry.get("error", entry.get("error_message", ""))
                code = entry.get("error_code", "")
                if code:
                    lines.append(f"  - code={code}, {err}")
                elif err:
                    lines.append(f"  - {err}")
        elif call == "set_session_mode":
            mid = entry.get("mode_id", "?")
            name = entry.get("mode_name", "")
            success = entry.get("success", False)
            lines.append(f"- `set_session_mode({mid})` ({name}): "
                         f"{'OK' if success else 'FAILED'}")
    lines.append("")


def _report_prompts(phases: dict, lines: list[str]) -> None:
    pr = phases.get("prompts", {})
    if not pr:
        return
    lines.append("## Phase 3: Prompts\n")
    for i, entry in enumerate(pr.get("entries", []), 1):
        lines.append(f"### Prompt {i}\n")
        lines.append(f"**Text**: {entry.get('prompt_text', '')[:200]}\n")
        _report_prompt_summary(entry, lines)


def _report_permissions(phases: dict, lines: list[str]) -> None:
    perm = phases.get("permissions", {})
    if not perm:
        return
    lines.append("## Phase 4: Permission Modes\n")
    for entry in perm.get("entries", []):
        mode = entry.get("mode", "?")
        lines.append(f"### Mode: {mode}\n")
        _report_prompt_summary(entry, lines)


def _report_cwd(phases: dict, lines: list[str]) -> None:
    cwd = phases.get("cwd_behavior", {})
    if not cwd:
        return
    lines.append("## Phase 5: CWD / Workspace Behavior\n")
    for entry in cwd.get("entries", []):
        lines.append(f"### {entry.get('test', '?')}\n")
        lines.append(f"- Duration: {entry.get('duration_s', 0):.1f}s")
        for u in entry.get("updates", []):
            if u.get("type") == "agent_message_chunk":
                text = u.get("data", {}).get("content", {}).get("text", "")
                if text.strip():
                    lines.append(f"\nAgent response excerpt:\n> {text[:500]}\n")
                    break
        lines.append("")


def _report_streaming(phases: dict, lines: list[str]) -> None:
    stream = phases.get("streaming", {})
    if not stream:
        return
    lines.append("## Phase 6: Streaming Timeline Analysis\n")
    for entry in stream.get("entries", []):
        test = entry.get("test", "")
        if test == "long_running_prompt":
            lines.append("### Long-running prompt\n")
            _report_prompt_summary(entry, lines)
        elif test == "timeline_analysis":
            _report_timeline(entry.get("analysis", {}), lines)


def _report_edge_cases(phases: dict, lines: list[str]) -> None:
    edge = phases.get("edge_cases", {})
    if not edge:
        return
    lines.append("## Phase 7: Edge Cases & Error Handling\n")
    for entry in edge.get("entries", []):
        test = entry.get("test", "?")
        lines.append(f"### {test}\n")
        if "duration_s" in entry:
            lines.append(f"- Duration: {entry.get('duration_s', 0):.1f}s")
        if "stop_reason" in entry:
            lines.append(f"- Stop reason: `{entry.get('stop_reason', 'N/A')}`")
        if entry.get("error"):
            lines.append(f"- **Error**: {entry['error']}")
        if "success" in entry:
            lines.append(f"- Success: {entry['success']}")
        lines.append("")


def _report_usage(phases: dict, lines: list[str]) -> None:
    usage = phases.get("usage_tracking", {})
    if not usage:
        return
    lines.append("## Phase 8: Usage & Cost Tracking\n")
    for entry in usage.get("entries", []):
        test = entry.get("test", "?")
        lines.append(f"### {test}\n")
        if entry.get("usage"):
            lines.append(f"**PromptResponse.usage**:\n```json\n"
                         f"{json.dumps(entry['usage'], indent=2)}\n```\n")
        if test == "usage_update_events":
            lines.append(f"- UsageUpdate events: {entry.get('count', 0)}")
            for evt in entry.get("events", []):
                lines.append(f"  - t={evt['timestamp']:.2f}s: {json.dumps(evt['data'])[:200]}")
            lines.append("")
        else:
            _report_prompt_summary(entry, lines)


def _report_config_option(phases: dict, lines: list[str]) -> None:
    co = phases.get("config_option", {})
    if not co:
        return
    lines.append("## Phase 9: Config Option Mutation + Plan Mode\n")
    for entry in co.get("entries", []):
        call = entry.get("call", "")
        test = entry.get("test", "")
        if call:
            success = entry.get("success", False)
            lines.append(f"### {call}\n")
            lines.append(f"- Success: {success}")
            if not success:
                err = entry.get("error", entry.get("error_message", ""))
                code = entry.get("error_code", "")
                if code:
                    lines.append(f"- Error: code={code}, {err}")
                elif err:
                    lines.append(f"- Error: {err}")
            updates_after = entry.get("updates_after", [])
            if updates_after:
                lines.append(f"- Updates received after call: {len(updates_after)}")
                for u in updates_after:
                    lines.append(f"  - `{u['type']}`")
            lines.append("")
        elif test == "plan_mode_prompt":
            lines.append("### Plan mode prompt\n")
            lines.append(f"- AgentPlanUpdate events: {entry.get('plan_update_count', 0)}")
            lines.append(f"- CurrentModeUpdate events: {entry.get('mode_update_count', 0)}")
            _report_prompt_summary(entry, lines)


def _report_permission_rejection(phases: dict, lines: list[str]) -> None:
    pr = phases.get("permission_rejection", {})
    if not pr:
        return
    lines.append("## Phase 10: Permission Rejection\n")
    for entry in pr.get("entries", []):
        test = entry.get("test", "?")
        lines.append(f"### {test}\n")
        perm_count = len(entry.get("permissions", []))
        lines.append(f"- Permissions requested: {perm_count}")
        if perm_count > 0:
            for p in entry["permissions"]:
                lines.append(f"  - Tool: {p.get('tool_name', '?')}, "
                             f"Decision: {p.get('decision', '?')}")
        _report_prompt_summary(entry, lines)


def _report_long_task(phases: dict, lines: list[str]) -> None:
    lt = phases.get("long_task", {})
    if not lt:
        return
    lines.append("## Phase 11: Longer-Running Task\n")
    for entry in lt.get("entries", []):
        lines.append(f"### {entry.get('test', '?')}\n")
        ttf = entry.get("time_to_first_update_s")
        if ttf is not None:
            lines.append(f"- Time to first update: {ttf:.2f}s")
        lines.append(f"- Max gap between updates: {entry.get('max_gap_between_updates_s', 0):.2f}s")
        lines.append(f"- Tool call count: {entry.get('tool_call_count', 0)}")
        lines.append(f"- Think/respond/work cycles: {entry.get('think_respond_work_cycles', 0)}")
        _report_prompt_summary(entry, lines)
        timeline = entry.get("timeline", {})
        if timeline:
            _report_timeline(timeline, lines)


def _report_session_load(phases: dict, lines: list[str]) -> None:
    sl = phases.get("session_load", {})
    if not sl:
        return
    lines.append("## Phase 12: Session Load/Resume\n")
    for entry in sl.get("entries", []):
        test = entry.get("test", "?")
        success = entry.get("success", False)
        lines.append(f"### {test}\n")
        lines.append(f"- Success: {success}")
        if not success:
            err = entry.get("error", entry.get("error_message", ""))
            code = entry.get("error_code", "")
            if code:
                lines.append(f"- Error: code={code}, {err}")
            elif err:
                lines.append(f"- Error: {err}")
        elif entry.get("response"):
            lines.append(f"```json\n{json.dumps(entry['response'], indent=2)}\n```")
        lines.append("")


def _report_image_resource(phases: dict, lines: list[str]) -> None:
    ir = phases.get("image_and_resource", {})
    if not ir:
        return
    lines.append("## Phase 13: Image Prompt + Embedded Resource\n")
    for entry in ir.get("entries", []):
        test = entry.get("test", "?")
        lines.append(f"### {test}\n")
        _report_prompt_summary(entry, lines)


def _report_mcp_discovery(phases: dict, lines: list[str]) -> None:
    mcp = phases.get("mcp_discovery", {})
    if not mcp:
        return
    lines.append("## Phase 14: MCP Tool Discovery\n")
    for entry in mcp.get("entries", []):
        test = entry.get("test", "?")
        lines.append(f"### {test}\n")
        if entry.get("error"):
            lines.append(f"- **Error**: {entry['error']}")
        if entry.get("session_id"):
            lines.append(f"- Session ID: `{entry['session_id']}`")
        if "duration_s" in entry:
            _report_prompt_summary(entry, lines)
        elif entry.get("response"):
            lines.append(f"```json\n{json.dumps(entry['response'], indent=2)[:2000]}\n```")
        lines.append("")


def _report_java_ts(phases: dict, lines: list[str]) -> None:
    data = phases.get("java_ts_compile", {})
    if not data:
        return
    lines.append("## Phase 15: Java/TypeScript Compilation\n")
    for entry in data.get("entries", []):
        test = entry.get("test", "?")
        lines.append(f"### {test}\n")
        _report_prompt_summary(entry, lines)


def _report_mcp_http(phases: dict, lines: list[str]) -> None:
    data = phases.get("mcp_http_discovery", {})
    if not data:
        return
    lines.append("## Phase 16: MCP Tool Discovery (HTTP Transport)\n")
    for entry in data.get("entries", []):
        test = entry.get("test", "?")
        lines.append(f"### {test}\n")
        if entry.get("error"):
            lines.append(f"- **Error**: {entry['error']}")
        if entry.get("session_id"):
            lines.append(f"- Session ID: `{entry['session_id']}`")
        if "duration_s" in entry:
            _report_prompt_summary(entry, lines)
        elif entry.get("response"):
            lines.append(
                f"```json\n{json.dumps(entry['response'], indent=2)[:2000]}\n```"
            )
        lines.append("")


def _report_session_recall(phases: dict, lines: list[str]) -> None:
    data = phases.get("session_recall", {})
    if not data:
        return
    lines.append("## Phase 17: load_session Conversation Recall\n")
    for entry in data.get("entries", []):
        test = entry.get("test", "?")
        lines.append(f"### {test}\n")
        if "success" in entry and "duration_s" not in entry:
            lines.append(f"- Success: {entry['success']}")
            if not entry["success"]:
                lines.append(f"- Error: {entry.get('error', 'unknown')}")
            lines.append("")
        else:
            _report_prompt_summary(entry, lines)


def _report_resource_content_block(phases: dict, lines: list[str]) -> None:
    data = phases.get("resource_content_block", {})
    if not data:
        return
    lines.append("## Phase 18: ResourceContentBlock (URI-based)\n")
    for entry in data.get("entries", []):
        test = entry.get("test", "?")
        lines.append(f"### {test}\n")
        if entry.get("uri"):
            lines.append(f"- URI: `{entry['uri']}`")
        if entry.get("error") and "duration_s" not in entry:
            lines.append(f"- **Error**: {entry['error']}")
            lines.append("")
        else:
            _report_prompt_summary(entry, lines)


def _report_agent_mode_switch(phases: dict, lines: list[str]) -> None:
    data = phases.get("agent_mode_switch", {})
    if not data:
        return
    lines.append("## Phase 19: Agent-Initiated Mode Switching\n")
    for entry in data.get("entries", []):
        test = entry.get("test", "?")
        lines.append(f"### {test}\n")
        lines.append(
            f"- CurrentModeUpdate events: {entry.get('mode_update_count', 0)}"
        )
        lines.append(
            f"- AgentPlanUpdate events: {entry.get('plan_update_count', 0)}"
        )
        _report_prompt_summary(entry, lines)


def _report_multi_session(phases: dict, lines: list[str]) -> None:
    data = phases.get("multi_session", {})
    if not data:
        return
    lines.append("## Phase 20: Multi-Session Isolation\n")
    for entry in data.get("entries", []):
        test = entry.get("test", "?")
        lines.append(f"### {test}\n")
        if entry.get("session_id"):
            lines.append(f"- Session ID: `{entry['session_id']}`")
        if entry.get("error") and "duration_s" not in entry:
            lines.append(f"- **Error**: {entry['error']}")
            lines.append("")
        elif "duration_s" in entry:
            _report_prompt_summary(entry, lines)
        elif "success" in entry:
            lines.append(f"- Success: {entry['success']}")
            lines.append("")


def _report_mcp_config(phases: dict, lines: list[str]) -> None:
    """Report Phase 21: MCP via .cursor/mcp.json."""
    data = phases.get("mcp_config", {})
    if not data:
        return
    lines.append("## Phase 21: MCP via .cursor/mcp.json\n")
    for entry in data.get("entries", []):
        test = entry.get("test", "?")
        if test == "mcp_config_written":
            lines.append(f"### {test}\n")
            lines.append(f"- Config path: `{entry.get('path', 'N/A')}`")
            cfg = entry.get("config", {})
            servers = list(cfg.get("mcpServers", {}).keys())
            lines.append(f"- Servers configured: {', '.join(servers)}")
            lines.append("")
        elif test in ("initialize", "new_session"):
            lines.append(f"### {test}\n")
            if entry.get("session_id"):
                lines.append(f"- Session ID: `{entry['session_id']}`")
            if entry.get("response"):
                lines.append(
                    f"- Response: `{json.dumps(entry['response'])[:300]}`"
                )
            lines.append("")
        elif test == "phase21_failed":
            lines.append(f"### {test}\n")
            lines.append(f"- **Error**: {entry.get('error', 'unknown')}")
            lines.append("")
        elif "duration_s" in entry:
            lines.append(f"### {test}\n")
            _report_prompt_summary(entry, lines)


def _report_prompt_summary(entry: dict, lines: list[str]) -> None:
    """Append standard prompt summary lines."""
    lines.append(f"- Duration: {entry.get('duration_s', 0):.1f}s")
    lines.append(f"- Stop reason: `{entry.get('stop_reason', 'N/A')}`")
    lines.append(f"- Updates: {entry.get('update_count', 0)}")
    perm_count = len(entry.get("permissions", []))
    if perm_count:
        lines.append(f"- Permissions: {perm_count}")
    if entry.get("error"):
        lines.append(f"- **Error**: {entry['error']}")
    if entry.get("usage"):
        lines.append(f"- Usage: {json.dumps(entry['usage'])[:200]}")
    lines.append("")


def _report_timeline(analysis: dict, lines: list[str]) -> None:
    """Append timeline analysis tables."""
    lines.append("### Update Type Summary\n")
    lines.append("| Type | Count | First (s) | Last (s) | Duration (s) |")
    lines.append("|------|-------|-----------|----------|--------------|")
    for t, info in analysis.get("update_types", {}).items():
        lines.append(
            f"| `{t}` | {info['count']} | "
            f"{info['first_at']:.2f} | {info['last_at']:.2f} | "
            f"{info['duration_s']:.2f} |"
        )
    lines.append("")

    lines.append("### Phase Timeline\n")
    lines.append("| Phase | Start (s) | End (s) | Duration (s) |")
    lines.append("|-------|-----------|---------|--------------|")
    for p in analysis.get("phases", []):
        lines.append(
            f"| {p['phase']} | {p['start']:.2f} | "
            f"{p['end']:.2f} | {p['duration_s']:.2f} |"
        )
    lines.append("")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def _parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(description="Cursor ACP Inspection Harness")
    parser.add_argument(
        "--phases", nargs="*", type=int, default=None,
        help="Run only these phase numbers (e.g. 8 9 10). Default: all.",
    )
    parser.add_argument(
        "--gaps-only", action="store_true",
        help="Run only the gap-filling phases (8-14).",
    )
    parser.add_argument(
        "--v3-only", action="store_true",
        help="Run only the v3 phases (15-21).",
    )
    parser.add_argument(
        "--output-suffix", default="",
        help="Suffix for output files (e.g. '_v2').",
    )
    return parser.parse_args()


async def main() -> None:
    """Run inspection and write reports."""
    args = _parse_args()

    if args.v3_only:
        phases_to_run = V3_PHASES.copy()
    elif args.gaps_only:
        phases_to_run = GAP_PHASES.copy()
    elif args.phases:
        phases_to_run = set(args.phases)
    else:
        phases_to_run = None

    suffix = args.output_suffix
    logger.info("Starting Cursor ACP inspection (phases=%s, suffix=%r)...",
                phases_to_run or "all", suffix)

    data = await run_inspection(phases_to_run=phases_to_run)
    sanitized = _sanitize(data)

    REPORT_DIR.mkdir(parents=True, exist_ok=True)

    json_path = REPORT_DIR / f"raw_responses{suffix}.json"
    with open(json_path, "w") as f:
        json.dump(sanitized, f, indent=2, default=str)
    logger.info("Wrote %s", json_path)

    report_path = REPORT_DIR / f"report{suffix}.md"
    report_text = _generate_report(sanitized)
    with open(report_path, "w") as f:
        f.write(report_text)
    logger.info("Wrote %s", report_path)

    logger.info("Inspection complete.")


if __name__ == "__main__":
    asyncio.run(main())
