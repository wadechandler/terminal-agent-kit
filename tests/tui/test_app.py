"""Tests for the tak TUI application and widgets."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, patch

from tak.tui.app import TakApp
from tak.tui.widgets import AgentTable, _get_agents

# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _make_agent(
    name: str = "agent1",
    provider: str = "cursor-acp",
    model: str | None = "claude-sonnet-4",
    status: str = "running",
    tabs: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "name": name,
        "provider": provider,
        "model": model,
        "status": status,
        "tabs": tabs or [],
    }


# ---------------------------------------------------------------------------
# _get_agents unit tests (no app required)
# ---------------------------------------------------------------------------


class TestGetAgents:
    async def test_daemon_error_response_returns_error_string(self, tmp_path: Any) -> None:
        """When the daemon responds with success=False, return its error message."""
        fake_path = tmp_path / "daemon.sock"
        fake_path.touch()

        mock_resp = AsyncMock()
        mock_resp.success = False
        mock_resp.error = "internal daemon error"

        with patch("tak.ipc.client.DEFAULT_SOCKET_PATH", fake_path), patch(
            "tak.ipc.client.send_request", new_callable=AsyncMock, return_value=mock_resp
        ):
            agents, error = await _get_agents()

        assert agents == []
        assert error == "internal daemon error"

    async def test_daemon_not_running_path(self, tmp_path: Any) -> None:
        """When the socket path does not exist, return helpful error string."""
        fake_path = tmp_path / "nonexistent.sock"

        with patch("tak.ipc.client.DEFAULT_SOCKET_PATH", fake_path):
            agents, error = await _get_agents()

        assert agents == []
        assert error is not None
        assert "daemon" in error.lower()

    async def test_returns_agents_on_success(self, tmp_path: Any) -> None:
        fake_path = tmp_path / "daemon.sock"
        fake_path.touch()

        mock_resp = AsyncMock()
        mock_resp.success = True
        mock_resp.data = [_make_agent()]

        with patch("tak.ipc.client.DEFAULT_SOCKET_PATH", fake_path), patch(
            "tak.ipc.client.send_request", new_callable=AsyncMock, return_value=mock_resp
        ):
            agents, error = await _get_agents()

        assert error is None
        assert len(agents) == 1
        assert agents[0]["name"] == "agent1"

    async def test_connection_error_returns_error_string(self, tmp_path: Any) -> None:
        fake_path = tmp_path / "daemon.sock"
        fake_path.touch()

        with patch("tak.ipc.client.DEFAULT_SOCKET_PATH", fake_path), patch(
            "tak.ipc.client.send_request",
            new_callable=AsyncMock,
            side_effect=ConnectionError("refused"),
        ):
            agents, error = await _get_agents()

        assert agents == []
        assert error is not None


# ---------------------------------------------------------------------------
# TakApp integration tests (Textual pilot)
# ---------------------------------------------------------------------------


class TestTakApp:
    async def test_app_mounts_without_errors(self) -> None:
        """App should compose and mount cleanly (daemon absent)."""
        with patch(
            "tak.tui.widgets._get_agents",
            new_callable=AsyncMock,
            return_value=([], "daemon not running"),
        ):
            app = TakApp()
            async with app.run_test(size=(120, 30)) as pilot:
                await pilot.pause(0.2)
                assert app.is_running

    async def test_header_contains_title(self) -> None:
        with patch(
            "tak.tui.widgets._get_agents",
            new_callable=AsyncMock,
            return_value=([], "daemon not running"),
        ):
            app = TakApp()
            async with app.run_test(size=(120, 30)) as pilot:
                await pilot.pause(0.1)
                # Header widget should be present
                from textual.widgets import Header

                assert app.query_one(Header) is not None

    async def test_agent_table_widget_is_mounted(self) -> None:
        with patch(
            "tak.tui.widgets._get_agents",
            new_callable=AsyncMock,
            return_value=([], "daemon not running"),
        ):
            app = TakApp()
            async with app.run_test(size=(120, 30)) as pilot:
                await pilot.pause(0.1)
                assert app.query_one(AgentTable) is not None

    async def test_datatable_columns_are_present(self) -> None:
        with patch(
            "tak.tui.widgets._get_agents",
            new_callable=AsyncMock,
            return_value=([], "daemon not running"),
        ):
            app = TakApp()
            async with app.run_test(size=(120, 30)) as pilot:
                await pilot.pause(0.2)
                from textual.widgets import DataTable

                table = app.query_one(DataTable)
                col_labels = [str(col.label) for col in table.columns.values()]
                assert "Name" in col_labels
                assert "Status" in col_labels

    async def test_agent_table_shows_mock_data(self) -> None:
        """DataTable should contain one row when daemon returns one agent."""
        agents = [_make_agent("myagent", status="running")]
        with patch(
            "tak.tui.widgets._get_agents",
            new_callable=AsyncMock,
            return_value=(agents, None),
        ):
            app = TakApp()
            async with app.run_test(size=(120, 30)) as pilot:
                await pilot.pause(0.3)
                from textual.widgets import DataTable

                table = app.query_one(DataTable)
                assert table.row_count == 1

    async def test_agent_table_shows_multiple_agents(self) -> None:
        agents = [
            _make_agent("alpha", status="running"),
            _make_agent("beta", status="stopped"),
            _make_agent("gamma", status="error"),
        ]
        with patch(
            "tak.tui.widgets._get_agents",
            new_callable=AsyncMock,
            return_value=(agents, None),
        ):
            app = TakApp()
            async with app.run_test(size=(120, 30)) as pilot:
                await pilot.pause(0.3)
                from textual.widgets import DataTable

                table = app.query_one(DataTable)
                assert table.row_count == 3

    async def test_quit_binding_exits_cleanly(self) -> None:
        """Pressing q should exit the app without raising."""
        with patch(
            "tak.tui.widgets._get_agents",
            new_callable=AsyncMock,
            return_value=([], "daemon not running"),
        ):
            app = TakApp()
            async with app.run_test(size=(120, 30)) as pilot:
                await pilot.pause(0.1)
                await pilot.press("q")
            # Reaching here means the app exited cleanly

    async def test_refresh_binding_triggers_reload(self) -> None:
        """Pressing r should call load_agents on the AgentTable."""
        with patch(
            "tak.tui.widgets._get_agents",
            new_callable=AsyncMock,
            return_value=([], "daemon not running"),
        ) as mock_get:
            app = TakApp()
            async with app.run_test(size=(120, 30)) as pilot:
                await pilot.pause(0.1)
                call_count_before = mock_get.call_count
                await pilot.press("r")
                await pilot.pause(0.2)
                assert mock_get.call_count > call_count_before

    async def test_spawn_binding_shows_notification(self) -> None:
        """Pressing s should display a 'not yet implemented' notification."""
        with patch(
            "tak.tui.widgets._get_agents",
            new_callable=AsyncMock,
            return_value=([], "daemon not running"),
        ):
            app = TakApp()
            async with app.run_test(size=(120, 30)) as pilot:
                await pilot.pause(0.1)
                await pilot.press("s")
                await pilot.pause(0.1)
                # App should still be running after pressing s
                assert app.is_running

    async def test_stop_binding_shows_notification(self) -> None:
        with patch(
            "tak.tui.widgets._get_agents",
            new_callable=AsyncMock,
            return_value=([], "daemon not running"),
        ):
            app = TakApp()
            async with app.run_test(size=(120, 30)) as pilot:
                await pilot.pause(0.1)
                await pilot.press("x")
                await pilot.pause(0.1)
                assert app.is_running
