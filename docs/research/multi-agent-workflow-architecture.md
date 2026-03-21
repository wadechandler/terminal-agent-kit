# Multi-Agent Workflow Architecture

A blueprint for professional, multi-agent workflows using ACP, session
management, and coordinated pipelines. Moves beyond simple "chatting" into
production-grade orchestration applicable to coding, research, ops, and
any structured work.

---

## 1. The Core Infrastructure

- **The Agent (The Host)**: The agent process (e.g. `cursor agent acp`). It
  provides the "brains" and tool access (file system, terminal, MCP tools).
- **The Session (The Thread)**: A unique, isolated conversation instance.
  Multiple sessions can run in parallel on the same connection, each with its
  own history, mode, model, and CWD.
- **The Subagent (The Recursive Worker)**: Specialized mini-workers spawned
  by an agent internally for automated background tasks (like a "searcher" or
  "executor"). These are less manually controllable than full sessions --
  surfaced via `cursor/task` extension methods.
- **Git Worktrees (The Isolation)**: The physical mechanism that allows
  parallel agents to work on the same repo in separate folders/branches
  simultaneously without file-write conflicts.

## 2. The Context Synthesis Pipeline

Instead of one "naive" request, work is broken into a high-signal chain where
each session's output is the "refined ore" for the next.

| Phase | Session Role | Key Action | Primary Artifact |
|---|---|---|---|
| Discovery | The Researcher | Interrogates the codebase via grep/tools to find relevant files and technical debt. | Q&A Technical Report |
| Definition | The Product Owner | Synthesizes user goals and the Research Report into a formal specification. | PRD / Spec |
| Decomposition | The Tech Lead | Breaks the PRD into small, atomic units of work compatible with Jira/ADO. | Task List (JSON/MD) |
| Planning | The Architect | Uses Chain of Thought (CoT) to build a step-by-step logic map for one specific task. | Implementation Plan |
| Execution | The Builder | Mounts the Plan as context in a Git Worktree and writes the actual code. | Feature Branch / PR |
| Verification | The Reviewer | Validates the Builder's Diff against the Architect's CoT and the original PRD. | Review Feedback |

## 3. Why Chain of Thought (CoT) is the "Glue"

In a multi-session architecture, CoT is not just "thinking out loud" -- it is
the structured logic passed between sessions.

- **Intent Handoff**: Captures *why* a decision was made, so the Builder
  session doesn't have to guess based on a static PRD.
- **Context Compression**: Summarizes thousands of lines of "Discovery" chat
  into a dense logic map, staying well within the Builder's context window.
- **Validation**: The Reviewer uses the Architect's CoT as a "truth source"
  to ensure the implementation didn't drift from the intended logic.

## 4. Professional Integration

- **External Tooling**: The Decomposition session can be scripted to push
  tasks directly to Azure DevOps or Jira via API, creating a natural
  human-in-the-loop checkpoint.
- **Context Mounting**: Shared artifacts (like PRD.md or PLAN.md) should be
  stored in a consistent location (e.g. `.tak/context/`) so any new ACP
  session can be initialized with that specific "memory."

---

## 5. Building Blocks (Primitives)

The layered model showing that both user interaction and pipeline
orchestration are built from the same primitives, and that pipelines reach
down to process spawning (not just session creation):

```
                    ┌─────────────────────────────────────────────┐
                    │            User-Driven                      │
                    │                                             │
                    │   Tab Agent ──► Session                     │
                    │   (user-spawned,  (conversational,          │
                    │    interactive)    long-lived)               │
                    └─────────────────────────────────────────────┘

                    ┌─────────────────────────────────────────────┐
                    │           Pipeline-Driven                   │
                    │                                             │
                    │   Pipeline Definition                       │
                    │        │                                    │
                    │        ▼                                    │
                    │   Phase (role, tools, model requirements)   │
                    │        │                    │               │
                    │        │ spawns if needed   │ creates       │
                    │        ▼                    ▼               │
                    │   Worker Process      Worker Session        │
                    │                            │               │
                    │                            ▼               │
                    │                       Artifact ───► Phase  │
                    └─────────────────────────────────────────────┘

                    ┌─────────────────────────────────────────────┐
                    │          Shared Primitives                  │
                    │                                             │
                    │   Process ──► Connection ──► Session        │
                    └─────────────────────────────────────────────┘
```

Bottom-up:

- **Process**: OS subprocess or remote endpoint running an agent binary.
  Expensive to create (~5-10s for Cursor). Started via `tak spawn`, stopped
  via `tak stop`. A pipeline run may involve N processes because different
  phases may need different tool configurations, MCP servers, models, or
  even different agent binaries.
- **Connection**: Authenticated ACP wire link to a process. Established via
  `initialize` + `authenticate`. Currently 1:1 with a process (stdio).
  Future: network transports (HTTP/SSE, SSH tunnel) where the connection is
  decoupled from process lifecycle.
