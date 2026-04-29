#!/usr/bin/env bash
set -euo pipefail

ROOT="/home/marcos/trade/momentum-v2"
TRIAD_CFG="$ROOT/config/screeners/triad_rts.json"
VCP_CFG="$ROOT/outputs/best_combos_run/combo_triad_rts_vcp_config.json"
OUTDIR="$ROOT/outputs/triad_sweep_vcp"
mkdir -p "$OUTDIR"

cp "$TRIAD_CFG" "$OUTDIR/triad_rts.json.bak"
cp "$VCP_CFG" "$OUTDIR/combo_triad_rts_vcp_config.json.bak"

# name,as5,as21,rts,rs
PROFILES=(
  "S0_STRICT,50,50,90,70"
  "S1_BALANCED,45,45,85,65"
  "S2_RELAXED,40,40,80,60"
  "S3_LOOSE,35,35,75,55"
)

echo "profile,as5,as21,rts,rs,verdict,sharpe_mean,pf_mean,trades_total,folds_valid" > "$OUTDIR/summary.csv"

for P in "${PROFILES[@]}"; do
  IFS=',' read -r NAME AS5 AS21 RTS RS <<< "$P"
  echo "=== $NAME ==="

  python3 - <<PY
import json, pathlib
triad_path = pathlib.Path("$TRIAD_CFG")
vcp_path = pathlib.Path("$VCP_CFG")

triad = json.loads(triad_path.read_text())
triad["params"]["min_as_5d_pct"] = float("$AS5")
triad["params"]["min_as_21d_pct"] = float("$AS21")
triad["params"]["min_rts_pct"] = float("$RTS")
triad_path.write_text(json.dumps(triad, indent=2))

vcp = json.loads(vcp_path.read_text())
vcp.setdefault("tier2_filters", {})
vcp["tier2_filters"]["min_rs_percentile"] = float("$RS")
vcp_path.write_text(json.dumps(vcp, indent=2))
PY

  # Rebuild cache PIT para este perfil (2022-2025, unión de universos WF)
  python3 - <<'PY'
import sqlite3
import sys
from pathlib import Path

# Add root to sys.path to find src
root = Path("/home/marcos/trade/momentum-v2")
sys.path.append(str(root))

from src.data.screener_cache import ScreenerCacheManager

db = root / "data/ticker_cache.db"
folds = [("2022-01-01","2022-12-31"),("2023-01-01","2023-12-31"),("2024-01-01","2024-12-31"),("2025-01-01","2025-12-31")]
u=set()
with sqlite3.connect(str(db)) as c:
    for s,e in folds:
        rows = c.execute("""
            SELECT ticker, COUNT(*) as cnt
            FROM ohlcv_cache
            WHERE date >= ? AND date <= ?
            GROUP BY ticker
            ORDER BY cnt DESC
            LIMIT 200
        """,(s,e)).fetchall()
        u.update(r[0] for r in rows)

scm = ScreenerCacheManager(root / "data/screener_cache")
scm.build_for_combo("triad_rts", sorted(u), "2022-01-01", "2025-12-31")
PY

  python3 scripts/walk_forward_combos.py --combo combo_triad_rts_vcp \
    2>&1 | tee "$OUTDIR/${NAME}.log"

  cp outputs/walk_forward/combo_triad_rts_vcp_wf.json "$OUTDIR/${NAME}_wf.json"

  python3 - <<PY
import json
from pathlib import Path
p = Path("$OUTDIR/${NAME}_wf.json")
d = json.loads(p.read_text())
a = d.get("aggregate", {})
row = [
  "$NAME","$AS5","$AS21","$RTS","$RS",
  a.get("verdict",""),
  a.get("sharpe_mean",0),
  a.get("pf_mean",0),
  a.get("trades_total",0),
  a.get("folds_valid",0),
]
print(",".join(map(str,row)))
with open("$OUTDIR/summary.csv","a") as f:
  f.write(",".join(map(str,row)) + "\n")
PY
done

# restore originales
cp "$OUTDIR/triad_rts.json.bak" "$TRIAD_CFG"
cp "$OUTDIR/combo_triad_rts_vcp_config.json.bak" "$VCP_CFG"

echo "Listo: $OUTDIR/summary.csv"
