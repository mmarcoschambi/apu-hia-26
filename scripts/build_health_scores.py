import pandas as pd
import sqlite3
from pathlib import Path
import os

# Logic:
# health_score (0-7):
# 1. spy_above_ema20: SPY close > EMA20 → +2 pts
# 2. spy_above_sma50: SPY > SMA50 → +1 pt
# 3. spy_above_sma200: SPY > SMA200 → +1 pt
# 4. vix_below_20: VIX close < 20 → +1 pt
# 5. vix_stable: VIX hasn't risen >15% in 5 days → +1 pt
# 6. breadth_proxy: % of the 20 sectors ETF in ohlcv_cache that are over their SMA20 → +1 pt

# regime_mode: "ATTACK" (≥6), "DEFENSE_PARTIAL" (4-5), "DEFENSE_FULL" (<4)

DB_PATH = Path("data/ticker_cache.db")

def build_health_scores():
    if not DB_PATH.exists():
        print(f"Error: {DB_PATH} not found.")
        return

    conn = sqlite3.connect(DB_PATH)
    
    print("Loading SPY and VIX...")
    spy = pd.read_sql_query("SELECT date, close FROM ohlcv_cache WHERE ticker='SPY' ORDER BY date", conn)
    spy['date'] = pd.to_datetime(spy['date'], format='mixed').dt.normalize()
    spy = spy.drop_duplicates(subset=['date']).set_index('date')
    
    vix = pd.read_sql_query("SELECT date, close FROM ohlcv_cache WHERE ticker='^VIX' ORDER BY date", conn)
    vix['date'] = pd.to_datetime(vix['date'], format='mixed').dt.normalize()
    vix = vix.drop_duplicates(subset=['date']).set_index('date')
    
    print("Calculating SPY indicators...")
    spy['ema20'] = spy['close'].ewm(span=20, adjust=False).mean()
    spy['sma50'] = spy['close'].rolling(50).mean()
    spy['sma200'] = spy['close'].rolling(200).mean()
    
    print("Calculating VIX indicators...")
    vix['prev_5d'] = vix['close'].shift(5)
    
    # Sector breadth (Available in DB based on diagnostic)
    ETFS = ['XLK', 'XLF', 'XLV', 'XLE', 'XLY', 'XLP', 'XLI', 'XLB', 'XLRE', 'XLU', 'XLC', 'IWM', 'QQQ', 'DIA', 'SMH', 'XBI']
    
    print(f"Loading {len(ETFS)} sector ETFs for breadth...")
    sector_closes = {}
    for ticker in ETFS:
        df = pd.read_sql_query(f"SELECT date, close FROM ohlcv_cache WHERE ticker='{ticker}' ORDER BY date", conn)
        if not df.empty:
            df['date'] = pd.to_datetime(df['date'], format='mixed').dt.normalize()
            df = df.drop_duplicates(subset=['date']).set_index('date')
            sector_closes[ticker] = df['close']
    
    sectors_df = pd.DataFrame(sector_closes)
    # Reindex to SPY to ensure alignment
    sectors_df = sectors_df.reindex(spy.index).ffill()
    sectors_sma20 = sectors_df.rolling(20).mean()
    # Breadth: % of sectors above their SMA20
    breadth_pct = (sectors_df > sectors_sma20).mean(axis=1)
    
    print("Combining scores...")
    results = []
    # We need a bit of history for SMA200 and VIX shift
    for date, row in spy.iterrows():
        # Minimum lookback for SMA200
        if pd.isna(row['sma200']): continue
        
        # We need VIX for that date
        if date not in vix.index: continue
        v_row = vix.loc[date]
        
        score = 0
        s_ema20 = row['close'] > row['ema20']
        s_sma50 = row['close'] > row['sma50']
        s_sma200 = row['close'] > row['sma200']
        
        v_below_20 = v_row['close'] < 20
        v_stable = False
        if pd.notna(v_row['prev_5d']):
            # VIX not up > 15% in 5 days
            v_stable = v_row['close'] <= v_row['prev_5d'] * 1.15
        else:
            # If no prev_5d, assume stable for early rows
            v_stable = True
            
        b_val = breadth_pct.get(date, 0)
        # Breadth proxy point: If more than 50% of sectors are above SMA20
        b_proxy = b_val >= 0.5
        
        if s_ema20: score += 2
        if s_sma50: score += 1
        if s_sma200: score += 1
        if v_below_20: score += 1
        if v_stable: score += 1
        if b_proxy: score += 1
        
        regime = "DEFENSE_FULL"
        if score >= 6: regime = "ATTACK"
        elif score >= 4: regime = "DEFENSE_PARTIAL"
        
        results.append({
            'date': date.strftime('%Y-%m-%d'),
            'health_score': int(score),
            'regime_mode': regime,
            'spy_above_ema20': int(s_ema20),
            'vix_below_20': int(v_below_20),
            'breadth_proxy': int(b_proxy)
        })
    
    print(f"Saving {len(results)} rows to daily_health_scores...")
    res_df = pd.DataFrame(results)
    res_df.to_sql('daily_health_scores', conn, if_exists='replace', index=False)
    
    conn.execute("CREATE INDEX IF NOT EXISTS idx_health_date ON daily_health_scores(date)")
    
    conn.commit()
    conn.close()
    print("Build completed successfully.")

if __name__ == "__main__":
    build_health_scores()
