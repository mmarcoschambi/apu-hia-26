import argparse
import json
import logging
import sqlite3
import sys
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.backtest.vectorbt_engine_advanced import AdvancedVectorBTEngine
from src.data.pit_universe import PointInTimeUniverse

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

DB_PATH = PROJECT_ROOT / "data" / "ticker_cache.db"
OUTPUT_DIR = PROJECT_ROOT / "outputs" / "experiments"

START_DATE = "2025-01-01"
END_DATE = "2026-04-30"
IS_START = "2025-01-01"
IS_END = "2025-09-30"
OOS_START = "2025-10-01"
OOS_END = "2026-04-30"

INITIAL_CAPITAL = 100_000
FIXED_RISK = 1_000.0

THRESHOLDS_A = [0.40, 0.45, 0.50, 0.55, 0.60]
THRESHOLDS_B = [0.40, 0.50, 0.60]


@dataclass
class Metrics:
    sharpe: float
    max_drawdown: float
    total_trades: int
    win_rate: float
    profit_factor: float


def _safe_float(value):
    try:
        value = float(value)
    except Exception:
        return 0.0
    if np.isnan(value) or np.isinf(value):
        return 0.0
    return value


def summarize_results(results: dict) -> Metrics:
    return Metrics(
        sharpe=_safe_float(results.get("sharpe_ratio")),
        max_drawdown=_safe_float(results.get("max_drawdown")),
        total_trades=int(results.get("total_trades", 0) or 0),
        win_rate=_safe_float(results.get("win_rate")),
        profit_factor=_safe_float(results.get("profit_factor")),
    )


def run_engine(
    start_date: str,
    end_date: str,
    use_sector_filter: bool,
    breadth_mode=None,
    breadth_threshold=0.0,
) -> dict:
    pit = PointInTimeUniverse()
    universe = pit.get_superset(start_date, end_date)
    logger.info("Universe size for %s to %s: %s", start_date, end_date, len(universe))

    engine = AdvancedVectorBTEngine(
        universe=universe,
        start_date=start_date,
        end_date=end_date,
        initial_capital=INITIAL_CAPITAL,
        use_fixed_dollar_risk=True,
        risk_dollars=FIXED_RISK,
        max_positions=15,
        use_sector_etf_filter=use_sector_filter,
        fee_rate=0.001,
        slippage_rate=0.001,
        rs_threshold=58,
        use_vcp_filter=False,
        rank_by="rs_composite",
        benchmark_ticker="SPY",
        use_breadth_filter=breadth_mode is not None,
        breadth_filter_mode=breadth_mode or "sma20",
        breadth_filter_threshold=breadth_threshold,
    )
    results = engine.run_backtest()
    breadth_stats = getattr(engine, "breadth_stats", None)
    if isinstance(breadth_stats, dict):
        results["breadth_stats"] = breadth_stats
    return results


def run_config(
    name: str,
    use_sector_filter: bool,
    breadth_mode=None,
    breadth_threshold=0.0,
    is_start: str = IS_START,
    is_end: str = IS_END,
    oos_start: str = OOS_START,
    oos_end: str = OOS_END,
) -> dict:
    results_is = run_engine(is_start, is_end, use_sector_filter, breadth_mode, breadth_threshold)
    results_oos = run_engine(oos_start, oos_end, use_sector_filter, breadth_mode, breadth_threshold)
    return {
        "name": name,
        "use_sector_filter": use_sector_filter,
        "breadth_mode": breadth_mode,
        "breadth_threshold": breadth_threshold,
        "is": asdict(summarize_results(results_is)),
        "oos": asdict(summarize_results(results_oos)),
        "is_breadth_stats": results_is.get("breadth_stats"),
        "oos_breadth_stats": results_oos.get("breadth_stats"),
    }


