#!/usr/bin/env python3
import sys
from pathlib import Path
import json
import pandas as pd
import numpy as np
import yfinance as yf
import sqlite3
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.backtest.vectorbt_engine_advanced import AdvancedVectorBTEngine
from scripts.walk_forward_combos import WF_FOLDS, load_combo_params, build_engine_kwargs, get_universe_from_db

SECTOR_TO_ETF = {
    'Technology': 'XLK',
    'Financial': 'XLF',
    'Financial Services': 'XLF',
    'Energy': 'XLE',
    'Healthcare': 'XLV',
    'Industrial': 'XLI',
    'Industrials': 'XLI',
    'Consumer Discretionary': 'XLY',
    'Consumer Cyclical': 'XLY',
    'Consumer Staples': 'XLP',
    'Consumer Defensive': 'XLP',
    'Materials': 'XLB',
    'Basic Materials': 'XLB',
    'Real Estate': 'XLRE',
    'Utilities': 'XLU',
    'Communication Services': 'XLC',
    'Services': 'XLY',
}

DB_PATH = Path("data/ticker_cache.db")

def get_ticker_sectors(tickers):
    sector_map = {}
    if DB_PATH.exists():
        conn = sqlite3.connect(DB_PATH)
        placeholders = ','.join(['?'] * len(tickers))
        query = f"SELECT ticker, sector FROM universe WHERE ticker IN ({placeholders})"
        try:
            df = pd.read_sql_query(query, conn, params=tickers)
            sector_map = dict(zip(df['ticker'], df['sector']))
        except Exception as e:
            logger.error(f"Error DB: {e}")
        finally:
            conn.close()
            
    unmapped = [t for t in tickers if t not in sector_map or pd.isna(sector_map[t])]
    if unmapped:
        logger.info(f"YFinance fallback for {len(unmapped)} tickers...")
        for t in unmapped:
            try:
                sector = yf.Ticker(t).info.get('sector')
                if sector: sector_map[t] = sector
            except: pass
            
    overrides = {
        "AMD": "Technology", "NXPI": "Technology", "MCHP": "Technology", "ON": "Technology",
        "INTC": "Technology", "HIMX": "Technology", "GOOG": "Technology", "DDOG": "Technology",
        "TWLO": "Technology", "TEAM": "Technology", "GOOGL": "Technology",
        "EPD": "Energy", "ET": "Energy", "SU": "Energy", "DVN": "Energy", "CTRA": "Energy", "HAL": "Energy"
    }
    for t, sec in overrides.items():
        if t in tickers: sector_map[t] = sec

    return sector_map

def calculate_metrics(group_df):
    if group_df.empty or len(group_df) < 2:
        return {"trades": len(group_df), "PF": 0.0, "Sharpe": 0.0, "win_rate": 0.0, "r_multiple_mean": 0.0}
        
    df_calc = group_df.copy()
    df_calc['pnl'] = df_calc['pnl'].astype(float)
    
    # User Fix 2: Sharpe over R-multiple
    if 'r_multiple' in df_calc.columns:
        r_mult = df_calc['r_multiple'].astype(float)
        # Handle cases where all r_multiples are the same (std=0)
        if r_mult.std() > 0:
            sharpe = (r_mult.mean() / r_mult.std()) * np.sqrt(252)
        else:
            sharpe = 0.0
        r_mult_mean = r_mult.mean()
    else:
        sharpe = 0.0
        r_mult_mean = 0.0
    
    wins = df_calc[df_calc['pnl'] > 0]['pnl'].sum()
    losses = abs(df_calc[df_calc['pnl'] < 0]['pnl'].sum())
    
    pf = wins / losses if losses > 0 else (99.9 if wins > 0 else 0)
    win_rate = (len(df_calc[df_calc['pnl'] > 0]) / len(df_calc)) * 100
    
    return {
        "trades": len(group_df),
        "PF": round(float(pf), 3),
        "Sharpe": round(float(sharpe), 3),
        "win_rate": round(float(win_rate), 1),
        "r_multiple_mean": round(float(r_mult_mean), 3)
    }

from src.data.pit_universe import PointInTimeUniverse

