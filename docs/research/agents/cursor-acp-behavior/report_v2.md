# Cursor ACP Behavior Report

**Generated**: 2026-03-17T17:42:46-0400
**Phases**: [8, 9, 10, 11, 12, 13, 14]

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

- **session_id**: `ded6cc5d-8b4b-4f35-a002-6d36fb9a2b67`

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

## Phase 8: Usage & Cost Tracking

### short_prompt_usage

- Duration: 8.9s
- Stop reason: `end_turn`
- Updates: 31

### usage_update_events

- UsageUpdate events: 0

### longer_prompt_usage

- Duration: 32.2s
- Stop reason: `end_turn`
- Updates: 315

## Phase 9: Config Option Mutation + Plan Mode

### set_config_option_mode_plan

- Success: True
- Updates received after call: 1
  - `current_mode_update`

### Plan mode prompt

- AgentPlanUpdate events: 1
- CurrentModeUpdate events: 0
- Duration: 38.0s
- Stop reason: `end_turn`
- Updates: 157

### set_config_option_mode_agent

- Success: True
- Updates received after call: 1
  - `current_mode_update`

### set_config_option_model_haiku

- Success: True

### set_config_option_invalid_mode

- Success: False
- Error: code=-32602, Invalid params

### set_config_option_bogus_id

- Success: False
- Error: code=-32602, Invalid params

## Phase 10: Permission Rejection

### forced_terminal_rejected_1

- Permissions requested: 2
  - Tool: `python3 -c 'print(42)'`, Decision: reject-once
  - Tool: `python3 -c 'print(42)'`, Decision: reject-once
- Duration: 12.6s
- Stop reason: `end_turn`
- Updates: 48
- Permissions: 2

### forced_terminal_rejected_2

- Permissions requested: 1
  - Tool: `echo hello`, Decision: reject-once
- Duration: 10.7s
- Stop reason: `end_turn`
- Updates: 36
- Permissions: 1

## Phase 11: Longer-Running Task

### multi_file_project

- Time to first update: 5.09s
- Max gap between updates: 5.43s
- Tool call count: 10
- Think/respond/work cycles: 17
- Duration: 59.4s
- Stop reason: `end_turn`
- Updates: 305
- Permissions: 1

### Update Type Summary

| Type | Count | First (s) | Last (s) | Duration (s) |
|------|-------|-----------|----------|--------------|
| `agent_message_chunk` | 67 | 15.10 | 59.35 | 44.25 |
| `agent_thought_chunk` | 208 | 5.09 | 55.17 | 50.08 |
| `tool_call` | 10 | 15.26 | 53.66 | 38.40 |
| `tool_call_update` | 20 | 17.15 | 54.01 | 36.85 |

### Phase Timeline

| Phase | Start (s) | End (s) | Duration (s) |
|-------|-----------|---------|--------------|
| thinking | 5.09 | 15.10 | 10.01 |
| responding | 15.10 | 15.26 | 0.15 |
| working | 15.26 | 22.96 | 7.70 |
| thinking | 22.96 | 23.68 | 0.72 |
| responding | 23.68 | 23.77 | 0.10 |
| working | 23.77 | 32.63 | 8.86 |
| thinking | 32.63 | 36.15 | 3.52 |
| responding | 36.15 | 36.20 | 0.05 |
| working | 36.20 | 44.52 | 8.32 |
| thinking | 44.52 | 45.32 | 0.80 |
| responding | 45.32 | 45.46 | 0.14 |
| working | 45.46 | 52.96 | 7.50 |
| thinking | 52.96 | 53.32 | 0.35 |
| responding | 53.32 | 53.66 | 0.34 |
| working | 53.66 | 55.17 | 1.51 |
| thinking | 55.17 | 55.68 | 0.51 |
| responding | 55.68 | 59.35 | 3.67 |

## Phase 12: Session Load/Resume

### load_valid_session

