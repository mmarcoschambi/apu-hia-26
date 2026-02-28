#!/usr/bin/env python3
"""
Parameter Optimization Suite
============================
Comprehensive optimization using multiple methods:
1. Grid Search - Test parameter combinations
2. Correlation Analysis - Find relationships  
3. Walk-Forward - Prevent overfitting

Usage:
    python3 optimize_parameters.py --method all
    python3 optimize_parameters.py --method grid
    python3 optimize_parameters.py --method correlations
    python3 optimize_parameters.py --method walkforward
"""

import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime
import itertools
import argparse
import sys

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from src.analytics.quantstats_analyzer import TradeGrouper


def load_complete_trades(filepath=None):
    """Load and group partial trades into complete trades."""
    if filepath is None:
        filepath = 'outputs/backtests/trade_log.csv'
    
    path = Path(filepath)
    if not path.exists():
        print(f"❌ File not found: {path}")
        sys.exit(1)
    
    print(f"📂 Loading: {path}")
    trade_log = pd.read_csv(path)
    print(f"   Raw events: {len(trade_log)}")
    
    # Group into complete trades
    complete_trades = TradeGrouper.group_partial_trades(trade_log)
    print(f"   ✅ Complete trades: {len(complete_trades)}\n")
    
    return complete_trades


def correlation_analysis(trades):
    """Analyze correlations between parameters and profitability."""
    print("\n" + "="*80)
    print("📊 CORRELATION ANALYSIS")
    print("="*80 + "\n")
    
    # Select relevant columns
    params = [
        'context_adr',
        'context_rvol',
        'dist_sma20_pct',
        'consolidation_days',
        'sector_strength',
        'adjusted_risk_dollars',
        'risk_reduction_factor',
    ]
    
    target = 'r_multiple'
    
    correlations = {}
    for param in params:
        if param in trades.columns:
            corr = trades[param].corr(trades[target])
            correlations[param] = corr
    
    # Sort by absolute correlation
    sorted_corr = dict(sorted(correlations.items(), 
                             key=lambda x: abs(x[1]), 
                             reverse=True))
    
    print("Parameter Correlations with R-Multiple:")
    print("-" * 80)
    for param, corr in sorted_corr.items():
        direction = "📈 POSITIVE" if corr > 0 else "📉 NEGATIVE"
        strength = "STRONG" if abs(corr) > 0.1 else ("MODERATE" if abs(corr) > 0.05 else "WEAK")
        print(f"{param:30s}: {corr:+.4f}  {direction} ({strength})")
    
    # Winners vs Losers comparison
    print("\n" + "-" * 80)
    print("Winners vs Losers - Average Values:")
    print("-" * 80)
    
    winners = trades[trades['is_winner'] == True]
    losers = trades[trades['is_winner'] == False]
    
    for param in params:
        if param in trades.columns:
            win_avg = winners[param].mean()
            lose_avg = losers[param].mean()
            diff_pct = ((win_avg - lose_avg) / lose_avg * 100) if lose_avg != 0 else 0
            
            print(f"{param:30s}: Winners={win_avg:8.2f}, Losers={lose_avg:8.2f}, "
                  f"Diff={diff_pct:+6.1f}%")
    
    return sorted_corr


