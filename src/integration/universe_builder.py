#!/usr/bin/env python3
"""
src/integration/universe_builder.py
Construcción de universo point-in-time para walk-forward.
ETF permitidos.
"""
from __future__ import annotations
import logging
import re
import sqlite3
from dataclasses import dataclass
from pathlib import Path
import pandas as pd

logger = logging.getLogger(__name__)

# Excluir símbolos obviamente no-US/listado raro:
# - sufijo internacional con guion (ej: 7974-T)
# - OTC común (final F/Y/Q)
# - warrants/units/rights básicos (W/U/R al final)
_NON_US_DASH_SUFFIX = re.compile(r".+-[A-Z]{1,3}$")
_OTC_SUFFIX = re.compile(r".*[FYQ]$")  # conservador; GOOGL no cae aquí
_STRUCT_SUFFIX = re.compile(r".*[WUR]$")

@dataclass
class UniverseSnapshot:
    cutoff_date: str
    tickers: list[str]
    n_candidates_raw: int
    n_excluded_symbol: int
    n_excluded_history: int
    n_excluded_liquidity: int
    n_excluded_gaps: int
    n_selected: int
    adv20_stats: dict
    coverage_recent_pct: float

def _is_clean_symbol(ticker: str) -> bool:
    t = ticker.upper().strip()
    if not t:
        return False
    if _NON_US_DASH_SUFFIX.match(t):
        return False
    if _OTC_SUFFIX.match(t) and len(t) >= 4:
        # Excluir OTCs pero permitir símbolos de 4 letras normales (como AAPL, GOOG)
        # Los OTC suelen terminar en F/Y/Q y tener 5 letras (ej: AAVVF)
        if len(t) == 5:
            return False
    if _STRUCT_SUFFIX.match(t) and len(t) >= 4:
        return False
    return True

def _pct(values: list[float], q: float) -> float:
    if not values:
        return 0.0
    i = min(len(values) - 1, max(0, int(round((len(values) - 1) * q))))
    return float(values[i])

