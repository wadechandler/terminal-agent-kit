"""Tests for the tak CLI commands.

All daemon-dependent commands are tested with ``_daemon_available`` mocked
to ``False`` (no-daemon fallback) and ``True`` + ``_run_async`` mocked
(daemon-available path) so tests never depend on a running daemon.
"""

from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

from click.testing import CliRunner

from tak.cli.main import cli


def _invoke_no_daemon(args: list[str]) -> Any:
    """Invoke a CLI command with the daemon unavailable."""
    with patch("tak.cli.main._daemon_available", return_value=False):
        return CliRunner().invoke(cli, args)


def _invoke_with_daemon(args: list[str], *, ipc_response: MagicMock) -> Any:
    """Invoke a CLI command with a mocked daemon IPC response."""
    with (
        patch("tak.cli.main._daemon_available", return_value=True),
        patch("tak.cli.main._run_async", return_value=ipc_response),
    ):
        return CliRunner().invoke(cli, args)


class TestCLIBasics:
    def test_version_flag(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["--version"])
        assert result.exit_code == 0
        assert "terminal-agent-kit" in result.output or "version" in result.output.lower()

    def test_help_flag(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
        assert "Terminal Agent Kit" in result.output


class TestSpawnCommand:
    def test_spawn_requires_name(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["spawn"])
        assert result.exit_code != 0

    def test_spawn_no_daemon_prints_info(self) -> None:
        result = _invoke_no_daemon(["spawn", "--name", "test-agent"])
        assert result.exit_code == 0
        assert "test-agent" in result.output
        assert "daemon not running" in result.output

    def test_spawn_no_daemon_with_model(self) -> None:
        result = _invoke_no_daemon(
            ["spawn", "--name", "test-agent", "--model", "claude-sonnet-4"]
        )
        assert result.exit_code == 0
        assert "claude-sonnet-4" in result.output

    def test_spawn_with_daemon_success(self) -> None:
        resp = MagicMock(
            success=True, data={"name": "test-agent", "status": "running"}
        )
        result = _invoke_with_daemon(
            ["spawn", "--name", "test-agent"], ipc_response=resp
        )
        assert result.exit_code == 0
        assert "spawned" in result.output

    def test_spawn_with_daemon_error(self) -> None:
        resp = MagicMock(success=False, error="spawn failed")
        result = _invoke_with_daemon(
            ["spawn", "--name", "test-agent"], ipc_response=resp
        )
        assert result.exit_code != 0


class TestStatusCommand:
    def test_status_no_daemon(self) -> None:
        result = _invoke_no_daemon(["status"])
        assert result.exit_code == 0
        assert "daemon not running" in result.output

    def test_agents_alias_no_daemon(self) -> None:
        result = _invoke_no_daemon(["agents"])
        assert result.exit_code == 0


class TestStopCommand:
    def test_stop_no_daemon(self) -> None:
        result = _invoke_no_daemon(["stop", "my-agent"])
        assert result.exit_code == 0
        assert "my-agent" in result.output

    def test_stop_with_daemon_success(self) -> None:
        resp = MagicMock(success=True)
        result = _invoke_with_daemon(
            ["stop", "my-agent"], ipc_response=resp
        )
        assert result.exit_code == 0
        assert "stopped" in result.output


class TestAskCommand:
    def test_ask_requires_query(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["ask"])
        assert result.exit_code != 0

    def test_ask_no_daemon(self) -> None:
        result = _invoke_no_daemon(["ask", "what", "is", "python"])
        assert result.exit_code == 0
        assert "what is python" in result.output
        assert "daemon not running" in result.output

    def test_ask_with_daemon_success(self) -> None:
        resp = MagicMock(
            success=True, data={"agent": "my-agent", "response": "42"}
        )
        with patch("tak.cli.main._detect_session_id", return_value=None):
            result = _invoke_with_daemon(
                ["ask", "meaning", "of", "life"], ipc_response=resp
            )
        assert result.exit_code == 0
        assert "42" in result.output

    def test_ask_with_session_id_resolves_agent(self) -> None:
        resp = MagicMock(
            success=True, data={"agent": "tab-agent", "response": "hello"}
        )
        with (
            patch("tak.cli.main._daemon_available", return_value=True),
            patch("tak.cli.main._run_async", return_value=resp),
            patch("tak.cli.main._detect_session_id", return_value="sess-abc"),
        ):
            result = CliRunner().invoke(cli, ["ask", "hi"])
        assert result.exit_code == 0
        assert "hello" in result.output

    def test_prompt_ipc_includes_cwd_and_mode(self) -> None:
        resp = MagicMock(success=True, data={"agent": "a", "response": "ok"})
        mock_send = AsyncMock(return_value=resp)
        with (
            patch("tak.cli.main._daemon_available", return_value=True),
            patch("tak.ipc.client.send_request", mock_send),
            patch("tak.cli.main._run_async", side_effect=lambda c: asyncio.run(c)),
            patch("tak.cli.main._detect_session_id", return_value=None),
            patch("tak.cli.main.os.getcwd", return_value="/from/cli"),
        ):
            result = CliRunner().invoke(cli, ["prompt", "--mode", "plan", "hello"])
        assert result.exit_code == 0
        mock_send.assert_called_once()
        method, params = mock_send.call_args[0]
        assert method == "prompt"
        assert params["cwd"] == "/from/cli"
        assert params["mode"] == "plan"

    def test_session_end_with_daemon(self) -> None:
        resp = MagicMock(
            success=True, data={"agent": "my-agent", "status": "session_ended"}
        )
        mock_send = AsyncMock(return_value=resp)
        with (
            patch("tak.cli.main._daemon_available", return_value=True),
            patch("tak.ipc.client.send_request", mock_send),
            patch("tak.cli.main._run_async", side_effect=lambda c: asyncio.run(c)),
            patch("tak.cli.main._detect_session_id", return_value=None),
        ):
            result = CliRunner().invoke(cli, ["session", "end", "my-agent"])
        assert result.exit_code == 0
        assert "Session ended" in result.output
        mock_send.assert_called_once()
        assert mock_send.call_args[0][0] == "session_end"
        assert mock_send.call_args[0][1]["agent"] == "my-agent"


class TestAssociateCommand:
    def test_associate_no_session_id_no_env_fails(self) -> None:
        with (
            patch("tak.cli.main._daemon_available", return_value=True),
            patch("tak.cli.main._detect_session_id", return_value=None),
        ):
            result = CliRunner().invoke(cli, ["associate", "my-agent"])
        assert result.exit_code != 0
        combined = result.output + str(result.exception or "")
        assert "session ID" in result.output or "session ID" in combined

    def test_associate_no_daemon_fails(self) -> None:
        with patch("tak.cli.main._detect_session_id", return_value="sess-123"):
            result = _invoke_no_daemon(["associate", "my-agent"])
        assert result.exit_code != 0

    def test_associate_with_daemon_success(self) -> None:
        resp = MagicMock(
            success=True, data={"agent": "my-agent", "session_id": "sess-123"}
        )
        with (
            patch("tak.cli.main._daemon_available", return_value=True),
            patch("tak.cli.main._run_async", return_value=resp),
            patch("tak.cli.main._detect_session_id", return_value="sess-123"),
        ):
            result = CliRunner().invoke(cli, ["associate", "my-agent"])
        assert result.exit_code == 0
        assert "Associated" in result.output

    def test_associate_with_explicit_session_id(self) -> None:
        resp = MagicMock(
            success=True, data={"agent": "my-agent", "session_id": "explicit-id"}
        )
        with (
            patch("tak.cli.main._daemon_available", return_value=True),
            patch("tak.cli.main._run_async", return_value=resp),
        ):
            result = CliRunner().invoke(
                cli, ["associate", "my-agent", "--session-id", "explicit-id"]
            )
        assert result.exit_code == 0


class TestPermissionsCommand:
    def test_permissions_no_daemon_fails(self) -> None:
        result = _invoke_no_daemon(["permissions", "my-agent", "reject"])
        assert result.exit_code != 0

    def test_permissions_with_daemon_success(self) -> None:
        resp = MagicMock(
            success=True, data={"agent": "my-agent", "policy": "auto-allow"}
        )
        result = _invoke_with_daemon(
            ["permissions", "my-agent", "auto-allow"], ipc_response=resp
        )
        assert result.exit_code == 0
        assert "auto-allow" in result.output

    def test_permissions_yolo_prints_warning(self) -> None:
        resp = MagicMock(
            success=True, data={"agent": "my-agent", "policy": "yolo"}
        )
        result = _invoke_with_daemon(
            ["permissions", "my-agent", "yolo"], ipc_response=resp
        )
        assert result.exit_code == 0
        assert "irrevocable" in result.output

    def test_permissions_invalid_choice_fails(self) -> None:
        result = CliRunner().invoke(cli, ["permissions", "my-agent", "invalid"])
        assert result.exit_code != 0


class TestSpawnAutoAssociation:
    def test_spawn_no_associate_flag(self) -> None:
        resp = MagicMock(
            success=True, data={"name": "test-agent", "status": "running"}
        )
        with (
            patch("tak.cli.main._daemon_available", return_value=True),
            patch("tak.cli.main._run_async", return_value=resp),
        ):
            result = CliRunner().invoke(
                cli, ["spawn", "--name", "test-agent", "--no-associate"]
            )
        assert result.exit_code == 0
        assert "spawned" in result.output

    def test_spawn_with_permissions_yolo_warns(self) -> None:
        resp = MagicMock(
            success=True, data={"name": "test-agent", "status": "running"}
        )
        with (
            patch("tak.cli.main._daemon_available", return_value=True),
            patch("tak.cli.main._run_async", return_value=resp),
            patch("tak.cli.main._detect_session_id", return_value=None),
        ):
            result = CliRunner().invoke(
                cli,
                ["spawn", "--name", "test-agent", "--permissions", "yolo"],
            )
        assert result.exit_code == 0
        assert "irrevocable" in result.output

    def test_spawn_auto_detects_session(self) -> None:
        resp = MagicMock(
            success=True, data={"name": "test-agent", "status": "running"}
        )
        with (
            patch("tak.cli.main._daemon_available", return_value=True),
            patch("tak.cli.main._run_async", return_value=resp),
            patch("tak.cli.main._detect_session_id", return_value="sess-auto"),
        ):
            result = CliRunner().invoke(
                cli, ["spawn", "--name", "test-agent"]
            )
        assert result.exit_code == 0

    def test_spawn_no_session_warns(self) -> None:
        resp = MagicMock(
            success=True, data={"name": "test-agent", "status": "running"}
        )
        with (
            patch("tak.cli.main._daemon_available", return_value=True),
            patch("tak.cli.main._run_async", return_value=resp),
            patch("tak.cli.main._detect_session_id", return_value=None),
        ):
            result = CliRunner().invoke(
                cli, ["spawn", "--name", "test-agent"]
            )
        assert result.exit_code == 0
        assert "No terminal session" in result.output


class TestSwitchCommand:
    def test_switch_no_daemon(self) -> None:
        result = _invoke_no_daemon(["switch", "my-agent"])
        assert result.exit_code == 0
        assert "my-agent" in result.output


class TestRenameCommand:
    def test_rename_no_daemon(self) -> None:
        result = _invoke_no_daemon(["rename", "old-name", "new-name"])
        assert result.exit_code == 0
        assert "daemon not running" in result.output

    def test_rename_with_daemon_success(self) -> None:
        resp = MagicMock(
            success=True, data={"old_name": "old", "new_name": "new"}
        )
        result = _invoke_with_daemon(
            ["rename", "old", "new"], ipc_response=resp
        )
        assert result.exit_code == 0


class TestMenuCommand:
    @patch("tak.tui.app.run_app")
    def test_menu_runs(self, mock_run: Any) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["menu"])
        assert result.exit_code == 0
        mock_run.assert_called_once()


