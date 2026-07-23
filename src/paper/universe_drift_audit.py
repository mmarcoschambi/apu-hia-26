"""
Universe Drift Audit - Auditor de divergencia vs universo de referencia.
"""

import json
import logging
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import pandas as pd

logger = logging.getLogger(__name__)


@dataclass
class DriftAuditResult:
    divergence_pct: float
    live_coverage_pct: float
    live_extra_pct: float
    intersection: int
    union: int
    live_size: int
    ref_size: int
    gate_passed: bool
    block_reason: Optional[str] = None


def compute_drift_metrics(live: set[str], ref: set[str]) -> dict:
    """
    Calcula métricas de drift usando Jaccard distance.

    Args:
        live: Set de tickers del universe live (Finviz)
        ref: Set de tickers del universo de referencia (DB top liquidity)

    Returns:
        Dict con métricas de divergencia
    """
    intersection = live & ref
    union = live | ref

    divergence_pct = 100.0 * (1.0 - (len(intersection) / max(1, len(union))))
    live_coverage_pct = 100.0 * len(intersection) / max(1, len(ref))
    live_extra_pct = 100.0 * len(live - ref) / max(1, len(live))

    return {
        "intersection": len(intersection),
        "union": len(union),
        "divergence_pct": round(divergence_pct, 2),
        "live_coverage_pct": round(live_coverage_pct, 2),
        "live_extra_pct": round(live_extra_pct, 2),
    }


def get_reference_universe(db_path: Path, limit: int = 200) -> set[str]:
    """
    Obtiene universo de referencia desde DB (top liquidity).
    Misma lógica que get_universe_from_db del runbook.
    """
    try:
        conn = sqlite3.connect(str(db_path))
        end_date = datetime.now().strftime("%Y-%m-%d")
        start_date = (datetime.now() - timedelta(days=365)).strftime("%Y-%m-%d")

        df = pd.read_sql_query(
            """
            SELECT ticker, COUNT(*) as cnt
            FROM ohlcv_cache
            WHERE date >= ? AND date <= ?
            GROUP BY ticker
            ORDER BY cnt DESC
            LIMIT ?
            """,
            conn,
            params=(start_date, end_date, limit),
        )
        conn.close()

        if not df.empty:
            return set(df["ticker"].tolist())
    except Exception as e:
        logger.error(f"Error obteniendo universo de referencia: {e}")

    return set()


def run_drift_audit(
    live_tickers: list[str],
    db_path: Path,
    max_divergence_pct: float = 15.0,
    reference_limit: int = 200,
) -> DriftAuditResult:
    """
    Ejecuta auditoría de drift entre universe live y referencia.

    Args:
        live_tickers: Lista de tickers del universo live (Finviz)
        db_path: Path a la base de datos
        max_divergence_pct: Umbral máximo de divergencia (default 15%)
        reference_limit: Tamaño del universo de referencia (default 200)

    Returns:
        DriftAuditResult con métricas y gate_passed
    """
    live_set = set(live_tickers)
    ref_set = get_reference_universe(db_path, limit=reference_limit)

    if not ref_set:
        return DriftAuditResult(
            divergence_pct=0.0,
            live_coverage_pct=0.0,
            live_extra_pct=0.0,
            intersection=0,
            union=len(live_set),
            live_size=len(live_set),
            ref_size=0,
            gate_passed=False,
            block_reason="reference_universe_empty",
        )

    metrics = compute_drift_metrics(live_set, ref_set)

    # El drift se debe medir como la porción del universo de referencia (limit 200) que NO está cubierta por el live (Finviz ~600)
    # Jaccard distance (divergence_pct) falla matemáticamente por la disparidad estructural de tamaños de los conjuntos
    drift_pct = 100.0 - metrics["live_coverage_pct"]
    gate_passed = drift_pct <= max_divergence_pct
    block_reason = None if gate_passed else f"high_drift:{drift_pct:.2f}%"

    logger.info(
        f"Drift audit: divergence={drift_pct:.2f}% (Jaccard={metrics['divergence_pct']}%) "
        f"coverage={metrics['live_coverage_pct']}% "
        f"gate_passed={gate_passed}"
    )

    return DriftAuditResult(
        divergence_pct=metrics["divergence_pct"],
        live_coverage_pct=metrics["live_coverage_pct"],
        live_extra_pct=metrics["live_extra_pct"],
        intersection=metrics["intersection"],
        union=metrics["union"],
        live_size=len(live_set),
        ref_size=len(ref_set),
        gate_passed=gate_passed,
        block_reason=block_reason,
    )


def save_drift_audit(
    scan_date: str,
    result: DriftAuditResult,
    live_tickers: list[str],
    base_dir: Path,
) -> Path:
    """Guarda reporte de auditoría de drift."""
    try:
        date_dir = base_dir / scan_date
        date_dir.mkdir(parents=True, exist_ok=True)

        report = {
            "scan_date": scan_date,
            "divergence_pct": result.divergence_pct,
            "live_coverage_pct": result.live_coverage_pct,
            "live_extra_pct": result.live_extra_pct,
            "intersection": result.intersection,
            "union": result.union,
            "live_size": result.live_size,
            "ref_size": result.ref_size,
            "gate_passed": result.gate_passed,
            "block_reason": result.block_reason,
            "live_tickers_sample": sorted(live_tickers)[:50],
            "created_at": datetime.now().isoformat(),
        }

        output_path = date_dir / f"universe_audit_{scan_date}.json"
        with open(output_path, "w") as f:
            json.dump(report, f, indent=2, default=str)

        logger.info(f"[OK] Drift audit guardado: {output_path}")
        return output_path

    except Exception as e:
        logger.error(f"Error guardando drift audit: {e}")
        return Path("")


if __name__ == "__main__":
    from src.data.finviz_universe_provider import get_universe
    from src.paper.universe_snapshot_service import save_universe_snapshot

    logging.basicConfig(level=logging.INFO)

    ROOT = Path(__file__).parent.parent.parent
    DB_PATH = ROOT / "data" / "ticker_cache.db"
    SNAPSHOT_DIR = ROOT / "outputs" / "paper_trading" / "universe_snapshots"

    finviz_result = get_universe()
    print(f"Finviz: {len(finviz_result.tickers)} tickers, ok={finviz_result.ok}")

    today = datetime.now().strftime("%Y-%m-%d")
    meta = {
        "provider": finviz_result.provider,
        "fetched_at": finviz_result.fetched_at,
        "pages_ok": finviz_result.pages_ok,
        "raw_rows": finviz_result.raw_rows,
        "warnings": finviz_result.parse_warnings,
    }

    snapshot = save_universe_snapshot(today, finviz_result.tickers, meta, SNAPSHOT_DIR)
    print(f"Snapshot: ok={snapshot.ok}, hash={snapshot.hash}")

    drift = run_drift_audit(
        finviz_result.tickers,
        DB_PATH,
        max_divergence_pct=15.0,
        reference_limit=200,
    )
    print(f"Drift: gate_passed={drift.gate_passed}, divergence={drift.divergence_pct}%")
