#!/usr/bin/env python3
"""
DEBUG DATA AVAILABILITY - Verifica si hay datos suficientes
"""

import sys
from pathlib import Path
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.data.ticker_cache import TickerCache


def debug_data_availability():
    """Debug: Verifica disponibilidad de datos para NVDA"""
    print("\n" + "=" * 80)
    print("📊 DATA AVAILABILITY DEBUG")
    print("=" * 80)

    ticker = "NVDA"
    start_date = "2024-01-01"
    end_date = "2024-06-30"

    print(f"\n🎯 Test: {ticker} ({start_date} to {end_date})")

    cache = TickerCache()

    # Extender start date para lookback (365 días)
    import datetime

    extended_start = (
        pd.to_datetime(start_date) - datetime.timedelta(days=365)
    ).strftime("%Y-%m-%d")

    try:
        df = cache.get_ohlcv(ticker, start_date=extended_start, end_date=end_date)

        print(f"\n✅ Datos cargados:")
        print(f"   Total rows: {len(df)}")
        print(f"   Columns: {list(df.columns)}")
        print(f"   Date range: {df.index[0]} to {df.index[-1]}")

        # Filtrar por período de backtest
        backtest_df = df[df.index >= start_date]

        print(f"\n📊 Datos en período de backtest ({start_date} to {end_date}):")
        print(f"   Rows: {len(backtest_df)}")

        if len(backtest_df) < 100:
            print("\n🔴 PROBLEMA: Menos de 100 días de datos!")
            print("   Esto puede causar problemas con indicadores (rolling windows)")

        # Check data quality (columnas pueden ser Close o close)
        close_col = "Close" if "Close" in backtest_df.columns else "close"
        volume_col = "Volume" if "Volume" in backtest_df.columns else "volume"

        print("\n📈 Data Quality:")
        print(f"   Nulls: {backtest_df.isnull().sum().sum()}")
        print(
            f"   Close range: ${backtest_df[close_col].min():.2f} - ${backtest_df[close_col].max():.2f}"
        )
        print(
            f"   Volume range: {backtest_df[volume_col].min():.0f} - {backtest_df[volume_col].max():.0f}"
        )

        # Verificar períodos sin datos (gaps)
        date_range = (pd.to_datetime(end_date) - pd.to_datetime(start_date)).days
        coverage = len(backtest_df) / date_range * 100
        print(f"\n📅 Coverage: {coverage:.1f}% ({len(backtest_df)}/{date_range} days)")

        if coverage < 80:
            print("\n🔴 PROBLEMA: Cobertura baja!")
            print("   Puede que el ticker no tradeaba en este período")
            print("   o hay datos faltantes en la base de datos")

        # Mostrar primeras 5 filas del período
        print("\n📋 Primeras 5 filas del período:")
        print(backtest_df.head())

    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    debug_data_availability()
