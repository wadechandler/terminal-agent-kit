# Architecture Decisions

Captured during initial planning sessions (March 2026).

## ADR-001: Project Name -- Terminal Agent Kit (tak)

**Decision**: Project is named "Terminal Agent Kit" with CLI command `tak`.

**Context**: Evaluated multiple names including `termagent`, `iterm2-devkit-ai`,
`term-devkit-ai`, various brand names. Key constraints: must not collide with
existing projects, must work as a short CLI command, must not be too narrow
(project extends beyond a single terminal).

**Alternatives considered**:
- `termagent` -- clear but `termagent-cli` exists on PyPI (different project)
- `iterm2-devkit-ai` -- too specific to iTerm2
- `devkit` / `ai-devkit` -- taken (npm/github)
- `anvil`, `loom`, `baton` -- too abstract

**Outcome**: `terminal-agent-kit` as repo/package name, `tak` as CLI command.
Intercepted prefixes `@tak` and `@ai` for terminal-level hooks. `termagentkit`
reserved as an alternate package name if needed.

## ADR-002: Apache 2.0 License

**Decision**: Apache 2.0 over MIT.

**Context**: Project integrates with commercial AI products (Cursor, Claude) in a
patent-heavy space. Target audience includes enterprise teams needing compliance
sign-off.

**Rationale**: Explicit patent grant, patent retaliation clause, trademark
protection. Enterprise-standard (Kubernetes, TensorFlow). Compatible with GPLv3.

## ADR-003: Core/Driver Architecture

**Decision**: Terminal-agnostic core with thin terminal-specific drivers.

**Context**: Starting with iTerm2 but planning Kitty, tmux, WezTerm support and
eventually IDE extensions (VS Code, JetBrains).

**Structure**:
- `core/` -- agent management, bus, registry, state, config. No terminal imports.
- `drivers/` -- each driver implements a common interface:
  `list_sessions()`, `get_active_session()`, `inject_text()`, `set_variable()`,
  `register_trigger()`, etc.
- `providers/` -- agent protocol implementations, also terminal-agnostic.

**Rationale**: Adding a new terminal is a new driver, not a rewrite. IDE extensions
can use the core directly with their own "driver" wrapping the IDE's API.

## ADR-004: Two Interaction Models

**Decision**: Both a CLI command (`tak`) and terminal-intercepted prefixes (`@tak`/`@ai`).

**Context**: These serve fundamentally different use cases.

**`tak` (CLI command)**:
- Standard POSIX citizen -- pipeable, scriptable, composable
- Works in any terminal, SSH, CI, cron
- Communicates with daemon via IPC (unix socket) when available
- Can operate standalone for basic tasks (scaffolding, config)

**`@tak` / `@ai` (intercepted)**:
- Caught by terminal daemon before reaching shell
- Has terminal context: tab identity, screen content, agent association
- Can trigger UI: overlays, split panes, inline response injection
- Only works when terminal driver daemon is running

## ADR-005: Cursor ACP as First Provider

**Decision**: Implement Cursor CLI via ACP (Agent Client Protocol) first.

**Context**: Cursor CLI exposes ACP -- JSON-RPC 2.0 over stdio. Spawn
`agent acp` as subprocess, write JSON-RPC to stdin, read from stdout. This is
exactly the interface the agent bus needs.

**Rationale**: Clean, well-documented protocol. JSON-RPC is standard. Cursor is
the primary agent the user works with. Other providers (Claude Code, Goose,
generic stdio, direct LLM API) follow the same abstract interface.

## ADR-006: N Agents of Any Type

**Decision**: Support multiple simultaneous instances of the same agent type.

**Context**: User may have `cursor-myapp`, `cursor-docs`, `cursor-infra` all
running. Each has a user-assigned name, a project path (git repo, OneDrive
folder, arbitrary directory), and zero or more associated tabs.

**State model**:
```yaml
agents:
  cursor-myapp:
    provider: cursor-acp
    project: ~/code/myapp
    tabs: [session-abc, session-def]
    status: running
  cursor-docs:
    provider: cursor-acp
    project: ~/OneDrive/docs
    tabs: [session-ghi]
    status: running
```

