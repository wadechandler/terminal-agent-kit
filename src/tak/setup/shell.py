"""Configure shell integration for tak.

Appends a managed block to ``~/.bashrc`` that initialises Starship.  The
block is fenced with ``# -- tak managed start/end --`` markers so it can be
detected (idempotency) and removed cleanly.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from tak.setup._cmd import has_command, run_cmd

if TYPE_CHECKING:
    from rich.console import Console

_MARKER_START = "# -- tak managed start --"
_MARKER_END = "# -- tak managed end --"

_MANAGED_BLOCK = f"""\
{_MARKER_START}
if [[ $- == *i* ]]; then
    eval "$(starship init bash)"
fi
{_MARKER_END}
"""


def setup_shell(
    console: Console,
    bashrc_path: Path | None = None,
    *,
    dry_run: bool = False,
) -> bool:
    """Configure ``~/.bashrc`` with Starship init and tak integrations.

    Idempotent: detects the managed-block marker before appending.

    Args:
        console: Rich console for output.
        bashrc_path: Override for the ``.bashrc`` path (default ``~/.bashrc``).
        dry_run: If True, print what would happen without making changes.

    Returns:
        True if shell configuration is in place.
    """
    bashrc_path = bashrc_path or Path.home() / ".bashrc"

    _check_bash_version(console)

    if bashrc_path.exists():
        content = bashrc_path.read_text()
        if _MARKER_START in content:
            existing_block = _extract_managed_block(content)
            expected_block = _MANAGED_BLOCK.strip()
            if existing_block == expected_block:
                console.print(
                    "[green]✓[/green] .bashrc already configured (tak marker found)"
                )
                return True
            if dry_run:
                console.print("[dim]would update:[/dim] tak managed block in .bashrc")
            else:
                updated = _replace_managed_block(content, _MANAGED_BLOCK.strip())
                bashrc_path.write_text(updated)
                console.print("[green]✓[/green] Updated tak managed block in .bashrc")
            return True
        if dry_run:
            console.print(f"[dim]would append:[/dim] tak managed block to {bashrc_path}")
        else:
            bashrc_path.write_text(content.rstrip() + "\n\n" + _MANAGED_BLOCK)
            console.print("[green]✓[/green] Added tak managed block to .bashrc")
    elif dry_run:
        console.print(f"[dim]would create:[/dim] {bashrc_path} with tak managed block")
    else:
        bashrc_path.parent.mkdir(parents=True, exist_ok=True)
        bashrc_path.write_text(_MANAGED_BLOCK)
        console.print("[green]✓[/green] Created .bashrc with tak managed block")

    return True


def _extract_managed_block(content: str) -> str:
    """Extract the managed block (markers included) from bashrc content."""
    start = content.find(_MARKER_START)
    end = content.find(_MARKER_END)
    if start == -1 or end == -1:
        return ""
    return content[start:end + len(_MARKER_END)].strip()


def _replace_managed_block(content: str, new_block: str) -> str:
    """Replace the managed block in bashrc content with a new version."""
    start = content.find(_MARKER_START)
    end = content.find(_MARKER_END)
    if start == -1 or end == -1:
        return content
    before = content[:start]
    after = content[end + len(_MARKER_END):]
    return before + new_block + after


def _check_bash_version(console: Console) -> None:
    """Detect the current bash version and warn if it is macOS stock 3.x."""
    if not has_command("bash"):
        console.print("[yellow]⚠[/yellow] bash not found on PATH")
        return

    result = run_cmd("bash", "--version")
    if result.returncode != 0:
        return

    first_line = result.stdout.split("\n", maxsplit=1)[0].strip()

    if "version 3." in first_line:
        console.print(
            f"[yellow]⚠[/yellow] Stock macOS bash detected: {first_line}"
        )
        console.print("  Recommend: [bold]brew install bash[/bold] for bash 5.x")
    else:
        console.print(f"[green]✓[/green] {first_line}")
