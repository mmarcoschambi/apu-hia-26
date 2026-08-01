"""
tests/test_baseline_calmar_fix.py
==================================

Regresión de la corrección BASELINE-CALMAR.

Contexto:
    El modo BASELINE del motor AdvancedVectorBTEngine (todos los filtros
    avanzados OFF) omitía las claves ``annualized_return``, ``mar_ratio``
    y ``calmar_ratio`` en el dict de resultados de ``run_backtest()``.
    El pipeline S4 leía ``calmar_ratio`` como 0.0 fantasma, silenciando
    la evaluación GATE_CALMAR y el bonus Calmar/CAGR del score compuesto.

    El fix (autorizado) replica el cálculo de ADVANCED mode en el bloque
    BASELINE, justo después de ``max_dd``.

Tests:
    1. BASELINE mode: ``run_backtest()`` devuelve un dict que CONTIENE las
       claves ``calmar_ratio``, ``annualized_return`` y ``mar_ratio``.
    2. BASELINE mode: con historia y trades suficientes, ``calmar_ratio``
       es ``annualized_return / abs(max_dd)`` (fórmula exacta del motor),
       finito y distinto de cero (no fantasma).
    3. Regresión: ADVANCED mode (un filtro activo) sigue devolviendo las
       mismas claves — comportamiento sin cambios.

Ejecutar:
    python -m pytest tests/test_baseline_calmar_fix.py -v
"""

import unittest

import numpy as np
import pandas as pd

from src.backtest.vectorbt_engine_advanced import AdvancedVectorBTEngine

# ──────────────────────────────────────────────
# Synthetic data + engine builders (sin red, sin cache)
# ──────────────────────────────────────────────


def _build_ohlcv(n_days: int = 504, seed: int = 42) -> pd.DataFrame:
    """Genera una serie OHLCV sintética con tendencia y retrocesos.

    El caminata aleatoria con componente senoidal de pullback produce
    trades reales y una curva de equity con drawdowns y ganancias, lo que
    permite verificar un calmar_ratio no-fantasma.
    """
    np.random.seed(seed)
    tickers = ["AAPL", "MSFT", "GOOGL"]
    dates = pd.date_range("2023-01-03", periods=n_days, freq="B")

    steps = np.random.normal(0.003, 0.02, (n_days, len(tickers))).astype(np.float32)
    pullbacks = (-0.008 * np.sin(np.linspace(0, 10 * np.pi, n_days)))[:, None].astype(
        np.float32
    )
    log_price = np.cumsum(steps + pullbacks, axis=0) + np.log(100.0)
    close = pd.DataFrame(np.exp(log_price), index=dates, columns=tickers)
    high = (close * 1.012).astype(np.float32)
    low = (close * 0.988).astype(np.float32)
    volume = pd.DataFrame(
        np.random.uniform(1e6, 1e7, (n_days, len(tickers))).astype(np.float32),
        index=dates,
        columns=tickers,
    )

    return {
        "close": close,
        "high": high,
        "low": low,
        "volume": volume,
        "dates": dates,
        "tickers": tickers,
    }


def _inject_engine_data(engine: AdvancedVectorBTEngine, data: dict) -> None:
    """Inyecta DataFrames sintéticos directamente (salta cache/DB)."""
    close = data["close"]
    high = data["high"]
    low = data["low"]
    volume = data["volume"]
    dates = data["dates"]
    tickers = data["tickers"]

    engine.close = close
    engine.high = high
    engine.low = low
    engine.open = (close * 0.998).astype(np.float32)
    engine.volume = volume

    avg_vol_20 = volume.rolling(20, min_periods=1).mean().fillna(1).astype(np.float32)
    engine.sma_20 = close.rolling(20, min_periods=1).mean().astype(np.float32)
    engine.sma_50 = close.rolling(50, min_periods=1).mean().astype(np.float32)
    engine.avg_volume_20 = avg_vol_20
    engine.rvol = (volume / avg_vol_20).fillna(1.0).astype(np.float32)
    engine.adr_pct = (
        ((high - low) / low * 100).rolling(20, min_periods=1).mean().fillna(0).astype(np.float32)
    )
    engine.ema_8 = close.ewm(span=8, adjust=False, min_periods=1).mean().astype(np.float32)
    engine.ema_10 = close.ewm(span=10, adjust=False, min_periods=1).mean().astype(np.float32)
    engine.ema_21 = close.ewm(span=21, adjust=False, min_periods=1).mean().astype(np.float32)
    engine.spy_close = pd.Series(np.full(len(dates), 450.0, dtype=np.float32), index=dates)
    engine.vix_close = pd.Series(np.full(len(dates), 15.0, dtype=np.float32), index=dates)
    engine.spy_sma50 = pd.Series(np.full(len(dates), 440.0, dtype=np.float32), index=dates)
    engine.adr_pct_14 = None
    engine.atr_ratio_matrix = None
    engine.trend_aligned = pd.DataFrame(0, index=dates, columns=tickers).astype(np.float32)

    high_20 = high.rolling(20, min_periods=1).max()
    low_20 = low.rolling(20, min_periods=1).min()
    engine.consolidation_range = ((high_20 - low_20) / low_20 * 100).fillna(0).astype(np.float32)
    sma_20_for_bb = close.rolling(20, min_periods=1).mean().fillna(0)
    bb_std = close.rolling(20).std().fillna(0)
    bb_upper = sma_20_for_bb + (bb_std * 2)
    bb_lower = sma_20_for_bb - (bb_std * 2)
    inside_bb = (close >= bb_lower) & (close <= bb_upper)
    engine.consolidation_days = (
        inside_bb.rolling(20, min_periods=1).sum().fillna(0).astype(np.float32)
    )
    engine.high_20 = high_20.astype(np.float32)
    engine.low_20 = low_20.astype(np.float32)
    engine.dist_sma20_pct = ((close - engine.sma_20) / engine.sma_20 * 100).fillna(0).astype(
        np.float32
    )
    engine.dollar_volume = (close * avg_vol_20).fillna(0).astype(np.float32)


