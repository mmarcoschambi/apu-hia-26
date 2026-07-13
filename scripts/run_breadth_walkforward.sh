#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUTDIR="$ROOT/outputs/experiments/breadth_walkforward"
mkdir -p "$OUTDIR"

FOLDS=(
  "2022-01-01 2022-06-30 2022-07-01 2022-09-30"
  "2022-04-01 2022-09-30 2022-10-01 2022-12-31"
  "2022-07-01 2022-12-31 2023-01-01 2023-03-31"
  "2022-10-01 2023-03-31 2023-04-01 2023-06-30"
  "2023-01-01 2023-06-30 2023-07-01 2023-09-30"
  "2023-04-01 2023-09-30 2023-10-01 2023-12-31"
  "2023-07-01 2023-12-31 2024-01-01 2024-03-31"
  "2023-10-01 2024-03-31 2024-04-01 2024-06-30"
  "2024-01-01 2024-06-30 2024-07-01 2024-09-30"
  "2024-04-01 2024-09-30 2024-10-01 2024-12-31"
  "2024-07-01 2024-12-31 2025-01-01 2025-03-31"
  "2024-10-01 2025-03-31 2025-04-01 2025-06-30"
  "2025-01-01 2025-06-30 2025-07-01 2025-09-30"
  "2025-04-01 2025-09-30 2025-10-01 2025-12-31"
  "2025-07-01 2025-12-31 2026-01-01 2026-04-30"
)

for fold in "${FOLDS[@]}"; do
  read -r IS_START IS_END OOS_START OOS_END <<< "$fold"
  TAG="${IS_START}_${OOS_END}"
  LOG="$OUTDIR/breadth_b_${TAG}.log"
  JSON="$OUTDIR/breadth_b_${TAG}.json"

  printf 'Running fold %s -> %s\n' "$IS_START" "$OOS_END"

  stdbuf -oL -eL timeout 2h python3 "$ROOT/experiments/breadth_sandbox.py" \
    --mode b \
    --configs S0 B_040 B_050 B_060 \
    --is-start "$IS_START" \
    --is-end "$IS_END" \
    --oos-start "$OOS_START" \
    --oos-end "$OOS_END" \
    2>&1 | tee "$LOG" || true

  grep -E "Report saved|Traceback|Error computing breadth mask|ValueError" "$LOG" || true
  latest_json=$(ls -t "$ROOT/outputs/experiments"/breadth_sandbox_*.json 2>/dev/null | head -n 1)
  if [[ -n "${latest_json:-}" ]]; then
    cp "$latest_json" "$JSON" || true
  fi
done
