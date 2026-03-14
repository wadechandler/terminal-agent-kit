"""iTerm2 terminal driver.

Implements the BaseDriver interface using the iTerm2 Python API.
Communicates with iTerm2 via websocket using the iterm2 package.
"""

from __future__ import annotations

from typing import Any

from tak.drivers.base import BaseDriver


class ITerm2Driver(BaseDriver):
    """iTerm2 driver using the iterm2 Python API (websocket)."""

    def __init__(self) -> None:
        self._connection: Any = None
        self._app: Any = None

    @property
    def name(self) -> str:
        return "iterm2"

    async def connect(self) -> None:
        import iterm2  # noqa: TCH004
        self._connection = await iterm2.Connection.async_create()
        self._app = await iterm2.async_get_app(self._connection)

    async def disconnect(self) -> None:
        self._connection = None
        self._app = None

    async def list_sessions(self) -> list[dict[str, Any]]:
        if self._app is None:
            raise RuntimeError("Not connected to iTerm2")

        sessions = []
        for window in self._app.windows:
            for tab in window.tabs:
                for session in tab.sessions:
                    sessions.append({
                        "id": session.session_id,
                        "name": session.name,
                        "tab_id": tab.tab_id,
                        "window_id": window.window_id,
                    })
        return sessions

    async def get_active_session(self) -> str | None:
        if self._app is None:
            raise RuntimeError("Not connected to iTerm2")

        session = self._app.current_terminal_window.current_tab.current_session
        return session.session_id if session else None

    async def inject_text(self, session_id: str, text: str) -> None:
        session = await self._get_session(session_id)
        await session.async_inject(text.encode())

    async def set_variable(self, session_id: str, key: str, value: str) -> None:
        session = await self._get_session(session_id)
        await session.async_set_variable(f"user.{key}", value)

    async def get_variable(self, session_id: str, key: str) -> str | None:
        session = await self._get_session(session_id)
        return await session.async_get_variable(f"user.{key}")

    async def get_screen_contents(self, session_id: str) -> str:
        session = await self._get_session(session_id)
        contents = await session.async_get_screen_contents()
        lines = []
        for line_num in range(contents.number_of_lines):
            line = contents.line(line_num)
            lines.append(line.string)
        return "\n".join(lines)

    async def set_session_title(self, session_id: str, title: str) -> None:
        session = await self._get_session(session_id)
        await session.async_set_name(title)

    async def _get_session(self, session_id: str) -> Any:
        if self._app is None:
            raise RuntimeError("Not connected to iTerm2")

        for window in self._app.windows:
            for tab in window.tabs:
                for session in tab.sessions:
                    if session.session_id == session_id:
                        return session

        raise ValueError(f"Session '{session_id}' not found")
