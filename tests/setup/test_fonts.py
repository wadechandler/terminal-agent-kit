"""Tests for tak setup fonts — brew cask install and idempotency."""

from __future__ import annotations

import subprocess
from io import StringIO
from typing import Any
from unittest.mock import patch

from rich.console import Console

from tak.setup.fonts import setup_fonts


def _make_console() -> tuple[Console, StringIO]:
    buf = StringIO()
    return Console(file=buf, no_color=True, width=120), buf


def _completed(
    returncode: int = 0,
    stdout: str = "",
) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(args=[], returncode=returncode, stdout=stdout, stderr="")


class TestSetupFonts:
    def test_already_installed(self) -> None:
        con, buf = _make_console()

        with (
            patch("tak.setup.fonts.has_command", return_value=True),
            patch("tak.setup.fonts.run_cmd", return_value=_completed()),
        ):
            ok = setup_fonts(con)

        assert ok is True
        assert "already installed" in buf.getvalue()

    def test_installs_font(self) -> None:
        con, buf = _make_console()
        calls: list[tuple[Any, ...]] = []

        def _mock_run(*args: str, **kwargs: Any) -> subprocess.CompletedProcess[str]:
            calls.append(args)
            if "list" in args:
                return _completed(returncode=1)
            return _completed()

        with (
            patch("tak.setup.fonts.has_command", return_value=True),
            patch("tak.setup.fonts.run_cmd", side_effect=_mock_run),
        ):
            ok = setup_fonts(con)

        assert ok is True
        out = buf.getvalue()
        assert "installed" in out.lower()
        install_calls = [c for c in calls if "install" in c]
        assert len(install_calls) == 1

    def test_no_brew(self) -> None:
        con, buf = _make_console()

        with patch("tak.setup.fonts.has_command", return_value=False):
            ok = setup_fonts(con)

        assert ok is False
        assert "Homebrew not found" in buf.getvalue()

    def test_no_brew_prints_manual_instructions(self) -> None:
        con, buf = _make_console()

        with patch("tak.setup.fonts.has_command", return_value=False):
            setup_fonts(con)

        out = buf.getvalue()
        assert "nerdfonts.com" in out
        assert "JetBrainsMono" in out

    def test_idempotent_when_installed(self) -> None:
        con1, buf1 = _make_console()
        con2, buf2 = _make_console()

        with (
            patch("tak.setup.fonts.has_command", return_value=True),
            patch("tak.setup.fonts.run_cmd", return_value=_completed()),
        ):
            setup_fonts(con1)
            setup_fonts(con2)

        assert buf1.getvalue() == buf2.getvalue()
