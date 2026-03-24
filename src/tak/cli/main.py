"""CLI entry point for the ``tak`` command."""

from __future__ import annotations

import asyncio
import os
import sys
from typing import TYPE_CHECKING, Any, TypeVar

if TYPE_CHECKING:
    from collections.abc import Coroutine

import click
from rich.console import Console
from rich.markup import escape as rich_escape
from rich.table import Table

console = Console()

_T = TypeVar("_T")


def _run_async(coro: Coroutine[Any, Any, _T]) -> _T:
    """Run an async coroutine from synchronous Click commands."""
    return asyncio.run(coro)


def _daemon_available() -> bool:
    """Check whether the tak daemon socket exists."""
    from tak.ipc.client import DEFAULT_SOCKET_PATH

    return DEFAULT_SOCKET_PATH.exists()


# ---------------------------------------------------------------------------
# Root group
# ---------------------------------------------------------------------------


@click.group(context_settings={"max_content_width": 120})
@click.version_option(package_name="terminal-agent-kit")
def cli() -> None:
    """Terminal Agent Kit (tak) -- Transform your terminal into an agentic workspace."""


# ---------------------------------------------------------------------------
# Agent management commands
# ---------------------------------------------------------------------------


def _detect_session_id() -> str | None:
    """Detect the terminal session ID via the active driver."""
    from tak.drivers.iterm2.driver import ITerm2Driver

    return ITerm2Driver.detect_session_id()


_PERMISSION_CHOICES = ["prompt", "reject", "auto-allow", "yolo"]

_MSG_DAEMON_OFF_IT2 = "  [daemon not running -- start iTerm2 with tak daemon]"
_MSG_DAEMON_OFF_SHORT = "  [daemon not running]"


@cli.command()
@click.argument("provider", default="cursor-acp")
@click.option("--name", "-n", required=True, help="Name for this agent instance")
@click.option("--project", "-p", default=None, help="Project folder path")
@click.option("--model", "-m", default=None, help="Model name (e.g. claude-sonnet-4)")
@click.option(
    "--no-associate", is_flag=True, default=False,
    help="Do not auto-associate the current terminal tab",
)
@click.option(
    "--permissions", "permission_policy", default="prompt",
    type=click.Choice(_PERMISSION_CHOICES, case_sensitive=False),
    help="Permission policy for tool calls (default: prompt)",
)
def spawn(
    provider: str,
    name: str,
    project: str | None,
    model: str | None,
    no_associate: bool,
    permission_policy: str,
) -> None:
    """Spawn a new agent instance.

    PROVIDER is the agent provider to use (default: cursor-acp).
    Run 'tak providers' to see available providers.
    """
    if permission_policy == "yolo":
        click.echo(
            "Warning: yolo mode grants irrevocable per-tool permissions "
            "for this session.",
            err=True,
        )

    if not _daemon_available():
        click.echo(f"Spawning agent '{name}' with provider '{provider}'...")
        if project:
            click.echo(f"  Project: {project}")
        if model:
            click.echo(f"  Model: {model}")
        click.echo(_MSG_DAEMON_OFF_IT2)
        return

    from tak.ipc.client import send_request

    params: dict[str, object] = {"name": name, "provider": provider}
    params["project_path"] = project or os.getcwd()
    if model:
        params["model"] = model
    params["permission_policy"] = permission_policy

    if not no_associate:
        session_id = _detect_session_id()
        if session_id:
            params["session_id"] = session_id
        else:
            click.echo(
                "Note: No terminal session detected; "
                "skipping tab auto-association.",
                err=True,
            )

    resp = _run_async(send_request("spawn", params))
    if resp.success:
        click.echo(f"Agent '{name}' spawned ({resp.data})")
    else:
        click.echo(f"Error: {resp.error}", err=True)
        sys.exit(1)


@cli.command()
def status() -> None:
    """Show status of all running agents."""
    if not _daemon_available():
        click.echo("Running agents:")
        click.echo(_MSG_DAEMON_OFF_SHORT)
        return

    from tak.ipc.client import send_request

    resp = _run_async(send_request("list_agents"))
    if not resp.success:
        click.echo(f"Error: {resp.error}", err=True)
        sys.exit(1)

    agents = resp.data or []
    if not agents:
        click.echo("No agents running.")
        return

    table = Table(title="tak agents")
    table.add_column("Name", style="cyan")
    table.add_column("Provider")
    table.add_column("Model")
    table.add_column("Status", style="bold")
    table.add_column("Tabs")

    for agent in agents:
        model_display = agent.get("model") or "--"
        table.add_row(
            rich_escape(agent["name"]),
            rich_escape(agent["provider"]),
            rich_escape(model_display),
            agent["status"],
            ", ".join(agent.get("tabs", [])) or "--",
        )

    console.print(table)


