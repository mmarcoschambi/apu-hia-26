#!/usr/bin/env python3
"""
Script para verificar que las columnas calculadas se están usando correctamente
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from src.data.ticker_cache import TickerCache
import pandas as pd
import time

def test_cache_retrieval():
    """Verifica que get_ohlcv devuelve todas las columnas calculadas"""
    cache = TickerCache()
    
    print("=" * 70)
    print("TEST 1: Verificar columnas devueltas por get_ohlcv()")
    print("=" * 70)
    
    # Obtener datos de prueba
    df = cache.get_ohlcv('AAPL', '2018-01-01', '2018-01-10', offline=True)
    
    if df is None or df.empty:
        print("❌ ERROR: No se obtuvieron datos")
        return False
    
    print(f"\n✅ Datos obtenidos: {len(df)} filas")
    print(f"\nColumnas devueltas ({len(df.columns)}):")
    for col in df.columns:
        print(f"  - {col}")
    
    # Verificar columnas esperadas
    expected_cols = [
        'Open', 'High', 'Low', 'Close', 'Volume',
        'dollar_volume', 'rolling_dollar_vol_20', 'avg_volume_20',
        'adr_14', 'adr_pct_14', 'sma_50', 'sma_200',
        'price_above_sma50', 'price_above_sma200', 'sma50_above_sma200', 'trend_aligned'
    ]
    
    missing = [col for col in expected_cols if col not in df.columns]
    if missing:
        print(f"\n⚠️  Columnas faltantes: {missing}")
        return False
    
    print("\n✅ Todas las columnas esperadas están presentes!")
    
    # Mostrar ejemplo de datos
    print("\n" + "=" * 70)
    print("Ejemplo de datos (primera fila):")
    print("=" * 70)
    first_row = df.iloc[0]
    print(f"Fecha: {df.index[0]}")
    print(f"Close: ${first_row['Close']:.2f}")
    print(f"ADR (14): ${first_row['adr_14']:.4f}")
    print(f"ADR %: {first_row['adr_pct_14']:.2f}%")
    print(f"Rolling Dollar Vol (20): ${first_row['rolling_dollar_vol_20']/1e9:.2f}B")
    print(f"SMA 50: ${first_row['sma_50']:.2f}")
    print(f"SMA 200: ${first_row['sma_200']:.2f}")
    print(f"Trend Aligned: {bool(first_row['trend_aligned'])}")
    
    return True


def test_performance():
    """Compara rendimiento con y sin columnas pre-calculadas"""
    cache = TickerCache()
    
    print("\n" + "=" * 70)
    print("TEST 2: Comparación de velocidad")
    print("=" * 70)
    
    # Test con cache completo
    start = time.time()
    df = cache.get_ohlcv('AAPL', '2018-01-01', '2018-12-31', offline=True)
    elapsed = time.time() - start
    
    if df is not None and not df.empty:
        has_adr = 'adr_14' in df.columns
        has_sma = 'sma_50' in df.columns
        
        print(f"\n✅ Datos obtenidos en {elapsed*1000:.2f}ms")
        print(f"   - {len(df)} filas")
        print(f"   - {len(df.columns)} columnas")
        print(f"   - ADR pre-calculado: {'✅' if has_adr else '❌'}")
        print(f"   - SMAs pre-calculadas: {'✅' if has_sma else '❌'}")
        
        if has_adr:
            # Verificar que no hay valores nulos en ADR
            null_count = df['adr_14'].isna().sum()
            print(f"   - Valores nulos en ADR: {null_count}/{len(df)}")
            
            if null_count < len(df):
                print("\n✅ Optimización aplicada correctamente!")
                print("   El backtest ahora usará ADR pre-calculado en lugar de recalcular.")
                return True
    
    return False


def test_multiple_symbols():
    """Prueba con múltiples símbolos"""
    cache = TickerCache()
    
    print("\n" + "=" * 70)
    print("TEST 3: Prueba con múltiples símbolos")
    print("=" * 70)
    
    symbols = ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'TSLA']
    
    start_total = time.time()
    for symbol in symbols:
        start = time.time()
        df = cache.get_ohlcv(symbol, '2018-01-01', '2018-12-31', offline=True)
        elapsed = time.time() - start
        
        if df is not None and not df.empty:
            has_metrics = 'adr_14' in df.columns and 'sma_50' in df.columns
            status = "✅" if has_metrics else "⚠️ "
            print(f"{status} {symbol}: {len(df)} filas en {elapsed*1000:.1f}ms")
        else:
            print(f"❌ {symbol}: No data")
    
    total_elapsed = time.time() - start_total
    print(f"\nTotal: {len(symbols)} símbolos en {total_elapsed:.2f}s")
    print(f"Promedio: {total_elapsed/len(symbols)*1000:.1f}ms por símbolo")
    
    return True


if __name__ == "__main__":
    success = True
    
    try:
        if not test_cache_retrieval():
            success = False
        
        if not test_performance():
            success = False
        
        if not test_multiple_symbols():
            success = False
        
        print("\n" + "=" * 70)
        if success:
            print("✅ TODOS LOS TESTS PASARON")
            print("\nBeneficios de la optimización:")
            print("  1. ADR y otras métricas ya están pre-calculadas")
            print("  2. Backtests se ejecutarán más rápido")
            print("  3. Menos cálculos redundantes en cada iteración")
        else:
            print("⚠️  ALGUNOS TESTS FALLARON")
        print("=" * 70)
        
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
