import pandas as pd
import sys
from pathlib import Path
import sqlite3
import argparse
from datetime import datetime

# Configurar paths
project_root = Path(__file__).resolve().parent
sys.path.insert(0, str(project_root))

from src.backtest.vectorbt_engine_advanced import AdvancedVectorBTEngine

def analyze_results(trades_df, params, year):
    """Analiza los resultados del backtest en detalle"""
    
    if trades_df.empty:
        print("\n❌ No hay trades para analizar")
        return
    
    print("\n" + "="*80)
    print("📊 ANÁLISIS DETALLADO DE TRADES")
    print("="*80)
    
    # 1. Resumen general
    print(f"\n📋 RESUMEN GENERAL:")
    print(f"   Total Trades: {len(trades_df)}")
    print(f"   Win Rate: {(len(trades_df[trades_df['pnl'] > 0]) / len(trades_df) * 100):.1f}%")
    print(f"   Total PnL: ${trades_df['pnl'].sum():,.2f}")
    
    # 2. Análisis por fase (exit_phase)
    print(f"\n🎯 ANÁLISIS POR FASE:")
    phase_analysis = trades_df.groupby('exit_phase').agg({
        'pnl': ['sum', 'count', 'mean'],
        'shares': 'mean'
    }).round(2)
    
    for phase in phase_analysis.index:
        pnl_sum = phase_analysis.loc[phase, ('pnl', 'sum')]
        count = int(phase_analysis.loc[phase, ('pnl', 'count')])
        pnl_mean = phase_analysis.loc[phase, ('pnl', 'mean')]
        
        print(f"\n   {phase}:")
        print(f"      Trades: {count}")
        print(f"      Total PnL: ${pnl_sum:,.2f}")
        print(f"      Avg PnL: ${pnl_mean:,.2f}")
    
    # 3. Análisis por outcome_category
    print(f"\n🏆 ANÁLISIS POR OUTCOME:")
    outcome_stats = trades_df.groupby('outcome_category').agg({
        'pnl': ['sum', 'count'],
        'r_multiple': 'mean'
    }).round(2)
    
    print(f"\n   {'Category':<15} {'Trades':<8} {'Total PnL':<12} {'Avg R':<8}")
    for outcome in ['BIG_WIN', 'WIN', 'SMALL_LOSS', 'BIG_LOSS']:
        if outcome in outcome_stats.index:
            count = int(outcome_stats.loc[outcome, ('pnl', 'count')])
            pnl_sum = outcome_stats.loc[outcome, ('pnl', 'sum')]
            r_mult = outcome_stats.loc[outcome, ('r_multiple', 'mean')]
            print(f"   {outcome:<15} {count:<8} ${pnl_sum:>10,.2f}  {r_mult:>6.2f}x")
    
    # 4. Análisis de Runner
    runner_trades = trades_df[trades_df['exit_phase'].str.contains('PHASE3|RUNNER', na=False)]
    if not runner_trades.empty:
        print(f"\n🚀 RUNNER ANALYSIS:")
        print(f"   Runner Trades: {len(runner_trades)}")
        print(f"   Total Runner PnL: ${runner_trades['pnl'].sum():,.2f}")
        print(f"   Avg Runner PnL: ${runner_trades['pnl'].mean():,.2f}")
        print(f"   Avg R-multiple: {runner_trades['r_multiple'].mean():.2f}x")
    
    # 5. Top trades (ganadores y perdedores)
    print(f"\n🏅 TOP 5 GANADORES:")
    top_winners = trades_df[trades_df['pnl'] > 0].nlargest(5, 'pnl')
    for _, trade in top_winners.iterrows():
        print(f"   {trade['ticker']:<6} ${trade['pnl']:>8.2f}  ({trade['r_multiple']:.2f}R)  {trade['exit_phase']}")
    
    print(f"\n🔻 TOP 5 PERDEDORES:")
    top_losers = trades_df[trades_df['pnl'] < 0].nsmallest(5, 'pnl')
    for _, trade in top_losers.iterrows():
        print(f"   {trade['ticker']:<6} ${trade['pnl']:>8.2f}  ({trade['r_multiple']:.2f}R)  {trade['exit_phase']}")
    
    # 6. Análisis por contexto (ADR, RVOL)
    print(f"\n📊 ANÁLISIS POR CONTEXTO:")
    
    # Por ADR
    trades_df['adr_bucket'] = pd.cut(trades_df['context_adr'], 
                                    bins=[0, 2.5, 5.0, 10.0, float('inf')],
                                    labels=['<2.5%', '2.5-5%', '5-10%', '>10%'])
    
    adr_analysis = trades_df.groupby('adr_bucket').agg({
        'pnl': ['sum', 'count', 'mean']
    }).round(2)
    
    print(f"\n   Por ADR:")
    print(f"   {'Bucket':<10} {'Trades':<8} {'Avg PnL':<10}")
    for bucket in adr_analysis.index:
        if not pd.isna(bucket):
            count = int(adr_analysis.loc[bucket, ('pnl', 'count')])
            pnl_mean = adr_analysis.loc[bucket, ('pnl', 'mean')]
            print(f"   {bucket:<10} {count:<8} ${pnl_mean:>8.2f}")
    
    # Por RVOL
    trades_df['rvol_bucket'] = pd.cut(trades_df['context_rvol'],
                                     bins=[0, 1.5, 3.0, 4.0, float('inf')],
                                     labels=['<1.5x', '1.5-3x', '3-4x', '>4x'])
    
    rvol_analysis = trades_df.groupby('rvol_bucket').agg({
        'pnl': ['sum', 'count', 'mean']
    }).round(2)
    
    print(f"\n   Por RVOL:")
    print(f"   {'Bucket':<10} {'Trades':<8} {'Avg PnL':<10}")
    for bucket in rvol_analysis.index:
        if not pd.isna(bucket):
            count = int(rvol_analysis.loc[bucket, ('pnl', 'count')])
            pnl_mean = rvol_analysis.loc[bucket, ('pnl', 'mean')]
            print(f"   {bucket:<10} {count:<8} ${pnl_mean:>8.2f}")
    
    # 7. Análisis por tiempo de holding
    print(f"\n⏱️  ANÁLISIS POR HOLDING TIME:")
    hold_time_stats = trades_df.groupby('hold_time_category').agg({
        'pnl': ['sum', 'count', 'mean'],
        'r_multiple': 'mean'
    }).round(2)
    
    print(f"\n   {'Category':<12} {'Trades':<8} {'Avg PnL':<10} {'Avg R':<8}")
    for category in ['SCALP', 'SWING', 'POSITION', 'LONG']:
        if category in hold_time_stats.index:
            count = int(hold_time_stats.loc[category, ('pnl', 'count')])
            pnl_mean = hold_time_stats.loc[category, ('pnl', 'mean')]
            r_mult = hold_time_stats.loc[category, ('r_multiple', 'mean')]
            print(f"   {category:<12} {count:<8} ${pnl_mean:>8.2f}  {r_mult:>6.2f}x")
    
    # 8. Detalle de trades completos
    print(f"\n📋 DETALLE DE TODAS LAS TRADES:")
    print(f"\n   {'Ticker':<8} {'Entry':<12} {'Exit':<12} {'PnL':<10} {'R':<6} {'Phase':<20}")
    print(f"   {'-'*70}")
    for _, trade in trades_df.iterrows():
        entry_date = pd.to_datetime(trade['entry_date']).strftime('%Y-%m-%d')
        exit_date = pd.to_datetime(trade['exit_date']).strftime('%Y-%m-%d')
        print(f"   {trade['ticker']:<8} {entry_date:<12} {exit_date:<12} ${trade['pnl']:>7.2f}  {trade['r_multiple']:>4.2f}x {trade['exit_phase'][:20]}")


