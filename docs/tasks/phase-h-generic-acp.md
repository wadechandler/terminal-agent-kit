# Phase H: Generic ACP Provider

## Goal

Refactor `CursorACPProvider` into a generic `ACPProvider` that works with
any ACP-compliant agent (Cursor, Goose, Claude via adapter), and create a
separate `TerminalSessionProvider` for agents that run in their own tab.

## Context

ACP (Agent Client Protocol) is becoming a cross-agent standard:
- **Cursor CLI**: native ACP via `cursor agent acp`
- **Goose**: migrating to ACP as its sole protocol (`goose-acp` crate)
- **Claude Code**: via `claude-agent-acp` adapter from Zed Industries

The current `CursorACPProvider` is already 90% generic -- the JSON-RPC
session flow, permission handling, and streaming are all ACP-standard.
The only Cursor-specific part is the spawn command (`cursor agent acp`).

Terminal-mode agents (Claude Code native, Goose interactive) don't use
ACP -- they run in their own tab with their own TUI. They need a different
provider that manages lifecycle only.

## Prerequisites

**Phase F must be completed first.** This phase refactors the ACP session
code that Phase F builds.

## Files to Read First

- `src/tak/providers/cursor_acp.py` -- current provider (will be refactored)
- `src/tak/providers/base.py` -- `BaseProvider`, `InteractionModel`
- `src/tak/providers/acp_session.py` -- ACP session manager (built in Phase F)
- `src/tak/core/agent_manager.py` -- `AgentHandle`
- `docs/research/acp-ecosystem.md` -- protocol details, agent landscape
- `AGENTS.md` -- conventions

## What to Build

### 1. Rename/refactor `cursor_acp.py` → `acp.py`

Create `src/tak/providers/acp.py` with a generic `ACPProvider`:

```python
class ACPProvider(BaseProvider):
    """Generic ACP provider for any ACP-compliant agent."""

    def __init__(self, name: str, command: list[str], auth_method: str = "env"):
        # command is the base command, e.g. ["cursor", "agent", "acp"]
        # or ["goose", "acp"] or ["claude-agent-acp"]
        # auth_method: "env" (CURSOR_API_KEY), "login" (cursor_login), "none"
```

Agent-specific spawn flags come from config, not hardcoded:

```yaml
# ~/.tak/agents.yaml
providers:
  cursor-acp:
    command: ["cursor", "agent", "acp"]
    auth_method: login
  goose-acp:
    command: ["goose", "acp"]
    auth_method: env
  claude-acp:
    command: ["claude-agent-acp"]
    auth_method: env
```

### 2. Create `src/tak/providers/terminal_session.py`

```python
class TerminalSessionProvider(BaseProvider):
    """Provider for agents that run in their own terminal tab."""

    @property
    def interaction_model(self) -> InteractionModel:
        return InteractionModel.TERMINAL
```

This provider:
- Spawns the agent command in a new iTerm2 tab (via the driver)
- Does NOT do JSON-RPC -- the agent has its own TUI
- `send()` raises NotImplementedError (user talks to agent directly)
- `stop()` sends SIGTERM to the process
- Tracks which tab the agent is in

### 3. Keep `cursor_acp.py` as a thin alias

For backwards compatibility:
```python
# src/tak/providers/cursor_acp.py
from tak.providers.acp import ACPProvider

class CursorACPProvider(ACPProvider):
    """Cursor-specific ACP provider. Convenience alias."""
    def __init__(self, command: str = "cursor"):
        super().__init__(
            name="Cursor (ACP)",
            command=[command, "agent", "acp"],
            auth_method="login",
        )
```

### 4. Update daemon to register providers from config

In `src/tak/drivers/iterm2/daemon.py`, load provider definitions from
config instead of hardcoding `CursorACPProvider`.

### 5. Update config schema

Add provider definitions to `config/default.yaml` (or create it if needed).

## Tests to Write

- `tests/providers/test_acp.py`:
  - Test generic ACPProvider with different command lists
  - Test spawn builds correct command
  - Test list_models calls the right command
- `tests/providers/test_terminal_session.py`:
  - Test interaction_model is TERMINAL
  - Test send raises NotImplementedError
  - Test stop terminates process
- Ensure existing tests still pass (CursorACPProvider backwards compat)

## Acceptance Criteria

- `ruff check src/ tests/` zero errors
- All tests pass
- `ACPProvider` works with arbitrary command lists
- `TerminalSessionProvider` has TERMINAL interaction model
- `CursorACPProvider` still works as before (backwards compat)
- Daemon loads providers from config

## Dependencies

- **Requires Phase F to be complete** (uses `acp_session.py`)

---

## Agent Prompt

```
Read AGENTS.md for project conventions, then read these files:
- src/tak/providers/cursor_acp.py
- src/tak/providers/base.py
- src/tak/providers/acp_session.py (built in Phase F)
- src/tak/core/agent_manager.py
- docs/research/acp-ecosystem.md

Then read docs/tasks/phase-h-generic-acp.md for the full task spec.

Implement everything: generic ACPProvider, TerminalSessionProvider,
CursorACPProvider backwards-compat alias, config-driven provider loading
in the daemon, and all tests. Run ruff check and pytest after each piece.
Do not stop until ruff check src/ tests/ shows zero errors and all tests pass.
```
