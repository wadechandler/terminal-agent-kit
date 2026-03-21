# Cursor ACP Behavior Report

**Generated**: 2026-03-17T19:46:05-0400
**Phases**: [21]

## Phase 1: Handshake & Introspection

### initialize

```json
{
  "_meta": null,
  "agentCapabilities": {
    "_meta": null,
    "loadSession": true,
    "mcpCapabilities": {
      "_meta": null,
      "http": true,
      "sse": true
    },
    "promptCapabilities": {
      "_meta": null,
      "audio": false,
      "embeddedContext": false,
      "image": true
    },
    "sessionCapabilities": {
      "_meta": null,
      "fork": null,
      "list": null,
      "resume": null
    }
  },
  "agentInfo": null,
  "authMethods": [
    {
      "_meta": null,
      "description": "Authenticate using existing Cursor login credentials. Run 'cursor agent login' first if not logged in.",
      "id": "cursor_login",
      "name": "Cursor Login"
    }
  ],
  "protocolVersion": 1
}
```

### authenticate

OK

### new_session

- **session_id**: `45e4b0bf-d935-4219-9bce-d8d5215995e4`

### Models

- **current_model_id**: `default[]`

| model_id | name |
|----------|------|
| `default[]` | Auto |
| `composer-1.5[]` | Composer 1.5 |
| `composer-1[]` | Composer 1 |
| `gpt-5.3-codex[reasoning=medium,fast=false]` | Codex 5.3 |
| `gpt-5.4[reasoning=medium,context=272k,fast=false]` | GPT-5.4 |
| `claude-sonnet-4-6[thinking=true,context=200k,effort=medium]` | Sonnet 4.6 |
| `claude-opus-4-6[thinking=true,context=200k,effort=high,fast=false]` | Opus 4.6 |
| `claude-opus-4-5[thinking=true]` | Opus 4.5 |
| `gpt-5.2[reasoning=medium,fast=false]` | GPT-5.2 |
| `gemini-3.1-pro[]` | Gemini 3.1 Pro |
| `gpt-5.4-mini[reasoning=medium]` | GPT-5.4 Mini |
| `gpt-5.4-nano[reasoning=medium]` | GPT-5.4 Nano |
| `claude-haiku-4-5[thinking=true]` | Haiku 4.5 |
| `gpt-5.3-codex-spark[reasoning=medium]` | Codex 5.3 Spark |
| `grok-code-fast-1[]` | Grok Code |
| `claude-sonnet-4-5[thinking=true,context=200k]` | Sonnet 4.5 |
| `gpt-5.2-codex[reasoning=medium,fast=false]` | Codex 5.2 |
| `gpt-5.1-codex-max[reasoning=medium,fast=false]` | Codex 5.1 Max |
| `gpt-5.1[reasoning=medium]` | GPT-5.1 |
| `gemini-3-pro[]` | Gemini 3 Pro |
| `gemini-3-flash[]` | Gemini 3 Flash |
| `gpt-5.1-codex-mini[reasoning=medium]` | Codex 5.1 Mini |
| `claude-sonnet-4[thinking=false,context=200k]` | Sonnet 4 |
| `gpt-5-mini[]` | GPT-5 Mini |
| `gemini-2.5-flash[]` | Gemini 2.5 Flash |
| `kimi-k2.5[]` | Kimi K2.5 |

### Modes

- **current_mode_id**: `agent`

| mode_id | name |
|---------|------|
| `agent` | Agent |
| `plan` | Plan |
| `ask` | Ask |

### Config Options

