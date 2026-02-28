#!/usr/bin/env python3
"""
Add Tickers to Database - Dynamic Version
==========================================
Descarga tickers desde archivo, lista, o argumentos CLI.

Usage:
    python3 add_tickers_quick.py AAPL MSFT GOOGL
    python3 add_tickers_quick.py --tickers "AAPL, MSFT, GOOGL"
    python3 add_tickers_quick.py --file tickers.txt
    python3 add_tickers_quick.py --interactive
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))

import yfinance as yf
from src.data.ticker_cache import TickerCache
import pandas as pd
import time
import argparse
from typing import List


def load_tickers_from_file(filepath: str) -> List[str]:
    """Carga tickers desde archivo."""
    with open(filepath, 'r') as f:
        content = f.read()
    
    tickers = []
    for line in content.split('\n'):
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        tickers.extend([t.strip() for t in line.replace(',', ' ').split()])
    
    return [t.upper() for t in tickers if t]


def populate_ticker(ticker: str, start_date: str, end_date: str, cache: TickerCache) -> bool:
    """Descarga y guarda data para un ticker."""
    try:
        df = yf.download(ticker, start=start_date, end=end_date, progress=False)
        
        if df is None or len(df) == 0:
            return False
        
        # Normalize columns
        df.columns = [col[0] if isinstance(col, tuple) else col for col in df.columns]
        df.columns = df.columns.str.capitalize()
        
        df = df.reset_index()
        df.columns = [col.lower() for col in df.columns]
        
        # Convert date to string
        if 'date' in df.columns:
            df['date'] = pd.to_datetime(df['date']).dt.strftime('%Y-%m-%d')
        
        # Clean data
        df = df.replace([float('inf'), float('-inf')], None)
        df = df.where(pd.notna(df), None)
        
        # Store
        for _, row in df.iterrows():
            try:
                cache.conn.execute(
                    """INSERT OR REPLACE INTO ohlcv_cache 
                       (ticker, date, open, high, low, close, volume)
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (
                        ticker, 
                        str(row['date']), 
                        float(row['open']) if row['open'] is not None else None,
                        float(row['high']) if row['high'] is not None else None,
                        float(row['low']) if row['low'] is not None else None,
                        float(row['close']) if row['close'] is not None else None,
                        int(row['volume']) if row['volume'] is not None else 0
                    )
                )
            except:
                continue
        
        cache.conn.commit()
        return True
    except:
        return False


def main():
    parser = argparse.ArgumentParser(description='Add tickers dynamically')
    parser.add_argument('tickers', nargs='*', help='Tickers (space separated)')
    parser.add_argument('--file', help='Load from file')
    parser.add_argument('--tickers', dest='ticker_list', help='Comma-separated list')
    parser.add_argument('--interactive', '-i', action='store_true', help='Interactive mode')
    parser.add_argument('--start-date', default='2020-01-01')
    parser.add_argument('--end-date', default='2024-12-31')
    parser.add_argument('--skip-existing', action='store_true')
    parser.add_argument('--batch-size', type=int, default=10, help='Sleep after N tickers')
    
    args = parser.parse_args()
    
    # Collect tickers
    tickers = []
    
    if args.tickers:
        tickers.extend(args.tickers)
    
    if args.ticker_list:
        tickers.extend([t.strip() for t in args.ticker_list.replace(',', ' ').split()])
    
    if args.file:
        print(f"📂 Loading from: {args.file}")
        tickers.extend(load_tickers_from_file(args.file))
    
    if args.interactive:
        print("📝 INTERACTIVE MODE - Paste your list")
        print("Press Ctrl+D when done:\n")
        
        lines = []
        try:
            while True:
                lines.append(input())
        except EOFError:
            pass
        
        content = '\n'.join(lines)
        for line in content.split('\n'):
            line = line.strip()
            if line and not line.startswith('#'):
                tickers.extend([t.strip() for t in line.replace(',', ' ').split()])
    
    # Clean
    tickers = sorted(set([t.upper() for t in tickers if t]))
    
    if not tickers:
        print("❌ No tickers provided!")
        parser.print_help()
        return 1
    
    print(f"\n🏎️ ADD TICKERS TO DATABASE")
    print(f"="*60)
    print(f"📊 Tickers to process: {len(tickers)}")
    print(f"📅 Period: {args.start_date} → {args.end_date}")
    print(f"="*60)
    
    cache = TickerCache()
    
    # Check existing
    if args.skip_existing:
        query = 'SELECT DISTINCT ticker FROM ohlcv_cache'
        existing = set([row[0] for row in cache.conn.execute(query).fetchall()])
        to_download = [t for t in tickers if t not in existing]
        
        print(f"\n✅ Already in DB: {len(tickers) - len(to_download)}")
        print(f"📥 To download: {len(to_download)}")
        
        tickers = to_download
    
    if not tickers:
        print(f"\n✅ All tickers already in DB!")
        return 0
    
    print(f"\n⏱️  Est. time: ~{len(tickers) * 6 / 60:.1f} minutes")
    
    # Download
    print(f"\n📥 Downloading...\n")
    start_time = time.time()
    success = 0
    failed = []
    
    for i, ticker in enumerate(tickers, 1):
        print(f"[{i}/{len(tickers)}] {ticker:6s} ... ", end="", flush=True)
        
        if populate_ticker(ticker, args.start_date, args.end_date, cache):
            print(f"✅")
            success += 1
        else:
            print(f"❌")
            failed.append(ticker)
        
        # Rate limiting
        if i % args.batch_size == 0:
            print(f"\n⏸️  Batch {i}/{len(tickers)} done. Sleeping 2s...\n")
            time.sleep(2)
        else:
            time.sleep(0.5)
    
    elapsed = time.time() - start_time
    
    # Summary
    print(f"\n{'='*60}")
    print(f"✅ COMPLETED!")
    print(f"{'='*60}")
    print(f"   Success: {success}/{len(tickers)} ({success/len(tickers)*100:.1f}%)")
    print(f"   Failed: {len(failed)}")
    print(f"   Time: {elapsed/60:.1f} minutes")
    
    if failed:
        print(f"\n❌ Failed: {', '.join(failed[:20])}")
        if len(failed) > 20:
            print(f"   ... and {len(failed)-20} more")
        
        with open('failed_tickers.txt', 'w') as f:
            f.write('\n'.join(failed))
        print(f"💾 Saved to: failed_tickers.txt")
    
    # Final count
    query = "SELECT COUNT(DISTINCT ticker) FROM ohlcv_cache"
    total = cache.conn.execute(query).fetchone()[0]
    print(f"\n📊 Total in DB: {total}")
    
    # Suggest fold-size
    suggested = min(int(total * 0.75), 300)
    print(f"💡 Suggested fold-size: {suggested}")
    print(f"\n🏎️ Ready for Bugatti EVO!")
    
    return 0


if __name__ == '__main__':
    sys.exit(main())
