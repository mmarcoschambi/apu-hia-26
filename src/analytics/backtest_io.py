"""
src/analytics/backtest_io.py
============================
Gestión de I/O para analytics de backtest.

Provee funciones para guardar/cargar resultados y compararlos con paper.
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
BACKTEST_OUTPUTS = PROJECT_ROOT / "outputs" / "backtests"


def save_backtest_analytics(run_id: str, payload: Dict) -> Path:
    """
    Guarda analytics JSON para un run de backtest.

    Args:
        run_id: Identificador único del run
        payload: Dict con schema canónico extendido

    Returns:
        Path al archivo guardado
    """
    BACKTEST_OUTPUTS.mkdir(parents=True, exist_ok=True)
    out_path = BACKTEST_OUTPUTS / f"analytics_{run_id}.json"
    with open(out_path, "w") as f:
        json.dump(payload, f, indent=2, default=str)
    logger.info(f"  [OK] Saved backtest analytics: {out_path}")
    return out_path


def load_backtest_analytics(run_id: str) -> Optional[Dict]:
    """
    Carga analytics para un run específico.

    Args:
        run_id: Identificador del run

    Returns:
        Dict con analytics o None si no existe
    """
    path = BACKTEST_OUTPUTS / f"analytics_{run_id}.json"
    if not path.exists():
        logger.warning(f"Backtest analytics not found: {run_id}")
        return None
    try:
        return json.load(open(path))
    except Exception as e:
        logger.warning(f"Could not load backtest analytics {run_id}: {e}")
        return None


def load_latest_backtest_analytics() -> Optional[Dict]:
    """
    Carga el análisis del backtest más reciente.

    Returns:
        Dict con analytics del último run o None
    """
    if not BACKTEST_OUTPUTS.exists():
        return None

    files = list(BACKTEST_OUTPUTS.glob("analytics_*.json"))
    if not files:
        return None

    # Sort by modification time, newest first
    latest = max(files, key=lambda f: f.stat().st_mtime)
    run_id = latest.stem.replace("analytics_", "")

    return load_backtest_analytics(run_id)


def list_backtest_runs() -> List[Dict]:
    """
    Lista todos los runs de backtest disponibles.

    Returns:
        Lista de dicts con {run_id, date, period_start, period_end, trades, pf}
    """
    if not BACKTEST_OUTPUTS.exists():
        return []

    runs = []
    for f in BACKTEST_OUTPUTS.glob("analytics_*.json"):
        try:
            data = json.load(open(f))
            meta = data.get("meta", {})
            oq = data.get("overall_quality", {})
            ts = data.get("trade_stats", {})

            runs.append(
                {
                    "run_id": meta.get("run_id", "unknown"),
                    "date": meta.get("date", ""),
                    "period_start": meta.get("period", {}).get("start", ""),
                    "period_end": meta.get("period", {}).get("end", ""),
                    "trades": ts.get("trades", 0),
                    "pf": oq.get("profit_factor", 0),
                    "sharpe": oq.get("sharpe", 0),
                    "cagr_pct": ts.get("cagr_pct", 0),
                }
            )
        except Exception as e:
            logger.warning(f"Could not parse {f.name}: {e}")

    return sorted(runs, key=lambda x: x.get("date", ""), reverse=True)


def compare_backtest_vs_paper(backtest_data: Dict, paper_date: str) -> Dict:
    """
    Compara métricas de backtest vs paper para el weekly review.

    Args:
        backtest_data: Analytics del backtest
        paper_date: Fecha del paper analytics a comparar (YYYY-MM-DD)

    Returns:
        Dict con comparación: {metric, backtest_value, paper_value, diff}
    """
    from src.paper.analytics_io import load_analytics

    paper_data = load_analytics(paper_date)

    if paper_data is None:
        return {"error": f"No paper analytics for {paper_date}"}

    # Extract metrics to compare
    bt_oq = backtest_data.get("overall_quality", {})
    pa_oq = paper_data.get("overall_quality", {})

    bt_ts = backtest_data.get("trade_stats", {})
    pa_ts = paper_data.get("trade_stats", {})

    comparisons = []
    metrics = [
        ("profit_factor", "PF"),
        ("sharpe", "Sharpe"),
        ("calmar", "Calmar"),
        ("max_drawdown_90d", "Max DD %"),
        ("expectancy", "Expectancy"),
    ]

    for key, label in metrics:
        bt_val = bt_oq.get(key, 0)
        pa_val = pa_oq.get(key, 0)

        if pa_val and bt_val:
            diff = bt_val - pa_val
            comparisons.append(
                {
                    "metric": label,
                    "backtest_value": round(bt_val, 2),
                    "paper_value": round(pa_val, 2),
                    "diff": round(diff, 2),
                }
            )

    # Trades comparison
    bt_trades = bt_ts.get("trades", 0)
    pa_trades = pa_ts.get("trades", 0)
    comparisons.append(
        {
            "metric": "Trades",
            "backtest_value": bt_trades,
            "paper_value": pa_trades,
            "diff": bt_trades - pa_trades,
        }
    )

    return {
        "backtest_run_id": backtest_data.get("meta", {}).get("run_id"),
        "paper_date": paper_date,
        "comparisons": comparisons,
        "system_edge": backtest_data.get("system_vs_actual", {}),
    }


# === CLI TEST ===

if __name__ == "__main__":
    print("Testing backtest_io...")

    # List runs (empty for now)
    runs = list_backtest_runs()
    print(f"  Found {len(runs)} backtest runs")

    # Load latest (may be None)
    latest = load_latest_backtest_analytics()
    print(f"  Latest: {latest['meta']['run_id'] if latest else 'None'}")
