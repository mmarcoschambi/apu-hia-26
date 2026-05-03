#!/usr/bin/env python3
import json
import pandas as pd
import yfinance as yf
from pathlib import Path
import datetime
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

JOURNAL_PATH = Path("outputs/paper_finviz/journal.json")
OUT_CSV = Path("outputs/paper_trading/paper_trades_tracker.csv")

def main():
    if not JOURNAL_PATH.exists():
        logger.error(f"No journal found at {JOURNAL_PATH}")
        return

    with open(JOURNAL_PATH, "r") as f:
        journal = json.load(f)

    records = []
    
    # Collect all setups
    for day in journal:
        for s in day.get("signals", []):
            if s.get("combo") != "combo_pure_momentum":
                continue
            
            # The date in the signal is usually the scan date, meaning the entry happens 
            # on the next open or the next few days. We will fetch from signal_date forward.
            records.append({
                "ticker": s["ticker"],
                "signal_date": s["signal_date"],
                "entry_price": float(s["entry_price"]),
                "stop_loss": float(s["stop_loss"]),
                "position_size": int(s.get("position_size", 0))
            })

    if not records:
        logger.warning("No combo_pure_momentum signals found in journal.")
        return

    df = pd.DataFrame(records)
    logger.info(f"Loaded {len(df)} setups for tracking.")

    # Unique tickers to download in one batch to save time
    tickers = df["ticker"].unique().tolist()
    
    # Find the earliest date
    start_date = pd.to_datetime(df["signal_date"]).min().strftime("%Y-%m-%d")
    
    logger.info(f"Downloading YF data for {len(tickers)} tickers starting {start_date}...")
    # Add a few days buffer to start_date
    start_dt = pd.to_datetime(start_date) - pd.Timedelta(days=5)
    
    try:
        yf_data = yf.download(tickers, start=start_dt.strftime("%Y-%m-%d"), group_by='ticker', auto_adjust=False, threads=True, progress=False)
    except Exception as e:
        logger.error(f"Error downloading data: {e}")
        return

    results = []

    for _, row in df.iterrows():
        ticker = row["ticker"]
        sig_date = pd.to_datetime(row["signal_date"])
        entry_price = row["entry_price"]
        stop_loss = row["stop_loss"]
        shares = row["position_size"]

        if shares == 0:
            logger.warning(f"Skipping {ticker} on {sig_date.date()} because size is 0")
            continue

        # Extract this ticker's data
        if len(tickers) == 1:
            t_data = yf_data
        else:
            if ticker not in yf_data.columns.levels[0]:
                logger.warning(f"No YF data for {ticker}")
                continue
            t_data = yf_data[ticker].dropna(subset=["Close"])

        if t_data.empty:
            logger.warning(f"Empty data for {ticker}")
            continue

        # Keep only dates strictly AFTER the signal date (the trade is entered the next day at the earliest)
        # Actually, in this simulated tracking, let's assume we entered AT the entry_price on the day after the signal or whenever it hits
        # For simplicity, we just look at the low/close from signal_date + 1 day onwards
        future_data = t_data[t_data.index > sig_date]
        
        if future_data.empty:
            # Maybe the signal was today and there is no future data yet
            # In that case, use the last available close from today
            future_data = t_data[t_data.index >= sig_date]
            if future_data.empty:
                continue

        exit_type = "Floating"
        exit_date = future_data.index[-1].strftime("%Y-%m-%d")
        exit_price = future_data["Close"].iloc[-1]
        
        # Check for stop loss hit
        for date, f_row in future_data.iterrows():
            low = f_row["Low"]
            if low <= stop_loss:
                exit_type = "Stop Loss"
                exit_date = date.strftime("%Y-%m-%d")
                exit_price = stop_loss
                break

        pnl = (exit_price - entry_price) * shares
        risk = (entry_price - stop_loss) * shares
        r_multiple = pnl / risk if risk > 0 else 0

        results.append({
            "ticker": ticker,
            "entry_date": sig_date.strftime("%Y-%m-%d"), # loosely tracking signal date as entry
            "exit_date": exit_date,
            "exit_type": exit_type,
            "entry_price": round(entry_price, 2),
            "exit_price": round(exit_price, 2),
            "shares": shares,
            "pnl": round(pnl, 2),
            "r_multiple": round(r_multiple, 2)
        })

    out_df = pd.DataFrame(results)
    
    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    out_df.to_csv(OUT_CSV, index=False)
    
    logger.info(f"Processed {len(out_df)} trades. Total PnL: ${out_df['pnl'].sum():,.2f}")
    logger.info(f"Saved PnL tracker data to {OUT_CSV}")

if __name__ == "__main__":
    main()
