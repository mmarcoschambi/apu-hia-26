#!/usr/bin/env python3
"""
DATA ALIGNMENT TOOL - Para Bugatti EVO
======================================
Alinea todos los tickers al calendario de SPY.
Rellena gaps y elimina precios inválidos.

Author: Marcos
Date: 2026-01-10
"""

import pandas as pd
import sqlite3
import numpy as np
from pathlib import Path
from datetime import datetime

# --- CONFIGURACIÓN ---
DB_PATH = "./data/ticker_cache.db"  # Tu SQLite DB actual
SPY_TICKER = "SPY"

print(f"🧹 DATA ALIGNMENT TOOL")
print(f"📂 Database: {DB_PATH}")
print("="*80)

# Conectar a DB
conn = sqlite3.connect(DB_PATH)

# 1. CARGAR CALENDARIO MAESTRO (SPY)
print(f"📅 Loading master calendar from {SPY_TICKER}...")
try:
    spy_df = pd.read_sql_query(
        "SELECT date, close FROM ohlcv_cache WHERE ticker = ? ORDER BY date",
        conn,
        params=(SPY_TICKER,),
        parse_dates=['date']
    )
    
    if len(spy_df) == 0:
        raise ValueError(f"❌ No data for {SPY_TICKER} in database!")
    
    # Calendario maestro
    spy_df = spy_df.drop_duplicates(subset='date', keep='first')
    market_dates = spy_df['date'].values
    
    print(f"✅ Master Calendar: {len(market_dates)} trading days")
    print(f"   Range: {spy_df['date'].min().date()} to {spy_df['date'].max().date()}")
    
except Exception as e:
    print(f"❌ Error loading SPY: {e}")
    conn.close()
    exit(1)

# 2. OBTENER LISTA DE TODOS LOS TICKERS
print(f"\n🎯 Scanning universe...")
tickers = pd.read_sql_query(
    "SELECT DISTINCT ticker FROM ohlcv_cache WHERE ticker != ? ORDER BY ticker",
    conn,
    params=(SPY_TICKER,)
)['ticker'].tolist()

print(f"📊 Found {len(tickers)} tickers (excluding {SPY_TICKER})")

# 3. VALIDAR Y ARREGLAR CADA TICKER
print(f"\n🔧 Processing tickers...")
issues_found = []
tickers_fixed = 0
tickers_with_issues = 0

for i, ticker in enumerate(tickers):
    if i % 100 == 0:
        print(f"   Progress: {i}/{len(tickers)}...")
    
    try:
        # Cargar data del ticker
        df = pd.read_sql_query(
            """SELECT date, open, high, low, close, volume 
               FROM ohlcv_cache 
               WHERE ticker = ? 
               ORDER BY date""",
            conn,
            params=(ticker,),
            parse_dates=['date']
        )
        
        # Check if the stock has sufficient data considering its age
        data_start_date = df['date'].min()

        # Determine the market dates that fall within the stock's trading period
        market_dates_in_stock_period = [d for d in market_dates if pd.Timestamp(d) >= data_start_date]
        expected_possible_data_points = len(market_dates_in_stock_period)

        # Allow for stocks that started trading recently (less than 1 year) to have proportionally less data
        days_since_listing = (spy_df['date'].max() - data_start_date).days
        if days_since_listing < 365:  # Less than 1 year
            # For newer stocks, adjust the threshold - allow at least 30% of expected data
            adjusted_threshold = max(20, int(expected_possible_data_points * 0.3))
        else:
            # For older stocks, require more data
            adjusted_threshold = 100

        if len(df) < adjusted_threshold:
            issues_found.append(f"{ticker}: Insufficient data ({len(df)} rows) for period since listing on {data_start_date.date()} (threshold: {adjusted_threshold}, days since listing: {days_since_listing})")
            continue
        
        # Crear índice completo con todas las fechas de mercado
        df = df.drop_duplicates(subset='date', keep='first')
        df = df.set_index('date')
        
        # Identificar fechas faltantes
        ticker_dates = set(df.index)
        missing_dates = [d for d in market_dates if pd.Timestamp(d) not in ticker_dates]
        
        # Reindex para alinear con el mercado
        df_aligned = df.reindex(pd.DatetimeIndex(market_dates))
        
        # Forward fill para rellenar gaps (usa precio anterior)
        df_aligned = df_aligned.ffill()
        
        # Verificar precios inválidos (<=0, NaN, inf)
        price_cols = ['open', 'high', 'low', 'close']
        invalid_mask = (
            (df_aligned[price_cols] <= 0).any(axis=1) | 
            df_aligned[price_cols].isna().any(axis=1) |
            np.isinf(df_aligned[price_cols]).any(axis=1)
        )
        
        n_invalid = invalid_mask.sum()
        n_missing = len(missing_dates)
        
        if n_missing > 0 or n_invalid > 0:
            tickers_with_issues += 1
            
            if n_missing > len(market_dates) * 0.3:  # >30% missing
                issues_found.append(f"{ticker}: {n_missing} gaps ({n_missing/len(market_dates)*100:.1f}%)")
            
            if n_invalid > 0:
                # Reemplazar inválidos con ffill/bfill
                df_aligned[price_cols] = df_aligned[price_cols].replace([np.inf, -np.inf], np.nan)
                df_aligned[price_cols] = df_aligned[price_cols].ffill().bfill()
                
                # Si aún hay NaNs, usar close del día anterior * 1.0
                if df_aligned[price_cols].isna().any().any():
                    issues_found.append(f"{ticker}: {n_invalid} precios inválidos (crítico)")
                    continue
            
            # UPDATE EN LA DB (solo si hay cambios)
            df_aligned = df_aligned.reset_index()
            df_aligned.columns = ['date'] + list(df_aligned.columns[1:])
            
            # Borrar data vieja
            conn.execute("DELETE FROM ohlcv_cache WHERE ticker = ?", (ticker,))
            
            # Insertar data limpia
            for _, row in df_aligned.iterrows():
                conn.execute(
                    """INSERT INTO ohlcv_cache (ticker, date, open, high, low, close, volume)
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (ticker, row['date'], row['open'], row['high'], row['low'], 
                     row['close'], row['volume'])
                )
            
            tickers_fixed += 1
            
            if tickers_fixed % 50 == 0:
                conn.commit()  # Commit cada 50 tickers
    
    except Exception as e:
        issues_found.append(f"{ticker}: Error - {str(e)[:50]}")

# Commit final
conn.commit()
conn.close()

print(f"\n{'='*80}")
print(f"✅ COMPLETED!")
print(f"   Tickers processed: {len(tickers)}")
print(f"   Tickers with issues: {tickers_with_issues}")
print(f"   Tickers fixed: {tickers_fixed}")
print(f"   Critical issues: {len(issues_found)}")

if issues_found:
    print(f"\n⚠️  ISSUES FOUND (showing first 20):")
    for issue in issues_found[:20]:
        print(f"   • {issue}")
    
    # Guardar reporte completo
    report_path = Path('outputs/data_alignment_report.txt')
    report_path.parent.mkdir(parents=True, exist_ok=True)
    with open(report_path, 'w') as f:
        f.write(f"Data Alignment Report - {datetime.now()}\n")
        f.write("="*80 + "\n\n")
        for issue in issues_found:
            f.write(f"{issue}\n")
    print(f"\n💾 Full report saved to: {report_path}")

print(f"\n🏎️  Your data is now aligned for Bugatti EVO!")
