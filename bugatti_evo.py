#!/usr/bin/env python3
"""
BUGATTI EVO - The Ultimate Optimization Engine
==============================================
Methodology: SPATIAL K-FOLD + TEMPORAL WALK-FORWARD
Author: Marcos & Gemini Agent
Version: EVO 2.1 (Modularized)

Features:
  - Stratified Sampling (High/Mid/Low)
  - Hierarchical Optimization (L1 -> L2)
  - Democratic Voting with Quality Veto
  - Stability Analysis (CV Re-test)
  - Full Logging & CSV Dump

"La robustez no es coincidencia, es estadística."
"""

import argparse
import json
import sys
import gc
from pathlib import Path
from datetime import datetime
import pandas as pd
import numpy as np
import optuna
import logging
from collections import Counter
from typing import List, Dict, Any

# Setup path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from src.backtest.optimization_engine_thor import OptimizationEngineTHOR
from src.data.ticker_cache import TickerCache

# Logging setup
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger("BugattiEvo")

# ============================================================================
# CONFIGURACIN DE PARMETROS (Espacio de Bsqueda)
# ============================================================================

LAYER1_PARAMS = {
    'risk_dollars': [150, 200],
    'max_exposure_pct': [0.20, 0.25, 0.30],
    'min_rvol': [1.0, 1.5, 2.0],
    'min_adr': [1.0, 1.5, 2.0],
    'signal_type': ['any'],
    'tp1_r': [1.5, 2.0],
    'tp2_r': [3.0, 4.0],
    'rvol_danger_size': [0.30, 0.40],
}

LAYER2_PARAMS = {
    'min_consolidation_days': [5, 10, 15],
    'max_consolidation_range': [15.0, 20.0, 25.0, 30.0],
    'min_volume': [100000, 150000, 200000],
    'min_dollar_volume': [2e6, 5e6, 10e6],
    'max_dist_sma20': [15.0, 20.0, 25.0],
    'max_stop_pct': [0.07, 0.08, 0.10],
    'rvol_danger': [3.0, 3.5, 4.0],
    'rvol_warning': [2.0, 2.5],
    'rvol_warning_size': [0.60, 0.70],
    'require_positive_rs': [False, True],
    'require_sma_trend': [False, True], 
    'require_bullish_spy': [False, True],
    'max_vix': [40.0, 50.0],
}

LAYER2_DEFAULTS = {
    'min_consolidation_days': 5,
    'max_consolidation_range': 20.0,
    'min_volume': 100000,
    'min_dollar_volume': 5e6,
    'max_dist_sma20': 20.0,
    'max_stop_pct': 0.08,
    'rvol_danger': 3.0,
    'rvol_warning': 2.0,
    'rvol_warning_size': 0.65,
    'require_bullish_spy': False,
    'require_positive_rs': False,
    'require_sma_trend': False, 
    'max_vix': 50.0,
}

FIXED_PARAMS = {
    'use_phases': True,
}

# ============================================================================
# UTILS
# ============================================================================

def create_engine_with_relaxed_requirements(tickers, start, end, equity):
    """
    Crea engine con requirements más relajados para data incompleta.
    Centraliza la configuración para asegurar consistencia en todas las fases.
    """
    return OptimizationEngineTHOR(
        tickers=tickers,
        start_date=start,
        end_date=end,
        initial_capital=equity,
        chunk_size=50,
        lookback_days=200,  # 🔥 REDUCIDO de 400 a 200 (más permisivo)
        offline_mode=True,
        use_float32=True
    )

def get_stratified_universe(start_date, end_date, target_size, seed):
    """Selección ESTRATIFICADA POR NIVELES (30% High / 40% Mid / 30% Low)."""
    np.random.seed(seed)
    cache = TickerCache()
    query = """
    SELECT ticker, AVG(close * volume) as avg_dv 
    FROM ohlcv_cache
    WHERE date BETWEEN ? AND ?
    GROUP BY ticker
    HAVING COUNT(*) >= 100 AND AVG(close * volume) > 100000
    ORDER BY avg_dv DESC
    """
    try:
        result = cache.conn.execute(query, (start_date, end_date)).fetchall()
        if not result: return []
        all_tickers = [row[0] for row in result]
        total = len(all_tickers)
        if total < target_size: return all_tickers
            
        n_high = int(target_size * 0.30)
        n_mid  = int(target_size * 0.40)
        n_low  = target_size - n_high - n_mid
        
        pool_high_end = max(n_high * 3, int(total * 0.20))
        pool_mid_end = pool_high_end + max(n_mid * 3, int(total * 0.40))
        
        pool_high = all_tickers[:pool_high_end]
        pool_mid = all_tickers[pool_high_end:pool_mid_end]
        pool_low = all_tickers[pool_mid_end:]
        
        try:
            sel_high = list(np.random.choice(pool_high, min(n_high, len(pool_high)), replace=False))
            sel_mid  = list(np.random.choice(pool_mid, min(n_mid, len(pool_mid)), replace=False))
            sel_low  = list(np.random.choice(pool_low, min(n_low, len(pool_low)), replace=False))
            uni = sel_high + sel_mid + sel_low
            logger.info(f"   🏛️ Stratified: {len(sel_high)} High + {len(sel_mid)} Mid + {len(sel_low)} Low")
            return uni
        except:
            return list(np.random.choice(all_tickers, target_size, replace=False))
    except:
        return []

