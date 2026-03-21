# Phase Q: Conversation TUI

## Goal

Build a full-screen Textual TUI for interactive agent sessions, inspired by
Claude Code's terminal UX but adapted for tak's multi-agent model. This is
the "deep session" experience -- the primary way to have extended conversations
with agents from the terminal.

## Context

tak already has a basic Textual TUI (`tak menu`) that shows an agent roster
table. This phase builds a separate conversation view that takes over the
terminal for an interactive session with a specific agent.

### Claude Code TUI Patterns (from screenshots, 2026-03-18)

The following patterns were observed in Claude Code v2.1.76 and inform
this phase's design:

**Conversation view:**
- Scrolling conversation with distinct visual treatment per message type
- User messages: highlighted background, full width
- Agent responses: bullet prefix, inline markdown rendering (headers, bold,
  italic, code blocks with syntax highlighting, bulleted lists)
- Tool calls rendered as function-style: `Write(hello.py)` with tree-style
  results: `└ Wrote 1 lines to hello.py` and inline code preview
- Subagent tasks: `claude-code-guide(Explain feature)` with stats
  `└ Done (4 tool uses · 35.9k tokens · 12s)` and `(ctrl+o to expand)`
- Thinking indicators: animated randomized verbs ("Gallivanting..",
  "Channeling..", "Befuddling..") with elapsed time and token count

**Input area:**
- Bottom of screen, always visible
- Slash command completion with progressive filtering (`/pl` → `/plan`,
  `/plugin`, etc.) and descriptions
- `@` file path completion for workspace files
- `!` prefix for local shell commands (client-side execution)
- Image attachments: `[Image #1] [Image #2]` with arrow navigation,
  Delete to remove, Esc to cancel
- Multi-line input via `backslash+return`

**Status bar:**
- Current mode: `plan mode on (shift+tab to cycle) · esc to interrupt`
- Activity state during work
- Model indicator (right side)
- Update notifications

**Mode-aware behavior:**
- Plan mode: structured plan display with approval flow (numbered options,
  "Yes, clear context and auto-accept edits", etc.)
- Agent mode: tool execution with inline results
- Ask mode: Q&A without edits

**Multi-step interview wizard:**
- Tabbed navigation (Backend, UI Style, React Features, Language, Submit)
- Numbered options with arrow key selection
- ASCII wireframe mockups rendered inline

**Keyboard shortcuts:**
- `Ctrl+C` (once): clear input / (twice within timeout): exit
- `Shift+Tab`: cycle modes (default → auto-accept → plan)
- `Esc`: interrupt/cancel current operation
- `Ctrl+O`: toggle verbose/transcript mode
- `Ctrl+T`: toggle tasks panel
- `Meta+P`: switch model
- `Ctrl+V`: paste images from clipboard

### Key Difference from Claude Code

tak manages multiple agents. The conversation view targets a specific agent
(resolved from tab association or explicit name). Agent switching is a
first-class operation within the TUI.

## Dependencies

- **Phase P (Event Fidelity)** provides `SessionEvent` types for rendering.
- **Phase N (Streaming)** provides the streaming IPC transport.
- **Phase M (Conversation)** provides session persistence.

## Files to Read First

- `src/tak/tui/app.py` -- existing `TakApp` (agent roster dashboard)
- `src/tak/tui/widgets.py` -- existing `AgentTable` widget
- `src/tak/tui/tak.tcss` -- existing stylesheet
- `src/tak/core/events.py` -- `SessionEvent` hierarchy (Phase P)
- `src/tak/providers/acp_session.py` -- streaming and event data
- `docs/research/agents/cursor-acp-behavior/analysis.md` -- §21, §24

## What to Build

### 1. Conversation Widget (pq-conversation-widget)

A scrolling message list that renders different message types with distinct
visual treatment. Uses Rich for inline markdown rendering.

**`src/tak/tui/conversation.py`**:
- `ConversationView(ScrollableContainer)` with message rendering.
- `UserMessage` widget: highlighted background, full width.
- `AgentMessage` widget: Rich markdown rendering for headers, bold, italic,
  code blocks, lists.