```json
[
  {
    "currentValue": "agent",
    "options": [
      {
        "_meta": null,
        "description": "Full agent capabilities with tool access",
        "name": "Agent",
        "value": "agent"
      },
      {
        "_meta": null,
        "description": "Read-only mode for planning and designing before implementation",
        "name": "Plan",
        "value": "plan"
      },
      {
        "_meta": null,
        "description": "Q&A mode - no edits or command execution",
        "name": "Ask",
        "value": "ask"
      }
    ],
    "_meta": null,
    "category": "mode",
    "description": "Controls how the agent executes tasks",
    "id": "mode",
    "name": "Mode",
    "type": "select"
  },
  {
    "currentValue": "default[]",
    "options": [
      {
        "_meta": null,
        "description": null,
        "name": "Auto",
        "value": "default[]"
      },
      {
        "_meta": null,
        "description": null,
        "name": "Composer 1.5",
        "value": "composer-1.5[]"
      },
      {
        "_meta": null,
        "description": null,
        "name": "Composer 1",
        "value": "composer-1[]"
      },
      {
        "_meta": null,
        "description": null,
        "name": "Codex 5.3",
        "value": "gpt-5.3-codex[reasoning=medium,fast=false]"
      },
      {
        "_meta": null,
        "description": null,
        "name": "GPT-5.4",
        "value": "gpt-5.4[reasoning=medium,context=272k,fast=false]"
      },
      {
        "_meta": null,
        "description": null,
        "name": "Sonnet 4.6",
        "value": "claude-sonnet-4-6[thinking=true,context=200k,effort=medium]"
      },
      {
        "_meta": null,
        "description": null,
        "name": "Opus 4.6",
        "value": "claude-opus-4-6[thinking=true,context=200k,effort=high,fast=false]"
      },
      {
        "_meta": null,
        "description": null,
        "name": "Opus 4.5",
        "value": "claude-opus-4-5[thinking=true]"
      },
      {
        "_meta": null,
        "description": null,
        "name": "GPT-5.2",
        "value": "gpt-5.2[reasoning=medium,fast=false]"
      },
      {
        "_meta": null,
        "description": null,
        "name": "Gemini 3.1 Pro",
        "value": "gemini-3.1-pro[]"
      },
      {
        "_meta": null,
        "description": null,
        "name": "GPT-5.4 Mini",
        "value": "gpt-5.4-mini[reasoning=medium]"
      },
      {
        "_meta": null,
        "description": null,
        "name": "GPT-5.4 Nano",
        "value": "gpt-5.4-nano[reasoning=medium]"
      },
      {
        "_meta": null,
        "description": null,
        "name": "Haiku 4.5",
        "value": "claude-haiku-4-5[thinking=true]"
      },
      {
        "_meta": null,
        "description": null,
        "name": "Codex 5.3 Spark",
        "value": "gpt-5.3-codex-spark[reasoning=medium]"
      },
      {
        "_meta": null,
        "description": null,
        "name": "Grok Code",
        "value": "grok-code-fast-1[]"
      },
      {
        "_meta": null,
        "description": null,
        "name": "Sonnet 4.5",
        "value": "claude-sonnet-4-5[thinking=true,context=200k]"
      },
      {
        "_meta": null,
        "description": null,
        "name": "Codex 5.2",
        "value": "gpt-5.2-codex[reasoning=medium,fast=false]"
      },
      {
        "_meta": null,
        "description": null,
        "name": "Codex 5.1 Max",
        "value": "gpt-5.1-codex-max[reasoning=medium,fast=false]"
      },
      {
        "_meta": null,
        "description": null,
        "name": "GPT-5.1",
        "value": "gpt-5.1[reasoning=medium]"
      },
      {
        "_meta": null,
        "description": null,
        "name": "Gemini 3 Pro",
        "value": "gemini-3-pro[]"
      },
      {
        "_meta": null,
        "description": null,
        "name": "Gemini 3 Flash",
        "value": "gemini-3-flash[]"
      },
      {
        "_meta": null,
        "description": null,
        "name": "Codex 5.1 Mini",
        "value": "gpt-5.1-codex-mini[reasoning=medium]"
      },
      {
        "_meta": null,
        "description": null,
        "name": "Sonnet 4",
        "value": "claude-sonnet-4[thinking=false,context=200k]"
      },
      {
        "_meta": null,
        "description": null,
        "name": "GPT-5 Mini",
        "value": "gpt-5-mini[]"
      },
      {
        "_meta": null,
        "description": null,
        "name": "Gemini 2.5 Flash",
        "value": "gemini-2.5-flash[]"
      },
      {
        "_meta": null,
        "description": null,
        "name": "Kimi K2.5",
        "value": "kimi-k2.5[]"
      }
    ],
    "_meta": null,
    "category": "model",
    "description": "Controls which model is used for responses",
    "id": "model",
    "name": "Model",
    "type": "select"
  }
]
```

## Phase 21: MCP via .cursor/mcp.json

### mcp_config_written

- Config path: `/var/folders/vj/tkmrz5cj4yz56zrtvb8lvc540000gn/T/tak-inspect-mcp-9_1q8fl0/.cursor/mcp.json`
- Servers configured: tak-test-echo, tak-test-echo-http

### initialize

- Response: `{"_meta": null, "agentCapabilities": {"_meta": null, "loadSession": true, "mcpCapabilities": {"_meta": null, "http": true, "sse": true}, "promptCapabilities": {"_meta": null, "audio": false, "embeddedContext": false, "image": true}, "sessionCapabilities": {"_meta": null, "fork": null, "list": null, `

### new_session

- Session ID: `8418d3bd-92ad-499d-a18b-f9bef5dd6cbd`

### list_tools

- Duration: 25.3s
- Stop reason: `end_turn`
- Updates: 245

### mcp_stdio_echo

- Duration: 60.8s
- Stop reason: `end_turn`
- Updates: 275
- Permissions: 1

### mcp_http_echo

- Duration: 28.4s
- Stop reason: `end_turn`
- Updates: 128
- Permissions: 2

## Ideation & Application

See [analysis.md](analysis.md) for full reasoning, discovery, and UX ideation
derived from this data.
