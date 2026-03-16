# Future Vision: Warp-like Agent Session Mode

This document captures a future vision for an agent session mode similar to Warp's agent integration. It is **Phase 4+ territory** — captured so the idea is not lost, not implemented in the near term.

## Overview

Two modes per tab:

1. **Bash mode** (default): Normal shell. tak is out of the performance-critical loop; no input interception.
2. **Agent mode**: Entered via `tak enter <agent>`. Input is routed to the agent instead of the shell.

## Agent Mode Behavior

- **Enter key**: Sends input to the agent (no shell execution)
- **Special syntax**:
  - `/exit` — Exit agent mode, return to bash
  - `/bash <cmd>` — Run a single command in bash, then return to agent mode
  - `@tak <cmd>` — Invoke tak CLI command (e.g., `@tak list`)

## Exit

- `/exit` or `tak exit` — Leave agent mode, return to bash mode for that tab

## Routing Question

**How do we know if input is a command or a prompt?**

- **First approach**: Explicit mode toggle. User is in agent mode or bash mode; no ambiguity.
- **Future**: Small local model for classification (e.g., "is this a natural language prompt or a shell command?"). Not required for v1.

## iTerm2 Mapping

- **KeystrokeFilter**: In agent mode, intercept Enter; in bash mode, no interception
- **Per-tab state**: One tab can be in agent mode while others remain in bash mode
- **Tab-agent association**: Session registry already tracks which agent is bound to which tab; session mode extends this

## Implementation Notes

- Phase 4+ — after core agent management, CLI, daemon, and basic @tak interception are stable
- Requires careful UX design to avoid confusion (clear mode indicator, discoverable commands)
- Warp and other terminals provide reference implementations for UX patterns