- `SystemMessage` widget: dimmed text for status messages.
- Messages append at the bottom; auto-scroll to latest.

### 2. Tool Call Display (pq-tool-call-display)

Tool calls rendered as collapsible blocks.

- `ToolCallBlock` widget showing title (e.g. "Write(hello.py)").
- Tree-style result: `└ Wrote 1 lines` with inline code preview.
- Collapsible via click or keyboard.
- Driven by `ToolStart` / `ToolProgress` / `ToolDone` events.

### 3. Thinking Indicator (pq-thinking-indicator)

Animated label during thinking phases.

- Randomized verb labels (configurable list).
- Elapsed time counter: `Channeling... (45s · ↓ 46 tokens · thought for 4s)`.
- Appears when `ThoughtChunk` events arrive.
- Disappears when `TextChunk` or `ToolStart` arrives.

### 4. Status Bar (pq-status-bar)

Bottom status bar with mode, activity, and model info.

- Left: mode indicator `plan mode on (shift+tab to cycle) · esc to interrupt`
- Right: model name, token/context usage if available
- Updates reactively from `ModeChange` and `ModelChange` events.

### 5. Input Box (pq-input-box)

Text input area at the bottom of the conversation view.

- Slash command completion: `/` triggers a dropdown with filtered commands
  from `AvailableCommandsUpdate`.
- `@` file path completion: triggers workspace file browser.
- `!` prefix: execute command in local shell, display output inline.
- Multi-line: `backslash+return` inserts newline.
- Enter: send prompt to agent.

### 6. Mode Cycling (pq-mode-cycling)

`Shift+Tab` cycles through ask → plan → agent modes.

- Calls `set_config_option("mode", next_mode)` via the ACP session.
- Updates status bar immediately.
- Shows brief notification: "Switched to plan mode".

### 7. Plan Approval (pq-plan-approval)

When `AgentPlanUpdate` events arrive (or `cursor/create_plan` extension):

- Display structured plan entries with priority badges and status.
- Show approval options (numbered list like Claude Code).
- Return user's choice to the agent.

### 8. Image Support (pq-image-support)

- `Ctrl+V`: detect image data on clipboard, create `ImageContentBlock`.
- Display `[Image #1]` tags with arrow-key navigation.
- For agent-generated images (`cursor/generate_image`): use iTerm2's
  inline image escape sequence if available, otherwise save and show path.

### 9. Multi-Agent Switch (pq-multi-agent-switch)

- Agent picker accessible via keyboard shortcut or `/switch` command.
- Shows list of running agents with current model and status.
- Switching changes the conversation view to the selected agent's session.

### 10. Ask Question Widget (pq-ask-question-widget)

When `cursor/ask_question` fires:

- Render the question text and numbered options.
- Arrow keys + Enter to select.
- Tab to navigate between option groups (like Claude Code's tabbed wizard).
- Return selection to the agent.

## Tests

**`tests/tui/test_conversation.py`**:
- Test `ConversationView` renders user and agent messages.
- Test tool call blocks render title and result.
- Test thinking indicator appears/disappears on events.

**`tests/tui/test_input.py`**:
- Test slash command filtering.
- Test `@` completion triggers.
- Test multi-line input.

## Acceptance Criteria

1. `tak tui [agent-name]` opens a full-screen conversation view.
2. Agent responses render with markdown formatting (headers, code blocks).
3. Tool calls display as collapsible blocks with results.
4. Thinking indicator animates during thought phases.
5. Status bar shows current mode, model, and activity.
6. `Shift+Tab` cycles modes.
7. Slash commands autocomplete from agent's command registry.
8. `Ctrl+C` (once) clears input, (twice) exits.
9. Multiple agents can be switched within the TUI.
10. All existing tests pass. `ruff check` clean.

## Agent Prompt

> Read `docs/tasks/phase-q-conversation-tui.md` for the full spec. This phase
> builds a full-screen Textual TUI for interactive agent conversations. Read
> "Files to Read First" and the Claude Code patterns section, then implement
> each widget in "What to Build" in order. Run `ruff check src/ tests/` and
> `pytest -q` after each change. Update manifest.yaml when done.
