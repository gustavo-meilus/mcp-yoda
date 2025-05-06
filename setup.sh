#!/usr/bin/env bash

# Get the directory of this script
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Check for python3 and version >= 3.10
PYTHON_BIN="python3"
PYTHON_OK=$($PYTHON_BIN -c 'import sys; print(sys.version_info >= (3,10))' 2>/dev/null)
if [ "$PYTHON_OK" != "True" ]; then
    echo "Python 3.10 or newer is required. Please install it and try again."
    exit 1
fi

# Remove old venv if exists
if [ -d ".venv" ]; then
    echo "Removing old .venv..."
    rm -rf .venv
fi

# Create new venv
$PYTHON_BIN -m venv .venv

# Activate venv
source .venv/bin/activate

# Install dependencies with uv
if [ -f requirements.txt ]; then
    uv pip install -r requirements.txt
else
    uv pip install .
fi

# Make run_yoda_server.sh executable if it exists
if [ -f run_yoda_server.sh ]; then
    chmod +x run_yoda_server.sh
fi

echo "Setup complete. To start the server, run ./run_yoda_server.sh" 