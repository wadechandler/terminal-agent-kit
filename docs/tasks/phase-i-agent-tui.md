# Phase I: Agent Management TUI

## Goal

Build a Textual-based terminal UI that shows a live dashboard of all
managed agents with keyboard controls for spawn, stop, switch, and
permission approval. Launched via `tak menu` or the `tak_agent_menu()` RPC.

## Context

The TUI is the primary visual management interface for tak. It runs in
a terminal (split pane, dedicated tab, or standalone) and provides a
richer experience than the CLI commands.

Textual is the TUI framework from the creators of Rich (already a
dependency). It provides widgets, reactive data binding, CSS-like styling,
and mouse support.

## Prerequisites

**Phase F should be complete** so the TUI can display permission requests.
Phase G and H are not required.

## Files to Read First

- `src/tak/cli/main.py` -- `tak menu` command to wire up
- `src/tak/ipc/client.py` -- how CLI talks to daemon
- `src/tak/ipc/protocol.py` -- request/response format
- `src/tak/core/agent_manager.py` -- `AgentHandle`, `AgentStatus`
- `AGENTS.md` -- conventions

## What to Build

### 1. Add Textual dependency

In `pyproject.toml`, add to dependencies:
```
"textual>=3.0",
```
Look up the latest stable version on PyPI first. Do not guess.

### 2. Create `src/tak/tui/__init__.py` (empty)

### 3. Create `src/tak/tui/app.py` -- main TUI application

```python
class TakApp(textual.app.App):
    """Agent management dashboard."""
    CSS_PATH = "tak.tcss"
    BINDINGS = [
        ("q", "quit", "Quit"),
        ("s", "spawn", "Spawn"),
        ("x", "stop_agent", "Stop"),
        ("g", "switch_tab", "Go to tab"),
        ("r", "refresh", "Refresh"),
    ]
```

Layout:
- Header: "tak -- Agent Dashboard"
- Main area: DataTable of agents (name, provider, model, status, tabs)
- Footer: keybinding help bar
- Optionally: a log panel showing recent agent activity

### 4. Create `src/tak/tui/tak.tcss` -- stylesheet

Style the app with a distinctive look. Dark theme, colored status
indicators (green=running, red=error, grey=stopped).

### 5. Create `src/tak/tui/widgets.py` -- custom widgets if needed

An `AgentTable` widget that polls the daemon via IPC and updates
the DataTable reactively.

### 6. Wire into CLI

Update `tak menu` in `src/tak/cli/main.py`:
```python
@cli.command()
def menu() -> None:
    from tak.tui.app import TakApp
    app = TakApp()
    app.run()
```

### 7. Wire into RPC

The `tak_agent_menu()` RPC in `src/tak/drivers/iterm2/rpc.py` could
launch the TUI in a split pane:
```python
new_session = await session.async_split_pane(vertical=False)
await new_session.async_send_text("tak menu\n")
```

## Tests to Write

Textual has a built-in testing framework (`app.run_test()`):

- `tests/tui/test_app.py`:
  - Test app starts and renders without errors
  - Test agent table displays mock data
  - Test keybindings trigger correct actions
  - Test quit binding exits cleanly

## Acceptance Criteria

- `ruff check src/ tests/` zero errors
- All tests pass
- `tak menu` launches the TUI
- TUI displays agent table with live data from daemon (or "daemon not
  running" message if no daemon)
- Keyboard shortcuts work (spawn prompts for input, stop confirms, etc.)
- App exits cleanly on `q`

## Dependencies

- Phase F recommended (for permission display) but not strictly required.
  The TUI can show agents and their status without the ACP relay.
- Textual package must be added to pyproject.toml.

---

## Agent Prompt

```
Read AGENTS.md for project conventions, then read these files:
- src/tak/cli/main.py
- src/tak/ipc/client.py
- src/tak/ipc/protocol.py
- src/tak/core/agent_manager.py
- pyproject.toml

Then read docs/tasks/phase-i-agent-tui.md for the full task spec.

Implement everything: add Textual dependency (look up latest version on
PyPI), create the src/tak/tui/ package with app, stylesheet, and widgets,
wire into CLI and RPC, and write Textual tests. Run ruff check and pytest
after each piece. Do not stop until ruff check src/ tests/ shows zero
errors and all tests pass.
```
