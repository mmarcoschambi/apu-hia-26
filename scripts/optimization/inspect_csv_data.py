#!/usr/bin/env python3
"""
CSV Data Inspector - Muestra qué datos están disponibles para optimización
"""

import pandas as pd
import sys
from pathlib import Path

def inspect_csv_for_optimization(csv_path=None):
    """Inspecciona qué columnas están disponibles en el CSV para optimización."""
    
    # Find CSV
    if csv_path is None:
        search_paths = [
            'outputs/backtests/trade_log.csv',
            'outputs/backtests/complete_trades.csv',
            'scripts/optimization/complete_trades_20260107.csv',
        ]
        
        for path in search_paths:
            if Path(path).exists():
                csv_path = path
                break
    
    if csv_path is None or not Path(csv_path).exists():
        print("❌ No se encontró archivo CSV")
        print("\nBusca en:")
        for p in search_paths:
            print(f"  - {p}")
        sys.exit(1)
    
    print("=" * 80)
    print("📊 CSV DATA INSPECTOR - Análisis para Optimización")
    print("=" * 80)
    print(f"\n📂 Archivo: {csv_path}\n")
    
    # Load CSV
    df = pd.read_csv(csv_path)
    print(f"✅ Trades cargados: {len(df)}\n")
    
    # Categorize columns
    print("=" * 80)
    print("🔍 COLUMNAS DISPONIBLES (Valores guardados en CSV)")
    print("=" * 80)
    
    context_columns = [col for col in df.columns if 'context_' in col]
    entry_columns = [col for col in df.columns if 'entry_' in col]
    exit_columns = [col for col in df.columns if 'exit_' in col]
    performance_columns = ['pnl', 'r_multiple', 'total_pnl', 'is_winner']
    other_columns = [col for col in df.columns if col not in context_columns + entry_columns + exit_columns + performance_columns]
    
    print("\n📌 CONTEXT DATA (Datos de entrada - OPTIMIZABLES):")
    for col in sorted(context_columns):
        if df[col].dtype in ['int64', 'float64']:
            print(f"   ✅ {col:30s} - Range: {df[col].min():.2f} to {df[col].max():.2f}")
        else:
            print(f"   ✅ {col:30s} - Type: {df[col].dtype}")
    
    print("\n📌 ENTRY DATA:")
    for col in sorted(entry_columns):
        if col in df.columns:
            if df[col].dtype in ['int64', 'float64']:
                print(f"   ✅ {col:30s} - Range: {df[col].min():.2f} to {df[col].max():.2f}")
            else:
                print(f"   ✅ {col:30s} - Type: {df[col].dtype}")
    
    print("\n📌 OTHER OPTIMIZABLE DATA:")
    opt_cols = ['dist_sma20_pct', 'consolidation_days', 'sector_strength', 
                'adjusted_risk_dollars', 'risk_reduction_factor', 'time_since_earnings']
    for col in opt_cols:
        if col in df.columns:
            print(f"   ✅ {col:30s} - Range: {df[col].min():.2f} to {df[col].max():.2f}")
    
    print("\n📌 PERFORMANCE METRICS:")
    for col in performance_columns:
        if col in df.columns:
            if df[col].dtype in ['int64', 'float64']:
                print(f"   ✅ {col:30s} - Range: {df[col].min():.2f} to {df[col].max():.2f}")
            else:
                print(f"   ✅ {col:30s} - Type: {df[col].dtype}")
    
    # What's NOT in CSV (filter LIMITS)
    print("\n" + "=" * 80)
    print("⚠️  NO DISPONIBLES (Filtros/límites aplicados durante backtest)")
    print("=" * 80)
    print("""
Los siguientes parámetros fueron usados como FILTROS durante el backtest,
pero NO se guardan en el CSV como columnas:

   ❌ min_rvol              - Solo trades con rvol >= min_rvol están en CSV
   ❌ max_dist_sma20        - Solo trades con dist <= max están en CSV
   ❌ min_adr               - Solo trades con adr >= min están en CSV
   ❌ min_consolidation     - Solo trades con consol >= min están en CSV
   ❌ min_volume            - Solo trades con volumen >= min están en CSV
   ❌ min_dollar_volume     - Solo trades con $ volume >= min están en CSV
   ❌ max_stop_pct          - Solo trades con stop <= max están en CSV
   ❌ earnings_days         - Solo trades fuera de ventana están en CSV
   ❌ rvol_danger/warning   - Usado para position sizing, no filtro
   ❌ adr_high/med          - Usado para position sizing, no filtro

⚠️  IMPLICACIÓN:
    Los scripts de optimización pueden aplicar filtros MÁS RESTRICTIVOS,
    pero NO pueden relajar filtros (no tienen datos de trades rechazados).
    """)
    
    # Recommendations
    print("=" * 80)
    print("💡 RECOMENDACIONES PARA OPTIMIZACIÓN")
    print("=" * 80)
    print("""
1. ✅ Puedes optimizar ajustando límites HACIA ARRIBA en:
   - min_rvol (ej. probar 1.5 → 2.0 → 2.5)
   - min_adr (ej. probar 1.5 → 2.0 → 3.0)
   - min_consolidation (ej. probar 10 → 15 → 20 días)

2. ✅ Puedes optimizar ajustando límites HACIA ABAJO en:
   - max_dist_sma20 (ej. probar 10% → 7% → 5%)
   - max_stop_pct (ej. probar 8% → 6% → 5%)

3. ❌ NO puedes optimizar RELAJANDO filtros sin re-ejecutar backtest:
   - min_rvol 2.0 → 1.0 (necesitas trades con rvol 1.0-2.0)
   - max_dist_sma20 5% → 10% (necesitas trades con dist 5-10%)

4. 🔄 Para optimización completa:
   - Ejecuta backtest con FILTROS MUY RELAJADOS
   - Exporta todos los trades
   - Optimización prueba filtros MÁS RESTRICTIVOS
   - Aplica mejores parámetros en nuevo backtest
    """)
    
    # Show sample data
    print("=" * 80)
    print("📊 SAMPLE DATA (primeros 3 trades)")
    print("=" * 80)
    
    sample_cols = ['ticker', 'entry_date', 'pnl', 'r_multiple']
    if 'context_rvol' in df.columns:
        sample_cols.append('context_rvol')
    if 'context_adr' in df.columns:
        sample_cols.append('context_adr')
    if 'dist_sma20_pct' in df.columns:
        sample_cols.append('dist_sma20_pct')
    if 'consolidation_days' in df.columns:
        sample_cols.append('consolidation_days')
    
    available_cols = [col for col in sample_cols if col in df.columns]
    print(df[available_cols].head(3).to_string(index=False))
    
    print("\n" + "=" * 80)

if __name__ == '__main__':
    csv_path = sys.argv[1] if len(sys.argv) > 1 else None
    inspect_csv_for_optimization(csv_path)
