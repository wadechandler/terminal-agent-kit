# Tryout Guide

How to install, run, and test tak -- and how to clean everything up afterward.
Steps marked **(agent)** can be executed by an AI agent. Steps marked
**(human)** require you to act in the iTerm2 GUI.

## Prerequisites

| Requirement | Minimum | Check |
|-------------|---------|-------|
| Python | 3.11+ | `python3 --version` |
| pip | any recent | `pip --version` |
| Homebrew | any recent | `brew --version` |
| iTerm2 | 3.5.11+ | iTerm2 > About iTerm2 |
| Cursor CLI | any (optional) | `cursor --version` |
| git | any | `git --version` |

Cursor CLI is only needed for the ACP provider. All other commands work without
it.

> **asdf users**: If you use [asdf](https://asdf-vm.com/) for Python version
> management, make sure a global Python is set so that `python3` resolves
> correctly outside of project directories:
>
> ```bash
> asdf set -u python <version>   # e.g. asdf set -u python 3.13.5
> ```

## Install

**(agent)**

```bash
git clone https://github.com/wadechandler/terminal-agent-kit.git
cd terminal-agent-kit
pip install -e ".[dev]"
```

Verify:

```bash
tak --version
tak --help
```

## Standalone Commands (No Daemon Needed)

These work immediately after install.

### Scaffold

```bash
# Generate an AGENTS.md for the current directory
tak scaffold agents

# Generate .cursor/rules/ structure
tak scaffold rules

# Generate a SKILL.md (will prompt for name/description)
tak scaffold skills --name "my-skill" --desc "Does something useful"
```

### New Project

```bash
# Quick mode (no interactive prompts)
tak new project my-app --quick --desc "A demo app" --language Python

# Interactive mode
tak new project my-app
```

### TUI Dashboard

```bash
tak menu
# Press 'q' to quit
```

The TUI shows an empty agent table when the daemon isn't running.

### Setup (Dry Run)

```bash
# Preview what each setup step would do (when --dry-run is available)
tak setup tak --dry-run
```

Without `--dry-run`, each setup command modifies the system (see below).

## Setup Commands (Modifies System)

Each command is idempotent -- safe to run multiple times.

### All-in-One

```bash
tak setup tak
```

This runs the following in order: iterm2 > fonts > starship > shell > profiles.

### Individual Steps

```bash
tak setup iterm2     # Enable Python API via defaults write
tak setup fonts      # Install JetBrains Mono Nerd Font via brew
tak setup starship   # Install Starship and add [custom.tak] module
tak setup shell      # Add Starship init to ~/.bashrc (managed markers)
tak setup profiles   # Create tak-default iTerm2 profile
```

### After Setup

**(human)** After running `tak setup iterm2`:
1. Open iTerm2 > Settings > General > Magic
2. Verify "Enable Python API" is checked
3. Restart iTerm2

## Daemon Deployment

The daemon is an iTerm2 Python API script that runs inside iTerm2. It manages
agents, serves IPC for the CLI, and provides the status bar and RPC functions.

### Deploy the Daemon

**(agent)**

```bash
# Create the AutoLaunch directory if needed
mkdir -p ~/Library/Application\ Support/iTerm2/Scripts/AutoLaunch/

# Symlink the daemon (editable install -- changes take effect on restart)
ln -sf "$(python3 -c 'import tak.drivers.iterm2.daemon; import os; print(os.path.abspath(tak.drivers.iterm2.daemon.__file__))')" \
  ~/Library/Application\ Support/iTerm2/Scripts/AutoLaunch/tak_daemon.py
```

**(human)** Restart iTerm2. The daemon starts automatically. When prompted,
approve the script's API access.

### Verify the Daemon

```bash
# Check if the IPC socket exists
ls ~/.tak/daemon.sock

# List agents (should return empty list if daemon is running)
tak agents
```

## Daemon-Dependent Commands

These require the daemon to be running in iTerm2.

```bash
# Spawn an agent
tak spawn cursor-acp --name my-agent --project ~/code/my-project

# List running agents
tak agents

# Ask a question
tak ask what files are in this directory

# Ask with a specific agent
tak ask --agent my-agent explain this project

# Stop an agent
tak stop my-agent

# Switch to an agent's tab
tak switch my-agent

# Rename an agent
tak rename my-agent better-name
```

## Cleanup / Reset

To completely remove tak's effects and restore iTerm2 to its previous state:

### 1. Remove the Daemon

**(agent)**

```bash
rm -f ~/Library/Application\ Support/iTerm2/Scripts/AutoLaunch/tak_daemon.py
```

**(human)** Restart iTerm2.

### 1b. Uninstall tak from iterm2env

**(agent)**

If you ran `tak setup iterm2-pip` (or `tak setup tak`), tak was installed into
iTerm2's bundled Python. Remove it:

```bash
pip_python=$(ls ~/.config/iterm2/AppSupport/iterm2env/versions/*/bin/python3 2>/dev/null | head -1)
if [ -n "$pip_python" ]; then
    "$pip_python" -m pip uninstall -y terminal-agent-kit
fi
```

### 2. Revert iTerm2 API Setting

**(agent)**

```bash
# Disable the Python API (only if you didn't use it before tak)
defaults write com.googlecode.iterm2 EnableAPIServer -bool false
```

**(human)** Restart iTerm2.

### 3. Remove the tak iTerm2 Profile

**(human)** Open iTerm2 > Settings > Profiles. Select "tak-default" (if it
exists) and click the minus button to delete it.

### 4. Revert Shell Config

**(agent)**

The managed block in `~/.bashrc` is fenced with markers:

```bash
# -- tak managed start --
eval "$(starship init bash)"
# -- tak managed end --
```

Remove everything between (and including) those markers:

```bash
sed -i.bak '/# -- tak managed start --/,/# -- tak managed end --/d' ~/.bashrc
```

### 5. Remove tak State

**(agent)**

```bash
rm -rf ~/.tak
```

### 6. Uninstall tak

**(agent)**

```bash
pip uninstall terminal-agent-kit
```

### 7. Optionally Remove Brew Packages

Only do this if you installed these specifically for tak:

```bash
brew uninstall --cask font-jetbrains-mono-nerd-font
brew uninstall starship
```

## Troubleshooting

**"daemon not running"**: The IPC socket at `~/.tak/daemon.sock` doesn't exist.
Verify the daemon symlink exists and iTerm2 has been restarted with API enabled.

**Connection test fails during `tak setup iterm2`**: iTerm2 may need a restart
after enabling the Python API. The setup command prints manual steps.

**Permission errors**: The daemon requires iTerm2's "Allow running of API
scripts" permission. This is prompted on first run.

**iterm2 package import errors**: The daemon runs inside iTerm2's Python
environment. If running `python -c 'import iterm2'` fails outside iTerm2,
that's expected -- the iTerm2 API is only available to scripts running under
iTerm2's script host.
