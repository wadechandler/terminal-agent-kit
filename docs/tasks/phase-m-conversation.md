# Phase M: Conversation and Context

## Goal

Make `tak ask` conversational: persistent ACP sessions across prompts, working
directory awareness, mode selection, and session reset. This is Level 1 of the
graduated conversation design (ADR-016).

## Context

Currently `tak ask` is one-shot: the CLI sends a single prompt via IPC, the
daemon forwards it to the ACP provider, collects the full response, and returns
it. Each call is independent -- no conversation history, no CWD context, no
mode control. This makes the "poor man's Warp" use case impossible: users need
to ask follow-up questions, have the agent remember prior context, and control
whether the agent is in ask/plan/agent mode.

### Design (from ADR-016)

- The daemon keeps ACP sessions alive per agent (not per `tak ask` call).
- Subsequent `tak ask` calls look up the existing session via agent association
  and send a new `session/prompt` within it.
- The agent accumulates conversation history across prompts.
- `tak ask --mode ask|plan|agent` sets the session mode on creation.
- `tak session end [agent]` explicitly closes a session for a fresh start.
- Each prompt includes the caller's CWD as context.

## Files to Read First

- `src/tak/providers/acp_session.py` -- `ACPSessionManager` (manages JSON-RPC lifecycle)
- `src/tak/providers/acp.py` -- `ACPProvider.send()` and `send_streaming()`
- `src/tak/ipc/server.py` -- `IPCServer` dispatch including the `ask` method
- `src/tak/ipc/client.py` -- `send_request()` used by the CLI
- `src/tak/cli/main.py` -- `ask` command implementation
- `src/tak/drivers/iterm2/daemon.py` -- daemon entry point, AdHocManager setup
- `src/tak/core/agent_bus.py` -- `BusMessage` and `BusResponse`
- `docs/research/architecture-decisions.md` -- ADR-016

## What to Build

### 1. CWD in IPC Requests

The `tak ask` CLI command should include the caller's working directory in the
IPC request so the agent knows where the user is.

**`src/tak/cli/main.py`** -- `ask` command:
- Add `os.getcwd()` to the params dict as `"cwd"`.

**`src/tak/ipc/server.py`** -- `ask` handler:
- Accept the `cwd` parameter and pass it through to the provider.

**`src/tak/core/agent_bus.py`** -- `BusMessage`:
- Add an optional `cwd: str | None` field to `BusMessage`.

**`src/tak/providers/acp.py`** -- `ACPProvider.send()`:
- When CWD is provided, prepend it to the prompt text as context, e.g.:
  `"[Working directory: /Users/me/project]\n\n{user_prompt}"`.

### 2. Session Persistence in the Daemon

The daemon should keep ACP sessions alive per agent rather than creating a new
session for each `tak ask` call.

**`src/tak/drivers/iterm2/daemon.py`**:
- Add a `_sessions: dict[str, ACPSessionManager]` mapping agent name to active
  session.
- When `ask` is called for an agent that already has a session, reuse it by
  calling `session.prompt()` instead of creating a new session.
- When an agent is stopped, close and remove its session.
- On daemon shutdown, close all sessions.

**`src/tak/providers/acp.py`** -- `ACPProvider`:
- Add a `get_session(agent_name: str) -> ACPSessionManager | None` method.
- Add a `close_session(agent_name: str) -> None` method.
- The `send()` method should check for an existing session before creating one.

### 3. Mode Selection

Users should be able to control the ACP session mode.

**`src/tak/cli/main.py`** -- `ask` command:
- Add `--mode` / `-M` option with choices `ask`, `plan`, `agent`.
- Default to `None` (let the provider use its default).
- Include `mode` in the IPC params.

**`src/tak/ipc/server.py`** -- `ask` handler:
- Pass `mode` through to the provider.

**`src/tak/providers/acp_session.py`** -- `ACPSessionManager.new_session()`:
- Already accepts a `mode` parameter; ensure it flows through.

### 4. Session Reset Command

**`src/tak/cli/main.py`**:
- Add a `session` group with an `end` subcommand:
  `tak session end [AGENT]` -- closes the ACP session for the named agent
  (or the ad-hoc agent if no name given), forcing a fresh session on next
  `tak ask`.

**`src/tak/ipc/server.py`**:
- Add a `session_end` handler that calls `provider.close_session(agent_name)`.

### 5. Tests

**`tests/cli/test_cli.py`**:
- Test `tak ask` includes CWD in params.
- Test `--mode` flag is passed through.
- Test `tak session end` command.

**`tests/ipc/test_server.py`**:
- Test `ask` handler passes CWD.
- Test `ask` handler passes mode.
- Test `session_end` handler.

**`tests/providers/test_acp.py`**:
- Test session reuse (second `send()` call reuses existing session).
- Test `close_session()` clears the session.
- Test CWD is prepended to prompt text.

**`tests/core/test_agent_bus.py`**:
- Test `BusMessage` with `cwd` field.

## Acceptance Criteria

1. `tak ask what files are here` sends `os.getcwd()` in the IPC request; the
   agent receives the CWD as context.
2. Two consecutive `tak ask` calls to the same agent reuse the same ACP session;
   the agent sees both prompts in conversation history.
3. `tak ask --mode plan "refactor auth"` creates a session in plan mode.
4. `tak session end my-agent` closes the session; the next `tak ask` creates
   a fresh session.
5. All existing tests continue to pass (357+).
6. `ruff check` passes with zero errors.
7. Manifest updated to mark phase-m tasks as done.

## Agent Prompt

Use this prompt to kick off a fresh agent session for this phase:

> Read `docs/tasks/phase-m-conversation.md` for the full spec. This phase adds
> session persistence, CWD awareness, mode selection, and session reset to
> `tak ask`. Read the "Files to Read First" section, then implement each item
> in "What to Build" in order. Run `ruff check src/ tests/` and `pytest -q`
> after each change. Update `docs/tasks/manifest.yaml` phase-m status to `done`
> when all acceptance criteria pass.
