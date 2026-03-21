# Phase MCP: MCP Integration

## Goal

Enable MCP (Model Context Protocol) servers for ACP agents via proper
`.cursor/mcp.json` configuration and pre-approval workflow. This allows
agents to use custom tools (database queries, API calls, browser automation)
beyond their built-in capabilities.

## Context

ACP analysis §15 documented the full MCP investigation across 6 rounds of
testing. Key findings:

1. **`new_session(mcp_servers=[...])` is inert for Cursor.** The parameter
   is accepted silently but servers are never connected. MCP servers must be
   configured via `.cursor/mcp.json` in the project directory.

2. **MCP tools require pre-approval in ACP mode.** A known Cursor
   approval-middleware bug blocks MCP tools silently. The workaround is to
   run `cursor agent mcp enable <name>` before spawning the ACP agent.

3. **MCP resources work without approval.** `list_mcp_resources` and
   `fetch_mcp_resource` are always available as built-in agent tools.

4. **Approval persists.** Once approved via `cursor agent mcp enable`,
   the approval file at `~/.cursor/projects/<slug>/mcp-approvals.json`
   persists across sessions. Re-enable is only needed once per project
   per server.

### Cursor MCP CLI Commands

| Command | Purpose |
|---------|---------|
| `cursor agent mcp list` | Show configured MCP servers and status |
| `cursor agent mcp enable <name>` | Approve a server (~1.5s) |
| `cursor agent mcp disable <name>` | Remove approval |
| `cursor agent mcp list-tools <name>` | List tools from a server |
| `cursor agent mcp login <name>` | OAuth for remote MCPs |

## Files to Read First

- `src/tak/providers/acp.py` -- `ACPProvider.spawn()` (where MCP enable runs)
- `src/tak/cli/main.py` -- `spawn` command (where `--with-mcp` flag goes)
- `src/tak/providers/acp_session.py` -- `new_session()` (mcp_servers param)
- `docs/research/agents/cursor-acp-behavior/analysis.md` -- §15

## What to Build

### 1. Read `.cursor/mcp.json` (pmcp-read-config)

**`src/tak/providers/mcp.py`** (new file):
- `read_mcp_config(project_path: Path) -> dict[str, dict]`
  Reads `.cursor/mcp.json` from the project directory. Returns a mapping
  of server name to server config. Returns empty dict if file not found.
- `filter_servers(servers: dict, pattern: str) -> list[str]`
  Filters server names by glob pattern. `"*"` matches all.

The `.cursor/mcp.json` format:
```json
{
  "mcpServers": {
    "server-name": {
      "command": "python",
      "args": ["server.py"],
      "type": "stdio"
    },
    "http-server": {
      "url": "http://localhost:8080/"
    }
  }
}
```

### 2. Enable MCP Servers Before Spawn (pmcp-enable-servers)

**`src/tak/providers/acp.py`** -- `ACPProvider.spawn()`:
- Accept an optional `mcp_servers: list[str] | None` parameter.
- When provided, for each server name:
  - Run `cursor agent mcp enable <name>` as a subprocess.
  - Set CWD to the project directory (approval is project-scoped).
  - Log success/failure per server.
  - Continue spawning even if some servers fail to enable.

**`src/tak/providers/mcp.py`**:
- `async enable_mcp_server(name: str, cwd: Path) -> bool`
  Runs the enable command and returns success.

### 3. `--with-mcp` Flag on CLI (pmcp-with-mcp-flag)

**`src/tak/cli/main.py`** -- `spawn` command:
- Add `--with-mcp` option (multiple=True, default=None).
  - No value or `"*"`: enable all servers in `.cursor/mcp.json`.
  - Named value: enable only that server.
  - Glob pattern: filter matching servers.
  - Omitted: do not run mcp enable (current behavior).
- Pass the list through IPC to the daemon.

**`src/tak/ipc/server.py`** -- `_handle_spawn`:
- Accept `mcp_servers` param and pass to provider.

### 4. `tak mcp list` Command (pmcp-list-servers)

**`src/tak/cli/main.py`**:
- Add `mcp` command group with `list` subcommand.
- `tak mcp list [--project PATH]`: reads `.cursor/mcp.json` and displays
  configured servers in a Rich table.
- Optionally runs `cursor agent mcp list` for live status if Cursor CLI
  is available.

### 5. Provider-Generic MCP Interface (pmcp-provider-generic)

**`src/tak/providers/base.py`**:
- Add optional `enable_mcp_servers(names, project_path)` method to
  `BaseProvider` with a no-op default.
- `ACPProvider` overrides with the Cursor-specific implementation.
- Other providers (Goose, Claude Code) can override with their own
  MCP registration mechanisms.

## Tests

**`tests/providers/test_mcp.py`**:
- Test `read_mcp_config` with valid JSON.
- Test `read_mcp_config` with missing file.
- Test `filter_servers` with glob patterns.
- Test `enable_mcp_server` subprocess call (mocked).

**`tests/providers/test_acp.py`**:
- Test spawn with `mcp_servers` parameter calls enable.
- Test spawn without `mcp_servers` skips enable.

**`tests/cli/test_cli.py`**:
- Test `--with-mcp` flag parsing.
- Test `tak mcp list` command.

## Acceptance Criteria

1. `tak spawn cursor-acp -n my-agent -p /path --with-mcp` reads
   `.cursor/mcp.json` and runs `cursor agent mcp enable` for each server.
2. `tak spawn ... --with-mcp my-server` enables only `my-server`.
3. `tak mcp list --project /path` shows configured MCP servers.
4. MCP enable failures are logged but do not block agent spawn.
5. Providers without MCP support silently skip the enable step.
6. All existing tests pass. `ruff check` clean.

## Agent Prompt

> Read `docs/tasks/phase-mcp-integration.md` for the full spec. This phase
> adds MCP server integration for ACP agents. Read "Files to Read First",
> then implement each item in "What to Build" in order. Run
> `ruff check src/ tests/` and `pytest -q` after each change. Update
> manifest.yaml when done.
