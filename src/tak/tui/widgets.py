"""Custom widgets for the tak TUI.

Provides :class:`AgentTable`, which polls the tak daemon via IPC and
renders the live agent roster in a :class:`~textual.widgets.DataTable`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from rich.text import Text
from textual import work
from textual.widget import Widget
from textual.widgets import DataTable, Label

if TYPE_CHECKING:
    from textual.app import ComposeResult

# Status → Rich style mapping used for coloured DataTable cells.
_STATUS_STYLE: dict[str, str] = {
    "running": "bold green",
    "starting": "yellow",
    "stopping": "yellow",
    "stopped": "dim",
    "error": "bold red",
}


async def _get_agents() -> tuple[list[dict[str, Any]], str | None]:
    """Fetch the agent list from the tak daemon.

    Returns:
        A 2-tuple of ``(agents, error_message)``.  ``agents`` is a list of
        agent dicts from the daemon.  ``error_message`` is ``None`` on success
        or a human-readable string when the daemon is unavailable.
    """
    from tak.ipc.client import DEFAULT_SOCKET_PATH, send_request

    if not DEFAULT_SOCKET_PATH.exists():
        return [], "daemon not running — start iTerm2 with the tak daemon"

    try:
        resp = await send_request("list_agents")
        if resp.success:
            return resp.data or [], None
        return [], resp.error or "unknown daemon error"
    except (ConnectionError, TimeoutError, OSError) as exc:
        return [], str(exc)


class AgentTable(Widget):
    """Live agent roster widget backed by periodic daemon polling.

    The table refreshes every :attr:`POLL_INTERVAL` seconds.  When the daemon
    is not reachable a status line is shown instead of an empty table.
    """

    POLL_INTERVAL: float = 2.0

    DEFAULT_CSS = """
    AgentTable {
        height: 1fr;
        padding: 0 1;
    }

    AgentTable Label {
        padding: 0 1;
        color: $warning;
    }

    AgentTable DataTable {
        height: 1fr;
    }
    """

    def compose(self) -> ComposeResult:
        """Build the widget tree."""
        yield Label("", id="agent-status-label")
        yield DataTable(id="agent-data-table")

    def on_mount(self) -> None:
        """Initialise columns and start the polling interval."""
        table = self.query_one("#agent-data-table", DataTable)
        table.add_columns("Name", "Provider", "Model", "Status", "Tabs")
        self.load_agents()
        self.set_interval(self.POLL_INTERVAL, self.load_agents)

    @work(exclusive=True)
    async def load_agents(self) -> None:
        """Fetch agents from the daemon and refresh the DataTable.

        This method is decorated with ``@work`` so each call runs as a
        Textual worker; the ``exclusive=True`` flag cancels any in-flight
        fetch before starting a new one.
        """
        agents, error = await _get_agents()

        status_label = self.query_one("#agent-status-label", Label)
        table = self.query_one("#agent-data-table", DataTable)

        if error:
            status_label.update(f"[dim]{error}[/dim]")
        else:
            status_label.update("")

        table.clear()

        for agent in agents:
            raw_status: str = agent.get("status", "unknown")
            style = _STATUS_STYLE.get(raw_status, "")
            status_cell = Text(raw_status, style=style)
            tabs = agent.get("tabs") or []
            table.add_row(
                agent.get("name", "?"),
                agent.get("provider", "?"),
                agent.get("model") or "—",
                status_cell,
                ", ".join(tabs) or "—",
            )
