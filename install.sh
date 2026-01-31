#!/usr/bin/env bash
set -euo pipefail

# Samuel System — Linux Install Script
# Sets up venv, installs deps, and installs systemd services.

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
VENV_DIR="$SCRIPT_DIR/.venv"

echo "=== Samuel System Install ==="
echo ""

# --- Check Python version ---
PYTHON=""
for candidate in python3.13 python3.12 python3.11 python3.10 python3; do
    if command -v "$candidate" &>/dev/null; then
        version=$("$candidate" -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
        major=$(echo "$version" | cut -d. -f1)
        minor=$(echo "$version" | cut -d. -f2)
        if [ "$major" -ge 3 ] && [ "$minor" -ge 10 ]; then
            PYTHON="$candidate"
            break
        fi
    fi
done

if [ -z "$PYTHON" ]; then
    echo "ERROR: Python 3.10+ is required."
    echo ""
    echo "Install with:"
    echo "  sudo apt install -y python3 python3-venv python3-pip"
    exit 1
fi

echo "Using $PYTHON ($($PYTHON --version))"

# --- Check for .env ---
ENV_FILE="$SCRIPT_DIR/.env"
if [ ! -f "$ENV_FILE" ]; then
    echo ""
    echo "WARNING: .env not found."
    echo "  Copy .env.example and fill in your values:"
    echo "    cp $SCRIPT_DIR/.env.example $ENV_FILE"
    echo ""
fi

# --- Create venv ---
echo ""
echo "Creating virtual environment at $VENV_DIR ..."
"$PYTHON" -m venv "$VENV_DIR"
source "$VENV_DIR/bin/activate"

# --- Install dependencies ---
echo "Installing dependencies ..."
pip install --quiet --upgrade pip
pip install --quiet -r "$SCRIPT_DIR/requirements.txt"
echo "Dependencies installed."

# --- Create data directory ---
DATA_DIR="${DATA_DIR:-$HOME/data}"
mkdir -p "$DATA_DIR"
echo "Data directory: $DATA_DIR"

# --- Install systemd services ---
echo ""
read -r -p "Install systemd services (auto-start on boot)? (y/N) " install_service
if [[ "$install_service" == "y" || "$install_service" == "Y" ]]; then
    sudo cp "$SCRIPT_DIR/systemd/samuel-mcp.service" /etc/systemd/system/
    sudo cp "$SCRIPT_DIR/systemd/samuel-bridge.service" /etc/systemd/system/
    sudo systemctl daemon-reload
    sudo systemctl enable samuel-mcp samuel-bridge
    sudo systemctl start samuel-mcp samuel-bridge

    echo ""
    echo "Services installed and started."
    echo ""
    echo "Manage with:"
    echo "  sudo systemctl status samuel-mcp"
    echo "  sudo systemctl status samuel-bridge"
    echo "  sudo systemctl restart samuel-mcp"
    echo "  sudo systemctl restart samuel-bridge"
    echo "  journalctl -u samuel-mcp -f"
    echo "  journalctl -u samuel-bridge -f"
else
    echo "Skipped service install."
    echo ""
    echo "Run manually with:"
    echo "  source $VENV_DIR/bin/activate"
    echo "  python -m samuel          # MCP server (port 5100)"
    echo "  python -m samuel.bridge   # Bridge server (port 5101)"
fi

echo ""
echo "=== Install Complete ==="
echo ""
echo "Samuel MCP will listen on port ${SAMUEL_PORT:-5100}."
echo "Samuel Bridge will listen on port ${BRIDGE_PORT:-5101}."
echo ""
echo "Connect Claude Code:"
echo "  claude mcp add --transport http samuel http://<this-ip>:5100/mcp"
echo ""
echo "Test bridge:"
echo "  curl http://localhost:5101/ping"
