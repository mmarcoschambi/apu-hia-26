"""
src/paper/analytics_io.py
==========================
Gestión de I/O para analytics: load/save trades, equity, snapshots, y analytics.

Provee funciones utilitarias para que runbook y weekly review lean/escriban
sin duplicar lógica.
"""

import json
import logging
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
OUTPUTS_DIR = PROJECT_ROOT / "outputs" / "paper_trading"
DB_PATH = PROJECT_ROOT / "data" / "ticker_cache.db"

DEFAULT_CAPITAL = 100_000


def load_trades_for_date(date: str) -> List[Dict]:
    """
    Carga trades para una fecha específica desde paper_trades.csv.

    Handles multiple date column names and missing columns gracefully.
    """
    trades_path = OUTPUTS_DIR / "paper_trades.csv"
    if not trades_path.exists():
        return []

    try:
        df = pd.read_csv(trades_path)

        # Find date column - check common names
        date_col = None
        for col in ["date", "entry_date", "exit_date", "timestamp", "trade_date"]:
            if col in df.columns:
                date_col = col
                break

        if date_col is None:
            logger.warning(f"Could not load trades for {date}: no date column found")
            return []

        df[date_col] = pd.to_datetime(df[date_col]).dt.strftime("%Y-%m-%d")
        day_trades = df[df[date_col] == date]
        return day_trades.to_dict("records")
    except Exception as e:
        logger.warning(f"Could not load trades for {date}: {e}")
        return []


def load_trades_range(start_date: str, end_date: str) -> List[Dict]:
    """
    Carga trades en un rango de fechas.
    """
    trades_path = OUTPUTS_DIR / "paper_trades.csv"
    if not trades_path.exists():
        return []

    try:
        df = pd.read_csv(trades_path)
        df["date"] = pd.to_datetime(df["date"])
        mask = (df["date"] >= start_date) & (df["date"] <= end_date)
        return df[mask].to_dict("records")
    except Exception as e:
        logger.warning(f"Could not load trades range {start_date}-{end_date}: {e}")
        return []


def load_equity_history(days: int = 90) -> pd.Series:
    """
    Carga historial de equity desde capital.json (ultimos N días).

    Returns:
        pd.Series con índice fecha, valores equity
    """
    capital_path = OUTPUTS_DIR / "capital.json"
    if not capital_path.exists():
        return pd.Series(dtype=float)

    try:
        data = json.load(open(capital_path))
        records = data.get("history", [])
        if not records:
            return pd.Series(dtype=float)

        df = pd.DataFrame(records)
        df["date"] = pd.to_datetime(df["date"])
        df = df.sort_values("date")

        cutoff = datetime.now() - timedelta(days=days)
        df = df[df["date"] >= cutoff]

        return df.set_index("date")["equity"]
    except Exception as e:
        logger.warning(f"Could not load equity history: {e}")
        return pd.Series(dtype=float)


def load_actual_snapshot(date: str) -> Optional[Dict]:
    """
    Carga snapshot real del portfolio para una fecha.

    Busca en outputs/paper_trading/ y outputs/baseline_snapshots/...
    """
    # Try capital.json current
    capital_path = OUTPUTS_DIR / "capital.json"
    if capital_path.exists():
        try:
            data = json.load(open(capital_path))
            current = data.get("current", {})
            snap_date = current.get("date", "")
            if snap_date == date:
                return {
                    "date": snap_date,
                    "equity": current.get("equity", DEFAULT_CAPITAL),
                }
        except Exception:
            pass

    # Try baseline snapshots
    baseline_dir = PROJECT_ROOT / "baseline_snapshots"
    if baseline_dir.exists():
        for subdir in sorted(baseline_dir.iterdir(), reverse=True):
            snap_file = subdir / "snapshot.json"
            if snap_file.exists():
                try:
                    snap = json.load(open(snap_file))
                    if snap.get("date") == date:
                        return {
                            "date": date,
                            "equity": snap.get("equity", DEFAULT_CAPITAL),
                        }
                except Exception:
                    continue

    return None


