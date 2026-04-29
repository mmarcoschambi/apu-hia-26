"""
src/analytics/market_score_engine.py
=====================================
Motor de market score real basado en datos de mercado.

Calcula un score 0-100 basado en:
- SPY posición relativa a MA50/MA200
- VIX nivel absoluto y percentil 20d
- SPY momentum 20d
- Amplitud de mercado (proxy via VIX si no hay datos)

API principal:
    compute_market_score(spy_data, vix_data) -> float
"""

import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import numpy as np
import pandas as pd
import yfinance as yf

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DB_PATH = PROJECT_ROOT / "data" / "ticker_cache.db"


def _fetch_spy_data(days: int = 90) -> Optional[pd.DataFrame]:
    """Descarga datos de SPY desde yfinance."""
    try:
        df = yf.download(
            "SPY", period=f"{days}d", auto_adjust=True, progress=False, timeout=10
        )
        if df is None or df.empty:
            return None
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        return df
    except Exception as e:
        logger.warning(f"Could not fetch SPY data: {e}")
        return None


def _fetch_vix_data(days: int = 30) -> Optional[pd.DataFrame]:
    """Descarga datos de VIX desde yfinance con fallback a VIXY."""
    for ticker in ["^VIX", "VIXY"]:
        try:
            df = yf.download(
                ticker, period=f"{days}d", auto_adjust=True, progress=False, timeout=10
            )
            if df is not None and not df.empty:
                if isinstance(df.columns, pd.MultiIndex):
                    df.columns = df.columns.get_level_values(0)
                return df
        except Exception:
            continue
    return None


def _calculate_ma_position(
    close: pd.Series, ma_short: int = 50, ma_long: int = 200
) -> float:
    """
    Calcula posición de price relativa a medias móviles.
    Returns: score 0-100 basado en distancia a MAs.
    """
    if len(close) < ma_long:
        if len(close) < ma_short:
            return 50.0  # neutral
        ma50 = close.rolling(ma_short).mean()
        score = (close.iloc[-1] - ma50.iloc[-1]) / ma50.iloc[-1] * 100
        return max(0, min(100, 50 + score * 5))

    ma50 = close.rolling(ma_short).mean()
    ma200 = close.rolling(ma_long).mean()

    # Price vs MA50
    price_vs_ma50 = (close.iloc[-1] - ma50.iloc[-1]) / ma50.iloc[-1]
    # Price vs MA200
    price_vs_ma200 = (close.iloc[-1] - ma200.iloc[-1]) / ma200.iloc[-1]
    # MA50 vs MA200 (trend)
    ma50_vs_ma200 = (ma50.iloc[-1] - ma200.iloc[-1]) / ma200.iloc[-1]

    # Composite score
    score = (
        30 * max(0, min(1, 0.5 + price_vs_ma50 * 5))  # 30% price vs MA50
        + 40 * max(0, min(1, 0.5 + price_vs_ma200 * 3))  # 40% price vs MA200
        + 30 * max(0, min(1, 0.5 + ma50_vs_ma200 * 3))  # 30% trend
    )

    return score * 100 / 30


def _calculate_vix_score(vix_close: pd.Series, lookback: int = 20) -> float:
    """
    Calcula score basado en VIX absoluto y percentil.
    Returns: 0-100 (menor VIX = mayor score)
    """
    if len(vix_close) < 5:
        return 50.0

    current_vix = vix_close.iloc[-1]

    # Percentil actual
    recent = vix_close.tail(lookback)
    if len(recent) > 1:
        percentile = (recent < current_vix).mean()
    else:
        percentile = 0.5

    # Score: VIX bajo = favorable (high score), VIX alto = unfavorable
    # Scale: VIX 10 -> 90, VIX 40 -> 10
    if current_vix <= 10:
        vix_score = 90
    elif current_vix >= 40:
        vix_score = 10
    else:
        vix_score = 90 - (current_vix - 10) * 80 / 30

    # Weight by confidence (percentile)
    confidence = min(1.0, len(recent) / lookback)
    weighted_score = vix_score * confidence + 50 * (1 - confidence)

    return weighted_score


def _calculate_momentum(close: pd.Series, days: int = 20) -> float:
    """Calcula momentum 20d de SPY. Returns 0-100."""
    if len(close) < days:
        return 50.0

    ret = (close.iloc[-1] - close.iloc[-days]) / close.iloc[-days]

    # Scale: +10% -> 90, -10% -> 10
    score = max(0, min(100, 50 + ret * 500))
    return score


