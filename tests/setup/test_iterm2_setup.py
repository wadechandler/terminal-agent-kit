"""Tests for tak setup iterm2 — defaults read/write, connection test, pip install."""

from __future__ import annotations

import subprocess
from io import StringIO
from typing import Any
from unittest.mock import patch

from rich.console import Console

from tak.setup.iterm2 import _test_connection, setup_iterm2, setup_iterm2_pip


def _make_console() -> tuple[Console, StringIO]:
    buf = StringIO()
    return Console(file=buf, no_color=True, width=120), buf


def _completed(
    returncode: int = 0,
    stdout: str = "",
) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(args=[], returncode=returncode, stdout=stdout, stderr="")


class TestSetupIterm2:
    """Tests for the main setup_iterm2 function (defaults read/write)."""

    def test_already_enabled(self) -> None:
        con, buf = _make_console()

        with (
            patch("tak.setup.iterm2.has_command", return_value=True),
            patch("tak.setup.iterm2.run_cmd", return_value=_completed(stdout="1\n")),
            patch("tak.setup.iterm2._test_connection"),
        ):
            ok = setup_iterm2(con)

        assert ok is True
        assert "already enabled" in buf.getvalue()

    def test_enables_api_when_disabled(self) -> None:
        con, buf = _make_console()
        calls: list[tuple[Any, ...]] = []

        def _mock_run(*args: str, **kwargs: Any) -> subprocess.CompletedProcess[str]:
            calls.append(args)
            if "read" in args:
                return _completed(returncode=1)
            return _completed()

        with (
            patch("tak.setup.iterm2.has_command", return_value=True),
            patch("tak.setup.iterm2.run_cmd", side_effect=_mock_run),
            patch("tak.setup.iterm2._test_connection"),
        ):
            ok = setup_iterm2(con)

        assert ok is True
        out = buf.getvalue()
        assert "Python API enabled" in out
        assert "Restart iTerm2" in out
        assert len(calls) == 2

    def test_no_defaults_command(self) -> None:
        con, buf = _make_console()

        with patch("tak.setup.iterm2.has_command", return_value=False):
            ok = setup_iterm2(con)

        assert ok is False
        assert "macOS required" in buf.getvalue()

    def test_idempotent_when_already_enabled(self) -> None:
        con1, buf1 = _make_console()
        con2, buf2 = _make_console()

        with (
            patch("tak.setup.iterm2.has_command", return_value=True),
            patch("tak.setup.iterm2.run_cmd", return_value=_completed(stdout="1\n")),
            patch("tak.setup.iterm2._test_connection"),
        ):
            assert setup_iterm2(con1) is True
            assert setup_iterm2(con2) is True

        assert buf1.getvalue() == buf2.getvalue()

    def test_prints_manual_steps(self) -> None:
        con, buf = _make_console()

        with (
            patch("tak.setup.iterm2.has_command", return_value=True),
            patch("tak.setup.iterm2.run_cmd", return_value=_completed(stdout="1\n")),
            patch("tak.setup.iterm2._test_connection"),
        ):
            setup_iterm2(con)

        out = buf.getvalue()
        assert "Manual steps" in out
        assert "Enable Python API" in out


class TestConnectionTest:
    """Tests for the _test_connection helper."""

    def test_connection_success(self) -> None:
        con, buf = _make_console()

        with patch("tak.setup.iterm2.asyncio") as mock_asyncio:
            mock_asyncio.run.return_value = None
            _test_connection(con)

        assert "connection verified" in buf.getvalue()

    def test_connection_refused(self) -> None:
        con, buf = _make_console()

        with patch("tak.setup.iterm2.asyncio") as mock_asyncio:
            mock_asyncio.run.side_effect = ConnectionRefusedError("refused")
            _test_connection(con)

        assert "Could not connect" in buf.getvalue()

    def test_connection_timeout(self) -> None:
        con, buf = _make_console()

        with patch("tak.setup.iterm2.asyncio") as mock_asyncio:
            mock_asyncio.run.side_effect = TimeoutError
            _test_connection(con)

        assert "Could not connect" in buf.getvalue()

    def test_iterm2_not_importable(self) -> None:
        con, buf = _make_console()

        with patch.dict("sys.modules", {"iterm2": None}):
            _test_connection(con)

        assert "not available" in buf.getvalue()


class TestSetupIterm2Pip:
    """Tests for setup_iterm2_pip — install tak into iterm2env."""

    def test_no_iterm2env_skips(self) -> None:
        con, buf = _make_console()

        with patch("tak.setup.iterm2.glob.glob", return_value=[]):
            ok = setup_iterm2_pip(con)

        assert ok is True
        assert "iterm2env not found" in buf.getvalue()

    def test_dry_run_shows_command(self) -> None:
        con, buf = _make_console()
        fake_python = "/Users/test/.config/iterm2/AppSupport/iterm2env/versions/3.11.4/bin/python3"

        with patch("tak.setup.iterm2.glob.glob", return_value=[fake_python]):
            ok = setup_iterm2_pip(con, dry_run=True)

        assert ok is True
        out = buf.getvalue()
        assert "would run" in out
        assert "pip install -e" in out

    def test_successful_install(self) -> None:
        con, buf = _make_console()
        fake_python = "/Users/test/.config/iterm2/AppSupport/iterm2env/versions/3.11.4/bin/python3"

        with (
            patch("tak.setup.iterm2.glob.glob", return_value=[fake_python]),
            patch("tak.setup.iterm2.subprocess.run", return_value=_completed()),
        ):
            ok = setup_iterm2_pip(con)

        assert ok is True
        assert "installed into iterm2env" in buf.getvalue()

    def test_failed_install(self) -> None:
        con, buf = _make_console()
        fake_python = "/Users/test/.config/iterm2/AppSupport/iterm2env/versions/3.11.4/bin/python3"

        with (
            patch("tak.setup.iterm2.glob.glob", return_value=[fake_python]),
            patch(
                "tak.setup.iterm2.subprocess.run",
                return_value=_completed(returncode=1),
            ),
        ):
            ok = setup_iterm2_pip(con)

        assert ok is False
        assert "pip install failed" in buf.getvalue()

    def test_exception_during_install(self) -> None:
        con, buf = _make_console()
        fake_python = "/Users/test/.config/iterm2/AppSupport/iterm2env/versions/3.11.4/bin/python3"

        with (
            patch("tak.setup.iterm2.glob.glob", return_value=[fake_python]),
            patch(
                "tak.setup.iterm2.subprocess.run",
                side_effect=OSError("permission denied"),
            ),
        ):
            ok = setup_iterm2_pip(con)

        assert ok is False
        assert "pip install error" in buf.getvalue()
