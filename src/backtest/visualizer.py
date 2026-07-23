"""
Backtest Visualizer - Interactive charts for historical signals
Shows entry/exit points, indicators, and trade outcomes
"""
import sys
from pathlib import Path
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.patches import Rectangle
from datetime import datetime
import warnings
warnings.filterwarnings('ignore')

project_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(project_root))

from src.data.market_data import MarketDataProvider
from src.indicators.triad import TriadIndicators


class BacktestVisualizer:
    
    def __init__(self):
        self.data_provider = MarketDataProvider()
        self.indicators = TriadIndicators()
    
    def visualize_trade(self, symbol: str, entry_date: str, signal_data: dict, 
                       days_before: int = 30, days_after: int = 15):
        """
        Create detailed chart for a single trade
        Shows: Price, Base, AVWAP, Entry/Exit points
        For VWAP_RECLAIM: Adds 5-minute intraday zoom
        """
        # Fetch data
        daily_df = self.data_provider.get_daily_data(symbol, period="max")
        daily_df.index = pd.to_datetime(daily_df.index).tz_localize(None)
        
        entry_date_pd = pd.to_datetime(entry_date).tz_localize(None)
        
        # Get window around entry - find closest date
        try:
            # Find the absolute index of the entry date
            entry_idx_abs = daily_df.index.get_indexer([entry_date_pd], method='nearest')[0]
            if entry_idx_abs == -1:
                print(f"[FAIL] Date {entry_date} not found for {symbol}")
                return
        except Exception as e:
            print(f"[FAIL] Error finding date {entry_date} for {symbol}: {e}")
            return
        
        start_idx = max(0, entry_idx_abs - days_before)
        end_idx = min(len(daily_df), entry_idx_abs + days_after)
        
        window_df = daily_df.iloc[start_idx:end_idx]
        
        # Calculate relative index for the entry date within the window
        # This is CRITICAL for alignment
        relative_entry_idx = entry_idx_abs - start_idx
        
        # Calculate indicators
        historical_df = daily_df.iloc[:entry_idx_abs+1]
        avwap_data = self.indicators.calculate_avwap_from_ath(historical_df)
        
        # Determine if we need intraday zoom (VWAP_RECLAIM)
        is_reclaim = signal_data.get('camino') == 'VWAP_RECLAIM'
        
        # Create figure layout
        if is_reclaim:
            # 3 rows: Daily Price, Daily Volume, Intraday Zoom
            fig = plt.figure(figsize=(16, 14))
            # hspace=0 merges the first two (Price/Volume)
            # hspace=0.3 separates the Intraday chart
            gs = fig.add_gridspec(3, 1, height_ratios=[3, 1, 2], hspace=0.0) 
            ax1 = fig.add_subplot(gs[0])
            ax2 = fig.add_subplot(gs[1], sharex=ax1)
            
            # Separate the intraday chart visually
            gs_intra = fig.add_gridspec(3, 1, height_ratios=[3, 1, 2], hspace=0.3)
            ax3 = fig.add_subplot(gs_intra[2])
        else:
            # 2 rows: Daily Price, Daily Volume
            fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(16, 10), 
                                           gridspec_kw={'height_ratios': [3, 1], 'hspace': 0},
                                           sharex=True)
        
        # Main price chart
        self._plot_price_chart(ax1, window_df, signal_data, avwap_data, relative_entry_idx)
        
        # Volume chart
        self._plot_volume_chart(ax2, window_df, relative_entry_idx)
        
        # Hide x-labels for top plot (Price) to avoid clutter
        plt.setp(ax1.get_xticklabels(), visible=False)
        
        # Intraday Zoom for VWAP Reclaim
        if is_reclaim:
            self._plot_intraday_zoom(ax3, symbol, entry_date_pd, signal_data)
        
        # Title
        camino = signal_data.get('camino', 'N/A')
        outcome = signal_data.get('outcome', 'N/A')
        return_pct = signal_data.get('return_pct', 0)
        
        color = 'green' if outcome == 'WIN' else 'red'
        # Adjust title position slightly
        fig.suptitle(f"{symbol} - {camino} Setup | {entry_date} | "
                    f"Outcome: {outcome} ({return_pct:+.2f}%)",
                    fontsize=16, fontweight='bold', color=color, y=0.92)
        
        # Save
        output_dir = Path("backtest_charts")
        output_dir.mkdir(exist_ok=True)
        
        filename = f"{symbol}_{entry_date}_{camino}.png"
        output_path = output_dir / filename
        plt.savefig(output_path, dpi=100, bbox_inches='tight')
        print(f"[OK] Chart saved: {output_path}")
        
        plt.close()

    def _plot_intraday_zoom(self, ax, symbol: str, entry_date: pd.Timestamp, signal_data: dict):
        """Plot 5-minute intraday chart for the entry day"""
        try:
            # ... (rest of intraday logic remains same) ...
            # Check if date is within last 60 days for YFinance
            days_diff = (datetime.now() - entry_date).days
            if days_diff > 59:
                ax.text(0.5, 0.5, "Intraday data not available for >60 days old trades (API Limit)\nImagine: Gap Down -> Stabilization -> Cross above VWAP", 
                       ha='center', va='center', transform=ax.transAxes, fontsize=12, 
                       bbox=dict(facecolor='lightgray', alpha=0.5))
                ax.set_title(f"Intraday 5m Zoom - {entry_date.date()} (Data Unavailable)")
                return

            # Fetch 5m data
            # We ask for 5 days to be safe and filter
            intraday_df = self.data_provider.get_intraday_data(symbol, interval="5m", days=days_diff+5)
            
            if intraday_df.empty:
                ax.text(0.5, 0.5, "No Intraday Data Found", ha='center', va='center')
                return

            # Filter for entry date
            target_day_str = entry_date.strftime('%Y-%m-%d')
            day_data = intraday_df[intraday_df.index.strftime('%Y-%m-%d') == target_day_str].copy()
            
            if day_data.empty:
                ax.text(0.5, 0.5, f"No data for {target_day_str}", ha='center', va='center')
                return

            # Plot Intraday Candles
            x = np.arange(len(day_data))
            
            for i in range(len(day_data)):
                open_p = day_data['Open'].iloc[i]
                close_p = day_data['Close'].iloc[i]
                high_p = day_data['High'].iloc[i]
                low_p = day_data['Low'].iloc[i]
                
                color = 'green' if close_p >= open_p else 'red'
                
                # Wick
                ax.plot([i, i], [low_p, high_p], color='black', linewidth=0.5)
                # Body
                body_height = abs(close_p - open_p)
                body_bottom = min(open_p, close_p)
                if body_height == 0: body_height = 0.01 # Doji visibility
                
                rect = Rectangle((i - 0.3, body_bottom), 0.6, body_height, 
                               facecolor=color, edgecolor='black', linewidth=0.5)
                ax.add_patch(rect)

            # Calculate and Plot VWAP
            # VWAP = Cumulative (Price * Volume) / Cumulative Volume
            day_data['TP'] = (day_data['High'] + day_data['Low'] + day_data['Close']) / 3
            day_data['CumVol'] = day_data['Volume'].cumsum()
            day_data['CumVolPrice'] = (day_data['TP'] * day_data['Volume']).cumsum()
            day_data['VWAP'] = day_data['CumVolPrice'] / day_data['CumVol']
            
            ax.plot(x, day_data['VWAP'], color='orange', linewidth=2, label='Intraday VWAP')
            
            # Annotate Entry
            entry_price = signal_data.get('entry_price')
            if entry_price:
                ax.axhline(entry_price, color='cyan', linestyle='--', alpha=0.5, label=f'Entry Level: ${entry_price:.2f}')

            # Formatting
            ax.set_title(f"[U+1F50D] Intraday 5m Action - {target_day_str} (VWAP Defense)", fontsize=12, fontweight='bold')
            ax.set_ylabel('Price ($)')
            ax.grid(True, alpha=0.3)
            ax.legend(loc='upper left')
            
            # X-Axis Time labels
            times = day_data.index.strftime('%H:%M')
            step = max(1, len(day_data) // 10)
            ax.set_xticks(x[::step])
            ax.set_xticklabels(times[::step], rotation=45)
            
        except Exception as e:
            print(f"Error plotting intraday: {e}")
            ax.text(0.5, 0.5, f"Error: {str(e)}", ha='center', va='center')

    def _plot_price_chart(self, ax, df, signal_data, avwap_data, entry_idx):
        """Plot price chart with indicators"""
        x = np.arange(len(df))
        
        # Plot candlesticks
        for i in range(len(df)):
            open_price = df['Open'].iloc[i]
            close_price = df['Close'].iloc[i]
            high_price = df['High'].iloc[i]
            low_price = df['Low'].iloc[i]
            
            color = 'green' if close_price >= open_price else 'red'
            
            # High-Low line
            ax.plot([i, i], [low_price, high_price], color='black', linewidth=0.5)
            
            # Body
            body_height = abs(close_price - open_price)
            body_bottom = min(open_price, close_price)
            rect = Rectangle((i - 0.3, body_bottom), 0.6, body_height, 
                           facecolor=color, edgecolor='black', linewidth=0.5)
            ax.add_patch(rect)
        
        # --- INDICATORS ---
        
        # AVWAP line (Global context)
        if avwap_data.get('calculated'):
            avwap_price = avwap_data['current_avwap']
            ax.axhline(avwap_price, color='orange', linestyle='--', linewidth=2, 
                      label=f'AVWAP ATH: ${avwap_price:.2f}', alpha=0.7)
        
        # --- STRATEGY SPECIFIC ANNOTATIONS ---
        
        camino = signal_data.get('camino')
        # entry_idx is now passed correctly!
        
        # 1. CAMINO 1: BLUE SKY (Base High Focus)
        if camino == 'BLUE_SKY' or signal_data.get('base_high'):
             if signal_data.get('base_high'):
                ax.axhline(signal_data['base_high'], color='blue', linestyle='--', 
                          linewidth=2, label=f"Base High: ${signal_data['base_high']:.2f}", alpha=0.7)

        # 2. CAMINO 2: VWAP RECLAIM (Gap & Session Low Focus)
        elif camino == 'VWAP_RECLAIM':
            # Highlight the Gap
            if entry_idx > 0:
                prev_close = df['Close'].iloc[entry_idx - 1]
                curr_open = df['Open'].iloc[entry_idx]
                
                # Draw Gap arrow if meaningful gap down
                if curr_open < prev_close:
                    gap_mid = (prev_close + curr_open) / 2
                    ax.annotate('Gap Down', xy=(entry_idx, gap_mid), xytext=(entry_idx-2, gap_mid),
                               arrowprops=dict(facecolor='black', shrink=0.05, width=1, headwidth=5),
                               fontsize=9, color='red')
            
            # Explicitly label Session Low
            if signal_data.get('stop_loss'):
                 ax.text(entry_idx + 1, signal_data['stop_loss'], ' Session Low (Risk)', 
                        verticalalignment='center', fontsize=8, color='red')

        # --- TRADE EXECUTION MARKERS ---
        
        # Entry point
        entry_price = signal_data.get('entry_price')
        if entry_price:
            marker_color = 'lime' if camino == 'BLUE_SKY' else '#00FFFF' # Cyan for Reclaim
            ax.scatter(entry_idx, entry_price, color=marker_color, s=200, marker='^', 
                      zorder=5, label=f'Entry: ${entry_price:.2f}', edgecolors='black', linewidths=2)
        
        # Stop loss line
        stop_loss = signal_data.get('stop_loss')
        if stop_loss:
            ax.axhline(stop_loss, color='red', linestyle=':', linewidth=2, 
                      label=f'Stop: ${stop_loss:.2f}', alpha=0.7)
        
        # Exit point
        exit_price = signal_data.get('exit_price')
        hold_days = signal_data.get('hold_days', 5)
        if exit_price:
            exit_idx = entry_idx + hold_days
            if exit_idx < len(df):
                outcome = signal_data.get('outcome')
                color = 'green' if outcome == 'WIN' else 'red'
                marker = 'v' if outcome == 'LOSS' else 'o'
                ax.scatter(exit_idx, exit_price, color=color, s=200, marker=marker, 
                          zorder=5, label=f'Exit: ${exit_price:.2f}', edgecolors='black', linewidths=2)
        
        # Formatting
        ax.set_ylabel('Price ($)')
        ax.legend(loc='upper left', fontsize=10)
        ax.grid(True, alpha=0.3)
        
        # X-axis handling is done by parent with sharex
        # But we still need to set ticks logic if it's the bottom plot (but this is ax1, top)
        # Ticks are shared. We set them on the bottom plot primarily, or matplotlib handles it.
        # But for custom date labels, we should set them on the shared axis.
        # Let's let _plot_volume_chart handle the labels since it's at the bottom.
    
    def _plot_volume_chart(self, ax, df, entry_idx):
        """Plot volume bars"""
        x = np.arange(len(df))
        colors = ['green' if df['Close'].iloc[i] >= df['Open'].iloc[i] else 'red' 
                 for i in range(len(df))]
        
        ax.bar(x, df['Volume'], color=colors, alpha=0.5)
        
        # Entry marker
        if entry_idx >= 0 and entry_idx < len(df):
             ax.axvline(entry_idx, color='lime', linestyle='--', linewidth=2, alpha=0.7)
        
        ax.set_ylabel('Volume')
        ax.set_xlabel('Date')
        ax.grid(True, alpha=0.3)
        
        # X-axis labels (Now critical since shared)
        date_labels = df.index.strftime('%Y-%m-%d')
        step = max(1, len(df) // 10)
        ax.set_xticks(x[::step])
        ax.set_xticklabels(date_labels[::step], rotation=45, ha='right')
    
    def visualize_all_trades(self, results_csv: str, max_trades: int = 20):
        """Generate charts for all trades"""
        results_df = pd.read_csv(results_csv)
        results_df['date'] = pd.to_datetime(results_df['date'])
        
        print(f"\n[U+1F4CA] Generating charts for {min(len(results_df), max_trades)} trades...")
        
        for i, row in results_df.head(max_trades).iterrows():
            print(f"[{i+1}/{min(max_trades, len(results_df))}] {row['symbol']} - {row['date'].date()}")
            
            signal_data = {
                'camino': row['camino'],
                'entry_price': row['entry_price'],
                'stop_loss': row['stop_loss'],
                'base_high': row.get('base_high'),
                'exit_price': row['exit_price'],
                'outcome': row['outcome'],
                'return_pct': row['return_pct'],
                'hold_days': row['hold_days']
            }
            
            self.visualize_trade(
                symbol=row['symbol'],
                entry_date=row['date'].strftime('%Y-%m-%d'),
                signal_data=signal_data,
                days_before=30,
                days_after=15
            )
        
        print(f"\n[OK] Charts in ./backtest_charts/")
    
    def create_summary_dashboard(self, results_csv: str):
        """Create summary dashboard"""
        results_df = pd.read_csv(results_csv)
        results_df['date'] = pd.to_datetime(results_df['date'])
        
        fig, axes = plt.subplots(2, 2, figsize=(16, 12))
        
        # 1. Returns Distribution
        ax = axes[0, 0]
        wins = results_df[results_df['outcome'] == 'WIN']['return_pct']
        losses = results_df[results_df['outcome'] == 'LOSS']['return_pct']
        
        ax.hist([wins, losses], bins=20, label=['Wins', 'Losses'], 
               color=['green', 'red'], alpha=0.7)
        ax.set_xlabel('Return %')
        ax.set_ylabel('Frequency')
        ax.set_title('Returns Distribution')
        ax.legend()
        ax.grid(True, alpha=0.3)
        
        # 2. Win Rate by Camino
        ax = axes[0, 1]
        camino_stats = []
        for camino in results_df['camino'].unique():
            subset = results_df[results_df['camino'] == camino]
            win_rate = (subset['outcome'] == 'WIN').sum() / len(subset) * 100
            camino_stats.append({'Camino': camino, 'Win Rate': win_rate, 'Count': len(subset)})
        
        stats_df = pd.DataFrame(camino_stats)
        bars = ax.bar(stats_df['Camino'], stats_df['Win Rate'], 
                     color=['#2E86AB', '#A23B72', '#F18F01'])
        ax.set_ylabel('Win Rate (%)')
        ax.set_title('Win Rate by Camino')
        ax.axhline(50, color='red', linestyle='--', alpha=0.5, label='50%')
        ax.legend()
        ax.grid(True, alpha=0.3)
        
        # Add counts
        for bar, count in zip(bars, stats_df['Count']):
            height = bar.get_height()
            ax.text(bar.get_x() + bar.get_width()/2., height + 2,
                   f'n={count}', ha='center', va='bottom', fontsize=10)
        
        # 3. Equity Curve
        ax = axes[1, 0]
        results_df_sorted = results_df.sort_values('date')
        results_df_sorted['cumulative_return'] = (1 + results_df_sorted['return_pct']/100).cumprod() - 1
        
        ax.plot(results_df_sorted['date'], results_df_sorted['cumulative_return'] * 100, 
               linewidth=2, color='#2E86AB')
        ax.fill_between(results_df_sorted['date'], 0, results_df_sorted['cumulative_return'] * 100, 
                       alpha=0.3, color='#2E86AB')
        ax.set_xlabel('Date')
        ax.set_ylabel('Cumulative Return (%)')
        ax.set_title('Equity Curve')
        ax.grid(True, alpha=0.3)
        ax.axhline(0, color='black', linewidth=0.8)
        
        # 4. Statistics
        ax = axes[1, 1]
        ax.axis('off')
        
        total_trades = len(results_df)
        wins = len(results_df[results_df['outcome'] == 'WIN'])
        losses = len(results_df[results_df['outcome'] == 'LOSS'])
        win_rate = wins / total_trades * 100
        avg_win = results_df[results_df['outcome'] == 'WIN']['return_pct'].mean()
        avg_loss = results_df[results_df['outcome'] == 'LOSS']['return_pct'].mean()
        avg_return = results_df['return_pct'].mean()
        total_return = results_df_sorted['cumulative_return'].iloc[-1] * 100
        
        stats_text = f"""
BACKTEST STATISTICS
{'='*40}

Total Trades:        {total_trades}
Wins:                {wins}
Losses:              {losses}
Win Rate:            {win_rate:.1f}%

Avg Win:             {avg_win:.2f}%
Avg Loss:            {avg_loss:.2f}%
Avg Return:          {avg_return:.2f}%

Total Return:        {total_return:.2f}%

Best Trade:          {results_df['return_pct'].max():.2f}%
Worst Trade:         {results_df['return_pct'].min():.2f}%

Symbols:             {results_df['symbol'].nunique()}
Date Range:          {results_df['date'].min().date()} 
                     to {results_df['date'].max().date()}
        """
        
        ax.text(0.1, 0.9, stats_text, transform=ax.transAxes, 
               fontsize=12, verticalalignment='top', fontfamily='monospace',
               bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))
        
        plt.suptitle('BACKTEST SUMMARY DASHBOARD', fontsize=18, fontweight='bold')
        plt.tight_layout()
        
        # Save
        output_path = Path("backtest_charts") / "summary_dashboard.png"
        plt.savefig(output_path, dpi=100, bbox_inches='tight')
        print(f"\n[OK] Dashboard saved: {output_path}")
        
        plt.close()


def main():
    """Visualize backtest results"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Visualize Backtest Results')
    parser.add_argument('results_csv', help='Path to backtest results CSV')
    parser.add_argument('--max-trades', type=int, default=20, 
                       help='Max trades to chart (default: 20)')
    parser.add_argument('--summary-only', action='store_true',
                       help='Only generate summary dashboard')
    
    args = parser.parse_args()
    
    if not Path(args.results_csv).exists():
        print(f"[FAIL] File not found: {args.results_csv}")
        sys.exit(1)
    
    visualizer = BacktestVisualizer()
    
    # Summary dashboard
    print("[U+1F4CA] Creating summary dashboard...")
    visualizer.create_summary_dashboard(args.results_csv)
    
    # Individual charts
    if not args.summary_only:
        visualizer.visualize_all_trades(args.results_csv, max_trades=args.max_trades)
    
    print("\n[OK] Complete! Check ./backtest_charts/")


if __name__ == "__main__":
    main()
