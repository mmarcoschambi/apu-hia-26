#!/usr/bin/env python3
"""
Advanced VectorBT Runner with Partial Exits
--------------------------------------------
"""

import argparse
import time
import json
from datetime import datetime
from pathlib import Path

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--start', type=str, default='2021-01-01')
    parser.add_argument('--end', type=str, default='2021-12-31')
    parser.add_argument('--equity', type=float, default=100000)
    parser.add_argument('--risk', type=float, default=0.5)
    parser.add_argument('--max_exp', type=float, default=25)
    parser.add_argument('--tickers', type=str, help='Comma-separated tickers')
    parser.add_argument('--limit', type=int, default=50)
    parser.add_argument('--mode', type=str, default='production', choices=['production', 'convergence'], 
                       help='Run mode: production (Percent Risk + Compounding) or convergence (Fixed Risk + THOR Logic)')
    parser.add_argument('--no-validated', action='store_true', help='Ignore config/validated_production_params.json')
    
    args = parser.parse_args()
    
    print("="*80)
    print(f"🚀 ADVANCED VECTORBT - {args.mode.upper()} MODE")
    print("="*80)
    print(f"📅 Period: {args.start} to {args.end}")
    print(f"💰 Capital: ${args.equity:,.0f}")
    
    if args.mode == 'convergence':
        print(f"⚠️  Risk: $150 Fixed (THOR Convergence)")
        print(f"   NOTE: Convergence mode uses fixed dollar risk for signal validation.")
        print(f"   Use 'production' mode for realistic P&L with compounding.")
    else:
        print(f"⚠️  Risk: {args.risk}% (Compounding)")
        
    print(f"📊 Max Exposure: {args.max_exp}%")
    print("="*80)
    
    # Build universe
    if args.tickers:
        universe = [t.strip().upper() for t in args.tickers.split(',')]
    else:
        import sqlite3
        conn = sqlite3.connect('./data/ticker_cache.db')
        query = """
        SELECT ticker, AVG(dollar_volume) as avg_dv
        FROM ohlcv_cache
        WHERE date BETWEEN ? AND ?
        GROUP BY ticker
        HAVING COUNT(*) >= 100
        ORDER BY avg_dv DESC
        LIMIT ?
        """
        cursor = conn.execute(query, (args.start, args.end, args.limit))
        universe = [row[0] for row in cursor.fetchall()]
        conn.close()
    
    print(f"🎯 Universe: {len(universe)} tickers")
    print(f"   {', '.join(universe[:10])}{'...' if len(universe) > 10 else ''}")
    print("="*80)
    
    # Use centralized mode configuration
    from config.advanced_engine_modes import get_engine_kwargs
    
    # Build overrides from command-line args
    overrides = {
        'initial_capital': args.equity,
        'max_exposure_pct': args.max_exp / 100,
    }
    
    # In production mode, allow risk_pct override (convergence mode ignores it)
    if args.mode == 'production' and not args.no_validated:
        # Let get_engine_kwargs load validated params
        pass
    elif args.mode == 'production':
        # Override with command-line risk
        overrides['risk_pct'] = args.risk / 100
    
    # Get complete engine configuration from centralized module
    engine_kwargs = get_engine_kwargs(
        mode=args.mode,
        universe=universe,
        start_date=args.start,
        end_date=args.end,
        **overrides
    )
    
    # Show loaded configuration
    if args.mode == 'production':
        print(f"\n✅ Using centralized PRODUCTION configuration")
        if not args.no_validated:
            print(f"   (Validated params automatically loaded if available)")
        print(f"   Risk: {engine_kwargs.get('risk_pct', 0)*100:.2f}%")
    else:
        print(f"\n✅ Using centralized CONVERGENCE configuration")
        print(f"   Risk: ${engine_kwargs.get('risk_dollars', 150):.0f} Fixed")
    
    print(f"   Filters: {'Baseline' if args.mode == 'convergence' else 'Professional'}")
    print("="*80)
    
    # Run backtest
    from src.backtest.vectorbt_engine_advanced import AdvancedVectorBTEngine
    
    start_time = time.time()
    
    engine = AdvancedVectorBTEngine(**engine_kwargs)
    
    try:
        results = engine.run_backtest()
        elapsed = time.time() - start_time
        
        print("\n" + "="*80)
        print("📊 RESULTS WITH PARTIAL EXITS")
        print("="*80)
        print(f"⏱️  Time: {elapsed:.2f}s")
        print(f"💹 Return: {results['total_return']*100:+.2f}%")
        print(f"📈 Sharpe: {results['sharpe_ratio']:.2f}")
        print(f"📉 Max DD: {results['max_drawdown']*100:.2f}%")
        print(f"✅ Win Rate: {results['win_rate']*100:.1f}%")
        print(f"📝 Total Exits: {results['total_trades']}")
        print("="*80)
        
        # Show trade breakdown
        trades = results['trades']
        if len(trades) > 0:
            print("\n📦 TRADE BREAKDOWN:")
            tp1_trades = trades[trades['exit_phase'] == 'TP1']
            tp2_trades = trades[trades['exit_phase'] == 'TP2']
            runner_trades = trades[trades['exit_phase'] == 'RUNNER']
            stop_trades = trades[trades['exit_phase'].str.contains('STOP', na=False)]
            
            print(f"   TP1 (1.5R): {len(tp1_trades)} exits, ${tp1_trades['pnl'].sum():.2f}")
            print(f"   TP2 (3R): {len(tp2_trades)} exits, ${tp2_trades['pnl'].sum():.2f}")
            print(f"   Runners:    {len(runner_trades)} exits, ${runner_trades['pnl'].sum():.2f}")
            print(f"   Stops:      {len(stop_trades)} exits, ${stop_trades['pnl'].sum():.2f}")
            
            # Save
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            output_file = f"outputs/advanced_trades_{timestamp}.csv"
            trades.to_csv(output_file, index=False)
            print(f"\n💾 Saved: {output_file}")
            
            equity_file = f"outputs/advanced_equity_{timestamp}.csv"
            results['equity_curve'].to_csv(equity_file)
            print(f"💾 Saved: {equity_file}")
        
    finally:
        engine.cleanup()
    
    return 0

if __name__ == '__main__':
    exit(main())