@cli.command()
def providers() -> None:
    """List available agent providers."""
    if not _daemon_available():
        click.echo("Available providers:")
        click.echo(_MSG_DAEMON_OFF_IT2)
        click.echo()
        click.echo("Default providers (when daemon is running):")
        click.echo("  cursor-acp    Cursor (ACP over stdio)")
        return

    from tak.ipc.client import send_request

    resp = _run_async(send_request("list_providers"))
    if not resp.success:
        click.echo(f"Error: {resp.error}", err=True)
        sys.exit(1)

    items = resp.data or []
    if not items:
        click.echo("No providers registered.")
        return

    table = Table(title="tak providers")
    table.add_column("ID", style="cyan")
    table.add_column("Name")
    table.add_column("Protocol")
    table.add_column("Interaction")

    for p in items:
        table.add_row(
            rich_escape(p["id"]),
            rich_escape(p["name"]),
            p.get("protocol", "--"),
            p.get("interaction_model", "--"),
        )

    console.print(table)
    click.echo()
    click.echo("Use the ID as the PROVIDER argument to 'tak spawn'.")


@cli.command()
@click.argument("name")
def stop(name: str) -> None:
    """Stop a running agent."""
    if not _daemon_available():
        click.echo(f"Stopping agent '{name}'...")
        click.echo(_MSG_DAEMON_OFF_SHORT)
        return

    from tak.ipc.client import send_request

    resp = _run_async(send_request("stop", {"name": name}))
    if resp.success:
        click.echo(f"Agent '{name}' stopped.")
    else:
        click.echo(f"Error: {resp.error}", err=True)
        sys.exit(1)


@cli.command()
@click.argument("name")
@click.option("--force", "-f", is_flag=True, help="Remove even if running (stops first)")
def remove(name: str, force: bool) -> None:
    """Remove an agent from tak entirely.

    Stops the agent if still running (with --force), then deletes it from
    state. Without --force, refuses to remove a running agent.
    """
    if not _daemon_available():
        click.echo(f"Cannot remove '{name}' -- daemon not running.")
        return

    from tak.ipc.client import send_request

    if not force:
        resp = _run_async(send_request("status", {"name": name}))
        if resp.success and resp.data and resp.data.get("status") == "running":
            click.echo(
                f"Agent '{name}' is still running. "
                "Use --force to stop and remove, or 'tak stop' first.",
                err=True,
            )
            sys.exit(1)

    resp = _run_async(send_request("remove", {"name": name}))
    if resp.success:
        click.echo(f"Agent '{name}' removed.")
    else:
        click.echo(f"Error: {resp.error}", err=True)
        sys.exit(1)


def _info_associated_agent_and_list(
    session_id: str | None,
) -> tuple[str, list[dict[str, Any]]]:
    """When the daemon is up, return (tab-associated agent name, all agents)."""
    if not _daemon_available():
        return "", []
    from tak.ipc.client import send_request

    resp = _run_async(send_request("list_agents"))
    if not resp.success:
        return "", []
    agents = list(resp.data or [])
    agent_name = ""
    if session_id:
        for ag in agents:
            if session_id in ag.get("tabs", []):
                agent_name = ag["name"]
                break
    return agent_name, agents


@cli.command()
def info() -> None:
    """Show terminal environment and session details.

    Displays the current terminal driver, session ID, associated agent,
    daemon status, and relevant environment variables.
    """
    session_id = _detect_session_id()
    daemon_up = _daemon_available()
    agent_name, agents = _info_associated_agent_and_list(session_id)

    table = Table(title="tak info", show_header=False, box=None, padding=(0, 2))
    table.add_column("Key", style="cyan")
    table.add_column("Value")

    table.add_row("Terminal", os.environ.get("TERM_PROGRAM", "unknown"))
    table.add_row("Term version", os.environ.get("TERM_PROGRAM_VERSION", "--"))
    table.add_row("Shell", os.environ.get("SHELL", "unknown"))
    table.add_row("TERM", os.environ.get("TERM", "unknown"))
    table.add_row("Session ID", session_id or "(not detected)")
    table.add_row("Daemon", "running" if daemon_up else "not running")
    table.add_row("Associated agent", agent_name or "(none)")

    if daemon_up and agents:
        running = [a for a in agents if a.get("status") == "running"]
        table.add_row("Running agents", str(len(running)))
        table.add_row("Total agents", str(len(agents)))

    table.add_row("CWD", os.getcwd())

    console.print(table)


