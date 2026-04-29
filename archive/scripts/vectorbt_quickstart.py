#!/usr/bin/env python3
"""
Quick Start Guide - VectorBT Migration
--------------------------------------
Script de demostración rápida de las nuevas capacidades
"""

import time

def demo_basic():
    """Demo básico: Speed comparison"""
    print("\n" + "="*80)
    print("🎬 DEMO 1: SPEED COMPARISON")
    print("="*80)
    
    tickers = ['SPY', 'AAPL', 'MSFT', 'NVDA', 'TSLA']
    
    print(f"\n🎯 Testing {len(tickers)} tickers for 2021...")
    print(f"   Tickers: {', '.join(tickers)}")
    
    from src.backtest.vectorbt_engine import run_vectorbt_backtest
    
    start = time.time()
    results = run_vectorbt_backtest(
        universe=tickers,
        start_date='2021-01-01',
        end_date='2021-12-31',
        initial_capital=100000,
        risk_pct=0.5,
        max_exposure=25.0
    )
    elapsed = time.time() - start
    
    print(f"\n✅ Completed in {elapsed:.2f} seconds")
    print(f"   Total Return: {results['total_return']*100:+.2f}%")
    print(f"   Win Rate: {results['win_rate']*100:.1f}%")
    print(f"   Trades: {results['total_trades']}")

def demo_advanced():
    """Demo avanzado: Partial exits"""
    print("\n" + "="*80)
    print("🎬 DEMO 2: PARTIAL EXITS (2-PHASE SYSTEM)")
    print("="*80)
    
    tickers = ['TSLA', 'NVDA', 'AMD', 'MRNA', 'LCID']
    
    print(f"\n🎯 Testing {len(tickers)} tickers with TP1/TP2 system...")
    
    from src.backtest.vectorbt_engine_advanced import AdvancedVectorBTEngine
    
    engine = AdvancedVectorBTEngine(
        universe=tickers,
        start_date='2021-01-01',
        end_date='2021-12-31',
        initial_capital=100000,
        risk_pct=0.005,
        max_exposure_pct=0.25
    )
    
    start = time.time()
    results = engine.run_backtest()
    elapsed = time.time() - start
    engine.cleanup()
    
    print(f"\n✅ Completed in {elapsed:.2f} seconds")
    print(f"   Total Return: {results['total_return']*100:+.2f}%")
    print(f"   Win Rate: {results['win_rate']*100:.1f}%")
    
    trades = results['trades']
    if len(trades) > 0:
        tp1 = len(trades[trades['phase'] == 'TP1'])
        tp2 = len(trades[trades['phase'] == 'TP2'])
        stops = len(trades[trades['phase'] == 'STOP'])
        
        print(f"\n📦 Exit Breakdown:")
        print(f"   TP1 (1.5R): {tp1} exits")
        print(f"   TP2 (3R): {tp2} exits")
        print(f"   Stops: {stops} exits")

def demo_scalability():
    """Demo escalabilidad: Many tickers"""
    print("\n" + "="*80)
    print("🎬 DEMO 3: SCALABILITY TEST")
    print("="*80)
    
    import sqlite3
    
    for limit in [10, 50, 100]:
        print(f"\n🔍 Testing top {limit} tickers...")
        
        conn = sqlite3.connect('./data/ticker_cache.db')
        query = """
        SELECT ticker FROM ohlcv_cache
        WHERE date BETWEEN '2021-01-01' AND '2021-12-31'
        GROUP BY ticker
        HAVING COUNT(*) >= 100
        ORDER BY AVG(dollar_volume) DESC
        LIMIT ?
        """
        cursor = conn.execute(query, (limit,))
        tickers = [row[0] for row in cursor.fetchall()]
        conn.close()
        
        from src.backtest.vectorbt_engine import run_vectorbt_backtest
        
        start = time.time()
        results = run_vectorbt_backtest(
            universe=tickers,
            start_date='2021-01-01',
            end_date='2021-12-31',
            initial_capital=100000,
            risk_pct=0.5,
            max_exposure=25.0
        )
        elapsed = time.time() - start
        
        print(f"   ⏱️  {elapsed:.2f}s | Trades: {results['total_trades']} | Return: {results['total_return']*100:+.2f}%")

def main():
    print("="*80)
    print("🚀 VECTORBT QUICK START DEMOS")
    print("="*80)
    print("\nEste script demuestra las capacidades del nuevo sistema vectorizado:")
    print("  1. Speed comparison")
    print("  2. Partial exits (TP1/TP2)")
    print("  3. Scalability test")
    print("\n")
    
    try:
        demo_basic()
        demo_advanced()
        demo_scalability()
        
        print("\n" + "="*80)
        print("✅ ALL DEMOS COMPLETED")
        print("="*80)
        print("\nPróximos pasos:")
        print("  1. Ver documentación completa: docs/VECTORBT_MIGRATION.md")
        print("  2. Ejecutar backtest custom: python3 backtest_vectorbt_advanced.py --help")
        print("  3. Comparar con motor original: python3 benchmark_engines.py")
        print("="*80)
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    main()
