"""
Historical Backtester - Replay trades in past date ranges
Visualize where the 3 Caminos triggered and their results
"""
import sys
from pathlib import Path
from datetime import datetime, timedelta
import pandas as pd
import numpy as np

project_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(project_root))

from src.data.market_data import MarketDataProvider
from src.indicators.triad import TriadIndicators
from src.strategies.triad_protocol import TriadStrategy, Camino
from src.core.market_context import MarketContext
from src.core.stock_filters import StockFilters


class HistoricalBacktester:
    
    def __init__(self):
        self.data_provider = MarketDataProvider()
        self.indicators = TriadIndicators()
        self.strategy = TriadStrategy()
        self.market_context = MarketContext(self.data_provider)
        self.stock_filters = StockFilters()
    
    def backtest_symbol(self, symbol: str, start_date: str, end_date: str) -> pd.DataFrame:
        """
        Backtest a symbol over a date range
        Returns DataFrame with all signals and their outcomes
        """
        print(f"\n{'='*80}")
        print(f"BACKTESTING {symbol}: {start_date} to {end_date}")
        print(f"{'='*80}")
        
        # Fetch historical data - use max period to get enough history
        print("Fetching historical data...")
        daily_df = self.data_provider.get_daily_data(symbol, period="max")
        
        if daily_df.empty:
            print(f"❌ No data for {symbol}")
            return pd.DataFrame()
        
        # Filter by date range FIRST
        daily_df.index = pd.to_datetime(daily_df.index).tz_localize(None)
        start_dt = pd.to_datetime(start_date)
        end_dt = pd.to_datetime(end_date)
        
        # Need extra history before start date for indicators
        # Get data from 6 months before start date
        history_start = start_dt - pd.Timedelta(days=180)
        
        # Filter to get history + range
        historical_mask = daily_df.index >= history_start
        daily_df = daily_df[historical_mask]
        
        # Now filter the actual trading range
        mask = (daily_df.index >= start_dt) & (daily_df.index <= end_dt)
        date_range_df = daily_df[mask]
        
        if date_range_df.empty:
            print(f"❌ No data in range {start_date} to {end_date} for {symbol}")
            print(f"   Available range: {daily_df.index.min().date()} to {daily_df.index.max().date()}")
            return pd.DataFrame()
        
        # ═══════════════════════════════════════════════════════════════
        # STOCK QUALITY FILTERS - Evaluate at END of backtest period
        # ═══════════════════════════════════════════════════════════════
        print("Checking stock quality filters at end of period...")
        # Get data up to end_date + 200 days buffer for SMA200
        filter_end_date = end_dt + pd.Timedelta(days=200)
        filter_data = daily_df[daily_df.index <= filter_end_date]
        
        if len(filter_data) >= 200:
            # Use smart filter that auto-detects cache availability
            filter_result = self.stock_filters.passes_filters(
                ticker=symbol,
                date=end_date,
                df=filter_data
            )
            
            if not filter_result['passed']:
                print(f"❌ {symbol} FAILS quality filters at {end_date}:")
                print(f"   {filter_result['details']}")
                print(f"   Skipping backtest for this symbol.")
                return pd.DataFrame()
            
            print(f"✅ {symbol} passes quality filters at {end_date}")
            print(f"   Dollar Volume: ${filter_result['metrics']['dollar_volume']/1e6:.0f}M")
            print(f"   ADR: {filter_result['metrics']['adr_pct']:.2f}%")
            print(f"   Trend: Price ${filter_result['metrics']['price']:.2f} > SMA50 ${filter_result['metrics']['sma50']:.2f} > SMA200 ${filter_result['metrics']['sma200']:.2f}")
        else:
            print(f"⚠️  Insufficient data for quality filters, proceeding anyway...")
        
        # Load SPY/QQQ for market regime filters
        print("Loading SPY/QQQ for market filters...")
        spy_df = self.data_provider.get_daily_data('SPY', period='max')
        spy_df.index = pd.to_datetime(spy_df.index).tz_localize(None)
        qqq_df = self.data_provider.get_daily_data('QQQ', period='max')
        qqq_df.index = pd.to_datetime(qqq_df.index).tz_localize(None)
        
        print(f"Analyzing {len(date_range_df)} trading days...")
        
        signals = []
        signals_blocked_by_filter = 0
        
        # Walk through each day in the range
        for i, (date, row) in enumerate(date_range_df.iterrows()):
            # Need at least 20 days of history for base detection
            if i < 20:
                continue
            
            # Get data up to this date
            historical_data = daily_df.loc[:date]
            
            # ═══════════════════════════════════════════════════════════════
            # MARKET REGIME FILTER (NEW)
            # ═══════════════════════════════════════════════════════════════
            spy_historical = spy_df.loc[:date] if not spy_df.empty else pd.DataFrame()
            qqq_historical = qqq_df.loc[:date] if not qqq_df.empty else pd.DataFrame()
            
            market_favorable = True  # Default to allow
            
            if len(spy_historical) >= 30:
                # Calculate SPY EMA20
                spy_ema20 = spy_historical['Close'].ewm(span=20, adjust=False).mean().iloc[-1]
                spy_current = spy_historical['Close'].iloc[-1]
                spy_above_ema20 = spy_current > spy_ema20
                
                # Estimate breadth
                breadth_improving = self._estimate_breadth_at_date(spy_historical, qqq_historical)
                
                # Check if market favorable for longs
                market_favorable = spy_above_ema20 or breadth_improving
                
                if not market_favorable:
                    # Skip this day - market unfavorable
                    signals_blocked_by_filter += 1
                    continue
            
            # ═══════════════════════════════════════════════════════════════
            # Continue with normal signal detection
            # ═══════════════════════════════════════════════════════════════
            
            # Calculate indicators
            base_data = self.indicators.detect_base(historical_data, lookback=20)
            avwap_data = self.indicators.calculate_avwap_from_ath(historical_data)
            
            # Use pre-calculated ADR from cache if available, otherwise calculate
            if 'adr_14' in daily_df.columns and date in daily_df.index:
                adr = daily_df.loc[date, 'adr_14']
                if pd.isna(adr):
                    adr = self._calculate_adr_at_date(daily_df, date, period=20)
            else:
                adr = self._calculate_adr_at_date(daily_df, date, period=20)
            
            # Simple market context
            market_ctx = {'market_weak': False, 'spy_gap_down': False, 'qqq_gap_down': False}
            
            # For Camino 2, detect gap downs
            prev_close = historical_data['Close'].iloc[-2] if len(historical_data) > 1 else historical_data['Close'].iloc[-1]
            current_open = row['Open']
            gap_pct = (current_open - prev_close) / prev_close
            gap_data = {
                'detected': gap_pct < -0.01,
                'gap_pct': gap_pct
            }
            
            # Simulate intraday VWAP with daily data
            vwap_estimate = (row['High'] + row['Low'] + row['Close']) / 3
            vwap_data = {
                'calculated': True,
                'current_vwap': vwap_estimate,
                'current_price': row['Close'],
                'above_vwap': row['Close'] > vwap_estimate,
                'crossed_up': (row['Close'] > row['Open']) and (row['Close'] > (row['High'] + row['Low']) / 2),
                'session_low': row['Low'],
                'session_open': row['Open'],
                'session_high': row['High']
            }
            
            if gap_data['detected']:
                market_ctx['market_weak'] = True
            
            # Generate signal
            signal = self.strategy.analyze(
                base_data=base_data,
                avwap_data=avwap_data,
                vwap_data=vwap_data,
                gap_data=gap_data,
                market_context=market_ctx,
                adr=adr
            )
            
            # Only track actionable signals
            if signal.action in ['BUY_STOP', 'MANUAL_WATCH']:
                # Calculate outcome
                outcome = self._simulate_trade_outcome(
                    daily_df, 
                    date, 
                    signal.entry_price or row['Close'],
                    signal.stop_loss or row['Low'],
                    hold_days=10
                )
                
                signals.append({
                    'date': date,
                    'symbol': symbol,
                    'camino': signal.camino.name if signal.camino else None,
                    'action': signal.action,
                    'entry_price': signal.entry_price or row['Close'],
                    'stop_loss': signal.stop_loss or row['Low'],
                    'base_high': base_data.get('base_high'),
                    'avwap': avwap_data.get('current_avwap'),
                    'gap_pct': gap_pct,
                    'outcome': outcome['outcome'],
                    'exit_price': outcome['exit_price'],
                    'exit_date': outcome['exit_date'],
                    'return_pct': outcome['return_pct'],
                    'hold_days': outcome['hold_days'],
                    'reasoning': signal.reasoning[:100]
                })
        
        results_df = pd.DataFrame(signals)
        
        if not results_df.empty:
            print(f"\n✅ Found {len(results_df)} signals")
            print(f"   Camino 1: {len(results_df[results_df['camino'] == 'BLUE_SKY'])}")
            print(f"   Camino 2: {len(results_df[results_df['camino'] == 'VWAP_RECLAIM'])}")
            print(f"   🛡️  Blocked by market filter: {signals_blocked_by_filter}")
            
            wins = len(results_df[results_df['outcome'] == 'WIN'])
            losses = len(results_df[results_df['outcome'] == 'LOSS'])
            print(f"\n   Wins: {wins} | Losses: {losses} | Win Rate: {wins/(wins+losses)*100:.1f}%")
            print(f"   Avg Return: {results_df['return_pct'].mean():.2f}%")
        else:
            print(f"\n⚠️  No signals found")
            if signals_blocked_by_filter > 0:
                print(f"   🛡️  {signals_blocked_by_filter} potential signals blocked by market filter")
        
        return results_df
    
    def _estimate_breadth_at_date(self, spy_hist: pd.DataFrame, qqq_hist: pd.DataFrame) -> bool:
        """Estimate if breadth was improving at historical date"""
        try:
            if len(spy_hist) < 20 or len(qqq_hist) < 20:
                return False
            
            # SMA20 for both
            spy_sma20 = spy_hist['Close'].rolling(20).mean().iloc[-1]
            qqq_sma20 = qqq_hist['Close'].rolling(20).mean().iloc[-1]
            
            spy_above = spy_hist['Close'].iloc[-1] > spy_sma20
            qqq_above = qqq_hist['Close'].iloc[-1] > qqq_sma20
            
            # Check ascending
            if len(spy_hist) >= 10:
                recent_5 = spy_hist['Close'].iloc[-5:].mean()
                previous_5 = spy_hist['Close'].iloc[-10:-5].mean()
                ascending = recent_5 > previous_5
            else:
                ascending = False
            
            return (spy_above and qqq_above) or ascending
        except:
            return False
    
    def _calculate_adr_at_date(self, df: pd.DataFrame, date, period: int = 20) -> float:
        """Calculate ADR at a specific historical date"""
        historical = df.loc[:date]
        if len(historical) < period:
            return 0.0
        recent = historical.tail(period)
        ranges = recent['High'] - recent['Low']
        return ranges.mean()
    
    def _simulate_trade_outcome(self, df: pd.DataFrame, entry_date, entry_price: float, 
                                stop_loss: float, hold_days: int = 10) -> dict:
        """Simulate trade outcome"""
        try:
            entry_idx = df.index.get_loc(entry_date)
        except KeyError:
            return {'outcome': 'UNKNOWN', 'exit_price': entry_price, 'exit_date': entry_date, 
                   'return_pct': 0, 'hold_days': 0}
        
        risk_per_share = entry_price - stop_loss
        target_2r = entry_price + (2 * risk_per_share)
        
        # Check next N days
        for i in range(1, hold_days + 1):
            if entry_idx + i >= len(df):
                break
            
            future_date = df.index[entry_idx + i]
            future_row = df.iloc[entry_idx + i]
            
            # Check if stop hit
            if future_row['Low'] <= stop_loss:
                return {
                    'outcome': 'LOSS',
                    'exit_price': stop_loss,
                    'exit_date': future_date,
                    'return_pct': ((stop_loss - entry_price) / entry_price) * 100,
                    'hold_days': i
                }
            
            # Check if 2R target hit
            if future_row['High'] >= target_2r:
                return {
                    'outcome': 'WIN',
                    'exit_price': target_2r,
                    'exit_date': future_date,
                    'return_pct': ((target_2r - entry_price) / entry_price) * 100,
                    'hold_days': i
                }
        
        # Held for full period
        exit_idx = min(entry_idx + hold_days, len(df) - 1)
        exit_date = df.index[exit_idx]
        exit_price = df.iloc[exit_idx]['Close']
        return_pct = ((exit_price - entry_price) / entry_price) * 100
        
        return {
            'outcome': 'WIN' if return_pct > 0 else 'LOSS',
            'exit_price': exit_price,
            'exit_date': exit_date,
            'return_pct': return_pct,
            'hold_days': hold_days
        }
    
    def backtest_watchlist(self, symbols: list, start_date: str, end_date: str) -> pd.DataFrame:
        """Backtest multiple symbols"""
        all_results = []
        
        for symbol in symbols:
            try:
                results = self.backtest_symbol(symbol, start_date, end_date)
                if not results.empty:
                    all_results.append(results)
            except Exception as e:
                print(f"❌ Error with {symbol}: {e}")
        
        if all_results:
            combined = pd.concat(all_results, ignore_index=True)
            return combined
        else:
            return pd.DataFrame()
    
    def save_results(self, results_df: pd.DataFrame, output_file: str = "outputs/backtests/backtest_results.csv"):
        """Save backtest results"""
        if results_df.empty:
            print("No results to save")
            return
        
        output_path = Path(output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        results_df.to_csv(output_path, index=False)
        print(f"\n✅ Results saved to {output_path}")


def main():
    """Example usage"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Backtest Triad Strategy')
    parser.add_argument('--symbols', nargs='+', default=['RDDT', 'NVDA', 'TSLA'],
                       help='Symbols to backtest')
    parser.add_argument('--start', default='2024-01-01', help='Start date (YYYY-MM-DD)')
    parser.add_argument('--end', default='2024-12-01', help='End date (YYYY-MM-DD)')
    parser.add_argument('--output', default='outputs/backtests/backtest_results.csv', help='Output CSV')
    
    args = parser.parse_args()
    
    backtester = HistoricalBacktester()
    
    results = backtester.backtest_watchlist(
        symbols=args.symbols,
        start_date=args.start,
        end_date=args.end
    )
    
    if not results.empty:
        print(f"\n{'='*80}")
        print("BACKTEST SUMMARY")
        print(f"{'='*80}")
        print(f"Total Signals: {len(results)}")
        print(f"Symbols: {results['symbol'].nunique()}")
        print(f"Date Range: {results['date'].min().date()} to {results['date'].max().date()}")
        
        print(f"\nBy Camino:")
        for camino in results['camino'].unique():
            camino_results = results[results['camino'] == camino]
            wins = len(camino_results[camino_results['outcome'] == 'WIN'])
            total = len(camino_results)
            avg_return = camino_results['return_pct'].mean()
            print(f"  {camino}: {total} signals | {wins}/{total} wins ({wins/total*100:.1f}%) | Avg: {avg_return:.2f}%")
        
        backtester.save_results(results, args.output)
        
        print(f"\n💡 Next: Visualize with:")
        print(f"   python3 src/backtest/visualizer.py {args.output}")


if __name__ == "__main__":
    main()