class TestScaffoldCommands:
    def test_scaffold_agents(self) -> None:
        runner = CliRunner()
        with runner.isolated_filesystem():
            result = runner.invoke(cli, ["scaffold", "agents", "--name", "testproj"])
        assert result.exit_code == 0, result.output

    def test_scaffold_rules(self) -> None:
        runner = CliRunner()
        with runner.isolated_filesystem():
            result = runner.invoke(cli, ["scaffold", "rules"])
        assert result.exit_code == 0, result.output

    def test_scaffold_skills(self) -> None:
        runner = CliRunner()
        with runner.isolated_filesystem():
            result = runner.invoke(
                cli,
                ["scaffold", "skills", "--name", "My Skill", "--desc", "Does something."],
            )
        assert result.exit_code == 0, result.output

    def test_scaffold_agents_force_flag(self) -> None:
        runner = CliRunner()
        with runner.isolated_filesystem():
            runner.invoke(cli, ["scaffold", "agents", "--name", "proj"])
            result = runner.invoke(cli, ["scaffold", "agents", "--name", "proj", "--force"])
        assert result.exit_code == 0, result.output

    def test_scaffold_agents_file_exists_without_force(self) -> None:
        runner = CliRunner()
        with runner.isolated_filesystem():
            runner.invoke(cli, ["scaffold", "agents", "--name", "proj"])
            result = runner.invoke(cli, ["scaffold", "agents", "--name", "proj"])
        assert result.exit_code != 0


