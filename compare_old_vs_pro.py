#!/usr/bin/env python3
"""
Backtest Comparison: OLD vs PROFESSIONAL Parameters
Ejecuta backtests comparativos para validar mejoras
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from src.backtest.vectorbt_engine_advanced import AdvancedVectorBTEngine
import pandas as pd
from datetime import datetime, timedelta

def run_comparison_backtest(test_universe, start_date, end_date):
    """
    Ejecuta dos backtests: uno con parámetros OLD y otro con PROFESSIONAL
    """
    
    print("\n" + "="*80)
    print(" "*25 + "🏁 BACKTEST COMPARISON")
    print(" "*20 + "OLD Parameters vs PROFESSIONAL Parameters")
    print("="*80)
    
    print(f"\n📅 Período: {start_date} a {end_date}")
    print(f"🎯 Universo: {len(test_universe)} tickers")
    print(f"   Tickers: {', '.join(test_universe[:10])}{'...' if len(test_universe) > 10 else ''}")
    
    # ========================================================================
    # BACKTEST 1: OLD PARAMETERS (Los que causaban -39% alpha)
    # ========================================================================
    print("\n" + "-"*80)
    print("📊 BACKTEST 1: OLD PARAMETERS (Baseline - Malo)")
    print("-"*80)
    
    print("\nParámetros OLD:")
    print("  - max_dist_sma20: 7.0%")
    print("  - min_rvol: 2.0x")
    print("  - min_adr: 3.0%")
    print("  - min_dollar_volume: $15M")
    print("  - max_stop_pct: 8.0%")
    print("  - min_consolidation_days: 5")
    print("  - rvol_danger: 3.0x")
    print("  - rvol_warning: 2.0x")
    
    try:
        engine_old = AdvancedVectorBTEngine(
            universe=test_universe,
            start_date=start_date,
            end_date=end_date,
            initial_capital=100000,
            risk_dollars=150,
            # OLD PARAMETERS (Malos)
            max_dist_sma20=7.0,
            min_rvol=2.0,
            min_adr=3.0,
            min_volume=300000,
            min_dollar_volume=15000000,  # $15M
            max_stop_pct=8.0,
            min_consolidation_days=5,
            rvol_danger=3.0,
            rvol_warning=2.0,
            rvol_danger_size=25,
            rvol_warning_size=60,
            adr_high=6.0,
            adr_med=5.0,
            offline_mode=True
        )
        
        print("\n⏳ Ejecutando backtest OLD...")
        results_old = engine_old.run_backtest()
        engine_old.cleanup()
        
        print("✅ Backtest OLD completado")
        
    except Exception as e:
        print(f"❌ Error en backtest OLD: {e}")
        results_old = None
    
    # ========================================================================
    # BACKTEST 2: PROFESSIONAL PARAMETERS
    # ========================================================================
    print("\n" + "-"*80)
    print("📊 BACKTEST 2: PROFESSIONAL PARAMETERS")
    print("-"*80)
    
    print("\nParámetros PROFESSIONAL:")
    print("  - max_dist_sma20: 2.5%")
    print("  - min_rvol: 2.5x")
    print("  - min_adr: 5.0%")
    print("  - min_dollar_volume: $5M")
    print("  - max_stop_pct: 6.5%")
    print("  - min_consolidation_days: 10")
    print("  - rvol_danger: 4.0x")
    print("  - rvol_warning: 3.0x")
    
    try:
        engine_pro = AdvancedVectorBTEngine(
            universe=test_universe,
            start_date=start_date,
            end_date=end_date,
            initial_capital=100000,
            risk_dollars=150,
            # PROFESSIONAL PARAMETERS (defaults ya aplicados)
            # No necesitamos especificarlos, los defaults son profesionales
            offline_mode=True
        )
        
        print("\n⏳ Ejecutando backtest PROFESSIONAL...")
        results_pro = engine_pro.run_backtest()
        engine_pro.cleanup()
        
        print("✅ Backtest PROFESSIONAL completado")
        
    except Exception as e:
        print(f"❌ Error en backtest PROFESSIONAL: {e}")
        results_pro = None
    
    # ========================================================================
    # COMPARACIÓN DE RESULTADOS
    # ========================================================================
    print("\n" + "="*80)
    print(" "*30 + "📈 RESULTADOS")
    print("="*80)
    
    if results_old is None or results_pro is None:
        print("\n❌ No se pudieron completar ambos backtests para comparar")
        return
    
    # Extract metrics
    trades_old = results_old.get('trades', pd.DataFrame())
    trades_pro = results_pro.get('trades', pd.DataFrame())
    
    metrics_old = results_old.get('metrics', {})
    metrics_pro = results_pro.get('metrics', {})
    
    print(f"\n{'Métrica':<30} {'OLD (Malo)':<20} {'PROFESSIONAL':<20} {'Cambio'}")
    print("-"*90)
    
    # Total Trades
    n_trades_old = len(trades_old) if not trades_old.empty else 0
    n_trades_pro = len(trades_pro) if not trades_pro.empty else 0
    change = ((n_trades_pro - n_trades_old) / n_trades_old * 100) if n_trades_old > 0 else 0
    print(f"{'Total Trades':<30} {n_trades_old:<20} {n_trades_pro:<20} {change:+.1f}%")
    
    # Win Rate
    win_rate_old = metrics_old.get('win_rate', 0)
    win_rate_pro = metrics_pro.get('win_rate', 0)
    change = ((win_rate_pro - win_rate_old) / win_rate_old * 100) if win_rate_old > 0 else 0
    print(f"{'Win Rate':<30} {win_rate_old:.1f}%{'':<15} {win_rate_pro:.1f}%{'':<15} {change:+.1f}%")
    
    # Profit Factor
    pf_old = metrics_old.get('profit_factor', 0)
    pf_pro = metrics_pro.get('profit_factor', 0)
    change = ((pf_pro - pf_old) / pf_old * 100) if pf_old > 0 else 0
    print(f"{'Profit Factor':<30} {pf_old:.2f}{'':<17} {pf_pro:.2f}{'':<17} {change:+.1f}%")
    
    # Total Return
    ret_old = metrics_old.get('total_return_pct', 0)
    ret_pro = metrics_pro.get('total_return_pct', 0)
    diff = ret_pro - ret_old
    print(f"{'Total Return':<30} {ret_old:+.2f}%{'':<15} {ret_pro:+.2f}%{'':<15} {diff:+.2f}%")
    
    # Avg R-Multiple
    if not trades_old.empty and 'r_multiple' in trades_old.columns:
        r_mult_old = trades_old['r_multiple'].mean()
    else:
        r_mult_old = 0
    
    if not trades_pro.empty and 'r_multiple' in trades_pro.columns:
        r_mult_pro = trades_pro['r_multiple'].mean()
    else:
        r_mult_pro = 0
    
    diff = r_mult_pro - r_mult_old
    print(f"{'Avg R-Multiple':<30} {r_mult_old:.2f}R{'':<16} {r_mult_pro:.2f}R{'':<16} {diff:+.2f}R")
    
    # Max Drawdown
    dd_old = metrics_old.get('max_drawdown_pct', 0)
    dd_pro = metrics_pro.get('max_drawdown_pct', 0)
    diff = dd_pro - dd_old
    print(f"{'Max Drawdown':<30} {dd_old:.2f}%{'':<15} {dd_pro:.2f}%{'':<15} {diff:+.2f}%")
    
    print("\n" + "="*80)
    print(" "*30 + "💡 INTERPRETACIÓN")
    print("="*80)
    
    print("\n✅ **Mejoras Esperadas con PROFESSIONAL:**")
    print("   - Win Rate: 27% → 58-65% (más selectividad)")
    print("   - Profit Factor: 0.39 → 2.0+ (mejor relación riesgo/recompensa)")
    print("   - R-Multiple: -0.30R → +1.2R (trades positivos en promedio)")
    print("   - Total Trades: Menos pero de mayor calidad")
    
    print("\n⚠️  **Si no ves mejoras inmediatas:**")
    print("   - Período puede ser demasiado corto")
    print("   - Universo puede carecer de setups de calidad")
    print("   - Market regime puede no ser favorable")
    print("   - Necesitas más datos históricos (recomendado: 2+ años)")
    
    print("\n🎯 **Recomendaciones:**")
    print("   1. Ejecutar en período más largo (2019-2024)")
    print("   2. Usar universo más amplio (S&P 500+)")
    print("   3. Habilitar market regime filter")
    print("   4. Comparar contra SPY benchmark")


def main():
    """Ejecuta comparación con universo de prueba"""
    
    # Universo de prueba (tickers líquidos conocidos)
    test_universe = [
        'AAPL', 'MSFT', 'NVDA', 'GOOGL', 'AMZN', 'META', 'TSLA',
        'AMD', 'NFLX', 'ADBE', 'CRM', 'AVGO', 'ORCL', 'CSCO',
        'INTC', 'TXN', 'QCOM', 'AMAT', 'MU', 'LRCX'
    ]
    
    # Período de prueba (1 año)
    end_date = datetime.now().strftime('%Y-%m-%d')
    start_date = (datetime.now() - timedelta(days=365)).strftime('%Y-%m-%d')
    
    print("\n" + "🚀"*40)
    print(" "*30 + "BACKTEST COMPARISON SUITE")
    print(" "*25 + "OLD vs PROFESSIONAL Parameters")
    print("🚀"*40)
    
    # Ejecutar comparación
    run_comparison_backtest(test_universe, start_date, end_date)
    
    print("\n" + "="*80)
    print(" "*30 + "🏁 COMPARACIÓN COMPLETA")
    print("="*80)
    
    print("\n📝 **Próximos pasos:**")
    print("   1. Revisar las métricas arriba")
    print("   2. Si mejoras son evidentes → aplicar en producción")
    print("   3. Si mejoras son marginales → aumentar período/universo")
    print("   4. Ejecutar optimización con Optuna para fine-tuning")
    print("   5. Habilitar market regime filter para mejor timing")
    
    print("\n💡 **Para backtest más completo:**")
    print("   - Ejecutar desde Streamlit UI con todo el universo SQLite")
    print("   - Período: 2019-2024 (incluye bull + bear markets)")
    print("   - Habilitar todos los filtros profesionales")
    print("   - Comparar contra SPY benchmark")


if __name__ == "__main__":
    main()
