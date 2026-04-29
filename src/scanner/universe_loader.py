"""
Universe Loader - Carga reusable de universo para scanners.

Contrato de fuente:
  1. tickers explícitos (--tickers)
  2. archivo CSV (--universe-file)
  3. stable_universe.csv (--universe-source stable)
  4. DB fallback (--universe-source db)

Uso:
    from src.scanner.universe_loader import load_scan_universe
    tickers = load_scan_universe(source="stable")
    tickers = load_scan_universe(source="file", path=Path("my_universe.csv"))
    tickers = load_scan_universe(source="db", top_n=200)
    tickers = load_scan_universe(tickers=["AAPL", "NVDA"])
"""

import logging
import sqlite3
from pathlib import Path
from typing import Optional

import pandas as pd

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DB_PATH = PROJECT_ROOT / "data" / "ticker_cache.db"
STABLE_CSV = PROJECT_ROOT / "data" / "stable_universe.csv"


def load_scan_universe(
    source: str = "db",
    path: Optional[Path] = None,
    top_n: int = 0,
    tickers: Optional[list[str]] = None,
) -> list[str]:
    """
    Carga universo según prioridad de fuente.

    Args:
        source: "db" | "stable" | "file" | "explicit"
        path: ruta a CSV (para source="file")
        top_n: límite de tickers por dollar volume (para source="db")
        tickers: lista explícita (mayor prioridad)

    Returns:
        Lista ordenada de tickers únicos (sin duplicados)
    """
    if tickers:
        result = sorted(set([t.upper().strip() for t in tickers if t]))
        logger.info(f"Universe (explicit): {len(result)} tickers")
        return result

    if source == "explicit":
        logger.warning("load_scan_universe: source='explicit' requiere tickers list")
        return []

    if source == "file":
        csv_path = path or STABLE_CSV
        if not csv_path:
            logger.error("load_scan_universe: no path specified for source='file'")
            return []
        return _load_from_csv(csv_path)

    if source == "stable":
        if not STABLE_CSV.exists():
            logger.warning(
                f"stable_universe.csv not found at {STABLE_CSV}, falling back to db"
            )
            return _load_from_db(top_n=top_n)
        return _load_from_csv(STABLE_CSV)

    return _load_from_db(top_n=top_n)


def _load_from_csv(csv_path: Path) -> list[str]:
    try:
        df = pd.read_csv(csv_path, usecols=["ticker"], dtype={"ticker": str})
        tickers = df["ticker"].dropna().str.strip().str.upper().unique().tolist()
        tickers.sort()
        logger.info(f"Universe (csv={csv_path.name}): {len(tickers)} tickers")
        return tickers
    except Exception as e:
        logger.error(f"Error loading {csv_path}: {e}")
        return []


def _load_from_db(top_n: int = 0) -> list[str]:
    try:
        conn = sqlite3.connect(DB_PATH)
        q = """
            SELECT ticker, AVG(close * volume) as avg_dv
            FROM ohlcv_cache
            WHERE date >= date('now', '-90 days')
            GROUP BY ticker
            HAVING COUNT(*) >= 30
            ORDER BY avg_dv DESC
        """
        if top_n > 0:
            q += f" LIMIT {top_n}"
        rows = conn.execute(q).fetchall()
        conn.close()
        tickers = [r[0] for r in rows]
        logger.info(
            f"Universe (db): {len(tickers)} tickers"
            + (f" (top_n={top_n})" if top_n else "")
        )
        return tickers
    except Exception as e:
        logger.error(f"Error loading universe from DB: {e}")
        return []


def universe_stats() -> dict:
    """Retorna stats del universo maestro vigente."""
    stats = {"source": "unknown", "count": 0, "exists": False}

    if STABLE_CSV.exists():
        stats["source"] = "stable"
        stats["exists"] = True
        try:
            df = pd.read_csv(STABLE_CSV, usecols=["ticker"])
            stats["count"] = int(df["ticker"].nunique())
        except Exception:
            pass
    else:
        stats["source"] = "db"
        try:
            conn = sqlite3.connect(DB_PATH)
            result = conn.execute(
                "SELECT COUNT(*) FROM ("
                "  SELECT ticker FROM ohlcv_cache "
                "  WHERE date >= date('now', '-90 days') "
                "  GROUP BY ticker HAVING COUNT(*) >= 30"
                ")"
            ).fetchone()
            stats["count"] = int(result[0]) if result else 0
            stats["exists"] = True
            conn.close()
        except Exception as e:
            logger.warning(f"universe_stats DB query failed: {e}")
            stats["count"] = 0

    return stats
