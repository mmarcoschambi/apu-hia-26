#!/usr/bin/env python3
"""
Runner for the Institutional Daily Backtest Engine
"""
import sys
import json
import argparse
import pandas as pd
from pathlib import Path

project_root = Path(__file__).resolve().parent
sys.path.insert(0, str(project_root))

from src.backtest.daily_engine import DailyBacktestEngine
from src.utils.risk_manager import RiskManager

def load_watchlist(json_path):
    try:
        with open(json_path, 'r') as f:
            data = json.load(f)
        symbols = []
        for cat in data.values():
            symbols.extend(cat)
        return list(set(symbols))
    except Exception as e:
        print(f"Error loading watchlist: {e}")
        return ['AAPL', 'MSFT', 'TSLA', 'NVDA']

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--start', required=True)
    parser.add_argument('--end', required=True)
    parser.add_argument('--watchlist', default='config/watchlist.json')
    parser.add_argument('--equity', type=float, default=100000.0)
    parser.add_argument('--risk', type=float, default=0.005)
    parser.add_argument('--max_exp', type=float, default=0.25)
    parser.add_argument('--stop_loss', type=float, default=None, help="Fixed Stop Loss % (Optional Override)")
    
    # Market Cap Filters (Mid-Cap Default)
    parser.add_argument('--min_mcap', type=float, default=2e9)
    parser.add_argument('--max_mcap', type=float, default=20e9)
    parser.add_argument('--min_volume', type=int, default=300000) # Updated default
    parser.add_argument('--min_adr', type=float, default=1.5) # New
    parser.add_argument('--min_price', type=float, default=5.0) # New
    parser.add_argument('--min_dollar_vol', type=float, default=15000000.0) # New
    parser.add_argument('--min_rvol', type=float, default=1.5, help="Minimum Relative Volume (RVOL)")
    parser.add_argument('--skip_filters', action='store_true', help="Skip fundamental filters")
    
    # New arguments for Universe Source
    parser.add_argument('--source', choices=['file', 'sqlite', 'sqlite_sector'], default='file', help="Source of the ticker universe")
    parser.add_argument('--sector', type=str, default=None, help="Sector to filter by (if source is sqlite_sector)")
    parser.add_argument('--offline', action='store_true', help="Use only cached data, do not download")
    parser.add_argument('--max_symbols', type=int, default=None, help="Limit universe size (useful for testing large datasets)")
    parser.add_argument('--sort_by', choices=['alphabetical', 'liquidity', 'random'], default='liquidity', 
                        help="How to select symbols when limiting: alphabetical, liquidity (recommended), or random")
    
    args = parser.parse_args()
    
    # Load Universe based on source
    universe = []
    if args.source == 'file':
        universe = load_watchlist(args.watchlist)
    elif args.source.startswith('sqlite'):
        try:
            from src.data.ticker_cache import TickerCache
            cache = TickerCache()
            
            filters = {}
            if args.source == 'sqlite_sector' and args.sector:
                print(f"Loading universe from SQLite (Sector: {args.sector})...")
                filters['sector'] = args.sector
            else:
                print("Loading full universe from SQLite...")
            
            # Use the improved method with sort_by and limit
            if args.max_symbols:
                print(f"📊 Selection Strategy: {args.sort_by.upper()}")
                # Si estamos usando 'liquidity' y hay fechas de backtest, usar filtro por fecha
                if args.sort_by == 'liquidity' and args.start and args.end:
                    # Para cada fecha del backtest, filtrar por liquidez en esa fecha específica
                    # Buscar la primera fecha válida después del start (por si es feriado/fin de semana)
                    cursor = cache.conn.execute(
                        "SELECT MIN(date) FROM ohlcv_cache WHERE date >= ?",
                        (args.start,)
                    )
                    first_valid_date = cursor.fetchone()[0]
                    
                    if first_valid_date:
                        print(f"📅 Usando fecha de referencia: {first_valid_date}")
                        universe = cache.get_active_tickers(
                            filters=filters,
                            sort_by=args.sort_by,
                            limit=args.max_symbols,
                            date_filter=first_valid_date,  # Usar primera fecha válida
                            min_price=args.min_price,
                            min_rolling_dollar_vol=args.min_dollar_vol
                        )
                    else:
                        print("⚠️ No hay datos para el rango especificado, usando método sin fecha")
                        universe = cache.get_active_tickers(filters=filters, sort_by=args.sort_by, limit=args.max_symbols)
                else:
                    universe = cache.get_active_tickers(filters=filters, sort_by=args.sort_by, limit=args.max_symbols)
            else:
                universe = cache.get_active_tickers(filters=filters, sort_by=args.sort_by)
            
            cache.close()
            
            # Remove duplicates just in case
            universe = list(set(universe))
                
        except Exception as e:
            print(f"Error loading from SQLite: {e}")
            universe = []

    print(f"Loaded Universe: {len(universe)} symbols")
    
    # Initialize Risk Manager
    rm = RiskManager(
        account_equity=args.equity,
        risk_fraction=args.risk,
        max_exposure_fraction=args.max_exp
    )
    
    # Initialize & Run Engine
    engine = DailyBacktestEngine(
        universe=universe,
        start_date=args.start,
        end_date=args.end,
        risk_manager=rm,
        min_mcap=args.min_mcap,
        max_mcap=args.max_mcap,
        min_avg_volume=args.min_volume,
        min_adr=args.min_adr,
        min_price=args.min_price,
        min_dollar_vol=args.min_dollar_vol,
        min_rvol=args.min_rvol,
        skip_filters=args.skip_filters,
        offline=args.offline
    )
    
    print("Running Daily Simulation (this may take a moment to preload data)...")
    trades_df = engine.run()
    
    if not trades_df.empty:
        # Normalize columns for dashboard
        # Dashboard expects: entry_date, exit_date, entry_price, exit_price, returns_pct, is_profitable, signal_type, signal_reason, symbol, shares, position_value, monetary_risk
        
        trades_df['is_profitable'] = trades_df['pnl'] > 0
        # trades_df['signal_type'] is already populated by engine
        trades_df['signal_reason'] = trades_df['reason']
        trades_df['returns_pct'] = trades_df['return_pct']
        trades_df['position_value'] = trades_df['entry_price'] * trades_df['shares']
        # Monetary risk approx
        trades_df['monetary_risk'] = args.equity * args.risk # Simplified assumption
        
        trades_df.to_csv('backtest_results.csv', index=False)
        print(f"✅ Simulation Complete. {len(trades_df)} trades generated.")
    else:
        print("No trades generated.")
        pd.DataFrame(columns=['entry_date', 'exit_date', 'entry_price', 'exit_price', 'returns_pct', 'is_profitable', 'signal_type', 'signal_reason', 'symbol', 'shares', 'position_value', 'monetary_risk']).to_csv('backtest_results.csv', index=False)

if __name__ == "__main__":
    main()
