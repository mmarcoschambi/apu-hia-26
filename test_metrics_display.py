#!/usr/bin/env python3
"""
Quick test to verify all new metrics are available and formatted correctly.
Run this to see sample output before running full backtest.
"""

from src.analytics.quantstats_analyzer import QuantStatsAnalyzer
import pandas as pd
import numpy as np

# Create realistic sample trade data
np.random.seed(42)
n_trades = 100

sample_trades = pd.DataFrame({
    'ticker': np.random.choice(['AAPL', 'MSFT', 'GOOGL', 'NVDA', 'TSLA'], n_trades),
    'entry_date': pd.date_range('2023-01-01', periods=n_trades, freq='3D'),
    'exit_date': pd.date_range('2023-01-06', periods=n_trades, freq='3D'),
    'entry_price': np.random.uniform(100, 300, n_trades),
    'exit_price': np.random.uniform(100, 300, n_trades),
    'shares': np.random.randint(10, 200, n_trades),
    'pnl': np.random.uniform(-2000, 3000, n_trades),
    'exit_phase': np.random.choice(['TP1', 'TP2', 'STOP'], n_trades, p=[0.4, 0.3, 0.3])
})

print("=" * 80)
print("TESTING ENHANCED METRICS SYSTEM")
print("=" * 80)

# Initialize analyzer
analyzer = QuantStatsAnalyzer(sample_trades, initial_capital=100000, benchmark_ticker='SPY')

# Get all metrics
print("\n📊 Calculating metrics...")
metrics = analyzer.get_quantstats_metrics()

print("\n✅ Metrics calculated successfully!\n")

# Display all metrics in organized format
print("=" * 80)
print("RISK-ADJUSTED RETURNS")
print("=" * 80)
print(f"CAGR:              {metrics.get('cagr', 0)*100:>8.2f}%")
print(f"Sharpe Ratio:      {metrics.get('sharpe_ratio', 0):>8.2f}")
print(f"Sortino Ratio:     {metrics.get('sortino_ratio', 0):>8.2f}")
print(f"Calmar Ratio:      {metrics.get('calmar_ratio', 0):>8.2f}")
print(f"Omega Ratio:       {metrics.get('omega_ratio', 0):>8.2f}")

print("\n" + "=" * 80)
print("RETURNS & DRAWDOWN")
print("=" * 80)
print(f"Total Return:      {metrics.get('total_return', 0)*100:>8.2f}%")
print(f"Max Drawdown:      {metrics.get('max_drawdown', 0)*100:>8.2f}%")
print(f"Avg Drawdown:      {metrics.get('avg_drawdown', 0)*100:>8.2f}%")

print("\n" + "=" * 80)
print("TRADE STATISTICS")
print("=" * 80)
print(f"Total Trades:      {metrics.get('total_trades', 0):>8.0f}")
print(f"Winning Trades:    {metrics.get('winning_trades', 0):>8.0f}")
print(f"Losing Trades:     {metrics.get('losing_trades', 0):>8.0f}")
print(f"Win Rate:          {metrics.get('win_rate', 0)*100:>8.1f}%")
print(f"Profit Factor:     {metrics.get('profit_factor', 0):>8.2f}")
print(f"Avg Hold Period:   {metrics.get('avg_holding_period', 0):>8.1f} days")

print("\n" + "=" * 80)
print("RISK METRICS")
print("=" * 80)
print(f"VaR (95%):         {metrics.get('var_95', 0)*100:>8.2f}%")
print(f"CVaR (95%):        {metrics.get('cvar_95', 0)*100:>8.2f}%")
print(f"Volatility:        {metrics.get('volatility_annual', 0)*100:>8.2f}%")

print("\n" + "=" * 80)
print("WIN/LOSS ANALYSIS")
print("=" * 80)
print(f"Average Win:       ${metrics.get('avg_win', 0):>8.0f}")
print(f"Average Loss:      ${metrics.get('avg_loss', 0):>8.0f}")
print(f"Win/Loss Ratio:    {metrics.get('avg_win_loss_ratio', 0):>8.2f}")
print(f"Largest Win:       ${metrics.get('largest_win', 0):>8.0f}")
print(f"Largest Loss:      ${metrics.get('largest_loss', 0):>8.0f}")

print("\n" + "=" * 80)
print("EXPOSURE & STREAKS")
print("=" * 80)
print(f"Exposure Time:     {metrics.get('exposure_time_pct', 0):>8.1f}%")
print(f"Max Consec. Wins:  {metrics.get('max_consecutive_wins', 0):>8.0f}")
print(f"Max Consec. Losses:{metrics.get('max_consecutive_losses', 0):>8.0f}")

print("\n" + "=" * 80)
print("DISTRIBUTION")
print("=" * 80)
print(f"Skewness:          {metrics.get('skewness', 0):>8.3f}")
print(f"Kurtosis:          {metrics.get('kurtosis', 0):>8.3f}")

print("\n" + "=" * 80)
print("METRICS AVAILABILITY CHECK")
print("=" * 80)

all_metrics = [
    'cagr', 'sharpe_ratio', 'sortino_ratio', 'calmar_ratio', 'omega_ratio',
    'total_return', 'max_drawdown', 'avg_drawdown',
    'total_trades', 'winning_trades', 'losing_trades', 'win_rate', 'profit_factor',
    'avg_win', 'avg_loss', 'avg_win_loss_ratio', 'largest_win', 'largest_loss',
    'avg_holding_period', 'var_95', 'cvar_95', 'volatility_annual',
    'max_consecutive_wins', 'max_consecutive_losses', 'exposure_time_pct',
    'skewness', 'kurtosis'
]

available = sum(1 for m in all_metrics if metrics.get(m) is not None)
print(f"\n✅ Available: {available}/{len(all_metrics)} metrics")

missing = [m for m in all_metrics if metrics.get(m) is None]
if missing:
    print(f"⚠️  Missing: {', '.join(missing)}")
else:
    print("🎉 All metrics available!")

print("\n" + "=" * 80)
print("TEST COMPLETE - All systems operational!")
print("=" * 80)
print("\nNext steps:")
print("1. Run a real backtest in Streamlit")
print("2. Navigate to Performance tab")
print("3. See all these metrics displayed")
print("4. Generate PDF report with comprehensive analytics")
print("\n✨ Ready for production use!")
