import os
import json
import sqlite3
import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime

# Etapa 1 — Sandbox: Pregunta: ¿las señales de combo_pure_momentum donde el sector ETF 
# está en Stage 2 (precio > SMA20) tienen mejor Sharpe OOS?

# Mapeo de nombre de sector en DB -> ETF correspondiente (basado en market_context.py)
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
    'Services': 'XLY', # Fallback común
}

DB_PATH = Path("data/ticker_cache.db")

def get_ticker_sectors(tickers):
    """Obtiene el sector de cada ticker desde la base de datos o yfinance como fallback."""
    sector_map = {}
    
    if DB_PATH.exists():
        conn = sqlite3.connect(DB_PATH)
        placeholders = ','.join(['?'] * len(tickers))
        query = f"SELECT ticker, sector FROM universe WHERE ticker IN ({placeholders})"
        try:
            df = pd.read_sql_query(query, conn, params=tickers)
            sector_map = dict(zip(df['ticker'], df['sector']))
        except Exception as e:
            print(f"Error consultando sectores DB: {e}")
        finally:
            conn.close()
    
    import yfinance as yf
    
    # Fallback to yfinance for unmapped
    unmapped = [t for t in tickers if t not in sector_map or pd.isna(sector_map[t])]
    if unmapped:
        print(f"Buscando sectores en YFinance para {len(unmapped)} tickers...")
        for t in unmapped:
            try:
                info = yf.Ticker(t).info
                sector = info.get('sector')
                if sector:
                    sector_map[t] = sector
            except Exception as e:
                pass
                
    # Hardcoded overrides provided by user
    overrides = {
        "AMD": "Technology", "NXPI": "Technology", "MCHP": "Technology", "ON": "Technology",
        "INTC": "Technology", "HIMX": "Technology", "GOOG": "Technology", "DDOG": "Technology",
        "TWLO": "Technology", "TEAM": "Technology", "GOOGL": "Technology",
        "EPD": "Energy", "ET": "Energy", "SU": "Energy", "DVN": "Energy", "CTRA": "Energy", "HAL": "Energy"
    }
    for t, sec in overrides.items():
        if t in tickers:
            sector_map[t] = sec

    return sector_map

def sector_etf_above_sma20(etf: str, date: str) -> bool:
    """Verifica si el ETF del sector cerró por encima de su SMA20 en la fecha dada usando yfinance."""
    import yfinance as yf
    import pandas as pd
    
    try:
        # Add 1 day to end date to ensure we get the 'date' itself
        end_date = (pd.to_datetime(date) + pd.Timedelta(days=1)).strftime("%Y-%m-%d")
        start_date = (pd.to_datetime(date) - pd.Timedelta(days=40)).strftime("%Y-%m-%d")
        
        data = yf.download(etf, start=start_date, end=end_date, progress=False, auto_adjust=False)
        if data.empty or len(data) < 20:
            return False
            
        data['SMA20'] = data['Close'].rolling(window=20).mean()
        
        # Get the row corresponding to the exact date, or the latest available before it
        data = data[data.index <= date]
        if data.empty:
            return False
            
        latest = data.iloc[-1]
        
        close_price = float(latest['Close'].iloc[0]) if isinstance(latest['Close'], pd.Series) else float(latest['Close'])
        sma20 = float(latest['SMA20'].iloc[0]) if isinstance(latest['SMA20'], pd.Series) else float(latest['SMA20'])
        
        if pd.isna(close_price) or pd.isna(sma20):
            return False
            
        return close_price > sma20
    except Exception as e:
        print(f"Error fetching ETF data for {etf}: {e}")
        return False

def calculate_metrics(group_df):
    """Calcula Profit Factor y Sharpe ratio sobre los trades del grupo."""
    if group_df.empty or 'pnl' not in group_df.columns or len(group_df) < 2:
        return {"trades": len(group_df), "PF": 0.0, "Sharpe": 0.0, "win_rate": 0.0}
        
    df_calc = group_df.copy()
    df_calc['pnl'] = df_calc['pnl'].astype(float)
    
    wins = df_calc[df_calc['pnl'] > 0]['pnl'].sum()
    losses = abs(df_calc[df_calc['pnl'] < 0]['pnl'].sum())
    
    pf = wins / losses if losses > 0 else (99.9 if wins > 0 else 0)
    win_rate = (len(df_calc[df_calc['pnl'] > 0]) / len(df_calc)) * 100
    
    mean_pnl = df_calc['pnl'].mean()
    std_pnl = df_calc['pnl'].std()
    sharpe = (mean_pnl / std_pnl) * np.sqrt(252) if std_pnl > 0 else 0
    
    return {
        "trades": len(group_df),
        "PF": round(float(pf), 3),
        "Sharpe": round(float(sharpe), 3),
        "win_rate": round(float(win_rate), 1)
    }

