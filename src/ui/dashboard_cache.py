"""
dashboard_cache.py — Fase 4
============================
Caché de dos niveles para el dashboard:

  Nivel 1: Lectura de archivo (key = path + mtime + size)
           Evita releer el archivo si no cambió en disco.

  Nivel 2: Normalización/flatten (key = hash del payload + parámetros de filtro)
           Evita recomputar agrupaciones caras en cada rerun de Streamlit.

Tiempos objetivo:
  - Cambio de filtro UI -> <300ms en payload típico
  - Recarga completa -> significativamente menor que sin caché

Uso:
    from src.ui.dashboard_cache import DashboardCache

    cache = DashboardCache()

    # Cargar config JSON con caché de archivo
    config = cache.get_optimizer_config("outputs/3tier_optimization/FINAL_CONFIG.json")

    # Cargar trades CSV con caché de archivo
    trades = cache.get_trades("outputs/backtests/complete_trades_clean.csv")

    # Vista filtrada con caché de computo
    view = cache.get_filtered_view(trades, asset="AAPL", pattern="vcp")
"""

from __future__ import annotations

import hashlib
import logging
import os
import time
from typing import Any, Dict, Optional, Tuple

import pandas as pd
import streamlit as st

from src.ui.dashboard_data_adapter import DashboardDataAdapter
from src.ui.filtered_view import get_filtered_trades

logger = logging.getLogger(__name__)


def _file_cache_key(path: str) -> Optional[str]:
    """Genera key de caché basada en path + mtime + size del archivo."""
    try:
        stat = os.stat(path)
        return f"{path}|{stat.st_mtime}|{stat.st_size}"
    except OSError:
        return None


def _df_hash(df: pd.DataFrame, extra: str = "") -> str:
    """Hash rápido de un DataFrame para cachear resultados de computo."""
    try:
        h = hashlib.md5(
            (str(df.shape) + str(df.columns.tolist()) + extra).encode()
        ).hexdigest()
        return h
    except Exception:
        return str(time.time())


