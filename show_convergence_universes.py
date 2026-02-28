#!/usr/bin/env python3
"""
Show Available Universes for Convergence Testing
=================================================
Helper script to display universe options and ticker counts.
"""

import sqlite3
from pathlib import Path

print("=" * 80)
print("📊 AVAILABLE UNIVERSES FOR CONVERGENCE TESTING")
print("=" * 80)

# 1. Database universe
print("\n1️⃣  DATABASE UNIVERSE (--tickers all)")
print("   Source: data/ticker_cache.db")
try:
    conn = sqlite3.connect('./data/ticker_cache.db')
    cursor = conn.execute("""
        SELECT COUNT(DISTINCT ticker) 
        FROM ohlcv_cache 
        WHERE date >= date('now', '-3 years')
    """)
    count = cursor.fetchone()[0]
    conn.close()
    print(f"   Available tickers: ~{count} (last 3 years)")
    print(f"   Usage: --tickers all --limit 50")
    print(f"   Example: python3 debug_convergence.py --tickers all --limit 100")
except Exception as e:
    print(f"   ⚠️  Could not access database: {e}")

# 2. S&P 500 universe
print("\n2️⃣  S&P 500 UNIVERSE (--tickers spy)")
print("   Source: sp500_tickers_since_2014.txt")
sp500_file = Path('sp500_tickers_since_2014.txt')
if sp500_file.exists():
    with open(sp500_file, 'r') as f:
        tickers = [line.strip() for line in f if line.strip()]
    print(f"   Available tickers: {len(tickers)}")
    print(f"   Usage: --tickers spy")
    print(f"   Example: python3 debug_convergence.py --tickers spy --limit 50")
    print(f"   Sample: {', '.join(tickers[:10])}...")
else:
    print(f"   ⚠️  File not found (will use database as fallback)")

# 3. NASDAQ 100 proxy
print("\n3️⃣  NASDAQ-STYLE UNIVERSE (--tickers nasdaq100)")
print("   Source: Top liquid stocks from database")
print(f"   Usage: --tickers nasdaq100")
print(f"   Example: python3 debug_convergence.py --tickers nasdaq100 --limit 50")

# 4. Custom list
print("\n4️⃣  CUSTOM TICKER LIST")
print("   Source: Manual specification")
print(f"   Usage: --tickers AAPL,MSFT,NVDA,GOOGL,META")
print(f"   Example: python3 debug_convergence.py --tickers AAPL,MSFT,NVDA")

# Recommendations
print("\n" + "=" * 80)
print("💡 RECOMMENDATIONS")
print("=" * 80)

print("\n🚀 Quick Test (2-5 min):")
print("   python3 debug_convergence.py --tickers AAPL,MSFT,NVDA")

print("\n📊 Standard Test (10-20 min):")
print("   python3 debug_convergence.py --tickers all --limit 50")

print("\n🎯 Full S&P 500 Validation (30-60 min):")
print("   python3 debug_convergence.py --tickers spy")

print("\n💾 Match Streamlit Universe (20-40 min):")
print("   python3 debug_convergence.py --tickers all --limit 100")

print("\n" + "=" * 80)
print("⏱️  TIME ESTIMATES")
print("=" * 80)
print("  • Per ticker: ~5-15 seconds")
print("  • 10 tickers: ~1-3 minutes")
print("  • 50 tickers: ~5-15 minutes")
print("  • 100 tickers: ~10-30 minutes")
print("  • 500 tickers: ~45-120 minutes")

print("\n💡 TIP: Use --limit to control universe size and testing time")
print("=" * 80)
