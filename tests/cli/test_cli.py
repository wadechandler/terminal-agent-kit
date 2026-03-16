"""Tests for the tak CLI commands."""

from __future__ import annotations

from typing import Any
from unittest.mock import patch

from click.testing import CliRunner

from tak.cli.main import cli


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

    def test_spawn_with_name(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["spawn", "--name", "test-agent"])
        assert result.exit_code == 0
        assert "test-agent" in result.output

    def test_spawn_with_model(self) -> None:
        runner = CliRunner()
        result = runner.invoke(
            cli, ["spawn", "--name", "test-agent", "--model", "claude-sonnet-4"]
        )
        assert result.exit_code == 0
        assert "claude-sonnet-4" in result.output


class TestStatusCommand:
    def test_status_runs(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["status"])
        assert result.exit_code == 0

    def test_agents_alias(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["agents"])
        assert result.exit_code == 0


class TestStopCommand:
    def test_stop_without_daemon(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["stop", "my-agent"])
        assert result.exit_code == 0
        assert "my-agent" in result.output


class TestAskCommand:
    def test_ask_requires_query(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["ask"])
        assert result.exit_code != 0

    def test_ask_with_query(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["ask", "what", "is", "python"])
        assert result.exit_code == 0
        assert "what is python" in result.output


class TestSwitchCommand:
    def test_switch_without_daemon(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["switch", "my-agent"])
        assert result.exit_code == 0
        assert "my-agent" in result.output


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
