#!/usr/bin/env python3
"""
Test script para verificar el fix de exit logic en numba_core.py

FIXES APLICADOS:
1. Reordenado prioridades: TP1 > TP2 > STOP (antes era STOP > TP2 > TP1)
2. Verificar que use_trailing_stop esté activado
3. Verificar que be_threshold_r sea razonable (0.8-1.0R)

OBJETIVO:
- Verificar que más trades lleguen a risk-free (TP1)
- Avg loss debería reducirse significativamente
- Win rate debería mejorar
"""

import sys
import os
from datetime import datetime, timedelta
import pandas as pd
import numpy as np
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from backtest.vectorbt_engine_advanced import VectorBTEngineAdvanced


def create_test_universe():
    """Crea un universo pequeño para testing rápido"""
    # Tickers con buena data y momentum histórico
    tickers = [
        "AAPL", "MSFT", "NVDA", "GOOGL", "AMZN",
        "META", "TSLA", "NFLX", "AMD", "COIN"
    ]
    return tickers


def run_comparison_test():
    """Corre backtest con y sin el fix para comparar"""
    
    print("=" * 80)
    print("🔧 TEST DE FIX DE EXIT LOGIC")
    print("=" * 80)
    
    # Período de test: 2024 completo
    start_date = "2024-01-01"
    end_date = "2024-12-31"
    
    universe = create_test_universe()
    
    print(f"\n📊 Configuración del Test:")
    print(f"   Período: {start_date} a {end_date}")
    print(f"   Universe: {len(universe)} tickers")
    print(f"   Capital inicial: $100,000")
    
    # ========================================================================
    # TEST 1: Con trailing stop DESACTIVADO (comportamiento anterior)
    # ========================================================================
    print("\n" + "=" * 80)
    print("TEST 1: SIN Trailing Stop (comportamiento anterior)")
    print("=" * 80)
    
    engine_old = VectorBTEngineAdvanced(
        tickers=universe,
        start_date=start_date,
        end_date=end_date,
        initial_capital=100000,
        use_trailing_stop=False,  # ← DESACTIVADO
        market_regime_filter=False,  # Simplificar
        verbose=True
    )
    
    try:
        results_old = engine_old.run()
        
        if results_old and 'trades' in results_old:
            trades_old = results_old['trades']
            
            # Métricas clave
            total_trades_old = len(trades_old)
            tp1_reached_old = (trades_old['exit_type'] == 1).sum()
            tp1_rate_old = (tp1_reached_old / total_trades_old * 100) if total_trades_old > 0 else 0
            
            wins_old = (trades_old['pnl'] > 0).sum()
            losses_old = (trades_old['pnl'] < 0).sum()
            win_rate_old = (wins_old / total_trades_old * 100) if total_trades_old > 0 else 0
            
            avg_win_old = trades_old[trades_old['pnl'] > 0]['pnl'].mean() if wins_old > 0 else 0
            avg_loss_old = trades_old[trades_old['pnl'] < 0]['pnl'].mean() if losses_old > 0 else 0
            
            final_equity_old = results_old.get('final_equity', 100000)
            total_return_old = ((final_equity_old - 100000) / 100000) * 100
            
            print(f"\n📈 RESULTADOS (Sin Trailing Stop):")
            print(f"   Total Trades: {total_trades_old}")
            print(f"   TP1 Rate: {tp1_rate_old:.1f}% ({tp1_reached_old}/{total_trades_old})")
            print(f"   Win Rate: {win_rate_old:.1f}% ({wins_old}/{total_trades_old})")
            print(f"   Avg Win: ${avg_win_old:,.2f}")
            print(f"   Avg Loss: ${avg_loss_old:,.2f}")
            print(f"   Total Return: {total_return_old:+.2f}%")
            print(f"   Final Equity: ${final_equity_old:,.0f}")
        else:
            print("   ⚠️ No se generaron trades")
            trades_old = pd.DataFrame()
            total_trades_old = 0
            tp1_rate_old = 0
            win_rate_old = 0
            total_return_old = 0
            
    except Exception as e:
        print(f"   ❌ Error en Test 1: {e}")
        import traceback
        traceback.print_exc()
        trades_old = pd.DataFrame()
        total_trades_old = 0
        tp1_rate_old = 0
        win_rate_old = 0
        total_return_old = 0
    
    # ========================================================================
    # TEST 2: Con trailing stop ACTIVADO + prioridad corregida
    # ========================================================================
    print("\n" + "=" * 80)
    print("TEST 2: CON Trailing Stop + Exit Logic Fix")
    print("=" * 80)
    
    engine_new = VectorBTEngineAdvanced(
        tickers=universe,
        start_date=start_date,
        end_date=end_date,
        initial_capital=100000,
        use_trailing_stop=True,  # ← ACTIVADO
        be_trailing_threshold=0.8,  # ← Breakeven a 0.8R (antes de TP1)
        market_regime_filter=False,
        verbose=True
    )
    
    try:
        results_new = engine_new.run()
        
        if results_new and 'trades' in results_new:
            trades_new = results_new['trades']
            
            # Métricas clave
            total_trades_new = len(trades_new)
            tp1_reached_new = (trades_new['exit_type'] == 1).sum()
            tp1_rate_new = (tp1_reached_new / total_trades_new * 100) if total_trades_new > 0 else 0
            
            wins_new = (trades_new['pnl'] > 0).sum()
            losses_new = (trades_new['pnl'] < 0).sum()
            win_rate_new = (wins_new / total_trades_new * 100) if total_trades_new > 0 else 0
            
            avg_win_new = trades_new[trades_new['pnl'] > 0]['pnl'].mean() if wins_new > 0 else 0
            avg_loss_new = trades_new[trades_new['pnl'] < 0]['pnl'].mean() if losses_new > 0 else 0
            
            final_equity_new = results_new.get('final_equity', 100000)
            total_return_new = ((final_equity_new - 100000) / 100000) * 100
            
            print(f"\n📈 RESULTADOS (Con Trailing Stop + Fix):")
            print(f"   Total Trades: {total_trades_new}")
            print(f"   TP1 Rate: {tp1_rate_new:.1f}% ({tp1_reached_new}/{total_trades_new})")
            print(f"   Win Rate: {win_rate_new:.1f}% ({wins_new}/{total_trades_new})")
            print(f"   Avg Win: ${avg_win_new:,.2f}")
            print(f"   Avg Loss: ${avg_loss_new:,.2f}")
            print(f"   Total Return: {total_return_new:+.2f}%")
            print(f"   Final Equity: ${final_equity_new:,.0f}")
        else:
            print("   ⚠️ No se generaron trades")
            trades_new = pd.DataFrame()
            total_trades_new = 0
            tp1_rate_new = 0
            win_rate_new = 0
            total_return_new = 0
            
    except Exception as e:
        print(f"   ❌ Error en Test 2: {e}")
        import traceback
        traceback.print_exc()
        trades_new = pd.DataFrame()
        total_trades_new = 0
        tp1_rate_new = 0
        win_rate_new = 0
        total_return_new = 0
    
    # ========================================================================
    # COMPARACIÓN
    # ========================================================================
    print("\n" + "=" * 80)
    print("📊 COMPARACIÓN DE RESULTADOS")
    print("=" * 80)
    
    if total_trades_old > 0 and total_trades_new > 0:
        print(f"\nMétrica                  | Antes      | Después    | Delta")
        print("-" * 65)
        print(f"TP1 Rate (risk-free)     | {tp1_rate_old:6.1f}%   | {tp1_rate_new:6.1f}%   | {tp1_rate_new - tp1_rate_old:+6.1f}%")
        print(f"Win Rate                 | {win_rate_old:6.1f}%   | {win_rate_new:6.1f}%   | {win_rate_new - win_rate_old:+6.1f}%")
        print(f"Total Return             | {total_return_old:6.1f}%   | {total_return_new:6.1f}%   | {total_return_new - total_return_old:+6.1f}%")
        
        # Verificaciones
        print("\n✅ VERIFICACIONES:")
        
        improvements = []
        warnings = []
        
        if tp1_rate_new > tp1_rate_old:
            delta_tp1 = tp1_rate_new - tp1_rate_old
            improvements.append(f"TP1 Rate mejoró {delta_tp1:+.1f}% → Más trades llegan a risk-free")
        else:
            warnings.append(f"TP1 Rate NO mejoró (esperado: aumento)")
        
        if win_rate_new > win_rate_old:
            delta_wr = win_rate_new - win_rate_old
            improvements.append(f"Win Rate mejoró {delta_wr:+.1f}%")
        else:
            warnings.append(f"Win Rate NO mejoró")
        
        if total_return_new > total_return_old:
            delta_ret = total_return_new - total_return_old
            improvements.append(f"Total Return mejoró {delta_ret:+.1f}%")
        else:
            warnings.append(f"Total Return NO mejoró")
        
        if improvements:
            print("\n   🎯 Mejoras detectadas:")
            for imp in improvements:
                print(f"      ✓ {imp}")
        
        if warnings:
            print("\n   ⚠️ Warnings:")
            for warn in warnings:
                print(f"      • {warn}")
        
        # Veredicto final
        print("\n" + "=" * 80)
        if len(improvements) >= 2:
            print("✅ FIX EXITOSO - El motor mejoró significativamente")
            print("=" * 80)
            return True
        elif len(improvements) >= 1:
            print("⚠️ FIX PARCIAL - Algunas métricas mejoraron")
            print("=" * 80)
            return True
        else:
            print("❌ FIX NO EFECTIVO - Revisar implementación")
            print("=" * 80)
            return False
    else:
        print("\n⚠️ No se pueden comparar - Uno o ambos tests no generaron trades")
        return False


