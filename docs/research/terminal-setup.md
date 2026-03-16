# Terminal Environment Setup Research

This document captures research on terminal environment setup for tak: prompt customization, fonts, shell targeting, and idempotent setup commands.

## Starship

**Overview**: Cross-shell prompt written in Rust. ~48k+ stars. Version 1.24.2 (as of audit).

**Characteristics**:

- Single config file (TOML)
- ~15ms render time
- Works across bash, zsh, fish
- CVE-2024-41815 fixed in 1.20.0; current release is clean

**tak integration**:

- Custom module `[custom.tak]` can display agent info in the prompt (e.g., active agent name, session state)
- `tak setup starship` adds the module and config block

**Installation**: `brew install starship`

## JetBrains Mono Nerd Font

**Important**: A **single** brew cask provides both JetBrains Mono and Nerd Font patches:

- **Cask**: `font-jetbrains-mono-nerd-font` (v3.4.0)
- **Installs**: JetBrains Mono (code readability) + Nerd Font icons (3600+ glyphs)
- **Usage**: ~73k installs/year

**Not** two separate installs. The unpatched `font-jetbrains-mono` cask has no icons and is a different package.

**Installation**: `brew install --cask font-jetbrains-mono-nerd-font`

## Bash vs Zsh

**Strategy**: Target **bash first**.

- **macOS stock bash**: 3.2 (GPLv2; Apple does not ship newer GPLv3 bash)
- **Homebrew bash**: 5.x available via `brew install bash`
- **User context**: Many users run bash 5.x from Homebrew

**tak setup shell**:

- Detect current shell and version
- Offer upgrade to Homebrew bash if on stock 3.2
- Starship and tak work identically on bash and zsh

## Brew Integration

tak does **not** vendor tools. It relies on Homebrew for:

- `brew install starship`
- `brew install --cask font-jetbrains-mono-nerd-font`
- `brew install bash` (if user wants upgrade)

Setup commands check for presence and version before suggesting installs.

## Idempotency Principle

Every `tak setup` command must:

1. **Check before acting** — Detect current state (e.g., Starship installed, config present)
2. **Skip if done** — Do not re-add, re-install, or duplicate
3. **Report clearly** — "Already configured" vs "Configured" vs "Skipped (reason)"
4. **Use markers** — `# -- tak managed start` / `# -- tak managed end` for reversibility (e.g., in `.bashrc`)

## tak setup Command Structure

| Command | Purpose |
|---------|---------|
| `tak setup` | All-in-one: run all setup steps |
| `tak setup iterm2` | Enable API, configure preferences |
| `tak setup fonts` | Install Nerd Font (or verify) |
| `tak setup starship` | Install Starship, add tak module |
| `tak setup shell` | Configure shell rc, offer bash upgrade |
| `tak setup profiles` | Create iTerm2 profiles (non-destructive) |

## iTerm2 Preferences API

Can programmatically set preferences via `async_set_preference()`:

- `STATUS_BAR_POSITION`
- `PER_PANE_STATUS_BAR`
- `SHOW_PANE_TITLES`
- `THEME`
- Others as documented in iTerm2 API

## iTerm2 Profile API

- Can create profiles with fonts, colors, status bar components
- **Non-destructive**: Never modify existing user profiles
- Create new profiles (e.g., "tak" or "tak-agent") or offer as optional

## asdf Compatibility

- **User context**: asdf used for Python version management
- **iterm2 module**: Installs correctly into asdf-managed Python
- **Daemon**: Can run from user's Python environment rather than iTerm2's bundled runtime
- No compatibility issues identified
