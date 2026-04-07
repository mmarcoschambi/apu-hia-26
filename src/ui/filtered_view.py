"""
filtered_view.py — Fase 3
==========================
Función pura centralizada de filtrado.

TODAS las visualizaciones del dashboard deben consumir get_filtered_trades()
en lugar de usar grouped_trades directamente. Esto garantiza:
  - Métricas coherentes con el scope activo (activo/patrón)
  - Sin mezcla de activos en gráficos
  - KPIs que siempre muestran un badge del scope activo

Uso:
    from src.ui.filtered_view import get_filtered_trades, get_scope_label

    view = get_filtered_trades(trades_df, selected_asset, selected_pattern)
    label = get_scope_label(selected_asset, selected_pattern)
"""

from __future__ import annotations

import logging
from typing import Optional, Tuple

import pandas as pd

logger = logging.getLogger(__name__)

ALL_LABEL = "ALL"


def get_filtered_trades(
    trades_df: pd.DataFrame,
    asset: str = ALL_LABEL,
    pattern: str = ALL_LABEL,
) -> pd.DataFrame:
    """
    Función pura de filtrado. Todas las visualizaciones del dashboard
    deben llamar a esta función en lugar de usar el DataFrame global.

    Args:
        trades_df: DataFrame canónico de trades (output de DashboardDataAdapter)
        asset: Activo a filtrar, e.g. "AAPL". "ALL" = no filtrar por activo.
        pattern: Patrón a filtrar, e.g. "vcp". "ALL" = no filtrar por patrón.

    Returns:
        DataFrame filtrado, nunca None. Puede ser vacío si no hay datos.
    """
    if trades_df is None or trades_df.empty:
        return pd.DataFrame()

    result = trades_df.copy()

    # Filtro por activo
    if asset and asset != ALL_LABEL:
        if "symbol" in result.columns:
            result = result[result["symbol"] == asset]
        else:
            logger.warning("[FilteredView] Columna 'symbol' no encontrada en DataFrame")

    # Filtro por patrón
    if pattern and pattern != ALL_LABEL:
        pattern_lower = pattern.lower()
        if "signal_type" in result.columns:
            result = result[result["signal_type"].str.lower() == pattern_lower]
        elif "pattern_type" in result.columns:
            result = result[result["pattern_type"].str.lower() == pattern_lower]
        else:
            logger.warning("[FilteredView] Columna 'signal_type' no encontrada en DataFrame")

    if result.empty:
        logger.debug(
            f"[FilteredView] 0 trades para asset='{asset}', pattern='{pattern}'"
        )

    return result


def get_scope_label(
    asset: str = ALL_LABEL,
    pattern: str = ALL_LABEL,
    short: bool = False,
) -> str:
    """
    Genera label del scope activo para mostrar en KPIs y badges.

    Args:
        asset: Activo seleccionado.
        pattern: Patrón seleccionado.
        short: Si True, devuelve label corto sin emoji.

    Returns:
        str, e.g. "🌐 Global", "🏦 AAPL", "🔍 AAPL · VCP"
    """
    if asset == ALL_LABEL:
        return "Global" if short else "🌐 Global"
    if pattern == ALL_LABEL:
        return asset if short else f"🏦 {asset}"
    return f"{asset} · {pattern}" if short else f"🔍 {asset} · {pattern}"


def get_scope_info(
    trades_df: pd.DataFrame,
    asset: str = ALL_LABEL,
    pattern: str = ALL_LABEL,
) -> Tuple[pd.DataFrame, str, int]:
    """
    Atajo conveniente: filtra y devuelve (df, label, n_trades).

    Args:
        trades_df: DataFrame canónico.
        asset: Activo seleccionado.
        pattern: Patrón seleccionado.

    Returns:
        Tuple (filtered_df, scope_label, n_trades)
    """
    filtered = get_filtered_trades(trades_df, asset, pattern)
    label = get_scope_label(asset, pattern)
    return filtered, label, len(filtered)


def assert_consistent_scope(
    df: pd.DataFrame,
    asset: str,
    pattern: str,
) -> bool:
    """
    Verifica que el DataFrame no mezcle activos/patrones fuera del scope.
    Útil para QA y tests.

    Returns:
        True si el scope es consistente, False si hay mezcla.
    """
    if df.empty:
        return True

    if asset != ALL_LABEL and "symbol" in df.columns:
        if df["symbol"].nunique() > 1:
            logger.error(
                f"[FilteredView] SCOPE INCONSISTENTE: "
                f"asset='{asset}' pero el DataFrame tiene {df['symbol'].nunique()} activos: "
                f"{df['symbol'].unique()[:5].tolist()}"
            )
            return False

    if pattern != ALL_LABEL and "signal_type" in df.columns:
        actual_patterns = df["signal_type"].str.lower().unique()
        if len(actual_patterns) > 1 or (
            len(actual_patterns) == 1 and actual_patterns[0] != pattern.lower()
        ):
            logger.error(
                f"[FilteredView] SCOPE INCONSISTENTE: "
                f"pattern='{pattern}' pero el DataFrame tiene patrones: {actual_patterns.tolist()}"
            )
            return False

    return True
