import argparse
import json
import logging
import sys
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.backtest.vectorbt_engine_advanced import AdvancedVectorBTEngine
from src.data.pit_universe import PointInTimeUniverse

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

INITIAL_CAPITAL = 100_000
RISK_DOLLARS = 1_000.0
BASE_MIN_RVOL = 1.5
BASE_MIN_CONSOLIDATION_DAYS = 5

IS_START = "2022-01-01"
IS_END = "2024-06-30"
OOS_START = "2024-07-01"
OOS_END = "2025-06-30"
HOLDOUT_START = "2025-07-01"
HOLDOUT_END = datetime.now().strftime("%Y-%m-%d")

CONFIGS = {
    "S0_15pct": 15.0,
    "S1_12pct": 12.0,
    "S2_10pct": 10.0,
    "S3_8pct": 8.0,
    "S4_6pct": 6.0,
}

WF_IS_MONTHS = 4
WF_OOS_MONTHS = 2
WF_STEP_MONTHS = 2


@dataclass
class PeriodMetrics:
    sharpe: float
    win_rate: float
    max_dd: float
    profit_factor: float
    total_trades: int
    avg_r_multiple: float
    all_exits: int


def _safe_float(value: object) -> float:
    if value is None:
        return 0.0
    try:
        value = float(value)
    except Exception:
        return 0.0
    if np.isnan(value) or np.isinf(value):
        return 0.0
    return value


def summarize_results(results: dict) -> PeriodMetrics:
    trades = results.get("trades_df")
    if trades is None:
        trades = results.get("trades")
    if isinstance(trades, pd.DataFrame) and not trades.empty and "r_multiple" in trades.columns:
        avg_r = _safe_float(trades["r_multiple"].mean())
    else:
        avg_r = 0.0

    return PeriodMetrics(
        sharpe=_safe_float(results.get("sharpe_ratio")),
        win_rate=_safe_float(results.get("win_rate")) * 100.0,
        max_dd=abs(_safe_float(results.get("max_drawdown"))),
        profit_factor=_safe_float(results.get("profit_factor")),
        total_trades=int(results.get("total_trades", 0) or 0),
        avg_r_multiple=avg_r,
        all_exits=int(results.get("all_exits", 0) or 0),
    )


def run_engine(start_date: str, end_date: str, threshold: float) -> dict:
    pit = PointInTimeUniverse()
    universe = pit.get_superset(start_date, end_date)
    logger.info("Universe size for %s to %s: %s", start_date, end_date, len(universe))

    engine = AdvancedVectorBTEngine(
        universe=universe,
        start_date=start_date,
        end_date=end_date,
        initial_capital=INITIAL_CAPITAL,
        use_fixed_dollar_risk=True,
        risk_dollars=RISK_DOLLARS,
        min_rvol=BASE_MIN_RVOL,
        min_consolidation_days=BASE_MIN_CONSOLIDATION_DAYS,
        max_consolidation_range=threshold,
        offline_mode=True,
    )
    return engine.run_backtest()


def run_period(label: str, start_date: str, end_date: str, threshold: float) -> dict:
    logger.info("Running %s with max_consolidation_range=%.1f", label, threshold)
    results = run_engine(start_date, end_date, threshold)
    metrics = summarize_results(results)
    return {
        "label": label,
        "start": start_date,
        "end": end_date,
        "threshold": threshold,
        **asdict(metrics),
    }


def run_configs_for_period(label: str, start_date: str, end_date: str) -> list[dict]:
    rows = []
    baseline_trades = None
    for name, threshold in CONFIGS.items():
        try:
            row = {"config": name, **run_period(label, start_date, end_date, threshold)}
            if baseline_trades is None:
                baseline_trades = row["total_trades"]
            row["filtered_pct_vs_baseline"] = (
                round((1 - (row["total_trades"] / baseline_trades)) * 100, 2)
                if baseline_trades
                else 0.0
            )
            rows.append(row)
        except Exception as exc:
            rows.append({"config": name, "label": label, "threshold": threshold, "error": str(exc)})
    return rows