- Success: True
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
  ],
  "models": {
    "_meta": null,
    "availableModels": [
      {
        "_meta": null,
        "description": null,
        "modelId": "default[]",
        "name": "Auto"
      },
      {
        "_meta": null,
        "description": null,
        "modelId": "composer-1.5[]",
        "name": "Composer 1.5"
      },
      {
        "_meta": null,
        "description": null,
        "modelId": "composer-1[]",
        "name": "Composer 1"
      },
      {
        "_meta": null,
        "description": null,
        "modelId": "gpt-5.3-codex[reasoning=medium,fast=false]",
        "name": "Codex 5.3"
      },
      {
        "_meta": null,
        "description": null,
        "modelId": "gpt-5.4[reasoning=medium,context=272k,fast=false]",
        "name": "GPT-5.4"
      },
      {
        "_meta": null,
        "description": null,
        "modelId": "claude-sonnet-4-6[thinking=true,context=200k,effort=medium]",
        "name": "Sonnet 4.6"
      },
      {
        "_meta": null,
        "description": null,
        "modelId": "claude-opus-4-6[thinking=true,context=200k,effort=high,fast=false]",
        "name": "Opus 4.6"
      },
      {
        "_meta": null,
        "description": null,
        "modelId": "claude-opus-4-5[thinking=true]",
        "name": "Opus 4.5"
      },
      {
        "_meta": null,
        "description": null,
        "modelId": "gpt-5.2[reasoning=medium,fast=false]",
        "name": "GPT-5.2"
      },
      {
        "_meta": null,
        "description": null,
        "modelId": "gemini-3.1-pro[]",
        "name": "Gemini 3.1 Pro"
      },
      {
        "_meta": null,
        "description": null,
        "modelId": "gpt-5.4-mini[reasoning=medium]",
        "name": "GPT-5.4 Mini"
      },
      {
        "_meta": null,
        "description": null,
        "modelId": "gpt-5.4-nano[reasoning=medium]",
        "name": "GPT-5.4 Nano"
      },
      {
        "_meta": null,
        "description": null,
        "modelId": "claude-haiku-4-5[thinking=true]",
        "name": "Haiku 4.5"
      },
      {
        "_meta": null,
        "description": null,
        "modelId": "gpt-5.3-codex-spark[reasoning=medium]",
        "name": "Codex 5.3 Spark"
      },
      {
        "_meta": null,
        "description": null,
        "modelId": "grok-code-fast-1[]",
        "name": "Grok Code"
      },
      {
        "_meta": null,
        "description": null,
        "modelId": "claude-sonnet-4-5[thinking=true,context=200k]",
        "name": "Sonnet 4.5"
      },
      {
        "_meta": null,
        "description": null,
        "modelId": "gpt-5.2-codex[reasoning=medium,fast=false]",
        "name": "Codex 5.2"
      },
      {
        "_meta": null,
        "description": null,
        "modelId": "gpt-5.1-codex-max[reasoning=medium,fast=false]",
        "name": "Codex 5.1 Max"
      },
      {
        "_meta": null,
        "description": null,
        "modelId": "gpt-5.1[reasoning=medium]",
        "name": "GPT-5.1"
      },
      {
        "_meta": null,
        "description": null,
        "modelId": "gemini-3-pro[]",
        "name": "Gemini 3 Pro"
      },
      {
        "_meta": null,
        "description": null,
        "modelId": "gemini-3-flash[]",
        "name": "Gemini 3 Flash"
      },
      {
        "_meta": null,
        "description": null,
        "modelId": "gpt-5.1-codex-mini[reasoning=medium]",
        "name": "Codex 5.1 Mini"
      },
      {
        "_meta": null,
        "description": null,
        "modelId": "claude-sonnet-4[thinking=false,context=200k]",
        "name": "Sonnet 4"
      },
      {
        "_meta": null,
        "description": null,
        "modelId": "gpt-5-mini[]",
        "name": "GPT-5 Mini"
      },
      {
        "_meta": null,
        "description": null,
        "modelId": "gemini-2.5-flash[]",
        "name": "Gemini 2.5 Flash"
      },
      {
        "_meta": null,
        "description": null,
        "modelId": "kimi-k2.5[]",
        "name": "Kimi K2.5"
      }
    ],
    "currentModelId": "default[]"
  },
  "modes": {
    "_meta": null,
    "availableModes": [
      {
        "_meta": null,
        "description": "Full agent capabilities with tool access",
        "id": "agent",
        "name": "Agent"
      },
      {
        "_meta": null,
        "description": "Read-only mode for planning and designing before implementation",
        "id": "plan",
        "name": "Plan"
      },
      {
        "_meta": null,
        "description": "Q&A mode - no edits or command execution",
        "id": "ask",
        "name": "Ask"
      }
    ],
    "currentModeId": "agent"
  }
}
```

### load_bogus_session

- Success: False
- Error: code=-32602, Invalid params

## Phase 13: Image Prompt + Embedded Resource

### image_with_text

- Duration: 8.8s
- Stop reason: `end_turn`
- Updates: 19

### image_only

- Duration: 9.3s
- Stop reason: `end_turn`
- Updates: 23

### embedded_resource

- Duration: 8.2s
- Stop reason: `end_turn`
- Updates: 34

## Phase 14: MCP Tool Discovery

### mcp_session_created

- Session ID: `e66ad07e-2241-4c6c-8874-80a189c329ba`
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

### mcp_echo_tool_use

- Duration: 35.7s
- Stop reason: `end_turn`
- Updates: 302


### mcp_tool_listing

- Duration: 16.8s
- Stop reason: `end_turn`
- Updates: 160


## Ideation & Application

See [analysis.md](analysis.md) for full reasoning, discovery, and UX ideation
derived from this data.
