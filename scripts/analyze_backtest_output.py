
import pandas as pd
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.utils.sector_rotation import SECTOR_MAP

def analyze_backtest(file_path):
    df = pd.read_csv(file_path)
    df['entry_date'] = pd.to_datetime(df['entry_date'])
    df['month'] = df['entry_date'].dt.to_period('M')
    
    # Map symbols to sectors
    df['sector'] = df['symbol'].map(SECTOR_MAP).fillna('UNKNOWN')
    
    monthly_stats = df.groupby('month').agg(
        trades=('symbol', 'count'),
        pnl=('pnl', 'sum'),
        win_rate=('pnl', lambda x: (x > 0).mean() * 100),
    ).reset_index()
    
    print("Monthly Performance:")
    print(monthly_stats)
    
    for month in ['2023-07', '2024-07']:
        m_df = df[df['month'] == month]
        if not m_df.empty:
            print(f"\nAnalysis for {month}:")
            print(f"Total Trades: {len(m_df)}")
            print(f"Total PnL: {m_df['pnl'].sum():.2f}")
            
            sector_stats = m_df.groupby('sector').agg(
                trades=('symbol', 'count'),
                pnl=('pnl', 'sum'),
                avg_ret=('return_pct', 'mean')
            ).sort_values('pnl')
            print("\nSector Performance in this month:")
            print(sector_stats)
            
            print("\nTop 5 Losing Trades:")
            print(m_df.sort_values('pnl').head(5)[['symbol', 'entry_date', 'pnl', 'exit_phase', 'return_pct']])

if __name__ == "__main__":
    analyze_backtest("outputs/backtests/complete_trades_clean.csv")
