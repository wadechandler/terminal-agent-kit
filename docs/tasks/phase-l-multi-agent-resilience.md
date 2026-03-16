# Phase K: Multi-Agent & Resilience

## Goal

Harden the agent management layer to support multiple simultaneous agents
with named instances, automatic restart recovery after iTerm2 restarts,
and ad-hoc mode for quick questions without a project folder.

## Context

The current `AgentManager` already supports multiple agents by name, but
several pieces are missing for this to be production-quality:

1. **Named instances of the same provider**: You can spawn `cursor-docs`
   and `cursor-myapp` today, but there's no validation, naming convention
   enforcement, or UI to manage conflicts.

2. **Restart recovery**: `StateManager` at `src/tak/core/state.py` can
   save/load agent state to `~/.tak/state.yaml`, but the daemon doesn't
   call `load()` on startup to restore agents. When iTerm2 restarts, all
   agents are lost.

3. **Ad-hoc mode**: Currently `spawn()` requires a provider and name. The
   user wants `tak ask "how do I fix this brew error?"` to just work
   without spawning a named agent first -- a lightweight, unnamed agent for
   quick questions.

## Files to Read First

- `src/tak/core/agent_manager.py` -- AgentHandle, spawn/stop/list
- `src/tak/core/state.py` -- StateManager save/load/clear
- `src/tak/core/session_registry.py` -- tab-agent associations
- `src/tak/ipc/server.py` -- IPC dispatch
- `src/tak/drivers/iterm2/daemon.py` -- daemon startup
- `src/tak/cli/main.py` -- CLI commands
- `AGENTS.md` -- project conventions

## What to Build

### 1. Multi-Agent Named Instances

**In `src/tak/core/agent_manager.py`:**

- Add name validation: names must be lowercase alphanumeric + hyphens,
  3-50 chars, no leading/trailing hyphens
- Add `rename()` method
- Add `get_by_provider()` method to list agents of a given provider type
- Emit events (or call hooks) on state changes so the daemon can update
  session variables and persist state

**In the IPC server:**

- Add `rename_agent` method
- Add `list_agents` filtering by provider or status

**In the CLI:**

- `tak agents --provider cursor-acp` -- filter by provider
- `tak agents --running` -- show only running agents
- `tak rename old-name new-name`

### 2. Restart Recovery

**In `src/tak/drivers/iterm2/daemon.py` (daemon startup):**

1. After creating AgentManager, call `StateManager.load()`
2. For each saved agent in state:
   - Look up the provider
   - Call `provider.spawn()` with the saved parameters
   - Re-associate with tabs if the tab session IDs still exist
   - If a tab no longer exists, log a warning and skip association
3. After recovery, call `StateManager.save()` to update state with any
   changes (e.g., tabs that disappeared)

**In `src/tak/core/agent_manager.py`:**

- Add `restore()` method that takes saved state dict and re-creates
  AgentHandles, calling provider.spawn() for each
- Handle failures gracefully -- if one agent fails to restore, log the
  error and continue with others

**In `src/tak/core/state.py`:**

- Save model name in state (already done, but verify)
- Add timestamp to state file for debugging
- Add `auto_save()` that the manager calls on every state change

**State auto-persistence:**

- AgentManager calls `StateManager.save()` after every spawn/stop
- Daemon sets up a periodic save (every 30s) as a safety net
- Clean shutdown calls save() + clear() on the way out

### 3. Ad-Hoc Mode

A lightweight "default agent" that gets auto-spawned for quick questions.

**New: `src/tak/core/adhoc.py`:**

```python
class AdHocManager:
    """Manages a lightweight default agent for quick questions."""

    async def ensure_agent(self) -> AgentHandle:
        """Return the ad-hoc agent, spawning it if needed."""
        # Looks for an agent named "_adhoc"
        # If not running, spawns one with default provider + no project path
        # Returns the handle

    async def ask(self, query: str) -> str:
        """Send a question to the ad-hoc agent."""
        agent = await self.ensure_agent()
        # Route through provider.send()
```

**In the daemon:**

- Initialize an `AdHocManager` alongside the `AgentManager`
- AdHocManager uses the same AgentManager internally but with a reserved
  `_adhoc` name prefix

**In the CLI:**

- `tak ask "question"` without `--agent` uses the ad-hoc agent
- First use auto-spawns with the default provider from config
- Config option `default_provider` in `config/default.yaml`

**In `config/default.yaml`:**

```yaml
adhoc:
  provider: cursor-acp
  model: null  # uses provider default
  auto_stop_after: 300  # seconds of inactivity before auto-stopping
```

## Tests to Write

- `tests/core/test_agent_manager.py` (extend existing):
  - Test name validation (valid names, invalid names)
  - Test rename
  - Test get_by_provider filtering
  - Test spawn/stop triggers state save

- `tests/core/test_state.py` (extend existing):
  - Test save includes model and timestamp
  - Test load with missing/corrupted file
  - Test round-trip: save then load produces equivalent state

- `tests/core/test_adhoc.py` (new):
  - Test ensure_agent spawns on first call
  - Test ensure_agent returns existing on second call
  - Test ask routes through provider
  - Test auto-stop after inactivity

- `tests/core/test_restart_recovery.py` (new):
  - Test daemon startup with saved state restores agents
  - Test recovery with missing tab handles gracefully
  - Test recovery with failed provider spawn continues with others
  - Test state file updated after recovery

- `tests/ipc/test_server.py` (extend):
  - Test rename_agent method
  - Test list_agents with filters

## Acceptance Criteria

- `ruff check src/ tests/` passes with zero errors
- All tests pass
- `tak spawn` with invalid name gives clear error
- `tak rename` works
- Daemon restores agents from state.yaml on startup
- `tak ask "question"` works without prior spawn (ad-hoc mode)
- State file updated on every spawn/stop

## Dependencies

- Phase F recommended (for ad-hoc mode to actually talk to an agent via
  ACP) but not strictly required. The ad-hoc manager can be wired to the
  existing basic `send()` method.
- Can run in parallel with Phase J (Scaffold & Project Creation).

---

## Agent Prompt

```
Read AGENTS.md for project conventions, then read these files:
- src/tak/core/agent_manager.py
- src/tak/core/state.py
- src/tak/core/session_registry.py
- src/tak/ipc/server.py
- src/tak/drivers/iterm2/daemon.py
- src/tak/cli/main.py
- config/default.yaml

Then read docs/tasks/phase-l-multi-agent-resilience.md for the full task spec.

Implement everything: name validation and rename in AgentManager, restart
recovery in the daemon, AdHocManager for tak ask without prior spawn,
state auto-persistence, CLI extensions, and all tests. Run ruff check
and pytest after each major piece. Do not stop until ruff check src/ tests/
shows zero errors and all tests pass.
```
