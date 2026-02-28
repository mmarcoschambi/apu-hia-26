#!/usr/bin/env python3
"""Test rápido para verificar cálculo de ADR"""

import sys
import pandas as pd
import sqlite3
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from src.backtest.vectorbt_engine_advanced import AdvancedVectorBTEngine

def get_test_universe(n=20):
    """Carga N tickers de prueba"""
    conn = sqlite3.connect('data/ticker_cache.db')
    cursor = conn.execute(f"SELECT DISTINCT ticker FROM ohlcv_cache LIMIT {n}")
    universe = [row[0] for row in cursor.fetchall()]
    conn.close()
    return universe

def main():
    universe = ['AAPL', 'MSFT', 'NVDA', 'TSLA', 'AMD'] # Fixed universe
    start_date = "2023-01-01"
    end_date = "2023-06-30"  # 6 months

    print(f"🧪 TEST ADR - {len(universe)} tickers, {start_date} a {end_date}")

    params = {
        'initial_capital': 100000,
        'risk_dollars': 150,
        'min_rvol': 1.0,      # Muy bajo para permitir entries
        'min_adr': 0.5,       # Muy bajo para permitir entries
        'min_dollar_volume': 500_000,  # Muy bajo
        'max_dist_sma20': 10.0,  # Muy alto
        'use_adaptive_filtering': False,
        'use_market_regime_filter': False,
        'require_spy_above_sma50': False,
        'min_consolidation_days': 1,  # Muy bajo
        'offline_mode': True,
        'require_positive_rs': False,
    }

    engine = AdvancedVectorBTEngine(
        universe=universe,
        start_date=start_date,
        end_date=end_date,
        **params
    )

    print("\n📥 Cargando datos...")
    engine.load_data()

    print(f"\n📊 Datos cargados:")
    print(f"   • Tickers: {len(engine.close.columns)}")
    print(f"   • Días: {len(engine.close)}")
    print(f"   • ADR mean: {engine.adr_pct.mean().mean():.2f}%")
    print(f"   • ADR max: {engine.adr_pct.max().max():.2f}%")
    print(f"   • RVOL mean: {engine.rvol.mean().mean():.2f}x")

    # Check if ADR has non-zero values
    non_zero_adr = (engine.adr_pct > 0).sum().sum()
    total_adr_cells = engine.adr_pct.size
    print(f"   • ADR > 0: {non_zero_adr}/{total_adr_cells} ({100*non_zero_adr/total_adr_cells:.1f}%)")

    if non_zero_adr == 0:
        print("\n❌ ERROR: ADR está todo en 0!")
        print("   Esto significa que el cálculo de ADR no está funcionando.")

    # Check samples
    sample_ticker = engine.close.columns[0]
    sample_date = engine.close.index[100] if len(engine.close) > 100 else engine.close.index[0]
    print(f"\n📋 Muestra ({sample_ticker} @ {sample_date.date()}):")
    print(f"   • Close: ${engine.close.loc[sample_date, sample_ticker]:.2f}")
    print(f"   • High: ${engine.high.loc[sample_date, sample_ticker]:.2f}")
    print(f"   • Low: ${engine.low.loc[sample_date, sample_ticker]:.2f}")
    print(f"   • Volume: {engine.volume.loc[sample_date, sample_ticker]:,.0f}")
    print(f"   • ADR: {engine.adr_pct.loc[sample_date, sample_ticker]:.2f}%")
    print(f"   • RVOL: {engine.rvol.loc[sample_date, sample_ticker]:.2f}x")
    print(f"   • $Volume: ${engine.dollar_volume.loc[sample_date, sample_ticker]/1e6:.2f}M")

    print("\n⚡ Ejecutando backtest...")
    results = engine.run_backtest()
    trades = results['trades']

    print(f"\n📊 RESULTADOS:")
    print(f"   Total trades: {len(trades)}")
    if not trades.empty:
        # Check for column name (PnL vs pnl)
        pnl_col = 'PnL' if 'PnL' in trades.columns else 'pnl'
        
        print(f"   Win Rate: {len(trades[trades[pnl_col] > 0]) / len(trades) * 100:.1f}%")
        print(f"   Total PnL: ${trades[pnl_col].sum():,.2f}")

    rejection_stats = engine.get_rejection_stats()
    print(f"\n🚫 FILTROS:")
    if rejection_stats:
        for reason, count in sorted(rejection_stats.items(), key=lambda x: x[1], reverse=True)[:10]:
            print(f"   • {reason}: {count}")

if __name__ == "__main__":
    main()
