#!/bin/bash
# falgen installer — installs via pipx, pip, or uvx
set -e

echo "Installing falgen..."

if command -v pipx &>/dev/null; then
    pipx install falgen
    echo "Installed via pipx. Run: falgen"
elif command -v uv &>/dev/null; then
    uv tool install falgen
    echo "Installed via uv. Run: falgen"
elif command -v pip3 &>/dev/null; then
    pip3 install --user falgen
    echo "Installed via pip3. Run: falgen"
elif command -v pip &>/dev/null; then
    pip install --user falgen
    echo "Installed via pip. Run: falgen"
else
    echo "Error: Python pip not found. Install Python 3.11+ first."
    echo "  brew install python3    # macOS"
    echo "  sudo apt install python3-pip  # Ubuntu/Debian"
    exit 1
fi
