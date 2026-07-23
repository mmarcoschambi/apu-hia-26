"""
Signal Engine — Módulo de Inyección de Rankings Pre-calculados
==============================================================
Carga daily_triad_rankings desde la DB UNA SOLA VEZ al inicio del backtest
y los convierte en arrays float32 listos para inyectar en el motor.

Elimina el cálculo on-the-fly de RS en prepare_numba_arrays(), convirtiendo
500 operaciones de rank() matricial por trial -> 1 lectura de DB por backtest.

Paridad garantizada: usa exactamente el mismo RS que live_trading_scanner.py
"""

import numpy as np
import pandas as pd
import sqlite3
import logging
from pathlib import Path
from typing import Optional, Tuple, Dict
import time

logger = logging.getLogger(__name__)


# ============================================================================
# DB PATH — resuelve relativo al proyecto
# ============================================================================
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
_DEFAULT_DB = _PROJECT_ROOT / "data" / "ticker_cache.db"


# ============================================================================
# CARGA PRINCIPAL
# ============================================================================

def load_precomputed_signals(
    tickers: list,
    start_date: str,
    end_date: str,
    db_path: Optional[str] = None,
) -> Dict[str, pd.DataFrame]:
    """
    Carga daily_triad_rankings para el rango de fechas dado y los tickers
    del universo. Devuelve un dict de DataFrames pivotados (date × ticker).

    Columnas disponibles:
        rs_composite      — Fuerza Relativa combinada (principal del Sistema B)
        rts_pct           — Percentil de RS real (0-100)
        trend_score_raw   — Score de tendencia unificado (Sistema A)
        pivot_dist_pct    — Distancia al pivot (breakout proximity)
        as_5d_pct         — Momentum 5d percentil
        as_21d_pct        — Momentum 21d percentil

    Args:
        tickers:    Lista de tickers del universo del backtest
        start_date: 'YYYY-MM-DD' — inicio del período (con buffer incluido)
        end_date:   'YYYY-MM-DD' — fin del período
        db_path:    Ruta a ticker_cache.db (opcional, usa default del proyecto)

    Returns:
        Dict[nombre_col -> DataFrame(index=date, columns=tickers, dtype=float32)]
        Retorna dict vacío si la DB no está disponible (fallback seguro).
    """
    t0 = time.perf_counter()
    db = Path(db_path) if db_path else _DEFAULT_DB

    if not db.exists():
        logger.warning(f"[WARN]  signal_engine: DB not found at {db}. Falling back to on-the-fly RS.")
        return {}

    # Columnas que queremos cargar
    SIGNAL_COLS = [
        "rs_composite",
        "rts_pct",
        "trend_score_raw",
        "pivot_dist_pct",
        "as_5d_pct",
        "as_21d_pct",
    ]

    try:
        conn = sqlite3.connect(str(db), timeout=30)

        # Query con filtro de tickers para no cargar el universo completo
        placeholders = ",".join("?" * len(tickers))
        query = f"""
            SELECT date, ticker, {", ".join(SIGNAL_COLS)}
            FROM daily_triad_rankings
            WHERE date BETWEEN ? AND ?
              AND ticker IN ({placeholders})
        """
        params = [start_date, end_date] + list(tickers)

        df_raw = pd.read_sql_query(query, conn, params=params)
        conn.close()

        if df_raw.empty:
            logger.warning(
                f"[WARN]  signal_engine: No ranking data found for "
                f"{len(tickers)} tickers between {start_date} and {end_date}."
            )
            return {}

        df_raw["date"] = pd.to_datetime(df_raw["date"])

        # Cobertura
        covered = df_raw["ticker"].nunique()
        total = len(tickers)
        coverage_pct = covered / total * 100
        logger.info(
            f"[CHART] signal_engine: Loaded {len(df_raw):,} rows | "
            f"Coverage: {covered}/{total} tickers ({coverage_pct:.1f}%) | "
            f"Date range: {df_raw['date'].min().date()} -> {df_raw['date'].max().date()}"
        )

        if coverage_pct < 50:
            logger.warning(
                f"[WARN]  signal_engine: Low coverage ({coverage_pct:.1f}%). "
                f"Consider running populate_triad_rankings.py to expand universe."
            )

        # Pivotar cada columna: date × ticker (float32)
        result: Dict[str, pd.DataFrame] = {}
        for col in SIGNAL_COLS:
            pivot = (
                df_raw.pivot(index="date", columns="ticker", values=col)
                .astype(np.float32)
            )
            pivot.index = pd.to_datetime(pivot.index)
            result[col] = pivot

        elapsed = time.perf_counter() - t0
        logger.info(f"[OK] signal_engine: Signals loaded in {elapsed:.2f}s — {len(SIGNAL_COLS)} matrices ready")

        return result

    except Exception as e:
        logger.error(f"[FAIL] signal_engine: Failed to load rankings: {e}")
        return {}


