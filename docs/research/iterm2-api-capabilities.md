# iTerm2 Python API Capabilities

Reference: https://iterm2.com/python-api (v0.26)

## Overview

iTerm2 provides a comprehensive Python API for scripting and automation.
Scripts communicate via a loopback websocket using async/await patterns.
Available as the `iterm2` package on PyPI. Requires Python 3.

## Key Classes and Capabilities

### Session Management
- Create, close, activate sessions
- Retrieve session contents (screen buffer)
- Inject text/commands into sessions (`session.async_inject()`)
- Add annotations to lines
- Set/get user-defined variables per session
- Monitor prompt state (EDITING, RUNNING, FINISHED) via shell integration

### Window and Tab Control
- Create tabs and windows
- Activate/focus specific tabs
- Get current window/tab/session
- Arrange terminal layouts

### Profile Management
- Query all profiles (`PartialProfile.async_query()`)
- Create/modify profiles programmatically
- Set fonts, colors, working directory, title settings
- Make profiles default
- ANSI color customization (all 16 colors)

### Status Bar Components
- Create custom status bar widgets
- Configuration knobs (checkboxes, text fields)
- Variable references for auto-update
- Variable-length responsive text
- Run as long-lived daemons (AutoLaunch folder)

### RPC Functions
- Register Python functions triggered by keyboard shortcuts
- `@iterm2.RPC` decorator
- Access to context variables (session ID, etc.)
- Can be invoked via keybindings or triggers

### Event Hooks
- Session creation/termination
- Tab changes, focus changes
- Variable updates (user-defined or built-in)
- Keyboard events
- Custom control sequences

### Triggers
- Pattern matching on terminal output
- Can invoke RPCs or scripts
- Useful for intercepting specific text patterns

### Broadcasting
- Send input to multiple sessions simultaneously
- Useful for multi-agent scenarios

### Transactions
- Atomic multi-step operations
- Ensures consistency when reading/writing multiple values

## Script Deployment

- **AutoLaunch**: `~/Library/Application Support/iTerm2/Scripts/AutoLaunch/`
  Scripts here run automatically when iTerm2 starts. Used for daemons.
- **One-shot**: Scripts that run once and exit.
- **run_forever()**: For daemon scripts that should persist.
- **run_until_complete()**: For one-shot scripts.

## Capabilities Relevant to tak

| Need | API | Notes |
|------|-----|-------|
| Tab-agent association | User-defined variables per session | `session.async_set_variable("user.agent_id", "cursor-1")` |
| Intercept `@ai` input | Triggers + RPC | Trigger matches `^@ai\s`, invokes RPC |
| Inject agent response | `session.async_inject()` | Write response text into session |
| Status bar agent info | StatusBarComponent | Show active agent name, status |
| Tab switching overlay | Window/Tab APIs + RPC | Custom RPC triggered by keybinding |
| Screen content reading | Session content retrieval | For context-aware `@ai` queries |
| Profile per agent | Profile management | Color-coded agent sessions |
| Restart recovery | Session variables + state file | Re-associate tabs on daemon restart |

## Open Research Questions

- [ ] Can triggers intercept text BEFORE it reaches the shell? (Triggers match
      on output, which happens after shell echo. May need shell integration
      hooks or a custom readline wrapper instead.)
- [ ] What's the latency of session.async_inject() for response display?
- [ ] Can we create floating/overlay windows via the API? (Likely no --
      may need a complementary approach like a split pane or popup.)
- [ ] How does the API behave when iTerm2 is restarted? Does it cleanly
      signal daemon scripts to shut down?
- [ ] Can user-defined variables survive iTerm2 restart if session
      restoration is enabled?