def main():
    parser = argparse.ArgumentParser(description='Análisis detallado de backtest')
    parser.add_argument('--year', type=int, default=2023, help='Año a analizar')
    parser.add_argument('--scenario', type=str, default='ibd',
                        choices=['professional', 'balanced', 'loose', 'ultra-loose', 'ibd'],
                        help='Escenario a analizar')
    args = parser.parse_args()
    
    start_date = f"{args.year}-01-01"
    end_date = f"{args.year}-12-31"
    
    # Parámetros según escenario
    base_params = {
        'initial_capital': 100000,
        'risk_dollars': 150,
        'min_rvol': 1.5,
        'min_adr': 2.5,
        'min_dollar_volume': 2_000_000,
        'max_dist_sma20': 2.5,
        'use_adaptive_filtering': False,
        'use_market_regime_filter': True,
        'min_consolidation_days': 10,
        'offline_mode': True,
        'require_positive_rs': False,
    }
    
    if args.scenario == 'ibd':
        base_params.update({
            'use_rs_percentile': True,
            'min_rs_percentile': 80.0,
            'rs_lookback_days': 60,
            'use_sma50_atr_filter': True,
            'max_sma50_atr_extension': 2.0,
        })
    
    # Obtener universo completo
    conn = sqlite3.connect('data/ticker_cache.db')
    cursor = conn.execute("SELECT DISTINCT ticker FROM ohlcv_cache")
    universe = [row[0] for row in cursor.fetchall()]
    conn.close()
    
    print(f"\n{'='*80}")
    print(f"🧪 ANALIZANDO ESCENARIO: {args.scenario.upper()} ({args.year})")
    print(f"{'='*80}")
    
    engine = AdvancedVectorBTEngine(
        universe=universe,
        start_date=start_date,
        end_date=end_date,
        **base_params
    )
    
    results = engine.run_backtest()
    trades_df = results['trades']
    
    analyze_results(trades_df, base_params, args.year)


if __name__ == "__main__":
    main()
