# Phase N: Streaming and IPC Enhancement

## Goal

Make `tak prompt` stream agent responses in real time: text appears as chunks
arrive, activity phase indicators show what the agent is doing, and inactivity
detection warns when something may be stuck. This is Level 2 of the graduated
conversation design (ADR-016).

## Context

Currently `tak prompt` (née `tak ask`) blocks until the full response is
collected, then prints it all at once. The ACP session already streams chunks
via `session_update` callbacks, but the IPC protocol between daemon and CLI
is request/response -- one message out, one message back. To stream, the IPC
protocol needs to support multiple response frames per request.

ACP analysis §5 provides concrete timing data from real Cursor agent tasks:
- Initial think time before first update: ~5s
- Max gap between consecutive updates: 5.43s (in a 59.4s task)
- Think/respond/work cycles repeat 5-17 times per task
- Thought chunks stream rapidly during thinking phases
- Tool calls produce start + progress + completion updates

## Dependencies

- **Phase P (Event Fidelity)** provides the `SessionEvent` types that this
  phase routes through IPC. If Phase P is not yet done, this phase can start
  with plain text chunks and upgrade to typed events later.
- **Phase M (Conversation)** provides session persistence so streaming works
  across multi-turn conversations.

## Files to Read First

- `src/tak/ipc/protocol.py` -- current length-prefixed JSON protocol
- `src/tak/ipc/server.py` -- `_handle_ask` sends one response
- `src/tak/ipc/client.py` -- `send_request` receives one response
- `src/tak/providers/acp_session.py` -- `prompt_streaming()` yields chunks
- `src/tak/providers/acp.py` -- `send_streaming()` wraps session streaming
- `src/tak/cli/main.py` -- `ask` command prints final response

## What to Build

### 1. Streaming IPC Protocol (pn-streaming-ipc)

Extend the IPC protocol to support streaming responses. The daemon sends
multiple length-prefixed JSON frames for a single request:

```python
# Each frame has a "type" field:
{"type": "chunk", "data": {"text": "Hello "}}
{"type": "chunk", "data": {"text": "world!"}}
{"type": "done", "data": {"agent": "my-agent"}}
# Or on error:
{"type": "error", "data": {"error": "No running agents"}}
```

**`src/tak/ipc/protocol.py`**:
- Add `write_message(writer, data)` helper (length-prefix + JSON encode).
- Add `StreamingResponse` type with `type` field.

**`src/tak/ipc/server.py`**:
- Add `_handle_ask_streaming` that writes multiple frames to the writer.
- Route `ask` requests to the streaming handler.

**`src/tak/ipc/client.py`**:
- Add `send_streaming_request()` that reads frames until `done` or `error`.
- Yield each chunk as it arrives.

### 2. Streaming CLI Output (pn-streaming-cli)

**`src/tak/cli/main.py`** -- `ask` / `prompt` command:
- Use `send_streaming_request()` instead of `send_request()`.
- Print each text chunk immediately (no buffering).
- Print a newline after the final chunk.

### 3. Agent Activity Phase Tracking (pn-activity-phases)

Track the agent's current activity phase based on streaming event types:

```
IDLE → THINKING (on AgentThoughtChunk)
     → RESPONDING (on AgentMessageChunk)
     → WORKING (on ToolCallUpdate with new tool_call_id)
     → IDLE (on prompt completion)
```

**`src/tak/providers/acp_session.py`**:
- Add an `ActivityPhase` enum: `IDLE`, `THINKING`, `WORKING`, `RESPONDING`.
- Track current phase in `TakACPClient.session_update()`.
- Expose via property on `ACPSessionManager`.

This phase data feeds into the status bar (Phase Q) and inactivity detection.

### 4. Inactivity Detection (pn-inactivity-detection)

Monitor the gap between streaming events and surface warnings.

Thresholds (from ACP analysis §5, configurable):
- **10-15s silence**: Unusual. Surface soft "still working..." indicator.
- **20-30s silence**: Likely abnormal. Show warning with cancel option.
- **30s+ silence**: Almost certainly stuck. Offer cancel and retry.

The inactivity timer resets on any streaming event. The initial delay before
the first event (up to 5s) is normal and should not trigger warnings.

**`src/tak/providers/acp_session.py`**:
- Track `_last_event_time` in `TakACPClient.session_update()`.
- Add `seconds_since_last_event` property.

**`src/tak/cli/main.py`** (or streaming client):
- During streaming, check elapsed time and print soft warnings.

### 5. Cancel from CLI (pn-cancel-cli)

**`src/tak/cli/main.py`**:
- Register a `SIGINT` handler during streaming that calls `session_cancel`
  via IPC instead of killing the CLI process.
- First `Ctrl+C`: cancel the in-flight prompt, print "Cancelled."
- Second `Ctrl+C` (within 2s): exit the CLI.

**`src/tak/ipc/server.py`**:
- Add a `cancel` IPC handler that calls `provider.cancel(handle)`.

### 6. Input Preemption (pn-input-preemption)

When a new prompt arrives while one is in-flight, cancel the current
operation and start the new one. This is the natural "I see you going
wrong, here's what I actually want" pattern.

**`src/tak/ipc/server.py`** -- `_handle_ask_streaming`:
- If the agent is in `PROMPTING` state, call `session.cancel()` first,
  then send the new prompt.

## Tests

**`tests/ipc/test_protocol.py`**:
- Test streaming frame encoding/decoding.

**`tests/ipc/test_server.py`**:
- Test streaming ask handler yields multiple frames.
- Test cancel handler.

**`tests/providers/test_acp_session.py`**:
- Test activity phase transitions.
- Test `seconds_since_last_event` tracking.

**`tests/cli/test_cli.py`**:
- Test streaming output prints chunks incrementally.

## Acceptance Criteria

1. `tak prompt my-agent "explain this code"` streams text to the terminal
   as chunks arrive, not after the full response.
2. Activity phase is tracked and accessible via `session.activity_phase`.
3. After 15s of silence during streaming, a soft warning appears.
4. `Ctrl+C` during streaming cancels the prompt cleanly; the session
   remains healthy for the next prompt.
5. Sending a new prompt while one is in-flight cancels the old one.
6. All existing tests pass. `ruff check` clean.

## Agent Prompt

> Read `docs/tasks/phase-n-streaming.md` for the full spec. This phase adds
> streaming IPC, activity phase tracking, inactivity detection, and cancel
> support to `tak prompt`. Read "Files to Read First", then implement each
> item in "What to Build" in order. Run `ruff check src/ tests/` and
> `pytest -q` after each change. Update manifest.yaml when done.