def build_universe_for_fold(
    db_path: Path,
    cutoff_date: str,
    window_start: str,
    max_tickers: int = 200,
    min_bars: int = 252,
    min_adv20: float = 5_000_000.0,
    recent_bars: int = 60,
    max_gap_pct: float = 0.15,
    table: str = "ohlcv_cache",
    index_name: str = "SP500",
    use_pit: bool = True,
) -> UniverseSnapshot:
    """
    Construye un universo PIT (Point-In-Time) basado en la cutoff_date.
    Filtra por historia, liquidez (ADV20) y cobertura de datos (gaps).
    """
    conn = sqlite3.connect(str(db_path))
    try:
        # 1) candidatos con historia mínima en [window_start, cutoff_date]
        # Integración de pit_constituents de QuantConnect:
        use_pit_filter = False
        pit_date = None
        
        # Verificar si existe la tabla pit_constituents y tiene registros para esta fecha
        table_exists = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='pit_constituents'"
        ).fetchone()
        
        if table_exists and use_pit:
            # Buscamos el snapshot de membresía mensual más cercano (menor o igual a cutoff_date) para ese índice específico
            db_date_row = conn.execute(
                "SELECT DISTINCT date FROM pit_constituents WHERE date <= ? AND index_member = ? ORDER BY date DESC LIMIT 1",
                (cutoff_date, index_name)
            ).fetchone()
            if db_date_row:
                pit_date = db_date_row[0]
                use_pit_filter = True
                logger.info(f"🎯 PIT filter enabled for {cutoff_date} (Index: {index_name}, using snapshot {pit_date})")

        if use_pit_filter:
            hist_rows = conn.execute(
                f"""
                SELECT ticker, COUNT(*) as bars
                FROM {table}
                WHERE date >= ? AND date <= ?
                  AND ticker IN (SELECT ticker FROM pit_constituents WHERE date = ? AND index_member = ?)
                GROUP BY ticker
                HAVING COUNT(*) >= ?
                """,
                (window_start, cutoff_date, pit_date, index_name, min_bars),
            ).fetchall()
        else:
            hist_rows = conn.execute(
                f"""
                SELECT ticker, COUNT(*) as bars
                FROM {table}
                WHERE date >= ? AND date <= ?
                GROUP BY ticker
                HAVING COUNT(*) >= ?
                """,
                (window_start, cutoff_date, min_bars),
            ).fetchall()
            
        n_candidates_raw = len(hist_rows)

        # 2) filtro símbolo
        filtered = []
        n_excluded_symbol = 0
        for ticker, bars in hist_rows:
            if not _is_clean_symbol(ticker):
                n_excluded_symbol += 1
                continue
            filtered.append((ticker, int(bars)))

        # 3) referencia de calendario reciente (SPY) para check de gaps
        spy_dates = [
            r[0]
            for r in conn.execute(
                f"""
                SELECT date
                FROM {table}
                WHERE ticker = 'SPY' AND date <= ?
                ORDER BY date DESC
                LIMIT ?
                """,
                (cutoff_date, recent_bars),
            ).fetchall()
        ]
        ref_days = len(spy_dates) if spy_dates else recent_bars

        # 4) por ticker: ADV20 real (últimas 20 barras) + cobertura reciente
        candidates = []
        n_excluded_history = 0
        n_excluded_liquidity = 0
        n_excluded_gaps = 0
        
        for ticker, bars in filtered:
            # Obtener últimas 20 barras para ADV real
            last20 = conn.execute(
                f"""
                SELECT close, volume
                FROM {table}
                WHERE ticker = ? AND date <= ?
                ORDER BY date DESC
                LIMIT 20
                """,
                (ticker, cutoff_date),
            ).fetchall()
            
            if len(last20) < 20:
                n_excluded_history += 1
                continue
            
            valid_last20 = [(c, v) for c, v in last20 if c is not None and v is not None]
            if not valid_last20:
                n_excluded_history += 1
                continue
                
            adv20 = float(sum(float(c) * float(v) for c, v in valid_last20) / len(valid_last20))
            if adv20 < min_adv20:
                n_excluded_liquidity += 1
                continue

            # Check de cobertura reciente
            recent_cnt = conn.execute(
                f"""
                SELECT COUNT(*)
                FROM (
                    SELECT date
                    FROM {table}
                    WHERE ticker = ? AND date <= ?
                    ORDER BY date DESC
                    LIMIT ?
                )
                """,
                (ticker, cutoff_date, recent_bars),
            ).fetchone()[0]
            
            coverage = float(recent_cnt) / max(ref_days, 1)
            gap_pct = max(0.0, 1.0 - coverage)
            if gap_pct > max_gap_pct:
                n_excluded_gaps += 1
                continue

            candidates.append((ticker, adv20, coverage))

        # 5) ranking neutral/determinista (Top ADV20 desc, tie-break ticker asc)
        candidates.sort(key=lambda x: (-x[1], x[0]))
        selected = candidates[:max_tickers]
        tickers = [t for t, _, _ in selected]
        
        advs = sorted([a for _, a, _ in selected])
        covs = [c for _, _, c in selected]
        
        adv20_stats = {
            "min": round(advs[0], 0) if advs else 0.0,
            "p10": round(_pct(advs, 0.10), 0) if advs else 0.0,
            "median": round(_pct(advs, 0.50), 0) if advs else 0.0,
            "p90": round(_pct(advs, 0.90), 0) if advs else 0.0,
            "max": round(advs[-1], 0) if advs else 0.0,
        }
        coverage_recent_pct = round((sum(covs) / len(covs)) * 100.0, 1) if covs else 0.0

        snap = UniverseSnapshot(
            cutoff_date=cutoff_date,
            tickers=tickers,
            n_candidates_raw=n_candidates_raw,
            n_excluded_symbol=n_excluded_symbol,
            n_excluded_history=n_excluded_history,
            n_excluded_liquidity=n_excluded_liquidity,
            n_excluded_gaps=n_excluded_gaps,
            n_selected=len(tickers),
            adv20_stats=adv20_stats,
            coverage_recent_pct=coverage_recent_pct,
        )
        
        logger.info(
            "universe_builder cutoff=%s raw=%d selected=%d (sym=%d hist=%d liq=%d gap=%d)",
            cutoff_date,
            n_candidates_raw,
            snap.n_selected,
            n_excluded_symbol,
            n_excluded_history,
            n_excluded_liquidity,
            n_excluded_gaps,
        )
        return snap
    finally:
        conn.close()
