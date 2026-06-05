import sys
import json
import logging
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(PROJECT_ROOT))

from src.data.ticker_cache import TickerCache
from src.utils.sector_rotation import SECTOR_MAP, SECTOR_ETFS

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)-8s | %(message)s")
logger = logging.getLogger(__name__)


def _build_shadow_setup_row(ticker: str, detail: dict) -> dict:
    ticker_upper = ticker.upper()
    sector = detail.get("sector_etf")
    if not sector and ticker_upper in SECTOR_ETFS:
        sector = ticker_upper
    if not sector:
        sector = SECTOR_MAP.get(ticker_upper, "UNKNOWN")
    sector = str(sector)
    breakout_lvl = detail.get("breakout_level")
    if breakout_lvl is None:
        breakout_lvl = detail.get("entry_price")
    if breakout_lvl is None:
        breakout_lvl = detail.get("price")

    dist_sma20_pct = detail.get("dist_sma20_pct")
    if dist_sma20_pct is None:
        dist_sma20_pct = detail.get("dist_sma20")

    rs_value = detail.get("rs_pct")
    if rs_value is None:
        rs_value = detail.get("rs_score")
    if rs_value is None:
        rs_value = detail.get("score", 0)

    rvol = detail.get("rvol", 1.0)
    waiting_desc = detail.get("waiting_for", "snapshot")
    excluded_by_xlv = sector == "XLV"

    return {
        "ticker": ticker,
        "rs": rs_value,
        "breakout_lvl": breakout_lvl,
        "dist_sma20_pct": dist_sma20_pct,
        "dist_sma20": dist_sma20_pct,
        "rvol": rvol,
        "waiting_desc": waiting_desc,
        "sector_etf": sector,
        "excluded_by_xlv": excluded_by_xlv,
        "allowed_shadow_candidate": not excluded_by_xlv,
        "shadow_status": "shadow_allowed" if not excluded_by_xlv else "blocked_by_sector",
        "source_snapshot": "paper_finviz",
    }


def generate_setups_from_snapshots() -> int:
    paper_dir = PROJECT_ROOT / "outputs" / "paper_finviz"
    out_base = PROJECT_ROOT / "outputs" / "shadow_sandbox" / "finviz_runs"

    snapshot_files = sorted(paper_dir.glob("2026-05-*/snapshot.json"))
    logger.info("Converting %d snapshot files into setups.csv", len(snapshot_files))

    written_days = 0
    for snap_file in snapshot_files:
        try:
            with open(snap_file, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as exc:
            logger.warning("  Failed to read %s: %s", snap_file, exc)
            continue

        watchlist = data.get("watchlist_detail", {}) or {}
        if not watchlist:
            logger.info("  Skipping %s (no watchlist_detail)", snap_file.parent.name)
            continue

        rows = [
            _build_shadow_setup_row(ticker, detail or {}) for ticker, detail in watchlist.items()
        ]
        out_dir = out_base / snap_file.parent.name
        out_dir.mkdir(parents=True, exist_ok=True)

        import pandas as pd

        pd.DataFrame(rows).to_csv(out_dir / "setups.csv", index=False)
        written_days += 1
        logger.info("  Wrote %s with %d setups", out_dir / "setups.csv", len(rows))

    return written_days


def rebuild():
    # 1. Escanear snapshots de mayo de 2026
    paper_dir = PROJECT_ROOT / "outputs" / "paper_finviz"
    logger.info(f"Scanning snapshots in {paper_dir} for May 2026...")

    unique_tickers = set()
    snapshot_files = list(paper_dir.glob("2026-05-*/snapshot.json"))

    logger.info(f"Found {len(snapshot_files)} snapshot files to process.")
    for snap_file in sorted(snapshot_files):
        try:
            with open(snap_file, "r") as f:
                data = json.load(f)
            watchlist = data.get("watchlist_detail", {})
            if watchlist:
                unique_tickers.update(watchlist.keys())
                logger.info(
                    f"  Processed {snap_file.parent.name}: added {len(watchlist)} candidates."
                )
        except Exception as e:
            logger.warning(f"  Failed to process {snap_file}: {e}")

    generate_setups_from_snapshots()

    # Ensure indices and sector ETFs required for market health scores and sector filters are also downloaded
    required_indices_etfs = {
        "SPY",
        "^VIX",
        "XLK",
        "XLF",
        "XLV",
        "XLE",
        "XLY",
        "XLP",
        "XLI",
        "XLB",
        "XLRE",
        "XLU",
        "XLC",
        "IWM",
        "QQQ",
        "DIA",
        "SMH",
        "XBI",
    }
    unique_tickers.update(required_indices_etfs)

    tickers_list = sorted(list(unique_tickers))
    logger.info(
        f"Total unique tickers found across all May 2026 snapshots (including index/ETFs): {len(tickers_list)}"
    )

    if not tickers_list:
        logger.error("No tickers found to download. Exiting.")
        return

    # 2. Descargar y actualizar datos en lote usando TickerCache (grupos de 40)
    cache = TickerCache()
    try:
        # Descargamos desde 2025 para garantizar suficientes barras para el cálculo de SMAs (especialmente SMA200) y acelerar 5x
        success = cache.update_ohlcv_batch(
            tickers_list, start_date="2025-01-01", end_date="2026-06-05"
        )
        logger.info(
            f"Database reconstruction completed: successfully updated {success}/{len(tickers_list)} tickers."
        )
    except Exception as e:
        logger.error(f"Error during batch download: {e}")
    finally:
        cache.close()


if __name__ == "__main__":
    rebuild()
