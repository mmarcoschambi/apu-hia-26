"""Tests para calculate_atr_percentile de src/indicators/atr.py.

Ciclo TDD (RED -> GREEN) para el helper de percentil movil de volatilidad.
Escenarios cubiertos:
  1. Valores conocidos calculados a mano (period=1, window=5).
  2. Parámetros por defecto: normalización [0, 100], warmup de NaNs, sin excepciones.
  3. Precios constantes: True Range = 0 -> percentil 100.0 (comportamiento de empates).
"""

import numpy as np
import pandas as pd
import pytest

from src.indicators.atr import calculate_atr_percentile

# OHLC diseñado para que TR (period=1) sea estrictamente [2, 3, 4, 5, 6, 7, 8, 2, 9]:
# el gap entre cierre previo y máximo actual domina al rango intrabarra.
HIGH = [102.0, 104.0, 107.5, 112.0, 117.5, 124.0, 131.5, 133.0, 141.5]
LOW = [100.0, 103.0, 106.5, 111.0, 116.5, 123.0, 130.5, 132.0, 140.5]
CLOSE = [101.0, 103.5, 107.0, 111.5, 117.0, 123.5, 131.0, 132.5, 141.0]


def test_calculate_atr_percentile_known_values():
    """Percentil calculable a mano: [100, 100, 100, 20, 100] tras warmup de 4 NaNs."""
    high = pd.Series(HIGH)
    low = pd.Series(LOW)
    close = pd.Series(CLOSE)

    result = calculate_atr_percentile(high, low, close, period=1, window=5)

    expected = [np.nan, np.nan, np.nan, np.nan, 100.0, 100.0, 100.0, 20.0, 100.0]
    pd.testing.assert_series_equal(result, pd.Series(expected), check_names=False)


def test_calculate_atr_percentile_default_params_normalized_0_100():
    """Con defaults (period=14, window=100) devuelve Serie en [0, 100] con warmup NaN."""
    n = 300
    rng = np.random.default_rng(42)
    close = pd.Series(100 + np.cumsum(rng.normal(0.01, 0.5, n)))
    high = close + np.abs(rng.normal(0.5, 0.3, n))
    low = close - np.abs(rng.normal(0.5, 0.3, n))

    result = calculate_atr_percentile(high, low, close)

    assert isinstance(result, pd.Series)
    # Warmup: ATR requiere `period` valores y el percentil `window` -> 112 NaNs iniciales
    assert result.iloc[:112].isna().all()
    assert result.index.equals(close.index)
    # Zona válida: valores normalizados en [0, 100] y con variación real (no constante)
    valid = result.iloc[112:]
    assert valid.notna().all()
    assert valid.between(0.0, 100.0).all()
    assert valid.nunique() > 1


def test_calculate_atr_percentile_constant_prices_ties():
    """Precios constantes -> TR = 0 -> percentil 100.0 en toda la zona válida."""
    n = 30
    high = pd.Series([100.0] * n)
    low = pd.Series([100.0] * n)
    close = pd.Series([100.0] * n)

    result = calculate_atr_percentile(high, low, close, period=2, window=3)

    # ATR NaN en idx 0; percentil necesita 3 valores de ATR -> NaNs hasta idx 2
    assert result.iloc[:3].isna().all()
    assert result.iloc[3:].eq(100.0).all()


def test_calculate_atr_percentile_no_exception_on_warmup():
    """El warmup con NaNs no debe lanzar excepciones (escenario minimo)."""
    high = pd.Series([1.0, 2.0, 3.0])
    low = pd.Series([0.5, 1.5, 2.5])
    close = pd.Series([0.75, 1.75, 2.75])

    result = calculate_atr_percentile(high, low, close)

    assert result.isna().all()  # Serie muy corta: solo warmup, sin excepciones
    assert len(result) == 3


if __name__ == "__main__":
    pytest.main([__file__])