def aggregate_params(results_list: List[Dict]) -> Dict:
    """Votación Democrática (Solo Folds válidos)."""
    # Filtrar folds con Sharpe decente (Veto de Calidad)
    valid_results = [r for r in results_list if r['sharpe'] > 0.3]  # Más estricto: > 0.5
    
    if not valid_results:
        print("⚠️  WARNING: No folds passed quality check (Sharpe > 0.2)")
        # Segundo intento: al menos Sharpe > 0
        valid_results = [r for r in results_list if r['sharpe'] > 0]
        if not valid_results:
            print("❌ CRITICAL: All folds returned -999. Check your data/parameters!")
            print("   Usando LAYER2_DEFAULTS como fallback...")
            return LAYER2_DEFAULTS.copy()
        else:
            print(f"   ⚡ Using {len(valid_results)} folds with Sharpe > 0")
    else:
        print(f"🗳️  Voting with {len(valid_results)}/{len(results_list)} qualified folds (Sharpe > 0.3)")

    aggregated = {}
    all_keys = set()
    for res in valid_results:
        all_keys.update(res['params'].keys())

    for key in all_keys:
        values = [r['params'][key] for r in valid_results if key in r['params']]
        if not values: continue
            
        if isinstance(values[0], list):
            # Flatten lists y contar
            flat_values = [item for sublist in values for item in (sublist if isinstance(sublist, list) else [sublist])]
            vote = Counter(flat_values)
        else:
            vote = Counter(values)

        winner = vote.most_common(1)[0][0]
        aggregated[key] = winner
    return aggregated

# ============================================================================
# OPTIMIZATION OBJECTIVES
# ============================================================================

def objective_wrapper(engine, param_grid, fixed_ctx=None):
    def objective(trial):
        params = LAYER2_DEFAULTS.copy()
        if fixed_ctx: params.update(fixed_ctx)
        for k, v in param_grid.items():
            params[k] = trial.suggest_categorical(k, v)
        params.update(FIXED_PARAMS)
        
        try:
            stats = engine.backtest(params)
            trades = stats.get('total_trades', 0)
            if trades < 30: return -999
            
            sharpe = stats.get('sharpe_ratio', -999)
            dd = abs(stats.get('max_drawdown_pct', 100))
            
            if dd > 25: sharpe *= 0.5
            if dd > 40: return -999
            return sharpe
        except: return -999
    return objective

# ============================================================================
# CORE ENGINE
# ============================================================================