def _estimate_amplitude(vix_score: float) -> float:
    """
    Estima amplitud de mercado basada en VIX.
    VIX bajo = alta amplitud (más stocks en tendencia).
    VIX alto = baja amplitud.
    """
    return vix_score  # Proxy: VIX score representa amplitud inversa


def compute_market_score(
    spy_data: Optional[pd.DataFrame] = None,
    vix_data: Optional[pd.DataFrame] = None,
    days: int = 90,
) -> Tuple[float, Dict[str, Any]]:
    """
    Calcula market score 0-100 basado en datos reales.

    Args:
        spy_data: DataFrame de SPY (opcional, se descarga si no se provee)
        vix_data: DataFrame de VIX (opcional, se descarga si no se provee)
        days: Días de historia a usar (default 90)

    Returns:
        (score, metadata) donde metadata incluye componentes y quality flags
    """
    metadata = {
        "components": {},
        "quality_flags": [],
        "data_sources": {},
    }

    # Fetch data if not provided
    if spy_data is None:
        spy_data = _fetch_spy_data(days)
        metadata["data_sources"]["spy"] = (
            "yfinance" if spy_data is not None else "missing"
        )
    else:
        metadata["data_sources"]["spy"] = "provided"

    if vix_data is None:
        vix_data = _fetch_vix_data(30)
        metadata["data_sources"]["vix"] = (
            "yfinance" if vix_data is not None else "missing"
        )
    else:
        metadata["data_sources"]["vix"] = "provided"

    # Default fallback
    if spy_data is None:
        metadata["quality_flags"].append("SPY_DATA_MISSING")
        return 50.0, metadata

    # Extract close series
    if "Close" in spy_data.columns:
        spy_close = spy_data["Close"]
    elif "close" in spy_data.columns:
        spy_close = spy_data["close"]
    else:
        metadata["quality_flags"].append("SPY_CLOSE_MISSING")
        return 50.0, metadata

    # Calculate components
    ma_score = _calculate_ma_position(spy_close)
    metadata["components"]["ma_position"] = round(ma_score, 1)

    momentum = _calculate_momentum(spy_close)
    metadata["components"]["momentum_20d"] = round(momentum, 1)

    if vix_data is not None and "Close" in vix_data.columns:
        vix_close = vix_data["Close"]
        vix_score = _calculate_vix_score(vix_close)
        metadata["components"]["vix_score"] = round(vix_score, 1)
        metadata["components"]["vix_current"] = round(vix_close.iloc[-1], 2)
    elif vix_data is not None and "close" in vix_data.columns:
        vix_close = vix_data["close"]
        vix_score = _calculate_vix_score(vix_close)
        metadata["components"]["vix_score"] = round(vix_score, 1)
        metadata["components"]["vix_current"] = round(vix_close.iloc[-1], 2)
    else:
        vix_score = 50.0
        metadata["quality_flags"].append("VIX_DATA_MISSING")
        metadata["components"]["vix_score"] = 50.0

    amplitude = _estimate_amplitude(vix_score)
    metadata["components"]["amplitude_proxy"] = round(amplitude, 1)

    # Composite score: weighted average
    # MA position: 35%, Momentum: 25%, VIX: 30%, Amplitude: 10%
    final_score = (
        0.35 * ma_score + 0.25 * momentum + 0.30 * vix_score + 0.10 * amplitude
    )

    final_score = max(0, min(100, final_score))

    # Add quality flags
    if len(spy_close) < 50:
        metadata["quality_flags"].append("SPY_INSUFFICIENT_HISTORY")
    if metadata["quality_flags"]:
        metadata["quality_flags"].append("MARKET_SCORE_FALLBACK")

    return round(final_score, 1), metadata


def get_live_market_score() -> Tuple[float, Dict[str, Any]]:
    """
    Convenience function: calcula market score con datos frescos de yfinance.
    """
    return compute_market_score(days=90)


# === CLI TEST ===

if __name__ == "__main__":
    print("Testing market_score_engine...")

    score, meta = get_live_market_score()
    print(f"Market Score: {score}")
    print(f"Components: {meta['components']}")
    print(f"Quality flags: {meta['quality_flags']}")
    print(f"Data sources: {meta['data_sources']}")
