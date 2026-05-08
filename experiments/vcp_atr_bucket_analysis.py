import argparse
import json
import logging
import sys
from dataclasses import asdict, dataclass
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

INITIAL_CAPITAL = 100_000
RISK_DOLLARS = 1_000.0

IS_START = "2022-01-01"
IS_END = "2024-06-30"
OOS_START = "2024-07-01"
OOS_END = "2025-06-30"

ATR_SHORT = 5
ATR_LONG = 20

BUCKETS = [
    ("<0.65", None, 0.65),
    ("0.65-0.75", 0.65, 0.75),
    ("0.75-0.85", 0.75, 0.85),
    ("0.85-1.0", 0.85, 1.0),
    (">1.0", 1.0, None),
]


@dataclass
class BucketMetrics:
    trades: int
    win_rate: float
    avg_r_multiple: float
    avg_return_pct: float
    median_atr_ratio: float


def _safe_float(value: object) -> float:
    try:
        value = float(value)
    except Exception:
        return 0.0
    if np.isnan(value) or np.isinf(value):
        return 0.0
    return value


def build_atr_ratio_matrix(engine: AdvancedVectorBTEngine) -> pd.DataFrame:
    close = getattr(engine, "close", None)
    high = getattr(engine, "high", None)
    low = getattr(engine, "low", None)
    if close is None or high is None or low is None:
        raise AttributeError("engine is missing close/high/low data; call load_data() first")

    prev_close = close.shift(1)
    if isinstance(close, pd.DataFrame):
        tr = pd.DataFrame(
            {
                col: pd.concat(
                    [
                        high[col] - low[col],
                        (high[col] - prev_close[col]).abs(),
                        (low[col] - prev_close[col]).abs(),
                    ],
                    axis=1,
                ).max(axis=1)
                for col in close.columns
            },
            index=close.index,
        )
    else:
        tr = pd.concat(
            [
                high - low,
                (high - prev_close).abs(),
                (low - prev_close).abs(),
            ],
            axis=1,
        ).max(axis=1)
    atr_s = tr.rolling(ATR_SHORT).mean()
    atr_l = tr.rolling(ATR_LONG).mean().replace(0, np.nan)
    return (atr_s / atr_l).astype(np.float32)


def run_engine(
    start_date: str, end_date: str
) -> tuple[dict, AdvancedVectorBTEngine, pd.DataFrame, pd.DataFrame]:
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
        offline_mode=True,
    )
    engine.load_data()
    atr_ratio_matrix = build_atr_ratio_matrix(engine)
    results = engine.run_backtest()
    trades = results.get("trades_df")
    if trades is None:
        trades = results.get("trades")
    if not isinstance(trades, pd.DataFrame):
        trades = pd.DataFrame()
    return results, engine, trades, atr_ratio_matrix


def summarize_bucket(df: pd.DataFrame) -> BucketMetrics:
    if df.empty:
        return BucketMetrics(0, 0.0, 0.0, 0.0, 0.0)
    wr = (df["pnl"] > 0).mean() * 100.0 if "pnl" in df.columns else 0.0
    avg_r = _safe_float(df["r_multiple"].mean()) if "r_multiple" in df.columns else 0.0
    avg_ret = _safe_float(df["return_pct"].mean()) if "return_pct" in df.columns else 0.0
    median_ratio = _safe_float(df["atr_ratio"].median()) if "atr_ratio" in df.columns else 0.0
    return BucketMetrics(
        trades=int(len(df)),
        win_rate=wr,
        avg_r_multiple=avg_r,
        avg_return_pct=avg_ret,
        median_atr_ratio=median_ratio,
    )


