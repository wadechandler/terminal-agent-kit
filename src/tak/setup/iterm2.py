"""Configure iTerm2 Python API for tak integration.

Enables the iTerm2 Python API via ``defaults write``, verifies connectivity
with a short-lived connection test, installs tak into iTerm2's bundled Python
environment, and prints follow-up instructions the user must complete manually.
"""

from __future__ import annotations

import asyncio
import glob
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING

from tak.setup._cmd import has_command, run_cmd

if TYPE_CHECKING:
    from rich.console import Console

_ITERM2ENV_GLOB = str(
    Path.home()
    / ".config" / "iterm2" / "AppSupport" / "iterm2env"
    / "versions" / "*" / "bin" / "python3"
)

_CONNECTION_TIMEOUT = 3.0


def setup_iterm2(console: Console, *, dry_run: bool = False) -> bool:
    """Enable the iTerm2 Python API and verify connectivity.

    Idempotent: skips the ``defaults write`` if the API is already enabled.

    Args:
        console: Rich console for output.
        dry_run: If True, print what would happen without making changes.

    Returns:
        True if setup completed (or was already done).
    """
    if not has_command("defaults"):
        console.print("[red]✗[/red] 'defaults' command not found — macOS required")
        return False

    result = run_cmd(
        "defaults", "read", "com.googlecode.iterm2", "EnableAPIServer",
    )
    api_enabled = result.returncode == 0 and result.stdout.strip() == "1"

    if api_enabled:
        console.print("[green]✓[/green] iTerm2 Python API already enabled")
    elif dry_run:
        console.print("[dim]would run:[/dim] defaults write com.googlecode.iterm2 "
                      "EnableAPIServer -bool true")
    else:
        run_cmd(
            "defaults", "write", "com.googlecode.iterm2",
            "EnableAPIServer", "-bool", "true",
            check=True,
        )
        console.print("[green]✓[/green] iTerm2 Python API enabled")
        console.print("[yellow]⚠[/yellow] Restart iTerm2 to apply changes")

    if not dry_run:
        _test_connection(console)

    console.print()
    console.print("[bold]Manual steps:[/bold]")
    console.print("  • Open iTerm2 → Settings → General → Magic")
    console.print("  • Verify 'Enable Python API' is checked")
    console.print("  • Approve the tak daemon when prompted on first run")
    return True


def _test_connection(console: Console) -> None:
    """Try a short-lived connection to verify the API is reachable."""
    try:
        import iterm2
    except ImportError:
        console.print(
            "[yellow]⚠[/yellow] iterm2 package not available — skipping connection test"
        )
        return

    async def _connect() -> None:
        await asyncio.wait_for(
            iterm2.Connection.async_create(), timeout=_CONNECTION_TIMEOUT,
        )

    try:
        asyncio.run(_connect())
        console.print("[green]✓[/green] iTerm2 API connection verified")
    except (TimeoutError, ConnectionRefusedError, OSError):
        console.print(
            "[yellow]⚠[/yellow] Could not connect to iTerm2 — restart may be needed"
        )


def _find_iterm2env_python() -> str | None:
    """Locate the Python interpreter inside iTerm2's bundled environment.

    Uses the unnumbered ``iterm2env/`` directory (not ``iterm2env-NN/``).

    Returns:
        Absolute path to the ``python3`` binary, or ``None`` if not found.
    """
    matches = sorted(glob.glob(_ITERM2ENV_GLOB))
    return matches[0] if matches else None


def setup_iterm2_pip(console: Console, *, dry_run: bool = False) -> bool:
    """Install tak into iTerm2's bundled Python environment.

    Finds the ``python3`` inside ``~/.config/iterm2/AppSupport/iterm2env/``
    and runs ``python3 -m pip install -e <project_root>``.  Uses ``-m pip``
    rather than bare ``pip`` because the pip shebang may point to a stale env.

    Args:
        console: Rich console for output.
        dry_run: If True, print what would happen without making changes.

    Returns:
        True if the install succeeded or was skipped (no iterm2env found).
    """
    python_path = _find_iterm2env_python()

    if python_path is None:
        console.print(
            "[yellow]⚠[/yellow] iterm2env not found — skipping pip install. "
            "Run iTerm2 once to create the Python environment."
        )
        return True

    project_root = Path(__file__).resolve().parents[3]

    cmd = [python_path, "-m", "pip", "install", "-e", str(project_root)]

    if dry_run:
        console.print(f"[dim]would run:[/dim] {' '.join(cmd)}")
        return True

    console.print(f"[dim]Installing tak into iterm2env ({python_path})…[/dim]")
    try:
        result = subprocess.run(  # noqa: S603
            cmd,
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode == 0:
            console.print("[green]✓[/green] tak installed into iterm2env")
            return True
        console.print(f"[red]✗[/red] pip install failed (exit {result.returncode})")
        if result.stderr:
            for line in result.stderr.strip().splitlines()[-3:]:
                console.print(f"  {line}")
        return False
    except Exception as exc:
        console.print(f"[red]✗[/red] pip install error: {exc}")
        return False
