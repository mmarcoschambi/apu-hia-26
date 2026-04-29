import pandas as pd
import sqlite3
from pathlib import Path
from src.screeners.qullamaggie_momentum import QullamaggieMomentumScreener
from src.screeners.base import ScreenerConfig

def test_qullamaggie():
    conn = sqlite3.connect('data/ticker_cache.db')
    ticker = 'TSLA'
    df = pd.read_sql(f"SELECT * FROM ohlcv_cache WHERE ticker='{ticker}' ORDER BY date", conn)
    conn.close()
    
    df['date'] = pd.to_datetime(df['date'], format='mixed')
    df = df.set_index('date')
    
    # Simular una fecha de corte (ej. fin de 2020)
    cutoff = '2020-12-30'
    df_pit = df[:cutoff].tail(300) # Darle suficiente historia
    
    screener = QullamaggieMomentumScreener()
    # Usar config relajada
    screener.config.min_adr_pct = 1.0
    screener.config.params['min_rs_percentile'] = 80.0
    screener.config.params['min_trend_intensity'] = 101.0
    screener.config.params['require_ma_stack'] = False
    
    result = screener.scan(ticker, df_pit)
    
    print(f"--- Diagnóstico {ticker} en {cutoff} ---")
    print(f"Passed: {result.passed}")
    print(f"Reason: {result.reason}")
    print(f"Metrics: {result.metrics}")
    
    # Ver por qué falló el stack si fuera el caso
    c = df_pit['close']
    ema10 = screener.ensure_ma(df_pit, 10, kind='ema').iloc[-1]
    sma20 = screener.ensure_ma(df_pit, 20).iloc[-1]
    sma200 = screener.ensure_ma(df_pit, 200).iloc[-1]
    print(f"Price: {c.iloc[-1]:.2f}, EMA10: {ema10:.2f}, SMA20: {sma20:.2f}, SMA200: {sma200:.2f}")

if __name__ == "__main__":
    test_qullamaggie()