# ============================================================================
# BUILDER DE ENTRY SCORE — reemplaza el bloque de prepare_numba_arrays()
# ============================================================================

def build_entry_score_from_signals(
    signals: Dict[str, pd.DataFrame],
    close_index: pd.DatetimeIndex,
    tickers: list,
    rs_weight: float = 0.70,
    proximity_weight: float = 0.30,
    rs_short_weight: float = 0.35,
    close_df: Optional[pd.DataFrame] = None,
) -> Optional[np.ndarray]:
    """
    Construye el entry_score float32 (shape: n_dates × n_tickers) usando
    los rankings pre-calculados de la DB.

    Lógica idéntica al bloque original de prepare_numba_arrays():
        entry_score = rs_weight * RS_combined + proximity_weight * proximity_52wk

    donde RS_combined = (1 - rs_short_weight) * rs_composite_normalized
                       + rs_short_weight * rts_pct_normalized

    La proximidad_52wk se calcula desde close_df solo si está disponible,
    sino se usa 0.5 neutro (sin penalizar el score base de RS).

    Args:
        signals:          Dict retornado por load_precomputed_signals()
        close_index:      DatetimeIndex del engine.close (fechas del backtest)
        tickers:          Lista de tickers del engine
        rs_weight:        Peso del componente RS (default 0.70)
        proximity_weight: Peso de la proximidad 52wk (default 0.30)
        rs_short_weight:  Peso del RS corto plazo dentro del componente RS
        close_df:         engine.close DataFrame para calcular proximity_52wk

    Returns:
        np.ndarray float32 shape (n_dates, n_tickers), o None si falla.
    """
    if not signals:
        return None

    n_rows = len(close_index)
    n_cols = len(tickers)
    target_shape = (n_rows, n_cols)

    try:
        def _align_signal(sig_df: pd.DataFrame) -> np.ndarray:
            """Reindexea el DataFrame pivotado al close_index y tickers del engine."""
            aligned = (
                sig_df
                .reindex(index=close_index, columns=tickers, method="ffill")
                .fillna(0.5)
                .astype(np.float32)
            )
            return aligned.values

        # --- Componente RS 60d (rs_composite ya está en percentil 0-100) ---
        if "rs_composite" in signals:
            rs_60_arr = _align_signal(signals["rs_composite"])
            rs_60_norm = rs_60_arr / 100.0  # normalizar a 0-1
        else:
            rs_60_norm = np.full(target_shape, 0.5, dtype=np.float32)

        # --- Componente RS corto (rts_pct, percentil 0-100) ---
        if "rts_pct" in signals:
            rs_short_arr = _align_signal(signals["rts_pct"])
            rs_short_norm = rs_short_arr / 100.0
        else:
            rs_short_norm = rs_60_norm.copy()

        # --- RS combinado: mismo esquema que el original ---
        score_rs = (1.0 - rs_short_weight) * rs_60_norm + rs_short_weight * rs_short_norm

        # --- Componente proximidad 52wk ---
        if close_df is not None:
            try:
                max_52wk = close_df.rolling(window=252, min_periods=50).max()
                proximity_52wk = (
                    (close_df / max_52wk.replace(0, np.nan))
                    .clip(0.0, 1.0)
                    .reindex(columns=tickers)
                    .values
                    .astype(np.float32)
                )
                proximity_52wk = np.nan_to_num(proximity_52wk, nan=0.5)
            except Exception:
                proximity_52wk = np.full(target_shape, 0.5, dtype=np.float32)
        else:
            proximity_52wk = np.full(target_shape, 0.5, dtype=np.float32)

        # --- Score final ponderado ---
        total_w = rs_weight + proximity_weight
        rs_w = rs_weight / total_w
        prox_w = proximity_weight / total_w

        entry_score = rs_w * score_rs + prox_w * proximity_52wk
        entry_score = np.clip(entry_score, 0.0, 1.0).astype(np.float32)
        entry_score = np.nan_to_num(entry_score, nan=0.5)

        # Sanity check shape
        if entry_score.shape != target_shape:
            padded = np.full(target_shape, 0.5, dtype=np.float32)
            r = min(entry_score.shape[0], n_rows)
            c = min(entry_score.shape[1], n_cols)
            padded[:r, :c] = entry_score[:r, :c]
            entry_score = padded

        logger.info(
            f"   [OK] entry_score (from DB): mean={entry_score.mean():.3f}, "
            f"std={entry_score.std():.3f} | shape={entry_score.shape}"
        )
        return entry_score

    except Exception as e:
        logger.error(f"[FAIL] build_entry_score_from_signals failed: {e}")
        return None


