"""Tests for tak setup shell — .bashrc configuration and idempotency."""

from __future__ import annotations

import subprocess
from io import StringIO
from typing import TYPE_CHECKING
from unittest.mock import patch

if TYPE_CHECKING:
    from pathlib import Path

from rich.console import Console

from tak.setup.shell import _MANAGED_BLOCK, _MARKER_END, _MARKER_START, setup_shell


def _make_console() -> tuple[Console, StringIO]:
    buf = StringIO()
    return Console(file=buf, no_color=True, width=120), buf


def _completed(
    returncode: int = 0,
    stdout: str = "",
) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(args=[], returncode=returncode, stdout=stdout, stderr="")


def _bash5() -> subprocess.CompletedProcess[str]:
    return _completed(stdout="GNU bash, version 5.2.26(1)-release (aarch64-apple-darwin23.2.0)\n")


def _bash3() -> subprocess.CompletedProcess[str]:
    return _completed(
        stdout="GNU bash, version 3.2.57(1)-release (x86_64-apple-darwin21)\n"
    )


class TestSetupShell:
    def test_marker_already_present_and_current(self, tmp_path: Path) -> None:
        bashrc = tmp_path / ".bashrc"
        bashrc.write_text(_MANAGED_BLOCK)
        con, buf = _make_console()

        with (
            patch("tak.setup.shell.has_command", return_value=True),
            patch("tak.setup.shell.run_cmd", return_value=_bash5()),
        ):
            ok = setup_shell(con, bashrc_path=bashrc)

        assert ok is True
        assert "already configured" in buf.getvalue()

    def test_stale_managed_block_is_upgraded(self, tmp_path: Path) -> None:
        bashrc = tmp_path / ".bashrc"
        old_block = f'{_MARKER_START}\neval "$(starship init bash)"\n{_MARKER_END}\n'
        bashrc.write_text(f"export FOO=bar\n\n{old_block}")
        con, buf = _make_console()

        with (
            patch("tak.setup.shell.has_command", return_value=True),
            patch("tak.setup.shell.run_cmd", return_value=_bash5()),
        ):
            ok = setup_shell(con, bashrc_path=bashrc)

        assert ok is True
        assert "Updated tak managed block" in buf.getvalue()
        content = bashrc.read_text()
        assert "if [[ $- == *i* ]]" in content
        assert "export FOO=bar" in content

    def test_appends_to_existing_bashrc(self, tmp_path: Path) -> None:
        bashrc = tmp_path / ".bashrc"
        bashrc.write_text("export PATH=$HOME/bin:$PATH\n")
        con, buf = _make_console()

        with (
            patch("tak.setup.shell.has_command", return_value=True),
            patch("tak.setup.shell.run_cmd", return_value=_bash5()),
        ):
            ok = setup_shell(con, bashrc_path=bashrc)

        assert ok is True
        content = bashrc.read_text()
        assert _MARKER_START in content
        assert _MARKER_END in content
        assert "export PATH" in content
        assert "Added tak managed block" in buf.getvalue()

    def test_creates_bashrc_when_missing(self, tmp_path: Path) -> None:
        bashrc = tmp_path / ".bashrc"
        con, buf = _make_console()

        with (
            patch("tak.setup.shell.has_command", return_value=True),
            patch("tak.setup.shell.run_cmd", return_value=_bash5()),
        ):
            ok = setup_shell(con, bashrc_path=bashrc)

        assert ok is True
        assert bashrc.exists()
        content = bashrc.read_text()
        assert _MARKER_START in content
        assert "starship init bash" in content
        assert "Created .bashrc" in buf.getvalue()

    def test_idempotent_double_run(self, tmp_path: Path) -> None:
        bashrc = tmp_path / ".bashrc"
        bashrc.write_text("existing content\n")
        con1, _ = _make_console()
        con2, buf2 = _make_console()

        with (
            patch("tak.setup.shell.has_command", return_value=True),
            patch("tak.setup.shell.run_cmd", return_value=_bash5()),
        ):
            setup_shell(con1, bashrc_path=bashrc)
            content_first = bashrc.read_text()
            setup_shell(con2, bashrc_path=bashrc)
            content_second = bashrc.read_text()

        assert content_first == content_second
        assert "already configured" in buf2.getvalue()

    def test_bash3_version_warning(self, tmp_path: Path) -> None:
        bashrc = tmp_path / ".bashrc"
        con, buf = _make_console()

        with (
            patch("tak.setup.shell.has_command", return_value=True),
            patch("tak.setup.shell.run_cmd", return_value=_bash3()),
        ):
            setup_shell(con, bashrc_path=bashrc)

        out = buf.getvalue()
        assert "Stock macOS bash" in out
        assert "brew install bash" in out

    def test_bash5_no_warning(self, tmp_path: Path) -> None:
        bashrc = tmp_path / ".bashrc"
        con, buf = _make_console()

        with (
            patch("tak.setup.shell.has_command", return_value=True),
            patch("tak.setup.shell.run_cmd", return_value=_bash5()),
        ):
            setup_shell(con, bashrc_path=bashrc)

        out = buf.getvalue()
        assert "Stock macOS bash" not in out

    def test_no_bash_on_path(self, tmp_path: Path) -> None:
        bashrc = tmp_path / ".bashrc"
        con, buf = _make_console()

        with patch("tak.setup.shell.has_command", return_value=False):
            ok = setup_shell(con, bashrc_path=bashrc)

        assert ok is True
        assert "bash not found" in buf.getvalue()

    def test_managed_block_contains_starship_init(self, tmp_path: Path) -> None:
        bashrc = tmp_path / ".bashrc"
        con, _ = _make_console()

        with (
            patch("tak.setup.shell.has_command", return_value=True),
            patch("tak.setup.shell.run_cmd", return_value=_bash5()),
        ):
            setup_shell(con, bashrc_path=bashrc)

        content = bashrc.read_text()
        start = content.index(_MARKER_START)
        end = content.index(_MARKER_END)
        block = content[start:end]
        assert "starship init bash" in block
