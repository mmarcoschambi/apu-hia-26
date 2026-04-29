#!/usr/bin/env python3
"""
Example: Integrate QuantStats into Your Backtest Workflow
==========================================================
Shows how to run a backtest and immediately analyze with QuantStats.
"""

import sys
from pathlib import Path

project_root = Path(__file__).resolve().parent
sys.path.insert(0, str(project_root))

from src.analytics.quantstats_analyzer import QuantStatsAnalyzer
import pandas as pd


def example_post_backtest_analysis():
    """
    Example workflow after running backtest_vectorbt_advanced.py
    """
    
    print("=" * 80)
    print("EXAMPLE: Post-Backtest QuantStats Analysis")
    print("=" * 80)
    
    # Step 1: Find latest trade log
    backtest_dir = Path('outputs/backtests')
    trade_logs = list(backtest_dir.glob('trade_log_*.csv'))
    
    if not trade_logs:
        print("\n❌ No trade logs found. Run a backtest first:")
        print("   python3 backtest_vectorbt_advanced.py")
        return
    
    latest_log = max(trade_logs, key=lambda p: p.stat().st_mtime)
    print(f"\n📂 Using: {latest_log}")
    
    # Step 2: Load trade log
    trade_log = pd.read_csv(latest_log)
    print(f"📊 Loaded {len(trade_log)} trade events (includes partial exits)")
    
    # Step 3: Create analyzer (auto-groups trades)
    print(f"\n🔄 Grouping partial exits into complete trades...")
    analyzer = QuantStatsAnalyzer(
        trade_log=trade_log,
        initial_capital=100000,
        benchmark_ticker='SPY'
    )
    
    print(f"✅ Grouped into {len(analyzer.complete_trades)} complete trades")
    
    # Step 4: Get trade metrics
    print(f"\n" + "=" * 80)
    print("TRADE METRICS (Complete Trades)")
    print("=" * 80)
    
    metrics = analyzer.get_trade_metrics()
    
    if metrics:
        print(f"\n📊 Basic Stats:")
        print(f"   Total Trades:    {metrics['total_trades']}")
        print(f"   Winners:         {metrics['winners']} ({metrics['win_rate_pct']:.1f}%)")
        print(f"   Losers:          {metrics['losers']}")
        print(f"   Stopped Out:     {metrics['stopped_out']}")
        
        print(f"\n💰 P&L Analysis:")
        print(f"   Total P&L:       ${metrics['total_pnl']:,.2f}")
        print(f"   Avg Win:         ${metrics['avg_win']:,.2f}")
        print(f"   Avg Loss:        ${metrics['avg_loss']:,.2f}")
        print(f"   Profit Factor:   {metrics['profit_factor']:.2f}")
        
        print(f"\n📈 R-Multiple (Expectancy):")
        print(f"   Average R:       {metrics['avg_r_multiple']:+.2f}R")
        print(f"   Median R:        {metrics['median_r_multiple']:+.2f}R")
        print(f"   Best R:          {metrics['best_r_multiple']:+.2f}R")
        print(f"   Worst R:         {metrics['worst_r_multiple']:+.2f}R")
        
        print(f"\n🎯 Exit Analysis:")
        print(f"   Hit TP1:         {metrics['hit_tp1']} ({metrics['hit_tp1']/metrics['total_trades']*100:.0f}%)")
        print(f"   Hit TP2:         {metrics['hit_tp2']} ({metrics['hit_tp2']/metrics['total_trades']*100:.0f}%)")
        print(f"   Had Runner:      {metrics['had_runner']} ({metrics['had_runner']/metrics['total_trades']*100:.0f}%)")
        
        print(f"\n⏱️  Hold Time:")
        print(f"   Avg Days:        {metrics['avg_hold_days']:.1f} days")
    
    # Step 5: Get QuantStats metrics
    print(f"\n" + "=" * 80)
    print("QUANTSTATS METRICS (Time-Series)")
    print("=" * 80)
    
    qs_metrics = analyzer.get_quantstats_metrics()
    
    if qs_metrics:
        print(f"\n🎯 Risk-Adjusted Returns:")
        print(f"   Sharpe Ratio:    {qs_metrics.get('sharpe_ratio', 0):.2f}")
        print(f"   Sortino Ratio:   {qs_metrics.get('sortino_ratio', 0):.2f}")
        print(f"   Calmar Ratio:    {qs_metrics.get('calmar_ratio', 0):.2f}")
        
        print(f"\n📊 Returns:")
        print(f"   Total Return:    {qs_metrics.get('total_return', 0)*100:+.2f}%")
        print(f"   CAGR:            {qs_metrics.get('cagr', 0)*100:+.2f}%")
        
        print(f"\n⚠️  Risk Metrics:")
        print(f"   Max Drawdown:    {qs_metrics.get('max_drawdown', 0)*100:.2f}%")
        print(f"   Volatility:      {qs_metrics.get('volatility_annual', 0)*100:.2f}%")
        print(f"   VaR (95%):       {qs_metrics.get('var_95', 0)*100:.2f}%")
    
    # Step 6: Export results
    print(f"\n" + "=" * 80)
    print("EXPORTING RESULTS")
    print("=" * 80)
    
    output_dir = 'outputs/quantstats'
    
    # Export complete trades
    analyzer.export_complete_trades(f'{output_dir}/complete_trades.csv')
    print(f"✅ Complete trades exported to: {output_dir}/complete_trades.csv")
    
    # Generate HTML report
    try:
        report_path = analyzer.generate_report(
            output_dir=output_dir,
            benchmark_ticker='SPY'
        )
        if report_path:
            print(f"✅ HTML report generated: {report_path}")
            print(f"\n🌐 Open in browser to see:")
            print(f"   - Equity curve with drawdowns")
            print(f"   - Monthly return heatmap")
            print(f"   - Return distribution")
            print(f"   - Rolling Sharpe/Sortino")
            print(f"   - Benchmark comparison")
    except Exception as e:
        print(f"⚠️  HTML report skipped: {e}")
    
    # Step 7: Advanced analysis examples
    print(f"\n" + "=" * 80)
    print("ADVANCED ANALYSIS EXAMPLES")
    print("=" * 80)
    
    complete_trades = analyzer.complete_trades
    
    # RVOL classification performance
    if 'rvol_classification' in complete_trades.columns:
        print(f"\n📊 Performance by RVOL Classification:")
        for rvol_type in complete_trades['rvol_classification'].unique():
            subset = complete_trades[complete_trades['rvol_classification'] == rvol_type]
            if len(subset) > 0:
                avg_r = subset['r_multiple'].mean()
                win_rate = (subset['is_winner'].sum() / len(subset)) * 100
                print(f"   {rvol_type:15}: {len(subset):3} trades | "
                      f"Win Rate: {win_rate:.1f}% | Avg R: {avg_r:+.2f}R")
    
    # VCP pattern analysis
    if 'is_vcp_pattern' in complete_trades.columns:
        print(f"\n🎯 VCP Pattern Performance:")
        vcp = complete_trades[complete_trades['is_vcp_pattern'] == True]
        non_vcp = complete_trades[complete_trades['is_vcp_pattern'] == False]
        
        if len(vcp) > 0:
            vcp_wr = (vcp['is_winner'].sum() / len(vcp)) * 100
            vcp_r = vcp['r_multiple'].mean()
            print(f"   VCP Trades:     {len(vcp):3} | Win Rate: {vcp_wr:.1f}% | Avg R: {vcp_r:+.2f}R")
        
        if len(non_vcp) > 0:
            non_vcp_wr = (non_vcp['is_winner'].sum() / len(non_vcp)) * 100
            non_vcp_r = non_vcp['r_multiple'].mean()
            print(f"   Non-VCP Trades: {len(non_vcp):3} | Win Rate: {non_vcp_wr:.1f}% | Avg R: {non_vcp_r:+.2f}R")
    
    # Best and worst trades
    print(f"\n🏆 Top 5 Winners:")
    top_winners = complete_trades.nlargest(5, 'r_multiple')
    for i, trade in top_winners.iterrows():
        print(f"   {trade['ticker']:6} | {trade['entry_date'][:10]} | "
              f"${trade['total_pnl']:+8.2f} | {trade['r_multiple']:+.2f}R | "
              f"{trade['exit_phases']}")
    
    print(f"\n💸 Top 5 Losers:")
    top_losers = complete_trades.nsmallest(5, 'r_multiple')
    for i, trade in top_losers.iterrows():
        print(f"   {trade['ticker']:6} | {trade['entry_date'][:10]} | "
              f"${trade['total_pnl']:+8.2f} | {trade['r_multiple']:+.2f}R | "
              f"{trade['exit_phases']}")
    
    print(f"\n" + "=" * 80)
    print("✅ Analysis Complete!")
    print("=" * 80)
    print(f"\nNext Steps:")
    print(f"1. Review HTML report for detailed visualizations")
    print(f"2. Analyze complete_trades.csv for pattern discovery")
    print(f"3. Focus on improving Avg R (target: >1.0R)")
    print(f"4. Optimize entry/exit based on RVOL, VCP analysis")
    print("=" * 80 + "\n")


if __name__ == "__main__":
    example_post_backtest_analysis()
