#!/usr/bin/env python3
"""
rebuild_screener_cache.py
=========================
Regenera los caches de screeners con los fixes aplicados:
  - Qullamaggie: escala RS corregida (RS fallback calibrado, min_rs_percentile=85)
  - Todos: usa DB local (offline=True), no conecta a red

Uso:
  python3 rebuild_screener_cache.py                        # rebuild qullamaggie
  python3 rebuild_screener_cache.py --screener minervini_trend
  python3 rebuild_screener_cache.py --all                  # todos los screeners
  python3 rebuild_screener_cache.py --tickers 50           # universo reducido (test rapido)
"""

import sys, time, json, argparse, logging
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(message)s")
logger = logging.getLogger(__name__)

sys.path.insert(0, str(Path(__file__).resolve().parent))
from src.data.screener_cache import ScreenerCacheManager

CACHE_DIR = Path("data/screener_cache")
META_REF = CACHE_DIR / "minervini_trend.meta.json"


def get_universe_and_dates(screener_name=None, tickers_limit=None):
    if screener_name:
        screener_meta = CACHE_DIR / f"{screener_name}.meta.json"
        if screener_meta.exists():
            meta = json.loads(screener_meta.read_text())
            if meta.get("tickers"):
                tickers = meta["tickers"]
                start_date = meta.get("start_date", "2022-01-01")
                end_date = meta.get("end_date", "2024-12-31")
                if tickers_limit:
                    tickers = tickers[:tickers_limit]
                return tickers, start_date, end_date
    if META_REF.exists():
        meta = json.loads(META_REF.read_text())
        tickers = meta["tickers"]
        start_date, end_date = meta["start_date"], meta["end_date"]
    else:
        tickers = [
            "AAPL",
            "MSFT",
            "NVDA",
            "TSLA",
            "META",
            "AMZN",
            "GOOGL",
            "AVGO",
            "NFLX",
            "KLAC",
        ]
        start_date, end_date = "2022-01-01", "2024-12-31"
    if tickers_limit:
        tickers = tickers[:tickers_limit]
    return tickers, start_date, end_date


def rebuild_one(screener_name, tickers, start_date, end_date):
    mgr = ScreenerCacheManager()
    logger.info(
        f"Rebuilding {screener_name}: {len(tickers)} tickers, {start_date} -> {end_date}"
    )
    t0 = time.time()
    result = mgr.build_for_combo(
        screener_name=screener_name,
        tickers=tickers,
        start_date=start_date,
        end_date=end_date,
    )
    elapsed = time.time() - t0
    if result.empty:
        logger.error(f"  ERROR: resultado vacio ({elapsed:.0f}s)")
        return
    passed = result["passed"].sum()
    total = len(result)
    logger.info(
        f"  Done {elapsed:.0f}s | rows={total} | passed={passed} ({passed / total * 100:.1f}%) | tickers={result['ticker'].nunique()}"
    )
    top = (
        result[result["passed"]]
        .groupby("ticker")
        .size()
        .sort_values(ascending=False)
        .head(10)
    )
    logger.info(f"  Top tickers:\n{top.to_string()}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--screener", default="qullamaggie_momentum")
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--tickers", type=int, default=None)
    args = parser.parse_args()

    screener_name_for_meta = args.screener if not args.all else None
    tickers, start_date, end_date = get_universe_and_dates(
        screener_name=screener_name_for_meta, tickers_limit=args.tickers
    )

    screeners = (
        ["minervini_trend", "qullamaggie_momentum", "universal_any", "ema21_pullback"]
        if args.all
        else [args.screener]
    )

    for s in screeners:
        rebuild_one(s, tickers, start_date, end_date)


if __name__ == "__main__":
    main()
