"""
Universe Snapshot Service - Guardado de snapshots diarios congelados.
"""

import csv
import hashlib
import json
import logging
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class SnapshotResult:
    snapshot_path: Optional[Path]
    csv_path: Optional[Path]
    hash: str
    tickers_count: int
    ok: bool
    error: Optional[str] = None


def _compute_hash(tickers: list[str]) -> str:
    """Calcula SHA256 de lista ordenada de tickers."""
    sorted_tickers = ",".join(sorted(tickers))
    return hashlib.sha256(sorted_tickers.encode()).hexdigest()


def save_universe_snapshot(
    scan_date: str,
    tickers: list[str],
    meta: dict,
    base_dir: Path,
) -> SnapshotResult:
    """
    Guarda snapshot JSON + CSV por fecha.

    Args:
        scan_date: Fecha del snapshot (YYYY-MM-DD)
        tickers: Lista de tickers
        meta: Metadatos (provider, fetched_at, pages_ok, raw_rows, warnings)
        base_dir: Directorio base para snapshots

    Returns:
        SnapshotResult con paths y metadatos
    """
    try:
        date_dir = base_dir / scan_date
        date_dir.mkdir(parents=True, exist_ok=True)

        tickers_hash = _compute_hash(tickers)

        payload = {
            "scan_date": scan_date,
            "tickers_count": len(tickers),
            "tickers_hash": tickers_hash,
            "tickers": sorted(tickers),
            "meta": meta,
            "created_at": datetime.now().isoformat(),
        }

        json_path = date_dir / "universe_snapshot.json"
        with open(json_path, "w") as f:
            json.dump(payload, f, indent=2, default=str)

        csv_path = date_dir / "universe_tickers.csv"
        with open(csv_path, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["ticker"])
            for t in sorted(tickers):
                writer.writerow([t])

        logger.info(f"[OK] Snapshot guardado: {json_path} ({len(tickers)} tickers)")

        return SnapshotResult(
            snapshot_path=json_path,
            csv_path=csv_path,
            hash=tickers_hash,
            tickers_count=len(tickers),
            ok=True,
        )

    except Exception as e:
        logger.error(f"Error guardando snapshot: {e}")
        return SnapshotResult(
            snapshot_path=None,
            csv_path=None,
            hash="",
            tickers_count=0,
            ok=False,
            error=str(e),
        )


def load_latest_snapshot(base_dir: Path) -> Optional[dict]:
    """Carga el snapshot más reciente."""
    try:
        date_dirs = sorted(
            [d for d in base_dir.iterdir() if d.is_dir()],
            key=lambda d: d.name,
            reverse=True,
        )
        for date_dir in date_dirs:
            snapshot_path = date_dir / "universe_snapshot.json"
            if snapshot_path.exists():
                return json.load(open(snapshot_path))
    except Exception as e:
        logger.error(f"Error cargando snapshot: {e}")
    return None


def load_snapshot_for_date(scan_date: str, base_dir: Path) -> Optional[dict]:
    """Carga snapshot para una fecha específica."""
    try:
        snapshot_path = base_dir / scan_date / "universe_snapshot.json"
        if snapshot_path.exists():
            return json.load(open(snapshot_path))
    except Exception as e:
        logger.error(f"Error cargando snapshot {scan_date}: {e}")
    return None


if __name__ == "__main__":
    from src.data.finviz_universe_provider import get_universe

    logging.basicConfig(level=logging.INFO)

    result = get_universe()

    ROOT = Path(__file__).parent.parent.parent
    base = ROOT / "outputs" / "paper_trading" / "universe_snapshots"

    today = datetime.now().strftime("%Y-%m-%d")
    meta = {
        "provider": result.provider,
        "fetched_at": result.fetched_at,
        "pages_ok": result.pages_ok,
        "raw_rows": result.raw_rows,
        "warnings": result.parse_warnings,
    }

    snap = save_universe_snapshot(today, result.tickers, meta, base)
    print(f"Ok: {snap.ok}, Hash: {snap.hash}, Count: {snap.tickers_count}")
