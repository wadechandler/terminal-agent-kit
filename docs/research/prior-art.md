# Prior Art

Survey of existing projects in the terminal AI agent space, conducted March 2026.

## iTerm2-Specific AI Integrations

| Project | Stars | Language | What It Does |
|---------|-------|----------|-------------|
| [iterm-mcp](https://github.com/ferrislucas/iterm-mcp) | 533 | TypeScript | MCP server letting Claude execute commands in iTerm2 |
| [iterm2-mcp-server](https://github.com/sumchattering/iterm2-mcp-server) | new | Python/JS | MCP server for Claude to read/write iTerm2 panes |
| [iTerm-MCP-Server](https://github.com/rishabkoul/iTerm-MCP-Server) | 15 | JavaScript | MCP for terminal management via AI assistants |
| [ai-terminal-agent](https://github.com/wpoPR/ai-terminal-agent) | 1 | - | Multi-AI workspace manager for iTerm2 |
| iTerm2 official AI plugin | n/a | - | Optional generative AI features (black box) |

**Gap**: All MCP servers are "outside-in" -- external AI controls the terminal.
None embed agent management INTO the terminal experience.

## Terminal Agent Orchestrators

| Project | Stars | Language | Approach |
|---------|-------|----------|----------|
| [Agency](https://github.com/tobias-walle/agency) | active | Rust | TUI + tmux + git worktrees. Most mature. Supports Claude/Codex/Gemini/OpenCode. |
| [AgentPipe](https://agentpipe.ai/) | small | Go | Multi-agent orchestration, 15+ agents, round-robin/reactive modes |
| [Agent Conductor](https://github.com/gaurav-yadav/agent-conductor) | small | Python | tmux-based supervisor/worker, REST API, SQLite persistence |
| [Agent Farmer](https://github.com/howinator/agent-farmer) | small | Go | Background agent tasks, workspace isolation via git worktrees |

**Gap**: These are standalone TUI apps, not terminal-integrated. No native
terminal API usage (iTerm2/Kitty), no tab-agent association, no intercepted
prefix routing, no terminal UX enhancements.

## Warp Terminal

Warp is the primary commercial comparison point:
- Natural language input directly in terminal
- Agent mode with multi-step autonomous execution
- Full terminal control (interactive apps, debuggers, REPLs)
- Oz platform for cloud agents
- Slack/Linear/GitHub Actions integrations

**Limitations from user's perspective**: Proprietary, recent changes broke
workflows, can't use own CLI tools freely, vendor lock-in.

## AI DevKit (ai-devkit)

- npm package by codeaholicguy
- Structured AI-assisted development workflows
- Works with Cursor, Claude Code, GitHub Copilot
- Documentation scaffolding, memory, skills

**Relationship**: Complementary, not competitive. Focuses on project-level AI
workflow, not terminal integration.

## Stripe Minions

Enterprise reference architecture:
- Fully unattended agents producing 1,000+ merged PRs/week
- Built on Block's open-source Goose agent
- Isolated "devboxes" (pre-warmed, no internet)
- MCP server ("Toolshed") with 400+ internal tools
- Invoked via Slack, CLI, web UI
- Key insight: wrap probabilistic agents in deterministic infrastructure

**Relevance**: Model for enterprise agent orchestration. tak could serve as
the developer-facing terminal layer in a similar architecture.

## Coder.com

- Self-hosted remote development environments
- Open source (AGPL v3), enterprise premium tier
- Terraform-based provisioning (VMs, K8s, cloud instances)
- IDE support: VS Code, JetBrains, Jupyter, code-server
- AI governance features (agent boundaries, LLM gateway)

**Relevance**: Potential integration target for remote agent environments.
tak agents could run inside Coder workspaces.

## Standards Landscape

| Standard | Purpose | Adoption |
|----------|---------|----------|
| AGENTS.md | Project context for AI agents | Codex, Copilot, Cursor, Windsurf, Amp, Devin |
| CLAUDE.md | Claude-specific project context | Claude Code |
| .cursor/rules/*.md | Scoped rules for Cursor | Cursor |
| SKILL.md | Reusable agent capabilities | 27+ agents (Claude, Cursor, Gemini CLI) |

## Key Differentiators for tak

1. **Terminal-native integration** via iTerm2 Python API (not MCP outside-in)
2. **Tab-agent association** with `@ai` routing (unique concept)
3. **Dual interaction model**: CLI command + intercepted prefixes
4. **Cross-terminal architecture**: core/driver split enables Kitty, tmux, IDE
5. **Not just coding**: system admin, document work, research, general tasks
6. **Enterprise-friendly**: Apache 2.0, security-conscious dependencies
