#!/usr/bin/env python3
"""A/B walk-forward experiment for Industry Group Filter (Sector ETF).

Runs baseline vs sector ETF filter variants over the same WF folds and writes
a compact JSON report for investment-committee review.
"""

from __future__ import annotations

import json
import logging
import sys
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scripts.walk_forward_combos import WF_FOLDS, load_combo_params, run_oos_fold

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)

OUT_DIR = ROOT / "outputs" / "experiments"
OUT_DIR.mkdir(parents=True, exist_ok=True)


def aggregate_folds(folds: list[dict[str, Any]]) -> dict[str, Any]:
    valid = [f for f in folds if f.get("status") == "ok"]
    if not valid:
        return {
            "folds": 0,
            "trades_total": 0,
            "sharpe_mean": 0.0,
            "sharpe_min": 0.0,
            "pf_mean": 0.0,
            "pf_min": 0.0,
            "return_mean": 0.0,
        }

    sharpes = np.array([f["sharpe"] for f in valid], dtype=float)
    pfs = np.array([f["pf"] for f in valid], dtype=float)
    rets = np.array([f["total_return"] for f in valid], dtype=float)
    trades = np.array([f["trades"] for f in valid], dtype=int)

    return {
        "folds": int(len(valid)),
        "trades_total": int(trades.sum()),
        "sharpe_mean": round(float(sharpes.mean()), 3),
        "sharpe_min": round(float(sharpes.min()), 3),
        "pf_mean": round(float(pfs.mean()), 3),
        "pf_min": round(float(pfs.min()), 3),
        "return_mean": round(float(rets.mean()), 2),
    }


def run_variant(
    combo: str, params: dict[str, Any], variant_name: str
) -> dict[str, Any]:
    logger.info("\n=== Variant: %s ===", variant_name)
    rows = []
    for fold in WF_FOLDS:
        logger.info(
            "Fold %s | %s -> %s",
            fold["fold"],
            fold["oos_start"],
            fold["oos_end"],
        )
        result = run_oos_fold(combo, params, fold)
        rows.append(result)
        logger.info(
            "  trades=%s sharpe=%s pf=%s return=%s%% status=%s",
            result["trades"],
            result["sharpe"],
            result["pf"],
            result["total_return"],
            result["status"],
        )

    return {
        "name": variant_name,
        "folds": rows,
        "aggregate": aggregate_folds(rows),
    }


def main() -> None:
    combo = "combo_pure_momentum"
    base_params = load_combo_params(combo)

    variants = []
    
    # S0: Baseline
    p0 = deepcopy(base_params)
    p0.setdefault("tier2_filters", {})
    p0["tier2_filters"]["use_sector_etf_filter"] = False
    variants.append(run_variant(combo, p0, "S0_baseline_off"))

    # S1: SMA20
    p1 = deepcopy(base_params)
    p1.setdefault("tier2_filters", {})
    p1["tier2_filters"]["use_sector_etf_filter"] = True
    p1["tier2_filters"]["sector_etf_sma_period"] = 20
    variants.append(run_variant(combo, p1, "S1_sma20"))
    
    # S2: SMA50
    p2 = deepcopy(base_params)
    p2.setdefault("tier2_filters", {})
    p2["tier2_filters"]["use_sector_etf_filter"] = True
    p2["tier2_filters"]["sector_etf_sma_period"] = 50
    variants.append(run_variant(combo, p2, "S2_sma50"))

    # S3: SMA40
    p3 = deepcopy(base_params)
    p3.setdefault("tier2_filters", {})
    p3["tier2_filters"]["use_sector_etf_filter"] = True
    p3["tier2_filters"]["sector_etf_sma_period"] = 40
    variants.append(run_variant(combo, p3, "S3_sma40"))

    report = {
        "run_at": datetime.now().isoformat(),
        "combo": combo,
        "variants": variants,
    }

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = OUT_DIR / f"sector_filter_ablation_{combo}_{ts}.json"
    with out_path.open("w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    logger.info("\nSaved experiment report: %s", out_path)
    
    # Print summary
    logger.info("\n=== SUMMARY ===")
    for v in variants:
        agg = v["aggregate"]
        logger.info(f"{v['name']:<18} | Trades: {agg['trades_total']:<4} | Sharpe: {agg['sharpe_mean']:<5.2f} | PF: {agg['pf_mean']:<5.2f}")


if __name__ == "__main__":
    main()
