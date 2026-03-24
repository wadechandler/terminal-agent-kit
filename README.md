# Terminal Agent Kit (tak)

> Transform your terminal into an agentic workspace

Terminal Agent Kit is an open-source framework for embedding, managing, and
orchestrating AI agents directly within your terminal -- for coding, system
management, workflows, and more. Starting with Cursor (via ACP) on iTerm2 for
macOS, it provides a terminal-native workspace where you can spawn agents, route
prompts from any tab, manage multiple agent instances, and scaffold projects --
without leaving your command line.

## Status

**Alpha.** Core agent management, full ACP session lifecycle (via the official
agent-client-protocol SDK), CLI (17 commands), IPC, TUI dashboard, scaffold
generators, and setup commands are implemented and tested (477 unit tests, zero
lint errors). Initial end-to-end integration with the iTerm2 daemon and Cursor CLI
has been validated, with numerous protocol-level fixes applied (ACP SDK adoption,
subprocess PATH resolution, session reconnection, permission relay, signal handling).
Streaming output and the conversation TUI are next. See
[docs/tasks/manifest.yaml](docs/tasks/manifest.yaml) for detailed phase status and
[docs/PROJECT-STATUS.md](docs/PROJECT-STATUS.md) for a quick orientation.

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

## Prerequisites

- **Python 3.11+** (3.12 or 3.13 recommended)
- **iTerm2 >= 3.5.11** (for the daemon and terminal integration)
- **Homebrew** (for font and Starship installation via `tak setup`)
- **Cursor CLI** (optional, for the Cursor ACP provider)

## Quick Start

```bash
# Install in development mode
git clone https://github.com/wadechandler/terminal-agent-kit.git
cd terminal-agent-kit
pip install -e ".[dev]"

# Try standalone commands (no daemon needed)
tak scaffold agents               # Generate AGENTS.md for current project
tak scaffold rules                # Generate .cursor/rules/
tak new project my-app --quick    # Create a new project skeleton
tak menu                          # Launch the agent management TUI

# Setup commands (configures iTerm2, fonts, shell, etc.)
tak setup tak                     # All-in-one opinionated setup
```

For daemon-dependent commands (agent lifecycle, interaction, and routing), the
iTerm2 daemon must be running. See [docs/tryout-guide.md](docs/tryout-guide.md)
for the full walkthrough.

## CLI Reference

**Agent lifecycle:**

| Command | Description |
|---------|-------------|
| `tak spawn [PROVIDER]` | Spawn a new agent (`-n NAME`, `-p PROJECT`, `-m MODEL`, `--permissions`, `--no-associate`) |
| `tak stop NAME` | Stop a running agent |
| `tak remove NAME` | Remove an agent from state entirely (`-f/--force`) |
| `tak rename OLD NEW` | Rename an agent |

**Interaction:**

| Command | Description |
|---------|-------------|
| `tak prompt QUERY...` | Send a prompt to an agent (`-a AGENT`, `-M MODE`). Shorthand: `tak p` |
| `tak session end [AGENT]` | End conversation session (fresh on next prompt) |

**Discovery and routing:**

| Command | Description |
|---------|-------------|
| `tak agents` | List all managed agents (`-p PROVIDER`, `--running`) |
| `tak status` | Show status of all running agents |
| `tak associate AGENT` | Associate current terminal tab with an agent (`-s SESSION_ID`) |
| `tak switch NAME` | Switch to the terminal tab of a named agent |
| `tak providers` | List available agent providers |
| `tak info` | Show terminal environment and session details |
| `tak permissions AGENT POLICY` | Set permission policy (`prompt`, `reject`, `auto-allow`, `yolo`) |

**Standalone (no daemon needed):**

| Command | Description |
|---------|-------------|
| `tak menu` | Open the agent management TUI |
| `tak scaffold agents\|rules\|skills` | Generate standards files for a project |
| `tak new project NAME` | Create a new project skeleton (`--quick`) |
| `tak setup tak\|iterm2\|fonts\|starship\|shell\|profiles\|iterm2-pip` | Set up environment components |

## Project Structure

```
terminal-agent-kit/
  src/tak/               # Python package
    core/                # Terminal-agnostic agent management
    providers/           # Agent protocol implementations (ACP, stdio, terminal)
    drivers/             # Terminal-specific integrations (iTerm2, Kitty, tmux)
    ipc/                 # Daemon-CLI communication (Unix socket, JSON protocol)
    tui/                 # Textual-based agent management dashboard
    scaffold/            # Standards file generators (AGENTS.md, rules, skills)
    setup/               # Environment bootstrap (iTerm2, fonts, Starship, shell)
    cli/                 # CLI entry point (the `tak` command)
  config/                # Default configuration files
  docs/
    research/            # Design decisions (ADRs) and API research
    tasks/               # Task tracking (manifest.yaml) and phase specs
  tests/                 # Mirrors src/ structure
```

## Security

- Dependencies are checked against MITRE/NVD for known vulnerabilities.
- We prefer dependencies with healthy bus factors and active maintenance.
- Remote agents execute on the remote machine only; responses return through
  the SSH tunnel without exposing your local system.
- The iTerm2 daemon communicates via a local-only Unix socket with cookie-based
  authentication.

## License

Apache 2.0 -- see [LICENSE](LICENSE).
