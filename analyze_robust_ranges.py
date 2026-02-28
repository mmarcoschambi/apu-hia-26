#!/usr/bin/env python3
"""
ROBUST RANGES ANALYZER
======================

Analiza resultados del Walk Forward para identificar rangos de parámetros
que funcionan consistentemente a través de múltiples ventanas.

Usage:
    python3 analyze_robust_ranges.py
"""

import json
import numpy as np
import pandas as pd
from pathlib import Path
from collections import defaultdict

def load_walk_forward_results():
    """Carga resultados del walk forward."""
    results_file = Path('outputs/walk_forward_results.json')
    
    if not results_file.exists():
        print(f"❌ No results file found: {results_file}")
        print("Run walk forward first: bash run_walk_forward.sh")
        return None
    
    with open(results_file, 'r') as f:
        data = json.load(f)
    
    return data

def analyze_parameter_stability(results):
    """Analiza estabilidad de parámetros a través de ventanas."""
    windows = results['windows']
    
    if len(windows) == 0:
        print("❌ No windows found in results")
        return
    
    # Collect all parameter values and their performance
    param_performance = defaultdict(lambda: defaultdict(list))
    
    for window in windows:
        params = window['params']
        sharpe = window['oos_sharpe']
        
        for param_name, param_value in params.items():
            # Skip non-numeric and feature flags
            if not isinstance(param_value, (int, float)):
                continue
            
            param_performance[param_name][param_value].append(sharpe)
    
    print("\n" + "="*70)
    print("📊 PARAMETER ROBUSTNESS ANALYSIS")
    print("="*70)
    
    robust_ranges = {}
    
    for param_name in sorted(param_performance.keys()):
        values = param_performance[param_name]
        
        # Calculate average Sharpe for each value
        value_sharpes = {}
        for val, sharpes in values.items():
            value_sharpes[val] = {
                'mean_sharpe': np.mean(sharpes),
                'std_sharpe': np.std(sharpes),
                'n_windows': len(sharpes),
                'consistency': np.mean(sharpes) / np.std(sharpes) if np.std(sharpes) > 0 else 0
            }
        
        # Find robust values (high consistency, good Sharpe)
        good_values = [
            val for val, stats in value_sharpes.items()
            if stats['mean_sharpe'] > 0.5 and stats['n_windows'] >= 2
        ]
        
        if good_values:
            robust_range = (min(good_values), max(good_values))
            robust_center = np.median(good_values)
            robust_ranges[param_name] = {
                'range': robust_range,
                'center': robust_center,
                'values_tested': list(value_sharpes.keys())
            }
            
            print(f"\n🎯 {param_name}:")
            print(f"   Robust Range: {robust_range[0]} → {robust_range[1]}")
            print(f"   Recommended: {robust_center}")
            print(f"   Performance by value:")
            for val in sorted(value_sharpes.keys()):
                stats = value_sharpes[val]
                print(f"      {val:>6}: Sharpe {stats['mean_sharpe']:>5.2f} ± {stats['std_sharpe']:.2f} ({stats['n_windows']} windows)")
    
    return robust_ranges

def analyze_feature_stability(results):
    """Analiza qué features funcionan consistentemente."""
    windows = results['windows']
    
    print("\n" + "="*70)
    print("🔧 FEATURE CONSISTENCY ANALYSIS")
    print("="*70)
    
    # In this implementation, features are fixed across windows
    # So we just report what was used
    if windows:
        features = {k: v for k, v in windows[0]['params'].items() 
                   if k.startswith('use_') or k.startswith('require_')}
        
        print("\n✅ Features enabled:")
        for feat, enabled in sorted(features.items()):
            if enabled:
                print(f"   • {feat}")
        
        print("\n❌ Features disabled:")
        for feat, enabled in sorted(features.items()):
            if not enabled:
                print(f"   • {feat}")

def generate_production_config(robust_ranges):
    """Genera configuración de producción basada en rangos robustos."""
    print("\n" + "="*70)
    print("🏭 PRODUCTION CONFIGURATION")
    print("="*70)
    
    production_params = {}
    
    print("\n📋 Recommended Parameters (center of robust range):")
    for param_name, data in sorted(robust_ranges.items()):
        recommended = data['center']
        production_params[param_name] = recommended
        range_str = f"[{data['range'][0]}, {data['range'][1]}]"
        print(f"   {param_name:<25} = {recommended:<8} (range: {range_str})")
    
    # Save to file
    output_file = Path('config/production_params.json')
    
    config = {
        'generated_from': 'walk_forward_analysis',
        'date': pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S'),
        'parameters': production_params,
        'robust_ranges': {k: v['range'] for k, v in robust_ranges.items()}
    }
    
    with open(output_file, 'w') as f:
        json.dump(config, f, indent=2)
    
    print(f"\n💾 Saved to: {output_file}")
    
    return production_params

def main():
    print("="*70)
    print("🔍 ROBUST RANGES ANALYZER")
    print("="*70)
    
    # Load results
    results = load_walk_forward_results()
    if not results:
        return
    
    print(f"\n📊 Analyzing {len(results['windows'])} windows...")
    first_train = results['windows'][0]['train_period'][0] if results['windows'] else 'N/A'
    last_test = results['windows'][-1]['test_period'][1] if results['windows'] else 'N/A'
    print(f"   Period: {first_train} to {last_test}")
    print(f"   Universe: {', '.join(results['universe'])}")
    
    # Analyze parameter stability
    robust_ranges = analyze_parameter_stability(results)
    
    # Analyze feature consistency
    analyze_feature_stability(results)
    
    # Generate production config
    if robust_ranges:
        production_params = generate_production_config(robust_ranges)
    
    # Summary statistics
    print("\n" + "="*70)
    print("📈 AGGREGATE OOS PERFORMANCE")
    print("="*70)
    
    sharpes = [w['oos_sharpe'] for w in results['windows']]
    returns = [w['oos_return'] for w in results['windows']]
    win_rates = [w['oos_win_rate'] for w in results['windows']]
    
    print(f"\nSharpe Ratio:")
    print(f"   Mean:   {np.mean(sharpes):.3f}")
    print(f"   Median: {np.median(sharpes):.3f}")
    print(f"   Std:    {np.std(sharpes):.3f}")
    print(f"   Range:  [{np.min(sharpes):.3f}, {np.max(sharpes):.3f}]")
    
    print(f"\nReturn %:")
    print(f"   Mean:   {np.mean(returns)*100:.2f}%")
    print(f"   Median: {np.median(returns)*100:.2f}%")
    print(f"   Total:  {np.sum(returns)*100:.2f}%")
    
    print(f"\nWin Rate:")
    print(f"   Mean:   {np.mean(win_rates)*100:.1f}%")
    print(f"   Median: {np.median(win_rates)*100:.1f}%")
    
    # Robustness score
    robustness = np.mean(sharpes) / np.std(sharpes) if np.std(sharpes) > 0 else 0
    print(f"\n🎯 ROBUSTNESS SCORE: {robustness:.2f}")
    
    if robustness > 2.0:
        print("   ✅ EXCELLENT: Very stable across windows")
    elif robustness > 1.0:
        print("   ✅ GOOD: Reasonably stable")
    elif robustness > 0.5:
        print("   ⚠️ FAIR: Some variability")
    else:
        print("   ❌ POOR: High variability, may be overfit")
    
    print("\n✅ Analysis complete!")

if __name__ == '__main__':
    main()
