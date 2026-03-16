"""Tests for tak setup profiles — iTerm2 profile creation and error handling."""

from __future__ import annotations

import subprocess
from io import StringIO
from unittest.mock import patch

from rich.console import Console

from tak.setup.profiles import _font_installed, setup_profiles


def _make_console() -> tuple[Console, StringIO]:
    buf = StringIO()
    return Console(file=buf, no_color=True, width=120), buf


def _completed(
    returncode: int = 0,
    stdout: str = "",
) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(args=[], returncode=returncode, stdout=stdout, stderr="")


class TestSetupProfiles:
    def test_iterm2_not_installed(self) -> None:
        con, buf = _make_console()

        with patch.dict("sys.modules", {"iterm2": None}):
            ok = setup_profiles(con)

        assert ok is False
        assert "iterm2 package not installed" in buf.getvalue()

    def test_connection_refused(self) -> None:
        con, buf = _make_console()

        with patch(
            "tak.setup.profiles.asyncio"
        ) as mock_asyncio:
            mock_asyncio.run.side_effect = ConnectionRefusedError("refused")
            ok = setup_profiles(con)

        assert ok is False
        assert "Cannot connect to iTerm2" in buf.getvalue()

    def test_os_error(self) -> None:
        con, buf = _make_console()

        with patch(
            "tak.setup.profiles.asyncio"
        ) as mock_asyncio:
            mock_asyncio.run.side_effect = OSError("socket error")
            ok = setup_profiles(con)

        assert ok is False
        assert "Cannot connect" in buf.getvalue()

    def test_api_incompatibility(self) -> None:
        con, buf = _make_console()

        with patch(
            "tak.setup.profiles.asyncio"
        ) as mock_asyncio:
            mock_asyncio.run.side_effect = AttributeError("missing method")
            ok = setup_profiles(con)

        assert ok is False
        assert "API incompatibility" in buf.getvalue()

    def test_success_delegates_to_async(self) -> None:
        con, _buf = _make_console()

        with patch(
            "tak.setup.profiles.asyncio"
        ) as mock_asyncio:
            mock_asyncio.run.return_value = True
            ok = setup_profiles(con)

        assert ok is True


class TestFontInstalled:
    def test_font_present(self) -> None:
        with (
            patch("tak.setup.profiles.has_command", return_value=True),
            patch("tak.setup.profiles.run_cmd", return_value=_completed()),
        ):
            assert _font_installed() is True

    def test_font_absent(self) -> None:
        with (
            patch("tak.setup.profiles.has_command", return_value=True),
            patch("tak.setup.profiles.run_cmd", return_value=_completed(returncode=1)),
        ):
            assert _font_installed() is False

    def test_no_brew(self) -> None:
        with patch("tak.setup.profiles.has_command", return_value=False):
            assert _font_installed() is False
