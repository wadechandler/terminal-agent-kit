"""Tests for the tak CLI commands."""

from __future__ import annotations

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


class TestStatusCommand:
    def test_status_runs(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["status"])
        assert result.exit_code == 0


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


class TestScaffoldCommands:
    def test_scaffold_agents(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["scaffold", "agents"])
        assert result.exit_code == 0

    def test_scaffold_rules(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["scaffold", "rules"])
        assert result.exit_code == 0

    def test_scaffold_skills(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["scaffold", "skills"])
        assert result.exit_code == 0


class TestSetupCommands:
    def test_setup_starship(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["setup", "starship"])
        assert result.exit_code == 0

    def test_setup_fonts(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["setup", "fonts"])
        assert result.exit_code == 0
