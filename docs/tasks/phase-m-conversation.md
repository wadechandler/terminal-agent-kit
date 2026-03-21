# Phase M: Conversation and Context

## Goal

Add session lifecycle management to `tak prompt`: the ability to reset
sessions for a fresh start, reconnect to sessions after daemon restart,
control mode/model per-prompt, and inject the user's CWD as context. This
is Level 1 of the graduated conversation design (ADR-016).

## Context

Session persistence already works: when an agent is spawned via `tak spawn`,
the ACP session survives across `tak prompt` calls because the process,
connection, and session all stay alive in the daemon. Conversation history
accumulates naturally. What's missing is **session lifecycle management**:

- No way to reset a session for a fresh conversation without stopping and
  re-spawning the entire agent process.
- No reconnection to a prior session after daemon restart (`load_session`
  is implemented but not wired into the restart flow).
- No per-prompt CWD injection (the user's shell directory at prompt time).
- No `--mode` flag to control the session mode from the CLI.
- No `set_config_option` usage (currently uses the older `set_session_mode`
  / `set_session_model` calls).

**Terminology note**: Phase M keeps the 1:1:1 model where one agent = one
process = one connection = one session. Multi-session support (N sessions
per process) is deferred to a future phase once the conceptual model
described in `docs/research/multi-agent-workflow-architecture.md` is
settled. The primitives built here (session reset, reconnection, mode
control, CWD injection) are prerequisites for both multi-session and
pipeline orchestration.

### Design (from ADR-016)

- Subsequent `tak prompt` calls send a new `session/prompt` within the
  existing session for the agent.
- `tak prompt --mode ask|plan|agent` sets the session mode on creation.
- `tak session end [agent]` closes the ACP session (but the process and
  connection stay alive); the next `tak prompt` creates a fresh session
  via a cheap `new_session()` call -- no process re-spawn needed.
- Each prompt includes the caller's CWD as context (configurable format).
- On daemon restart, agents with a saved `acp_session_id` attempt
  `load_session` before falling back to `new_session`.

## Files to Read First

- `src/tak/providers/acp_session.py` -- `ACPSessionManager` (manages JSON-RPC lifecycle)
- `src/tak/providers/acp.py` -- `ACPProvider.send()` and `send_streaming()`
- `src/tak/ipc/server.py` -- `IPCServer` dispatch including the `prompt` method
- `src/tak/ipc/client.py` -- `send_request()` used by the CLI
- `src/tak/cli/main.py` -- `prompt` command implementation
- `src/tak/drivers/iterm2/daemon.py` -- daemon entry point, AdHocManager setup
- `src/tak/core/agent_bus.py` -- `BusMessage` and `BusResponse`
- `src/tak/core/config.py` -- config loading (for CWD format option)
- `docs/research/architecture-decisions.md` -- ADR-016
- `docs/research/agents/cursor-acp-behavior/analysis.md` -- ACP behavior study;
  sections §4 (config options / modes), §8 (CWD / workspace behavior),
  §11 (session load / resume), §5 (streaming timeline)
- `docs/research/multi-agent-workflow-architecture.md` -- conceptual model
  (process vs connection vs session, tab/worker agents, terminology)

## What to Build

### 1. User CWD in IPC Requests (pm-cwd-awareness + pm-cwd-configurable)

The `tak prompt` CLI command should include the caller's working directory in
the IPC request so the agent knows where the user is.

**Important distinction -- two CWDs are in play:**

- **Session CWD** -- set once via `new_session(cwd=...)` when the agent spawns.
  This defines the agent's workspace root for the entire session. It is
  immutable for the session's lifetime (ACP analysis §8 confirmed this). The
  agent's built-in file tools (Read, Edit, Find) operate relative to it.
- **User CWD** -- the user's shell `os.getcwd()` at the moment they run
  `tak prompt`. This can differ from the session CWD if the user `cd`s into
  a subdirectory. Injecting it per-prompt helps the agent resolve relative
  references (e.g. "look at this file" from a subdirectory).

Only the user CWD is injected per-prompt. The session CWD is already set.

**`src/tak/cli/main.py`** -- `prompt` command:
- Add `os.getcwd()` to the params dict as `"cwd"`.

**`src/tak/ipc/server.py`** -- `prompt` handler:
- Accept the `cwd` parameter and pass it through to the provider.

**`src/tak/core/agent_bus.py`** -- `BusMessage`:
- Add an optional `cwd: str | None` field to `BusMessage`.

**`src/tak/providers/acp.py`** -- `ACPProvider.send()`:
- When CWD is provided, prepend it to the prompt text using the configured
  format (see below).

#### Configurable CWD Injection Format

The format for injecting the user's CWD into the prompt is configurable via
`~/.tak/config.yaml`:

```yaml
prompt:
  cwd_context:
    enabled: true          # false to disable injection entirely
    format: xml            # xml | bracket | json | none
```

Format options:

| Format    | Output                                                        |
|-----------|---------------------------------------------------------------|
| `xml`     | `<context><user_cwd>/path</user_cwd></context>\n\n{prompt}`  |
| `bracket` | `[User CWD: /path]\n\n{prompt}`                              |
| `json`    | `{"user_cwd": "/path"}\n\n{prompt}`                          |
| `none`    | `{prompt}` (no injection, same as `enabled: false`)           |

Default: `xml`. Agents (particularly Claude-family models) treat XML-delimited
context as metadata rather than conversational content, which reduces the
tendency to echo the directory back in the response. The bracket format is
simpler but can cause agents to repeat and hedge ("I can see your working
directory is..."). Users who prefer a different style or want no injection at
all can override.

**`src/tak/core/config.py`**:
- Add `prompt.cwd_context.enabled` (bool, default `True`) and
  `prompt.cwd_context.format` (str, default `"xml"`) to the config schema.

**`src/tak/providers/acp.py`** -- `ACPProvider.send()`:
- Read the CWD format from config.
- Apply the chosen format when prepending CWD to the prompt text.
- A helper function `format_cwd_context(cwd, fmt)` keeps the logic testable.

### 2. Session Reset and Lifecycle

Session persistence already works: `ACPProvider` keeps sessions alive in
`_sessions` across `tak prompt` calls. This section adds lifecycle
management on top of that.

**`src/tak/providers/acp.py`** -- `ACPProvider`:
- Add a `close_session(agent_name: str) -> None` method that calls
  `session.close_session()` and removes the entry from `_sessions`.
  The process and connection remain alive.
- The next `tak prompt` call to that agent detects no session exists and
  creates a fresh one via `new_session()` (cheap JSON-RPC call, no
  process re-spawn).

**`src/tak/drivers/iterm2/daemon.py`**:
- On agent stop, close the session before killing the process.
- On daemon shutdown, close all sessions.

### 3. Mode Selection

Users should be able to control the ACP session mode.

**`src/tak/cli/main.py`** -- `prompt` command:
- Add `--mode` / `-M` option with choices `ask`, `plan`, `agent`.
- Default to `None` (let the provider use its default).
- Include `mode` in the IPC params.

**`src/tak/ipc/server.py`** -- `prompt` handler:
- Pass `mode` through to the provider.

**`src/tak/providers/acp_session.py`** -- `ACPSessionManager.new_session()`:
- Already accepts a `mode` parameter; ensure it flows through.

### 4. Session Reset Command

**`src/tak/cli/main.py`**:
- Add a `session` group with an `end` subcommand:
  `tak session end [AGENT]` -- closes the ACP session for the named agent
  (or the ad-hoc agent if no name given), forcing a fresh session on next
  `tak prompt`.

**`src/tak/ipc/server.py`**:
- Add a `session_end` handler that calls `provider.close_session(agent_name)`.

### 5. Session Reconnection on Daemon Restart (pm-session-reconnect) -- DONE

Implemented 2026-03-21. When the daemon restarts, agents with a saved
`acp_session_id` reconnect via `load_session` before falling back to
`new_session`. Conversation history is preserved when Cursor still holds
the session.

**What was done:**

- `ACPProvider.spawn()` accepts optional `acp_session_id` keyword argument.
- When provided, calls `session.load_session(acp_session_id)` first.
- On any error (stale session, -32602, etc.), falls back to `new_session()`.
- `AgentManager.restore()` passes the saved `acp_session_id` from state.yaml
  through to `provider.spawn()` via `**spawn_kwargs`.

**Prerequisites fixed in the same session:**

- `model_id` field added to `AgentHandle` and persisted in state.yaml so
  model ID (not display name) is used on restore (ptf-model-id-resolution).
- Session ID format mismatch between `$ITERM_SESSION_ID` (`w0t0p0:UUID`)
  and iTerm2 Python API (bare `UUID`) fixed with `_strip_session_prefix()`
  normalisation (ptf-session-id-format-mismatch).
- `_handle_associate` now calls `_auto_save()` so associations persist
  immediately rather than waiting for periodic save or graceful shutdown
  (ptf-associate-state-persistence).
- SIGTERM/SIGINT signal handlers added to daemon for graceful shutdown
  (ptf-signal-handling).

### 6. Use `set_config_option` as Primary Mutation Path (pm-config-option-mutation)

ACP analysis §4 confirmed that `set_config_option` works for both mode and
model changes and returns the full refreshed `configOptions` in the response.
Mode changes fire `CurrentModeUpdate` notifications; model changes do not.

**`src/tak/providers/acp_session.py`**:
- Add a `set_config_option(option_id, value)` method that calls
  `conn.set_config_option()` and updates local state from the response.
- Update `new_session()` to use `set_config_option("mode", mode)` and
  `set_config_option("model", model_id)` instead of the separate
  `set_session_mode` / `set_session_model` calls.

### 7. Tests

**`tests/cli/test_cli.py`**:
- Test `tak prompt` includes CWD in params.
- Test `--mode` flag is passed through.
- Test `tak session end` command.

**`tests/ipc/test_server.py`**:
- Test `prompt` handler passes CWD.
- Test `prompt` handler passes mode.
- Test `session_end` handler.

**`tests/providers/test_acp.py`**:
- Test session reuse (second `send()` call reuses existing session).
- Test `close_session()` clears the session.
- Test CWD is prepended to prompt text in the configured format.
- Test each CWD format option (xml, bracket, json, none).

**`tests/core/test_agent_bus.py`**:
- Test `BusMessage` with `cwd` field.

## Acceptance Criteria

1. `tak prompt "what files are here"` sends `os.getcwd()` in the IPC request;
   the agent receives the user CWD as context in the configured format.
2. Two consecutive `tak prompt` calls to the same agent reuse the same ACP
   session; the agent sees both prompts in conversation history.
3. `tak prompt --mode plan "refactor auth"` creates a session in plan mode.
4. `tak session end my-agent` closes the session; the next `tak prompt`
   creates a fresh session.
5. After daemon restart, agents with saved `acp_session_id` reconnect via
   `load_session` and retain prior conversation context.
6. Mode and model changes use `set_config_option` and local state is updated
   from the response.
7. CWD injection format is configurable via `~/.tak/config.yaml`; the default
   `xml` format does not cause the agent to echo the directory in its response.
8. All existing tests continue to pass (432+).
9. `ruff check` passes with zero errors.
10. Manifest updated to mark phase-m tasks as done.

## Agent Prompt

Use this prompt to kick off a fresh agent session for this phase:

> Read `docs/tasks/phase-m-conversation.md` for the full spec. This phase adds
> session lifecycle management (reset, reconnection), configurable CWD
> awareness, mode selection via `--mode`, and `set_config_option` as the
> primary mutation path for `tak prompt`. Session persistence across prompts
> already works; this phase builds lifecycle control on top of it. Read the
> "Files to Read First" section (including the ACP analysis and workflow
> architecture references), then implement each item in "What to Build" in
> order. Run `ruff check src/ tests/` and `pytest -q` after each change.
> Update `docs/tasks/manifest.yaml` phase-m status to `done` when all
> acceptance criteria pass.
