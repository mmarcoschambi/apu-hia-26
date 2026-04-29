#!/usr/bin/env python3
"""
Test script para verificar el sistema de chunking y cache
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from src.backtest.chunked_backtest_engine import ChunkedBacktestEngine
from src.indicators.indicator_cache import IndicatorCache, PrecomputedIndicators

import logging
import pandas as pd
import numpy as np

logging.basicConfig(level=logging.INFO)


def test_indicator_cache():
    print("\n" + "=" * 60)
    print("TEST 1: Indicator Cache")
    print("=" * 60)

    # Datos de prueba
    dates = pd.date_range("2020-01-01", "2024-12-31", freq="D")
    data = pd.DataFrame(
        {
            "close": np.random.randn(len(dates)).cumsum() + 100,
            "high": np.random.randn(len(dates)).cumsum() + 105,
            "low": np.random.randn(len(dates)).cumsum() + 95,
            "volume": np.random.randint(1000000, 10000000, len(dates)),
        },
        index=dates,
    )

    cache = IndicatorCache()

    # Primer cálculo
    print("Primer cálculo de SMA20...")
    sma20 = cache.get_or_compute(
        "TEST", "sma20", data, PrecomputedIndicators.sma, window=20
    )
    print(f"✅ SMA20 shape: {sma20.shape}")

    # Segundo cálculo (del cache)
    print("Segundo cálculo de SMA20 (debe ser del cache)...")
    sma20_cached = cache.get_or_compute(
        "TEST", "sma20", data, PrecomputedIndicators.sma, window=20
    )
    print(f"✅ SMA20 cached shape: {sma20_cached.shape}")

    # Estadísticas
    stats = cache.get_cache_stats()
    print(f"\n📊 Cache stats:")
    print(f"   Memory entries: {stats['memory_entries']}")
    print(f"   Disk files: {stats['disk_files']}")
    print(f"   Disk size: {stats['disk_size_mb']:.2f} MB")

    return True


def test_chunked_backtest():
    print("\n" + "=" * 60)
    print("TEST 2: Chunked Backtest Engine")
    print("=" * 60)

    # Tickers pequeños para prueba rápida
    tickers = ["NVDA", "TSLA", "AAPL"]

    # Período de 2 años
    start_date = "2023-01-01"
    end_date = "2024-12-31"

    print(f"Tickers: {tickers}")
    print(f"Período: {start_date} a {end_date}")

    # Crear engine
    try:
        engine = ChunkedBacktestEngine(
            tickers=tickers,
            start_date=start_date,
            end_date=end_date,
            initial_capital=100000,
            chunk_period="quarter",
            offline_mode=True,
        )

        print(f"✅ Engine inicializado con {len(engine.chunks)} chunks")

        # Ejecutar backtest
        print("\nEjecutando backtest...")
        results = engine.run(
            signal_type="vcp",
            tp1_r=2.0,
            tp2_r=4.0,
            tp1_pct=0.3,
            tp2_pct=0.4,
            runner_pct=0.3,
            risk_pct_per_trade=0.005,
            max_exposure_pct=0.25,
            max_stop_pct=0.03,
        )

        if not results.empty:
            print(f"\n✅ Backtest completado!")
            print(f"   Total trades: {len(results)}")
            print(f"   Total PnL: ${results['pnl'].sum():,.2f}")
            print(f"   Win rate: {(results['pnl'] > 0).mean() * 100:.1f}%")
            return True
        else:
            print("⚠️ No se generaron trades")
            return False

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback

        traceback.print_exc()
        return False


if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("🧪 TEST DEL SISTEMA DE CHUNKING Y CACHE")
    print("=" * 60)

    # Test 1: Indicator Cache
    test1_passed = test_indicator_cache()

    # Test 2: Chunked Backtest
    test2_passed = test_chunked_backtest()

    # Resumen
    print("\n" + "=" * 60)
    print("📊 RESUMEN DE TESTS")
    print("=" * 60)
    print(f"Indicator Cache: {'✅ PASÓ' if test1_passed else '❌ FALLÓ'}")
    print(f"Chunked Backtest: {'✅ PASÓ' if test2_passed else '❌ FALLÓ'}")

    if test1_passed and test2_passed:
        print("\n🎉 TODOS LOS TESTS PASARON!")
    else:
        print("\n⚠️ Algunos tests fallaron, revisa el log para más detalles")
