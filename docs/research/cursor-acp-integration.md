# Cursor CLI ACP Integration

Reference: https://cursor.com/docs/cli/acp

## What is ACP?

Agent Client Protocol (ACP) is Cursor CLI's machine-readable interface for
subprocess-based integration. It enables custom clients to communicate with
Cursor's AI agent over stdio using JSON-RPC 2.0.

## Protocol Details

- **Start command**: `agent acp`
- **Transport**: stdio (newline-delimited JSON, one message per line)
- **Protocol**: JSON-RPC 2.0
- **Direction**: Client writes requests/notifications to stdin, Cursor CLI
  writes responses to stdout, logs go to stderr

## Authentication

Pre-authenticate using one of:
- `--api-key` flag
- `CURSOR_API_KEY` environment variable
- `agent login` command before starting ACP

## Output Formats (non-ACP modes)

For simpler, non-interactive use:
- `--output-format text` (default)
- `--output-format json`
- `--output-format stream-json` (with `--stream-partial-output`)

These use the `-p/--print` flag for headless operation.

## Integration Architecture for tak

```
tak AgentManager
  └── CursorACPProvider
        ├── spawn: subprocess.Popen(["cursor", "agent", "acp"], stdin=PIPE, stdout=PIPE, stderr=PIPE)
        ├── send: write JSON-RPC request to stdin
        ├── receive: read JSON-RPC response from stdout
        └── stop: terminate subprocess
```

### Provider Implementation Sketch

```python
class CursorACPProvider(BaseProvider):
    protocol = "acp"

    async def spawn(self, name: str, project_path: str) -> AgentHandle:
        process = await asyncio.create_subprocess_exec(
            "cursor", "agent", "acp",
            "--project", project_path,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        return AgentHandle(name=name, process=process, protocol=self.protocol)

    async def send(self, handle: AgentHandle, message: str) -> str:
        request = json_rpc_request("agent/query", {"message": message})
        handle.process.stdin.write(json.dumps(request).encode() + b"\n")
        await handle.process.stdin.drain()
        response_line = await handle.process.stdout.readline()
        return json.loads(response_line)

    async def stop(self, handle: AgentHandle) -> None:
        handle.process.terminate()
        await handle.process.wait()
```

## Open Research Questions

- [ ] What are the exact JSON-RPC method names for ACP? (Need to test or
      find detailed protocol docs beyond the overview page.)
- [ ] Does ACP support streaming responses? (Likely yes given stream-json
      exists in non-ACP mode.)
- [ ] Can we pass context (file contents, terminal output) in ACP requests?
- [ ] Does Cursor CLI ACP support session resumption? (Critical for restart
      recovery.)
- [ ] What happens to the ACP subprocess when the parent process dies?
      Does it clean up or orphan?
- [ ] Can multiple ACP sessions share a single Cursor authentication token?
- [ ] What's the ACP startup time? Relevant for "quick agent" use case.
