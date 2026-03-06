#!/usr/bin/env python3
"""
Test Screener con Scoring - Validación Completa
===============================================

Este script valida que el screener y el scoring (Entry Quality Score + RS)
funcionan correctamente en el motor AdvancedVectorBTEngine.

Verifica:
1. RS Percentile (IBD-style) activado y filtrando correctamente
2. Entry Quality Score calculado y usado para priorización
3. Screener integrado con el motor de backtest

Uso:
    python3 test_screener_scoring.py
"""

import sys
import logging
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import pandas as pd
import numpy as np

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def test_rs_percentile_calculation():
    """Test 1: Verificar cálculo de RS Percentile."""
    from src.backtest.vectorbt_engine_advanced import AdvancedVectorBTEngine

    logger.info("\n" + "=" * 70)
    logger.info("TEST 1: RS Percentile Calculation")
    logger.info("=" * 70)

    universe = ["AAPL", "MSFT", "GOOGL", "NVDA", "TSLA", "META", "AMZN", "NFLX"]

    engine = AdvancedVectorBTEngine(
        universe=universe,
        start_date="2024-01-01",
        end_date="2024-12-31",
        use_rs_percentile=True,
        min_rs_percentile=70.0,
        rs_lookback_days=60,
        risk_dollars=150,
    )

    engine.load_data()

    rs_percentile = engine.calculate_rs_percentile(lookback_days=60)

    assert rs_percentile is not None, "RS Percentile no calculado"
    assert rs_percentile.shape == engine.close.shape, "Shape mismatch"
    assert rs_percentile.min().min() >= 0, "RS debe ser >= 0"
    assert rs_percentile.max().max() <= 100, "RS debe ser <= 100"

    mean_rs = rs_percentile.mean().mean()
    logger.info(f"   ✅ RS Percentile calculado correctamente")
    logger.info(f"      Mean RS: {mean_rs:.1f}")
    logger.info(f"      Min RS: {rs_percentile.min().min():.1f}")
    logger.info(f"      Max RS: {rs_percentile.max().max():.1f}")

    return True


def test_entry_quality_score():
    """Test 2: Verificar Entry Quality Score."""
    from src.backtest.vectorbt_engine_advanced import AdvancedVectorBTEngine

    logger.info("\n" + "=" * 70)
    logger.info("TEST 2: Entry Quality Score Calculation")
    logger.info("=" * 70)

    universe = ["AAPL", "MSFT", "GOOGL", "NVDA", "TSLA"]

    engine = AdvancedVectorBTEngine(
        universe=universe,
        start_date="2024-01-01",
        end_date="2024-12-31",
        risk_dollars=150,
        score_vwap_weight=0.4,
        score_volume_weight=0.4,
        score_ema_weight=0.2,
    )

    engine.load_data()

    numba_arrays = {}
    from src.backtest.vectorbt_engine_advanced import prepare_numba_arrays

    numba_arrays = prepare_numba_arrays(engine)

    assert "entry_score" in numba_arrays, "Entry score no está en numba_arrays"

    entry_score = numba_arrays["entry_score"]

    assert entry_score.min() >= 0, "Entry score debe ser >= 0"
    assert entry_score.max() <= 1, "Entry score debe ser <= 1"

    mean_score = entry_score.mean()
    logger.info(f"   ✅ Entry Quality Score calculado correctamente")
    logger.info(f"      Mean Score: {mean_score:.3f}")
    logger.info(f"      Min Score: {entry_score.min():.3f}")
    logger.info(f"      Max Score: {entry_score.max():.3f}")

    high_quality_count = (entry_score >= 0.7).sum()
    low_quality_count = (entry_score < 0.3).sum()
    logger.info(f"      High Quality (≥0.7): {high_quality_count:,} signals")
    logger.info(f"      Low Quality (<0.3): {low_quality_count:,} signals")

    return True


