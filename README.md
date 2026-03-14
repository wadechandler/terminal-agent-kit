# Terminal Agent Kit (tak)

> Forging your terminal into an agentic environment

Terminal Agent Kit is an open-source framework for embedding, managing, and interacting
with AI coding agents directly within your terminal. Starting with iTerm2 on macOS, it
provides a terminal-native agentic workspace where you can spawn agents, route questions
from any tab, manage multiple agent instances, and scaffold projects -- without leaving
your command line.

## Status

**Pre-alpha / Research phase.** This project is actively being designed and prototyped.
See [docs/tasks/manifest.yaml](docs/tasks/manifest.yaml) for current status and
[docs/research/](docs/research/) for design decisions.

## Vision

- **Agent Management**: Spawn, stop, and monitor N agents (Cursor CLI, Claude Code, Goose,
  direct LLM APIs, and more) as managed subprocesses. Each agent can target any folder --
  git repos, OneDrive directories, arbitrary paths.
- **Tab-Agent Association**: Associate any terminal tab with a running agent. Type `@ai`
  in a working tab and your question routes to the associated agent. Multiple tabs can
  share an agent. Multiple agents can run simultaneously.
- **Two Interaction Models**:
  - `tak` -- a standard CLI command on your PATH. Pipeable, scriptable, composable.
  - `@tak` / `@ai` -- terminal-intercepted prefixes caught by the daemon before reaching
    your shell. Context-aware: knows your tab, reads screen content, triggers overlays.
- **Terminal UX Enhancements**: Status bar components, tab management overlays, keyboard
  shortcuts, agent session panels.
- **Project Scaffolding**: `tak new project`, `tak scaffold agents|rules|skills` to
  generate AGENTS.md, .cursor/rules, SKILL.md, and other standards files.
- **Environment Setup**: Automated setup for Starship prompt, JetBrains Mono Nerd Font,
  shell integration, and iTerm2 profiles.
- **Cross-Terminal Architecture**: Core logic is terminal-agnostic. iTerm2 is the first
  driver; Kitty, tmux, and WezTerm drivers are planned.
- **Remote Agent Support**: Run agents on remote machines via SSH + tmux. The agent
  executes remotely (sandboxed from your local machine) while you interact locally.

## Architecture

```
tak (CLI command)  ──┐
                     ├──▶  Core (terminal-agnostic)
@tak / @ai (hooks) ──┘     ├── AgentManager (lifecycle, subprocesses)
                            ├── AgentBus (message routing)
                            ├── SessionRegistry (tab-agent associations)
                            ├── Providers (Cursor ACP, Claude, LLM APIs...)
                            └── State (persistence, restart recovery)
                                    │
                            Drivers (terminal-specific)
                            ├── iTerm2 (Python API, status bar, triggers)
                            ├── Kitty (remote control, kittens)
                            └── tmux (control mode, scripting)
```

## Quick Start

> Not yet functional -- scaffolding and research phase.

```bash
pip install terminal-agent-kit
tak spawn cursor --name my-project --project ~/code/myapp
tak status
```

## Project Structure

```
terminal-agent-kit/
  src/tak/               # Python package
    core/                # Terminal-agnostic agent management
    providers/           # Agent protocol implementations (ACP, stdio, LLM API)
    drivers/             # Terminal-specific integrations (iTerm2, Kitty, tmux)
    scaffold/            # Standards file generators (AGENTS.md, rules, skills)
    cli/                 # CLI entry point (the `tak` command)
  config/                # Default configuration files
  setup/                 # Environment bootstrap scripts
  docs/
    research/            # Design decisions and API research
    tasks/               # Task tracking and project manifest
  tests/
```

## Security

- Dependencies are checked against MITRE/NVD for known vulnerabilities.
- We prefer dependencies with healthy bus factors and active maintenance.
- Remote agents execute on the remote machine only; responses return through
  the SSH tunnel without exposing your local system.
- See [SECURITY.md](SECURITY.md) (planned) for our full security posture.

## License

Apache 2.0 -- see [LICENSE](LICENSE).
