# AGENTS.md - Terminal Agent Kit (tak)

## Project Overview

Terminal Agent Kit (tak) is a Python framework for embedding, managing, and
orchestrating AI agents within terminal environments -- for coding, system
management, workflows, and more. It provides a core agent management layer with
terminal-specific drivers, starting with Cursor (via ACP) on iTerm2 for macOS.

## Tech Stack

- **Language**: Python 3.11+
- **Async**: asyncio (required by iTerm2 Python API)
- **CLI Framework**: Click
- **Terminal Output**: Rich
- **TUI Framework**: Textual (built on Rich; provides widgets, reactive data, CSS-like styling)
- **Configuration**: YAML (PyYAML)
- **iTerm2 Integration**: iterm2 Python package (websocket-based API)
- **Agent Communication**: JSON-RPC 2.0 over stdio (Cursor ACP), generic stdio
- **Build System**: Hatchling (PEP 517 build backend only; the full Hatch CLI is
  not used). Build with `python -m build` or `pip install -e .`.
- **Linting**: Ruff
- **Type Checking**: mypy (strict mode)
- **Testing**: pytest + pytest-asyncio

## Architecture

The codebase follows a core/driver split:

- `src/tak/core/` -- Terminal-agnostic logic. Agent lifecycle management, message
  routing (agent bus), session registry (tab-agent associations), state persistence,
  and configuration loading. This code has NO terminal-specific imports.
- `src/tak/providers/` -- Agent protocol implementations. Each provider knows how
  to spawn, communicate with, and stop a specific type of agent (Cursor via ACP,
  Claude Code via stdio, direct LLM API calls, etc.). Providers implement the
  abstract base in `base.py`.
- `src/tak/drivers/` -- Terminal-specific integrations. Each driver implements a
  common interface for terminal operations (list sessions, inject text, set variables,
  register triggers). The iTerm2 driver uses the iterm2 Python API. Future drivers
  for Kitty, tmux, WezTerm.
- `src/tak/tui/` -- Textual-based terminal UI. `TakApp` is the agent dashboard launched
  by `tak menu`. `AgentTable` polls the daemon via IPC and renders the live agent roster.
  `tak.tcss` holds the dark-theme stylesheet.
- `src/tak/ipc/` -- Daemon-CLI communication. Unix socket with length-prefixed JSON
  protocol. `server.py` runs in the daemon; `client.py` is used by the CLI.
- `src/tak/scaffold/` -- Generators for standards files (AGENTS.md, .cursor/rules,
  SKILL.md). Template-driven.
- `src/tak/setup/` -- Environment bootstrap commands. Idempotent setup for iTerm2 API,
  JetBrains Mono Nerd Font, Starship prompt, shell config, and iTerm2 profiles.
- `src/tak/cli/` -- The `tak` CLI command. Uses Click. Delegates to core.

## Coding Conventions

Follow the [Google Python Style Guide](https://google.github.io/styleguide/pyguide.html)
as the authoritative reference for code style. Project-specific overrides and
clarifications below.

- Line length is 100 (project override; Google default is 80).
- All async code uses `async`/`await` with asyncio. No threads unless unavoidable.
- Type hints on all public functions. mypy strict mode must pass.
- Ruff enforces style automatically (including Google-style docstrings via pydocstyle
  `D` rules). Run `ruff check` before considering code complete.
- No wildcard imports. Explicit is better than implicit.
- Prefer composition over inheritance for providers and drivers.
- Configuration is always loaded from YAML files, never hardcoded.
- **Documentation maintenance**: When adding, removing, or modifying CLI commands,
  subcommands, options, or parameters, update the corresponding documentation in the
  same change set. This includes: README.md (CLI Reference section), Click help strings
  in `src/tak/cli/main.py`, and any affected `docs/` files. A change that alters the
  user-facing CLI surface without updating documentation is incomplete.

## Dependencies

When adding or updating a dependency:

- **Check for CVEs**: Search the [MITRE CVE database](https://cve.mitre.org/) and
  [NVD](https://nvd.nist.gov/) for known vulnerabilities before adopting any package.
  Do not add a dependency with unpatched critical or high-severity CVEs.
- **Verify maintenance health**: The package must have recent commits, responsive
  maintainers, and a bus factor > 1. Avoid abandoned or single-maintainer packages
  for critical functionality.
- **Use the latest stable version**: Always specify the latest stable release available
  at the time of addition. Do not add an outdated version when a newer stable release
  exists — search PyPI or the package's release page to confirm. For example, if a
  library is at 4.1, do not add 3.9.
- **Pin minimum versions explicitly**: Use `>=X.Y` lower bounds that reflect the
  actual version you verified. Do not guess version numbers — look them up.

## Docstring Style

Use Google-style docstrings on all public modules, classes, and functions. Enforced
by Ruff pydocstyle (`D` rules) with `convention = "google"`.

```python
def route(self, message: BusMessage) -> BusResponse:
    """Route a message to the appropriate agent and return the response.

    Args:
        message: The incoming bus message with session and text.

    Returns:
        A BusResponse containing the agent's reply.

    Raises:
        ValueError: If no agent is found for the session.
    """
```

## File Naming

- Snake_case for all Python files.
- Tests mirror source structure: `tests/core/test_agent_manager.py` tests
  `src/tak/core/agent_manager.py`.

## Key Design Decisions

- **Two interaction models**: `tak` (CLI command, works anywhere) and `@tak`/`@ai`
  (terminal-intercepted, context-aware, iTerm2 daemon required).
- **N agents of any type**: Multiple instances of the same agent type supported,
  each with a user-assigned name and project path.
- **State persistence**: Agent state written to `~/.tak/state.yaml` for restart
  recovery.
- **Provider protocol**: Cursor CLI uses ACP (JSON-RPC 2.0 over stdio). Other
  agents use generic stdio or direct HTTP APIs.
- **Configurable prefixes**: `@ai`, `@tak`, `??` are defaults, all user-configurable
  via `~/.tak/config.yaml`.

## Project Status

See [docs/PROJECT-STATUS.md](docs/PROJECT-STATUS.md) for current project state,
priorities, and ADR summaries. See [docs/tasks/manifest.yaml](docs/tasks/manifest.yaml)
for authoritative phase and task tracking.