def make_report_mode_a(
    is_start: str = IS_START,
    is_end: str = IS_END,
    oos_start: str = OOS_START,
    oos_end: str = OOS_END,
) -> dict:
    rows = []
    rows.append(run_config("S0_Baseline", False, None, 0.0, is_start, is_end, oos_start, oos_end))
    rows.append(run_config("S1_SectorOnly", True, None, 0.0, is_start, is_end, oos_start, oos_end))
    rows.append(
        run_config("B1_BreadthSolo_040", False, "sma20", 0.40, is_start, is_end, oos_start, oos_end)
    )
    rows.append(
        run_config("B1_BreadthSolo_045", False, "sma20", 0.45, is_start, is_end, oos_start, oos_end)
    )
    rows.append(
        run_config("B1_BreadthSolo_050", False, "sma20", 0.50, is_start, is_end, oos_start, oos_end)
    )
    rows.append(
        run_config("B1_BreadthSolo_055", False, "sma20", 0.55, is_start, is_end, oos_start, oos_end)
    )
    rows.append(
        run_config("B1_BreadthSolo_060", False, "sma20", 0.60, is_start, is_end, oos_start, oos_end)
    )
    rows.append(
        run_config(
            "B2_BreadthPlusSector_040", True, "sma20", 0.40, is_start, is_end, oos_start, oos_end
        )
    )
    rows.append(
        run_config(
            "B2_BreadthPlusSector_045", True, "sma20", 0.45, is_start, is_end, oos_start, oos_end
        )
    )
    rows.append(
        run_config(
            "B2_BreadthPlusSector_050", True, "sma20", 0.50, is_start, is_end, oos_start, oos_end
        )
    )
    rows.append(
        run_config(
            "B2_BreadthPlusSector_055", True, "sma20", 0.55, is_start, is_end, oos_start, oos_end
        )
    )
    rows.append(
        run_config(
            "B2_BreadthPlusSector_060", True, "sma20", 0.60, is_start, is_end, oos_start, oos_end
        )
    )
    return {
        "experiment": "breadth_market_wide_gate",
        "hypothesis": "Agregar breadth binario mejora Sharpe OOS sin empeorar el riesgo",
        "variables_modified": [
            "use_breadth_filter",
            "breadth_filter_mode",
            "breadth_filter_threshold",
        ],
        "variables_fixed": [
            "use_sector_etf_filter",
            "max_positions",
            "risk_dollars",
            "rs_threshold",
            "use_vcp_filter",
            "rank_by",
            "fee_rate",
            "slippage_rate",
        ],
        "dataset": {
            "source": "data/ticker_cache.db (ohlcv_cache + PIT universe)",
            "universe": "pit.get_superset(START_DATE, END_DATE)",
            "start": START_DATE,
            "end": END_DATE,
            "is": [IS_START, IS_END],
            "oos": [OOS_START, OOS_END],
            "lookbacks": {
                "sma20": 20,
                "nh_nl": 252,
            },
        },
        "baseline": "S0_Baseline (use_sector_etf_filter=False, use_breadth_filter=False)",
        "comparison_anchor": "S1_SectorOnly for B2 (use_sector_etf_filter=True, use_breadth_filter=False)",
        "metrics_expected": ["sharpe", "max_drawdown", "total_trades", "win_rate", "profit_factor"],
        "go_no_go": "GO if OOS Sharpe >= S0, max drawdown no worse than S0, trades do not collapse, and the edge appears across at least 2 thresholds.",
        "results": rows,
        "notes": "Stage 1 tests Hypothesis A only (% universe above SMA20). Stage B is reserved if A fails.",
        "timestamp": datetime.now().isoformat(),
    }


