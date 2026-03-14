"""Abstract base for terminal drivers.

Each driver implements terminal-specific operations. The core logic calls
driver methods without knowing which terminal is in use.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


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
        """Set a user-defined variable on a session."""

    @abstractmethod
    async def get_variable(self, session_id: str, key: str) -> str | None:
        """Get a user-defined variable from a session."""

    @abstractmethod
    async def get_screen_contents(self, session_id: str) -> str:
        """Read the visible screen contents of a session."""

    async def set_session_title(self, session_id: str, title: str) -> None:
        """Set the title of a session. Optional -- not all terminals support this."""

    async def create_session(self, **kwargs: Any) -> str:
        """Create a new terminal session. Returns session ID."""
        raise NotImplementedError

    async def register_trigger(self, pattern: str, callback_name: str) -> None:
        """Register a trigger pattern that invokes a callback. Optional."""
        raise NotImplementedError
