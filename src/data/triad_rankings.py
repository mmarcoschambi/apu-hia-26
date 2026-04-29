"""
src/data/triad_rankings.py
Funciones de lectura del daily_triad_rankings (RTS/AS/Trend).
"""

import sqlite3
import pandas as pd
from pathlib import Path
from typing import Optional, List, Dict, Any
import logging

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).parent.parent.parent
DB_PATH = PROJECT_ROOT / "data" / "ticker_cache.db"


def _get_conn() -> sqlite3.Connection:
    return sqlite3.connect(DB_PATH)


def get_triad_metrics(
    ticker: str,
    date: Optional[str] = None,
    conn: Optional[sqlite3.Connection] = None,
) -> Optional[Dict[str, Any]]:
    """
    Retorna las métricas RTS/AS de un ticker en una fecha dada.

    Args:
        ticker: Símbolo (ej. 'NVDA')
        date:   Fecha YYYY-MM-DD. Si None, usa la última disponible.
        conn:   Conexión opcional (para reutilizar)

    Returns:
        Dict con métricas o None si no hay datos.
    """
    close_conn = conn is None
    conn = conn or _get_conn()

    try:
        if date:
            query = """
                SELECT as_5d_pct, as_21d_pct, trend_score_raw, rs_composite, 
                       rts_raw, rts_pct, atr14, atr14_universe_mean, 
                       pivot_dist_pct, green_candle
                FROM daily_triad_rankings 
                WHERE ticker=? AND date=?
            """
            row = conn.execute(query, (ticker, date)).fetchone()
        else:
            query = """
                SELECT as_5d_pct, as_21d_pct, trend_score_raw, rs_composite,
                       rts_raw, rts_pct, atr14, atr14_universe_mean,
                       pivot_dist_pct, green_candle
                FROM daily_triad_rankings 
                WHERE ticker=? ORDER BY date DESC LIMIT 1
            """
            row = conn.execute(query, (ticker,)).fetchone()

        if not row:
            return None

        return {
            "as_5d_pct": row[0],
            "as_21d_pct": row[1],
            "trend_score_raw": row[2],
            "rs_composite": row[3],
            "rts_raw": row[4],
            "rts_pct": row[5],
            "atr14": row[6],
            "atr14_universe_mean": row[7],
            "pivot_dist_pct": row[8],
            "green_candle": bool(row[9]),
        }
    finally:
        if close_conn:
            conn.close()


def get_top_rts_tickers(
    date: Optional[str] = None,
    min_rts_pct: float = 90.0,
    min_universe_size: int = 50,
    conn: Optional[sqlite3.Connection] = None,
) -> List[str]:
    """
    Retorna los tickers con RTS >= min_rts_pct para una fecha.

    Args:
        date:              Fecha YYYY-MM-DD. Si None, última disponible.
        min_rts_pct:       Umbral mínimo de RTS percentil (default 90)
        min_universe_size: Ignora fechas con universo muy pequeño.
        conn:              Conexión opcional.

    Returns:
        Lista de tickers ordenados de mayor a menor rts_pct.
    """
    close_conn = conn is None
    conn = conn or _get_conn()

    try:
        if date is None:
            row = conn.execute(
                "SELECT date FROM daily_triad_rankings ORDER BY date DESC LIMIT 1"
            ).fetchone()
            if not row:
                return []
            date = row[0]

        query = """
            SELECT ticker, rts_pct
            FROM daily_triad_rankings
            WHERE date = ?
              AND rts_pct >= ?
              AND universe_size >= ?
            ORDER BY rts_pct DESC
        """
        rows = conn.execute(query, (date, min_rts_pct, min_universe_size)).fetchall()
        return [r[0] for r in rows]
    finally:
        if close_conn:
            conn.close()


def get_triad_dataframe(
    date: Optional[str] = None,
    conn: Optional[sqlite3.Connection] = None,
) -> pd.DataFrame:
    """
    Retorna todos los rankings RTS de una fecha como DataFrame.
    Útil para análisis masivos.
    """
    close_conn = conn is None
    conn = conn or _get_conn()

    try:
        if date is None:
            row = conn.execute(
                "SELECT date FROM daily_triad_rankings ORDER BY date DESC LIMIT 1"
            ).fetchone()
            if not row:
                return pd.DataFrame()
            date = row[0]

        query = (
            "SELECT * FROM daily_triad_rankings WHERE date = ? ORDER BY rts_pct DESC"
        )
        df = pd.read_sql_query(query, conn, params=(date,))
        return df
    finally:
        if close_conn:
            conn.close()


def get_triad_history(
    ticker: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    conn: Optional[sqlite3.Connection] = None,
) -> pd.DataFrame:
    """
    Retorna la historia de métricas RTS de un ticker.
    """
    close_conn = conn is None
    conn = conn or _get_conn()

    try:
        conditions = ["ticker = ?"]
        params: list = [ticker]
        if start_date:
            conditions.append("date >= ?")
            params.append(start_date)
        if end_date:
            conditions.append("date <= ?")
            params.append(end_date)

        where = " AND ".join(conditions)
        query = f"SELECT * FROM daily_triad_rankings WHERE {where} ORDER BY date"
        df = pd.read_sql_query(query, conn, params=params)
        return df
    finally:
        if close_conn:
            conn.close()


def get_passing_tickers(
    date: str,
    min_as_5d_pct: float = 50.0,
    min_as_21d_pct: float = 50.0,
    min_rts_pct: float = 90.0,
    require_green_candle: bool = False,
    conn: Optional[sqlite3.Connection] = None,
) -> List[str]:
    """
    Retorna tickers que cumplen los filtros AS + RTS + green candle.

    Útil para validaciones rápidas del pipeline completo.
    """
    close_conn = conn is None
    conn = conn or _get_conn()

    try:
        query = """
            SELECT ticker FROM daily_triad_rankings
            WHERE date = ?
              AND as_5d_pct >= ?
              AND as_21d_pct >= ?
              AND rts_pct >= ?
        """
        params = [date, min_as_5d_pct, min_as_21d_pct, min_rts_pct]

        if require_green_candle:
            query += " AND green_candle = 1"

        query += " ORDER BY rts_pct DESC"

        rows = conn.execute(query, params).fetchall()
        return [r[0] for r in rows]
    finally:
        if close_conn:
            conn.close()
