#!/usr/bin/env python3
"""
sync_universe.py - Canonical universe sync desde Finviz.

Single entry-point para refrescar el universo maestro:
  - Lee config de production_config.json -> universe_source.finviz
  - Llama a fetch_finviz_universe()
  - Persiste data/stable_universe.csv + .meta.json
  - Guarda snapshot fechado en outputs/paper_trading/universe_snapshots/

Uso:
    python3 scripts/sync_universe.py                       # hoy
    python3 scripts/sync_universe.py --date 2026-04-20    # fecha específica
    python3 scripts/sync_universe.py --force              # sobreescribir existente
    python3 scripts/sync_universe.py --dry-run            # sin persistir nada
    python3 scripts/sync_universe.py --out /tmp/my_univ.csv
    python3 scripts/sync_universe.py --filters "cap_midover,sh_avgvol_o500"
"""

import argparse
import csv
import hashlib
import json
import logging
import sys
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.data.finviz_universe_provider import fetch_finviz_universe, load_config  # noqa: E402
from src.paper.universe_snapshot_service import save_universe_snapshot  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


DATA_DIR = PROJECT_ROOT / "data"
STABLE_CSV = DATA_DIR / "stable_universe.csv"
STABLE_META = DATA_DIR / "stable_universe.meta.json"


def _compute_hash(tickers: list[str]) -> str:
    sorted_tickers = ",".join(sorted(tickers))
    return hashlib.sha256(sorted_tickers.encode()).hexdigest()


def _load_existing_meta() -> dict | None:
    if STABLE_META.exists():
        return json.loads(STABLE_META.read_text())
    return None


def _persist_stable(tickers: list[str], meta: dict) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    with open(STABLE_CSV, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["ticker"])
        for t in sorted(tickers):
            writer.writerow([t])

    tickers_hash = _compute_hash(tickers)
    payload = {
        **meta,
        "tickers_count": len(tickers),
        "tickers_hash": tickers_hash,
        "persisted_at": datetime.now().isoformat(),
    }
    with open(STABLE_META, "w") as f:
        json.dump(payload, f, indent=2, default=str)

    logger.info(f"✅ stable_universe.csv: {len(tickers)} tickers -> {STABLE_CSV}")
    logger.info(f"   meta: {STABLE_META}")


def _save_snapshot(tickers: list[str], meta: dict, scan_date: str) -> None:
    snap_base = PROJECT_ROOT / "outputs" / "paper_trading" / "universe_snapshots"
    snap_base.mkdir(parents=True, exist_ok=True)

    snap_meta = {
        "provider": meta.get("provider", "finviz_scrape"),
        "fetched_at": meta.get("fetched_at"),
        "pages_ok": meta.get("pages_ok", 0),
        "raw_rows": meta.get("raw_rows", 0),
        "warnings": meta.get("warnings", []),
    }
    save_universe_snapshot(scan_date, tickers, snap_meta, snap_base)


def run_sync(
    date: str | None = None,
    force: bool = False,
    dry_run: bool = False,
    out_path: Path | None = None,
    override_filters: str | None = None,
) -> dict:
    today = date or datetime.now().strftime("%Y-%m-%d")

    cfg = load_config()
    universe_cfg = cfg.get("universe_source", {})

    if not universe_cfg.get("enabled", True):
        logger.warning("universe_source.enabled=false — skipping fetch")
        return {"ok": False, "error": "provider_disabled", "tickers": [], "count": 0}

    finviz_cfg = dict(universe_cfg.get("finviz", {}))
    if override_filters:
        finviz_cfg["filters"] = override_filters
        logger.info(f"Override filters: {override_filters}")

    fetch_cfg = {**universe_cfg, "finviz": finviz_cfg}
    logger.info(f"Solicitando universo Finviz ({today})...")
    result = fetch_finviz_universe(fetch_cfg)

    if not result.ok:
        existing = _load_existing_meta()
        if existing:
            logger.error(
                f"❌ Finviz fetch falló: {result.error}. "
                f"Manteniendo universo vigente: {existing['tickers_count']} tickers"
            )
        else:
            logger.error(
                f"❌ Finviz fetch falló y no existe universo previo: {result.error}"
            )
        return {
            "ok": False,
            "error": result.error,
            "tickers": [],
            "count": 0,
            "provider": result.provider,
        }

    tickers = result.tickers
    tickers_count = len(tickers)
    tickers_hash = _compute_hash(tickers)

    meta = {
        "provider": result.provider,
        "fetched_at": result.fetched_at,
        "pages_ok": result.pages_ok,
        "raw_rows": result.raw_rows,
        "warnings": result.parse_warnings,
        "scan_date": today,
        "filters": finviz_cfg.get("filters", ""),
        "sort": finviz_cfg.get("sort", ""),
        "max_pages": finviz_cfg.get("max_pages", 20),
        "tickers_count": tickers_count,
        "tickers_hash": tickers_hash,
    }

    logger.info(
        f"✅ Fetch OK: {tickers_count} tickers ({result.pages_ok} pages, {result.raw_rows} raw rows)"
    )
    if result.parse_warnings:
        for w in result.parse_warnings:
            logger.warning(f"   warning: {w}")

    if dry_run:
        logger.info("🔍 DRY-RUN: no se persisten archivos")
        return {"ok": True, "tickers": tickers, "count": tickers_count, "meta": meta}

    if out_path:
        out_path = Path(out_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["ticker"])
            for t in sorted(tickers):
                writer.writerow([t])
        logger.info(f"✅ Output CSV: {out_path} ({tickers_count} tickers)")
    else:
        _persist_stable(tickers, meta)

    _save_snapshot(tickers, meta, today)

    return {"ok": True, "tickers": tickers, "count": tickers_count, "meta": meta}


def main():
    parser = argparse.ArgumentParser(description="Sync master universe from Finviz")
    parser.add_argument("--date", type=str, help="Scan date (YYYY-MM-DD)")
    parser.add_argument(
        "--force", action="store_true", help="Force re-fetch even if CSV exists"
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Fetch only, do not persist"
    )
    parser.add_argument("--out", type=str, help="Output CSV path")
    parser.add_argument("--filters", type=str, help="Override Finviz filters")
    args = parser.parse_args()

    if STABLE_CSV.exists() and not args.force and not args.dry_run and not args.out:
        existing_meta = _load_existing_meta()
        if existing_meta:
            logger.info(
                f"stable_universe.csv ya existe "
                f"({existing_meta.get('tickers_count', '?')} tickers, "
                f"fetched {existing_meta.get('fetched_at', '?')})"
            )
            logger.info("Usa --force para re-fresh")

    result = run_sync(
        date=args.date,
        force=args.force,
        dry_run=args.dry_run,
        out_path=args.out,
        override_filters=args.filters,
    )

    if result["ok"]:
        print(f"\n{'=' * 50}")
        print(f"  UNIVERSE SYNC OK  |  {result['count']} tickers")
        print(f"{'=' * 50}")
    else:
        print(f"\n❌ SYNC FAILED: {result.get('error', 'unknown')}")
        sys.exit(1)


if __name__ == "__main__":
    main()