def grid_search(trades, output_dir='outputs/optimization'):
    """Test all parameter combinations."""
    print("\n" + "="*80)
    print("🔍 GRID SEARCH OPTIMIZATION")
    print("="*80 + "\n")
    
    # Define parameter ranges
    param_grid = {
        'max_dist_sma20': [5.0, 7.0, 10.0, 12.0, 15.0],
        'consolidation_min': [10, 15, 20, 25],
        'rvol_min': [1.2, 1.5, 2.0],
    }
    
    results = []
    
    # Generate all combinations
    keys = list(param_grid.keys())
    values = list(param_grid.values())
    combinations = list(itertools.product(*values))
    
    print(f"Testing {len(combinations)} parameter combinations...")
    
    for i, combo in enumerate(combinations):
        if (i + 1) % 10 == 0:
            print(f"  Progress: {i+1}/{len(combinations)}...")
        
        params = dict(zip(keys, combo))
        
        # Filter trades based on parameters
        filtered = trades.copy()
        
        if 'dist_sma20_pct' in filtered.columns:
            filtered = filtered[filtered['dist_sma20_pct'] <= params['max_dist_sma20']]
        if 'consolidation_days' in filtered.columns:
            filtered = filtered[filtered['consolidation_days'] >= params['consolidation_min']]
        if 'context_rvol' in filtered.columns:
            filtered = filtered[filtered['context_rvol'] >= params['rvol_min']]
        
        # Calculate metrics
        if len(filtered) > 20:  # Need minimum trades
            win_rate = (filtered['is_winner'].sum() / len(filtered)) * 100
            avg_r = filtered['r_multiple'].mean()
            total_r = filtered['r_multiple'].sum()
            
            # Profit factor
            gross_profit = filtered[filtered['is_winner']]['total_pnl'].sum()
            gross_loss = abs(filtered[~filtered['is_winner']]['total_pnl'].sum())
            profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else 0
            
            # Combined score (weighted)
            score = (
                win_rate * 0.2 +           # 20% weight on win rate
                avg_r * 100 * 0.3 +        # 30% weight on avg R
                profit_factor * 20 * 0.3 + # 30% weight on PF
                (total_r / len(filtered)) * 50 * 0.2  # 20% weight on consistency
            )
            
            results.append({
                **params,
                'trades': len(filtered),
                'win_rate': win_rate,
                'avg_r': avg_r,
                'total_r': total_r,
                'profit_factor': profit_factor,
                'score': score
            })
    
    # Convert to DataFrame and sort
    results_df = pd.DataFrame(results)
    results_df = results_df.sort_values('score', ascending=False)
    
    # Save results
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    csv_file = output_path / f'grid_search_{timestamp}.csv'
    results_df.to_csv(csv_file, index=False)
    
    print(f"\n✅ Results saved to {csv_file}")
    print("\n🏆 TOP 10 PARAMETER COMBINATIONS:")
    print("-" * 80)
    print(results_df.head(10).to_string(index=False))
    
    return results_df


def walk_forward(trades, train_years=2, test_years=1, output_dir='outputs/optimization'):
    """Walk-forward optimization to prevent overfitting."""
    print("\n" + "="*80)
    print("🚀 WALK-FORWARD OPTIMIZATION")
    print("="*80 + "\n")
    
    # Ensure dates are datetime
    trades['entry_date'] = pd.to_datetime(trades['entry_date'])
    trades['final_exit_date'] = pd.to_datetime(trades['final_exit_date'])
    
    # Sort by date
    trades = trades.sort_values('entry_date')
    
    min_date = trades['entry_date'].min()
    max_date = trades['final_exit_date'].max()
    total_years = (max_date - min_date).days / 365.25
    
    print(f"Data range: {min_date.date()} to {max_date.date()} ({total_years:.1f} years)")
    print(f"Train period: {train_years} years")
    print(f"Test period: {test_years} years\n")
    
    # Define parameter ranges (smaller than grid search)
    param_ranges = {
        'max_dist_sma20': [5.0, 7.0, 10.0],
        'consolidation_min': [10, 15, 20],
        'rvol_min': [1.5, 2.0],
    }
    
    results = []
    
    # Walk forward through time
    train_period = pd.DateOffset(years=train_years)
    test_period = pd.DateOffset(years=test_years)
    
    current_start = min_date
    fold = 1
    
    while current_start + train_period + test_period <= max_date:
        train_end = current_start + train_period
        test_end = train_end + test_period
        
        print(f"FOLD {fold}:")
        print(f"  Train: {current_start.date()} to {train_end.date()}")
        print(f"  Test:  {train_end.date()} to {test_end.date()}")
        
        # Split data
        train_data = trades[(trades['entry_date'] >= current_start) & 
                           (trades['entry_date'] < train_end)]
        test_data = trades[(trades['entry_date'] >= train_end) & 
                          (trades['entry_date'] < test_end)]
        
        print(f"  Train trades: {len(train_data)}, Test trades: {len(test_data)}")
        
        if len(train_data) < 20 or len(test_data) < 5:
            print("  ⚠️ Insufficient data, skipping fold\n")
            current_start += test_period
            fold += 1
            continue
        
        # Optimize on training data
        best_params = optimize_on_data(train_data, param_ranges)
        print(f"  Best params: {best_params}")
        
        # Test on validation data
        test_metrics = evaluate_params(test_data, best_params)
        print(f"  Test performance: WR={test_metrics['win_rate']:.1f}%, "
              f"Avg R={test_metrics['avg_r']:.2f}R, PF={test_metrics['profit_factor']:.2f}\n")
        
        results.append({
            'fold': fold,
            'train_start': current_start,
            'train_end': train_end,
            'test_end': test_end,
            **best_params,
            **test_metrics
        })
        
        # Move window forward
        current_start += test_period
        fold += 1
    
    results_df = pd.DataFrame(results)
    
    # Save results
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    csv_file = output_path / f'walkforward_{timestamp}.csv'
    results_df.to_csv(csv_file, index=False)
    
    print("="*80)
    print(f"✅ Results saved to {csv_file}")
    print("\n📊 AVERAGE TEST PERFORMANCE:")
    print("-" * 80)
    avg_metrics = {
        'win_rate': results_df['win_rate'].mean(),
        'avg_r': results_df['avg_r'].mean(),
        'profit_factor': results_df['profit_factor'].mean(),
    }
    for metric, value in avg_metrics.items():
        print(f"  {metric:15s}: {value:.2f}")
    
    print("\n🔧 MOST STABLE PARAMETER VALUES:")
    print("-" * 80)
    for param in param_ranges.keys():
        if param in results_df.columns:
            mode_value = results_df[param].mode()[0] if not results_df[param].empty else "N/A"
            print(f"  {param:20s}: {mode_value}")
    
    return results_df


