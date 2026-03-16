"""CLI entry point for the ``tak`` command."""

from __future__ import annotations

import asyncio
import sys

import click
from rich.console import Console
from rich.table import Table

console = Console()


def _run_async(coro):  # type: ignore[no-untyped-def]
    """Run an async coroutine from synchronous Click commands."""
    return asyncio.run(coro)


def _daemon_available() -> bool:
    """Check whether the tak daemon socket exists."""
    from tak.ipc.client import DEFAULT_SOCKET_PATH

    return DEFAULT_SOCKET_PATH.exists()


# ---------------------------------------------------------------------------
# Root group
# ---------------------------------------------------------------------------


@click.group()
@click.version_option(package_name="terminal-agent-kit")
def cli() -> None:
    """Terminal Agent Kit (tak) -- Forging your terminal into an agentic environment."""


# ---------------------------------------------------------------------------
# Agent management commands
# ---------------------------------------------------------------------------


@cli.command()
@click.argument("provider", default="cursor-acp")
@click.option("--name", "-n", required=True, help="Name for this agent instance")
@click.option("--project", "-p", default=None, help="Project folder path")
@click.option("--model", "-m", default=None, help="Model name (e.g. claude-sonnet-4)")
def spawn(provider: str, name: str, project: str | None, model: str | None) -> None:
    """Spawn a new agent instance."""
    if not _daemon_available():
        click.echo(f"Spawning agent '{name}' with provider '{provider}'...")
        if project:
            click.echo(f"  Project: {project}")
        if model:
            click.echo(f"  Model: {model}")
        click.echo("  [daemon not running -- start iTerm2 with tak daemon]")
        return

    from tak.ipc.client import send_request

    params = {"name": name, "provider": provider}
    if project:
        params["project_path"] = project
    if model:
        params["model"] = model

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
        click.echo("  [daemon not running]")
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
        table.add_row(
            agent["name"],
            agent["provider"],
            agent.get("model") or "--",
            agent["status"],
            ", ".join(agent.get("tabs", [])) or "--",
        )

    console.print(table)


@cli.command()
@click.argument("name")
def stop(name: str) -> None:
    """Stop a running agent."""
    if not _daemon_available():
        click.echo(f"Stopping agent '{name}'...")
        click.echo("  [daemon not running]")
        return

    from tak.ipc.client import send_request

    resp = _run_async(send_request("stop", {"name": name}))
    if resp.success:
        click.echo(f"Agent '{name}' stopped.")
    else:
        click.echo(f"Error: {resp.error}", err=True)
        sys.exit(1)


@cli.command()
@click.argument("query", nargs=-1, required=True)
@click.option("--agent", "-a", default=None, help="Target a specific agent by name")
def ask(query: tuple[str, ...], agent: str | None) -> None:
    """Send a question to an agent (uses ad-hoc agent if --agent is omitted)."""
    full_query = " ".join(query)

    if not _daemon_available():
        click.echo(f"Asking: {full_query}")
        click.echo("  [daemon not running -- start iTerm2 with tak daemon]")
        return

    from tak.ipc.client import send_request

    params: dict[str, object] = {"message": full_query}
    if agent:
        params["agent"] = agent
    else:
        params["use_adhoc"] = True

    resp = _run_async(send_request("ask", params))
    if resp.success:
        data = resp.data or {}
        click.echo(f"[{data.get('agent', '?')}] {data.get('response', '')}")
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
        click.echo("  [daemon not running]")
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
        table.add_row(
            ag["name"],
            ag["provider"],
            ag.get("model") or "--",
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

    if not quick:
        if not desc:
            desc = click.prompt("Project description", default=f"{name} project.")
        if not language:
            language = click.prompt("Primary language", default="")
            language = language.strip() or None
        if language and not framework:
            framework = click.prompt("Framework (optional)", default="")
            framework = framework.strip() or None
        if not skill:
            skill = click.confirm("Generate SKILL.md?", default=False)

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
