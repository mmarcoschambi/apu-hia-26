import sys
import argparse
import logging
import sqlite3
from pathlib import Path
from datetime import date
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from src.data.finviz_universe_provider import fetch_finviz_universe
from src.signals.signal_engine import evaluate_ticker
from src.integration.combo_loader import load_combo_merged

VALIDATED_OVERRIDES = {
    "min_rs_percentile": 75,
    "min_trend_intensity": 104,
    "require_ma_stack": True,
    "min_adr_pct": 1.2,
    "require_spy_above_sma200": True,
}

FINVIZ_CFG = {
    "finviz": {
        "base_url": "https://finviz.com/screener.ashx",
        "filters": "cap_midover,sh_avgvol_o1000,sh_price_o10",
        "sort": "relativevolume",
        "max_pages": 20,
        "timeout_sec": 15,
        "retries": 3,
        "min_tickers": 80,
    }
}


def load_ohlcv_from_db(db_path, ticker, end_date):
    conn = sqlite3.connect(db_path)
    df = pd.read_sql_query(
        "SELECT date, open, high, low, close, volume FROM ohlcv_cache WHERE ticker = ? AND date <= ? ORDER BY date",
        conn,
        params=(ticker, end_date),
        parse_dates=["date"],
    )
    conn.close()
    if df.empty:
        return None
    df.set_index("date", inplace=True)
    return df


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
    )
    logger = logging.getLogger(__name__)

    parser = argparse.ArgumentParser(description="Show Finviz near-miss signals")
    parser.add_argument("--date", required=True, help="Scan date (YYYY-MM-DD)")
    parser.add_argument(
        "--top",
        type=int,
        default=20,
        help="Number of top near-misses to show (default: 20)",
    )
    parser.add_argument(
        "--by-reason", action="store_true", help="Show rejection reason breakdown"
    )
    args = parser.parse_args()

    scan_date = args.date

    cfg_a, _ = load_combo_merged("combo_pure_momentum")
    cfg_b, _ = load_combo_merged("combo_stage2_breakout")

    for cfg in [cfg_a, cfg_b]:
        for k, v in VALIDATED_OVERRIDES.items():
            cfg.setdefault("tier2_filters", {})[k] = v
            cfg.setdefault("screener", {}).setdefault("params", {})[k] = v
            if k in ["min_adr_pct"]:
                cfg.setdefault("screener", {})[k] = v

    finviz_result = fetch_finviz_universe(FINVIZ_CFG)
    universe = finviz_result.tickers if finviz_result.ok else []
    logger.info(f"Fetched Finviz universe: {len(universe)} tickers")

    db_path = str(PROJECT_ROOT / "data" / "ticker_cache.db")
    if not Path(db_path).exists():
        logger.error(f"DB not found at {db_path}")
        sys.exit(1)

    spy_df = load_ohlcv_from_db(db_path, "SPY", scan_date)
    if spy_df is None or len(spy_df) < 65:
        logger.error("SPY data not available or insufficient")
        sys.exit(1)

    all_decisions = []
    skipped = 0
    scanned = 0

    for ticker in universe:
        ticker_df = load_ohlcv_from_db(db_path, ticker, scan_date)
        if ticker_df is None or len(ticker_df) < 65:
            skipped += 1
            continue
        scanned += 1
        for cfg, mode in [(cfg_a, "A"), (cfg_b, "B")]:
            try:
                decision = evaluate_ticker(
                    ticker=ticker,
                    df=ticker_df,
                    spy_df=spy_df,
                    combo_cfg=cfg,
                    mode=mode,
                    scan_date=scan_date,
                )
                all_decisions.append(
                    {
                        "ticker": ticker,
                        "entry_score": decision.entry_score,
                        "screener_score": decision.screener_score,
                        "reject_reason": decision.reject_reason,
                        "screener_reason": decision.screener_reason,
                        "mode": mode,
                        "passed": decision.passed,
                    }
                )
            except Exception as e:
                logger.error(f"Error evaluating {ticker} mode {mode}: {e}")

    passed = [d for d in all_decisions if d["passed"]]
    rejected = [d for d in all_decisions if not d["passed"]]
    near_misses = sorted(rejected, key=lambda x: x["screener_score"], reverse=True)[
        : args.top
    ]

    print("=" * 60)
    print(f"  FINVIZ NEAR-MISSES  |  {args.date}")
    print("=" * 60)
    print(f"  Universe: {len(universe)} tickers")
    print(f"  Scanned:  {scanned} ({skipped} skipped: no data)")
    print(f"  Total evaluations: {len(all_decisions)} (A+B modes)")
    print()

    print(f"  PASSED SIGNALS ({len(passed)}):")
    for d in sorted(passed, key=lambda x: x["entry_score"], reverse=True):
        print(f"    ★ {d['ticker']:6}  score={d['entry_score']:.3f}  mode={d['mode']}")
    print()

    print(f"  TOP NEAR-MISSES (rejected, highest screener_score):")
    print(f"    Ticker   ScrScore  Mode  Reject Reason")
    print(f"    -------  --------  ----  -----------------------------------")
    for d in near_misses:
        reason = d["reject_reason"] if d["reject_reason"] else d["screener_reason"]
        if not reason:
            reason = "N/A"
        reason = str(reason)[:60]
        print(
            f"    {d['ticker']:6}  {d['screener_score']:>8.1f}  {d['mode']:3}  {reason}"
        )
    print()

    if args.by_reason:
        print("  REJECTION REASON BREAKDOWN:")
        reason_counts = {}
        for d in rejected:
            reason = d["reject_reason"] if d["reject_reason"] else d["screener_reason"]
            if not reason:
                reason = "unknown"
            reason = str(reason)[:50]
            reason_counts[reason] = reason_counts.get(reason, 0) + 1
        for reason, count in sorted(
            reason_counts.items(), key=lambda x: x[1], reverse=True
        ):
            print(f"    {reason:50} {count:5} tickers")
        print()
