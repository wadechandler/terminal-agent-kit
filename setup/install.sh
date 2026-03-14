#!/usr/bin/env bash
# Terminal Agent Kit (tak) -- Environment Bootstrap
# Installs common developer tools on macOS.
# Run: bash setup/install.sh
set -euo pipefail

echo "=== Terminal Agent Kit -- Environment Setup ==="
echo ""

# Check for Homebrew
if ! command -v brew &>/dev/null; then
    echo "Homebrew not found. Install it from https://brew.sh"
    exit 1
fi

echo "[1/3] Installing Starship prompt..."
if command -v starship &>/dev/null; then
    echo "  Starship already installed: $(starship --version)"
else
    brew install starship
    echo "  Installed. Add 'eval \"\$(starship init bash)\"' to your shell rc file."
fi

echo ""
echo "[2/3] Installing JetBrains Mono Nerd Font..."
if brew list --cask font-jetbrains-mono-nerd-font &>/dev/null 2>&1; then
    echo "  JetBrains Mono Nerd Font already installed."
else
    brew install --cask font-jetbrains-mono-nerd-font
    echo "  Installed. Set it in iTerm2: Preferences > Profiles > Text > Font."
fi

echo ""
echo "[3/3] Installing terminal-agent-kit..."
if command -v tak &>/dev/null; then
    echo "  tak already on PATH: $(tak --version 2>/dev/null || echo 'installed')"
else
    echo "  Install with: pip install -e .[dev]"
fi

echo ""
echo "=== Setup complete ==="
