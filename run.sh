#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

if [ ! -d .venv ]; then
    echo "Run ./setup.sh first."
    exit 1
fi

# liquidctl needs root for USB access
exec sudo "$SCRIPT_DIR/.venv/bin/python" -m rgb_control.app "$@"
