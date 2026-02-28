#!/usr/bin/env python3
"""
Test rápido del EXIT LOGIC FIX con trailing stop activado

Compara resultados con trailing_stop OFF vs ON para validar mejoras
"""

import sys
from pathlib import Path
import warnings
warnings.filterwarnings('ignore')

sys.path.insert(0, str(Path(__file__).parent / "src"))

from backtest.vectorbt_engine_advanced import AdvancedVectorBTEngine

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Test Exit Logic Fix")
    parser.add_argument("--start", default="2024-11-01", help="Start date")
    parser.add_argument("--end", default="2024-12-31", help="End date")
    parser.add_argument("--tickers", nargs="+", 
                       default=["AAPL", "MSFT", "NVDA", "AMD", "TSLA", "GOOGL", "META", "AMZN"],
                       help="Tickers to test")
    parser.add_argument("--capital", type=float, default=100000, help="Initial capital")
    parser.add_argument("--trailing-stop", action="store_true", 
                       help="Activate trailing stop (default: compare both)")
    parser.add_argument("--compare", action="store_true", default=True,
                       help="Compare OFF vs ON (default)")
    
    args = parser.parse_args()
    
    print("=" * 80)
    print("🧪 EXIT LOGIC FIX - VALIDATION TEST")
    print("=" * 80)
    print(f"\n📊 Configuration:")
    print(f"   Period: {args.start} to {args.end}")
    print(f"   Tickers: {len(args.tickers)}")
    print(f"   Capital: ${args.capital:,.0f}")
    
    if not args.compare and args.trailing_stop:
        # Solo test con trailing stop ON
        print("\n🔧 Testing WITH trailing stop only...")
        run_test(args.tickers, args.start, args.end, args.capital, 
                use_trailing=True, label="WITH Trailing Stop")
    elif not args.compare:
        # Solo test con trailing stop OFF
        print("\n🔧 Testing WITHOUT trailing stop only...")
        run_test(args.tickers, args.start, args.end, args.capital,
                use_trailing=False, label="WITHOUT Trailing Stop")
    else:
        # Comparación completa
        print("\n📊 Running comparison: OFF vs ON\n")
        
        # Test 1: Sin trailing stop
        print("-" * 80)
        print("TEST 1: Trailing Stop = OFF (baseline)")
        print("-" * 80)
        results_off = run_test(args.tickers, args.start, args.end, args.capital,
                              use_trailing=False, label="OFF")
        
        # Test 2: Con trailing stop
        print("\n" + "-" * 80)
        print("TEST 2: Trailing Stop = ON (with exit fix)")
        print("-" * 80)
        results_on = run_test(args.tickers, args.start, args.end, args.capital,
                             use_trailing=True, label="ON")
        
        # Comparación
        if results_off and results_on:
            print("\n" + "=" * 80)
            print("📊 COMPARISON - Impact of Exit Logic Fix")
            print("=" * 80)
            
            compare_results(results_off, results_on)