_MODE_CHOICES = ["ask", "plan", "agent"]


def _prompt_impl(
    query: tuple[str, ...],
    agent: str | None,
    mode: str | None,
) -> None:
    """Send a prompt to an agent (shared by ``prompt`` and ``ask`` commands)."""
    full_query = " ".join(query)

    if not _daemon_available():
        click.echo(f"Prompting: {full_query}")
        click.echo(_MSG_DAEMON_OFF_IT2)
        return

    from tak.ipc.client import send_request

    params: dict[str, object] = {"message": full_query, "cwd": os.getcwd()}
    if mode is not None:
        params["mode"] = mode
    if agent:
        params["agent"] = agent
    else:
        session_id = _detect_session_id()
        if session_id:
            params["session_id"] = session_id
        else:
            params["use_adhoc"] = True

    resp = _run_async(send_request("prompt", params))
    if resp.success:
        data = resp.data or {}
        click.echo(f"[{data.get('agent', '?')}] {data.get('response', '')}")
    else:
        click.echo(f"Error: {resp.error}", err=True)
        sys.exit(1)


@cli.command(name="prompt")
@click.argument("query", nargs=-1, required=True)
@click.option("--agent", "-a", default=None, help="Target a specific agent by name")
@click.option(
    "--mode", "-M",
    type=click.Choice(_MODE_CHOICES, case_sensitive=False),
    default=None,
    help="Session mode when a new ACP session is created (ask, plan, agent)",
)
def prompt_cmd(query: tuple[str, ...], agent: str | None, mode: str | None) -> None:
    """Send a prompt to an agent.

    Uses the agent associated with the current tab, or ad-hoc if none.
    Shorthand: tak p
    """
    _prompt_impl(query, agent, mode)


@cli.command(name="p", hidden=True)
@click.argument("query", nargs=-1, required=True)
@click.option("--agent", "-a", default=None, help="Target a specific agent by name")
@click.option(
    "--mode", "-M",
    type=click.Choice(_MODE_CHOICES, case_sensitive=False),
    default=None,
    help="Session mode when a new ACP session is created (ask, plan, agent)",
)
def prompt_short(query: tuple[str, ...], agent: str | None, mode: str | None) -> None:
    """Shorthand for 'tak prompt'."""
    _prompt_impl(query, agent, mode)


@cli.command(hidden=True)
@click.argument("query", nargs=-1, required=True)
@click.option("--agent", "-a", default=None, help="Target a specific agent by name")
@click.option(
    "--mode", "-M",
    type=click.Choice(_MODE_CHOICES, case_sensitive=False),
    default=None,
    help="Session mode when a new ACP session is created (ask, plan, agent)",
)
def ask(query: tuple[str, ...], agent: str | None, mode: str | None) -> None:
    """Send a prompt to an agent (alias for 'tak prompt')."""
    _prompt_impl(query, agent, mode)


@cli.group()
def session() -> None:
    """Manage agent conversation sessions."""


@session.command("end")
@click.argument("agent", required=False)
def session_end(agent: str | None) -> None:
    """End the ACP session for an agent (fresh conversation on next prompt).

    With no AGENT, uses the tab-associated agent or the ad-hoc agent.
    """
    if not _daemon_available():
        target = agent or "(default)"
        click.echo(f"Ending session for '{target}'...")
        click.echo(_MSG_DAEMON_OFF_IT2)
        return

    from tak.ipc.client import send_request

    params: dict[str, object] = {}
    if agent:
        params["agent"] = agent
    else:
        session_id = _detect_session_id()
        if session_id:
            params["session_id"] = session_id
        else:
            params["use_adhoc"] = True

    resp = _run_async(send_request("session_end", params))
    if resp.success:
        data = resp.data or {}
        click.echo(f"Session ended for agent '{data.get('agent', '?')}'.")
    else:
        click.echo(f"Error: {resp.error}", err=True)
        sys.exit(1)