- **Session**: Isolated conversation context on a connection. Cheap to create
  (~1 JSON-RPC call). Each has its own conversation history, mode, model,
  and CWD. Multiple sessions per connection are supported by ACP (confirmed:
  ACP analysis §17, ALPHA/BRAVO isolation test). The primary working unit.
  A pipeline phase may involve N sessions.
- **Prompt**: Single turn within a session. Carries user text, optional
  content blocks (images, resources), and per-prompt context (user CWD).
  Produces a stream of events (thoughts, messages, tool calls).
- **Artifact**: Output of a session or phase that can be passed as input to
  another. Lives on disk or in a shared context location. Examples: research
  report, PRD, task list, diff, test result.

## 6. Tab Agents vs Worker Agents

Two distinct lifecycle models share the same primitives:

### Tab Agents (interactive, user-owned)

- Spawned by the user (`tak spawn`), attached to a terminal tab/context
- Interactive, conversational, long-lived
- User drives them directly via `tak prompt`
- Think: "my assistant in this tab" -- helps with quick questions, tool
  installs, script writing, config editing
- Lifecycle: user spawns, user stops
- Examples: the ad-hoc agent (`_adhoc`), a named agent attached to a project
  tab

### Worker Agents (orchestrated, pipeline-owned)

- Spawned by a pipeline phase because that phase needs specific tool configs,
  MCP servers, models, or agent binaries
- Potentially automated, task-scoped, may run in the background
- User needs **visibility** (what are they doing, progress, failures) and
  **intervention capability** (pause, redirect, inspect) but does not
  normally drive them turn-by-turn
- Think: "the build team working on my task"
- Lifecycle: pipeline creates, pipeline destroys (or parks for inspection
  on failure)
- Examples: a Researcher session doing codebase analysis, a Builder session
  implementing in a git worktree

### UX implications

Both appear in `tak agents` but are distinguishable (type column: interactive
vs worker, or pipeline association). The TUI (Phase Q) would provide
different views: conversational interface for tab agents, dashboard/monitoring
view for worker agents. Both use the same underlying primitives (process,
connection, session) but with different UX surfaces.

## 7. How It Maps to tak Today

Current `AgentHandle` conflates process + connection + session (1:1:1):

- `tak spawn cursor myagent` starts a process, establishes a connection,
  and creates one session -- all stored as one `AgentHandle`
- `ACPProvider._sessions: dict[str, ACPSessionManager]` is keyed by agent
  name (one session per agent)
- `ACPProvider.send()` looks up the single session by agent name
- No way to create additional sessions on the same connection
- `stop()` kills everything; no way to end just the session

Where the model needs to evolve:

- `tak session end` should drop the session but keep process+connection alive
- Multiple sessions on one connection would avoid redundant process spawns
- The ad-hoc agent (`_adhoc`) could be a lightweight session on an existing
  connection instead of a whole separate process

Future CLI model:

- `tak spawn` creates a process+connection and gives it a name
- `tak session create [--agent name] [--name label]` creates sessions on
  that connection
- `tak prompt --session label "..."` routes to a specific session
- `tak session list` shows all sessions across all agents
- Default behavior: if no session is specified, use (or create) a default
  session for the agent

## 8. Pipeline Model

A pipeline is a coordinated workflow of phases. Key characteristics:

- A pipeline definition describes phases, roles, artifact flow, and tooling
  per phase
- A pipeline run may span **N processes with N sessions** -- pipelines are
  not just a session-layer concept; they reach down to process spawning
  because different phases may need fundamentally different agent
  configurations
- Phases are not strictly linear -- discovery and definition overlap,
  verification loops back to execution
- A phase has an associated **role/persona** with potentially a custom
  system prompt, driving details, and artifact expectations
- Pipelines apply to coding workflows, research workflows, ops workflows,
  or anything with structured phases

### How phases use the full primitive stack

- A phase definition specifies its requirements: agent binary, model, MCP
  servers, mode, tools
- The pipeline orchestrator checks if a running process already matches
  those requirements; if not, it **spawns a new process** (this is
  `tak spawn` territory, not just session creation)
- On the matching process/connection, the orchestrator creates a session
  for the phase's work
- Artifact handoff: output of phase N is mounted as context for phase N+1
  (via embedded resources, file references, prompt injection, or a shared
  context directory like `.tak/context/`)
- Different phases may use different external tools: JIRA/ADO for
  decomposition, git worktrees for execution, documentation tools for
  definition
- Worker processes created by the pipeline may be torn down after their
  phase completes, or kept alive if later phases might reuse them

## 9. Phases and Roles

The generic phase model (applicable beyond coding):

- **Discovery**: Interrogates the problem space, codebase, or domain.
  Output: research report, technical debt inventory, landscape analysis.
- **Definition**: Synthesizes goals and research into formal specification.
  Output: PRD, spec, requirements. Overlaps with discovery (raises
  questions that loop back).
- **Decomposition**: Breaks the spec into atomic work units. Output: task
  list (structured: JSON, YAML, or pushed to JIRA/ADO).