## ADR-007: Remote Agent Model

**Decision**: Agents run on remote machines via SSH. Communication through
SSH tunnel. Local machine is never exposed to agent actions.

**Context**: User wants to work with remote dev machines, Coder.com
environments, and cloud VMs. Security requirement: agent actions are sandboxed
to the remote environment.

**Implementation**: SSH + tmux for session persistence. ACP/stdio protocols
work transparently over SSH tunnels. State file tracks remote agents with
connection details for reconnection.

## ADR-008: Configurable Prefixes

**Decision**: All intercepted prefixes (`@ai`, `@tak`, `??`) are user-configurable
via `~/.tak/config.yaml`.

**Context**: Different users have different conventions. `@ai` is intuitive and
extends to `@ai:agent-name` for targeting. `??` is fast for quick questions.
`@tak` namespaces toolkit commands vs agent queries.

**Default mapping**:
- `@ai [query]` -- route to tab's default agent
- `@ai:name [query]` -- route to specific named agent
- `@tak [command]` -- toolkit commands (tabs, switch, status, spawn)
- `??[query]` -- shorthand alias for `@ai`

## ADR-009: Security Posture

**Decision**: Check all dependencies against MITRE/NVD. Prefer libraries with
bus factor > 1 and active maintenance.

**Context**: Enterprise adoption requires defensible dependency choices. AI/agent
space has many fast-moving, single-maintainer packages.

**Implementation**: Integrate safety/pip-audit into CI. Document dependency
rationale in a DEPENDENCIES.md or similar. Flag single-maintainer packages
for review.

## ADR-010: Variable Namespace (user.tak_*)

**Decision**: Use underscore-namespaced flat keys under `user.tak_*` prefix.

**Context**: iTerm2 requires `user.` prefix for user-defined variables. Dots
after `user.` not clearly documented.

**Variables**: `user.tak_agent_id`, `user.tak_agent_status`,
`user.tak_agent_provider`, `user.tak_agent_model`

## ADR-011: Deferred @ai Interception

**Decision**: Defer @ai prefix interception. Use tak CLI (`tak ask`) first.

**Context**: Triggers match output only; KeystrokeFilter is complex. Shell
function is interim.

**Rationale**: Daemon proves value through UI features, not input interception.

## ADR-012: Headless vs Terminal Agent Models

**Decision**: Support both headless (ACP subprocess) and terminal (own tab)
agents.

**Context**: Different agent types have different interaction models.

- **Headless**: tak mediates permissions via session/request_permission relay
- **Terminal**: Agent has own TUI, tak manages lifecycle only
- BaseProvider needs `interaction_model` property

## ADR-013: Bash-First Shell Target

**Decision**: Target bash first, zsh/fish later.

**Context**: User runs bash 5.x from Homebrew. Bash is universal.

**Implementation**: `tak setup shell` should detect macOS stock bash 3.2 and
offer upgrade.

## ADR-014: Idempotent Setup Commands

**Decision**: All `tak setup` commands must be idempotent.

**Context**: Users may run setup multiple times. Duplication causes confusion
and breakage.

**Implementation**: Check before acting, skip if done, never duplicate, report
clearly, use markers.

## ADR-015: Generic ACP Provider

**Decision**: Refactor CursorACPProvider to generic ACPProvider.

**Context**: ACP becoming cross-agent standard (Cursor, Goose, Claude via
adapter).

**Implementation**: Agent-specific spawn flags via config. Separate
TerminalSessionProvider for TUI agents.

## ADR-016: Graduated Conversation Surface

**Decision**: Build the "poor man's Warp" interaction model in three levels:
session persistence, streaming, then a dedicated conversation pane.

**Context**: The core use case is conversational terminal AI -- ask a question,
see the answer, follow up, have the agent act, handle permissions, iterate. Warp
integrates its AI panel into the terminal chrome. iTerm2 cannot modify its chrome,
but we can replicate the UX with split panes and the Textual TUI framework.

