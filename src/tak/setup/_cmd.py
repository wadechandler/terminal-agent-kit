"""Subprocess helpers for setup commands.

Wraps ``subprocess.run`` with full-path resolution (via ``shutil.which``) so
that Ruff S607 (partial executable path) does not fire on every call site.
"""

from __future__ import annotations

import shutil
import subprocess


def run_cmd(
    *args: str,
    check: bool = False,
    capture_output: bool = True,
) -> subprocess.CompletedProcess[str]:
    """Run an external command after resolving the executable to its full path.

    Args:
        *args: Command and arguments (e.g. ``"brew", "install", "starship"``).
        check: Raise :class:`subprocess.CalledProcessError` on non-zero exit.
        capture_output: Capture stdout and stderr.

    Returns:
        The completed process result.

    Raises:
        FileNotFoundError: If the executable is not found on ``PATH``.
        subprocess.CalledProcessError: If *check* is True and exit code != 0.
    """
    exe = shutil.which(args[0])
    if exe is None:
        msg = f"Command not found: {args[0]}"
        raise FileNotFoundError(msg)
    return subprocess.run(  # noqa: S603
        [exe, *args[1:]],
        capture_output=capture_output,
        text=True,
        check=check,
    )


def has_command(name: str) -> bool:
    """Check whether *name* exists on ``PATH``.

    Args:
        name: The command name to look up.

    Returns:
        True if the command is found.
    """
    return shutil.which(name) is not None