class TestNewProjectCommand:
    def test_new_project_quick_creates_directory(self) -> None:
        runner = CliRunner()
        with runner.isolated_filesystem():
            result = runner.invoke(cli, ["new", "project", "--quick", "--no-git", "myapp"])
        assert result.exit_code == 0, result.output
        assert "myapp" in result.output

    def test_new_project_quick_creates_agents_md(self) -> None:
        import os

        runner = CliRunner()
        with runner.isolated_filesystem() as tmpdir:
            runner.invoke(cli, ["new", "project", "--quick", "--no-git", "myapp"])
            assert os.path.exists(os.path.join(tmpdir, "myapp", "AGENTS.md"))

    def test_new_project_quick_creates_readme(self) -> None:
        import os

        runner = CliRunner()
        with runner.isolated_filesystem() as tmpdir:
            runner.invoke(cli, ["new", "project", "--quick", "--no-git", "myapp"])
            assert os.path.exists(os.path.join(tmpdir, "myapp", "README.md"))

    def test_new_project_quick_creates_cursor_rules(self) -> None:
        import os

        runner = CliRunner()
        with runner.isolated_filesystem() as tmpdir:
            runner.invoke(cli, ["new", "project", "--quick", "--no-git", "myapp"])
            assert os.path.isdir(os.path.join(tmpdir, "myapp", ".cursor", "rules"))

    def test_new_project_language_flag(self) -> None:
        runner = CliRunner()
        with runner.isolated_filesystem():
            result = runner.invoke(
                cli,
                ["new", "project", "--quick", "--no-git", "--language", "Python", "pyproj"],
            )
        assert result.exit_code == 0, result.output

    def test_new_project_desc_flag(self) -> None:
        import os

        runner = CliRunner()
        with runner.isolated_filesystem() as tmpdir:
            runner.invoke(
                cli,
                ["new", "project", "--quick", "--no-git", "--desc", "My great app.", "myapp"],
            )
            with open(os.path.join(tmpdir, "myapp", "README.md")) as f:
                readme = f.read()
            assert "My great app." in readme

    def test_new_project_language_override_in_agents_md(self) -> None:
        import os

        runner = CliRunner()
        with runner.isolated_filesystem() as tmpdir:
            runner.invoke(
                cli,
                ["new", "project", "--quick", "--no-git", "--language", "Rust", "rustapp"],
            )
            with open(os.path.join(tmpdir, "rustapp", "AGENTS.md")) as f:
                agents_md = f.read()
            assert "Rust" in agents_md

    def test_new_project_directory_exists_fails(self) -> None:
        import os

        runner = CliRunner()
        with runner.isolated_filesystem() as tmpdir:
            os.makedirs(os.path.join(tmpdir, "myapp"))
            result = runner.invoke(cli, ["new", "project", "--quick", "--no-git", "myapp"])
        assert result.exit_code != 0

    def test_new_project_output_mentions_next_steps(self) -> None:
        runner = CliRunner()
        with runner.isolated_filesystem():
            result = runner.invoke(cli, ["new", "project", "--quick", "--no-git", "myapp"])
        assert "Next steps" in result.output or "cd myapp" in result.output