def _build_engine(advanced: bool = False) -> AdvancedVectorBTEngine:
    """Construye el motor con datos sintéticos.

    Args:
        advanced: Si True, activa un filtro avanzado (require_spy_above_sma50)
            para forzar ADVANCED mode. Si False, todos los filtros OFF ->
            BASELINE mode.
    """
    data = _build_ohlcv()
    engine = AdvancedVectorBTEngine(
        universe=data["tickers"],
        start_date="2023-01-03",
        end_date="2024-12-31",
        initial_capital=100_000,
        mode="production",
        offline_mode=True,
        use_pit_universe=False,
        use_market_regime_filter=False,
        require_spy_above_sma50=advanced,
        use_dynamic_thresholds=False,
        use_adaptive_filtering=False,
        require_positive_rs=False,
        use_rs_percentile=False,
        use_sma50_atr_filter=False,
        use_pattern_filter=False,
        use_earnings_calendar=False,
        signal_type="breakout",
        min_rvol=0.5,
        min_adr=1.0,
        max_dist_sma20=20.0,
        min_consolidation_days=3,
        max_consolidation_range=15.0,
    )
    _inject_engine_data(engine, data)
    return engine


def _compute_engine_formula(equity_curve: pd.Series, initial_capital: float) -> dict:
    """Replica la fórmula exacta del motor para annualized/mar/calmar."""
    if len(equity_curve) == 0:
        return {"annualized_return": 0, "mar_ratio": 0, "calmar_ratio": 0, "max_dd": 0}

    total_return = (equity_curve.iloc[-1] - initial_capital) / initial_capital
    cum_max = equity_curve.cummax()
    drawdown = (equity_curve - cum_max) / cum_max
    max_dd = drawdown.min()

    days_trading = len(equity_curve)
    years_trading = days_trading / 252
    annualized_return = (
        (equity_curve.dropna().iloc[-1] / initial_capital) ** (1 / years_trading) - 1
        if years_trading > 0 and total_return > -1 and not equity_curve.dropna().empty
        else 0
    )
    mar_ratio = annualized_return / abs(max_dd) if max_dd < 0 and max_dd != -1 else 0
    calmar_ratio = annualized_return / abs(max_dd) if max_dd < 0 and max_dd != -1 else 0

    return {
        "annualized_return": annualized_return,
        "mar_ratio": mar_ratio,
        "calmar_ratio": calmar_ratio,
        "max_dd": max_dd,
    }


# ──────────────────────────────────────────────
# Tests
# ──────────────────────────────────────────────


class TestBaselineCalmarFix(unittest.TestCase):
    """Valida que BASELINE mode reporte métricas Calmar reales."""

    def test_baseline_mode_returns_calmar_keys(self):
        """run_backtest() en BASELINE mode incluye calmar/annualized/mar."""
        engine = _build_engine(advanced=False)
        results = engine.run_backtest()

        self.assertIsInstance(results, dict)
        for key in ("calmar_ratio", "annualized_return", "mar_ratio"):
            self.assertIn(key, results, f"Falta la clave '{key}' en el dict de BASELINE")

    def test_baseline_calmar_matches_engine_formula(self):
        """calmar_ratio = annualized_return / abs(max_dd) y no es fantasma."""
        engine = _build_engine(advanced=False)
        results = engine.run_backtest()

        self.assertGreaterEqual(
            results.get("total_trades", 0), 5, "El fixture debe generar trades reales"
        )
        equity_curve = results["equity_curve"]
        expected = _compute_engine_formula(equity_curve, engine.initial_capital)

        self.assertTrue(np.isfinite(results["calmar_ratio"]))
        self.assertNotEqual(results["calmar_ratio"], 0.0, "calmar_ratio NO debe ser 0.0 fantasma")
        self.assertAlmostEqual(
            results["annualized_return"],
            expected["annualized_return"],
            places=6,
        )
        self.assertAlmostEqual(
            results["max_drawdown"],
            expected["max_dd"],
            places=6,
        )
        self.assertAlmostEqual(
            results["calmar_ratio"],
            expected["calmar_ratio"],
            places=6,
        )
        self.assertAlmostEqual(
            results["mar_ratio"],
            expected["mar_ratio"],
            places=6,
        )

    def test_advanced_mode_still_returns_calmar_keys(self):
        """Regresión: ADVANCED mode conserva las mismas claves sin cambios."""
        engine = _build_engine(advanced=True)
        results = engine.run_backtest()

        self.assertIsInstance(results, dict)
        for key in ("calmar_ratio", "annualized_return", "mar_ratio"):
            self.assertIn(key, results, f"Falta la clave '{key}' en el dict de ADVANCED")
        self.assertTrue(np.isfinite(results["calmar_ratio"]))


if __name__ == "__main__":
    unittest.main()