**Level 1 -- Session persistence** (Phase M): The daemon keeps ACP sessions
alive per agent. Subsequent `tak ask` calls reuse the same session so the agent
has conversation history. Each `tak ask` is a new prompt in an ongoing
conversation. Permissions and multiple-choice questions use keystroke injection
(existing). Plans and todos are included in the response text. `--mode
ask|plan|agent` controls agent behavior. `tak session end` resets.

**Level 2 -- Streaming** (Phase N): Enhance the IPC protocol to support
streaming responses. `tak ask` prints text as chunks arrive instead of waiting
for the full response. The user sees the agent reasoning in real time.

**Level 3 -- Conversation pane** (Phase O): A Textual TUI running in an iTerm2
split pane serves as the dedicated conversation surface. It shows full
conversation history, streaming output, plans, todos, permissions, and accepts
typed input including free text. This is the "AI panel" equivalent:

```
+-------------------------------------------+
| iTerm2 Tab                                |
+---------------------+---------------------+
| Shell (your CWD)    | tak Agent Panel     |
|                     | (Textual TUI)       |
| $ ls                | [cursor-myapp]      |
| $ brew search jq    | You: install jq     |
|                     | I'll install jq:    |
|                     | brew install jq     |
|                     | Allow? [y] [n] [a]  |
|                     | > type follow-up    |
+---------------------+---------------------+
```

**Multi-tab model**: If tabs A and B share agent `cursor-myapp`, they share one
ACP session. CWD differs per tab. The prompt includes CWD so the agent knows
context. When the daemon routes a message, it attaches a context dict:
`{"cwd": "/Users/me/project", "session_id": "..."}`.

**CLI quoting**: `tak ask` uses Click `nargs=-1` so `tak ask what files are
here` works without quotes. Quoting is only needed for shell metacharacters
(`?`, `!`, `$`, `*`).

**Rationale**: Graduated approach lets us validate the plumbing (Level 1) before
investing in protocol changes (Level 2) or TUI work (Level 3). Each level is
independently useful.

## ADR-017: Remote Agent Model

**Decision**: Support remote agents via SSH tunnels for ACP and SSH + tmux for
terminal sessions, using a context dict to carry remote environment information.

**Context**: Users want agents running on remote machines (devboxes, Coder.com
environments, cloud VMs) while interacting locally. The agent executes remotely
(sandboxed from the local machine); only responses travel back. ADR-007
established the SSH + tmux foundation; this ADR details the implementation
approach.

**Provider layer**: A remote ACP agent is an `ACPProvider` whose command goes
through SSH: `["ssh", "devbox", "cursor", "agent", "acp"]`. A remote terminal
agent is a `TerminalSessionProvider` that spawns an SSH session in a new tab.
No new provider types are needed -- the existing providers work transparently
over SSH because ACP/stdio protocols don't care about transport.

**Context dict**: Bus messages carry a context dict instead of a flat CWD string:

```yaml
context:
  local_cwd: /Users/me/projects/foo
  remote_cwd: /home/me/projects/foo   # present only for SSH sessions
  is_remote: true
  ssh_host: devbox.internal
```

Local sessions have `is_remote: false` and no `remote_cwd` or `ssh_host`. The
ACP provider includes context in the prompt so the agent knows where it is.

**Driver layer**: The iTerm2 driver can detect SSH sessions via shell integration
variables. The tmux driver is a natural fit for remote work -- tmux sessions
persist across SSH disconnections, providing durable remote agent sessions.

**Architecture impact**: None. The core/driver/provider split already has the
right boundaries. Remote support is additive: new config entries, richer context
dict, optional SSH-aware command construction. No existing interfaces change.

**Extensibility**: This model supports the "agentic IDE" vision: the TUI can
evolve to show file browsers, vim integration, and multi-panel layouts. The split
pane approach (ADR-016 Level 3) extends naturally to remote contexts. Nothing in
the current architecture prevents these future directions.
