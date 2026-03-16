"""Install JetBrains Mono Nerd Font via Homebrew.

A single cask (``font-jetbrains-mono-nerd-font``) provides both JetBrains
Mono and the Nerd Font icon patches (~3 600 glyphs).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from tak.setup._cmd import has_command, run_cmd

if TYPE_CHECKING:
    from rich.console import Console

_CASK = "font-jetbrains-mono-nerd-font"


def setup_fonts(console: Console, *, dry_run: bool = False) -> bool:
    """Install JetBrainsMono Nerd Font if not already present.

    Idempotent: checks ``brew list --cask`` before attempting an install.

    Args:
        console: Rich console for output.
        dry_run: If True, print what would happen without making changes.

    Returns:
        True if the font is installed (or was just installed).
    """
    if not has_command("brew"):
        console.print(
            "[yellow]⚠[/yellow] Homebrew not found — cannot install font automatically"
        )
        console.print("  Install manually from: https://www.nerdfonts.com/font-downloads")
        console.print("  Font: JetBrainsMono Nerd Font")
        return False

    result = run_cmd("brew", "list", "--cask", _CASK)
    if result.returncode == 0:
        console.print("[green]✓[/green] JetBrainsMono Nerd Font already installed")
        return True

    if dry_run:
        console.print(f"[dim]would run:[/dim] brew install --cask {_CASK}")
        return True

    console.print("Installing JetBrainsMono Nerd Font…")
    run_cmd("brew", "install", "--cask", _CASK, check=True)
    console.print("[green]✓[/green] JetBrainsMono Nerd Font installed")
    return True
