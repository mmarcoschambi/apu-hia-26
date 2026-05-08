import argparse
import json
import logging
import sys
from dataclasses import asdict, dataclass
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

IS_START = "2022-01-01"
IS_END = "2024-06-30"
OOS_START = "2024-07-01"
OOS_END = "2025-06-30"

CONFIGS = {
    "S0_baseline": {"ratio_min": None, "ratio_max": None},
    "C1_sweet_065_085": {"ratio_min": 0.65, "ratio_max": 0.85},
    "C2_wider_060_090": {"ratio_min": 0.60, "ratio_max": 0.90},
    "C3_upper_085": {"ratio_min": None, "ratio_max": 0.85},
    "C4_upper_075": {"ratio_min": None, "ratio_max": 0.75},
    "C5_no_expansion_100": {"ratio_min": None, "ratio_max": 1.0},
}


@dataclass
class PeriodMetrics:
    sharpe: float
    win_rate: float
    max_dd: float
    profit_factor: float
    total_trades: int
    avg_r_multiple: float


def _safe_float(value: object) -> float:
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
    )


def run_engine(start_date: str, end_date: str, zone: Optional[dict]) -> dict:
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
        min_rvol=1.5,
        signal_type="breakout",
        contraction_zone=zone,
        offline_mode=True,
    )
    return engine.run_backtest()


def run_period(label: str, start_date: str, end_date: str, zone: Optional[dict]) -> dict:
    results = run_engine(start_date, end_date, zone)
    metrics = summarize_results(results)
    return {"label": label, "start": start_date, "end": end_date, **asdict(metrics)}


def run_configs(period_label: str, start_date: str, end_date: str) -> list[dict]:
    rows = []
    baseline_trades = None
    for name, zone in CONFIGS.items():
        try:
            row = {
                "config": name,
                "zone": zone,
                **run_period(period_label, start_date, end_date, zone),
            }
            if baseline_trades is None:
                baseline_trades = row["total_trades"]
            row["filtered_pct_vs_baseline"] = (
                round((1 - (row["total_trades"] / baseline_trades)) * 100, 2)
                if baseline_trades
                else 0.0
            )
            rows.append(row)
        except Exception as exc:
            rows.append({"config": name, "zone": zone, "label": period_label, "error": str(exc)})
    return rows


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["is", "oos", "all"], default="is")
    args = parser.parse_args()

    payload = {
        "experiment": "vcp_atr_contraction_zone",
        "date": datetime.now().strftime("%Y-%m-%d"),
        "hypothesis": "ATR5/ATR20 en zona 0.65-0.85 en dia del breakout predice mayor win rate",
        "variables_modified": ["contraction_zone.ratio_min", "contraction_zone.ratio_max"],
        "variables_fixed": [
            "signal_type",
            "exits",
            "sizing",
            "min_rvol",
            "consolidation",
            "breadth=OFF",
        ],
        "dataset": {
            "is": [IS_START, IS_END],
            "oos": [OOS_START, OOS_END],
            "source": "data/ticker_cache.db (PIT universe)",
        },
        "configs_tested": list(CONFIGS.keys()),
        "metrics": {},
        "decision": "PENDING",
        "results": [],
    }

    if args.mode in {"is", "all"}:
        is_rows = run_configs("IS", IS_START, IS_END)
        payload["metrics"]["is"] = is_rows
        payload["results"].extend(is_rows)

    if args.mode in {"oos", "all"}:
        oos_rows = run_configs("OOS", OOS_START, OOS_END)
        payload["metrics"]["oos"] = oos_rows
        payload["results"].extend(oos_rows)

    output_dir = PROJECT_ROOT / "outputs" / "experiments"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = (
        output_dir / f"vcp_atr_contraction_sandbox_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    )
    with open(output_path, "w") as f:
        json.dump(payload, f, indent=2, default=str)

    print(json.dumps(payload, indent=2, default=str))
    logger.info("Report saved to %s", output_path)


if __name__ == "__main__":
    main()