class TestSetupCommands:
    @patch("tak.setup.iterm2.setup_iterm2", return_value=True)
    def test_setup_iterm2(self, mock_fn: Any) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["setup", "iterm2"])
        assert result.exit_code == 0
        mock_fn.assert_called_once()

    @patch("tak.setup.iterm2.setup_iterm2_pip", return_value=True)
    def test_setup_iterm2_pip(self, mock_fn: Any) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["setup", "iterm2-pip"])
        assert result.exit_code == 0
        mock_fn.assert_called_once()

    @patch("tak.setup.fonts.setup_fonts", return_value=True)
    def test_setup_fonts(self, mock_fn: Any) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["setup", "fonts"])
        assert result.exit_code == 0
        mock_fn.assert_called_once()

    @patch("tak.setup.starship.setup_starship", return_value=True)
    def test_setup_starship(self, mock_fn: Any) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["setup", "starship"])
        assert result.exit_code == 0
        mock_fn.assert_called_once()

    @patch("tak.setup.shell.setup_shell", return_value=True)
    def test_setup_shell(self, mock_fn: Any) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["setup", "shell"])
        assert result.exit_code == 0
        mock_fn.assert_called_once()

    @patch("tak.setup.profiles.setup_profiles", return_value=True)
    def test_setup_profiles(self, mock_fn: Any) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["setup", "profiles"])
        assert result.exit_code == 0
        mock_fn.assert_called_once()

    @patch("tak.setup.tak_setup.setup_tak", return_value=True)
    def test_setup_tak(self, mock_fn: Any) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["setup", "tak"])
        assert result.exit_code == 0
        mock_fn.assert_called_once()

    @patch("tak.setup.fonts.setup_fonts", return_value=False)
    def test_setup_failure_exits_nonzero(self, mock_fn: Any) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["setup", "fonts"])
        assert result.exit_code != 0