def build_config_registry(mode: str) -> dict:
    if mode == "b":
        return {
            "S0": ("S0_Baseline", False, None, 0.0),
            "B_040": ("B_HighLow_040", False, "nh_nl", 0.40),
            "B_050": ("B_HighLow_050", False, "nh_nl", 0.50),
            "B_060": ("B_HighLow_060", False, "nh_nl", 0.60),
        }

    return {
        "S0": ("S0_Baseline", False, None, 0.0),
        "S1": ("S1_SectorOnly", True, None, 0.0),
        "B1_040": ("B1_BreadthSolo_040", False, "sma20", 0.40),
        "B1_045": ("B1_BreadthSolo_045", False, "sma20", 0.45),
        "B1_050": ("B1_BreadthSolo_050", False, "sma20", 0.50),
        "B1_055": ("B1_BreadthSolo_055", False, "sma20", 0.55),
        "B1_060": ("B1_BreadthSolo_060", False, "sma20", 0.60),
        "B2_040": ("B2_BreadthPlusSector_040", True, "sma20", 0.40),
        "B2_045": ("B2_BreadthPlusSector_045", True, "sma20", 0.45),
        "B2_050": ("B2_BreadthPlusSector_050", True, "sma20", 0.50),
        "B2_055": ("B2_BreadthPlusSector_055", True, "sma20", 0.55),
        "B2_060": ("B2_BreadthPlusSector_060", True, "sma20", 0.60),
    }


def run_selected_configs(
    mode: str,
    selected_configs: list[str] | None,
    is_start: str = IS_START,
    is_end: str = IS_END,
    oos_start: str = OOS_START,
    oos_end: str = OOS_END,
) -> list[dict]:
    registry = build_config_registry(mode)
    keys = selected_configs or list(registry.keys())
    rows = []
    for key in keys:
        if key not in registry:
            rows.append({"config": key, "error": "Unknown config"})
            continue
        name, use_sector_filter, breadth_mode, breadth_threshold = registry[key]
        try:
            rows.append(
                run_config(
                    name,
                    use_sector_filter,
                    breadth_mode,
                    breadth_threshold,
                    is_start,
                    is_end,
                    oos_start,
                    oos_end,
                )
            )
        except Exception as exc:
            rows.append({"config": key, "name": name, "error": str(exc)})
    return rows


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["a", "b"], default="a")
    parser.add_argument("--configs", nargs="+", default=None)
    parser.add_argument("--is-start", default=IS_START)
    parser.add_argument("--is-end", default=IS_END)
    parser.add_argument("--oos-start", default=OOS_START)
    parser.add_argument("--oos-end", default=OOS_END)
    args = parser.parse_args()

    if args.mode == "b":
        thresholds = THRESHOLDS_B
        payload = {
            "experiment": "breadth_market_wide_gate",
            "hypothesis": "New highs / (new highs + new lows) gate improves OOS Sharpe",
            "variables_modified": [
                "use_breadth_filter",
                "breadth_filter_mode",
                "breadth_filter_threshold",
            ],
            "variables_fixed": [
                "use_sector_etf_filter",
                "max_positions",
                "risk_dollars",
                "rs_threshold",
            ],
            "dataset": {
                "source": "data/ticker_cache.db (ohlcv_cache + PIT universe)",
                "lookback": 252,
                "thresholds": thresholds,
            },
            "baseline": "S0_Baseline",
            "metrics_expected": [
                "sharpe",
                "max_drawdown",
                "total_trades",
                "win_rate",
                "profit_factor",
            ],
            "go_no_go": "GO if OOS Sharpe >= S0, max drawdown no worse than S0, and the edge is robust across thresholds.",
            "results": [],
            "timestamp": datetime.now().isoformat(),
        }
        payload["results"] = run_selected_configs(
            "b", args.configs, args.is_start, args.is_end, args.oos_start, args.oos_end
        )
    else:
        payload = make_report_mode_a(args.is_start, args.is_end, args.oos_start, args.oos_end)
        if args.configs:
            payload["results"] = run_selected_configs(
                "a", args.configs, args.is_start, args.is_end, args.oos_start, args.oos_end
            )

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = OUTPUT_DIR / f"breadth_sandbox_{ts}.json"
    with open(output_path, "w") as f:
        json.dump(payload, f, indent=2, default=str)

    print(json.dumps(payload, indent=2, default=str))
    logger.info("Report saved to %s", output_path)


if __name__ == "__main__":
    main()