def run_test(tickers, start, end, capital, use_trailing, label):
    """Run single backtest"""
    
    try:
        engine = AdvancedVectorBTEngine(
            universe=tickers,
            start_date=start,
            end_date=end,
            initial_capital=capital,
            use_trailing_stop=use_trailing,
            be_trailing_threshold=0.8 if use_trailing else 1.0,
            market_regime_filter=False,  # Simplify
            verbose=False
        )
        
        results = engine.run_backtest()
        
        if not results or 'trades' not in results:
            print(f"⚠️ No trades generated")
            return None
        
        trades = results['trades']
        
        # Calcular métricas
        total_trades = len(trades)
        tp1_exits = (trades['exit_type'] == 1).sum()
        tp2_exits = (trades['exit_type'] == 2).sum()
        stop_exits = (trades['exit_type'] == 0).sum()
        runner_exits = (trades['exit_type'] == 3).sum()
        
        wins = (trades['pnl'] > 0).sum()
        losses = (trades['pnl'] < 0).sum()
        
        tp1_rate = (tp1_exits / total_trades * 100) if total_trades > 0 else 0
        win_rate = (wins / total_trades * 100) if total_trades > 0 else 0
        
        avg_win = trades[trades['pnl'] > 0]['pnl'].mean() if wins > 0 else 0
        avg_loss = trades[trades['pnl'] < 0]['pnl'].mean() if losses > 0 else 0
        
        final_equity = results.get('final_equity', capital)
        total_return = ((final_equity - capital) / capital) * 100
        
        # Display
        print(f"\n📈 Results ({label}):")
        print(f"   Total Trades: {total_trades}")
        print(f"   Win Rate: {win_rate:.1f}% ({wins}W/{losses}L)")
        print(f"\n   Exit Distribution:")
        print(f"      TP1 (risk-free): {tp1_exits} ({tp1_rate:.1f}%)")
        print(f"      TP2: {tp2_exits}")
        print(f"      STOP: {stop_exits}")
        print(f"      RUNNER: {runner_exits}")
        print(f"\n   P&L:")
        print(f"      Avg Win: ${avg_win:,.2f}")
        print(f"      Avg Loss: ${avg_loss:,.2f}")
        print(f"      Total Return: {total_return:+.2f}%")
        print(f"      Final Equity: ${final_equity:,.0f}")
        
        return {
            'total_trades': total_trades,
            'tp1_rate': tp1_rate,
            'win_rate': win_rate,
            'avg_loss': avg_loss,
            'total_return': total_return,
            'final_equity': final_equity,
            'tp1_exits': tp1_exits,
            'tp2_exits': tp2_exits,
            'stop_exits': stop_exits,
            'trades': trades
        }
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return None


def compare_results(off, on):
    """Compare two result sets"""
    
    if not off or not on:
        print("⚠️ Cannot compare - one or both tests failed")
        return
    
    print(f"\nMetric                   | OFF         | ON          | Delta")
    print("-" * 70)
    
    # TP1 Rate
    delta_tp1 = on['tp1_rate'] - off['tp1_rate']
    print(f"TP1 Rate (risk-free)     | {off['tp1_rate']:6.1f}%     | {on['tp1_rate']:6.1f}%     | {delta_tp1:+6.1f}%")
    
    # Win Rate
    delta_wr = on['win_rate'] - off['win_rate']
    print(f"Win Rate                 | {off['win_rate']:6.1f}%     | {on['win_rate']:6.1f}%     | {delta_wr:+6.1f}%")
    
    # Avg Loss
    delta_loss = on['avg_loss'] - off['avg_loss']
    print(f"Avg Loss                 | ${off['avg_loss']:7.2f}   | ${on['avg_loss']:7.2f}   | ${delta_loss:+7.2f}")
    
    # Total Return
    delta_ret = on['total_return'] - off['total_return']
    print(f"Total Return             | {off['total_return']:6.1f}%     | {on['total_return']:6.1f}%     | {delta_ret:+6.1f}%")
    
    print("\n" + "=" * 80)
    
    # Evaluación
    improvements = 0
    
    if delta_tp1 > 5:  # Al menos 5% más trades a risk-free
        print("✅ TP1 Rate improved significantly")
        improvements += 1
    elif delta_tp1 > 0:
        print("⚠️ TP1 Rate improved slightly")
    else:
        print("❌ TP1 Rate did not improve")
    
    if delta_loss > 0:  # Avg loss menos negativo (mejora)
        print(f"✅ Avg Loss improved (less negative)")
        improvements += 1
    else:
        print("⚠️ Avg Loss did not improve")
    
    if delta_ret > 0:
        print(f"✅ Total Return improved")
        improvements += 1
    else:
        print("⚠️ Total Return did not improve")
    
    print("\n" + "=" * 80)
    
    if improvements >= 2:
        print("🎯 FIX VALIDATED - Significant improvements detected!")
        print(f"\nThe exit logic fix with trailing stop is working.")
        print(f"More trades reach risk-free (TP1) and avg losses reduced.")
    elif improvements == 1:
        print("⚠️ PARTIAL IMPROVEMENT - Some metrics improved")
        print("\nThe fix shows some benefit but results are mixed.")
        print("Consider testing on a longer period or different market conditions.")
    else:
        print("❌ NO CLEAR IMPROVEMENT")
        print("\nPossible causes:")
        print("  1. Market conditions in test period not suitable")
        print("  2. Sample size too small (try more tickers or longer period)")
        print("  3. Other configuration issues")
    
    print("\n" + "=" * 80)


if __name__ == "__main__":
    main()
