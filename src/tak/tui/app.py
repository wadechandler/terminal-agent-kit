"""Textual application for the tak agent management dashboard.

Launch with ``tak menu`` or call :func:`run_app` directly.
"""

from __future__ import annotations

from typing import ClassVar

from textual.app import App, ComposeResult
from textual.binding import Binding, BindingType
from textual.widgets import Footer, Header

from tak.tui.widgets import AgentTable


class TakApp(App[None]):
    """Agent management dashboard.

    Displays a live table of all managed agents with keyboard shortcuts for
    common actions.  Data is fetched from the running tak daemon via IPC;
    when the daemon is not reachable the table shows a status message.
    """

    CSS_PATH = "tak.tcss"

    TITLE = "tak — Agent Dashboard"
    SUB_TITLE = "q quit · s spawn · x stop · g go to tab · r refresh"

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("q", "quit", "Quit", priority=True),
        Binding("s", "spawn", "Spawn"),
        Binding("x", "stop_agent", "Stop"),
        Binding("g", "switch_tab", "Go to tab"),
        Binding("r", "refresh", "Refresh"),
    ]

    def compose(self) -> ComposeResult:
        """Compose the app layout."""
        yield Header()
        yield AgentTable()
        yield Footer()

    def action_spawn(self) -> None:
        """Prompt the user to spawn a new agent (not yet implemented)."""
        self.notify("spawn: not yet implemented — use `tak spawn --name <name>`")

    def action_stop_agent(self) -> None:
        """Stop the selected agent (not yet implemented)."""
        self.notify("stop: not yet implemented — use `tak stop <name>`")

    def action_switch_tab(self) -> None:
        """Switch to the selected agent's terminal tab (requires daemon)."""
        self.notify("switch: not yet implemented — use `tak switch <name>`")

    def action_refresh(self) -> None:
        """Manually trigger a daemon poll and table refresh."""
        self.query_one(AgentTable).load_agents()


def run_app() -> None:
    """Create and run the :class:`TakApp`.

    This is the entry point used by ``tak menu``.
    """
    TakApp().run()