class DashboardCache:
    """
    Caché de dos niveles para el dashboard.
    Se puede usar standalone o a través de las funciones @st.cache_data de Streamlit.
    """

    def __init__(self) -> None:
        self._adapter = DashboardDataAdapter()
        # Nivel 1: caché de archivos en memoria de la sesión
        # key: cache_key_string -> value: data
        self._file_cache: Dict[str, Any] = {}
        # Nivel 2: caché de computo filtrado
        # key: (df_hash, asset, pattern) -> filtered_df
        self._compute_cache: Dict[Tuple, pd.DataFrame] = {}
        self._timings: Dict[str, float] = {}

    # --------------------------------------------------------------------------
    # Nivel 1 — caché de archivo
    # --------------------------------------------------------------------------

    def get_optimizer_config(self, path: str) -> Dict[str, Any]:
        """
        Carga config del optimizer con caché de archivo (mtime + size).
        Si el archivo no cambió, devuelve la versión en memoria.
        """
        key = _file_cache_key(path)
        if key and key in self._file_cache:
            logger.debug(f"[Cache L1 HIT] optimizer config: {path}")
            return self._file_cache[key]

        t0 = time.perf_counter()
        config = self._adapter.load_optimizer_json(path)
        elapsed = time.perf_counter() - t0

        if key:
            self._file_cache[key] = config
        self._timings[f"load_config:{path}"] = elapsed
        logger.debug(f"[Cache L1 MISS] optimizer config: {path} ({elapsed*1000:.1f}ms)")
        return config

    def get_trades(self, path: str) -> pd.DataFrame:
        """
        Carga trades CSV con caché de archivo (mtime + size).
        Si el archivo no cambió, devuelve el DataFrame en memoria.
        """
        key = _file_cache_key(path)
        if key and key in self._file_cache:
            logger.debug(f"[Cache L1 HIT] trades CSV: {path}")
            return self._file_cache[key]

        t0 = time.perf_counter()
        df = self._adapter.load_trades_csv(path)
        elapsed = time.perf_counter() - t0

        if key:
            self._file_cache[key] = df
        self._timings[f"load_trades:{path}"] = elapsed
        logger.debug(f"[Cache L1 MISS] trades CSV: {path} ({elapsed*1000:.1f}ms), {len(df)} filas")
        return df

    def get_asset_pattern_index(self, trades_df: pd.DataFrame) -> Dict[str, Any]:
        """
        Construye el índice asset->patterns con caché de computo.
        """
        h = _df_hash(trades_df, "index")
        cache_key = ("index", h)
        if cache_key in self._compute_cache:
            logger.debug("[Cache L2 HIT] asset_pattern_index")
            return self._compute_cache[cache_key]

        t0 = time.perf_counter()
        index = self._adapter.build_asset_pattern_index(trades_df)
        elapsed = time.perf_counter() - t0

        self._compute_cache[cache_key] = index
        self._timings["build_index"] = elapsed
        logger.debug(f"[Cache L2 MISS] asset_pattern_index ({elapsed*1000:.1f}ms)")
        return index

    # --------------------------------------------------------------------------
    # Nivel 2 — caché de computo filtrado
    # --------------------------------------------------------------------------

    def get_filtered_view(
        self,
        trades_df: pd.DataFrame,
        asset: str = "ALL",
        pattern: str = "ALL",
    ) -> pd.DataFrame:
        """
        Devuelve la vista filtrada con caché de computo.
        Evita refiltrar en cada rerun si el DataFrame y los parámetros no cambiaron.
        """
        h = _df_hash(trades_df)
        cache_key = ("filter", h, asset, pattern)

        if cache_key in self._compute_cache:
            logger.debug(f"[Cache L2 HIT] filtered_view asset={asset} pattern={pattern}")
            return self._compute_cache[cache_key]

        t0 = time.perf_counter()
        filtered = get_filtered_trades(trades_df, asset, pattern)
        elapsed = time.perf_counter() - t0

        self._compute_cache[cache_key] = filtered
        self._timings[f"filter:{asset}:{pattern}"] = elapsed
        logger.debug(
            f"[Cache L2 MISS] filtered_view asset={asset} pattern={pattern} "
            f"({elapsed*1000:.1f}ms) -> {len(filtered)} filas"
        )
        return filtered

    def get_segment_metrics(
        self,
        trades_df: pd.DataFrame,
        group_by_cols: list,
    ) -> pd.DataFrame:
        """
        Calcula métricas por segmento con caché de computo.
        """
        h = _df_hash(trades_df, str(group_by_cols))
        cache_key = ("metrics", h, tuple(group_by_cols))

        if cache_key in self._compute_cache:
            logger.debug(f"[Cache L2 HIT] segment_metrics {group_by_cols}")
            return self._compute_cache[cache_key]

        t0 = time.perf_counter()
        metrics = DashboardDataAdapter.compute_segment_metrics(trades_df, group_by_cols)
        elapsed = time.perf_counter() - t0

        self._compute_cache[cache_key] = metrics
        self._timings[f"metrics:{group_by_cols}"] = elapsed
        logger.debug(f"[Cache L2 MISS] segment_metrics {group_by_cols} ({elapsed*1000:.1f}ms)")
        return metrics

    # --------------------------------------------------------------------------
    # Telemetría
    # --------------------------------------------------------------------------

    def render_timing_sidebar(self) -> None:
        """
        Renderiza métricas de timing en el sidebar de Streamlit.
        Activar con: cache.render_timing_sidebar()
        """
        if not self._timings:
            return

        import streamlit as st
        with st.sidebar.expander("[STOPWATCH] Cache Timings", expanded=False):
            for op, elapsed in sorted(self._timings.items()):
                st.text(f"{op}: {elapsed*1000:.1f}ms")

            # Stats del caché
            l1_size = len(self._file_cache)
            l2_size = len(self._compute_cache)
            st.caption(f"L1 entries: {l1_size} | L2 entries: {l2_size}")

    def get_timing_summary(self) -> Dict[str, float]:
        """Retorna diccionario de timings para uso programático."""
        return dict(self._timings)

    def invalidate(self, path: Optional[str] = None) -> None:
        """
        Invalida caché.
        Si path es None, invalida todo.
        Si path es un string, invalida solo las entradas de ese archivo.
        """
        if path is None:
            self._file_cache.clear()
            self._compute_cache.clear()
            self._timings.clear()
            logger.debug("[Cache] Caché invalidado completamente")
        else:
            keys_to_del = [k for k in self._file_cache if str(path) in k]
            for k in keys_to_del:
                del self._file_cache[k]
            logger.debug(f"[Cache] Invalidadas {len(keys_to_del)} entradas para {path}")


# -----------------------------------------------------------------------------
# Integración con Streamlit cache_data
# Funciones standalone decoradas para uso directo desde app.py
# -----------------------------------------------------------------------------


@st.cache_data(ttl=300, show_spinner=False)
def cached_load_optimizer_config(path: str) -> Dict[str, Any]:
    """
    Versión cacheada por Streamlit del cargador de config.
    TTL=300s: recarga automática cada 5 minutos.
    """
    adapter = DashboardDataAdapter()
    return adapter.load_optimizer_json(path)


@st.cache_data(ttl=300, show_spinner=False)
def cached_load_trades(path: str) -> pd.DataFrame:
    """
    Versión cacheada por Streamlit del cargador de trades CSV.
    TTL=300s: recarga automática cada 5 minutos.
    """
    adapter = DashboardDataAdapter()
    return adapter.load_trades_csv(path)


@st.cache_data(show_spinner=False)
def cached_build_index(trades_json: str) -> Dict[str, Any]:
    """
    Versión cacheada del índice asset->patterns.
    Recibe trades como JSON string (requerido por st.cache_data que no serializa DataFrames).
    """
    import json
    adapter = DashboardDataAdapter()
    try:
        df = pd.read_json(trades_json)
    except Exception:
        return {"ALL": ["any"]}
    return adapter.build_asset_pattern_index(df)


@st.cache_data(show_spinner=False)
def cached_segment_metrics(trades_json: str, group_by: str) -> pd.DataFrame:
    """
    Versión cacheada de las métricas por segmento.
    group_by: string separado por comas, e.g. "symbol,signal_type"
    """
    import json
    try:
        df = pd.read_json(trades_json)
        group_cols = [c.strip() for c in group_by.split(",") if c.strip()]
        return DashboardDataAdapter.compute_segment_metrics(df, group_cols)
    except Exception as e:
        logger.error(f"[Cache] Error en cached_segment_metrics: {e}")
        return pd.DataFrame()