@cli.command(name="agents")
@click.option("--provider", "-p", default=None, help="Filter by provider name")
@click.option(
    "--running", "running_only", is_flag=True, default=False,
    help="Show only running agents",
)
def list_agents(provider: str | None, running_only: bool) -> None:
    """List all managed agents with optional filters."""
    if not _daemon_available():
        click.echo("Running agents:")
        click.echo(_MSG_DAEMON_OFF_SHORT)
        return

    from tak.ipc.client import send_request

    params: dict[str, object] = {}
    if provider:
        params["provider"] = provider
    if running_only:
        params["running"] = True

    resp = _run_async(send_request("list_agents", params))
    if not resp.success:
        click.echo(f"Error: {resp.error}", err=True)
        sys.exit(1)

    agents = resp.data or []
    if not agents:
        click.echo("No agents found.")
        return

    table = Table(title="tak agents")
    table.add_column("Name", style="cyan")
    table.add_column("Provider")
    table.add_column("Model")
    table.add_column("Status", style="bold")
    table.add_column("Tabs")

    for ag in agents:
        model_display = ag.get("model") or "--"
        table.add_row(
            rich_escape(ag["name"]),
            rich_escape(ag["provider"]),
            rich_escape(model_display),
            ag["status"],
            ", ".join(ag.get("tabs", [])) or "--",
        )

    console.print(table)


@cli.command()
@click.argument("old_name")
@click.argument("new_name")
def rename(old_name: str, new_name: str) -> None:
    """Rename an agent."""
    if not _daemon_available():
        click.echo(f"Cannot rename '{old_name}' -- daemon not running.")
        return

    from tak.ipc.client import send_request

    resp = _run_async(send_request("rename_agent", {"old_name": old_name, "new_name": new_name}))
    if resp.success:
        data = resp.data or {}
        click.echo(f"Renamed '{data.get('old_name')}' → '{data.get('new_name')}'")
    else:
        click.echo(f"Error: {resp.error}", err=True)
        sys.exit(1)


@cli.command()
@click.argument("agent_name")
@click.option(
    "--session-id", "-s", default=None,
    help="iTerm2 session ID (defaults to $ITERM_SESSION_ID)",
)
def associate(agent_name: str, session_id: str | None) -> None:
    """Associate the current terminal tab with a named agent."""
    effective_session_id = session_id or _detect_session_id() or ""
    if not effective_session_id:
        click.echo(
            "Error: No session ID. Run this inside iTerm2 "
            "(needs $ITERM_SESSION_ID) or pass --session-id.",
            err=True,
        )
        sys.exit(1)

    if not _daemon_available():
        click.echo("Error: daemon not running.", err=True)
        sys.exit(1)

    from tak.ipc.client import send_request

    resp = _run_async(
        send_request("associate", {"agent": agent_name, "session_id": effective_session_id})
    )
    if resp.success:
        click.echo(f"Associated this tab with agent '{agent_name}'.")
    else:
        click.echo(f"Error: {resp.error}", err=True)
        sys.exit(1)


@cli.command()
@click.argument("agent_name")
@click.argument(
    "policy",
    type=click.Choice(_PERMISSION_CHOICES, case_sensitive=False),
)
def permissions(agent_name: str, policy: str) -> None:
    """Set the permission policy for a running agent.

    POLICY is one of: prompt, reject, auto-allow, yolo.
    """
    if policy == "yolo":
        click.echo(
            "Warning: yolo mode grants irrevocable per-tool permissions. "
            "Already-allowed tools cannot be revoked without restarting the agent.",
            err=True,
        )

    if not _daemon_available():
        click.echo("Error: daemon not running.", err=True)
        sys.exit(1)

    from tak.ipc.client import send_request

    resp = _run_async(
        send_request("set_permissions", {"agent": agent_name, "policy": policy})
    )
    if resp.success:
        data = resp.data or {}
        click.echo(f"Permission policy for '{agent_name}' set to '{data.get('policy')}'.")
    else:
        click.echo(f"Error: {resp.error}", err=True)
        sys.exit(1)


@cli.command()
@click.argument("name")
def switch(name: str) -> None:
    """Switch to the terminal tab of a named agent."""
    if not _daemon_available():
        click.echo(f"Cannot switch to '{name}' -- daemon not running.")
        return

    from tak.ipc.client import send_request

    resp = _run_async(send_request("switch", {"name": name}))
    if resp.success:
        click.echo(f"Switched to agent '{name}'.")
    else:
        click.echo(f"Error: {resp.error}", err=True)
        sys.exit(1)


@cli.command()
def menu() -> None:
    """Open the agent management TUI."""
    from tak.tui.app import run_app

    run_app()