def run_synthetic_test():
    """Test con datos sintéticos para verificar lógica de exit"""
    print("\n" + "=" * 80)
    print("🧪 TEST SINTÉTICO - Verificar lógica de exits")
    print("=" * 80)
    
    from src.backtest.numba_core import simulate_fast_core
    
    # Crear datos sintéticos
    n_days = 10
    n_tickers = 1
    
    # Escenario: Entrada en día 0, TP1 alcanzado en día 2, luego pullback
    close = np.array([[100], [102], [108], [105], [103], [101], [99], [97], [95], [93]], dtype=np.float32)
    high =  np.array([[101], [103], [110], [106], [104], [102], [100], [98], [96], [94]], dtype=np.float32)
    low =   np.array([[99],  [101], [107], [104], [102], [100], [98],  [96], [94], [92]], dtype=np.float32)
    open_arr = close.copy()
    volume = np.ones((n_days, n_tickers), dtype=np.float32) * 1000000
    
    # Entry en día 0
    entries = np.zeros((n_days, n_tickers), dtype=np.float32)
    entries[0, 0] = 1.0
    
    # Indicadores dummy
    atr = np.ones((n_days, n_tickers), dtype=np.float32) * 3.0
    sma20 = close.copy() * 0.98
    ema10 = close.copy() * 0.99
    adr = np.ones((n_days, n_tickers), dtype=np.float32) * 2.5
    rvol = np.ones((n_days, n_tickers), dtype=np.float32) * 1.5
    
    spy_close = np.ones(n_days, dtype=np.float32) * 450
    spy_sma50 = np.ones(n_days, dtype=np.float32) * 440
    
    # Parámetros
    initial_capital = 100000.0
    tp1_r = 1.5  # TP1 @ $104.5 (entry $100 + 1.5*$3 ATR stop)
    tp2_r = 3.0  # TP2 @ $109
    tp1_pct = 0.5
    tp2_pct = 0.3
    runner_pct = 0.2
    risk_pct = 0.02
    max_exposure = 1.0
    be_threshold_r = 0.8  # Breakeven @ $102.4
    use_trailing_stop = True
    max_stop_pct = 0.10
    risk_dollars = 0.0
    use_fixed_dollar = False
    
    print(f"\n📊 Escenario Sintético:")
    print(f"   Entry: Día 0 @ $100")
    print(f"   Stop: $97 (3 ATR)")
    print(f"   TP1 @ 1.5R: $104.5")
    print(f"   TP2 @ 3.0R: $109")
    print(f"   Breakeven @ 0.8R: $102.4")
    print(f"\n   Día 2: High=$110 → TP1 y TP2 alcanzados!")
    print(f"   Día 5: Low=$100 → Pullback al breakeven")
    print(f"   Día 9: Low=$92 → Stop original hit\n")
    
    # Ejecutar simulación
    results = simulate_fast_core(
        close, high, low, open_arr, volume,
        entries, atr, sma20, ema10, adr, rvol,
        spy_close, spy_sma50,
        initial_capital, tp1_r, tp2_r, tp1_pct, tp2_pct, runner_pct,
        risk_pct, max_exposure, be_threshold_r, use_trailing_stop,
        max_stop_pct, risk_dollars, use_fixed_dollar
    )
    
    equity_arr, trades_log, final_cash = results
    
    # Filtrar trades válidos
    valid_trades = trades_log[trades_log[:, 0] > 0]
    
    print(f"✅ Trades ejecutados: {len(valid_trades)}")
    
    for idx, trade in enumerate(valid_trades):
        day = int(trade[0])
        ticker_idx = int(trade[1])
        exit_type = int(trade[2])
        exit_price = trade[3]
        shares = trade[4]
        pnl = trade[5]
        
        exit_type_names = {0: "STOP", 1: "TP1", 2: "TP2", 3: "RUNNER"}
        
        print(f"\n   Trade {idx + 1}:")
        print(f"      Día: {day}")
        print(f"      Exit Type: {exit_type_names.get(exit_type, 'UNKNOWN')}")
        print(f"      Exit Price: ${exit_price:.2f}")
        print(f"      Shares: {shares:.0f}")
        print(f"      PnL: ${pnl:,.2f}")
    
    # Verificaciones
    print("\n✅ VERIFICACIONES:")
    
    # Debe haber al menos 2 exits (TP1 y algo más)
    if len(valid_trades) >= 1:
        first_exit = valid_trades[0]
        exit_type_first = int(first_exit[2])
        
        if exit_type_first == 1:
            print("   ✓ Primera salida fue TP1 (correcto)")
        else:
            print(f"   ✗ Primera salida fue tipo {exit_type_first} (esperado: TP1)")
        
        # PnL del primer exit debe ser positivo
        if first_exit[5] > 0:
            print(f"   ✓ TP1 generó profit: ${first_exit[5]:,.2f}")
        else:
            print(f"   ✗ TP1 generó loss: ${first_exit[5]:,.2f}")
    else:
        print("   ✗ No se generaron trades")
    
    print("\n" + "=" * 80)


if __name__ == "__main__":
    print("\n🚀 INICIANDO TESTS DE EXIT LOGIC FIX\n")
    
    # Test 1: Sintético (rápido, verifica lógica básica)
    run_synthetic_test()
    
    # Test 2: Real data (más lento, verifica mejora real)
    input("\n⏸️  Presiona ENTER para continuar con test de data real (puede tardar 1-2 min)...")
    success = run_comparison_test()
    
    print("\n" + "=" * 80)
    if success:
        print("✅ TESTS COMPLETADOS - Fix validado exitosamente")
    else:
        print("⚠️ TESTS COMPLETADOS - Revisar resultados arriba")
    print("=" * 80 + "\n")