def save_daily_analytics(date: str, payload: Dict) -> Path:
    """
    Guarda analytics JSON para una fecha.
    """
    OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUTPUTS_DIR / f"analytics_{date}.json"
    with open(out_path, "w") as f:
        json.dump(payload, f, indent=2, default=str)
    logger.info(f"  [OK] Saved analytics: {out_path}")
    return out_path


def load_analytics(date: str) -> Optional[Dict]:
    """
    Carga analytics para una fecha específica.
    """
    path = OUTPUTS_DIR / f"analytics_{date}.json"
    if not path.exists():
        return None
    try:
        return json.load(open(path))
    except Exception as e:
        logger.warning(f"Could not load analytics for {date}: {e}")
        return None


def load_analytics_range(start_date: str, end_date: str) -> List[Dict]:
    """
    Carga analytics para un rango de fechas.
    """
    results = []
    start = pd.to_datetime(start_date)
    end = pd.to_datetime(end_date)

    for i in range((end - start).days + 1):
        check_date = (start + timedelta(days=i)).strftime("%Y-%m-%d")
        data = load_analytics(check_date)
        if data:
            results.append(data)

    return results


def get_market_score_from_context(ctx: Dict) -> Optional[float]:
    """
    Extrae market_score del régimen context.

    Intenta usar el motor real de market_score (S3).
    Si falla, usa fallback heurístico.
    """
    # Try real engine (S3)
    try:
        from src.analytics.market_score_engine import get_live_market_score

        score, meta = get_live_market_score()

        # Check quality flags
        if meta.get("quality_flags"):
            logger.debug(f"Market score quality flags: {meta['quality_flags']}")

        return score
    except Exception as e:
        logger.debug(f"Real market score engine failed, using fallback: {e}")

    # Fallback heuristic (original S1/S2 behavior)
    if ctx is None:
        return None

    spy_ok = ctx.get("spy_ok", True)
    vix_ok = ctx.get("vix_ok", True)
    quality = ctx.get("regime_quality", "OK")

    score = 50.0  # base

    if spy_ok and vix_ok and quality == "OK":
        score = 70.0
    elif spy_ok and quality == "OK":
        score = 55.0
    elif vix_ok:
        score = 40.0
    else:
        score = 20.0

    return score


def build_analytics_inputs(date: str, runbook_result: Optional[Dict] = None) -> Dict:
    """
    Construye los inputs necesarios para compute_daily_analytics.

    Reune trades, equity history, market context, y actual snapshot.
    """
    # Trades
    trades = load_trades_for_date(date)

    # Equity history (90 days)
    equity_curve = load_equity_history(days=90)

    # Market context (from pre_report si existe)
    market_score = None
    regime_quality = "OK"

    pre_report_path = OUTPUTS_DIR / f"pre_report_{date}.json"
    if pre_report_path.exists():
        try:
            pre = json.load(open(pre_report_path))
            ctx = pre.get("regime", {})
            market_score = get_market_score_from_context(ctx)
            regime_quality = ctx.get("regime_quality", "OK")
        except Exception:
            pass

    # Actual snapshot
    actual_snapshot = load_actual_snapshot(date)

    # Initial capital (from capital.json current si existe)
    initial_capital = DEFAULT_CAPITAL
    capital_path = OUTPUTS_DIR / "capital.json"
    if capital_path.exists():
        try:
            data = json.load(open(capital_path))
            initial_capital = data.get("current", {}).get("equity", DEFAULT_CAPITAL)
        except Exception:
            pass

    return {
        "trades": trades,
        "equity_curve": equity_curve,
        "market_score": market_score,
        "regime_quality": regime_quality,
        "actual_snapshot": actual_snapshot,
        "initial_capital": initial_capital,
    }


# === CLI TEST ===

if __name__ == "__main__":
    print("Testing analytics_io...")

    # Test build_analytics_inputs (vacio pero no rompe)
    result = build_analytics_inputs("2026-04-09")
    print(f"  Trades: {len(result['trades'])}")
    print(f"  Equity length: {len(result['equity_curve'])}")
    print(f"  Market score: {result['market_score']}")
    print(f"  Initial capital: {result['initial_capital']}")