# ---------------------------------------------------------------------------
# Scaffold commands
# ---------------------------------------------------------------------------


@cli.group()
def scaffold() -> None:
    """Generate standards files for a project."""


@scaffold.command("agents")
@click.option("--output", "-o", default="AGENTS.md", show_default=True, help="Output file path")
@click.option("--name", "-n", default=None, help="Project name (defaults to cwd name)")
@click.option("--desc", "-d", default="", help="One-sentence project description")
@click.option("--force", "-f", is_flag=True, help="Overwrite existing file")
def scaffold_agents(output: str, name: str | None, desc: str, force: bool) -> None:
    """Generate an AGENTS.md file for the current project."""
    from pathlib import Path

    from tak.scaffold.agents_md import generate_agents_md

    project_name = name or Path.cwd().name
    output_path = Path(output)

    try:
        stack = generate_agents_md(
            project_name=project_name,
            output=output_path,
            project_description=desc,
            force=force,
        )
        console.print(f"[green]Created[/green] {output_path}")
        console.print(f"  Detected stack: {stack.language}"
                      + (f" / {stack.framework}" if stack.framework else ""))
    except FileExistsError as exc:
        console.print(f"[red]Error:[/red] {exc}", highlight=False)
        raise SystemExit(1) from exc


@scaffold.command("rules")
@click.option(
    "--rules-dir",
    default=".cursor/rules",
    show_default=True,
    help="Directory to write rule files into",
)
def scaffold_rules(rules_dir: str) -> None:
    """Generate .cursor/rules/ structure for the current project."""
    from pathlib import Path

    from tak.scaffold.rules import generate_rules

    created, skipped = generate_rules(rules_dir=Path(rules_dir))
    for fname in created:
        console.print(f"[green]Created[/green] {rules_dir}/{fname}")
    for fname in skipped:
        console.print(f"[yellow]Skipped[/yellow] {rules_dir}/{fname} (already exists)")
    if not created and not skipped:
        console.print("[yellow]No rule files to generate.[/yellow]")


@scaffold.command("skills")
@click.option("--output", "-o", default="SKILL.md", show_default=True, help="Output file path")
@click.option("--name", "-n", default=None, help="Skill name")
@click.option("--desc", "-d", default=None, help="One-sentence skill description")
@click.option("--force", "-f", is_flag=True, help="Overwrite existing file")
def scaffold_skills(output: str, name: str | None, desc: str | None, force: bool) -> None:
    """Generate a SKILL.md file."""
    from pathlib import Path

    from tak.scaffold.skills import generate_skill_md

    skill_name = name or click.prompt("Skill name")
    skill_desc = desc or click.prompt("Skill description")
    output_path = Path(output)

    try:
        generate_skill_md(
            skill_name=skill_name,
            description=skill_desc,
            output=output_path,
            force=force,
        )
        console.print(f"[green]Created[/green] {output_path}")
    except FileExistsError as exc:
        console.print(f"[red]Error:[/red] {exc}", highlight=False)
        raise SystemExit(1) from exc


# ---------------------------------------------------------------------------
# New project command
# ---------------------------------------------------------------------------


@cli.group(name="new")
def new_group() -> None:
    """Create new projects and files from templates."""


def _prompt_new_project_fields(
    name: str,
    quick: bool,
    desc: str,
    language: str | None,
    framework: str | None,
    skill: bool,
) -> tuple[str, str | None, str | None, bool]:
    """Collect optional interactive fields for ``tak new project``."""
    if quick:
        return desc, language, framework, skill
    if not desc:
        desc = click.prompt("Project description", default=f"{name} project.")
    if not language:
        raw_language = click.prompt("Primary language", default="")
        language = raw_language.strip() or None
    if language and not framework:
        raw_framework = click.prompt("Framework (optional)", default="")
        framework = raw_framework.strip() or None
    if not skill:
        skill = click.confirm("Generate SKILL.md?", default=False)
    return desc, language, framework, skill


