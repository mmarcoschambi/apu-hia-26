#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

cd "${ROOT_DIR}"

if [ -f ".venv/bin/python" ]; then
    .venv/bin/python scripts/paper_demo_telegram.py "$@"
else
    python3 scripts/paper_demo_telegram.py "$@"
fi
