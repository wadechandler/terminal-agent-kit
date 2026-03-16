"""Tests for tak setup starship — install, config merge, and idempotency."""

from __future__ import annotations

import subprocess
from io import StringIO
from typing import TYPE_CHECKING
from unittest.mock import patch

if TYPE_CHECKING:
    from pathlib import Path

from rich.console import Console

from tak.setup.starship import setup_starship


def _make_console() -> tuple[Console, StringIO]:
    buf = StringIO()
    return Console(file=buf, no_color=True, width=120), buf


def _completed(
    returncode: int = 0,
    stdout: str = "",
) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(args=[], returncode=returncode, stdout=stdout, stderr="")


class TestSetupStarship:
    def test_already_installed_and_configured(self, tmp_path: Path) -> None:
        config = tmp_path / "starship.toml"
        config.write_text("[custom.tak]\ncommand = ...\n")
        con, buf = _make_console()

        with patch("tak.setup.starship.has_command", return_value=True):
            ok = setup_starship(con, config_path=config)

        assert ok is True
        assert "already in starship config" in buf.getvalue()

    def test_appends_tak_module_to_existing_config(self, tmp_path: Path) -> None:
        config = tmp_path / "starship.toml"
        original = "[character]\nsuccess_symbol = '>'\n"
        config.write_text(original)
        con, buf = _make_console()

        with patch("tak.setup.starship.has_command", return_value=True):
            ok = setup_starship(con, config_path=config)

        assert ok is True
        content = config.read_text()
        assert "[custom.tak]" in content
        assert "[character]" in content
        assert "Added tak module" in buf.getvalue()

    def test_creates_default_config_when_missing(self, tmp_path: Path) -> None:
        config = tmp_path / ".config" / "starship.toml"
        con, buf = _make_console()

        with patch("tak.setup.starship.has_command", return_value=True):
            ok = setup_starship(con, config_path=config)

        assert ok is True
        assert config.exists()
        content = config.read_text()
        assert "[custom.tak]" in content
        assert "Created starship config" in buf.getvalue()

    def test_default_config_includes_character_section(self, tmp_path: Path) -> None:
        config = tmp_path / "starship.toml"
        con, _ = _make_console()

        with patch("tak.setup.starship.has_command", return_value=True):
            setup_starship(con, config_path=config)

        content = config.read_text()
        assert "[character]" in content
        assert "success_symbol" in content

    def test_installs_starship_via_brew(self, tmp_path: Path) -> None:
        config = tmp_path / "starship.toml"
        con, buf = _make_console()

        def _mock_has(name: str) -> bool:
            return name != "starship"

        with (
            patch("tak.setup.starship.has_command", side_effect=_mock_has),
            patch("tak.setup.starship.run_cmd", return_value=_completed()),
        ):
            ok = setup_starship(con, config_path=config)

        assert ok is True
        assert "Starship installed" in buf.getvalue()

    def test_no_starship_no_brew(self, tmp_path: Path) -> None:
        config = tmp_path / "starship.toml"
        con, buf = _make_console()

        with patch("tak.setup.starship.has_command", return_value=False):
            ok = setup_starship(con, config_path=config)

        assert ok is False
        assert "not found" in buf.getvalue().lower()
        assert "starship.rs" in buf.getvalue()

    def test_idempotent_append(self, tmp_path: Path) -> None:
        config = tmp_path / "starship.toml"
        config.write_text("[character]\nsuccess_symbol = '>'\n")
        con1, _ = _make_console()
        con2, buf2 = _make_console()

        with patch("tak.setup.starship.has_command", return_value=True):
            setup_starship(con1, config_path=config)
            content_first = config.read_text()
            setup_starship(con2, config_path=config)
            content_second = config.read_text()

        assert content_first == content_second
        assert "already in starship config" in buf2.getvalue()

    def test_creates_parent_directories(self, tmp_path: Path) -> None:
        config = tmp_path / "deep" / "nested" / "starship.toml"
        con, _ = _make_console()

        with patch("tak.setup.starship.has_command", return_value=True):
            ok = setup_starship(con, config_path=config)

        assert ok is True
        assert config.exists()
