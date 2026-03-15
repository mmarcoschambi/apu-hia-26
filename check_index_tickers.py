#!/usr/bin/env python3
"""
check_index_tickers.py
=======================
Fetches the current S&P 500 and Russell 1000 constituents from Wikipedia
and compares them against the local SQLite database to find any missing tickers.
This is useful for the live scanner to ensure no "monster stocks" are missed.
"""

import sqlite3
import pandas as pd
import requests
import io
from pathlib import Path

# Paths
PROJECT_ROOT = Path(__file__).resolve().parent
DB_PATH = PROJECT_ROOT / "data" / "ticker_cache.db"
OUTPUT_FILE = PROJECT_ROOT / "new_tickers_today.txt"

def get_sp500_tickers():
    print("Fetching S&P 500 constituents from Wikipedia...")
    url = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        html = requests.get(url, headers=headers, timeout=10).text
        df = pd.read_html(io.StringIO(html))[0]
        tickers = df["Symbol"].tolist()
        # Clean tickers: BRK.B -> BRK-B
        tickers = [t.replace(".", "-") for t in tickers]
        print(f"  Found {len(tickers)} S&P 500 tickers.")
        return set(tickers)
    except Exception as e:
        print(f"Error fetching S&P 500: {e}")
        return set()

def get_russell1000_tickers():
    print("Fetching Russell 1000 constituents from Wikipedia...")
    url = "https://en.wikipedia.org/wiki/Russell_1000_Index"
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        html = requests.get(url, headers=headers, timeout=10).text
        dfs = pd.read_html(io.StringIO(html))
        # The constituents table is usually the largest one on the page
        df = max(dfs, key=len)
        if "Symbol" in df.columns:
            tickers = df["Symbol"].dropna().astype(str).tolist()
            tickers = [t.replace(".", "-") for t in tickers]
            print(f"  Found {len(tickers)} Russell 1000 tickers.")
            return set(tickers)
        else:
            print("Could not find 'Symbol' column in Russell 1000 table.")
            return set()
    except Exception as e:
        print(f"Error fetching Russell 1000: {e}")
        return set()

def get_cached_tickers():
    print("Fetching tickers currently in local database...")
    if not DB_PATH.exists():
        print(f"Database not found at {DB_PATH}")
        return set()
    
    try:
        conn = sqlite3.connect(DB_PATH)
        # Fetch tickers that have at least some recent data
        query = "SELECT DISTINCT ticker FROM ohlcv_cache"
        cursor = conn.execute(query)
        tickers = [row[0] for row in cursor.fetchall()]
        conn.close()
        print(f"  Found {len(tickers)} unique tickers in database.")
        return set(tickers)
    except Exception as e:
        print(f"Error reading database: {e}")
        return set()

def main():
    sp500 = get_sp500_tickers()
    russell = get_russell1000_tickers()
    
    index_tickers = sp500.union(russell)
    print(f"\nTotal unique index tickers (S&P 500 + Russell 1000): {len(index_tickers)}")
    
    cached_tickers = get_cached_tickers()
    
    if not cached_tickers:
        print("Cannot compare. Exiting.")
        return
    
    missing_tickers = index_tickers - cached_tickers
    
    print("\n" + "="*50)
    print(f"MISSING TICKERS ANALYSIS")
    print("="*50)
    
    if len(missing_tickers) == 0:
        print("✅ Awesome! Your database already has all current S&P 500 and Russell 1000 constituents.")
    else:
        print(f"⚠️  Missing {len(missing_tickers)} tickers from your local DB:")
        missing_sorted = sorted(list(missing_tickers))
        print(", ".join(missing_sorted[:50]) + ("..." if len(missing_sorted) > 50 else ""))
        
        # Save to file
        with open(OUTPUT_FILE, "w") as f:
            for t in missing_sorted:
                f.write(f"{t}\n")
        print(f"\n💾 Saved missing tickers to {OUTPUT_FILE}")
        print("You can add them to your DB using a population script, for example by copying them into populate_custom_list.py or passing the file to your API downloader.")

if __name__ == "__main__":
    main()