def generate_wf_windows(start: str, end: str) -> list[dict]:
    windows = []
    cursor = pd.Timestamp(start)
    final_end = pd.Timestamp(end)
    while True:
        is_start = cursor
        is_end = is_start + pd.DateOffset(months=WF_IS_MONTHS) - pd.Timedelta(days=1)
        oos_start = is_end + pd.Timedelta(days=1)
        oos_end = oos_start + pd.DateOffset(months=WF_OOS_MONTHS) - pd.Timedelta(days=1)
        if oos_end > final_end:
            break
        windows.append(
            {
                "is_start": is_start.strftime("%Y-%m-%d"),
                "is_end": is_end.strftime("%Y-%m-%d"),
                "oos_start": oos_start.strftime("%Y-%m-%d"),
                "oos_end": oos_end.strftime("%Y-%m-%d"),
            }
        )
        cursor = cursor + pd.DateOffset(months=WF_STEP_MONTHS)
    return windows


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["is", "oos", "holdout", "wf", "all"], default="is")
    args = parser.parse_args()

    payload = {
        "experiment": "setup_quality_consolidation_range",
        "date": datetime.now().strftime("%Y-%m-%d"),
        "hypothesis": "Bases más tight producen breakouts más fiables",
        "variables_modified": ["max_consolidation_range"],
        "variables_fixed": [
            "min_consolidation_days",
            "min_rvol",
            "min_adr",
            "tp1_r",
            "tp2_r",
            "stop_atr",
        ],
        "dataset": {
            "is_start": IS_START,
            "is_end": IS_END,
            "oos_start": OOS_START,
            "oos_end": OOS_END,
            "holdout_start": HOLDOUT_START,
            "holdout_end": HOLDOUT_END,
            "source": "data/ticker_cache.db (PIT universe)",
        },
        "baseline": "combo_pure_momentum",
        "configs_tested": list(CONFIGS.keys()),
        "metrics": {},
        "winner_threshold": None,
        "decision": "PENDING",
        "notes": "",
        "results": [],
    }

    if args.mode in {"is", "all"}:
        period_results = run_configs_for_period("IS", IS_START, IS_END)
        payload["metrics"]["is"] = period_results
        payload["results"].extend(period_results)

    if args.mode in {"oos", "all"}:
        period_results = run_configs_for_period("OOS", OOS_START, OOS_END)
        payload["metrics"]["oos"] = period_results
        payload["results"].extend(period_results)

    if args.mode in {"holdout", "all"}:
        period_results = run_configs_for_period("HOLDOUT", HOLDOUT_START, HOLDOUT_END)
        payload["metrics"]["holdout"] = period_results
        payload["results"].extend(period_results)

    if args.mode == "wf":
        windows = generate_wf_windows(IS_START, OOS_END)
        wf_rows = []
        for window in windows:
            logger.info(
                "WF window IS %s to %s | OOS %s to %s",
                window["is_start"],
                window["is_end"],
                window["oos_start"],
                window["oos_end"],
            )
            is_rows = run_configs_for_period("WF_IS", window["is_start"], window["is_end"])
            oos_rows = run_configs_for_period("WF_OOS", window["oos_start"], window["oos_end"])
            wf_rows.append({"window": window, "is": is_rows, "oos": oos_rows})
        payload["metrics"]["wf"] = wf_rows
        payload["notes"] = "Walk-forward uses 4m IS + 2m OOS windows stepped every 2m."

    output_dir = PROJECT_ROOT / "outputs" / "experiments"
    output_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = output_dir / f"setup_quality_sandbox_{ts}.json"
    with open(output_path, "w") as f:
        json.dump(payload, f, indent=2, default=str)

    print(json.dumps(payload, indent=2, default=str))
    logger.info("Report saved to %s", output_path)


if __name__ == "__main__":
    main()
