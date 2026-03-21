# Phase P: ACP Event Fidelity

## Goal

Properly capture, route, and expose all ACP event types and Cursor extension
methods so tak is a full-fidelity client, not just a text pipe. This is
foundational -- streaming (Phase N), TUI (Phase Q), and CLI display all
depend on structured event data.

## Context

The ACP protocol streams 11+ distinct update types through `session/update`
notifications, plus 5 Cursor-specific extension methods. Currently,
`TakACPClient.session_update()` only captures `AgentMessageChunk` text and
silently drops everything else. Extension methods return `{}` for most
types, meaning the agent gets no feedback from its questions, plans, or
task completions.

ACP analysis §5, §13, §14, §18 document the full event taxonomy:

| ACP Update Type | UX Phase | What it carries |
|-----------------|----------|-----------------|
| `AgentMessageChunk` | Responding | User-visible response text |
| `AgentThoughtChunk` | Thinking | Internal reasoning (not shown by default) |
| `ToolCallUpdate` | Working | Tool invocation start/progress/completion |
| `AgentPlanUpdate` | Planning | Structured plan entries with priority/status |
| `CurrentModeUpdate` | Mode change | New mode ID |
| `CurrentModelUpdate` | Model change | New model ID |
| `AvailableCommandsUpdate` | Commands | Slash command registry |

Extension methods (§18):

| Method | Purpose |
|--------|---------|
| `cursor/ask_question` | Multi-choice question for user |
| `cursor/create_plan` | Plan approval request |
| `cursor/update_todos` | Task state changes |
| `cursor/task` | Subagent task completion |
| `cursor/generate_image` | Image generation output |

## Files to Read First

- `src/tak/providers/acp_session.py` -- `TakACPClient` and `ACPSessionManager`
- `src/tak/providers/acp.py` -- `ACPProvider` wrapping session manager
- `src/tak/ipc/server.py` -- IPC dispatch (will need event routing)
- `docs/research/agents/cursor-acp-behavior/analysis.md` -- §5, §13, §14, §18

## What to Build

### 1. SessionEvent Dataclass Hierarchy (pp-event-model)

Define a typed event model in a new file `src/tak/core/events.py`:

```python
from dataclasses import dataclass
from enum import Enum

class EventType(Enum):
    TEXT_CHUNK = "text_chunk"
    THOUGHT_CHUNK = "thought_chunk"
    TOOL_START = "tool_start"
    TOOL_PROGRESS = "tool_progress"
    TOOL_DONE = "tool_done"
    PLAN_UPDATE = "plan_update"
    MODE_CHANGE = "mode_change"
    MODEL_CHANGE = "model_change"
    COMMANDS_UPDATE = "commands_update"

@dataclass
class SessionEvent:
    event_type: EventType
    session_id: str

@dataclass
class TextChunk(SessionEvent):
    text: str

@dataclass
class ThoughtChunk(SessionEvent):
    text: str

@dataclass
class ToolStart(SessionEvent):
    tool_call_id: str
    title: str

@dataclass
class ToolProgress(SessionEvent):
    tool_call_id: str
    content: str

@dataclass
class ToolDone(SessionEvent):
    tool_call_id: str
    title: str

@dataclass
class PlanEntry:
    content: str
    priority: str
    status: str

@dataclass
class PlanUpdate(SessionEvent):
    entries: list[PlanEntry]

@dataclass
class ModeChange(SessionEvent):
    mode_id: str
    mode_name: str

@dataclass
class ModelChange(SessionEvent):
    model_id: str
    model_name: str

@dataclass
class CommandsUpdate(SessionEvent):
    commands: list[dict[str, str]]
```

### 2. Typed Event Queue (pp-event-queue)

**`src/tak/providers/acp_session.py`**:
- Replace `_update_chunks: Queue[str | None]` with
  `_event_queue: Queue[SessionEvent | None]`.
- Update `session_update()` to create typed `SessionEvent` instances for
  each ACP update type and enqueue them.
- Update `prompt()` to filter for `TextChunk` events and concatenate text
  (backward compatible).
- Update `prompt_streaming()` to yield `SessionEvent` instances. Add a
  `text_streaming()` convenience method that yields only text strings
  (backward compatible with current callers).

### 3. Extension Method Handlers

#### cursor/ask_question (pp-ext-ask-question)

**`src/tak/providers/acp_session.py`** -- `ext_method()`:
- Parse the question text and options from params.
- Route to `_ask_question_callback` (already partially implemented).
- Return the selected answer in the expected response format.
- When no callback is set, log the question and return the first option
  as a default (better than empty `{}`).

#### cursor/create_plan (pp-ext-create-plan)

- Parse plan entries from params.
- Enqueue a `PlanUpdate` event so the TUI/CLI can display it.
- Return an approval signal. Initially auto-approve; Phase Q adds
  interactive approval.

#### cursor/update_todos (pp-ext-update-todos)

- Parse todo items from params.
- Store in a `_todos: list[dict]` on the client for display.
- Enqueue an event for TUI consumption.

#### cursor/task (pp-ext-task)

- Parse task result from params.
- Enqueue a task completion event.
- Return acknowledgment.

#### cursor/generate_image (pp-ext-generate-image)

- Extract image data from params.
- Save to a temp file.
- If iTerm2 is the active driver, use the iTerm2 inline image escape
  sequence to display it. Otherwise, print the file path.

### 4. Session Capabilities Parsing (pp-session-capabilities)

**`src/tak/providers/acp_session.py`** -- `initialize()`:
- Parse `sessionCapabilities` from the `InitializeResponse`.
- Store `supports_list`, `supports_fork`, `supports_resume` booleans.
- Guard any future calls to these methods with capability checks.

## Tests

**`tests/core/test_events.py`**:
- Test `SessionEvent` hierarchy construction and type checking.

**`tests/providers/test_acp_session.py`**:
- Test `session_update` creates correct `SessionEvent` types.
- Test `prompt()` still returns concatenated text (backward compat).
- Test `text_streaming()` yields only text strings.
- Test `ext_method` handlers for each extension method.
- Test session capabilities parsing.

## Acceptance Criteria

1. All 11 ACP update types produce typed `SessionEvent` instances.
2. `prompt()` returns the same text as before (backward compatible).
3. `prompt_streaming()` yields `SessionEvent` objects.
4. `cursor/ask_question` routes to callback and returns user's choice.
5. `cursor/create_plan` enqueues `PlanUpdate` events.
6. `cursor/update_todos` tracks task state.
7. Session capabilities are parsed and stored.
8. All existing tests pass. `ruff check` clean.

## Agent Prompt

> Read `docs/tasks/phase-p-event-fidelity.md` for the full spec. This phase
> adds a typed event model for all ACP update types and implements proper
> handlers for Cursor extension methods. Read "Files to Read First", then
> implement each item in "What to Build" in order. Run `ruff check src/ tests/`
> and `pytest -q` after each change. Update manifest.yaml when done.
