"""Install and configure Starship prompt with a tak custom module.

If Starship is missing, this module installs it via Homebrew.  It then
ensures ``~/.config/starship.toml`` contains the ``[custom.tak]`` section
that displays the active agent name in the prompt.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from tak.setup._cmd import has_command, run_cmd

if TYPE_CHECKING:
    from rich.console import Console

_TAK_MODULE = """\

[custom.tak]
command = "echo $TAK_AGENT"
when = '[ -n "$TAK_AGENT" ]'
format = "via [tak:$output](bold blue) "
"""

_DEFAULT_CONFIG = """\
# Starship prompt configuration
# Managed by tak — https://github.com/wadechandler/terminal-agent-kit
# See https://starship.rs/config/ for full documentation

format = "$all"

[character]
success_symbol = "[❯](bold green)"
error_symbol = "[❯](bold red)"

[custom.tak]
command = "echo $TAK_AGENT"
when = '[ -n "$TAK_AGENT" ]'
format = "via [tak:$output](bold blue) "
"""


def setup_starship(
    console: Console,
    config_path: Path | None = None,
    *,
    dry_run: bool = False,
) -> bool:
    """Install Starship and add the tak custom module to its config.

    Idempotent: skips install if Starship is on ``PATH`` and skips config
    edits when the ``[custom.tak]`` section is already present.

    Args:
        console: Rich console for output.
        config_path: Override for the ``starship.toml`` path
            (default ``~/.config/starship.toml``).
        dry_run: If True, print what would happen without making changes.

    Returns:
        True if Starship is installed and configured.
    """
    config_path = config_path or Path.home() / ".config" / "starship.toml"

    if has_command("starship"):
        console.print("[green]✓[/green] Starship already installed")
    elif has_command("brew"):
        if dry_run:
            console.print("[dim]would run:[/dim] brew install starship")
        else:
            console.print("Installing Starship…")
            run_cmd("brew", "install", "starship", check=True)
            console.print("[green]✓[/green] Starship installed")
    else:
        console.print(
            "[yellow]⚠[/yellow] Starship not found and Homebrew not available"
        )
        console.print("  Install from: https://starship.rs")
        return False

    if config_path.exists():
        content = config_path.read_text()
        if "[custom.tak]" in content:
            console.print("[green]✓[/green] tak module already in starship config")
            return True
        if dry_run:
            console.print(f"[dim]would append:[/dim] [custom.tak] section to {config_path}")
        else:
            config_path.write_text(content.rstrip() + _TAK_MODULE)
            console.print("[green]✓[/green] Added tak module to starship config")
    elif dry_run:
        console.print(f"[dim]would create:[/dim] {config_path} with default config")
    else:
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text(_DEFAULT_CONFIG)
        console.print(
            f"[green]✓[/green] Created starship config at {config_path}"
        )

    return True
