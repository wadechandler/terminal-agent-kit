"""Shared test fixtures for Terminal Agent Kit."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any

import pytest

from tak.core.agent_bus import AgentBus
from tak.core.agent_manager import AgentHandle, AgentManager
from tak.core.session_registry import SessionRegistry
from tak.providers.base import BaseProvider

if TYPE_CHECKING:
    from pathlib import Path


class MockProcess:
    """Simulates an asyncio subprocess for testing."""

    def __init__(self) -> None:
        self.returncode: int | None = None
        self.stdin = MockStream()
        self.stdout = MockStream()
        self.stderr = MockStream()
        self._terminated = False

    def terminate(self) -> None:
        self._terminated = True
        self.returncode = -15

    def kill(self) -> None:
        self._terminated = True
        self.returncode = -9

    async def wait(self) -> int:
        await asyncio.sleep(0)
        self.returncode = self.returncode or 0
        return self.returncode


class MockStream:
    """Simulates async stdin/stdout for testing."""

    def __init__(self) -> None:
        self._buffer: list[bytes] = []
        self._read_buffer: bytes = b""

    def write(self, data: bytes) -> None:
        self._buffer.append(data)

    async def drain(self) -> None:
        """Yield to the loop; the mock has no OS buffer to flush."""
        await asyncio.sleep(0)

    def feed(self, data: bytes) -> None:
        """Feed data to be read by readline."""
        self._read_buffer += data

    async def readline(self) -> bytes:
        await asyncio.sleep(0)
        if b"\n" in self._read_buffer:
            line, self._read_buffer = self._read_buffer.split(b"\n", 1)
            return line + b"\n"
        remaining = self._read_buffer
        self._read_buffer = b""
        return remaining


class MockProvider(BaseProvider):
    """Test provider that records calls and returns canned responses."""

    def __init__(self, canned_response: str = "mock response") -> None:
        self._canned_response = canned_response
        self.spawn_calls: list[dict[str, Any]] = []
        self.send_calls: list[dict[str, Any]] = []
        self.stop_calls: list[str] = []

    @property
    def name(self) -> str:
        return "mock"

    @property
    def protocol(self) -> str:
        return "mock"

    async def spawn(
        self,
        agent_name: str,
        project_path: Path | None = None,
        model: str | None = None,
    ) -> asyncio.subprocess.Process:
        await asyncio.sleep(0)
        self.spawn_calls.append({
            "name": agent_name,
            "project": project_path,
            "model": model,
        })
        return MockProcess()  # type: ignore[return-value]

    async def send(
        self,
        handle: AgentHandle,
        message: str,
        *,
        cwd: str | None = None,
        mode: str | None = None,
    ) -> str:
        await asyncio.sleep(0)
        self.send_calls.append({
            "agent": handle.name,
            "message": message,
            "cwd": cwd,
            "mode": mode,
        })
        return self._canned_response

    async def stop(self, handle: AgentHandle) -> None:
        await asyncio.sleep(0)
        self.stop_calls.append(handle.name)
        if handle.process:
            handle.process.terminate()  # type: ignore[union-attr]


class MockDriver:
    """Test driver that simulates terminal sessions in memory."""

    def __init__(self) -> None:
        self.sessions: dict[str, dict[str, Any]] = {}
        self.injected_text: list[dict[str, str]] = []

    def add_session(self, session_id: str, name: str = "bash") -> None:
        self.sessions[session_id] = {
            "id": session_id,
            "name": name,
            "variables": {},
            "screen": "",
        }

    async def list_sessions(self) -> list[dict[str, Any]]:
        await asyncio.sleep(0)
        return list(self.sessions.values())

    async def get_active_session(self) -> str | None:
        await asyncio.sleep(0)
        if self.sessions:
            return next(iter(self.sessions))
        return None

    async def inject_text(self, session_id: str, text: str) -> None:
        await asyncio.sleep(0)
        self.injected_text.append({"session_id": session_id, "text": text})

    async def set_variable(self, session_id: str, key: str, value: str) -> None:
        await asyncio.sleep(0)
        if session_id in self.sessions:
            self.sessions[session_id]["variables"][key] = value

    async def get_variable(self, session_id: str, key: str) -> str | None:
        await asyncio.sleep(0)
        if session_id in self.sessions:
            return self.sessions[session_id]["variables"].get(key)
        return None


@pytest.fixture
def mock_provider() -> MockProvider:
    return MockProvider()


@pytest.fixture
def mock_driver() -> MockDriver:
    driver = MockDriver()
    driver.add_session("sess-1", "bash")
    driver.add_session("sess-2", "bash")
    return driver


@pytest.fixture
def agent_manager(mock_provider: MockProvider) -> AgentManager:
    manager = AgentManager()
    manager.register_provider("mock", mock_provider)
    return manager


@pytest.fixture
def session_registry() -> SessionRegistry:
    return SessionRegistry()


@pytest.fixture
def agent_bus(
    agent_manager: AgentManager,
    session_registry: SessionRegistry,
    mock_provider: MockProvider,
) -> AgentBus:
    return AgentBus(
        agent_manager=agent_manager,
        session_registry=session_registry,
        providers={"mock": mock_provider},
    )


@pytest.fixture
def tmp_state_dir(tmp_path: Path) -> Path:
    state_dir = tmp_path / ".tak"
    state_dir.mkdir()
    return state_dir
