"""
ATR Module
----------
Calculo de Average True Range (Wilder) y percentiles moviles de volatilidad.
"""

import numpy as np
import pandas as pd


def _wilder_atr(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    period: int,
) -> pd.Series:
    """
    Calcula el Average True Range (ATR) con suavizado de Wilder.

    El True Range es el maximo entre el rango intrabarra y los gaps contra el
    cierre anterior. El ATR aplica una media exponencial con alpha = 1/period
    (suavizado de Wilder) y devuelve NaN durante el warmup inicial.

    Args:
        high: Serie de precios maximos.
        low: Serie de precios minimos.
        close: Serie de precios de cierre.
        period: Ventana del suavizado (default 14).

    Returns:
        Serie con el ATR (NaN en los primeros `period - 1` valores).
    """
    prev_close = close.shift(1)
    true_range = pd.concat(
        [
            high - low,
            (high - prev_close).abs(),
            (low - prev_close).abs(),
        ],
        axis=1,
    ).max(axis=1)
    return true_range.ewm(alpha=1.0 / period, adjust=False, min_periods=period).mean()


def _percentile_rank(window_values: np.ndarray) -> float:
    """
    Percentil del ultimo valor dentro de la ventana, normalizado en [0, 100].

    Args:
        window_values: Ventana deslizante de valores, incluye el valor actual.

    Returns:
        Porcentaje de valores de la ventana menores o iguales al valor actual.
    """
    return float((window_values <= window_values[-1]).mean() * 100.0)


def calculate_atr_percentile(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    period: int = 14,
    window: int = 100,
) -> pd.Series:
    """
    Calcula el percentil movil del ATR, normalizado en [0, 100].

    Convierte la volatilidad del True Range en un ranking relativo: para cada
    barra se compara el ATR actual contra la ventana deslizante previa
    (`window` barras). El resultado indica el percentil de volatilidad
    historica reciente de la barra (0 = minima, 100 = maxima).

    Args:
        high: Serie de precios maximos.
        low: Serie de precios minimos.
        close: Serie de precios de cierre.
        period: Periodo del ATR (suavizado de Wilder, default 14).
        window: Ventana deslizante para el percentil (default 100).

    Returns:
        Serie de pandas con valores en [0, 100]; NaN durante el warmup inicial
        (requiere `period` barras para el ATR y `window` para el percentil).
        No lanza excepciones por datos insuficientes.
    """
    atr = _wilder_atr(high, low, close, period)
    return atr.rolling(window, min_periods=window).apply(
        _percentile_rank, raw=True
    )
