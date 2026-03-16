"""Create iTerm2 profiles for tak agent sessions.

Connects to a running iTerm2 instance, checks for an existing
``tak-default`` profile, and creates one if absent.  Requires the
Python API to be enabled (see :mod:`tak.setup.iterm2`).
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any

from tak.setup._cmd import has_command, run_cmd

if TYPE_CHECKING:
    from rich.console import Console

PROFILE_NAME = "tak-default"
_FONT = "JetBrainsMono Nerd Font 14"
_FALLBACK_FONT = "Monaco 14"
_FONT_CASK = "font-jetbrains-mono-nerd-font"


def setup_profiles(console: Console, *, dry_run: bool = False) -> bool:
    """Create the ``tak-default`` iTerm2 profile if it does not exist.

    Idempotent: queries existing profiles before attempting creation.

    Args:
        console: Rich console for output.
        dry_run: If True, print what would happen without making changes.

    Returns:
        True if the profile exists or was created.
    """
    if dry_run:
        console.print(f"[dim]would create:[/dim] iTerm2 profile '{PROFILE_NAME}' "
                      f"(font: {_FONT}, dark blue-gray theme)")
        return True

    try:
        import iterm2 as _iterm2  # noqa: F401
    except ImportError:
        console.print("[yellow]⚠[/yellow] iterm2 package not installed")
        console.print("  Install: pip install iterm2")
        return False

    try:
        return asyncio.run(_create_profile_async(console))
    except (ConnectionRefusedError, OSError) as exc:
        console.print(f"[yellow]⚠[/yellow] Cannot connect to iTerm2: {exc}")
        console.print("  Ensure iTerm2 is running with Python API enabled")
        return False
    except (AttributeError, TypeError) as exc:
        console.print(f"[yellow]⚠[/yellow] iTerm2 API incompatibility: {exc}")
        console.print("  Try updating the iterm2 package: pip install --upgrade iterm2")
        return False


def _font_installed() -> bool:
    """Check whether JetBrainsMono Nerd Font is installed via Homebrew."""
    if not has_command("brew"):
        return False
    result = run_cmd("brew", "list", "--cask", _FONT_CASK)
    return result.returncode == 0


async def _create_profile_async(console: Console) -> bool:
    """Query iTerm2 profiles and create ``tak-default`` if absent."""
    import iterm2

    connection = await iterm2.Connection.async_create()
    all_profiles = await iterm2.PartialProfile.async_query(connection)

    for prof in all_profiles:
        if _profile_name(prof) == PROFILE_NAME:
            console.print(
                f"[green]✓[/green] Profile '{PROFILE_NAME}' already exists"
            )
            return True

    font = _FONT if _font_installed() else _FALLBACK_FONT

    new_profile = iterm2.LocalWriteOnlyProfile()
    new_profile.set_name(PROFILE_NAME)
    new_profile.set_normal_font(font)
    new_profile.set_foreground_color(iterm2.Color(212, 212, 212))
    new_profile.set_background_color(iterm2.Color(30, 33, 39))
    new_profile.set_cursor_color(iterm2.Color(97, 175, 239))
    await iterm2.Profile.async_create(connection, new_profile)

    console.print(f"[green]✓[/green] Created profile '{PROFILE_NAME}' (font: {font})")
    console.print()
    console.print("[bold]Manual steps:[/bold]")
    console.print("  • Open iTerm2 → Profiles → select 'tak-default'")
    console.print("  • Optionally add a status bar component via Session → Configure Status Bar")
    return True


def _profile_name(profile: Any) -> str | None:
    """Extract the name from a PartialProfile, or None if unavailable."""
    try:
        return profile.name  # type: ignore[no-any-return]
    except AttributeError:
        return None
