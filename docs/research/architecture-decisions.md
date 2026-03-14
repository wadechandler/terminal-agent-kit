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
