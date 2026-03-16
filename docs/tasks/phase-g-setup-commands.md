# Phase G: Terminal Environment Setup Commands

## Goal

Implement the `tak setup` CLI commands that configure the user's terminal
environment: iTerm2 API, fonts, Starship prompt, shell config, iTerm2
profiles, and the all-in-one orchestrator.

## Design Principle: Idempotency

Every command MUST be safe to run repeatedly:
- Check before acting (is the font installed? is the API enabled?)
- Skip if done, report "already configured"
- Never duplicate entries
- Report clearly what was done, skipped, and what needs manual action
- Use markers (`# -- tak managed start/end --`) for reversibility

## Files to Read First

- `src/tak/cli/main.py` -- existing stub commands to wire up
- `docs/research/terminal-setup.md` -- Starship, fonts, bash, brew decisions
- `docs/research/iterm2-security.md` -- API enablement details
- `AGENTS.md` -- project conventions
- `.cursor/rules/workspace-safety.mdc` -- allowed write zones

## What to Build

Create `src/tak/setup/` package with one module per command.

### 1. `src/tak/setup/__init__.py` (empty)

### 2. `src/tak/setup/iterm2.py` -- `tak setup iterm2`

1. Check if Python API is enabled: read plist with
   `defaults read com.googlecode.iterm2 EnableAPIServer` (returns 1 if enabled)
2. If not enabled: run `defaults write com.googlecode.iterm2 EnableAPIServer -bool true`
   and tell user to restart iTerm2
3. Test connection: try `iterm2.Connection.async_create()` with a short timeout
4. Print instructions for keybinding setup (cannot assign keys programmatically)
5. Report status with Rich console output

### 3. `src/tak/setup/fonts.py` -- `tak setup fonts`

1. Check if JetBrainsMono Nerd Font is installed:
   `ls ~/Library/Fonts/*JetBrainsMono*Nerd* 2>/dev/null` or
   `system_profiler SPFontsDataType | grep -i jetbrainsmono` or simpler:
   check if the brew cask is installed via `brew list --cask font-jetbrains-mono-nerd-font`
2. If not: check brew is available, then `brew install --cask font-jetbrains-mono-nerd-font`
3. If brew not available: print manual install instructions
4. Report status

### 4. `src/tak/setup/starship.py` -- `tak setup starship`

1. Check if Starship is installed: `which starship`
2. If not: `brew install starship` (or print manual instructions if no brew)
3. Check `~/.config/starship.toml`:
   - If exists: check for `[custom.tak]` section. If missing, append it.
   - If not exists: copy template from `config/starship.toml`
4. The tak custom module config:
   ```toml
   [custom.tak]
   command = "echo $TAK_AGENT"
   when = '[ -n "$TAK_AGENT" ]'
   format = "via [tak:$output](bold blue) "
   ```

### 5. `src/tak/setup/shell.py` -- `tak setup shell`

1. Detect current shell and bash version
2. If macOS stock bash 3.2: warn and suggest `brew install bash`
3. Check `~/.bashrc` for `# -- tak managed start --` marker
4. If marker found: report already configured
5. If not found: append the managed block:
   ```bash
   # -- tak managed start --
   eval "$(starship init bash)"
   # -- tak managed end --
   ```
6. Do NOT touch `~/.bash_profile`, `~/.zshrc`, etc.

### 6. `src/tak/setup/profiles.py` -- `tak setup profiles`

1. Connect to iTerm2 via the `iterm2` package
2. List existing profiles via `iterm2.PartialProfile.async_query()`
3. Check if a `tak-default` profile already exists
4. If not: create one with:
   - JetBrainsMono Nerd Font (if installed)
   - A distinctive color scheme
5. Report what was created
6. Print instructions for adding status bar component manually

### 7. `src/tak/setup/tak_setup.py` -- `tak setup tak`

Orchestrator that runs all 5 in sequence:
1. `setup_iterm2()`
2. `setup_fonts()`
3. `setup_starship()`
4. `setup_shell()`
5. `setup_profiles()`

Each step uses Rich console to show progress, confirmations, and results.

### 8. Wire into CLI

Update `src/tak/cli/main.py` to import and call the actual setup functions
instead of printing stubs.

### 9. Create `config/starship.toml`

Template Starship config with the tak custom module and sensible defaults.

## Tests to Write

- `tests/setup/test_fonts.py`: mock subprocess calls to brew, test
  idempotency (already installed → skip)
- `tests/setup/test_starship.py`: mock which/brew, test config merge vs
  fresh create, test idempotent append of [custom.tak]
- `tests/setup/test_shell.py`: use tmp_path for fake .bashrc, test marker
  detection, test idempotent append, test bash version detection
- `tests/setup/test_iterm2_setup.py`: mock defaults read/write, mock iterm2
  connection
- `tests/cli/test_cli.py`: verify new setup commands still pass (they do
  as stubs; confirm they still work when wired)

## Acceptance Criteria

- `ruff check src/ tests/` passes with zero errors
- All tests pass
- Each `tak setup X` command:
  - Is idempotent (running twice produces same result)
  - Reports what it did and what was skipped
  - Does not modify files outside allowed zones
- `config/starship.toml` exists with tak module

## Dependencies

- None on other phases. Can run independently.
- Actually running `brew install` and `defaults write` requires the user's
  machine. Tests should mock all external commands.

## Safety Notes

Per `.cursor/rules/workspace-safety.mdc`:
- `~/.bashrc` modification only in `setup_shell()`
- `~/.config/starship.toml` only in `setup_starship()`
- `defaults write` only in `setup_iterm2()`
- `brew` commands only in setup functions
- Never touch `~/.bash_profile`, `~/.zshrc`, `~/.profile`

---

## Agent Prompt

```
Read AGENTS.md for project conventions, then read these files:
- src/tak/cli/main.py
- docs/research/terminal-setup.md
- docs/research/iterm2-security.md
- .cursor/rules/workspace-safety.mdc

Then read docs/tasks/phase-g-setup-commands.md for the full task spec.

Implement everything described in the task file. Create the src/tak/setup/
package with all modules, the config/starship.toml template, wire the CLI,
and write all tests. Every setup command must be idempotent. Mock all
external commands (brew, defaults, which) in tests. Run ruff check and
pytest after each major piece. Do not stop until ruff check src/ tests/
shows zero errors and all tests pass.
```
