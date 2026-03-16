# Project Status -- Terminal Agent Kit (tak)

Read this first when starting a new agent session on this project. It provides
orientation and pointers to authoritative documents. Do not assume status from
this file alone -- always check the manifest.

## Quick Summary

tak is a Python framework for embedding and managing AI coding agents within
terminal environments. It provides a core agent management layer with
terminal-specific drivers, starting with iTerm2 on macOS. The CLI command is
`tak`. The vision is a "poor man's Warp" -- conversational terminal AI using
iTerm2, Cursor CLI, and eventually other agents and terminals.

## Authoritative Status

**`docs/tasks/manifest.yaml`** is the single source of truth for what is done,
in progress, not started, or deferred. Always read it. Always update it after
completing work. See `.cursor/rules/manifest-maintenance.mdc` for the full
maintenance protocol.

As of 2026-03-16: Phases 0, 1, F, G, H, I, J, and K are done (357 tests, 0 ruff
errors). Phases M through CI are not started. See the manifest for details.

## Key Documents

| Document | Purpose |
|----------|---------|
| `AGENTS.md` | Coding conventions, architecture, tech stack, dependency policy |
| `docs/tasks/manifest.yaml` | Phase/task tracking (the source of truth) |
| `docs/research/architecture-decisions.md` | 17 numbered ADRs (design decisions) |
| `docs/tasks/phase-*.md` | Implementation specs for each phase |
| `docs/tryout-guide.md` | How to install, run, and clean up tak (when it exists) |
| `.cursor/rules/` | Cursor rules for agents working on this project |
| `config/agents.yaml` | Provider definitions (Cursor ACP, with Claude/Goose commented) |
| `config/default.yaml` | Default runtime configuration |

## Architecture at a Glance

```
src/tak/
  core/        Terminal-agnostic: agent manager, bus, session registry, state, config, adhoc
  providers/   Agent protocols: ACP (generic + Cursor), terminal session, base
  drivers/     Terminal integrations: iTerm2 (daemon, driver, RPC, status bar)
  ipc/         Daemon-CLI communication: Unix socket, length-prefixed JSON protocol
  cli/         Click-based CLI: spawn, stop, ask, agents, switch, menu, scaffold, setup
  tui/         Textual TUI: agent dashboard (tak menu)
  scaffold/    Generators: AGENTS.md, .cursor/rules, SKILL.md, new project
  setup/       Environment bootstrap: iTerm2, fonts, starship, shell, profiles
```

The `iterm2` package is imported only inside `src/tak/drivers/iterm2/`. Everything
else is terminal-agnostic. See ADR-003 for the core/driver split rationale.

## ADR Summary

| ADR | Decision |
|-----|----------|
| 001 | Project name: Terminal Agent Kit (tak) |
| 002 | Apache 2.0 license |
| 003 | Core/driver architecture -- terminal-agnostic core with thin drivers |
| 004 | Two interaction models: `tak` CLI and `@tak`/`@ai` intercepted prefixes |
| 005 | Cursor ACP as first provider |
| 006 | N agents of any type with user-assigned names |
| 007 | Remote agents via SSH tunnels |
| 008 | Configurable prefixes (`@ai`, `@tak`, `??`) |
| 009 | Dependency security: CVE checks, bus factor > 1, pip-audit |
| 010 | Variable namespace: `user.tak_*` |
| 011 | Deferred @ai interception -- use `tak ask` first |
| 012 | Headless vs terminal agent models |
| 013 | Bash-first shell target |
| 014 | Idempotent setup commands |
| 015 | Generic ACP provider |
| 016 | Graduated conversation surface: session persistence, streaming, Warp-like pane |
| 017 | Remote agent model: SSH tunnels, context dict, tmux integration |

## Current Priorities

1. **Documentation catch-up** (Wave A) -- README, AGENTS.md accuracy
2. **Tryout preparation** (Wave B) -- guide, `--dry-run` for setup, Phase M implementation
3. **Security and CI** (Wave C) -- SECURITY.md, GitHub Actions, pip-audit
4. **Polish** (Wave D) -- TUI review, @ai alias, real integration testing

## Deferred Items

- @ai interception via KeystrokeFilter (depends on proven daemon + IPC)
- Agent session mode (Warp-like per-tab mode toggle, Phase 4+ territory)
- Additional providers (Claude Code, Goose, direct LLM API)
- Additional drivers (Kitty, tmux, WezTerm)
- Enterprise features (VS Code extension, JetBrains plugin, Azure DevOps)

## Maintenance Rule

After completing any phase or task, update `docs/tasks/manifest.yaml`. See
`.cursor/rules/manifest-maintenance.mdc` for the full protocol.