def main():
    logger.info("--- Etapa 1: Sandbox - Industry Group Filter (Historical Backtest v3 - PIT Universe) ---")
    
    combo_name = "combo_pure_momentum"
    params = load_combo_params(combo_name)
    
    all_trades = []
    total_signals_potential = 0
    
    # Initialize PIT Universe
    pit = PointInTimeUniverse()
    
    for fold in WF_FOLDS:
        logger.info(f"Running fold {fold['oos_start']} to {fold['oos_end']}")
        
        # User Fix 1: Use Point-in-Time S&P 500 Universe (realistic and broader)
        universe = pit.get_superset(fold["oos_start"], fold["oos_end"])
        logger.info(f"   PIT Universe size: {len(universe)} tickers")
        
        kwargs = build_engine_kwargs(combo_name, params)
        
        engine = AdvancedVectorBTEngine(
            universe=universe,
            start_date=fold["oos_start"],
            end_date=fold["oos_end"],
            initial_capital=100_000,
            **kwargs,
        )
        try:
            result = engine.run_backtest()
            trades_df = result.get("trades_df")
            if trades_df is not None and not trades_df.empty:
                all_trades.append(trades_df)
            
            # Record potential signals (unique_entries) for transparency
            total_signals_potential += result.get("total_trades", 0)
        except Exception as e:
            logger.error(f"Engine failed for fold {fold['oos_start']}: {e}")
            
    if not all_trades:
        logger.error("No trades generated from backtest.")
        return
        
    df_trades = pd.concat(all_trades, ignore_index=True)
    logger.info(f"Total potential signals: {total_signals_potential}")
    logger.info(f"Total executed trades: {len(df_trades)}")
    
    # Clean up column names since it comes from vectorbt
    if 'symbol' in df_trades.columns:
        df_trades['ticker'] = df_trades['symbol']
    if 'entry_date' not in df_trades.columns:
        logger.error("No entry_date column found in trades.")
        return
        
    df_trades['entry_date'] = pd.to_datetime(df_trades['entry_date']).dt.strftime('%Y-%m-%d')
    
    tickers = df_trades['ticker'].unique().tolist()
    ticker_to_sector = get_ticker_sectors(tickers)
    df_trades['sector'] = df_trades['ticker'].map(ticker_to_sector)
    df_trades['sector_etf'] = df_trades['sector'].map(SECTOR_TO_ETF)
    
    # Download all unique ETFs data 
    etfs = df_trades['sector_etf'].dropna().unique().tolist()
    logger.info(f"Downloading history for ETFs: {etfs}")
    
    start_date = (pd.to_datetime(df_trades['entry_date'].min()) - pd.Timedelta(days=60)).strftime("%Y-%m-%d")
    end_date = (pd.to_datetime(df_trades['entry_date'].max()) + pd.Timedelta(days=5)).strftime("%Y-%m-%d")
    
    etf_data = yf.download(etfs, start=start_date, end=end_date, auto_adjust=False, progress=False)['Close']
    
    # Compute SMA20 for all ETFs
    sma20 = etf_data.rolling(window=20).mean()
    
    df_trades['sector_ok'] = False
    
    for idx, row in df_trades.iterrows():
        etf = row['sector_etf']
        if pd.isna(etf):
            continue
            
        trade_date = row['entry_date']
        
        # Get latest available date <= trade_date
        past_dates = etf_data.index[etf_data.index <= trade_date]
        if len(past_dates) == 0:
            continue
            
        latest_date = past_dates[-1]
        
        try:
            if len(etfs) == 1:
                close_price = float(etf_data.loc[latest_date])
                sma = float(sma20.loc[latest_date])
            else:
                close_price = float(etf_data.loc[latest_date, etf])
                sma = float(sma20.loc[latest_date, etf])
            
            if not pd.isna(close_price) and not pd.isna(sma):
                df_trades.at[idx, 'sector_ok'] = (close_price > sma)
        except Exception:
            pass

    group_ok = df_trades[df_trades['sector_ok'] == True]
    group_no = df_trades[df_trades['sector_ok'] == False]
    group_unmapped = df_trades[df_trades['sector_etf'].isna()]
    
    metrics_ok = calculate_metrics(group_ok)
    metrics_no = calculate_metrics(group_no)
    
    report = {
        "run_at": pd.Timestamp.now().isoformat(),
        "total_trades": len(df_trades),
        "mapped_trades": len(df_trades[df_trades['sector_etf'].notna()]),
        "results": {
            "sector_ok": metrics_ok,
            "sector_no_ok": metrics_no
        }
    }
    
    out_path = ROOT / "outputs" / "experiments" / "industry_filter_backtest_eval.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(report, f, indent=2)
        
    logger.info(f"\n--- REPORTE GENERADO: {out_path} ---")
    logger.info(f"Grupo OK (SMA20↑):  Trades={metrics_ok['trades']}, PF={metrics_ok['PF']}, Sharpe={metrics_ok['Sharpe']}, WR={metrics_ok['win_rate']}%, R-Mult={metrics_ok['r_multiple_mean']}")
    logger.info(f"Grupo NO (SMA20↓):  Trades={metrics_no['trades']}, PF={metrics_no['PF']}, Sharpe={metrics_no['Sharpe']}, WR={metrics_no['win_rate']}%, R-Mult={metrics_no['r_multiple_mean']}")
    
    if len(group_unmapped) > 0:
        unmapped_tickers = group_unmapped['ticker'].unique()
        logger.info(f"Tickers sin sector mapeado ({len(unmapped_tickers)}): {unmapped_tickers[:10]}...")

if __name__ == "__main__":
    main()