def collapse_to_entries(trades_df: pd.DataFrame) -> pd.DataFrame:
    if trades_df.empty or not {"entry_date", "symbol"}.issubset(trades_df.columns):
        return pd.DataFrame()

    grouped = []
    for (entry_date, symbol), group in trades_df.groupby(["entry_date", "symbol"], sort=False):
        pnl = group["pnl"].sum() if "pnl" in group.columns else 0.0
        entry_price = group["entry_price"].iloc[0] if "entry_price" in group.columns else np.nan
        atr_ratio = group["atr_ratio"].iloc[0] if "atr_ratio" in group.columns else np.nan
        return_pct = group["return_pct"].sum() if "return_pct" in group.columns else np.nan
        grouped.append(
            {
                "entry_date": entry_date,
                "symbol": symbol,
                "pnl": pnl,
                "entry_price": entry_price,
                "atr_ratio": atr_ratio,
                "return_pct": return_pct,
                "r_multiple": (group["pnl"].sum() / group["initial_risk"].iloc[0])
                if "initial_risk" in group.columns
                and group["initial_risk"].iloc[0] not in (0, np.nan)
                else np.nan,
            }
        )

    return pd.DataFrame(grouped)


def analyze_period(label: str, start_date: str, end_date: str) -> dict:
    results, engine, trades, atr_ratio_matrix = run_engine(start_date, end_date)

    entry_df = collapse_to_entries(trades)
    if not entry_df.empty:
        atr_vals = []
        for _, row in entry_df.iterrows():
            entry_date = row["entry_date"]
            symbol = row["symbol"]
            if entry_date in atr_ratio_matrix.index and symbol in atr_ratio_matrix.columns:
                atr_vals.append(float(atr_ratio_matrix.loc[entry_date, symbol]))
            else:
                atr_vals.append(np.nan)
        entry_df = entry_df.copy()
        entry_df["atr_ratio"] = atr_vals
    else:
        entry_df = pd.DataFrame(
            columns=[
                "entry_date",
                "symbol",
                "pnl",
                "entry_price",
                "atr_ratio",
                "return_pct",
                "r_multiple",
            ]
        )

    bucket_rows = []
    for name, lower, upper in BUCKETS:
        subset = entry_df.copy()
        if lower is not None:
            subset = subset[subset["atr_ratio"] >= lower]
        if upper is not None:
            subset = subset[subset["atr_ratio"] < upper]
        bucket_rows.append({"bucket": name, **asdict(summarize_bucket(subset))})

    non_null = entry_df[entry_df["atr_ratio"].notna()]
    summary = {
        "label": label,
        "start": start_date,
        "end": end_date,
        "total_trades": int(len(entry_df)),
        "atr_ratio_median": _safe_float(non_null["atr_ratio"].median())
        if not non_null.empty
        else 0.0,
        "atr_ratio_p25": _safe_float(non_null["atr_ratio"].quantile(0.25))
        if not non_null.empty
        else 0.0,
        "pct_trades_below_085": float((non_null["atr_ratio"] < 0.85).mean())
        if not non_null.empty
        else 0.0,
        "bucket_rows": bucket_rows,
        "baseline_metrics": {
            "sharpe": _safe_float(results.get("sharpe_ratio")),
            "win_rate": _safe_float(results.get("win_rate")) * 100.0,
            "max_dd": abs(_safe_float(results.get("max_drawdown"))),
            "profit_factor": _safe_float(results.get("profit_factor")),
            "total_trades": int(results.get("total_trades", 0) or 0),
        },
    }
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["is", "oos", "all"], default="is")
    args = parser.parse_args()

    payload = {
        "experiment": "vcp_atr_bucket_analysis",
        "date": datetime.now().strftime("%Y-%m-%d"),
        "hypothesis": "La distribucion de WR cambia por bucket de ATR5/ATR20 en el breakout",
        "atr_short": ATR_SHORT,
        "atr_long": ATR_LONG,
        "buckets": [b[0] for b in BUCKETS],
        "metrics": {},
    }

    if args.mode in {"is", "all"}:
        payload["metrics"]["is"] = analyze_period("IS", IS_START, IS_END)
    if args.mode in {"oos", "all"}:
        payload["metrics"]["oos"] = analyze_period("OOS", OOS_START, OOS_END)

    output_dir = PROJECT_ROOT / "outputs" / "experiments"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = (
        output_dir / f"vcp_atr_bucket_analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    )
    with open(output_path, "w") as f:
        json.dump(payload, f, indent=2, default=str)

    print(json.dumps(payload, indent=2, default=str))
    logger.info("Report saved to %s", output_path)


if __name__ == "__main__":
    main()
