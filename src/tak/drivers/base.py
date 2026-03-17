"""Abstract base for terminal drivers.

Each driver implements terminal-specific operations. The core logic calls
driver methods without knowing which terminal is in use.

Variable keys use the ``tak_*`` prefix convention (e.g. ``tak_agent_id``).
The driver prepends the terminal-specific scope (``user.`` for iTerm2).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

TAK_VAR_AGENT_ID = "tak_agent_id"
TAK_VAR_AGENT_STATUS = "tak_agent_status"
TAK_VAR_AGENT_PROVIDER = "tak_agent_provider"
TAK_VAR_AGENT_MODEL = "tak_agent_model"


class BaseDriver(ABC):
    """Interface that all terminal drivers must implement."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Driver name (e.g., 'iterm2', 'kitty', 'tmux')."""

    @abstractmethod
    async def connect(self) -> None:
        """Establish connection to the terminal application."""

    @abstractmethod
    async def disconnect(self) -> None:
        """Clean up connection to the terminal application."""

    @abstractmethod
    async def list_sessions(self) -> list[dict[str, Any]]:
        """List all terminal sessions (tabs/panes)."""

    @abstractmethod
    async def get_active_session(self) -> str | None:
        """Get the ID of the currently active session."""

    @abstractmethod
    async def inject_text(self, session_id: str, text: str) -> None:
        """Inject text into a terminal session (as if typed or output)."""

    @abstractmethod
    async def set_variable(self, session_id: str, key: str, value: str) -> None:
        """Set a user-defined variable on a session.

        Args:
            session_id: Target session identifier.
            key: Variable name without terminal scope prefix.
                Use ``tak_*`` keys (see module-level constants).
            value: Value to store.
        """

    @abstractmethod
    async def get_variable(self, session_id: str, key: str) -> str | None:
        """Get a user-defined variable from a session.

        Args:
            session_id: Target session identifier.
            key: Variable name without terminal scope prefix.

        Returns:
            The variable value, or ``None`` if not set.
        """

    @abstractmethod
    async def get_screen_contents(self, session_id: str) -> str:
        """Read the visible screen contents of a session."""

    async def set_session_title(self, session_id: str, title: str) -> None:
        """Set the title of a session. Optional -- not all terminals support this."""
        raise NotImplementedError

    async def activate_session(
        self, session_id: str, *, focus_window: bool = True
    ) -> None:
        """Bring a session's tab/window to the foreground.

        Args:
            session_id: Target session identifier.
            focus_window: Whether to also bring the window to front.
        """
        raise NotImplementedError

    async def split_pane(
        self, session_id: str, *, vertical: bool = True
    ) -> str:
        """Create a split pane from an existing session.

        Args:
            session_id: The session to split.
            vertical: If True, split vertically (side-by-side).

        Returns:
            The session ID of the newly created pane.
        """
        raise NotImplementedError

    async def create_session(self, **kwargs: Any) -> str:
        """Create a new terminal session. Returns session ID."""
        raise NotImplementedError

    async def register_trigger(self, pattern: str, callback_name: str) -> None:
        """Register a trigger pattern that invokes a callback. Optional."""
        raise NotImplementedError

    @staticmethod
    def detect_session_id() -> str | None:
        """Detect the terminal session ID from the environment.

        Each driver overrides this to check its specific env var
        (e.g. ``$ITERM_SESSION_ID`` for iTerm2). Returns ``None``
        if not running inside that terminal.
        """
        return None
