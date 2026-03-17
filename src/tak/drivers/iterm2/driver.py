"""iTerm2 terminal driver.

Implements the BaseDriver interface using the iTerm2 Python API.
Communicates with iTerm2 via websocket using the iterm2 package.

Variable keys use the ``tak_*`` convention; this driver prepends ``user.``
as required by iTerm2's user-defined variable scope.
"""

from __future__ import annotations

import os
from typing import Any

from tak.drivers.base import BaseDriver


class ITerm2Driver(BaseDriver):
    """iTerm2 driver using the iterm2 Python API (websocket)."""

    def __init__(self) -> None:
        """Initialize with no connection."""
        self._connection: Any = None
        self._app: Any = None

    @property
    def name(self) -> str:
        """Return driver name."""
        return "iterm2"

    @property
    def connection(self) -> Any:
        """Return the raw iterm2 connection for advanced callers."""
        return self._connection

    async def connect(self) -> None:
        """Establish websocket connection to iTerm2."""
        import iterm2

        self._connection = await iterm2.Connection.async_create()
        self._app = await iterm2.async_get_app(self._connection)

    async def disconnect(self) -> None:
        """Tear down iTerm2 connection."""
        self._connection = None
        self._app = None

    async def list_sessions(self) -> list[dict[str, Any]]:
        """List all sessions across windows and tabs."""
        self._ensure_connected()

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
        """Get the session ID of the focused pane."""
        self._ensure_connected()

        window = self._app.current_terminal_window
        if window is None:
            return None
        session = window.current_tab.current_session
        return session.session_id if session else None

    async def inject_text(self, session_id: str, text: str) -> None:
        """Inject text into a session as simulated terminal output."""
        session = await self._get_session(session_id)
        await session.async_inject(text.encode())

    async def set_variable(self, session_id: str, key: str, value: str) -> None:
        """Set a user-defined variable (``user.<key>``) on a session."""
        session = await self._get_session(session_id)
        await session.async_set_variable(f"user.{key}", value)

    async def get_variable(self, session_id: str, key: str) -> str | None:
        """Get a user-defined variable (``user.<key>``) from a session."""
        session = await self._get_session(session_id)
        return await session.async_get_variable(f"user.{key}")

    async def get_screen_contents(self, session_id: str) -> str:
        """Read all visible lines from a session's screen buffer."""
        session = await self._get_session(session_id)
        contents = await session.async_get_screen_contents()
        lines = []
        for line_num in range(contents.number_of_lines):
            line = contents.line(line_num)
            lines.append(line.string)
        return "\n".join(lines)

    async def set_session_title(self, session_id: str, title: str) -> None:
        """Set the display title of a session."""
        session = await self._get_session(session_id)
        await session.async_set_name(title)

    async def activate_session(
        self, session_id: str, *, focus_window: bool = True
    ) -> None:
        """Bring a session's tab and window to the foreground."""
        session = await self._get_session(session_id)
        await session.async_activate(
            select_tab=True, order_window_front=focus_window
        )

    async def split_pane(
        self, session_id: str, *, vertical: bool = True
    ) -> str:
        """Split a session into two panes.

        Returns:
            The session ID of the newly created pane.
        """
        session = await self._get_session(session_id)
        new_session = await session.async_split_pane(vertical=vertical)
        return new_session.session_id

    async def send_text(self, session_id: str, text: str) -> None:
        """Send text to a session as simulated keystrokes."""
        session = await self._get_session(session_id)
        await session.async_send_text(text)

    @staticmethod
    def detect_session_id() -> str | None:
        """Detect the iTerm2 session ID from ``$ITERM_SESSION_ID``."""
        return os.environ.get("ITERM_SESSION_ID")

    def _ensure_connected(self) -> None:
        """Raise if not connected to iTerm2."""
        if self._app is None:
            raise RuntimeError("Not connected to iTerm2")

    async def _get_session(self, session_id: str) -> Any:
        """Look up a session by ID across all windows/tabs."""
        self._ensure_connected()

        found = self._app.get_session_by_id(session_id)
        if found is not None:
            return found

        raise ValueError(f"Session '{session_id}' not found")
