"""Configure iTerm2 Python API for tak integration.

Enables the iTerm2 Python API via ``defaults write``, verifies connectivity
with a short-lived connection test, and prints follow-up instructions the
user must complete manually (restart, keybindings).
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from tak.setup._cmd import has_command, run_cmd

if TYPE_CHECKING:
    from rich.console import Console

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
