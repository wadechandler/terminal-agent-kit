# Phase F: ACP Permission and Interaction Relay

## Goal

Implement the full ACP session lifecycle in `CursorACPProvider` so that tak
can spawn a Cursor agent, send prompts, stream responses, and relay
permission requests to the user without YOLO mode.

## Context

The current `CursorACPProvider` at `src/tak/providers/cursor_acp.py` has a
basic `spawn()` / `send()` / `stop()` skeleton. The `send()` method uses a
simplified request-response model (`agent/query`) that doesn't match the
real ACP protocol. This phase replaces it with the actual JSON-RPC session
flow.

### ACP Session Flow (JSON-RPC 2.0 over stdio)

1. `initialize` -- exchange capabilities
2. `authenticate` with `methodId: "cursor_login"` (or `CURSOR_API_KEY` env var)
3. `session/new` (or `session/load` to resume a previous session)
4. `session/prompt` -- send user message, with `prompt` array of `{type: "text", text: "..."}`
5. Handle `session/update` notifications -- streamed output chunks
6. Handle `session/request_permission` -- agent wants to run a tool; respond
   with `reject-once`, `allow-once`, or `allow-always`. **Agent blocks until answered.**
7. Optionally handle `cursor/ask_question` (multiple choice from agent)
8. `session/cancel` to abort

Session modes: `ask` (read-only), `plan` (read-only), `agent` (full tool access).
Permissions only apply in `agent` mode.

## Files to Read First

- `src/tak/providers/cursor_acp.py` -- current provider (rewrite the session methods)
- `src/tak/providers/base.py` -- `BaseProvider` with `InteractionModel`, `send_streaming()`
- `src/tak/core/agent_manager.py` -- `AgentHandle` dataclass, `AgentManager.spawn()`
- `src/tak/ipc/server.py` -- IPC dispatch (may need new methods for permission relay)
- `src/tak/drivers/iterm2/daemon.py` -- daemon entry point that wires everything
- `docs/research/acp-ecosystem.md` -- full protocol details
- `docs/research/cursor-acp-integration.md` -- Cursor-specific notes

## What to Build

### 1. ACP Session Manager (new: `src/tak/providers/acp_session.py`)

A class that manages the JSON-RPC session lifecycle over a subprocess's
stdin/stdout. Responsibilities:

- Send JSON-RPC requests and correlate responses by `id`
- Read stdout in a background task, dispatching:
  - Responses (have `id`) to waiting request futures
  - Notifications (no `id`) to registered handlers
- Handle `session/update` by yielding text chunks to the caller
- Handle `session/request_permission` by calling a callback
- Handle `cursor/ask_question` by calling a callback
- Provide `initialize()`, `authenticate()`, `new_session()`, `prompt()`,
  `cancel()` methods

### 2. Update CursorACPProvider

- Replace the current `send()` with `prompt()` that uses ACP session flow
- `send_streaming()` yields chunks from `session/update`
- `spawn()` now also calls `initialize()` + `authenticate()` + `session/new()`
- Add a `permission_callback` that the daemon sets to handle permission requests
- Add `cancel()` method

### 3. Permission Relay in the Daemon

In `src/tak/drivers/iterm2/daemon.py`:

- When a headless agent sends `session/request_permission`, the daemon:
  1. Injects a prompt into the user's associated terminal session:
     `[tak] cursor-myapp wants to: Edit src/foo.py\n  Allow? [y]es / [n]o / [a]lways: `
  2. Reads the user's response (single keypress or line)
  3. Maps y→allow-once, n→reject-once, a→allow-always
  4. Sends the response back to the ACP subprocess

- For `cursor/ask_question`, inject the choices and read the selection.

### 4. IPC Extension

Add an `ask` method to the IPC server so `tak ask "query"` can send a
prompt through the daemon to the agent and stream the response back.

## Tests to Write

- `tests/providers/test_acp_session.py`:
  - Mock subprocess with canned JSON-RPC responses
  - Test initialize/authenticate/new_session handshake
  - Test prompt sending and update chunk collection
  - Test permission request callback invocation
  - Test request ID correlation
  - Test connection error handling

- `tests/providers/test_cursor_acp.py`:
  - Test spawn builds correct command with --model flag
  - Test list_models parses output
  - Test stop terminates gracefully then kills

- Update `tests/ipc/test_server.py`:
  - Test `ask` method dispatch

## Acceptance Criteria

- `ruff check src/ tests/` passes with zero errors
- All tests pass
- A `CursorACPProvider` can be spawned (with mock subprocess) and:
  - Completes the initialize → authenticate → session/new handshake
  - Sends a prompt and collects streamed update chunks
  - Invokes the permission callback when request_permission arrives
  - Cancels a session cleanly
- The IPC server accepts `ask` requests

## Dependencies

- None on other phases. Can run independently.
- Testing the real Cursor ACP end-to-end requires Cursor CLI auth (mark as
  `@pytest.mark.integration`).

---

## Agent Prompt

```
Read AGENTS.md for project conventions, then read these files to understand
the current code:
- src/tak/providers/cursor_acp.py
- src/tak/providers/base.py
- src/tak/core/agent_manager.py
- src/tak/ipc/server.py
- src/tak/drivers/iterm2/daemon.py
- docs/research/acp-ecosystem.md
- docs/research/cursor-acp-integration.md

Then read docs/tasks/phase-f-acp-permissions.md for the full task spec.

Implement everything described in the task file. Work through each section
(ACP Session Manager, CursorACPProvider update, permission relay, IPC
extension, tests). Run ruff check and pytest after each major piece.
Do not stop until ruff check src/ tests/ shows zero errors and all tests pass.
```