def run_bugatti_evo(args):
    start_time = datetime.now()
    timestamp = start_time.strftime("%Y%m%d_%H%M%S")
    output_dir = Path('outputs/bugatti_evo')
    output_dir.mkdir(parents=True, exist_ok=True)
    
    print("\n" + "="*80)
    print(f"🏎️  BUGATTI EVO 2.0 - K-FOLD CROSS VALIDATION")
    print("="*80)
    print(f"🔹 IN-SAMPLE:  {args.in_start} -> {args.in_end} ({args.k_folds} Folds)")
    print(f"🔹 VALIDATION: {args.val_start} -> {args.val_end}")
    print(f"🔹 OOS:        {args.oos_start} -> {args.oos_end}")
    print("-" * 80)

    # ---------------------------------------------------------
    # FASE 1: IN-SAMPLE K-FOLD OPTIMIZATION
    # ---------------------------------------------------------
    fold_results = []
    
    for k in range(args.k_folds):
        fold_seed = args.seed + k
        print(f"\n🧩 FOLD {k+1}/{args.k_folds} (Seed: {fold_seed})")
        
        # 1. Universe
        universe = get_stratified_universe(args.in_start, args.in_end, args.fold_size, fold_seed)
        
        # 2. Engine
        engine = create_engine_with_relaxed_requirements(
            universe, 
            args.in_start, 
            args.in_end, 
            args.equity
        )
        
        # 3. Optimización
        study_l1 = optuna.create_study(direction='maximize', sampler=optuna.samplers.TPESampler(seed=fold_seed))
        study_l1.optimize(objective_wrapper(engine, LAYER1_PARAMS), n_trials=args.l1_trials, show_progress_bar=True)
        best_l1 = study_l1.best_params
        
        # CSV DUMP L1 (Mejora #3)
        study_l1.trials_dataframe().to_csv(output_dir / f'fold_{k+1}_l1_trials.csv', index=False)
        
        study_l2 = optuna.create_study(direction='maximize', sampler=optuna.samplers.TPESampler(seed=fold_seed))
        study_l2.optimize(objective_wrapper(engine, LAYER2_PARAMS, fixed_ctx=best_l1), n_trials=args.l2_trials, show_progress_bar=True)
        
        # CSV DUMP L2 (Mejora #3)
        study_l2.trials_dataframe().to_csv(output_dir / f'fold_{k+1}_l2_trials.csv', index=False)
        
        # 4. Resultados
        final_fold_params = LAYER2_DEFAULTS.copy()
        final_fold_params.update(best_l1)
        final_fold_params.update(study_l2.best_params)
        final_fold_params.update(FIXED_PARAMS)
        
        fold_sharpe = study_l2.best_value
        
        # Diagnóstico de calidad del fold
        if fold_sharpe < 0:
            print(f"   ❌ Fold {k+1} FAILED: Sharpe={fold_sharpe:.3f} (insufficient trades or bad params)")
            # Ejecutar un backtest con params defaults para diagnóstico
            diag_params = LAYER2_DEFAULTS.copy()
            diag_params.update(FIXED_PARAMS)
            diag_stats = engine.backtest(diag_params)
            print(f"      🔍 Diagnostic w/ defaults: Trades={diag_stats.get('total_trades', 0)}, "
                  f"Sharpe={diag_stats.get('sharpe_ratio', 0):.2f}")
        else:
            print(f"   ✅ Fold {k+1} Best Sharpe: {fold_sharpe:.3f}")
        
        # PARAM LOGGING (Mejora #2)
        print(f"   🔑 Key Params: Signal={final_fold_params.get('signal_type')} | Risk=${final_fold_params.get('risk_dollars')} | Stop={final_fold_params.get('max_stop_pct')}")
        
        fold_results.append({
            'fold': k+1,
            'sharpe': fold_sharpe,
            'params': final_fold_params
        })
        
        del engine, study_l1, study_l2
        gc.collect()
        
    # ---------------------------------------------------------
    # AGGREGATION & STABILITY CHECK
    # ---------------------------------------------------------
    print("\n🗳️  AGGREGATING RESULTS...")
    consensus_params = aggregate_params(fold_results)
    
    print("\n🏆 CONSENSUS PARAMETERS:")
    for key, val in sorted(consensus_params.items()):
        print(f"   {key}: {val}")
        
    # CROSS-VALIDATION RE-TEST (Mejora #1)
    print("\n⚖️  CROSS-VALIDATION: Testing consensus on all folds...")
    cv_scores = []
    
    for k in range(args.k_folds):
        fold_seed = args.seed + k
        universe = get_stratified_universe(args.in_start, args.in_end, args.fold_size, fold_seed)
        
        engine = create_engine_with_relaxed_requirements(
            universe, 
            args.in_start, 
            args.in_end, 
            args.equity
        )
        
        stats = engine.backtest(consensus_params)
        s = stats.get('sharpe_ratio', 0)
        cv_scores.append(s)
        print(f"   Fold {k+1} Consensus Sharpe: {s:.3f}")
        
        del engine
        gc.collect()
        
    cv_mean = np.mean(cv_scores)
    cv_std = np.std(cv_scores)
    stability_score = (1 - (cv_std / abs(cv_mean))) * 100 if cv_mean != 0 else 0
    
    print(f"\n📊 STABILITY REPORT:")
    print(f"   Mean Sharpe: {cv_mean:.3f} ± {cv_std:.3f}")
    print(f"   Stability Score: {stability_score:.1f}%")

    # ---------------------------------------------------------
    # FASE 2: VALIDATION
    # ---------------------------------------------------------
    print("\n" + "="*80)
    print("🧪 FASE 2: VALIDATION (WALK-FORWARD)")
    print("="*80)
    
    val_universe = get_stratified_universe(args.val_start, args.val_end, args.fold_size, args.seed + 999)
    engine_val = create_engine_with_relaxed_requirements(
        val_universe, 
        args.val_start, 
        args.val_end, 
        args.equity
    )
    
    stats_val = engine_val.backtest(consensus_params)
    val_sharpe = stats_val.get('sharpe_ratio', 0)
    
    degradation = ((val_sharpe - cv_mean) / abs(cv_mean)) * 100 if cv_mean != 0 else 0
    
    print(f"📊 VALIDATION RESULTS:")
    print(f"   Sharpe: {val_sharpe:.3f}")
    print(f"   Return: {stats_val.get('total_return_pct', 0):.2f}%")
    print(f"   Trades: {stats_val.get('total_trades', 0)}")
    print(f"   Expected Sharpe (CV Mean): {cv_mean:.3f}")
    print(f"   Degradation: {degradation:+.1f}%")
    
    robustness = "UNKNOWN"
    if abs(degradation) < 20:
        print("✅ ROBUST STRATEGY")
        robustness = "ROBUST"
    elif abs(degradation) < 40:
        print("⚠️  MODERATE OVERFITTING")
        robustness = "MODERATE"
    else:
        print("❌ SEVERE OVERFITTING")
        robustness = "CRITICAL"

    del engine_val
    gc.collect()

    # ---------------------------------------------------------
    # FASE 3: OUT-OF-SAMPLE
    # ---------------------------------------------------------
    stats_oos = {}
    if args.run_oos:
        print("\n" + "="*80)
        print("🚀 FASE 3: OUT-OF-SAMPLE (FINAL TEST)")
        print("="*80)
        
        oos_universe = get_stratified_universe(args.oos_start, args.oos_end, args.fold_size, args.seed + 888)
        engine_oos = create_engine_with_relaxed_requirements(
            oos_universe, 
            args.oos_start, 
            args.oos_end, 
            args.equity
        )
        
        stats_oos = engine_oos.backtest(consensus_params)
        print(f"📊 OOS RESULTS:")
        print(f"   Sharpe: {stats_oos.get('sharpe_ratio', 0):.3f}")
        print(f"   Return: {stats_oos.get('total_return_pct', 0):.2f}%")
        print(f"   Trades: {stats_oos.get('total_trades', 0)}")
        
        del engine_oos
        gc.collect()

    # ---------------------------------------------------------
    # SAVE REPORT
    # ---------------------------------------------------------
    report = {
        'timestamp': timestamp,
        'config': vars(args),
        'consensus_params': {k: str(v) for k,v in consensus_params.items()},
        'stability': {
            'cv_mean': cv_mean,
            'cv_std': cv_std,
            'stability_score': stability_score
        },
        'validation': {
            'sharpe': val_sharpe,
            'degradation': degradation,
            'robustness': robustness,
            'metrics': {k: v for k,v in stats_val.items() if isinstance(v, (int, float))}
        },
        'oos': {
            'metrics': {k: v for k,v in stats_oos.items() if isinstance(v, (int, float))}
        }
    }
    
    report_file = output_dir / f'bugatti_evo_report_{timestamp}.json'
    with open(report_file, 'w') as f:
        json.dump(report, f, indent=2)
        
    print(f"\n💾 Report saved to: {report_file}")
    print(f"⏱️  Total Time: {datetime.now() - start_time}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Bugatti EVO 2.0')
    parser.add_argument('--k-folds', type=int, default=3)
    parser.add_argument('--fold-size', type=int, default=150)
    parser.add_argument('--l1-trials', type=int, default=50)
    parser.add_argument('--l2-trials', type=int, default=30)
    parser.add_argument('--in-start', default='2020-01-01')
    parser.add_argument('--in-end', default='2022-12-31')
    parser.add_argument('--val-start', default='2023-01-01')
    parser.add_argument('--val-end', default='2023-12-31')
    parser.add_argument('--oos-start', default='2024-01-01')
    parser.add_argument('--oos-end', default='2025-12-31')
    parser.add_argument('--equity', type=float, default=100000)
    parser.add_argument('--seed', type=int, default=42)
    parser.add_argument('--run-oos', action='store_true')
    
    args = parser.parse_args()
    run_bugatti_evo(args)
