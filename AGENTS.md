# AGENTS.md - Terminal Agent Kit (tak)

## Project Overview

Terminal Agent Kit (tak) is a Python framework for embedding and managing AI coding
agents within terminal environments. It provides a core agent management layer with
terminal-specific drivers, starting with iTerm2 on macOS.

## Tech Stack

- **Language**: Python 3.11+
- **Async**: asyncio (required by iTerm2 Python API)
- **CLI Framework**: Click
- **Terminal Output**: Rich
- **Configuration**: YAML (PyYAML)
- **iTerm2 Integration**: iterm2 Python package (websocket-based API)
- **Agent Communication**: JSON-RPC 2.0 over stdio (Cursor ACP), generic stdio
- **Build System**: Hatch/Hatchling
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
- `src/tak/scaffold/` -- Generators for standards files (AGENTS.md, .cursor/rules,
  SKILL.md). Template-driven.
- `src/tak/cli/` -- The `tak` CLI command. Uses Click. Delegates to core.

## Coding Conventions

- All async code uses `async`/`await` with asyncio. No threads unless unavoidable.
- Type hints on all public functions. mypy strict mode must pass.
- Ruff for linting and formatting. Line length 100.
- No wildcard imports. Explicit is better than implicit.
- Prefer composition over inheritance for providers and drivers.
- Configuration is always loaded from YAML files, never hardcoded.
- All dependencies must be checked for known CVEs before adoption.
- Prefer dependencies with healthy maintenance (bus factor > 1, recent commits).

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