- **Planning**: Builds step-by-step implementation plan for a specific task.
  Output: implementation plan with reasoning chain (CoT as handoff artifact).
- **Execution**: Implements the plan. Output: code, docs, configs (in a git
  worktree or branch).
- **Verification**: Validates execution against the plan and original spec.
  Output: review feedback, test results, approval/rejection.

Each phase could have:

- A configurable role/persona and system prompt
- Driving details (what specifically to focus on, constraints)
- Mode (ask for discovery, plan for planning, agent for execution)
- Model selection (cheaper/faster for discovery, stronger for execution)
- Tool surface (MCP servers, external APIs)
- Phases are customizable -- a pipeline definition can include a subset of
  these phases, reorder them, or add custom phases for specific workflows

## 10. Automation and Failure Modes

Pipeline execution modes:

- **Fully automated**: phases chain without human input (useful for
  well-defined repeatable tasks)
- **Interactive**: human reviews artifacts between phases, can
  adjust/redirect
- **Hybrid**: starts automated and pauses at checkpoints, or starts manual
  and goes hands-off once approved -- either direction
- A phase can be **interrupted** mid-session if the user sees it going wrong
  (cancel + redirect)
- On **failure**: the phase session stays alive for inspection; can be
  adjusted and re-run without blocking the whole pipeline
- **Dependency management**: later phases depend on earlier artifacts; if an
  early phase re-runs, dependent phases can be invalidated and re-queued

## 11. OSS Framework Landscape

Existing frameworks that could serve as the orchestration engine rather than
building everything from scratch:

- **LangGraph** (LangChain ecosystem): Graph-based workflow with cycles,
  persistence, human-in-the-loop. Best fit for the non-linear phase model.
  Python. Would bridge to ACP sessions as execution substrate.
- **CrewAI**: Role-based multi-agent orchestration with the persona concept
  built in. Tasks, tools, delegation. Python. Maps directly to the
  phase/role model. More opinionated about agent internals.
- **AutoGen** (Microsoft): Multi-agent conversation framework. Good at
  agent-to-agent patterns but more conversational than workflow-oriented.
- **Prefect / Dagster / Temporal**: General workflow engines. Battle-tested
  for DAG execution, retry, persistence. Less AI-native but strong on
  infrastructure (dependency management, failure handling, checkpointing).

Key question: does tak use one of these as a dependency, or is the pipeline
layer thin enough to be custom? tak's unique value is the ACP/terminal
integration -- for DAG execution, retry, and checkpointing, leveraging an
existing framework avoids reinventing well-solved problems.

## 12. Protocol Surface

What's available today and what's on the horizon:

- **ACP**: Client-to-agent protocol. tak's current wire protocol. Sessions,
  prompts, streaming events, permissions, extension methods.
- **MCP**: Model Context Protocol. Extends the agent's tool surface with
  external capabilities. Already researched (ACP analysis §15). Phase MCP
  handles enablement.
- **Resources**: ACP agents have built-in `list_mcp_resources` /
  `fetch_mcp_resource`. Can expose data to agents without tool approval.
  Useful for artifact handoff.
- **A2A** (Google Agent-to-Agent): Protocol for agent interop and discovery.
  Would matter if pipeline phases need agents to discover and delegate to
  each other without tak as intermediary. Future consideration.
- **Embedded content**: ACP supports text, images, embedded resources, and
  resource links in prompts. Artifact handoff could use embedded resources
  for inline content or resource links for file references.

## 13. Terminology Reference

Quick-reference table using simple terms. No "agentic" prefix -- within
tak's context, the AI-agent nature is implicit. Use "agent session" only
when disambiguating from terminal sessions.

### Nouns

| Term | Definition |
|------|-----------|
| Process | OS subprocess or remote endpoint running an agent binary |
| Connection | Authenticated ACP wire link to a process |
| Session | Isolated conversation context on a connection (history, mode, model, CWD) |
| Prompt | Single turn within a session |
| Artifact | Output of a phase; input to the next |
| Pipeline | Coordinated workflow of phases |
| Phase | A stage of work with a role, objective, and tool surface |
| Agent (tak user-facing) | Named handle for a process+connection (currently 1:1:1 with session; evolving to 1:1:N) |
| Tab agent | User-spawned interactive agent attached to a terminal context; lifecycle owned by user |
| Worker agent | Pipeline-spawned agent for a specific phase; lifecycle owned by the pipeline orchestrator |
| Role / Persona | The identity a phase's session operates under (Researcher, Architect, Builder, Reviewer...) |

### Verbs

| Term | Definition |
|------|-----------|
| spawn | Start a process + establish connection (done by user for tab agents, by pipeline for worker agents) |
| connect | Establish connection to existing process (future: remote) |
| create session | Create a new session on a connection |
| load session | Re-attach to a prior session (preserves history) |
| prompt | Send a turn within a session |
| end session | Close a session; process+connection stay alive |
| stop | Terminate the process and all its sessions |
| run pipeline | Execute a pipeline definition, spawning processes and creating sessions as phases require |