def optimize_on_data(data, param_ranges):
    """Optimize parameters on given data."""
    best_score = -999999
    best_params = {}
    
    # Generate combinations
    keys = list(param_ranges.keys())
    values = list(param_ranges.values())
    combinations = list(itertools.product(*values))
    
    for combo in combinations:
        params = dict(zip(keys, combo))
        
        # Filter data
        filtered = data.copy()
        if 'dist_sma20_pct' in filtered.columns:
            filtered = filtered[filtered['dist_sma20_pct'] <= params['max_dist_sma20']]
        if 'consolidation_days' in filtered.columns:
            filtered = filtered[filtered['consolidation_days'] >= params['consolidation_min']]
        if 'context_rvol' in filtered.columns:
            filtered = filtered[filtered['context_rvol'] >= params['rvol_min']]
        
        if len(filtered) < 10:
            continue
        
        # Calculate score
        win_rate = (filtered['is_winner'].sum() / len(filtered)) * 100
        avg_r = filtered['r_multiple'].mean()
        
        gross_profit = filtered[filtered['is_winner']]['total_pnl'].sum()
        gross_loss = abs(filtered[~filtered['is_winner']]['total_pnl'].sum())
        profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else 0
        
        score = win_rate * 0.3 + avg_r * 100 * 0.4 + profit_factor * 20 * 0.3
        
        if score > best_score:
            best_score = score
            best_params = params.copy()
    
    return best_params


def evaluate_params(data, params):
    """Evaluate parameters on given data."""
    # Filter data
    filtered = data.copy()
    if 'dist_sma20_pct' in filtered.columns:
        filtered = filtered[filtered['dist_sma20_pct'] <= params['max_dist_sma20']]
    if 'consolidation_days' in filtered.columns:
        filtered = filtered[filtered['consolidation_days'] >= params['consolidation_min']]
    if 'context_rvol' in filtered.columns:
        filtered = filtered[filtered['context_rvol'] >= params['rvol_min']]
    
    if len(filtered) < 5:
        return {
            'trades': 0,
            'win_rate': 0,
            'avg_r': 0,
            'total_r': 0,
            'profit_factor': 0,
        }
    
    gross_profit = filtered[filtered['is_winner']]['total_pnl'].sum()
    gross_loss = abs(filtered[~filtered['is_winner']]['total_pnl'].sum())
    profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else 0
    
    return {
        'trades': len(filtered),
        'win_rate': (filtered['is_winner'].sum() / len(filtered)) * 100,
        'avg_r': filtered['r_multiple'].mean(),
        'total_r': filtered['r_multiple'].sum(),
        'profit_factor': profit_factor,
    }


def main():
    parser = argparse.ArgumentParser(description='Optimize backtest parameters')
    parser.add_argument('--method', type=str, default='all',
                       choices=['all', 'correlations', 'grid', 'walkforward'],
                       help='Optimization method to use')
    parser.add_argument('--file', type=str, default=None,
                       help='Path to trade log CSV')
    args = parser.parse_args()
    
    # Load trades
    trades = load_complete_trades(args.file)
    
    if args.method in ['all', 'correlations']:
        correlation_analysis(trades)
    
    if args.method in ['all', 'grid']:
        grid_search(trades)
    
    if args.method in ['all', 'walkforward']:
        walk_forward(trades)
    
    print("\n" + "="*80)
    print("✅ OPTIMIZATION COMPLETE!")
    print("="*80)


if __name__ == '__main__':
    main()