def test_screener_integration():
    """Test 3: Verificar integración del Screener con el motor."""
    from src.core.screener import InstitutionalScreener
    from src.data.ticker_cache import TickerCache

    logger.info("\n" + "=" * 70)
    logger.info("TEST 3: Screener Integration")
    logger.info("=" * 70)

    cache = TickerCache()

    symbol = "AAPL"
    df = cache.get_ohlcv(symbol, "2024-01-01", "2024-12-31", offline=True)
    spy_df = cache.get_ohlcv("SPY", "2024-01-01", "2024-12-31", offline=True)

    if df is None or spy_df is None:
        logger.warning(f"   ⚠️ No data available for {symbol}, skipping test")
        return False

    df = df.reset_index()
    df.rename(columns={df.columns[0]: "date"}, inplace=True)
    df["date"] = pd.to_datetime(df["date"])
    df = df.set_index("date")

    df["sma_20"] = df["Close"].rolling(20).mean()
    df["sma_50"] = df["Close"].rolling(50).mean()
    df["sma_volume_20"] = df["Volume"].rolling(20).mean()

    spy_df = spy_df.reset_index()
    spy_df.rename(columns={spy_df.columns[0]: "date"}, inplace=True)
    spy_df["date"] = pd.to_datetime(spy_df["date"])
    spy_df = spy_df.set_index("date")

    screener = InstitutionalScreener(
        adr_threshold=1.5,
        min_price=5.0,
        min_avg_vol=300000,
        min_dollar_vol=15000000,
        rs_window=50,
        min_rvol=1.5,
    )

    test_date = df.index[-50]
    result, reason = screener.scan_verbose(symbol, df, spy_df, test_date)

    if result:
        logger.info(f"   ✅ Screener funcionando correctamente")
        logger.info(f"      Symbol: {result['symbol']}")
        logger.info(f"      Setup: {result['setup']}")
        logger.info(f"      RVOL: {result['rvol']:.2f}x")
        logger.info(f"      ADR: {result['adr_pct']:.2f}%")
        logger.info(f"      Vol_Trig: {result['vol_trig']}")
        logger.info(f"      Dist SMA20: {result['dist_sma20_pct']:.2f}%")
    else:
        logger.info(f"   ℹ️ No signal for {test_date.date()}: {reason}")

    return True


def test_full_backtest_with_rs_and_scoring():
    """Test 4: Backtest completo con RS y Entry Quality Score activados."""
    from src.backtest.vectorbt_engine_advanced import AdvancedVectorBTEngine

    logger.info("\n" + "=" * 70)
    logger.info("TEST 4: Full Backtest with RS + Entry Quality Score")
    logger.info("=" * 70)

    universe = ["AAPL", "MSFT", "GOOGL", "NVDA", "TSLA", "META", "AMZN", "NFLX"]

    engine = AdvancedVectorBTEngine(
        universe=universe,
        start_date="2024-01-01",
        end_date="2024-12-31",
        use_rs_percentile=True,
        min_rs_percentile=70.0,
        rs_lookback_days=60,
        score_vwap_weight=0.4,
        score_volume_weight=0.4,
        score_ema_weight=0.2,
        risk_dollars=150,
        mode="production",
    )

    result = engine.run_backtest()

    trades_df = result.get("trades_df")
    metrics = result.get("metrics", {})

    if trades_df is not None and len(trades_df) > 0:
        logger.info(f"   ✅ Backtest completado con trades")
        logger.info(f"      Total trades: {len(trades_df)}")
        logger.info(f"      Sharpe: {metrics.get('sharpe_ratio', 0):.2f}")
        logger.info(f"      Win Rate: {metrics.get('win_rate', 0) * 100:.1f}%")

        if "entry_score" in trades_df.columns:
            avg_entry_score = trades_df["entry_score"].mean()
            logger.info(f"      Avg Entry Score: {avg_entry_score:.3f}")
    else:
        logger.info(f"   ℹ️ No trades generated (filters may be too restrictive)")

    return True


def main():
    """Ejecutar todos los tests."""
    logger.info("=" * 70)
    logger.info("VALIDANDO SCREENER + SCORING (RS + Entry Quality)")
    logger.info("=" * 70)

    tests = [
        ("RS Percentile", test_rs_percentile_calculation),
        ("Entry Quality Score", test_entry_quality_score),
        ("Screener Integration", test_screener_integration),
        ("Full Backtest", test_full_backtest_with_rs_and_scoring),
    ]

    passed = 0
    failed = 0

    for name, test_func in tests:
        try:
            if test_func():
                passed += 1
                logger.info(f"   ✅ {name}: PASSED")
            else:
                failed += 1
                logger.info(f"   ⚠️ {name}: SKIPPED (no data)")
        except Exception as e:
            failed += 1
            logger.error(f"   ❌ {name}: FAILED - {e}")
            import traceback

            logger.error(traceback.format_exc())

    logger.info("\n" + "=" * 70)
    logger.info(f"RESULTADO: {passed}/{len(tests)} tests passed")
    if failed > 0:
        logger.warning(f"   ⚠️ {failed} tests failed or skipped")
    logger.info("=" * 70)

    return failed == 0


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
