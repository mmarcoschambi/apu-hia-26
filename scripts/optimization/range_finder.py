#!/usr/bin/env python3
"""
Range Finder - Encuentra rangos óptimos
========================================

Analiza qué rangos de cada parámetro producen mejores resultados.

Uso: python3 range_finder.py [--file path/to/trade_log.csv]
"""

import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime
import sys
import argparse

def find_latest_trade_log():
    """Busca automáticamente el trade_log más reciente."""
    search_paths = [
        Path('outputs/backtests/trade_log.csv'),
        Path('trade_log.csv'),
    ]
    
    backtest_dir = Path('outputs/backtests')
    if backtest_dir.exists():
        timestamped = list(backtest_dir.glob('*trade_log*.csv'))
        if timestamped:
            latest = max(timestamped, key=lambda p: p.stat().st_mtime)
            return latest
    
    for path in search_paths:
        if path.exists():
            return path
    
    return None

def load_and_group_trades(filepath=None):
    """Carga y agrupa trades."""
    if filepath:
        path = Path(filepath)
    else:
        path = find_latest_trade_log()
    
    if path is None or not path.exists():
        print("❌ No se encontró trade_log.csv")
        sys.exit(1)
    
    print(f"📂 Cargando: {path}")
    df = pd.read_csv(path)
    
    # Group by trade if needed
    if 'exit_phase' in df.columns:
        grouped = df.groupby(['ticker', 'entry_date']).agg({
            'pnl': 'sum',
            'dist_sma20_pct': 'first',
            'consolidation_days': 'first',
            'context_rvol': 'first',
            'context_adr': 'first',
            'sector_strength': 'first',
        }).reset_index()  # Keep ticker column
        
        grouped['is_winner'] = grouped['pnl'] > 0
        grouped['r_multiple'] = grouped['pnl'] / 100
        
        print(f"   ✅ Agrupados en {len(grouped)} trades completos\n")
        return grouped
    
    return df

def analyze_ranges(df):
    """Analiza rangos óptimos para cada parámetro."""
    
    print("="*90)
    print("🔍 RANGE ANALYSIS - Finding Optimal Parameter Ranges")
    print("="*90)
    print(f"Total Trades: {len(df)}\n")
    
    # Define bucket ranges
    param_configs = {
        'dist_sma20_pct': {
            'bins': [0, 3, 5, 7, 10, 100],
            'labels': ['0-3%', '3-5%', '5-7%', '7-10%', '>10%']
        },
        'context_rvol': {
            'bins': [0, 1.5, 2.0, 2.5, 3.0, 10000],
            'labels': ['<1.5x', '1.5-2x', '2-2.5x', '2.5-3x', '>3x']
        },
        'context_adr': {
            'bins': [0, 2, 3, 4, 5, 100],
            'labels': ['<2%', '2-3%', '3-4%', '4-5%', '>5%']
        },
        'consolidation_days': {
            'bins': [0, 10, 15, 20, 25, 1000],
            'labels': ['<10d', '10-15d', '15-20d', '20-25d', '>25d']
        },
    }
    
    results = []
    
    for param, config in param_configs.items():
        if param not in df.columns:
            continue
        
        print(f"\n{'='*90}")
        print(f"📊 Parameter: {param}")
        print(f"{'='*90}")
        
        # Create buckets
        df[f'{param}_bucket'] = pd.cut(df[param], bins=config['bins'], labels=config['labels'])
        
        # Calculate stats per bucket
        stats = df.groupby(f'{param}_bucket', observed=False).agg({
            'ticker': 'count',
            'is_winner': lambda x: (x.sum() / len(x) * 100) if len(x) > 0 else 0,
            'r_multiple': 'mean',
            'pnl': 'sum',
        })
        
        stats.columns = ['Trades', 'Win Rate %', 'Avg R', 'Total PnL']
        
        # Find best bucket
        if len(stats) > 0:
            best_idx = stats['Avg R'].idxmax()
            
            print(f"\n{stats.to_string()}")
            print(f"\n🏆 BEST RANGE: {best_idx} (Avg R={stats.loc[best_idx, 'Avg R']:.2f}R)")
            
            # Store results
            for bucket_name, row in stats.iterrows():
                results.append({
                    'parameter': param,
                    'range': bucket_name,
                    'trades': row['Trades'],
                    'win_rate': row['Win Rate %'],
                    'avg_r': row['Avg R'],
                    'pnl': row['Total PnL']
                })
    
    # Save results
    output_dir = Path('outputs/optimization')
    output_dir.mkdir(parents=True, exist_ok=True)
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    output_file = output_dir / f'ranges_{timestamp}.csv'
    
    results_df = pd.DataFrame(results)
    results_df.to_csv(output_file, index=False)
    
    print(f"\n\n💾 Resultados guardados en: {output_file}")
    
    # Summary recommendations
    print(f"\n{'='*90}")
    print("💡 RECOMMENDED PARAMETER RANGES:")
    print(f"{'='*90}")
    
    for param in param_configs.keys():
        param_results = results_df[results_df['parameter'] == param]
        if not param_results.empty:
            # Find best range with sufficient trades
            sufficient = param_results[param_results['trades'] >= 20]
            if not sufficient.empty:
                best = sufficient.loc[sufficient['avg_r'].idxmax()]
                print(f"{param:25s}: {best['range']} (R={best['avg_r']:+.2f}, WR={best['win_rate']:.1f}%)")
    
    print("="*90)

def main():
    parser = argparse.ArgumentParser(description='Find optimal parameter ranges')
    parser.add_argument('--file', type=str, help='Path to trade_log.csv')
    args = parser.parse_args()
    
    # Load trades
    df = load_and_group_trades(args.file)
    
    # Analyze ranges
    analyze_ranges(df)
    
    print("\n✅ Análisis completo!")

if __name__ == '__main__':
    main()
