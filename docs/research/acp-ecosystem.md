# ACP (Agent Client Protocol) Ecosystem Research

This document captures research findings on the Agent Client Protocol ecosystem, its adoption across tools, and implications for tak's provider architecture.

## Protocol Overview

ACP is **JSON-RPC 2.0 over stdio**. It originated with Cursor and is becoming a de facto standard for agent-to-client communication. The protocol enables structured request/response and streaming interactions between AI agents and host applications.

## Implementations by Vendor

### Cursor CLI

Cursor provides native ACP support. Both invocation forms work:

- `cursor agent acp`
- `agent acp`

**Flags:**

| Flag | Purpose |
|------|---------|
| `--model` | Model to use at spawn |
| `--mode` | Session mode: `ask`, `plan`, or `agent` |
| `--list-models` | List available agent models |
| `--api-key` | API key override |
| `--workspace` | Workspace path |
| `--sandbox` | Sandbox configuration |
| `--approve-mcps` | MCP approval policy |
| `--trust` | Trust settings |

### Goose (Block)

Goose is **actively migrating to ACP** as its single protocol. The `goose-acp` crate is in development. Phased rollout planned for February 2026. ACP will replace the custom REST+SSE API.

### Claude Code (Anthropic)

- **Native ACP support**: Request closed as "not planned" (February 2026).
- **Community adapter**: Zed Industries built `claude-agent-acp` (v0.21.0, ~1.1k stars), which wraps the Claude Agent SDK and exposes an ACP-compatible interface.

## Architectural Implication for tak

**tak should build a generic ACPProvider** instead of per-agent providers (e.g., CursorProvider, GooseProvider, ClaudeProvider). A single ACPProvider can spawn any ACP-compatible agent binary and communicate via the standard protocol. Agent-specific behavior (model selection, mode defaults) can be configured per-agent in tak's config.

## Full ACP Session Flow

1. **initialize** — Protocol handshake
2. **authenticate** — Client authentication
3. **session/new** (or **session/load**) — Create or restore a session
4. **session/prompt** — Send user prompt to agent
5. **session/update** (streaming) — Agent streams progress, tool calls, responses
6. **session/request_permission** — Agent requests permission; client responds
7. **session/cancel** — Cancel in-flight request

## Session Modes

| Mode | Capabilities |
|------|--------------|
| `ask` | Read-only. Agent can read files, answer questions. No writes or tool execution. |
| `plan` | Read-only. Agent can create plans, update todos. No execution. |
| `agent` | Full tool access. Agent can run commands, edit files, use MCP tools. |

## Permission Handling

- **Method**: `session/request_permission`
- **Client responses**: `reject-once`, `allow-once`, `allow-always`
- **Behavior**: Agent blocks until the client responds. No timeout-based fallback in the base protocol.

## Cursor Extension Methods

Cursor extends ACP with additional methods:

- `cursor/ask_question` — Ask user a question
- `cursor/create_plan` — Create a plan
- `cursor/update_todos` — Update todo list
- `cursor/task` — Task management
- `cursor/generate_image` — Image generation

These are Cursor-specific; a generic ACPProvider would pass them through without special handling unless tak adds Cursor-specific features.

## Model Selection

- **At spawn**: `--model` flag when launching the agent process
- **Listing**: `agent models` or `--list-models` to enumerate available models
- **Mid-session**: `session/set_config_option` may support model changes (unverified)

## References

- Cursor CLI documentation
- Goose/Block migration announcements (Feb 2026)
- Anthropic Claude Code ACP request (closed)
- Zed Industries `claude-agent-acp` repository
