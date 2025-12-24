#!/usr/bin/env python3
"""
Test script to verify OpenBB can fetch historical intraday data
Testing: MU on 2021-01-20
"""

from src.data.openbb_data import OpenBBData
from datetime import datetime, timedelta
import pandas as pd

def test_historical_intraday():
    print("=" * 70)
    print("🧪 TEST: OpenBB Historical Intraday Data")
    print("=" * 70)
    
    # Test parameters
    symbol = "MU"
    target_date = "2021-01-20"
    intervals = ["5m", "15m", "30m", "1h"]
    
    openbb = OpenBBData()
    
    # Calculate date range (1 day before and after for context)
    target_dt = datetime.strptime(target_date, '%Y-%m-%d')
    start_date = (target_dt - timedelta(days=1)).strftime('%Y-%m-%d')
    end_date = (target_dt + timedelta(days=1)).strftime('%Y-%m-%d')
    
    print(f"\n📊 Symbol: {symbol}")
    print(f"📅 Target Date: {target_date}")
    print(f"🔍 Date Range: {start_date} to {end_date}")
    print(f"⏰ Today: {datetime.now().strftime('%Y-%m-%d')}")
    print(f"📆 Days Ago: {(datetime.now() - target_dt).days} days")
    print("\n" + "-" * 70)
    
    for interval in intervals:
        print(f"\n⏱️  Testing interval: {interval}")
        print("-" * 50)
        
        try:
            df = openbb.get_intraday_data(
                symbol=symbol,
                start_date=start_date,
                end_date=end_date,
                interval=interval
            )
            
            if df is not None and not df.empty:
                # Filter for target date
                df_target = df[df.index.strftime('%Y-%m-%d') == target_date]
                
                print(f"✅ SUCCESS!")
                print(f"   Total records retrieved: {len(df)}")
                print(f"   Records for {target_date}: {len(df_target)}")
                print(f"   Date range: {df.index.min()} to {df.index.max()}")
                print(f"   Columns: {list(df.columns)}")
                
                if not df_target.empty:
                    print(f"\n   📈 Sample data for {target_date}:")
                    print(f"   First bar: {df_target.index[0]}")
                    print(f"   Last bar:  {df_target.index[-1]}")
                    print(f"   Open:  ${df_target.iloc[0]['open']:.2f}")
                    print(f"   High:  ${df_target['high'].max():.2f}")
                    print(f"   Low:   ${df_target['low'].min():.2f}")
                    print(f"   Close: ${df_target.iloc[-1]['close']:.2f}")
                else:
                    print(f"   ⚠️  No data for specific date {target_date}")
            else:
                print(f"❌ FAILED: No data returned")
                
        except Exception as e:
            print(f"❌ ERROR: {str(e)}")
    
    print("\n" + "=" * 70)
    print("🏁 Test Complete")
    print("=" * 70)

if __name__ == "__main__":
    test_historical_intraday()