class TestRemoveCommand:
    def test_remove_no_daemon(self) -> None:
        result = _invoke_no_daemon(["remove", "my-agent"])
        assert result.exit_code == 0
        assert "daemon not running" in result.output

    def test_remove_with_daemon_success(self) -> None:
        resp = MagicMock(success=True, data={"name": "old-agent", "status": "removed"})
        result = _invoke_with_daemon(["remove", "--force", "old-agent"], ipc_response=resp)
        assert result.exit_code == 0
        assert "removed" in result.output

    def test_remove_running_without_force_refuses(self) -> None:
        status_resp = MagicMock(
            success=True, data={"name": "live", "status": "running"},
        )
        with (
            patch("tak.cli.main._daemon_available", return_value=True),
            patch("tak.cli.main._run_async", return_value=status_resp),
        ):
            result = CliRunner().invoke(cli, ["remove", "live"])
        assert result.exit_code != 0
        assert "still running" in result.output

    def test_remove_error(self) -> None:
        resp = MagicMock(success=False, error="No agent named 'ghost'")
        result = _invoke_with_daemon(["remove", "--force", "ghost"], ipc_response=resp)
        assert result.exit_code != 0
        assert "ghost" in result.output


class TestInfoCommand:
    def test_info_no_daemon(self) -> None:
        result = _invoke_no_daemon(["info"])
        assert result.exit_code == 0
        assert "not running" in result.output
        assert "Session ID" in result.output

    def test_info_with_daemon(self) -> None:
        resp = MagicMock(
            success=True,
            data=[
                {"name": "my-agent", "provider": "cursor-acp", "status": "running",
                 "model": "Auto", "tabs": ["sess-123"]},
            ],
        )
        with (
            patch("tak.cli.main._daemon_available", return_value=True),
            patch("tak.cli.main._run_async", return_value=resp),
            patch("tak.cli.main._detect_session_id", return_value="sess-123"),
        ):
            result = CliRunner().invoke(cli, ["info"])
        assert result.exit_code == 0
        assert "my-agent" in result.output
        assert "running" in result.output
