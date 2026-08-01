"""validate_s4_oomc.py - Bloque 2: OOS validation de los 6 sobrevivientes S4."""
from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "scratch"))

import pandas as pd

from src.analytics.simulation_pack import run_monte_carlo_full
from scripts.walk_forward_combos import get_universe_from_db
from scripts.s4_optuna_run import build_engine_kwargs_from_params
from src.validation.purged_walk_forward import PurgedWalkForwardValidator

from run_mc_combo_neutral import (
    aggregate_positions, bootstrap_sharpe, compute_psr_dsr, daily_sharpe_annualized,
)

OOS_START = "2024-01-01"
OOS_END = "2025-12-31"
N_SEARCH_TRIALS = 1000
UNIVERSE_SIZE = 199
RESULTS_JSON = ROOT / "outputs" / "optuna_s4" / "results_momentum_s4_prod_20260801_172540.json"
RECEIPT_DIR = ROOT / "artifacts" / "purged_cv"
PARAMS_DIR = ROOT / "artifacts" / "s4_candidates"
OUT_DIR = ROOT / "outputs" / "optuna_s4"

OOS_FOLDS = [
    {"fold": 1, "oos_start": "2024-01-01", "oos_end": "2024-12-31"},
    {"fold": 2, "oos_start": "2025-01-01", "oos_end": "2025-12-31"},
]


def git_head() -> str:
    try:
        import subprocess
        return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True, encoding="utf-8").strip()
    except Exception:
        return "UNKNOWN_GIT_HASH"


def load_survivors() -> List[Dict[str, Any]]:
    with open(RESULTS_JSON, "r", encoding="utf-8") as f:
        data = json.load(f)
    passed_ids = {
        str(cid) for cid, gr in data["gate_results"].items()
        if gr.get("passed", False)
    }
    survivors = [c for c in data["candidates"] if str(c["trial_id"]) in passed_ids]
    survivors.sort(key=lambda c: -c["score_composed"])
    return survivors

def run_oos_backtest(params, universe):
    from src.backtest.vectorbt_engine_advanced import AdvancedVectorBTEngine
    kwargs = build_engine_kwargs_from_params(params)
    engine = AdvancedVectorBTEngine(universe=universe, start_date=OOS_START, end_date=OOS_END, initial_capital=100_000, **kwargs)
    engine.load_data()
    result = engine.run_backtest()
    engine.cleanup()
    return result


def oos_mc_analysis(result, n_sims=1000, n_boot=2000):
    trades_df = result.get("trades_df", pd.DataFrame())
    equity = result.get("equity_curve", pd.Series())
    out = {"engine": {"sharpe": result.get("sharpe_ratio"), "profit_factor": result.get("profit_factor"), "total_trades": int(result.get("total_trades", 0)), "mdd": result.get("max_drawdown")}}
    if trades_df is None or len(trades_df) == 0:
        out["error"] = "empty_trades_df"
        return out
    pos_returns = aggregate_positions(trades_df)
    out["n_positions"] = int(len(pos_returns))
    out["bootstrap"] = bootstrap_sharpe(pos_returns, n_boot=n_boot)
    out["psr_dsr"] = compute_psr_dsr(pos_returns, n_trials=N_SEARCH_TRIALS)
    if len(equity) > 2:
        out["equity"] = {"initial": round(float(equity.iloc[0]), 2), "final": round(float(equity.iloc[-1]), 2), "n_days": int(len(equity)), "daily_sharpe_ann": round(daily_sharpe_annualized(equity), 4)}
        mc = run_monte_carlo_full(equity, n_sims=n_sims, projection_days=252)
        s = mc.get("summary", {})
        out["mc_summary"] = {"expected_growth": float(s.get("expected_growth", 0)), "median_outcome": float(s.get("median_outcome", 0)), "risk_of_loss": float(s.get("risk_of_loss", 0)), "mean_outcome": float(s.get("mean_outcome", 0))}
    return out


