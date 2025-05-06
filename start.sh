#!/usr/bin/env bash

# Get the directory of this script
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Change to the script directory
cd "$SCRIPT_DIR"

# Ensure environment is set up
source .venv/bin/activate

# Run the server using uv and the correct path to server.py
uv run mcp run src/server.py 