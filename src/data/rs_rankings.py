"""
src/data/rs_rankings.py
Funciones de lectura del RS cross-sectional desde daily_rs_rankings.
"""
import sqlite3
import pandas as pd
from pathlib import Path
from functools import lru_cache
from typing import Optional, List
import logging

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).parent.parent.parent
DB_PATH = PROJECT_ROOT / "data" / "ticker_cache.db"


_persistent_conn = None


def _get_persistent_conn() -> sqlite3.Connection:
    global _persistent_conn
    if _persistent_conn is None:
        _persistent_conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    return _persistent_conn


def _get_conn() -> sqlite3.Connection:
    return sqlite3.connect(DB_PATH)


@lru_cache(maxsize=1048576)
def _get_rs_percentile_cached(ticker: str, date: Optional[str], metric: str, max_age_days: Optional[int] = 5) -> Optional[float]:
    conn = _get_persistent_conn()
    if date:
        query = f"SELECT date, {metric} FROM daily_rs_rankings WHERE ticker=? AND date=?"
        row = conn.execute(query, (ticker, date)).fetchone()
    else:
        query = f"SELECT date, {metric} FROM daily_rs_rankings WHERE ticker=? ORDER BY date DESC LIMIT 1"
        row = conn.execute(query, (ticker,)).fetchone()
        
    if not row:
        return None
        
    row_date, val = row
    if date is None and max_age_days is not None:
        from datetime import datetime
        try:
            db_date = datetime.strptime(row_date, "%Y-%m-%d")
            age = (datetime.now() - db_date).days
            if age > max_age_days:
                logger.warning(f"RS data for {ticker} is stale (age={age}d > {max_age_days}d). Returning None.")
                return None
        except Exception:
            pass
            
    return val


def get_rs_percentile(
    ticker: str,
    date: Optional[str] = None,
    metric: str = "rs_composite",
    conn: Optional[sqlite3.Connection] = None,
    max_age_days: Optional[int] = 5,
) -> Optional[float]:
    """
    Retorna el percentil RS de un ticker en una fecha dada.

    Args:
        ticker: Símbolo (ej. 'NVDA')
        date:   Fecha YYYY-MM-DD. Si None, usa la última disponible.
        metric: 'rs_composite' | 'rs_60d_pct' | 'rs_20d_pct' | 'rs_5d_pct'
        conn:   Conexión opcional (para reutilizar)
        max_age_days: Edad máxima permitida en días si date es None.

    Returns:
        Percentil 0–100 o None si no hay datos o están stale.
    """
    valid_metrics = {"rs_composite", "rs_60d_pct", "rs_20d_pct", "rs_5d_pct"}
    if metric not in valid_metrics:
        raise ValueError(f"metric debe ser uno de {valid_metrics}")

    if conn is not None:
        if date:
            query = f"SELECT date, {metric} FROM daily_rs_rankings WHERE ticker=? AND date=?"
            row = conn.execute(query, (ticker, date)).fetchone()
        else:
            query = f"SELECT date, {metric} FROM daily_rs_rankings WHERE ticker=? ORDER BY date DESC LIMIT 1"
            row = conn.execute(query, (ticker,)).fetchone()
            
        if not row:
            return None
            
        row_date, val = row
        if date is None and max_age_days is not None:
            from datetime import datetime
            try:
                db_date = datetime.strptime(row_date, "%Y-%m-%d")
                age = (datetime.now() - db_date).days
                if age > max_age_days:
                    return None
            except Exception:
                pass
        return val

    return _get_rs_percentile_cached(ticker, date, metric, max_age_days)


def get_top_rs_tickers(
    date: Optional[str] = None,
    percentile: float = 97.0,
    metric: str = "rs_composite",
    min_universe_size: int = 50,
    conn: Optional[sqlite3.Connection] = None,
) -> List[str]:
    """
    Retorna los tickers en el Top N% de RS para una fecha.

    Args:
        date:              Fecha YYYY-MM-DD. Si None, última disponible.
        percentile:        Umbral mínimo (ej. 97 = Top 3%).
        metric:            Métrica a usar.
        min_universe_size: Ignora fechas con universo muy pequeño.

    Returns:
        Lista de tickers ordenados de mayor a menor percentil.
    """
    close_conn = conn is None
    conn = conn or _get_conn()

    try:
        if date is None:
            row = conn.execute(
                "SELECT date FROM daily_rs_rankings ORDER BY date DESC LIMIT 1"
            ).fetchone()
            if not row:
                return []
            date = row[0]

        query = f"""
            SELECT ticker, {metric}
            FROM daily_rs_rankings
            WHERE date = ?
              AND {metric} >= ?
              AND universe_size >= ?
            ORDER BY {metric} DESC
        """
        rows = conn.execute(query, (date, percentile, min_universe_size)).fetchall()
        return [r[0] for r in rows]
    finally:
        if close_conn:
            conn.close()


def get_rs_dataframe(
    date: Optional[str] = None,
    conn: Optional[sqlite3.Connection] = None,
) -> pd.DataFrame:
    """
    Retorna todos los RS rankings de una fecha como DataFrame.
    Útil para análisis masivos.
    """
    close_conn = conn is None
    conn = conn or _get_conn()

    try:
        if date is None:
            row = conn.execute(
                "SELECT date FROM daily_rs_rankings ORDER BY date DESC LIMIT 1"
            ).fetchone()
            if not row:
                return pd.DataFrame()
            date = row[0]

        query = "SELECT * FROM daily_rs_rankings WHERE date = ? ORDER BY rs_composite DESC"
        df = pd.read_sql_query(query, conn, params=(date,))
        return df
    finally:
        if close_conn:
            conn.close()


def get_rs_history(
    ticker: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    conn: Optional[sqlite3.Connection] = None,
) -> pd.DataFrame:
    """
    Retorna la historia de RS percentiles de un ticker.
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
        query = f"SELECT * FROM daily_rs_rankings WHERE {where} ORDER BY date"
        df = pd.read_sql_query(query, conn, params=params)
        return df
    finally:
        if close_conn:
            conn.close()
