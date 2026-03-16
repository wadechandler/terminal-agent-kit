"""All-in-one ``tak setup tak`` orchestrator.

Runs every individual setup step in sequence, presenting a Rich-formatted
summary of results at the end.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from tak.setup.fonts import setup_fonts
from tak.setup.iterm2 import setup_iterm2
from tak.setup.profiles import setup_profiles
from tak.setup.shell import setup_shell
from tak.setup.starship import setup_starship

if TYPE_CHECKING:
    from rich.console import Console


def setup_tak(console: Console, *, dry_run: bool = False) -> bool:
    """Run all setup steps in order and report a summary.

    Steps: iterm2 → fonts → starship → shell → profiles.

    Args:
        console: Rich console for output.
        dry_run: If True, print what each step would do without making changes.

    Returns:
        True if every step succeeded.
    """
    if dry_run:
        console.print("[bold]Dry run — showing what each step would do:[/bold]\n")

    steps: list[tuple[str, bool]] = []

    for label, fn in (
        ("iTerm2 API", setup_iterm2),
        ("Fonts", setup_fonts),
        ("Starship", setup_starship),
        ("Shell config", setup_shell),
        ("iTerm2 profiles", setup_profiles),
    ):
        console.rule(f"[bold]{label}[/bold]")
        ok = fn(console, dry_run=dry_run)
        steps.append((label, ok))
        console.print()

    console.rule("[bold]Summary[/bold]")
    all_ok = True
    for label, ok in steps:
        icon = "[green]✓[/green]" if ok else "[yellow]⚠[/yellow]"
        console.print(f"  {icon} {label}")
        if not ok:
            all_ok = False

    return all_ok