def main():
    print("--- Etapa 1: Sandbox - Industry Group Filter ---")
    
    # 1. Cargar las señales de paper trading (probamos varios journals)
    possible_journals = [
        "outputs/paper_finviz/journal.json",
        "outputs/paper_local/journal.json"
    ]
    
    journal_path = None
    for p in possible_journals:
        if Path(p).exists():
            journal_path = Path(p)
            break
            
    if not journal_path:
        print("Error: No se encontró ningún journal.json en outputs/")
        return
        
    print(f"Usando journal: {journal_path}")
    with open(journal_path, "r") as f:
        journal_data = json.load(f)
        
    trades = []
    for day in journal_data:
        signals = day.get("signals", [])
        for sig in signals:
            trades.append(sig)
            
    df_signals = pd.DataFrame(trades)
    if df_signals.empty:
        print("No hay trades en el journal.")
        return
        
    # Filtrar por combo_pure_momentum (o dejar todos para ver el impacto general)
    # df_signals = df_signals[df_signals['combo'] == 'combo_pure_momentum'].copy()
    
    # 2. Auto-mapping de sectores
    tickers = df_signals['ticker'].unique().tolist()
    ticker_to_sector = get_ticker_sectors(tickers)
    df_signals['sector'] = df_signals['ticker'].map(ticker_to_sector)
    df_signals['sector_etf'] = df_signals['sector'].map(SECTOR_TO_ETF)
    
    # 3. Evaluar condición Stage 2
    print("Evaluando condición Stage 2 (ETF > SMA20) para cada trade...")
    df_signals['sector_ok'] = False
    
    # Intentamos cargar PnL real generado por journal_pnl_tracker.py
    pnl_real = {}
    trades_csv = Path("outputs/paper_trading/paper_trades_tracker.csv")
    if trades_csv.exists():
        try:
            df_pnl = pd.read_csv(trades_csv)
            # Simplificación: en caso de múltiples entradas para un ticker, usamos la suma o el último
            for _, row in df_pnl.iterrows():
                pnl_real[row['ticker']] = row['pnl']
            print(f"Se cargó PnL real para {len(pnl_real)} tickers desde {trades_csv.name}")
        except Exception as e:
            print(f"Error cargando CSV de PnL: {e}")

    for idx, row in df_signals.iterrows():
        etf = row['sector_etf']
        if pd.isna(etf):
            continue
        
        df_signals.at[idx, 'sector_ok'] = sector_etf_above_sma20(etf, row['signal_date'])
        
        # Asignar PnL Real o fallback a 0 si no se encontró
        if row['ticker'] in pnl_real:
            df_signals.at[idx, 'pnl'] = pnl_real[row['ticker']]
        else:
            df_signals.at[idx, 'pnl'] = 0.0 # No PnL data means 0 PnL for this test

    # 4. Resultados
    group_ok = df_signals[df_signals['sector_ok'] == True]
    group_no = df_signals[df_signals['sector_ok'] == False]
    
    metrics_ok = calculate_metrics(group_ok)
    metrics_no = calculate_metrics(group_no)
    
    report = {
        "run_at": datetime.now().isoformat(),
        "journal_used": str(journal_path),
        "total_signals": len(df_signals),
        "mapped_signals": len(df_signals[df_signals['sector_etf'].notna()]),
        "results": {
            "sector_ok": metrics_ok,
            "sector_no_ok": metrics_no
        }
    }
    
    # Guardar reporte JSON (estilo pattern_only_eval)
    out_dir = Path("outputs/experiments")
    out_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = out_dir / f"industry_filter_eval_{ts}.json"
    
    with open(out_path, "w") as f:
        json.dump(report, f, indent=2)
        
    print(f"\n--- REPORTE GENERADO: {out_path} ---")
    print(f"Grupo OK (SMA20↑):  Trades={metrics_ok['trades']}, PF={metrics_ok['PF']}, Sharpe={metrics_ok['Sharpe']}, WR={metrics_ok['win_rate']}%")
    print(f"Grupo NO (SMA20↓):  Trades={metrics_no['trades']}, PF={metrics_no['PF']}, Sharpe={metrics_no['Sharpe']}, WR={metrics_no['win_rate']}%")
    
    unmapped = df_signals[df_signals['sector_etf'].isna()]['ticker'].unique()
    if len(unmapped) > 0:
        print(f"Tickers sin sector mapeado ({len(unmapped)}): {unmapped[:10]}...")

if __name__ == "__main__":
    main()

