#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

cd "${ROOT_DIR}"

if [ -f ".venv/bin/python" ]; then
    .venv/bin/python scripts/telegram_bot_listener.py "$@"
else
    python3 scripts/telegram_bot_listener.py "$@"
fi