def run_purged_cv(params, universe, params_json_source, receipt_path):
    validator = PurgedWalkForwardValidator(n_folds=len(OOS_FOLDS), purge_days=10, embargo_days=5)
    from src.backtest.vectorbt_engine_advanced import AdvancedVectorBTEngine
    t0 = time.time()
    report = validator.validate(engine_class=AdvancedVectorBTEngine, params=build_engine_kwargs_from_params(params), universe=universe, fold_definitions=OOS_FOLDS)
    dt = time.time() - t0
    payload = {
        "generated_at_utc": datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"),
        "git_commit": git_head(),
        "params_json_source": params_json_source,
        "universe_size": len(universe),
        "train_start": "2019-01-01",
        "oos_folds": OOS_FOLDS,
        "purged_cv_config": {"n_folds": len(OOS_FOLDS), "purge_days": 10, "embargo_days": 5},
        "degradation_pct": round(report.degradation_pct, 2),
        "gate_passed": report.gate_passed,
        "gate_threshold_pct": 25,
        "is_sharpe_mean": round(report.is_sharpe_mean, 4),
        "oos_sharpe_mean": round(report.oos_sharpe_mean, 4),
        "trades_per_fold": report.trades_per_fold,
        "total_oos_trades": int(sum(report.trades_per_fold)),
        "warnings": report.warnings,
        "folds": [asdict(f) for f in report.folds],
        "runtime_s": round(dt, 1),
    }
    receipt_path.parent.mkdir(parents=True, exist_ok=True)
    with open(receipt_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False, sort_keys=True)
    return payload

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--n-sims", type=int, default=1000)
    parser.add_argument("--n-boot", type=int, default=2000)
    parser.add_argument("--only", type=str, default=None)
    args = parser.parse_args()

    survivors = load_survivors()
    if args.only:
        only = {s.strip() for s in args.only.split(",")}
        survivors = [c for c in survivors if str(c["trial_id"]) in only]

    print(f"[B2] Survivors a validar OOS: {[c['trial_id'] for c in survivors]}")
    universe = get_universe_from_db(OOS_START, OOS_END, UNIVERSE_SIZE)
    print(f"[B2] Universe OOS: {len(universe)} tickers")

    PARAMS_DIR.mkdir(parents=True, exist_ok=True)
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    consolidated = {"period": {"oos_start": OOS_START, "oos_end": OOS_END}, "n_search_trials_for_dsr": N_SEARCH_TRIALS, "run_at_utc": datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"), "git_commit": git_head(), "candidates": {}}

    for cand in survivors:
        tid = cand["trial_id"]
        print(f"\n{'='*60}\n[B2] Trial {tid} (score={cand['score_composed']}, cost={cand['cost_robustness']})")
        params_json = PARAMS_DIR / f"s4_candidate_trial{tid}_params.json"
        with open(params_json, "w", encoding="utf-8") as f:
            json.dump(build_engine_kwargs_from_params(cand["params"]), f, indent=2)
        src = str(params_json.relative_to(ROOT)).replace("\\", "/")

        res = run_oos_backtest(cand["params"], universe)
        oos_anal = oos_mc_analysis(res, n_sims=args.n_sims, n_boot=args.n_boot)

        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        receipt = RECEIPT_DIR / f"purged_cv_report_{ts}_s4trial{tid}.json"
        purged = run_purged_cv(cand["params"], universe, src, receipt)

        consolidated["candidates"][str(tid)] = {
            "score_composed": cand["score_composed"],
            "cost_robustness": cand["cost_robustness"],
            "is_metrics": {"sharpe": cand.get("is_sharpe"), "pf": cand.get("pf"), "calmar": cand.get("calmar"), "trades": cand.get("trades")},
            "oos_analysis": oos_anal,
            "purged_cv": {k: v for k, v in purged.items() if k != "folds"},
            "purged_cv_folds": purged.get("folds"),
            "receipt": str(receipt.relative_to(ROOT)).replace("\\", "/"),
            "params_json_source": src,
        }

        d = oos_anal.get("psr_dsr", {})
        print(f"  OOS trades(pos)={oos_anal.get('n_positions')} | DSR={d.get('dsr')} PBO_mc={d.get('pbo_mc_equiv')} | risk_loss={oos_anal.get('mc_summary', {}).get('risk_of_loss')}")
        print(f"  PurgedCV degradation={purged['degradation_pct']}% gate={purged['gate_passed']} oos_trades_total={purged['total_oos_trades']}")

    out_path = OUT_DIR / f"oos_validation_6_survivors_{consolidated['run_at_utc']}.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(consolidated, f, indent=2, ensure_ascii=False, default=str)
    print(f"\n[B2] Consolidado guardado: {out_path}")


if __name__ == "__main__":
    main()
