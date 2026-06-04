import sqlite3
import pandas as pd
import numpy as np
from pathlib import Path
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DB_PATH = Path("data/ticker_cache.db")

def sandbox_analysis():
    conn = sqlite3.connect(DB_PATH)
    
    # 1. Load trades (confirmed breakouts)
    query_breakouts = """
    SELECT date, ticker, sector_etf, close as price_entry
    FROM candidate_state
    WHERE close > breakout_level AND sector_etf != ''
    """
    df_trades = pd.read_sql_query(query_breakouts, conn)
    df_trades['date'] = pd.to_datetime(df_trades['date'])
    logger.info(f"Loaded {len(df_trades)} breakouts.")
    
    # 2. Load sector cohort data
    query_cohort = """
    SELECT date, sector_etf, score_delta_5d, rank_today
    FROM sector_cohort
    WHERE score_delta_5d IS NOT NULL
    """
    df_cohort = pd.read_sql_query(query_cohort, conn)
    df_cohort['date'] = pd.to_datetime(df_cohort['date'])
    
    # 3. Merge trades with cohort data
    df = df_trades.merge(df_cohort, on=['date', 'sector_etf'], how='inner')
    logger.info(f"Matched {len(df)} breakouts with cohort data.")
    
    # 4. Load all prices for these tickers to calculate returns (Optimized)
    tickers = df['ticker'].unique()
    tickers_str = "('" + "','".join(tickers) + "')"
    query_prices = f"SELECT ticker, date, close FROM ohlcv_cache WHERE ticker IN {tickers_str}"
    df_prices = pd.read_sql_query(query_prices, conn)
    df_prices['date'] = pd.to_datetime(df_prices['date'], errors='coerce')
    df_prices = df_prices.dropna(subset=['date']).sort_values(['ticker', 'date'])
    
    # Calculate 5d and 10d forward prices
    df_prices['price_5d'] = df_prices.groupby('ticker')['close'].shift(-5)
    df_prices['price_10d'] = df_prices.groupby('ticker')['close'].shift(-10)
    
    # Join forward prices back to trades
    df = df.merge(df_prices[['ticker', 'date', 'price_5d', 'price_10d']], on=['ticker', 'date'], how='left')
    
    # Calculate returns
    df['return_5d'] = (df['price_5d'] / df['price_entry'] - 1) * 100
    df['return_10d'] = (df['price_10d'] / df['price_entry'] - 1) * 100
    
    df = df.dropna(subset=['return_5d'])
    logger.info(f"Calculated returns for {len(df)} trades.")

    # 5. Group Analysis
    logger.info("--- SANDBOX RESULTS ---")
    
    # Group A: Positive Sector Momentum
    group_a = df[df['score_delta_5d'] > 0]
    # Group B: Negative Sector Momentum
    group_b = df[df['score_delta_5d'] <= 0]
    
    if len(group_a) > 0 and len(group_b) > 0:
        print(f"\nGroup A (Positive Sector Momentum) - N={len(group_a)}")
        print(f"  Avg 5d Return: {group_a['return_5d'].mean():.2f}%")
        print(f"  Win Rate (5d): {(group_a['return_5d'] > 0).mean()*100:.1f}%")
        print(f"  Median 5d Return: {group_a['return_5d'].median():.2f}%")

        print(f"\nGroup B (Negative/Neutral Sector Momentum) - N={len(group_b)}")
        print(f"  Avg 5d Return: {group_b['return_5d'].mean():.2f}%")
        print(f"  Win Rate (5d): {(group_b['return_5d'] > 0).mean()*100:.1f}%")
        print(f"  Median 5d Return: {group_b['return_5d'].median():.2f}%")

        edge = group_a['return_5d'].mean() - group_b['return_5d'].mean()
        print(f"\nEdge: {edge:.2f}% improvement in 5d return.")
    else:
        print("\nInsufficient data for comparison.")
    
    conn.close()

if __name__ == "__main__":
    sandbox_analysis()
