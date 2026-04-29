#!/usr/bin/env python3
"""
Script rápido para poblar datos OHLCV con yfinance
"""

import sqlite3
import yfinance as yf
import pandas as pd
import argparse
from datetime import datetime, timedelta
from pathlib import Path
from tqdm import tqdm

def setup_database(db_path='data/ticker_cache.db'):
    conn = sqlite3.connect(db_path)
    conn.execute('''
        CREATE TABLE IF NOT EXISTS ohlcv_cache (
            ticker TEXT,
            date DATE,
            open REAL,
            high REAL,
            low REAL,
            close REAL,
            volume INTEGER,
            dollar_volume REAL,
            PRIMARY KEY (ticker, date)
        )
    ''')
    conn.commit()
    return conn

def process_ticker(conn, ticker, start_date, end_date):
    try:
        df = yf.download(ticker, start=start_date, end=end_date, progress=False, auto_adjust=True)
        if df.empty or len(df) < 50:
            return False
        
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        
        df['dollar_volume'] = df['Close'] * df['Volume']
        
        data = []
        for date, row in df.iterrows():
            data.append((
                ticker,
                date.strftime('%Y-%m-%d'),
                float(row['Open']),
                float(row['High']),
                float(row['Low']),
                float(row['Close']),
                int(row['Volume']),
                float(row['dollar_volume'])
            ))
        
        conn.executemany('''
            INSERT OR REPLACE INTO ohlcv_cache 
            (ticker, date, open, high, low, close, volume, dollar_volume)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', data)
        conn.commit()
        return True
    except Exception as e:
        print(f"Error {ticker}: {e}")
        return False

def main():
    parser = argparse.ArgumentParser(description='Poblar datos históricos OHLCV')
    parser.add_argument('--years', type=int, default=2, help='Años de historia a descargar (default: 2)')
    parser.add_argument('--tickers', nargs='+', help='Lista específica de tickers (opcional)')
    
    args = parser.parse_args()
    
    if args.tickers:
        tickers = args.tickers
        print(f"📊 {len(tickers)} tickers específicos")
    else:
        ticker_file = Path("top_global_tickers.txt")
        
        if not ticker_file.exists():
            print("❌ No se encontró top_global_tickers.txt")
            return
        
        with open(ticker_file, 'r') as f:
            tickers = [line.strip() for line in f if line.strip()]
        
        print(f"📊 {len(tickers)} tickers")
    
    conn = setup_database()
    
    years = args.years
    end_date = datetime.now().strftime('%Y-%m-%d')
    start_date = (datetime.now() - timedelta(days=years*365)).strftime('%Y-%m-%d')
    print(f"📅 {start_date} -> {end_date} ({years} años)")
    
    success = 0
    for ticker in tqdm(tickers):
        if process_ticker(conn, ticker, start_date, end_date):
            success += 1
    
    print(f"\n✅ {success}/{len(tickers)} exitosos")
    conn.close()

if __name__ == "__main__":
    main()
