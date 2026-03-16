"""Tests for tak setup iterm2 — defaults read/write, connection test, idempotency."""

from __future__ import annotations

import subprocess
from io import StringIO
from typing import Any
from unittest.mock import patch

from rich.console import Console

from tak.setup.iterm2 import _test_connection, setup_iterm2


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
