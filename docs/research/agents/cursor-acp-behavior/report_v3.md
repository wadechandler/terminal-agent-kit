# Cursor ACP Behavior Report

**Generated**: 2026-03-17T18:58:16-0400
**Phases**: [15, 16, 17, 18, 19, 20]

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

- **session_id**: `e2bb2835-9a22-4735-bbff-d94d18dd4361`

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

## Phase 15: Java/TypeScript Compilation

### java_compile_run

- Duration: 13.6s
- Stop reason: `end_turn`
- Updates: 37
- Permissions: 1

### typescript_run

- Duration: 33.0s
- Stop reason: `end_turn`
- Updates: 97
- Permissions: 4

## Phase 16: MCP Tool Discovery (HTTP Transport)

### http_mcp_session_created

- Session ID: `7e7f7de2-e239-4dda-8aed-20e64e8f3b3b`
```json
{
  "_meta": null,
  "configOptions": [
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
          "value": "claude-opus-4-6[thinking=true,context=200k,effort=hi
```

### http_mcp_echo_tool_use

- Duration: 15.1s
- Stop reason: `end_turn`
- Updates: 180


### http_mcp_tool_listing

- Duration: 16.7s
- Stop reason: `end_turn`
- Updates: 225


## Phase 17: load_session Conversation Recall

### set_code_word

- Duration: 8.1s
- Stop reason: `end_turn`
- Updates: 41

### load_session_for_recall

- Success: True

### recall_code_word

- Duration: 5.7s
- Stop reason: `end_turn`
- Updates: 19

## Phase 18: ResourceContentBlock (URI-based)

### resource_link_file_uri

- URI: `file:///var/folders/vj/tkmrz5cj4yz56zrtvb8lvc540000gn/T/tak-inspect-vs2kmpjj/hello.py`
- Duration: 7.0s
- Stop reason: `end_turn`
- Updates: 24

### resource_link_http_uri

- URI: `http://127.0.0.1:52318/resources/config.txt`
- Duration: 10.0s
- Stop reason: `end_turn`
- Updates: 86

### text_path_baseline

- Duration: 8.0s
- Stop reason: `end_turn`
- Updates: 32

## Phase 19: Agent-Initiated Mode Switching

### prompted_mode_switch

- CurrentModeUpdate events: 0
- AgentPlanUpdate events: 0
- Duration: 24.5s
- Stop reason: `end_turn`
- Updates: 286
- Permissions: 1

## Phase 20: Multi-Session Isolation

### create_session_a

- Session ID: `add5dacc-d4fa-4fa5-a738-93d62cee8c69`
- Success: True

### create_session_b

- Session ID: `ffe21e00-60dc-4fde-9d0a-d8a8bdcdc401`
- Success: True

### set_word_session_a

- Duration: 5.5s
- Stop reason: `end_turn`
- Updates: 21

### set_word_session_b

- Duration: 6.7s
- Stop reason: `end_turn`
- Updates: 30

### recall_session_a

- Duration: 7.7s
- Stop reason: `end_turn`
- Updates: 12

### recall_session_b

- Duration: 5.4s
- Stop reason: `end_turn`
- Updates: 11

## Ideation & Application

See [analysis.md](analysis.md) for full reasoning, discovery, and UX ideation
derived from this data.