# ============================================================================
# HELPER: obtener trend_score y pivot_dist como arrays listos para Numba
# ============================================================================

def get_signal_array(
    signals: Dict[str, pd.DataFrame],
    signal_name: str,
    close_index: pd.DatetimeIndex,
    tickers: list,
    default_value: float = 0.5,
    normalize_100: bool = False,
) -> np.ndarray:
    """
    Extrae un array float32 alineado al engine para un signal específico.
    Útil para pasar trend_score_raw o pivot_dist_pct al núcleo Numba.

    Args:
        signals:        Dict de signals pre-cargados
        signal_name:    Nombre de la columna ('trend_score_raw', 'pivot_dist_pct', etc.)
        close_index:    DatetimeIndex del engine
        tickers:        Tickers del engine
        default_value:  Valor de relleno si el signal no existe
        normalize_100:  Si True, divide por 100 (para percentiles 0-100 -> 0-1)

    Returns:
        np.ndarray float32 (n_dates × n_tickers)
    """
    n_rows = len(close_index)
    n_cols = len(tickers)

    if signal_name not in signals:
        logger.debug(f"signal_engine: '{signal_name}' not in signals, using default={default_value}")
        return np.full((n_rows, n_cols), default_value, dtype=np.float32)

    try:
        aligned = (
            signals[signal_name]
            .reindex(index=close_index, columns=tickers, method="ffill")
            .fillna(default_value)
            .astype(np.float32)
        )
        arr = aligned.values
        if normalize_100:
            arr = arr / 100.0
        return arr
    except Exception as e:
        logger.warning(f"signal_engine: Could not align '{signal_name}': {e}")
        return np.full((n_rows, n_cols), default_value, dtype=np.float32)


# ============================================================================
# INTERFACE WITH ENGINE (A+B UNIFICATION)
# ============================================================================

def inject_precomputed_signals(engine):
    """
    Función de entrada principal llamada por AdvancedVectorBTEngine.load_data().
    Realiza el proceso completo de carga e inyección de señales pre-calculadas.
    """
    # 1. Cargar señales de la DB
    signals = load_precomputed_signals(
        tickers=list(engine.close.columns),
        start_date=engine.close.index.min().strftime('%Y-%m-%d'),
        end_date=engine.close.index.max().strftime('%Y-%m-%d')
    )
    
    if not signals:
        return

    # 2. Construir Entry Score unificado (Sistema A+B)
    entry_score = build_entry_score_from_signals(
        signals=signals,
        close_index=engine.close.index,
        tickers=list(engine.close.columns),
        rs_weight=getattr(engine, "score_rs_weight", 0.70),
        proximity_weight=getattr(engine, "score_proximity_weight", 0.30),
        rs_short_weight=getattr(engine, "rs_short_weight", 0.35),
        close_df=engine.close
    )
    
    if entry_score is not None:
        # 3. Inyectar en el hook del motor
        engine._entry_score_precomputed = entry_score
        
        # Guardar señales crudas por si el motor necesita trend_score o dist_pivot
        # en el futuro para filtros adaptativos
        engine._precomputed_signals = signals
        
        logger.info("[ROCKET] [A+B] Señales inyectadas con éxito desde daily_triad_rankings.")
    else:
        logger.warning("[WARN] [A+B] No se pudo construir el entry_score a partir de las señales.")
