#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Interactive Web Dashboard for Backtest Results
Creates interactive charts with Plotly
"""
import sys
from pathlib import Path
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import plotly.express as px
import webbrowser
from datetime import datetime

# Fix imports
project_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(project_root))

from src.data.market_data import MarketDataProvider
from src.indicators.triad import TriadIndicators


class InteractiveDashboard:
    
    def __init__(self, results_csv: str):
        self.results_df = pd.read_csv(results_csv)
        # Fix column name mismatch: Dashboard expects 'date', CSV has 'entry_date'
        if 'date' not in self.results_df.columns and 'entry_date' in self.results_df.columns:
            self.results_df['date'] = pd.to_datetime(self.results_df['entry_date'])
        else:
            self.results_df['date'] = pd.to_datetime(self.results_df['date'])
            
        self.data_provider = MarketDataProvider()
        self.indicators = TriadIndicators()
        
        print(f"📊 Loaded {len(self.results_df)} signals")
        print(f"   Symbols: {self.results_df['symbol'].nunique()}")
        print(f"   Date range: {self.results_df['date'].min().date()} to {self.results_df['date'].max().date()}")
    
    def create_overview_dashboard(self):
        """Create main overview dashboard with filters"""
        
        # Create subplots
        fig = make_subplots(
            rows=3, cols=2,
            subplot_titles=(
                '📊 Returns Distribution',
                '🎯 Win Rate by Camino',
                '📈 Equity Curve',
                '💰 Returns by Symbol',
                '📅 Signals Over Time',
                '🔍 Risk vs Reward'
            ),
            specs=[
                [{'type': 'histogram'}, {'type': 'bar'}],
                [{'type': 'scatter', 'colspan': 2}, None],
                [{'type': 'bar'}, {'type': 'scatter'}]
            ],
            vertical_spacing=0.12,
            horizontal_spacing=0.1
        )
        
        # 1. Returns Distribution
        wins = self.results_df[self.results_df['outcome'] == 'WIN']['return_pct']
        losses = self.results_df[self.results_df['outcome'] == 'LOSS']['return_pct']
        
        fig.add_trace(
            go.Histogram(x=wins, name='Wins', marker_color='green', opacity=0.7, nbinsx=30),
            row=1, col=1
        )
        fig.add_trace(
            go.Histogram(x=losses, name='Losses', marker_color='red', opacity=0.7, nbinsx=30),
            row=1, col=1
        )
        
        # 2. Win Rate by Camino
        camino_stats = []
        for camino in self.results_df['camino'].unique():
            subset = self.results_df[self.results_df['camino'] == camino]
            win_rate = (subset['outcome'] == 'WIN').sum() / len(subset) * 100
            camino_stats.append({
                'Camino': camino,
                'Win Rate': win_rate,
                'Count': len(subset)
            })
        
        stats_df = pd.DataFrame(camino_stats)
        colors = ['#2E86AB', '#A23B72', '#F18F01']
        
        fig.add_trace(
            go.Bar(
                x=stats_df['Camino'],
                y=stats_df['Win Rate'],
                text=[f"{wr:.1f}%<br>n={cnt}" for wr, cnt in zip(stats_df['Win Rate'], stats_df['Count'])],
                textposition='auto',
                marker_color=colors[:len(stats_df)],
                name='Win Rate'
            ),
            row=1, col=2
        )
        
        # Add 50% reference line
        fig.add_hline(y=50, line_dash="dash", line_color="red", opacity=0.5, row=1, col=2)
        
        # 3. Equity Curve
        sorted_df = self.results_df.sort_values('date')
        sorted_df['cumulative_return'] = (1 + sorted_df['return_pct']/100).cumprod() - 1
        
        fig.add_trace(
            go.Scatter(
                x=sorted_df['date'],
                y=sorted_df['cumulative_return'] * 100,
                mode='lines',
                name='Equity Curve',
                line=dict(color='#2E86AB', width=3),
                fill='tozeroy',
                fillcolor='rgba(46, 134, 171, 0.2)'
            ),
            row=2, col=1
        )
        
        fig.add_hline(y=0, line_dash="solid", line_color="black", opacity=0.3, row=2, col=1)
        
        # 4. Returns by Symbol
        symbol_returns = self.results_df.groupby('symbol').agg({
            'return_pct': 'mean',
            'outcome': lambda x: (x == 'WIN').sum() / len(x) * 100
        }).reset_index()
        symbol_returns.columns = ['Symbol', 'Avg Return', 'Win Rate']
        
        fig.add_trace(
            go.Bar(
                x=symbol_returns['Symbol'],
                y=symbol_returns['Avg Return'],
                text=[f"{ret:+.1f}%<br>WR:{wr:.0f}%" for ret, wr in zip(symbol_returns['Avg Return'], symbol_returns['Win Rate'])],
                textposition='auto',
                marker_color=['green' if x > 0 else 'red' for x in symbol_returns['Avg Return']],
                name='Avg Return'
            ),
            row=3, col=1
        )
        
        # 5. Risk vs Reward scatter
        self.results_df['risk_pct'] = abs(
            (self.results_df['entry_price'] - self.results_df['stop_loss']) / self.results_df['entry_price'] * 100
        )
        
        fig.add_trace(
            go.Scatter(
                x=self.results_df['risk_pct'],
                y=self.results_df['return_pct'],
                mode='markers',
                marker=dict(
                    color=self.results_df['return_pct'],
                    colorscale='RdYlGn',
                    size=8,
                    colorbar=dict(title="Return %", x=1.15)
                ),
                text=[f"{sym}<br>{date.date()}<br>{cam}" 
                      for sym, date, cam in zip(self.results_df['symbol'], 
                                                 self.results_df['date'],
                                                 self.results_df['camino'])],
                hovertemplate='<b>%{text}</b><br>Risk: %{x:.2f}%<br>Return: %{y:.2f}%<extra></extra>',
                name='Trades'
            ),
            row=3, col=2
        )
        
        # Add ideal R:R lines
        max_risk = self.results_df['risk_pct'].max()
        fig.add_trace(
            go.Scatter(
                x=[0, max_risk],
                y=[0, max_risk * 2],
                mode='lines',
                line=dict(dash='dash', color='gray'),
                name='2:1 R/R',
                showlegend=False
            ),
            row=3, col=2
        )
        
        # Update layout
        fig.update_xaxes(title_text="Return %", row=1, col=1)
        fig.update_yaxes(title_text="Frequency", row=1, col=1)
        
        fig.update_xaxes(title_text="Camino", row=1, col=2)
        fig.update_yaxes(title_text="Win Rate %", row=1, col=2)
        
        fig.update_xaxes(title_text="Date", row=2, col=1)
        fig.update_yaxes(title_text="Cumulative Return %", row=2, col=1)
        
        fig.update_xaxes(title_text="Symbol", row=3, col=1)
        fig.update_yaxes(title_text="Avg Return %", row=3, col=1)
        
        fig.update_xaxes(title_text="Risk %", row=3, col=2)
        fig.update_yaxes(title_text="Return %", row=3, col=2)
        
        fig.update_layout(
            title_text="<b>📊 TRIAD BACKTEST DASHBOARD</b><br><sup>Interactive Analysis</sup>",
            title_font_size=24,
            showlegend=True,
            height=1200,
            template='plotly_white'
        )
        
        return fig
    
    def create_trade_chart(self, symbol: str, entry_date: str, signal_data: dict):
        """Create interactive candlestick chart for a single trade"""
        
        # Fetch data
        daily_df = self.data_provider.get_daily_data(symbol, period="max")
        daily_df.index = pd.to_datetime(daily_df.index).tz_localize(None)
        
        entry_date_pd = pd.to_datetime(entry_date).tz_localize(None)
        
        # Find entry index
        entry_idx = daily_df.index.get_indexer([entry_date_pd], method='nearest')[0]
        
        # Get window
        start_idx = max(0, entry_idx - 30)
        end_idx = min(len(daily_df), entry_idx + 15)
        window_df = daily_df.iloc[start_idx:end_idx].copy()
        
        # Calculate SMAs for context
        window_df['SMA_10'] = window_df['Close'].rolling(window=10).mean()
        window_df['SMA_20'] = window_df['Close'].rolling(window=20).mean()
        
        # Calculate AVWAP
        historical_df = daily_df.iloc[:entry_idx+1]
        avwap_data = self.indicators.calculate_avwap_from_ath(historical_df)
        
        # Create candlestick
        fig = go.Figure()
        
        fig.add_trace(go.Candlestick(
            x=window_df.index,
            open=window_df['Open'],
            high=window_df['High'],
            low=window_df['Low'],
            close=window_df['Close'],
            name='Price',
            increasing_line_color='green',
            decreasing_line_color='red'
        ))
        
        # Add SMA 10
        fig.add_trace(go.Scatter(
            x=window_df.index,
            y=window_df['SMA_10'],
            mode='lines',
            line=dict(color='#FFD700', width=1.5), # Gold
            name='SMA 10'
        ))

        # Add SMA 20
        fig.add_trace(go.Scatter(
            x=window_df.index,
            y=window_df['SMA_20'],
            mode='lines',
            line=dict(color='#1E90FF', width=1.5), # Dodger Blue
            name='SMA 20'
        ))
        
        # Add AVWAP line
        if avwap_data.get('calculated'):
            fig.add_hline(
                y=avwap_data['current_avwap'],
                line_dash="dash",
                line_color="orange",
                line_width=2,
                annotation_text=f"AVWAP ATH: ${avwap_data['current_avwap']:.2f}",
                annotation_position="right"
            )
        
        # Add Base High
        if signal_data.get('base_high'):
            fig.add_hline(
                y=signal_data['base_high'],
                line_dash="dash",
                line_color="blue",
                line_width=2,
                annotation_text=f"Base High: ${signal_data['base_high']:.2f}",
                annotation_position="right"
            )
        
        # Add Stop Loss / Session Low
        if signal_data.get('stop_loss'):
            fig.add_hline(
                y=signal_data['stop_loss'],
                line_dash="dot",
                line_color="red",
                line_width=2,
                annotation_text=f"Stop: ${signal_data['stop_loss']:.2f}",
                annotation_position="right"
            )
            # Explicit Session Low Annotation for Masterclass feel
            fig.add_annotation(
                x=entry_date_pd,
                y=signal_data['stop_loss'],
                text="Session Low (Risk)",
                showarrow=True,
                arrowhead=2,
                arrowcolor="red",
                ax=0,
                ay=40
            )

        # GAP DOWN Detection (Masterclass feature)
        if signal_data.get('camino') == 'VWAP_RECLAIM' and entry_idx > 0:
            prev_close = daily_df['Close'].iloc[entry_idx - 1]
            curr_open = daily_df['Open'].iloc[entry_idx]
            
            if curr_open < prev_close:
                gap_mid = (prev_close + curr_open) / 2
                fig.add_annotation(
                    x=entry_date_pd,
                    y=gap_mid,
                    text="Gap Down",
                    showarrow=True,
                    arrowhead=1,
                    arrowcolor="red",
                    ax=-40,
                    ay=0
                )
        
        # Entry point
        if signal_data.get('entry_price'):
            fig.add_trace(go.Scatter(
                x=[entry_date_pd],
                y=[signal_data['entry_price']],
                mode='markers',
                marker=dict(color='lime', size=15, symbol='triangle-up', line=dict(color='black', width=2)),
                name='Entry',
                hovertemplate=f"<b>ENTRY</b><br>${signal_data['entry_price']:.2f}<extra></extra>"
            ))
        
        # Exit point
        if signal_data.get('exit_price'):
            exit_date = entry_date_pd + pd.Timedelta(days=signal_data.get('hold_days', 5))
            outcome = signal_data.get('outcome')
            color = 'green' if outcome == 'WIN' else 'red'
            symbol_marker = 'circle' if outcome == 'WIN' else 'triangle-down'
            
            fig.add_trace(go.Scatter(
                x=[exit_date],
                y=[signal_data['exit_price']],
                mode='markers',
                marker=dict(color=color, size=15, symbol=symbol_marker, line=dict(color='black', width=2)),
                name='Exit',
                hovertemplate=f"<b>EXIT ({outcome})</b><br>${signal_data['exit_price']:.2f}<extra></extra>"
            ))
        
        # Layout
        camino = signal_data.get('camino', 'N/A')
        outcome = signal_data.get('outcome', 'N/A')
        return_pct = signal_data.get('return_pct', 0)
        
        title_color = 'green' if outcome == 'WIN' else 'red'
        
        fig.update_layout(
            title=f"<b>{symbol}</b> - {camino} | {entry_date} | <span style='color:{title_color}'>{outcome} ({return_pct:+.2f}%)</span>",
            xaxis_title="Date",
            yaxis_title="Price ($)",
            template='plotly_white',
            hovermode='x unified',
            height=600,
            xaxis_rangeslider_visible=False,
            xaxis=dict(
                rangebreaks=[
                    dict(bounds=["sat", "mon"]), # Hide weekends
                ]
            )
        )
        
        return fig
    
    def create_intraday_chart(self, symbol: str, entry_date: str, signal_data: dict):
        """Create interactive 5m intraday chart for VWAP Reclaim"""
        entry_date_pd = pd.to_datetime(entry_date).tz_localize(None)
        
        # Check if date is within last 60 days for YFinance limits
        days_diff = (datetime.now() - entry_date_pd).days
        if days_diff > 59:
            fig = go.Figure()
            fig.add_annotation(text="Intraday data not available for >60 days old trades (API Limit)",
                              xref="paper", yref="paper", x=0.5, y=0.5, showarrow=False)
            fig.update_layout(title=f"Intraday 5m - {symbol} (Data Unavailable)")
            return fig

        # Fetch 5m data
        intraday_df = self.data_provider.get_intraday_data(symbol, interval="5m", days=days_diff+5)
        
        if intraday_df.empty:
            return None

        # Filter for entry date
        target_day_str = entry_date_pd.strftime('%Y-%m-%d')
        day_data = intraday_df[intraday_df.index.strftime('%Y-%m-%d') == target_day_str].copy()
        
        if day_data.empty:
            return None

        # Calculate VWAP
        day_data['TP'] = (day_data['High'] + day_data['Low'] + day_data['Close']) / 3
        day_data['CumVol'] = day_data['Volume'].cumsum()
        day_data['CumVolPrice'] = (day_data['TP'] * day_data['Volume']).cumsum()
        day_data['VWAP'] = day_data['CumVolPrice'] / day_data['CumVol']

        fig = go.Figure()

        # Candlesticks
        fig.add_trace(go.Candlestick(
            x=day_data.index,
            open=day_data['Open'],
            high=day_data['High'],
            low=day_data['Low'],
            close=day_data['Close'],
            name='Price 5m'
        ))

        # VWAP Line
        fig.add_trace(go.Scatter(
            x=day_data.index,
            y=day_data['VWAP'],
            mode='lines',
            line=dict(color='orange', width=2),
            name='Intraday VWAP'
        ))

        # Entry Level
        entry_price = signal_data.get('entry_price')
        if entry_price:
            fig.add_hline(y=entry_price, line_dash="dash", line_color="cyan", annotation_text="Entry Level")

        # Session Low / Stop
        stop_loss = signal_data.get('stop_loss')
        if stop_loss:
             fig.add_hline(y=stop_loss, line_dash="dot", line_color="red", annotation_text="Session Low (Stop)")

        fig.update_layout(
            title=f"<b>🔍 Intraday 5m Zoom - {symbol}</b><br><sup>VWAP Defense Analysis | {target_day_str}</sup>",
            yaxis_title="Price ($)",
            xaxis_title="Time",
            template='plotly_white',
            height=500,
            xaxis_rangeslider_visible=False
        )
        
        return fig
    
    def create_symbol_detail_page(self, symbol: str):
        """Create detailed page for a specific symbol"""
        
        symbol_df = self.results_df[self.results_df['symbol'] == symbol].sort_values('date')
        
        if symbol_df.empty:
            print(f"No data for {symbol}")
            return None
        
        # Create subplots
        fig = make_subplots(
            rows=2, cols=2,
            subplot_titles=(
                f'📈 {symbol} - Cumulative P&L',
                f'📊 Trade Statistics',
                f'📅 Returns Over Time',
                f'🎯 Win/Loss Distribution'
            ),
            specs=[
                [{'type': 'scatter'}, {'type': 'indicator'}],
                [{'type': 'scatter'}, {'type': 'bar'}]
            ],
            vertical_spacing=0.15
        )
        
        # 1. Cumulative P&L
        symbol_df['cumulative'] = (1 + symbol_df['return_pct']/100).cumprod() - 1
        
        fig.add_trace(
            go.Scatter(
                x=symbol_df['date'],
                y=symbol_df['cumulative'] * 100,
                mode='lines+markers',
                name='Cumulative Return',
                line=dict(color='#2E86AB', width=2),
                fill='tozeroy'
            ),
            row=1, col=1
        )
        
        # 2. Statistics indicator
        wins = len(symbol_df[symbol_df['outcome'] == 'WIN'])
        total = len(symbol_df)
        win_rate = wins / total * 100
        
        fig.add_trace(
            go.Indicator(
                mode="number+delta",
                value=win_rate,
                title={"text": f"Win Rate<br><span style='font-size:0.8em'>{wins}/{total} wins</span>"},
                delta={'reference': 50, 'relative': False},
                domain={'x': [0, 1], 'y': [0, 1]},
                number={'suffix': "%"}
            ),
            row=1, col=2
        )
        
        # 3. Individual returns over time
        colors = ['green' if x > 0 else 'red' for x in symbol_df['return_pct']]
        
        fig.add_trace(
            go.Scatter(
                x=symbol_df['date'],
                y=symbol_df['return_pct'],
                mode='markers',
                marker=dict(color=colors, size=10),
                name='Trade Returns',
                text=[f"{cam}<br>{ret:+.2f}%" for cam, ret in zip(symbol_df['camino'], symbol_df['return_pct'])],
                hovertemplate='<b>%{text}</b><extra></extra>'
            ),
            row=2, col=1
        )
        
        # 4. Win/Loss distribution
        outcomes = symbol_df['outcome'].value_counts()
        
        fig.add_trace(
            go.Bar(
                x=outcomes.index,
                y=outcomes.values,
                marker_color=['green' if x == 'WIN' else 'red' for x in outcomes.index],
                text=outcomes.values,
                textposition='auto',
                showlegend=False
            ),
            row=2, col=2
        )
        
        fig.update_layout(
            title_text=f"<b>{symbol} - Detailed Analysis</b><br><sup>Total Trades: {total} | Win Rate: {win_rate:.1f}% | Avg Return: {symbol_df['return_pct'].mean():+.2f}%</sup>",
            title_font_size=20,
            height=800,
            showlegend=False,
            template='plotly_white'
        )
        
        return fig
    
    def generate_html_report(self, output_file: str = "outputs/backtests/backtest_dashboard.html"):
        """Generate complete HTML report with all charts"""
        
        print("\n📊 Generating Interactive Dashboard...")
        
        # Overview dashboard
        print("  Creating overview dashboard...")
        overview_fig = self.create_overview_dashboard()
        
        # Symbol details
        print("  Creating symbol detail pages...")
        symbol_figs = {}
        for symbol in self.results_df['symbol'].unique():
            print(f"    Processing {symbol}...")
            symbol_figs[symbol] = self.create_symbol_detail_page(symbol)
        
        # Top trades
        print("  Creating top trades charts...")
        top_wins = self.results_df.nlargest(5, 'return_pct')
        top_losses = self.results_df.nsmallest(5, 'return_pct')
        
        trade_figs = []
        for idx, row in pd.concat([top_wins, top_losses]).iterrows():
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
            fig = self.create_trade_chart(row['symbol'], row['date'].strftime('%Y-%m-%d'), signal_data)
            trade_figs.append(fig)
        
        # Generate HTML
        print("  Generating HTML file...")
        
        # Calculate advanced metrics
        wins = (self.results_df['outcome'] == 'WIN').sum()
        losses = (self.results_df['outcome'] == 'LOSS').sum()
        total_trades = len(self.results_df)
        win_rate = (wins / total_trades * 100) if total_trades > 0 else 0
        
        avg_win = self.results_df[self.results_df['outcome'] == 'WIN']['return_pct'].mean() if wins > 0 else 0
        avg_loss = abs(self.results_df[self.results_df['outcome'] == 'LOSS']['return_pct'].mean()) if losses > 0 else 0
        
        # Risk/Reward Ratio
        rr_ratio = (avg_win / avg_loss) if avg_loss > 0 else 0
        
        # Total R (assuming 1R per trade risk)
        total_r = self.results_df['return_pct'].sum() / (self.results_df['risk_pct'].mean() if 'risk_pct' in self.results_df.columns else 1)
        
        # Profit Factor
        total_wins = self.results_df[self.results_df['outcome'] == 'WIN']['return_pct'].sum()
        total_losses = abs(self.results_df[self.results_df['outcome'] == 'LOSS']['return_pct'].sum())
        profit_factor = (total_wins / total_losses) if total_losses > 0 else 0
        
        # Expectancy in R
        expectancy_r = (win_rate/100 * avg_win - (1 - win_rate/100) * avg_loss) / (self.results_df['risk_pct'].mean() if 'risk_pct' in self.results_df.columns else 1)
        
        # Total return
        cumulative_return = ((1 + self.results_df['return_pct']/100).prod() - 1) * 100
        
        # Market filter info (if available in data)
        date_range_str = f"{self.results_df['date'].min().strftime('%Y-%m-%d')} to {self.results_df['date'].max().strftime('%Y-%m-%d')}"
        
        html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Triad Backtest Dashboard</title>
    <script src="https://cdn.plot.ly/plotly-latest.min.js"></script>
    <style>
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            margin: 0;
            padding: 20px;
            background-color: #f5f5f5;
        }}
        .header {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 30px;
            border-radius: 10px;
            margin-bottom: 30px;
            text-align: center;
        }}
        .section {{
            background: white;
            padding: 20px;
            margin-bottom: 30px;
            border-radius: 10px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        .section-title {{
            font-size: 24px;
            font-weight: bold;
            margin-bottom: 20px;
            color: #333;
        }}
        .metrics-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
            gap: 15px;
            margin-bottom: 30px;
        }}
        .metric-card {{
            background: white;
            border: 2px solid #e0e0e0;
            border-radius: 10px;
            padding: 20px;
            text-align: center;
            transition: transform 0.2s, box-shadow 0.2s;
        }}
        .metric-card:hover {{
            transform: translateY(-5px);
            box-shadow: 0 4px 12px rgba(0,0,0,0.15);
        }}
        .metric-value {{
            font-size: 32px;
            font-weight: bold;
            margin-bottom: 8px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
        }}
        .metric-label {{
            font-size: 13px;
            color: #666;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }}
        .metric-card.positive .metric-value {{
            background: linear-gradient(135deg, #11998e 0%, #38ef7d 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
        }}
        .metric-card.negative .metric-value {{
            background: linear-gradient(135deg, #ee0979 0%, #ff6a00 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
        }}
        .nav-tabs {{
            display: flex;
            gap: 10px;
            margin-bottom: 20px;
            flex-wrap: wrap;
        }}
        .nav-tab {{
            padding: 12px 24px;
            background: #667eea;
            color: white;
            border: none;
            border-radius: 8px;
            cursor: pointer;
            font-size: 15px;
            transition: all 0.3s;
            font-weight: 500;
        }}
        .nav-tab:hover {{
            background: #764ba2;
            transform: translateY(-2px);
            box-shadow: 0 4px 8px rgba(0,0,0,0.2);
        }}
        .nav-tab.active {{
            background: #764ba2;
            box-shadow: 0 4px 8px rgba(0,0,0,0.2);
        }}
        .tab-content {{
            display: none;
        }}
        .tab-content.active {{
            display: block;
        }}
    </style>
</head>
<body>
    <div class="header">
        <h1>&#128200; TRIAD MOMENTUM BACKTEST DASHBOARD</h1>
        <p>Interactive Analysis - Generated {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
        <p style="font-size: 14px; opacity: 0.9;">Period: {date_range_str} | &#128737; Market Regime Filters Applied</p>
    </div>
    
    <div class="section">
        <div class="section-title">Performance Metrics</div>
        <div class="metrics-grid">
            <div class="metric-card {'positive' if cumulative_return > 0 else 'negative'}">
                <div class="metric-value">{cumulative_return:+.2f}%</div>
                <div class="metric-label">Total Return</div>
            </div>
            <div class="metric-card">
                <div class="metric-value">{total_trades}</div>
                <div class="metric-label">Total Trades</div>
            </div>
            <div class="metric-card {'positive' if win_rate >= 50 else 'negative'}">
                <div class="metric-value">{win_rate:.1f}%</div>
                <div class="metric-label">Win Rate</div>
            </div>
            <div class="metric-card positive">
                <div class="metric-value">{wins}</div>
                <div class="metric-label">Winners</div>
            </div>
            <div class="metric-card negative">
                <div class="metric-value">{losses}</div>
                <div class="metric-label">Losers</div>
            </div>
            <div class="metric-card {'positive' if rr_ratio >= 2 else 'negative'}">
                <div class="metric-value">{rr_ratio:.2f}</div>
                <div class="metric-label">Risk/Reward Ratio</div>
            </div>
            <div class="metric-card {'positive' if total_r > 0 else 'negative'}">
                <div class="metric-value">{total_r:.2f}R</div>
                <div class="metric-label">Total R</div>
            </div>
            <div class="metric-card {'positive' if profit_factor > 1 else 'negative'}">
                <div class="metric-value">{profit_factor:.2f}</div>
                <div class="metric-label">Profit Factor</div>
            </div>
            <div class="metric-card {'positive' if expectancy_r > 0 else 'negative'}">
                <div class="metric-value">{expectancy_r:.2f}R</div>
                <div class="metric-label">Expectancy (R)</div>
            </div>
            <div class="metric-card positive">
                <div class="metric-value">{avg_win:.2f}%</div>
                <div class="metric-label">Avg Win</div>
            </div>
            <div class="metric-card negative">
                <div class="metric-value">{avg_loss:.2f}%</div>
                <div class="metric-label">Avg Loss</div>
            </div>
            <div class="metric-card">
                <div class="metric-value">{self.results_df['symbol'].nunique()}</div>
                <div class="metric-label">Symbols Traded</div>
            </div>
        </div>
    </div>
    
    <div class="section">
        <div class="nav-tabs">
            <button class="nav-tab active" onclick="showTab('overview')">Overview</button>
"""
        
        # Add symbol tabs
        for symbol in self.results_df['symbol'].unique():
            html_content += f'            <button class="nav-tab" onclick="showTab(\'{symbol}\')">{symbol}</button>\n'
        
        html_content += """            <button class="nav-tab" onclick="showTab('trades')">Best/Worst Trades</button>
            <button class="nav-tab" onclick="showTab('masterclass')">🎓 Masterclass</button>
        </div>
        
        <div id="overview" class="tab-content active">
            <div class="section-title">Overview Dashboard</div>
"""
        
        html_content += f"            {overview_fig.to_html(full_html=False, include_plotlyjs=False)}\n"
        html_content += "        </div>\n"
        
        # Add masterclass content
        html_content += """
        <div id="masterclass" class="tab-content">
            <div class="section-title">🎓 The Lifecycle of a Trade (Masterclass)</div>
            <div class="section" style="line-height: 1.6; color: #333;">
                <h3>1. The Setup (Entry Logic)</h3>
                <p><strong>Camino 1: Blue Sky Breakout</strong><br>
                Buying strength. We enter when price breaks the "Base High" + 0.05c.<br>
                <em>Stop Loss:</em> Automatically set to the higher of [Structure Low] or [Entry - 1 ADR].</p>
                
                <p><strong>Camino 2: VWAP Reclaim (The "Zoom In" Chart)</strong><br>
                Buying weakness that recovers. We enter when a gap-down stock crosses back ABOVE its Intraday VWAP.<br>
                <em>Stop Loss:</em> Strictly set to the Session Low.</p>
                
                <hr>
                
                <h3>2. The Execution Engine (Risk Management)</h3>
                <p>Once inside, the <strong>"State Machine"</strong> manages the trade automatically:</p>
                <ul>
                    <li><strong>Phase A (Protection):</strong> Hard Stop. If price hits the stop, we exit immediately (-1R).</li>
                    <li><strong>Phase B (TP1 - Risk Off):</strong> At <strong>1.5R</strong> profit, we sell 40% and move Stop to <strong>Breakeven</strong>.</li>
                    <li><strong>Phase C (Momentum):</strong> After 4 days, we sell another 30% to capture short-term burst.</li>
                    <li><strong>Phase D (Runner):</strong> The last 30% trails with the EMA 8. We exit when EMA 8 crosses below EMA 21.</li>
                </ul>
                
                <div style="background: #e3f2fd; padding: 15px; border-left: 5px solid #2196f3; margin-top: 20px;">
                    <strong>💡 Pro Tip:</strong> Check the "Zoom" charts for VWAP Reclaim trades to see the specific 5-minute candle where institutions stepped in.
                </div>
            </div>
        </div>
"""
        
        # Add symbol tabs content
        for symbol, fig in symbol_figs.items():
            html_content += f"""
        <div id="{symbol}" class="tab-content">
            <div class="section-title">{symbol} - Detailed Analysis</div>
            {fig.to_html(full_html=False, include_plotlyjs=False)}
        </div>
"""
        
        # Add best/worst trades
        html_content += """
        <div id="trades" class="tab-content">
            <div class="section-title">Best & Worst Trades</div>
"""
        
        for fig in trade_figs:
            html_content += f"            {fig.to_html(full_html=False, include_plotlyjs=False)}\n"
        
        html_content += """
        </div>
    </div>
    
    <script>
        function showTab(tabName) {
            // Remove active from all tabs
            var tabs = document.getElementsByClassName('tab-content');
            for (var i = 0; i < tabs.length; i++) {
                tabs[i].classList.remove('active');
            }
            
            var buttons = document.getElementsByClassName('nav-tab');
            for (var i = 0; i < buttons.length; i++) {
                buttons[i].classList.remove('active');
            }
            
            // Show selected tab
            document.getElementById(tabName).classList.add('active');
            
            // Highlight active button
            event.target.classList.add('active');
        }
    </script>
</body>
</html>
"""
        
        # Save HTML
        output_path = Path(output_file)
        output_path.write_text(html_content)
        
        print(f"\n✅ Dashboard saved: {output_path}")
        print(f"   File size: {output_path.stat().st_size / 1024:.1f} KB")
        
        return str(output_path)


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='Generate Interactive Dashboard')
    parser.add_argument('results_csv', help='Path to backtest results CSV')
    parser.add_argument('--output', default='outputs/backtests/backtest_dashboard.html', help='Output HTML file')
    parser.add_argument('--no-browser', action='store_true', help='Don\'t open browser automatically')
    
    args = parser.parse_args()
    
    if not Path(args.results_csv).exists():
        print(f"❌ File not found: {args.results_csv}")
        sys.exit(1)
    
    dashboard = InteractiveDashboard(args.results_csv)
    output_file = dashboard.generate_html_report(args.output)
    
    if not args.no_browser:
        print("\n🌐 Opening dashboard in browser...")
        webbrowser.open('file://' + str(Path(output_file).absolute()))
    
    print("\n✅ Dashboard ready!")
    print(f"   Open: {output_file}")


if __name__ == "__main__":
    main()