@new_group.command("project")
@click.argument("name")
@click.option("--quick", "-q", is_flag=True, help="Quick mode: skip interactive prompts")
@click.option("--desc", "-d", default="", help="One-sentence project description")
@click.option("--language", "-l", default=None, help="Primary language (e.g. Python, Rust)")
@click.option("--framework", default=None, help="Framework (e.g. FastAPI, React)")
@click.option("--skill", is_flag=True, help="Also generate a SKILL.md")
@click.option("--no-git", is_flag=True, help="Skip git init")
def new_project(
    name: str,
    quick: bool,
    desc: str,
    language: str | None,
    framework: str | None,
    skill: bool,
    no_git: bool,
) -> None:
    """Create a new project skeleton in a subdirectory named NAME."""
    import os
    from pathlib import Path

    from tak.scaffold.new_project import create_project

    parent_dir = Path(os.getcwd())

    desc, language, framework, skill = _prompt_new_project_fields(
        name, quick, desc, language, framework, skill,
    )

    try:
        result = create_project(
            name=name,
            parent_dir=parent_dir,
            description=desc,
            language=language,
            framework=framework,
            include_skill=skill,
            git=not no_git,
        )
    except FileExistsError as exc:
        console.print(f"[red]Error:[/red] {exc}", highlight=False)
        raise SystemExit(1) from exc

    project_dir: Path = result["project_dir"]  # type: ignore[assignment]
    files_created: list[str] = result["files_created"]  # type: ignore[assignment]
    git_initialized: bool = result["git_initialized"]  # type: ignore[assignment]

    console.print(f"\n[bold green]Created project:[/bold green] {project_dir}")
    for f in files_created:
        console.print(f"  [green]+[/green] {f}")
    if git_initialized:
        console.print("  [green]✓[/green] git init")
    elif not no_git:
        console.print("  [yellow]![/yellow] git init failed (is git installed?)")
    console.print(f"\nNext steps:\n  cd {name}")
    if not no_git:
        console.print("  git add .\n  git commit -m 'chore: initial scaffold'")


# ---------------------------------------------------------------------------
# Setup commands
# ---------------------------------------------------------------------------


@cli.group()
def setup() -> None:
    """Set up development environment components."""


@setup.command("iterm2")
@click.option("--dry-run", is_flag=True, help="Show what would happen without making changes")
def setup_iterm2_cmd(dry_run: bool) -> None:
    """Enable iTerm2 Python API and install the tak daemon."""
    from tak.setup.iterm2 import setup_iterm2

    ok = setup_iterm2(console, dry_run=dry_run)
    if not ok:
        sys.exit(1)


@setup.command("iterm2-pip")
@click.option("--dry-run", is_flag=True, help="Show what would happen without making changes")
def setup_iterm2_pip_cmd(dry_run: bool) -> None:
    """Install tak into iTerm2's bundled Python environment."""
    from tak.setup.iterm2 import setup_iterm2_pip

    ok = setup_iterm2_pip(console, dry_run=dry_run)
    if not ok:
        sys.exit(1)


@setup.command("fonts")
@click.option("--dry-run", is_flag=True, help="Show what would happen without making changes")
def setup_fonts_cmd(dry_run: bool) -> None:
    """Install JetBrains Mono Nerd Font."""
    from tak.setup.fonts import setup_fonts

    ok = setup_fonts(console, dry_run=dry_run)
    if not ok:
        sys.exit(1)


@setup.command("starship")
@click.option("--dry-run", is_flag=True, help="Show what would happen without making changes")
def setup_starship_cmd(dry_run: bool) -> None:
    """Install and configure Starship prompt."""
    from tak.setup.starship import setup_starship

    ok = setup_starship(console, dry_run=dry_run)
    if not ok:
        sys.exit(1)


@setup.command("shell")
@click.option("--dry-run", is_flag=True, help="Show what would happen without making changes")
def setup_shell_cmd(dry_run: bool) -> None:
    """Configure shell (.bashrc) with tak integrations."""
    from tak.setup.shell import setup_shell

    ok = setup_shell(console, dry_run=dry_run)
    if not ok:
        sys.exit(1)


@setup.command("profiles")
@click.option("--dry-run", is_flag=True, help="Show what would happen without making changes")
def setup_profiles_cmd(dry_run: bool) -> None:
    """Create iTerm2 profiles for agents."""
    from tak.setup.profiles import setup_profiles

    ok = setup_profiles(console, dry_run=dry_run)
    if not ok:
        sys.exit(1)


@setup.command("tak")
@click.option("--dry-run", is_flag=True, help="Show what would happen without making changes")
def setup_tak_cmd(dry_run: bool) -> None:
    """All-in-one opinionated setup (iterm2 + fonts + starship + shell + profiles)."""
    from tak.setup.tak_setup import setup_tak

    ok = setup_tak(console, dry_run=dry_run)
    if not ok:
        sys.exit(1)


if __name__ == "__main__":
    cli()
