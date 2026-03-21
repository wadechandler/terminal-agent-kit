# Cursor ACP Behavior — Analysis & Discovery

**Date**: 2026-03-17 (updated 2026-03-18)
**Sources**:
- **v1** (phases 1–7): `report.md`, `raw_responses.json`
- **v2** (phases 8–14, gap-fill): `report_v2.md`, `raw_responses_v2.json`
- **v3** (phases 15–20): `report_v3.md`, `raw_responses_v3.json`
- **v3b–v3d** (phase 21, MCP config): `raw_responses_v3b.json` – `raw_responses_v3d.json`
- **v3e** (phase 21, pre-approval + CLI): `raw_responses_v3e.json`
- **External**: [Cursor ACP docs](https://cursor.com/docs/cli/acp),
  [Cursor MCP docs](https://cursor.com/docs/mcp),
  [Forum: MCP approval bug](https://forum.cursor.com/t/mcp-servers-passed-via-session-new-dont-work-in-acp-mode/153823)

**Inspection script**: `scripts/agent_inspection/cursor_acp_inspect.py`
**Mock MCP servers**: `scripts/agent_inspection/mock_mcp_echo.py` (stdio),
`scripts/agent_inspection/mock_mcp_http.py` (HTTP)

---

## 1. The `list_sessions` Error — Explained

The inspection script called `conn.list_sessions(cwd=tmpdir)`, which sends a
`session/list` JSON-RPC request to the Cursor agent process. Cursor returned:

```
RequestError code=-32601: "Method not found": session/list
```

This is **expected and correct behavior**, not a bug. The `initialize` response
explicitly declares this capability as unsupported:

```json
"sessionCapabilities": {
  "fork": null,
  "list": null,
  "resume": null
}
```

All three session management capabilities — `fork`, `list`, `resume` — are `null`,
meaning Cursor does not implement them. The ACP SDK itself marks `session/list` as:

> **UNSTABLE** — This capability is not part of the spec yet, and may be removed
> or changed at any point.

**Takeaway for tak**: Before calling `list_sessions`, `session_fork`, or
`session_resume`, check the corresponding `sessionCapabilities` field from the
`initialize` response. Guard these calls or skip them entirely for agents that
report `null`.

---

## 2. Model Name Resolution — Root Cause Analysis

### The data confirms the lookup chain works

The `NewSessionResponse` from Cursor includes:

| Field | Value |
|-------|-------|
| `current_model_id` | `default[]` |
| `available_models` entry | `model_id: "default[]"`, `name: "Auto"` |

The `acp_session.py` logic builds `models_by_id = {"default[]": "Auto", ...}` and
sets `_current_model_name = models_by_id.get("default[]", "default[]")` → `"Auto"`.

The `@property current_model_name` correctly returns `"Auto"`.
The `_extract_model_display()` in `agent_manager.py` correctly reads this property.

**So why did `tak agents` show `default□`?**

### Hypothesis 1: Rich markup interpretation (LIKELY contributing factor)

The CLI renders the agents table with Rich's `Table`:

```python
table.add_row(
    agent["name"],
    agent["provider"],
    agent.get("model") or "--",   # raw string passed to Rich
    agent["status"],
    ...
)
```

Rich interprets `[...]` as markup tags. The model ID `default[]` contains an empty
bracket pair `[]` which Rich would interpret as an empty/malformed markup tag,
rendering it as a box placeholder character `□` or stripping it entirely.

**Even if the primary resolution is correct**, any code path that leaks the raw
`model_id` (instead of the human-readable `name`) into a Rich-rendered context
will produce garbled output. This means we need **two layers of defense**:

1. Always resolve to the human-readable name (primary fix)
2. Escape Rich markup in display values (safety net)

### Hypothesis 2: Stale daemon / state persistence

If `tak agents` was queried against a daemon that loaded agent state from
`~/.tak/state.yaml` persisted by an older code version — one that stored the raw
`model_id` instead of the resolved name — the display would show the raw ID.

### Hypothesis 3: Model parameter passthrough

If a user runs `tak spawn cursor myagent --model default`, the CLI sets
`handle.model = "default"` (truthy), so `_extract_model_display` is never called.
The display would show `"default"` verbatim. Not `"default[]"`, but close — and
if the daemon internally reconciles this to the Cursor model ID `"default[]"`,
the Rich issue kicks in.

### Recommended fix strategy

1. **`_extract_model_display` should always prefer human-readable name** — already
   does this; no change needed in the getter.
2. **Escape model strings in CLI table rendering** — use `rich.markup.escape()` or
   `Text(value)` objects to prevent bracket interpretation.
3. **Add fallback resolution in `new_session`** — if the user passes a `model`
   string that doesn't exactly match an `available_models` entry (e.g. `"default"`
   without brackets), try fuzzy matching: strip `[]` suffix from known IDs, do
   case-insensitive lookup.
4. **Add debug logging** — log the raw `result.models` payload in `new_session()`
   so we can diagnose mismatches without re-running the inspection.

---

## 3. Model ID Format — The Bracket Convention

All Cursor model IDs follow the pattern `name[params]`:

| Pattern | Examples |
|---------|----------|
| `name[]` (empty params) | `default[]`, `composer-1.5[]`, `gemini-3-flash[]` |
| `name[key=value]` | `gpt-5.1[reasoning=medium]` |
| `name[k1=v1,k2=v2,...]` | `claude-opus-4-6[thinking=true,context=200k,effort=high,fast=false]` |

The bracket suffix encodes model capabilities/flags. Key observations:

- **`fast=false`** appears on larger models (Opus, GPT-5.4, Codex 5.3) — these
  are presumably slower/premium.
- **`thinking=true/false`** distinguishes extended-thinking Claude variants.
- **`reasoning=medium`** is universal for GPT/Codex models.
- **`context=200k/272k`** explicit context window declarations.
- **`effort=medium/high`** thinking effort levels for Claude.

### Model catalog growth (v2 observation)

The v2 inspection captured models not present in v1:

| New Model | ID |
|-----------|----|
| GPT-5.4 Mini | `gpt-5.4-mini[reasoning=medium]` |
| GPT-5.4 Nano | `gpt-5.4-nano[reasoning=medium]` |
| Kimi K2.5 | `kimi-k2.5[]` |

The catalog now spans 20+ models across four vendors (Anthropic, OpenAI, Google,
Moonshot). The list is dynamic — tak must treat `available_models` as the
authoritative roster per session, never a hard-coded enum.

**Implications for tak**:

- Never display raw model IDs to users. Always resolve to `name` from `available_models`.
- The bracket params could be exposed in an advanced "model info" view.
- Model selection UI should show the human-readable name and optionally the params.
- The model list changes between Cursor releases; tak must refresh it per-session.

---

## 4. Modes and Config Options — Dual Access Pattern

Cursor exposes mode information through **two parallel mechanisms**:

### Mechanism A: `NewSessionResponse.modes`

```
current_mode_id: "agent"
available_modes: [{id: "agent", name: "Agent"}, {id: "plan", name: "Plan"}, {id: "ask", name: "Ask"}]
```

### Mechanism B: `NewSessionResponse.config_options`

```json
{
  "category": "mode",
  "id": "mode",
  "type": "select",
  "currentValue": "agent",
  "options": [
    {"value": "agent", "name": "Agent", "description": "Full agent capabilities with tool access"},
    {"value": "plan", "name": "Plan", "description": "Read-only mode for planning and designing before implementation"},
    {"value": "ask", "name": "Ask", "description": "Q&A mode - no edits or command execution"}
  ]
}
```

And similarly for models — the same data appears in both `models` and `config_options`.

**Key discovery**: `config_options` provides **descriptions** that `modes`/`models`
do not. The mode descriptions are particularly useful:

- **Agent**: "Full agent capabilities with tool access"
- **Plan**: "Read-only mode for planning and designing before implementation"
- **Ask**: "Q&A mode — no edits or command execution"

**Implications for tak**: Use `config_options` as the richer data source when
available. The `modes` and `models` fields are sufficient for basic operation, but
`config_options` gives us the descriptions needed for a good user-facing UI.

### `set_config_option` — Unified Mutation Path (v2 confirmed)

The v2 inspection tested `set_config_option` for both modes and models. Results:

| Call | Success | Side Effects |
|------|---------|--------------|
| `set_config_option("mode", "plan")` | Yes | Returns updated `configOptions` with `currentValue: "plan"`. Fires `current_mode_update` notification. |
| `set_config_option("mode", "agent")` | Yes | Returns updated config. Fires `current_mode_update`. |
| `set_config_option("model", "claude-haiku-4-5[thinking=true]")` | Yes | Returns updated config with new `currentValue`. **No notification fired.** |
| `set_config_option("mode", "nonexistent")` | No | `-32602: Invalid params` |
| `set_config_option("bogus", "x")` | No | `-32602: Invalid params` |

Key findings:

1. **`set_config_option` is a fully functional alternative** to `set_session_mode` /
   `set_session_model`. Both mutation paths work.

2. **Mode changes fire `current_mode_update` notifications; model changes do not.**
   This asymmetry means a client watching for streaming notifications will be
   notified of mode transitions but must rely on the synchronous response to confirm
   model switches.

3. **The response always returns the full `configOptions` array**, not just the
   changed option. This provides a single source of truth — the client can
   re-sync its entire config state from any mutation response.

4. **Invalid values produce clean errors.** Both unknown config IDs and invalid
   option values return `-32602`. No silent failures, no partial state changes.

**Design recommendation for tak**: Use `set_config_option` as the primary mutation
path for both modes and models. The response gives the full refreshed config in
one call, and the notification system handles mode-change propagation to any
listening TUI components. For model changes, update the local state from the
synchronous response since no async notification fires.

---

## 5. Streaming Timeline — Phase Transitions

The inspection captured a multi-step agent task (create Fibonacci script, check
lints, explain) and revealed a clear **think → respond → work** cycle pattern:

```
Phase 1:  thinking (0.85s) → responding (0.03s) → working (3.06s)
Phase 2:  thinking (1.29s) → responding (0.10s) → working (1.79s)
Phase 3:  thinking (0.37s) → responding (1.57s)
```

### Update types and their meaning

| ACP Update Type | UX Phase | What it carries |
|-----------------|----------|-----------------|
| `agent_thought_chunk` | **Thinking** | Internal reasoning text (not shown to user by convention) |
| `agent_message_chunk` | **Responding** | User-visible response text, streamed incrementally |
| `tool_call` | **Working** | Tool invocation start — has `title` (e.g. "Edit File", "Read File") |
| `tool_call_update` | **Working** | Tool progress/completion updates |

### Longer-running task timeline (v2, Phase 11)

Phase 11 sent a multi-file project creation prompt (3 Python files + run + report)
and captured a much richer timeline than Phase 6:

| Metric | Value |
|--------|-------|
| Total duration | 59.4s |
| Time to first update | 5.09s (thought chunk) |
| Max gap between updates | 5.43s |
| Total updates | 305 |
| Tool calls | 10 |
| Think/respond/work cycles | 17 |

The phase timeline shows a consistent internal rhythm:

```
Initial think: 10.0s  (deep planning)
Cycle 1: respond 0.15s → work 7.7s → think 0.7s
Cycle 2: respond 0.10s → work 8.9s → think 3.5s
Cycle 3: respond 0.05s → work 8.3s → think 0.8s
Cycle 4: respond 0.14s → work 7.5s → think 0.35s
Cycle 5: respond 0.34s → work 1.5s → think 0.5s
Final:   respond 3.7s  (summary to user)
```

**Patterns extracted**:

- The initial thinking phase is the longest (5–10s). Subsequent think phases
  drop to sub-second as the agent already has its plan.
- "Working" phases (tool execution) are consistently 7–9s for file write + lint
  operations. The last work phase is shorter (1.5s) — likely a final read.
- "Responding" phases are brief mid-task (0.05–0.35s, just status snippets)
  but longer at the end (3.7s for the final summary).
- **No gaps exceed 5.5s.** This gives us a concrete inactivity detection
  threshold: 10–15s of silence reliably indicates something abnormal.

### Thought chunk characteristics

Thought chunks stream rapidly and contain the agent's internal reasoning verbatim.
Examples from the capture:

- _"The user wants me to create a Python script that: 1. Generates the first 100
  Fibonacci numbers..."_
- _"The script is created. Let me verify there are no linter errors..."_
- _"No linter errors. The script is complete."_

These are **not** shown to the end user in Cursor's UI, but they are transmitted
over ACP. This means tak could:

1. **Show a "thinking" indicator** when thought chunks arrive.
2. **Configurable thought visibility** — a verbosity dial, not a binary toggle.
   Possible levels: `off` (indicator only), `summary` (first line / key phrases),
   `full` (stream everything), with the ability to adjust mid-session. Power users
   who want to supervise closely can turn it up; those who just want results can
   turn it down.
3. **Detect phase transitions** by watching for the first `agent_message_chunk`
   after a sequence of `agent_thought_chunk`s.

### Tool call taxonomy

From the inspection (run with `mcp_servers=[]`), Cursor used these built-in tools:

| Tool Title | Permission Required | Notes |
|------------|-------------------|-------|
| **Find** | No | File/directory search |
| **Read File** | No | Read file contents |
| **Edit File** | No | Create/modify files |
| **Read Lints** | No | Check linter output |
| **Terminal** | **Yes** | Execute shell commands |

Only `Terminal` (shell execution) triggers a permission callback. File operations
are auto-approved by the agent. This aligns with Cursor's security model: reading
and writing files in the workspace is allowed, but arbitrary command execution
requires user consent.

### Tool surface is not static

The above table represents the **built-in** tool set observed with no MCPs
attached. In practice, the tool surface is a layered composition:

1. **Baked-in agent tools** — the core set shown above. These are hard-coded in
   the agent and always available.
2. **MCP resource tools** — always available: `list_mcp_resources` and
   `fetch_mcp_resource`. These allow the agent to discover and read MCP
   resources (structured data) but not invoke MCP tools (actions).
3. **MCP-provided tools** — configured via `.cursor/mcp.json` (project or user
   level). The `initialize` response declares `mcpCapabilities: {http: true,
   sse: true}`. However, **MCP tools are currently blocked in ACP mode** due to
   an approval middleware bug (see §15). When functional, these tools vary by
   user configuration and can include database queries, API calls, browser
   automation, or any custom capability.
4. **Future protocol extensions** — as ACP evolves, new tool types and capability
   categories will emerge.

**Implications for tak**: The tool call display, permission model, and progress
tracking must treat tool names as **opaque strings**, not a known enum. The
`tool_call.title` field is the only reliable identifier, and tak should render
whatever title the agent reports. Permission policies should operate on patterns
or categories (e.g. "all terminal-like tools require approval") rather than
hard-coded tool names. The MCP dimension also means that the same agent type
can have very different capabilities depending on which MCP servers are configured
for the session — tak's agent info/status display should reflect the active tool
surface when possible.

---

## 6. Permission Handling

### Auto-approve mode

In the default auto-approve mode, the `Terminal` tool call in Prompt 4 ("Run
hello.py") triggered 1 permission request which was automatically approved.

### Reject-once mode

In reject-once mode, the agent was asked to "Delete all .py files and list what
remains." The agent chose to use **Edit File** (which doesn't require permission)
rather than **Terminal** (which would have been rejected). The agent completed the
task with 0 permission requests.

### Rejection behavior (v2, Phase 10)

Phase 10 forced the agent to use the Terminal tool and persistently rejected all
permission requests. Results:

**First prompt** ("Execute `python3 -c 'print(42)'` — you MUST use the terminal"):

- Agent requested Terminal permission → rejected
- Agent **retried the same tool** → rejected again
- Agent gave up after 2 rejections, responded in text explaining it could not execute
- Total: 2 permission requests, 48 updates, 12.6s

**Second prompt** ("Run `echo hello`"):

- Agent requested Terminal permission once → rejected
- Agent gave up after 1 rejection (learned from previous experience in the session)
- Total: 1 permission request, 34 updates, 10.9s

**Key findings**:

1. **Retry-once-then-fallback**: The agent retries a rejected tool exactly once
   on the first encounter, then falls back to text-based explanation. On subsequent
   prompts in the same session, it only tries once before falling back — it
   learns within the session that rejection is persistent.

2. **Graceful degradation**: The agent does not error, crash, or enter a stuck
   state when tools are rejected. It shifts to a text-only response explaining
   what it would have done and why it cannot.

3. **Session-level learning**: The retry count decreases across prompts in the
   same session. The agent appears to maintain awareness that the permission was
   previously rejected.

**Implications for tak**: Permission rejection is safe and well-handled. A tak
safety policy that rejects certain tools (e.g. "no Terminal for unattended agents")
will produce clean degradation. The agent won't spin or crash — it will explain
what it cannot do.

### Permission model is user-configured, not tool-intrinsic

From real-world Cursor usage: whether a tool (built-in or MCP-provided) triggers
a permission request depends on **user-configured policy**, not a fixed property
of the tool itself. Cursor provides an allowlist mechanism where the user can
mark specific tools or tool patterns as pre-approved. This means:

- The same MCP tool might require permission for one user but not another.
- A tool that required permission initially can be allowlisted for future calls.
- The permission callback tak receives from `request_permission` is the **result**
  of Cursor's internal policy evaluation — tak does not need to replicate this
  logic, only respond to whatever the agent asks.

**Implications for tak**: tak's permission layer should be a pass-through that
presents the request and returns the user's decision. It should NOT try to
maintain its own allowlist or guess which tools need permission — that's the
agent's responsibility. However, tak could offer its own **additional** policy
layer on top (e.g. "always reject Terminal calls for this agent") as a safety
net, since tak manages agents that the user may not be directly supervising.

---

## 7. Timeout and Cancellation Behavior

### Short timeout (2 seconds)

- Prompt sent: "Write a haiku about programming."
- After 2 seconds: **0 updates received** — not even thought chunks.
- The prompt was still in-flight on the server side.

**Insight**: 2 seconds is insufficient for any meaningful agent response. The agent
needs at least 3-5 seconds before streaming begins. Hard timeouts are the wrong
primitive here — see "Interaction patterns during long operations" below.

### Cancel after timeout

After the 2-second timeout, `session_cancel` was called. It succeeded. This confirms
the cancel mechanism works even for in-flight prompts.

### Recovery after timeout

A new prompt ("Say 'recovered' if you can hear me") was sent after the timeout +
cancel. It completed successfully in 5.5 seconds with 10 updates.

**Critical finding**: The ACP session remains healthy after a timeout + cancel
sequence. No reconnection or re-initialization is needed. The session absorbs the
cancellation gracefully.

### Mid-flight cancel

A prompt was sent and immediately cancelled. Result: `stop_reason: "cancelled"`,
`success: true`.

**Implications for tak**:

- Cancel is safe and non-destructive to the session.
- After cancel, the next prompt works immediately.
- A "stop generation" button in the UI can call `session_cancel` without fear of
  corrupting state.

### Interaction patterns during long operations

Hard timeouts are the wrong model for agent interactions. Instead, there are
several distinct patterns for managing long-running operations, observed in
Cursor's own UX:

1. **Soft elapsed-time feedback** — Cursor displays "Taking longer than expected"
   after some threshold. This is purely informational: it doesn't interrupt the
   operation, just keeps the user aware that time is passing. The agent continues
   working. This is preferable to a hard timeout because many legitimate tasks
   (complex refactors, multi-file operations) take significant time.

2. **User-initiated cancel** — The user explicitly stops generation via a stop
   button. This sends `session_cancel` (confirmed safe and non-destructive).
   The key is that the *user* decides when to stop, not an arbitrary timer.

3. **Preemptive new input** — The user sends a new command or correction while
   the agent is still working, causing it to abandon the current operation and
   attend to the new input. This is a natural interaction pattern: the user sees
   (via thought stream or tool calls) that the agent is going the wrong direction
   and redirects it without an explicit cancel step.

4. **Input queuing** — Cursor's IDE supports queuing follow-up prompts while the
   current one is in-flight. The queued input is delivered once the current
   operation completes. The CLI agent does not appear to replicate this feature.

**Design guidance for tak**: Rather than hard timeouts, tak should use a
combination of:

- **Elapsed-time indicator** — show how long the current operation has been
  running (e.g. a timer or "running for 45s..."), with configurable thresholds
  for soft warnings.
- **Inactivity detection** — if no streaming events arrive for an extended period,
  surface a warning. This is different from elapsed time: a busy agent streaming
  thought chunks for 2 minutes is fine; silence may indicate a hang.

  **v2 data provides concrete thresholds**: In the longest observed task (59.4s,
  Phase 11), the maximum gap between any two consecutive updates was 5.43s. The
  initial think time before the first update was 5.09s. This means:
  - **10–15s of silence**: Unusual but possible (e.g. slow model, heavy
    server load). Surface a soft "still working..." indicator.
  - **20–30s of silence**: Likely abnormal. Show a warning with cancel option.
  - **30s+**: Almost certainly stuck. Offer to cancel and retry.

  These thresholds should be configurable. The initial delay (before first update)
  is the trickiest — 5s is normal for the first think phase, so the inactivity
  timer should only start after the first update arrives.
- **Cancel always available** — the user should be able to cancel at any point
  during streaming.
- **Input preemption** — if the user sends a new prompt while one is in-flight,
  cancel the current operation and deliver the new input. This is the natural
  "I see you going wrong, here's what I actually want" pattern.

---

## 8. CWD / Workspace Behavior

The agent was asked to report its working directory. Response:

> `/private/var/folders/vj/tkmrz5cj4yz56zrtvb8lvc540000gn/T/tak-inspect-lsdfuw4w`

This is the macOS `/tmp` symlink resolved to its canonical path under `/private/var/folders`.
The inspection passed `tmpdir` as `cwd` to both `spawn_agent_process()` (OS-level)
and `new_session()` (ACP-level).

**Confirmed**: The `cwd` parameter to `new_session()` correctly sets the agent's
working directory. The agent sees files created in that directory and operates within it.

**Current bug in tak**: `ACPProvider.spawn()` passes `project_path` to
`session.new_session(cwd=...)` but does NOT pass it to `spawn_agent_process(cwd=...)`.
This means the subprocess's OS-level working directory defaults to whatever the
daemon's CWD is (often `/`). While the ACP `cwd` parameter tells the agent where
to work, the OS-level CWD affects where the subprocess itself resolves relative
paths (e.g. for `.env` files, git operations on the subprocess level).

**Recommendation**: Pass `cwd` to both `spawn_agent_process` and `new_session` in
`ACPProvider.spawn()`.

---

## 9. Edge Cases and Empty Prompts

### Empty prompt

Sending an empty string prompt returned immediately (0.0005s) with `stop_reason:
"end_turn"` and a single `agent_message_chunk` update. The agent did not error —
it simply returned an empty/minimal response.

**Implication**: Empty prompts are safe but wasteful. The client should validate
input before sending.

### Invalid model IDs

Three invalid model tests all returned `-32602: Invalid params`:

- `nonexistent-model` — completely bogus ID
- empty string — no model specified
- `default` — missing the `[]` suffix

**Critical insight**: Cursor requires the **exact** model ID including the bracket
suffix. `"default"` is NOT equivalent to `"default[]"`. This confirms that any
model selection UI must use the full `model_id` value from `available_models`, not
a stripped/simplified version.

---

## 10. Usage & Cost Tracking — The Null Result

Phase 8 tested whether Cursor exposes token/cost data via ACP. Two prompts were
sent (short and long), and all data paths were checked:

| Data Path | Result |
|-----------|--------|
| `PromptResponse.usage` | `null` on every prompt (short and long) |
| `UsageUpdate` streaming events | Zero events across all prompts |

**This is a definitive null result.** Cursor's ACP implementation does not expose
any token usage, cost, or billing data to external clients. The `usage` field
exists in the protocol schema but Cursor returns `null` for it consistently.

**Implications for tak**:

- tak cannot display per-prompt token counts or cost estimates from the ACP
  connection alone.
- A separate Cursor billing/usage API (if one exists) would be needed for cost
  tracking. This is outside ACP scope.
- tak should still handle `UsageUpdate` events if they arrive (other ACP agents
  may implement them), but should not expect or depend on them for Cursor.
- Graceful handling: display "—" or omit the usage column entirely when data is
  null, rather than showing "0" which would be misleading.

---

## 11. Session Load/Resume

Phase 12 tested session persistence despite `sessionCapabilities.resume: null`.

| Test | Result |
|------|--------|
| `load_session(session_id=<valid>)` | **Succeeds.** Returns full `LoadSessionResponse` with models, modes, config_options. |
| `load_session(session_id="bogus-id")` | `-32602: Invalid params` |

**This is a major finding.** The `sessionCapabilities.resume: null` flag refers
specifically to the `session/resume` RPC method (an unstable protocol extension),
NOT to `load_session`. The `load_session` method is a standard ACP call that
works regardless of the `resume` capability flag.

What `load_session` returns (identical shape to `new_session` response):

- `session_id` — same ID, confirming session identity
- `models` — full model roster with `current_model_id`
- `modes` — full mode list with `current_mode_id`
- `config_options` — full config with current values

**Implications for tak**:

1. **Session reconnection is possible.** If tak stores `session_id` in state
   persistence (`~/.tak/state.yaml`), it can call `load_session` after a daemon
   restart to re-attach to an existing Cursor agent session without creating a
   new one. This preserves conversation history and context.

2. **The distinction matters**:
   - `new_session(cwd=...)` — creates a fresh session, no prior context
   - `load_session(cwd=..., session_id=...)` — re-attaches to an existing session
   - `session/resume` (not implemented) — would be a protocol-level session
     migration mechanism, likely for cross-process transfer

3. **Error handling**: Bogus session IDs produce clean `-32602` errors. tak should
   attempt `load_session` first, fall back to `new_session` if the stored session
   ID is stale or invalid. This gives resilient reconnection without user
   intervention.

4. **Scope of "load" — conversation recall confirmed (v3)**:
   Phase 17 tested this directly. A code word (PHOENIX42) was set in the session,
   then `load_session` was called to reload, followed by a recall prompt. The
   agent replied: _"The code word you gave me earlier is **PHOENIX42**."_

   **Conversation history survives `load_session`.** This is critical for tak's
   daemon restart story: store the `session_id`, respawn the agent process, call
   `load_session`, and the agent retains prior context. No re-injection of
   conversation history needed.

---

## 12. Content Block Types — What Prompts Can Carry

Phase 13 tested the three non-text content block types that ACP supports.

### ImageContentBlock

| Test | Result |
|------|--------|
| Image + text prompt | Succeeds. Agent describes the image content. 8.8s. |
| Image-only prompt (no text) | Succeeds. Agent processes image and responds. 9.3s. |

The agent correctly identified the test image as "a small 8x8 pixel image" with
red coloring. Image-only prompts (no accompanying text) are valid — the agent
infers the user wants a description.

### EmbeddedResourceContentBlock

| Test | Result |
|------|--------|
| Embedded text resource + question | Succeeds. Agent reads inline content. 8.2s. |

The test sent a `TextResourceContents` block with inline config text:

```
uri: "file:///config.txt"
text: "This is a sample config file:\nport=8080\nhost=localhost"
mime_type: "text/plain"
```

The agent parsed the content and answered the question about it. This works
**despite** the `initialize` response declaring `embeddedContext: false`.

**Interpretation (unverified)**: One hypothesis is that the `embeddedContext`
flag governs `ResourceContentBlock` (URI-based references where the agent would
need to fetch/resolve the resource), while `EmbeddedResourceContentBlock` works
because it carries content inline and needs no fetching. However, we did not
test `ResourceContentBlock` at all — this is inference, not observed behavior.
The flag could mean something different entirely. What we can say empirically:
inline embedded content works regardless of the flag.

### AudioContentBlock — Not tested

The ACP schema defines `AudioContentBlock` with base64-encoded audio data. Cursor
explicitly declares `audio: false` in its capabilities. We chose not to test this
in v2 to avoid cost. When tak adds voice capabilities (e.g. integrating speech-to-text
for the TUI), this block type will need testing against agents that declare
`audio: true`. For now, tak should gracefully skip audio blocks for Cursor.

### ResourceContentBlock (URI-based) — v3 Phase 18

Phase 18 tested `ResourceContentBlock` (`type: "resource_link"`) with three
variants against a baseline.

**Test A — `file://` URI** pointing to `hello.py` in the workspace:
The agent successfully described the file's contents. It used its `Read` tool
to access the file at the path encoded in the URI. The resource link acted as
a hint pointing the agent to the file.

**Test B — `http://` URI** pointing to mock server's `/resources/config.txt`:
The agent could NOT read the HTTP resource. Response: _"I can only read files
in your workspace."_ The agent did not attempt an HTTP fetch; it tried to find
`config.txt` as a local file and failed. The mock server logs confirmed no
incoming GET request.

**Test C — plain text path baseline** ("Read hello.py and tell me what it does"):
Identical behavior to Test A — the agent read the file and described it.

**Key findings**:

1. `ResourceContentBlock` is accepted without error despite `embeddedContext: false`.
   The flag does NOT gate resource links.
2. The agent treats URIs as **hints**, not fetch targets. For `file://` URIs,
   it resolves the path and reads the file with its built-in tools. For `http://`
   URIs, it does not fetch — it has no HTTP client capability.
3. A `file://` resource link is functionally equivalent to mentioning the path
   in text. The main benefit is structured metadata (name, mime_type, size).
4. `EmbeddedResourceContentBlock` (v2 Phase 13) remains the only way to inject
   content the agent cannot access via its own tools (e.g. HTTP-fetched data,
   inline configs).

### Summary of content type support

| Block Type | Cursor Support | Notes |
|-----------|----------------|-------|
| `TextContentBlock` | Yes | Primary prompt content |
| `ImageContentBlock` | Yes | Base64 PNG/JPEG, with or without text |
| `EmbeddedResourceContentBlock` | Yes (inline) | Inline text works despite `embeddedContext: false` |
| `ResourceContentBlock` | Yes (URI hint) | `file://` resolved via agent tools; `http://` not fetched. Acts as a hint, not a fetch directive. |
| `AudioContentBlock` | No | `audio: false` in capabilities |

---

## 13. Plan Mode and AgentPlanUpdate

Phase 9 set the agent to Plan mode via `set_config_option` and sent a planning
prompt. The response included a structured plan update:

### AgentPlanUpdate structure

```json
{
  "sessionUpdate": "plan",
  "entries": [
    {
      "content": "Error handling for hello.py",
      "priority": "high",
      "status": "pending"
    }
  ]
}
```

Each plan entry has three fields:

- **`content`** — human-readable task description
- **`priority`** — severity/importance level (observed: `"high"`)
- **`status`** — task state (observed: `"pending"`)

Only 1 `AgentPlanUpdate` was emitted during the 38-second plan prompt. The update
arrived late (37.9s into the response), suggesting the agent builds the plan
internally during its think/respond cycle and emits the structured version near
the end.

### Plan mode does NOT restrict tool use

The agent in Plan mode still emitted `tool_call` events (file reads). The mode
description says "Read-only mode for planning and designing before implementation"
— "read-only" means no writes, but the agent still reads files to inform its plan.
This is consistent with Cursor's UI behavior where Plan mode produces plans but
won't execute changes.

### Autonomous mode switching — empirically tested (v3 Phase 19)

The user noted observing the agent sometimes switching modes on its own during
regular conversations. Phase 19 tested this directly by prompting the agent to
"plan your approach, then execute it" and "switch between plan and agent modes
as you see fit."

**Results**: Zero `CurrentModeUpdate` events. Zero `AgentPlanUpdate` events. The
agent stayed in Agent mode throughout, planning within its text response and then
implementing — all without triggering any mode-switch notifications.

**This is a definitive negative result.** Mode switching via ACP is
**IDE-mediated, not agent-initiated**. The autonomous mode switching observed in
Cursor's IDE is triggered by the IDE's own logic (possibly analyzing the agent's
system prompt output or tool calls), not by the agent emitting ACP notifications.

**Implications for tak**: tak must implement its own mode-switching logic if it
wants agent mode to change automatically based on task phase. It cannot rely on
the agent switching modes via ACP. Options:
1. Explicit user control only (the simplest path).
2. tak heuristics (e.g. detect planning language in thought chunks → switch to
   Plan mode display, detect tool calls → switch to Agent mode display).
3. System prompt instructions that tell the agent to use `set_config_option` to
   switch modes, though this relies on agent compliance.

**Implications for tak TUI**:

1. **Plan display widget**: The `AgentPlanUpdate` entries can populate a structured
   plan view — a checklist with content, priority badges, and status indicators.
   This maps naturally to a Textual `DataTable` or custom widget.

2. **Mode indicator**: Show the current mode prominently. Update it reactively
   via `CurrentModeUpdate` notifications (fires for mode changes, whether
   initiated by the user or the agent).

3. **Mode controls**: Expose Plan/Agent/Ask mode switching in the TUI, routed
   through `set_config_option("mode", value)`. The TUI can show mode descriptions
   from `config_options` as tooltips or in a mode picker.

---

## 14. AvailableCommandsUpdate — Slash Command Discovery

The v2 data revealed that `AvailableCommandsUpdate` events fire at the start of
each prompt response cycle. These contain the agent's full command registry:

```json
{
  "sessionUpdate": "available_commands_update",
  "availableCommands": [
    {"name": "copy-request-id", "description": "Copy the last request ID to clipboard"},
    {"name": "create-rule", "description": ">- (builtin skill)"},
    ...
  ]
}
```

The command list includes both built-in Cursor commands and user-configured custom
commands (team-specific skills, workspace rules, etc.). Each command has a `name`
and `description`.

**Implications for tak**:

- These commands are the agent's slash-command vocabulary. A TUI implementing `/`
  command completion could use this list as the autocomplete source.
- The list may change between prompts if the agent's context changes (e.g. after
  switching projects). Caching should be refreshed on each `AvailableCommandsUpdate`.
- Custom team commands may contain sensitive descriptions. Reports and logs that
  include this data should sanitize or omit custom command details.

---

## 15. MCP Tool Discovery — The Full Journey

MCP tool integration in ACP mode was the most investigated topic across v2 and
v3, progressing through four rounds of testing and two external documentation
discoveries before reaching the root cause. This section documents the full
diagnostic chain.

### Round 1 (v2 Phase 14): `new_session(mcp_servers=[McpServerStdio(...)])`

The first test passed a stdio MCP server config directly to `new_session()`:

```python
new_session(mcp_servers=[McpServerStdio(
    command="python", args=["mock_mcp_echo.py"], name="tak-test-echo"
)])
```

**Result**: Session created successfully, but the agent could not find the echo
tool. It reported only built-in tools plus "two MCP resource tools" (the
Cursor-level `list_mcp_resources` and `fetch_mcp_resource`).

**Initial hypothesis**: Transport mismatch. The `initialize` response declares
`mcpCapabilities: {http: true, sse: true}` with no stdio mention. We guessed
Cursor only supports HTTP/SSE MCP transport.

### Round 2 (v3 Phase 16): `new_session(mcp_servers=[HttpMcpServer(...)])`

To test the transport hypothesis, we created `mock_mcp_http.py` (an HTTP mock
MCP server using stdlib `http.server`) and passed it via `HttpMcpServer`:

```python
new_session(mcp_servers=[HttpMcpServer(
    type="http", name="tak-test-echo-http",
    url=f"http://127.0.0.1:{port}/", headers=[]
)])
```

**Result**: Same failure. The agent still could not find MCP tools. Both stdio
AND HTTP transports failed identically when configured through `new_session()`.

**Revised hypothesis**: The transport is not the issue. Something about how
MCP servers are configured or approved is wrong.

### Root cause discovery: `.cursor/mcp.json`

Reviewing the [Cursor ACP docs](https://cursor.com/docs/cli/acp) and
[Cursor MCP docs](https://cursor.com/docs/mcp) revealed:

> ACP supports MCP servers defined in a project-level or user-level
> `.cursor/mcp.json`. Launch `agent` from your project directory and approve
> the servers you want to use.

Cursor reads MCP server configs from `.cursor/mcp.json` in the project
directory — **not** from the `new_session(mcp_servers=[...])` ACP parameter.
The `new_session()` param is an ACP SDK construct. Cursor accepts it silently
but never connects to the servers defined there.

### Round 3 (v3b Phase 21): `.cursor/mcp.json` + new agent process

Phase 21 spawned a **second** agent process with a properly structured
`.cursor/mcp.json` in the temp workspace before the agent started:

```json
{
  "mcpServers": {
    "tak-test-echo": {
      "command": "python",
      "args": ["mock_mcp_echo.py"]
    },
    "tak-test-echo-http": {
      "url": "http://127.0.0.1:57127/"
    }
  }
}
```

**Result — tool discovery**: The agent's tool listing included `list_mcp_resources`
and `fetch_mcp_resource` but said: _"I don't have a built-in tool that lists
MCP tools (only MCP resources)."_ The agent could not natively invoke MCP tools.

**Result — workaround**: When asked to use the echo tools, the agent improvised:
it manually spawned the stdio server via Shell and piped JSON-RPC messages, and
used `curl` for the HTTP server. Both workarounds produced correct results
(`Echo: hello from tak`, `Echo: hello via HTTP`).

### Round 3b (v3c): Adding `"type": "stdio"` to config

The [Cursor MCP docs](https://cursor.com/docs/mcp#stdio-server-configuration)
list `type` as a required field for stdio servers, though their own examples
omit it. We added `"type": "stdio"` to the config.

**Result**: The agent now **described** the echo tool by name in its tool listing
(_"Tool: echo — echoes back the given text"_), showing improved awareness. But
it still could not invoke the tool natively — it still said _"I don't have an
echo tool in my callable tool set"_ and fell back to shell workarounds.

This confirmed the agent reads `.cursor/mcp.json` and can describe its contents,
but tool invocation is a separate mechanism.

### Round 3c (v3d): Server-side logging

Added file-based logging to `mock_mcp_echo.py` via the `MCP_ECHO_LOG_FILE` env
var, passed through `.cursor/mcp.json`'s `env` config.

**Result**: The log file was **never created**. Cursor never started the MCP
server process. The agent's knowledge of the echo tool came from reading the
`.cursor/mcp.json` file with its `read_file` tool, not from MCP protocol
negotiation.

### Root cause confirmed: MCP approval middleware bug

A [Cursor community forum post](https://forum.cursor.com/t/mcp-servers-passed-via-session-new-dont-work-in-acp-mode/153823)
(March 2026) confirmed this is a **known bug**:

> MCP servers passed via `session/new` don't work in ACP mode. The approval
> middleware blocks them silently, and there's no ACP-compatible way to approve.
>
> - `--approve-mcps` is not wired to ACP (only affects the interactive CLI path)
> - `--yolo`/`--force` bypasses tool permissions but not MCP approval

The MCP approval flow is broken in ACP mode. Cursor loads the server configs
from `.cursor/mcp.json`, but the approval middleware silently blocks them before
the agent can connect. The servers are never started.

### Workaround: pre-created approval file

The forum post documents a workaround — pre-creating the MCP approval file:

```
~/.cursor/projects/<slug>/mcp-approvals.json
```

Where `<slug>` is the CWD with non-alphanumeric characters replaced by `-`, and
the approval key is `${name}-${sha256(JSON.stringify({path: cwd, server: {...}})).hex.slice(0, 16)}`.

With the pre-approval file in place, the poster confirmed MCP tools work:
`"Kiwi tool called: YES"`.

### Round 4 (v3e): Pre-approval file + `cursor agent mcp enable`

We confirmed the workaround works in two ways:

**Programmatic pre-approval**: Computed the approval key hash
(`sha256(JSON.stringify({path, server}, compact))[:16]`) and wrote the approval
file before spawning the agent. Result: **MCP tools became natively callable.**
The agent listed `mcp_tak-test-echo-http_echo` as a real tool, invoked it
directly via `MCP: tool` (not shell workarounds), and got results in 3.9s
(vs 60s+ with shell workarounds in v3b).

**`cursor agent mcp enable <name>`**: Discovered this is the official CLI
command for approving MCP servers. It reads `.cursor/mcp.json` from the CWD,
computes the hash internally, and writes the approval file. Clean output:
`"✓ Enabled and approved MCP server: test-echo"`. Takes ~1.5s per server.

Additional CLI commands discovered:

| Command | Purpose |
|---------|---------|
| `cursor agent mcp list` | Show configured MCP servers and their status |
| `cursor agent mcp enable <name>` | Approve an MCP server for the current workspace |
| `cursor agent mcp disable <name>` | Remove approval for an MCP server |
| `cursor agent mcp list-tools <name>` | List tools exposed by a specific MCP server |
| `cursor agent mcp login <name>` | Authenticate with an OAuth-based MCP server |
| `cursor agent --approve-mcps` | Auto-approve all MCPs (interactive mode only) |

**Note on stdio vs HTTP**: In v3e, the HTTP server's echo tool was discovered
and callable, but the stdio server still was not started. The config included
`"type": "stdio"` and `"env"` fields which may affect the hash computation
vs what the approval key expects. The HTTP server config (just `{"url": "..."}`)
matched cleanly. For production use, `cursor agent mcp enable` avoids this
issue entirely since it computes the correct hash internally.

### Summary of MCP investigation

| Round | Config Method | Result | Root Cause |
|-------|--------------|--------|------------|
| v2 Phase 14 | `new_session(McpServerStdio)` | Tools not found | `new_session()` param silently ignored |
| v3 Phase 16 | `new_session(HttpMcpServer)` | Tools not found | Same — param ignored regardless of transport |
| v3b Phase 21 | `.cursor/mcp.json` (no type) | Resources only, no tools | Approval middleware blocks silently |
| v3c Phase 21 | `.cursor/mcp.json` (type: stdio) | Agent aware of tool, can't invoke | Config read but server never started |
| v3d Phase 21 | + server-side logging | Log never created | Confirms server never started |
| v3e Phase 21 | + pre-approval file | **HTTP MCP tool works natively** | Approval bypass confirms root cause |
| CLI test | `cursor agent mcp enable` | **Approval file created** | Official CLI mechanism confirmed |

### Implications for tak

1. **The `new_session(mcp_servers=[...])` parameter is currently inert** for
   Cursor. Do not rely on it. MCP servers must be configured via `.cursor/mcp.json`.

2. **MCP tools in ACP mode require pre-approval.** The recommended approach:
   - Read `.cursor/mcp.json` from the project directory
   - Run `cursor agent mcp enable <name>` for each server (or a filtered set)
   - Then spawn `cursor agent acp` as usual
   - Approval persists in `~/.cursor/projects/<slug>/mcp-approvals.json`
     so re-enable is only needed once per project per server.

3. **tak should expose a `--with-mcp` flag** on spawn:
   ```
   tak spawn cursor myagent --project /path --with-mcp          # enable all
   tak spawn cursor myagent --project /path --with-mcp '*'      # same, glob
   tak spawn cursor myagent --project /path --with-mcp ado      # specific server
   tak spawn cursor myagent --project /path --with-mcp 'tak-*'  # glob pattern
   tak spawn cursor myagent --project /path                     # no MCP approval
   ```
   The driver reads `.cursor/mcp.json`, filters server names by the
   argument, and calls `cursor agent mcp enable` for each match before
   spawning ACP.

4. **MCP resources work without approval.** The `list_mcp_resources` and
   `fetch_mcp_resource` built-in tools are always available. tak can expose
   data to the agent via MCP resources even without tool approval.

5. **The `mcpCapabilities: {http: true, sse: true}` declaration** refers to
   transport support, not whether MCP actually works in ACP mode. Both stdio
   and HTTP configs are read from `.cursor/mcp.json`; the capability flags
   describe what the agent *can* do, not what ACP mode currently allows.

6. **Other ACP agents may handle MCP differently.** The approval bug is
   Cursor-specific. tak's MCP integration should be generic, with per-provider
   configuration for how MCP servers are registered and approved.

---

## 16. Java/TypeScript Compilation (v3 Phase 15)

Phase 15 tested whether the agent can compile and run Java and TypeScript code
in the sandboxed workspace (seed files `Hello.java` and `hello.ts` were present).

### Java

- **Prompt**: "Compile and run Hello.java using javac and java."
- **Result**: Success. `javac Hello.java` produced `Hello.class`, `java Hello`
  printed `"Hello from Java!"`. Single Terminal permission request. 13.6s.
- The agent found `javac` and `java` on the system PATH without assistance.

### TypeScript

- **Prompt**: "Run hello.ts. Try using ts-node, tsx, or compile with tsc first."
- **Result**: Success after fallback chain. The agent tried:
  1. `tsx hello.ts` — not found
  2. `ts-node hello.ts` — not found
  3. `tsc hello.ts` — not found
  4. `npx tsx hello.ts` — **success**, printed `"Hello from TypeScript!"`
- Four Terminal permission requests (one per attempt). 33.0s total.

### Key findings

1. The agent handles missing toolchains gracefully — it tries alternatives in a
   logical order and falls back to `npx` for on-demand package fetching.
2. Each shell attempt triggers a separate permission request. A policy of
   "allow all Terminal for this session" would streamline multi-step toolchain
   exploration.
3. Java toolchains are typically system-installed; TypeScript toolchains depend
   on `node_modules` or global npm packages. The agent correctly adapts its
   strategy based on what's available.

---

## 17. Multi-Session Isolation (v3 Phase 20)

Phase 20 created two concurrent sessions (A and B) on the same ACP connection
and tested whether conversation context bleeds between them.

### Setup

- Session A: `new_session(cwd=tmpdir)` → secret word "ALPHA"
- Session B: `new_session(cwd=tmpdir)` → secret word "BRAVO"

### Results

| Prompt | Session | Expected | Actual |
|--------|---------|----------|--------|
| "What is the secret word?" | A | ALPHA | **ALPHA** |
| "What is the secret word?" | B | BRAVO | **BRAVO** |

**Perfect isolation.** No cross-bleed between sessions sharing the same
connection and workspace directory.

### Implications for tak

1. **N agents, one connection**: tak can multiplex multiple logical agents
   (each with their own session) over a single ACP connection to a Cursor
   process. Sessions are fully isolated.
2. **Shared workspace is safe**: Two sessions can operate in the same `cwd`
   without their conversation histories interfering.
3. **Session IDs are the isolation boundary**: All prompt routing depends on
   `session_id`. tak must never mix up session IDs between agents.

---

## 18. Cursor ACP Extension Methods

The [Cursor ACP docs](https://cursor.com/docs/cli/acp) document extension
methods that Cursor sends for richer client UX:

| Method | Purpose | Response |
|--------|---------|----------|
| `cursor/ask_question` | Ask users multiple-choice questions | Question + options |
| `cursor/create_plan` | Request explicit plan approval from user | Plan entries |
| `cursor/update_todos` | Notify client about todo state changes | Todo list |
| `cursor/task` | Notify client about subagent task completion | Task result |
| `cursor/generate_image` | Notify client about generated image output | Image data |

Our inspection script's `RecordingClient` catches these generically via its
`ext_method` handler, returning `{}` for all of them. The agent continues
working after receiving the empty response.

### Observed behavior

During v3 testing, the agent invoked `cursor/ask_question` (observed as the
`AskQuestion` tool in the system prompt), `cursor/update_todos` (the
`TodoWrite` tool), and `cursor/task` (the `Task`/`mcp_task` subagent tool).
These map directly to the Cursor IDE's interactive features:

- **`cursor/ask_question`** → the multi-choice question widget in Cursor's chat
- **`cursor/create_plan`** → the plan approval dialog
- **`cursor/update_todos`** → the task list sidebar
- **`cursor/task`** → background subagent orchestration
- **`cursor/generate_image`** → image generation display

### Implications for tak

These extension methods are the bridge between the agent's IDE-aware capabilities
and the client's UI. For full-fidelity tak integration:

1. **`cursor/ask_question`**: tak should present the question and options to the
   user and return their selection. Without this, the agent gets empty responses
   and may not get the clarification it needs.
2. **`cursor/create_plan`**: tak should display the plan and return an approval
   signal. This enables the "plan then execute" workflow.
3. **`cursor/update_todos`**: tak can use these to populate a task progress view.
4. **`cursor/task`**: tak should acknowledge subagent completions. The agent uses
   subagents for complex multi-step work.
5. **`cursor/generate_image`**: tak should handle image output (display or save).

Implementing these properly transforms tak from a "text pipe to the agent" into
a first-class client that matches Cursor IDE capabilities.

---

## 19. `PromptResponse.content` — Non-Gap (Resolved)

The v2 gaps table listed "PromptResponse.content blocks" as untested. Review
of the ACP SDK source confirms this was a misunderstanding:

**`PromptResponse` has only two fields**: `stop_reason: StopReason` and
`usage: Optional[Usage]`. There is no `content` field.

All agent response content arrives via streaming `AgentMessageChunk` session
updates — not in the `PromptResponse` itself. The response object is purely a
completion signal (why the agent stopped) and optional usage metadata.

This is consistent with the streaming architecture: the agent streams content
incrementally via `session/update` notifications, and `PromptResponse` signals
that the stream is complete.

---

## 20. Gaps — Current State

### Filled in v2

| Gap | Finding | Section |
|-----|---------|---------|
| `UsageUpdate` events | Definitively null — Cursor does not expose usage data | §10 |
| Permission rejection | Retry-once-then-fallback pattern, graceful degradation | §6 |
| `set_config_option` | Works for both mode and model, fires mode notifications | §4 |
| `load_session` / `resume` | `load_session` works despite `resume: null` capability | §11 |
| MCP servers not passed | `mcp_servers` param accepted but tool discovery failed | §15 |
| Streaming timestamp precision | Fixed — per-prompt monotonic offsets now captured | Script update |
| Longer-running tasks | 59.4s task profiled with detailed timeline analysis | §5 |
| Image prompt capability | Works (with text, without text, embedded resource) | §12 |
| Attachment types beyond images | `EmbeddedResourceContentBlock` works for inline text | §12 |

### Filled in v3

| Gap | Finding | Section |
|-----|---------|---------|
| Java/TypeScript compilation | Java: javac/java work. TypeScript: npx tsx fallback. Agent handles missing toolchains gracefully. | §16 |
| MCP tool discovery | Root cause: approval middleware bug in ACP mode, not transport mismatch. `.cursor/mcp.json` read but servers never started. Workaround exists (pre-approval file). Known bug confirmed by Cursor team. | §15 |
| `load_session` conversation recall | **History survives.** Agent recalled PHOENIX42 after `load_session`. Critical for daemon restart reconnection. | §11 |
| Agent-initiated mode switching | Zero `CurrentModeUpdate` events. Mode switching is IDE-mediated, not agent-initiated via ACP. | §13 |
| `PromptResponse.content` blocks | **Non-gap.** `PromptResponse` only has `stop_reason` and `usage`. Content arrives via streaming `AgentMessageChunk`. | §19 |
| `ResourceContentBlock` (URI-based) | `file://` works (resolved via agent tools). `http://` accepted but not fetched. Acts as hint, not fetch directive. | §12 |
| Multi-session interactions | Perfect isolation. ALPHA/BRAVO recalled correctly across concurrent sessions, no cross-bleed. | §17 |

### Filled in v3e

| Gap | Finding | Section |
|-----|---------|---------|
| MCP tool invocation via pre-approval | **Confirmed working.** Programmatic pre-approval enables HTTP MCP tools. `cursor agent mcp enable <name>` is the recommended approach (official CLI, correct hash). Stdio still has edge cases. Design sketch for `--with-mcp` flag documented. | §15 |

### Remaining gaps

| Gap | Impact | Suggested Follow-Up |
|-----|--------|---------------------|
| `AudioContentBlock` | Untested (Cursor declares `audio: false`) | Test against an agent that supports audio when tak adds voice. |
| `agentInfo` field is null | No agent metadata beyond capabilities | May be populated in future ACP versions. |
| Extension method fidelity | `cursor/ask_question`, `cursor/create_plan`, etc. receive `{}` responses; untested with proper payloads | Implement proper handlers for each extension method and verify the agent uses the returned data. |
| `session/cancel` during tool execution | We tested cancel on in-flight prompts but not during active tool calls | Send a long-running prompt that triggers tool calls, cancel mid-tool, verify session health. |
| MCP resource discovery | `list_mcp_resources` and `fetch_mcp_resource` exist as built-in tools but were not exercised with real MCP resources | Configure an MCP server that exposes resources (not just tools) and test resource listing/fetching. |
| MCP stdio server startup in ACP | HTTP MCP works with approval but stdio server was never started in v3e. May be a hash input mismatch (extra `type`/`env` fields) or a deeper Cursor bug. | Test with minimal stdio config (just `command`+`args`, no `type`/`env`) or rely on `cursor agent mcp enable` which handles it internally. |

---

## 21. Ideation & Application — UX Signals from Streaming

### Concept: Agent Activity Phases

Based on the streaming data, a tak client can present four distinct visual states:

```
┌──────────┐    ┌─────────────┐    ┌──────────┐    ┌──────────┐
│ ● IDLE   │───▶│ ◉ THINKING  │───▶│ ▶ ACTING  │───▶│ ✎ TYPING │
│          │    │             │    │           │    │          │
│ awaiting │    │ thought     │    │ tool_call │    │ message  │
│ input    │    │ chunks      │    │ + updates │    │ chunks   │
└──────────┘    └──────────────┘    └──────────┘    └──────────┘
                      │                  │                │
                      └──────────────────┴────────────────┘
                              (cycles repeat)
```

The `tak menu` TUI and/or terminal status line could show:

1. **Thinking** (pulsing indicator) — when `agent_thought_chunk` events arrive.
   Duration: typically 0.3–1.3 seconds per cycle.
2. **Working on: [tool name]** — when `tool_call` arrives. Show the `title` field
   ("Edit File", "Read File", "Terminal"). Update to "done" on final `tool_call_update`.
3. **Responding** (streaming text) — when `agent_message_chunk` arrives. Could
   stream the text character-by-character or chunk-by-chunk to the terminal.

### Concept: Multi-Cycle Progress (refined with v2 data)

The Phase 11 long task showed 17 think→act cycles across 59.4 seconds, a much
richer dataset than the Phase 6 Fibonacci prompt. A progress model could track:

```
Cycle 1: Thinking → Created fib.py (Edit File)
Cycle 2: Thinking → Checked lints (Read Lints)
Cycle 3: Thinking → Explained result
```

Each cycle could appear as a step in a collapsible progress view, giving the user
a sense of how far the agent has progressed.

### Concept: Smart Timeout with Heartbeat

Instead of a fixed timeout, use streaming events as a heartbeat:

```python
last_event_time = now()

while waiting:
    if now() - last_event_time > INACTIVITY_TIMEOUT:
        # Agent appears hung — offer cancel
        show_cancel_prompt()
    
    on_any_update:
        last_event_time = now()  # reset timer
```

The inspection showed that 2 seconds produced 0 events, while active prompts stream
events continuously. An inactivity timeout of 15-30 seconds would catch truly stuck
agents while tolerating normal processing gaps.

### Concept: Permission Request UX

Only `Terminal` commands require permission. The UI could:

1. Show a permission prompt with the command to be executed.
2. Offer "Always allow for this session" / "Allow once" / "Deny".
3. In @ai terminal mode, the permission could be shown inline in the terminal
   with a keypress to approve/deny.

### Concept: Thought Stream as a Supervision Channel

The `agent_thought_chunk` data isn't just a debug curiosity — it's an active
supervision signal. In practice (observed in Cursor's own UI), the thought stream
reveals:

- **Loop detection**: When the agent keeps revisiting the same details or
  re-reading the same files, a human can spot the pattern and interrupt with
  corrective context before the agent wastes tokens and time.
- **Directional drift**: When the agent's reasoning diverges from the user's
  intent, early fragments of thought make this visible well before the agent
  commits to a wrong approach.
- **Tool call spin**: Repeated identical or near-identical tool calls become
  obvious in the thought stream before they surface in the final output.

These are signals that are trivially detectable from streaming data but completely
invisible if you only see the final response.

**Terminal adaptation**: While a terminal lacks the rich overlay of Cursor's UI,
iTerm2 natively supports split panes, and scrolling text is actually well-suited
to displaying a thought stream. Possible approaches:

1. **Split pane**: Dedicate a narrow pane to the live thought stream, scrolling
   alongside the main agent output. The pane could use dimmed/italic text to
   visually distinguish reasoning from output.
2. **Collapsible sections**: In the TUI, show thought chunks as expandable
   sections between tool calls (collapsed by default, expandable on demand).
3. **Pattern detection**: Automatically flag repetitive patterns in thought
   chunks (e.g. same file read 3+ times, same phrase repeated) and surface
   a warning: "Agent may be stuck — consider interrupting."
4. **Session transcript**: Log all thought chunks to a file for post-hoc review,
   enabling "why did you do that?" analysis after a session.

### Concept: Plan Mode Integration in TUI

The `AgentPlanUpdate` data (section 13) enables a plan view that updates live:

```
┌─ Agent Plan ──────────────────────────────────┐
│                                               │
│  ● Error handling for hello.py       HIGH     │
│    status: pending                            │
│                                               │
│  ○ Input validation for data.json    MEDIUM   │
│    status: pending                            │
│                                               │
└───────────────────────────────────────────────┘
```

The plan widget could:

1. Appear automatically when the agent is in Plan mode (detected via
   `CurrentModeUpdate`).
2. Update entries live as `AgentPlanUpdate` events arrive.
3. Allow the user to approve the plan and switch to Agent mode for execution,
   using `set_config_option("mode", "agent")`.

### Concept: Session Reconnection on Daemon Restart

Given that `load_session` works (section 11), tak can implement resilient
session management:

```
Daemon starts → load state.yaml → for each saved agent:
  1. spawn_agent_process()
  2. initialize + authenticate
  3. load_session(session_id=saved_id)
     - Success → agent reconnected, prior context preserved
     - Error → new_session() as fallback
  4. Update state.yaml with session_id
```

This means a daemon restart doesn't necessarily lose agent context. The UX
improvement is significant — the user doesn't have to re-explain their task
after a daemon crash or system update.

### Concept: Mode-Aware Agent Status Display

The `CurrentModeUpdate` notification enables real-time mode display:

```
┌─ myagent (Cursor) ──────────────────────┐
│  Model: Opus 4.6     Mode: [Plan]       │
│  Status: ◉ Thinking  Elapsed: 12s       │
│  Last: "Reading project structure..."    │
└──────────────────────────────────────────┘
```

The mode badge `[Plan]` / `[Agent]` / `[Ask]` updates reactively. When the agent
autonomously switches modes (observed in Cursor IDE), the TUI reflects the change
immediately without user action — the `CurrentModeUpdate` event handles this.

### Concept: Permission Rejection Policy

Phase 10 proved that permission rejection is safe and well-handled. This enables
a configurable safety policy per agent:

```yaml
# ~/.tak/config.yaml
agents:
  unattended-reviewer:
    provider: cursor
    permissions:
      terminal: deny      # never allow shell execution
      file_write: prompt   # ask before writes
      file_read: allow     # auto-approve reads
```

When a tool is denied by policy, the agent gracefully degrades (retry once, then
explain). The TUI could show a "permission denied" indicator and optionally let the
user override the policy for a single call.

### Concept: Model Picker with Capabilities

The inspection captured the full model catalog with parameters. A model picker could
display:

```
┌─────────────────────────────────────────────────┐
│ Model               │ Thinking │ Context │ Speed │
│─────────────────────│──────────│─────────│───────│
│ ● Auto              │   —      │   —     │  —    │
│   Opus 4.6          │  ✓ high  │  200k   │ slow  │
│   Sonnet 4.6        │  ✓ med   │  200k   │  —    │
│   GPT-5.4           │  ✓ med   │  272k   │ slow  │
│   Codex 5.3         │  ✓ med   │   —     │ slow  │
│   Codex 5.3 Spark   │  ✓ med   │   —     │ fast  │
│   Haiku 4.5         │  ✓       │   —     │ fast  │
│   ...               │          │         │       │
└─────────────────────────────────────────────────┘
```

The bracket parameters can be parsed: `fast=false` → "slow", `context=200k` →
"200k", `thinking=true` + `effort=high` → "✓ high".

A `tak models <agent-name>` command could return the full model catalog with
parsed capabilities for the named agent. The same data powers a TUI model picker
for switching models mid-session. In both cases the display uses human-friendly
names; the full `model_id` (with bracket suffix) is kept internally for API calls.

### Concept: Implicit Agent Targeting via Tab Association

Currently, most `tak` commands require an explicit agent name:

```
tak prompt myagent "refactor the auth module"
tak models myagent
tak stop myagent
```

This is friction. tak already maintains a session registry mapping tabs to agents.
If a command is run from a tab that has an associated agent, the agent name should
be inferred automatically:

```
tak prompt "refactor the auth module"   # uses the agent attached to this tab
tak models                             # shows models for this tab's agent
tak stop                               # stops this tab's agent
```

The explicit name form remains available for cross-tab operations or when multiple
agents exist, but the common case — one agent per tab, commands issued from that
tab — should just work without extra typing.

This extends to other context-dependent defaults:

- **`--project`**: If not specified and the agent has a `project_path`, use it.
  If neither is set, use the tab's current working directory.
- **`--model`**: If not specified, keep whatever the agent's current model is.
- **`--mode`**: Default to the agent's current mode.

The principle: pick sensible defaults from the current context. Only require
explicit arguments when the context is ambiguous or the user wants to override.

### Concept: Agent Server Model (Beyond CLI Spawn)

Today, tak spawns agents as subprocesses via CLI commands (`cursor agent`). The
ACP connection is established over stdio to that child process. This is the
**CLI-spawned** model:

```
tak daemon  →  spawn_agent_process("cursor", "agent")  →  child process
            →  ACP connection over stdio to child
```

A natural evolution is the **agent server** model: the agent is already running
(as a long-lived service, a cloud endpoint, or a shared team resource), and tak
connects to it over a network transport (HTTP, SSE, WebSocket) rather than
spawning a subprocess:

```
tak daemon  →  ACP connection over HTTP/SSE to existing agent server
```

This shifts several things:

- **Session persistence becomes essential**: In the CLI model, sessions are
  ephemeral — the subprocess dies, the session dies. In the server model, the
  agent persists across client connections. `load_session` and `resume` (currently
  `null` in Cursor) become the primary session management mechanisms.
- **No subprocess CWD**: There's no OS-level `cwd` to set — the agent's workspace
  context comes entirely from the ACP `cwd` parameter in `new_session` /
  `load_session`.
- **Connection lifecycle**: Instead of "spawn + connect + session", it's "connect
  + authenticate + load-or-create session". The `initialize` → `authenticate`
  handshake still applies, but there's no process to manage.
- **Shared agents**: Multiple tak instances (or users) could connect to the same
  agent server, each with their own session. Session listing (`session/list`)
  becomes relevant for discovering existing sessions.
- **The driver split matters more**: The `core/` layer would handle both models
  through a common interface, while `providers/` would have separate
  implementations for CLI-spawned vs. server-connected agents.

This is forward-looking — no current ACP agent implements the server model with
full session persistence. But the protocol already has the primitives (`list`,
`fork`, `resume` in `sessionCapabilities`), and the architecture should not
preclude it.

---

## 22. Summary of Actionable Findings

### Immediate fixes (model display bug)

| # | Action | File |
|---|--------|------|
| 1 | Escape Rich markup in CLI table values | `cli/main.py` |
| 2 | Add fallback model name resolution (strip `[]`, case-insensitive) | `providers/acp_session.py` |
| 3 | Add debug logging for raw model payload | `providers/acp_session.py` |
| 4 | Update test mocks with real `NewSessionResponse` payloads | `tests/` |

### Architecture improvements

| # | Action | File |
|---|--------|------|
| 5 | Pass `cwd` to `spawn_agent_process` in addition to `new_session` | `providers/acp.py` |
| 6 | Check `sessionCapabilities` before calling list/fork/resume | `providers/acp_session.py` |
| 7 | Parse `config_options` for descriptions, expose in agent info | `providers/acp_session.py` |
| 8 | Implement inactivity-based timeout (10–15s warning, 30s+ stuck) instead of fixed duration | `providers/acp_session.py` |
| 9 | Use `set_config_option` as primary mutation path for mode/model | `providers/acp_session.py` |
| 10 | Implement session reconnection via `load_session` on daemon restart | `providers/acp_session.py`, `core/state.py` |
| 11 | Store `session_id` in agent state persistence | `core/agent_manager.py` |
| 12 | Handle `PromptResponse.usage` as null gracefully (display "—") | `providers/acp_session.py` |
| 13 | Configure MCP servers via `.cursor/mcp.json` in project dir, not `new_session()` param | `providers/acp.py` |
| 14 | Implement Cursor extension method handlers (`cursor/ask_question`, `cursor/create_plan`, `cursor/update_todos`, `cursor/task`, `cursor/generate_image`) | `providers/acp_session.py` |
| 15 | Session reconnection: `load_session` first, `new_session` fallback (v3 confirmed recall works) | `providers/acp_session.py`, `core/state.py` |
| 16 | MCP pre-approval via `cursor agent mcp enable <name>` before ACP spawn | `providers/acp.py` |
| 17 | `--with-mcp` flag on `tak spawn` / `tak prompt` to selectively enable MCP servers | `cli/main.py`, `providers/acp.py` |
| 18 | Read `.cursor/mcp.json` from project dir to discover server names for `--with-mcp` | `providers/acp.py` |

### UX features (future)

| # | Feature | Leverages |
|---|---------|-----------|
| 16 | Agent activity phase indicator (thinking/working/responding) | Streaming update types |
| 17 | Tool call progress display ("Working on: Edit File") | `tool_call.title` |
| 18 | Soft elapsed-time feedback + inactivity detection | Streaming heartbeat, v2 thresholds |
| 19 | Input preemption (new prompt cancels in-flight) | `session_cancel` + re-prompt |
| 20 | Model picker / `tak models` command with parsed capabilities | Model ID bracket params |
| 21 | Thought stream as supervision channel (configurable verbosity) | `agent_thought_chunk` content |
| 22 | Multi-cycle progress tracking | Phase transition detection |
| 23 | Implicit agent targeting from tab association | Session registry |
| 24 | Context-aware defaults (project, model, mode from current state) | `AgentHandle` + tab CWD |
| 25 | Plan mode view (structured plan entries, approve-and-execute flow) | `AgentPlanUpdate` events |
| 26 | Mode indicator + reactive mode badge in TUI | `CurrentModeUpdate` notifications |
| 27 | Permission rejection policy (per-agent tool allow/deny config) | Permission callback + v2 rejection data |
| 28 | Slash command completion from agent's command registry | `AvailableCommandsUpdate` events |
| 29 | Session reconnection on daemon restart (transparent to user) | `load_session` + state persistence (v3 confirmed) |
| 30 | Image attachment in TUI (paste or file path) | `ImageContentBlock` support confirmed |
| 31 | Multi-choice question UI for `cursor/ask_question` | Extension method §18 |
| 32 | Plan approval dialog for `cursor/create_plan` | Extension method §18 |
| 33 | Subagent task display for `cursor/task` | Extension method §18 |

---

## 23. Inspection Script Evolution

The v2 update implemented several previously planned capabilities:

**Now implemented**:
- **Phase selection**: `--phases 8 9 10`, `--gaps-only`, `--v3-only`,
  `--output-suffix _v2` CLI arguments allow targeted runs.
- **21 phases** covering handshake, models/modes, prompts, permissions, CWD,
  streaming, edge cases, usage, config options, permission rejection, long tasks,
  session load, image/resource content, MCP discovery, Java/TypeScript compilation,
  HTTP MCP transport, session recall, ResourceContentBlock, mode switching,
  multi-session isolation, and MCP via `.cursor/mcp.json` with separate agent spawn.
- **Per-prompt monotonic timestamps** for accurate timeline analysis.
- **Full `PromptResponse` capture** including `usage` and `response_raw` fields.
- **All 11 streaming update types** classified and logged.
- **Secret sanitization** in output files (API keys, tokens, JWTs redacted).
- **Two mock MCP servers**: `mock_mcp_echo.py` (stdio, Content-Length framed)
  and `mock_mcp_http.py` (HTTP, dual-purpose: MCP JSON-RPC + static resource).
- **Server-side logging** in `mock_mcp_echo.py` via `MCP_ECHO_LOG_FILE` env var
  for diagnosing whether Cursor actually starts MCP server processes.
- **Multi-agent-process support**: Phase 21 spawns a second agent process with
  its own `RecordingClient` and temp workspace.

- **MCP pre-approval** (v3e): Phase 21 updated to programmatically write
  `mcp-approvals.json` before spawning. Also tested `cursor agent mcp enable`
  CLI command as the recommended production approach.

**Future direction**:
- **Agent-agnostic core**: The ACP handshake, streaming capture, and report
  generation are protocol-level — they apply to any ACP agent. The
  Cursor-specific parts (spawn command, auth method) should be isolated so
  the same framework can inspect other ACP-compatible agents (Goose, Claude
  Code, future agents) with only a different startup configuration.
- **Reuse a running session**: For gap-filling, connect to an already-spawned
  agent and existing session rather than starting fresh. This enables
  incremental investigation without the 10+ second spawn overhead each time.
- **Extension method testing**: Implement proper handlers for `cursor/ask_question`,
  `cursor/create_plan`, etc. and verify the agent uses returned data correctly.

---

## 24. Agent CLI TUI Reference — Observed Patterns

These observations come from hands-on testing of Cursor CLI and Claude Code CLI.
Not all of these are ACP-specific — some are CLI TUI features, some are
terminal-level behaviors — but all are relevant to the experience tak aims to
provide.

### Input modes and prefixes

Both Cursor CLI and Claude Code CLI use single-character prefixes to switch
input context:

| Prefix | Function | Source |
|--------|----------|--------|
| `/` | Command palette — slash commands (`/exit`, `/create-rule`, etc.) | CLI TUI |
| `@` | File/path completion — references files in the project workspace | CLI TUI |
| `!` | Bash mode — run shell commands directly (see note below) | Claude Code |
| `&` | Background — run task in background | Claude Code |
| `/btw` | Side question — ask without interrupting current task | Claude Code |
| `?` | Help — show keyboard shortcuts | Claude Code |

### Keyboard shortcuts (Claude Code reference)

| Shortcut | Action |
|----------|--------|
| `ctrl + v` | Paste images from clipboard |
| `cmd + v` | Standard macOS paste (text/paths via terminal) |
| `ctrl + c` (first) | Clear input field |
| `ctrl + c` (second, within timeout) | Exit agent |
| `shift + tab` | Auto-accept edits |
| `ctrl + o` | Toggle verbose output |
| `meta + p` | Switch model |
| `ctrl + t` | Toggle tasks |
| `ctrl + s` | Stash prompt |
| `ctrl + shift + -` | Undo |
| `ctrl + z` | Suspend |
| `ctrl + g` | Edit in `$EDITOR` |
| `backslash + return` | Insert newline in prompt |
| `/keybindings` | Customize keybindings |

### Image attachment UX

- **CTRL+V** pastes clipboard image data as numbered attachments: `[Image #1]
  [Image #2]` etc.
- **↑ arrow** when editing the prompt enters attachment selection mode.
- **← →** navigate between attachments, **Delete** removes, **Esc** cancels.
- Attaching a file icon (e.g. copying a .md file in Finder, CTRL+V) pastes the
  file type thumbnail/icon — CTRL+V is purely about image clipboard data, not
  file content. File content is referenced via `@` path completion.
- The agent correctly processes pasted images and can describe their contents.

### CTRL+C double-tap exit

- First press: clears the current input field entirely.
- Displays a brief "press again to exit" overlay that times out after ~2 seconds.
- Second press within the timeout: exits the TUI.
- After timeout: returns to normal input mode, requiring the double-tap sequence
  again.

This prevents accidental exits while keeping the escape path fast.

### `!` bash mode — client vs agent execution

The `!` prefix runs shell commands from within the TUI. These appear to be
**client-side** commands (the TUI subprocess shells out locally), not commands
sent to the agent via `Terminal` tool calls. This is a convenience so the user
doesn't have to exit the TUI to run a quick `ls` or `git status`.

Claude Code is a local Node.js process — `!` almost certainly spawns a child
process in the local shell. There is no remote execution path today.

The distinction becomes significant in the agent server model: if the TUI is
running locally but the agent is on a remote server, the user may need **both**
execution contexts. Possible syntax differentiation:

- `!` — run in the **local** shell (where tak is running). Useful for `open .`,
  `pbcopy`, local git operations, clipboard access.
- `!!` or `!>` — run on the **agent's** machine (routed through the agent's
  Terminal tool or an SSH channel). Useful for `git status`, `make`, `npm test`
  on the remote where the code lives.

Which context is the default depends on the common case. With SSH+mux, the
remote context is likely more frequent (that's where the project is), so
`!` could default to remote with a `!local` or `!~` prefix for local. This
is a UX decision to make when the remote execution model is built out.

### `@` file completion and remote considerations

The `@` operator shows files in the project/workspace the agent is operating on.
This is workspace-relative, not local-machine-relative. If the agent were running
remotely (SSH + mux to a remote ACP server), `@` would reference remote files,
not local ones. This distinction matters for the agent server model (§21):
local clipboard operations (CTRL+V for images) are inherently client-side, while
`@` file references are server-side.

### Implications for tak's interaction modes

tak can support two distinct interaction modes:

1. **Command mode** (`tak prompt`, `tak stop`, `@ai`, `@tak`) — CLI commands and
   terminal triggers. Lightweight, works from any shell prompt, no full TUI
   required. The `@ai` prefix is the primary way to interact with an agent from
   the terminal without entering a full TUI session.

2. **TUI mode** (`tak tui` or `tak menu`) — a full-screen Textual-based interface
   with rich input handling: slash commands, `@` completion, image paste,
   streaming output, keyboard shortcuts, model switching. This is the "deep
   session" experience.

The two modes share the same backend (ACP sessions, IPC to daemon) but offer
different levels of interaction depth. Command mode commands could also work as
slash commands within TUI mode, providing a unified vocabulary across both
interaction surfaces.
