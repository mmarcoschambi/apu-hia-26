#!/usr/bin/env python3
"""
Quick backtest to verify trend filter is working
This will show rejected trades in the logs
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from src.backtest.daily_engine import DailyBacktestEngine
import logging

# Setup logging to see rejections
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

def run_test_backtest():
    print("=" * 80)
    print("🧪 TESTING TREND FILTER FOR BLUE SKY BREAKOUTS")
    print("=" * 80)
    print()
    
    # Test on same symbols that had Weak trend
    test_symbols = ['MU', 'GH', 'COHR', 'LITE', 'EXAS']
    
    print(f"📊 Testing symbols: {', '.join(test_symbols)}")
    print(f"📅 Period: 2020-12-15 to 2021-02-28")
    print()
    print("🔍 Looking for REJECTED Blue Sky signals with Weak trend...")
    print("=" * 80)
    print()
    
    # Create risk manager
    from src.utils.risk_calculator import RiskManager
    risk_manager = RiskManager(account_equity=50000, risk_pct=0.01, max_positions=5)
    
    # Create engine
    engine = DailyBacktestEngine(
        universe=test_symbols,
        start_date='2020-12-15',
        end_date='2021-02-28',
        risk_manager=risk_manager,
        skip_filters=True  # Skip filters to test trend-specific filter
    )
    
    # Run backtest
    try:
        results = engine.run()
        
        print()
        print("=" * 80)
        print("📊 BACKTEST RESULTS")
        print("=" * 80)
        
        if results and not results.empty:
            # Filter for Blue Sky trades
            blue_sky = results[results['signal_type'].str.contains('BLUE_SKY', na=False)]
            
            print(f"\n✅ Total trades executed: {len(results)}")
            print(f"🚀 Blue Sky trades: {len(blue_sky)}")
            
            if not blue_sky.empty:
                print("\n📋 Blue Sky Trades Details:")
                for idx, row in blue_sky.iterrows():
                    trend = row.get('context_trend', 'Unknown')
                    symbol = row['symbol']
                    entry_date = row['entry_date']
                    returns = row['returns_pct']
                    
                    status = "✅" if trend == 'Uptrend' else "⚠️"
                    print(f"  {status} {symbol} | {entry_date} | Trend: {trend} | Return: {returns:+.2f}%")
            
            # Check for weak trends that got through (shouldn't happen)
            weak_blue_sky = blue_sky[blue_sky.get('context_trend', '') == 'Weak']
            if not weak_blue_sky.empty:
                print(f"\n❌ ERROR: Found {len(weak_blue_sky)} Blue Sky trades with Weak trend!")
                print("   These should have been REJECTED by the filter!")
            else:
                print(f"\n✅ SUCCESS: No Blue Sky trades with Weak trend found!")
                print("   Filter is working correctly!")
        else:
            print("\n⚠️  No trades executed in this period")
            
        print()
        print("💾 Results saved to: outputs/backtests/backtest_results.csv")
        
    except Exception as e:
        print(f"\n❌ Error running backtest: {e}")
        import traceback
        traceback.print_exc()
    
    print()
    print("=" * 80)
    print("🏁 Test Complete - Check logs above for REJECTED signals")
    print("=" * 80)

if __name__ == "__main__":
    run_test_backtest()
