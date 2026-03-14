"""CLI entry point for the `tak` command."""

from __future__ import annotations

import click


@click.group()
@click.version_option(package_name="terminal-agent-kit")
def cli() -> None:
    """Terminal Agent Kit (tak) -- Forging your terminal into an agentic environment."""


@cli.command()
@click.argument("provider", default="cursor-acp")
@click.option("--name", "-n", required=True, help="Name for this agent instance")
@click.option("--project", "-p", default=None, help="Project folder path")
def spawn(provider: str, name: str, project: str | None) -> None:
    """Spawn a new agent instance."""
    click.echo(f"Spawning agent '{name}' with provider '{provider}'...")
    if project:
        click.echo(f"  Project: {project}")
    click.echo("  [not yet implemented]")


@cli.command()
def status() -> None:
    """Show status of all running agents."""
    click.echo("Running agents:")
    click.echo("  [not yet implemented]")


@cli.command()
@click.argument("name")
def stop(name: str) -> None:
    """Stop a running agent."""
    click.echo(f"Stopping agent '{name}'...")
    click.echo("  [not yet implemented]")


@cli.command()
@click.argument("query", nargs=-1, required=True)
@click.option("--agent", "-a", default=None, help="Target a specific agent by name")
def ask(query: tuple[str, ...], agent: str | None) -> None:
    """Send a question to an agent."""
    full_query = " ".join(query)
    target = agent or "default"
    click.echo(f"Asking [{target}]: {full_query}")
    click.echo("  [not yet implemented]")


@cli.group()
def scaffold() -> None:
    """Generate standards files for a project."""


@scaffold.command("agents")
@click.option("--output", "-o", default="AGENTS.md", help="Output file path")
def scaffold_agents(output: str) -> None:
    """Generate an AGENTS.md file."""
    click.echo(f"Generating {output}...")
    click.echo("  [not yet implemented]")


@scaffold.command("rules")
def scaffold_rules() -> None:
    """Generate .cursor/rules/ structure."""
    click.echo("Generating .cursor/rules/...")
    click.echo("  [not yet implemented]")


@scaffold.command("skills")
def scaffold_skills() -> None:
    """Generate SKILL.md file."""
    click.echo("Generating SKILL.md...")
    click.echo("  [not yet implemented]")


@cli.group()
def setup() -> None:
    """Set up development environment components."""


@setup.command("starship")
def setup_starship() -> None:
    """Install and configure Starship prompt."""
    click.echo("Setting up Starship...")
    click.echo("  [not yet implemented]")


@setup.command("fonts")
def setup_fonts() -> None:
    """Install JetBrains Mono Nerd Font."""
    click.echo("Installing JetBrains Mono Nerd Font...")
    click.echo("  [not yet implemented]")


@setup.command("profiles")
def setup_profiles() -> None:
    """Create iTerm2 profiles for agents."""
    click.echo("Creating iTerm2 profiles...")
    click.echo("  [not yet implemented]")


if __name__ == "__main__":
    cli()
