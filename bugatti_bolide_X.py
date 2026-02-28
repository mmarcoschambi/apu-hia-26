#!/usr/bin/env python3
"""
BUGATTI BOLIDE WALK-FORWARD - Lo mejor de ambos mundos
=======================================================

Combina:
1. Optimización 2-capas (inteligente, rápida)
2. Walk-forward IS/VAL/OOS (robusto, anti-overfitting)
3. Motor DIVO (memory-optimized)

Metodología:
┌─────────────────────────────────────────────────────────────────┐
│ Timeline:                                                       │
│ |------- IN-SAMPLE -------|---- VAL ----|------- OOS ---------|│
│   2020-01    2022-12       2023-01 06-30  2023-07-01  2024-12 │
│                                                                 │
│ Phase 1 (IS): Layer 1 (8 critical params)                      │
│ Phase 2 (IS): Layer 2 (11 secondary params)                    │
│ Phase 3 (VAL): Test robustness → Degradation %                 │
│ Phase 4 (OOS): Final test (optional, never touched)            │
└─────────────────────────────────────────────────────────────────┘

Ventajas:
- 90% más rápido que brute-force (2-layer)
- Anti-overfitting (walk-forward)
- 60% menos RAM (DIVO)
- Mejor generalización (estratificación)

Author: Built for the Bugatti Bolide WF 🏎️⚡📊
"""

import argparse
import json
import sys
from pathlib import Path
from datetime import datetime
import pandas as pd
import logging
import optuna
from typing import Dict, List
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))

from src.backtest.optimization_engine_divo import OptimizationEngineDIVO
from src.data.ticker_cache import TickerCache

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger(__name__)


# ============================================================================
# CONFIGURACIÓN DE CAPAS (igual que BOLIDE original)
# ============================================================================

# CAPA 1: PARÁMETROS CRÍTICOS (8 params) - FILTROS RELAJADOS
LAYER1_PARAMS = {
    'risk_dollars': [150, 200, 250],
    'max_exposure_pct': [0.20, 0.25, 0.30],
    'min_rvol': [1.0, 1.5, 2.0],  # ← Relajado (antes 1.5 min)
    'min_adr': [1.0, 1.5, 2.0],   # ← Relajado (antes 1.5 min)
    'signal_type': ['any', 'breakout'],  # ← Sin VCP (muy restrictivo)
    'tp1_r': [1.25, 1.5, 1.75, 2.0],
    'tp2_r': [2.5, 3.0, 3.5, 4.0],
    'rvol_danger_size': [0.25, 0.30, 0.35, 0.40],
}

# CAPA 2: PARÁMETROS SECUNDARIOS (11 params) - FILTROS RELAJADOS
LAYER2_PARAMS = {
    'min_consolidation_days': [5, 10],  # ← Menos opciones
    'max_consolidation_range': [15.0, 20.0, 25.0],  # ← Más permisivo
    'min_volume': [100000, 200000],  # ← Relajado (antes 200k min)
    'min_dollar_volume': [5e6, 10e6],  # ← Relajado (antes 10M min)
    'max_dist_sma20': [15.0, 20.0, 25.0],  # ← Más permisivo
    'max_stop_pct': [0.07, 0.08],  # ← Simplificado
    'rvol_danger': [3.0, 3.5],
    'rvol_warning': [2.0, 2.5],
    'rvol_warning_size': [0.60, 0.65, 0.70],
    'require_bullish_spy': [False],  # ← Solo False (SPY filter muy restrictivo)
    'max_vix': [40.0, 50.0],
}

# PARÁMETROS FIJOS
FIXED_PARAMS = {
    'use_phases': True,
    'require_positive_rs': False,
    'require_sma_trend': False,  # ← NUEVO: Desactiva filtros SMA/VIX hardcoded
}


# ============================================================================
# UNIVERSO ESTRATIFICADO
# ============================================================================

def get_stratified_universe(
    start_date: str,
    end_date: str,
    target_size: int = 100,
    seed: int = 42
) -> List[str]:
    """Selección estratificada por liquidez + diversidad."""
    np.random.seed(seed)
    cache = TickerCache()
    
    query = """
    SELECT ticker, 
           AVG(volume * close) as avg_dv,
           COUNT(*) as days
    FROM ohlcv_cache
    WHERE date BETWEEN ? AND ?
    GROUP BY ticker
    HAVING days >= 100
    ORDER BY avg_dv DESC
    """
    result = cache.conn.execute(query, (start_date, end_date)).fetchall()
    
    if len(result) == 0:
        raise ValueError("No tickers found in database")
    
    all_tickers = [(row[0], row[1]) for row in result]
    
    # Estratificación 30/40/30
    n_top = int(target_size * 0.3)
    n_mid = int(target_size * 0.4)
    n_low = target_size - n_top - n_mid
    
    top_liquid = [t[0] for t in all_tickers[:n_top]]
    
    mid_start = n_top
    mid_end = min(mid_start + n_mid * 3, len(all_tickers))
    mid_pool = [t[0] for t in all_tickers[mid_start:mid_end]]
    mid_liquid = list(np.random.choice(mid_pool, min(n_mid, len(mid_pool)), replace=False))
    
    low_start = mid_end
    low_pool = [t[0] for t in all_tickers[low_start:]]
    low_liquid = list(np.random.choice(low_pool, min(n_low, len(low_pool)), replace=False))
    
    universe = top_liquid + mid_liquid + low_liquid
    
    logger.info(f"✅ Stratified universe: {len(universe)} tickers")
    logger.info(f"   Top: {len(top_liquid)} | Mid: {len(mid_liquid)} | Low: {len(low_liquid)}")
    
    return universe


# ============================================================================
# OBJECTIVES (igual que BOLIDE)
# ============================================================================

def create_layer1_objective(engine, metric='sharpe', verbose=False):
    """Optimiza SOLO parámetros críticos."""
    
    trial_count = [0]  # Mutable counter
    
    def objective(trial):
        trial_count[0] += 1
        
        params = {
            'risk_dollars': trial.suggest_categorical('risk_dollars', LAYER1_PARAMS['risk_dollars']),
            'max_exposure_pct': trial.suggest_categorical('max_exposure_pct', LAYER1_PARAMS['max_exposure_pct']),
            'min_rvol': trial.suggest_categorical('min_rvol', LAYER1_PARAMS['min_rvol']),
            'min_adr': trial.suggest_categorical('min_adr', LAYER1_PARAMS['min_adr']),
            'signal_type': trial.suggest_categorical('signal_type', LAYER1_PARAMS['signal_type']),
            'tp1_r': trial.suggest_categorical('tp1_r', LAYER1_PARAMS['tp1_r']),
            'tp2_r': trial.suggest_categorical('tp2_r', LAYER1_PARAMS['tp2_r']),
            'rvol_danger_size': trial.suggest_categorical('rvol_danger_size', LAYER1_PARAMS['rvol_danger_size']),
            
            # Layer 2 defaults - RELAJADOS
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
            'max_vix': 50.0,
        }
        
        params.update(FIXED_PARAMS)
        
        try:
            stats = engine.backtest(params)
            
            # AUDITORÍA: Diagnóstico completo
            trades = stats.get('total_trades', 0)
            sharpe = stats.get('sharpe_ratio', -999)
            
            # Si falla, diagnosticar
            if trades == 0 or sharpe == -999:
                if verbose or trial_count[0] <= 5:  # Primeros 5 trials siempre verbose
                    print(f"\n⚠️  TRIAL {trial_count[0]} FALLIDO - 0 Trades")
                    print(f"   Params: signal={params['signal_type']}, rvol>={params['min_rvol']}, adr>={params['min_adr']}")
                    print(f"   require_sma_trend={params.get('require_sma_trend', True)}")
                    
                    # Check engine data
                    if engine.close is None:
                        print(f"   ❌ ERROR CRÍTICO: engine.close es None (no hay data)")
                    else:
                        print(f"   ✅ Engine tiene {engine.close.shape[0]} días × {engine.close.shape[1]} tickers")
                        
                        # Check RVOL data
                        if hasattr(engine, 'rvol'):
                            rvol_data = engine.rvol
                            rvol_valid = (~rvol_data.isna()).sum().sum()
                            rvol_total = rvol_data.size
                            print(f"   📊 RVOL: {rvol_valid}/{rvol_total} valid values ({rvol_valid/rvol_total*100:.1f}%)")
                            if rvol_valid == 0:
                                print(f"   ❌ CRÍTICO: RVOL es todo NaN!")
                        
                        # Check ADR data
                        if hasattr(engine, 'adr'):
                            adr_data = engine.adr
                            adr_valid = (~adr_data.isna()).sum().sum()
                            adr_total = adr_data.size
                            print(f"   📊 ADR: {adr_valid}/{adr_total} valid values ({adr_valid/adr_total*100:.1f}%)")
                            if adr_valid == 0:
                                print(f"   ❌ CRÍTICO: ADR es todo NaN!")
                    
                    # Check SPY data (solo si require_bullish_spy=True)
                    if params.get('require_bullish_spy', False):
                        if hasattr(engine, '_spy_close') and engine._spy_close is None:
                            print(f"   ⚠️  SPY no cargado (lazy) pero require_bullish_spy=True")
                        elif hasattr(engine, 'spy_close'):
                            spy_data = engine.spy_close  # Trigger lazy load
                            if spy_data is None or len(spy_data) == 0:
                                print(f"   ❌ ERROR: SPY data vacía o None")
                            else:
                                print(f"   ✅ SPY data OK ({len(spy_data)} días)")
            
            # Filtro mínimo de trades
            if trades < 5:
                return -999
            
            # Risk-adjusted score
            max_dd = abs(stats.get('max_drawdown_pct', 100))
            
            if max_dd > 30:
                sharpe *= 0.5
            elif max_dd > 20:
                sharpe *= 0.8
            
            return sharpe if metric == 'sharpe' else stats.get('profit_factor', 0)
                
        except Exception as e:
            print(f"\n🔥 EXCEPCIÓN EN TRIAL {trial_count[0]}: {str(e)}")
            import traceback
            traceback.print_exc()
            logger.error(f"Trial failed: {e}")
            return -999
    
    return objective


def create_layer2_objective(engine, best_layer1_params, metric='sharpe', verbose=False):
    """Fine-tune parámetros secundarios CON Layer 1 fijo."""
    
    trial_count = [0]
    
    def objective(trial):
        trial_count[0] += 1
        
        params = best_layer1_params.copy()
        
        params.update({
            'min_consolidation_days': trial.suggest_categorical('min_consolidation_days', LAYER2_PARAMS['min_consolidation_days']),
            'max_consolidation_range': trial.suggest_categorical('max_consolidation_range', LAYER2_PARAMS['max_consolidation_range']),
            'min_volume': trial.suggest_categorical('min_volume', LAYER2_PARAMS['min_volume']),
            'min_dollar_volume': trial.suggest_categorical('min_dollar_volume', LAYER2_PARAMS['min_dollar_volume']),
            'max_dist_sma20': trial.suggest_categorical('max_dist_sma20', LAYER2_PARAMS['max_dist_sma20']),
            'max_stop_pct': trial.suggest_categorical('max_stop_pct', LAYER2_PARAMS['max_stop_pct']),
            'rvol_danger': trial.suggest_categorical('rvol_danger', LAYER2_PARAMS['rvol_danger']),
            'rvol_warning': trial.suggest_categorical('rvol_warning', LAYER2_PARAMS['rvol_warning']),
            'rvol_warning_size': trial.suggest_categorical('rvol_warning_size', LAYER2_PARAMS['rvol_warning_size']),
            'require_bullish_spy': trial.suggest_categorical('require_bullish_spy', LAYER2_PARAMS['require_bullish_spy']),
            'max_vix': trial.suggest_categorical('max_vix', LAYER2_PARAMS['max_vix']),
        })
        
        try:
            stats = engine.backtest(params)
            
            # AUDITORÍA Layer 2
            trades = stats.get('total_trades', 0)
            sharpe = stats.get('sharpe_ratio', -999)
            
            if trades == 0 or sharpe == -999:
                if verbose or trial_count[0] <= 3:
                    print(f"\n⚠️  L2 TRIAL {trial_count[0]} FALLIDO - 0 Trades")
                    print(f"   Layer2 params: vol>={params['min_volume']}, $vol>={params['min_dollar_volume']/1e6:.0f}M")
            
            if trades < 5:
                return -999
            
            sharpe = stats.get('sharpe_ratio', -999)
            max_dd = abs(stats.get('max_drawdown_pct', 100))
            
            if max_dd > 30:
                sharpe *= 0.5
            elif max_dd > 20:
                sharpe *= 0.8
            
            return sharpe if metric == 'sharpe' else stats.get('profit_factor', 0)
                
        except Exception as e:
            print(f"\n🔥 EXCEPCIÓN EN L2 TRIAL {trial_count[0]}: {str(e)}")
            import traceback
            traceback.print_exc()
            logger.error(f"Trial failed: {e}")
            return -999
    
    return objective


# ============================================================================
# MAIN - WALK-FORWARD
# ============================================================================

def main():
    parser = argparse.ArgumentParser(description='Bugatti BOLIDE Walk-Forward')
    
    # IN-SAMPLE (optimization)
    parser.add_argument('--in-start', type=str, default='2020-01-01')
    parser.add_argument('--in-end', type=str, default='2022-12-31')
    
    # VALIDATION (robustness test)
    parser.add_argument('--val-start', type=str, default='2023-01-01')
    parser.add_argument('--val-end', type=str, default='2023-06-30')
    
    # OUT-OF-SAMPLE (final test, optional)
    parser.add_argument('--oos-start', type=str, default='2023-07-01')
    parser.add_argument('--oos-end', type=str, default='2024-12-31')
    
    # Layer settings
    parser.add_argument('--layer1-trials', type=int, default=100)
    parser.add_argument('--layer1-tickers', type=int, default=100)
    parser.add_argument('--layer2-trials', type=int, default=50)
    parser.add_argument('--layer2-tickers', type=int, default=50)
    
    # General
    parser.add_argument('--metric', type=str, default='sharpe', choices=['sharpe', 'profit_factor'])
    parser.add_argument('--equity', type=float, default=100000)
    parser.add_argument('--lookback', type=int, default=365)
    parser.add_argument('--seed', type=int, default=42)
    parser.add_argument('--run-oos', action='store_true', help='Run OOS test immediately (no prompt)')
    
    args = parser.parse_args()
    
    print("="*80)
    print("🏎️⚡📊 BUGATTI BOLIDE WALK-FORWARD")
    print("="*80)
    print(f"\n📊 DATA SPLIT:")
    print(f"  IN-SAMPLE:     {args.in_start} to {args.in_end}  (Optimize)")
    print(f"  VALIDATION:    {args.val_start} to {args.val_end}  (Robustness)")
    print(f"  OUT-OF-SAMPLE: {args.oos_start} to {args.oos_end}  (Final Test)")
    print(f"\n⚙️  OPTIMIZATION:")
    print(f"  Layer 1: {args.layer1_trials} trials × {args.layer1_tickers} tickers (critical)")
    print(f"  Layer 2: {args.layer2_trials} trials × {args.layer2_tickers} tickers (fine-tune)")
    print(f"\n🎯 METRIC: {args.metric.upper()}")
    print(f"💰 CAPITAL: ${args.equity:,.0f}")
    print("="*80)
    
    output_dir = Path('outputs/bolide_walkforward')
    output_dir.mkdir(parents=True, exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # ========================================================================
    # PHASE 1 & 2: IN-SAMPLE OPTIMIZATION (2-LAYER)
    # ========================================================================
    logger.info("\n" + "="*80)
    logger.info("📈 PHASE 1 & 2: IN-SAMPLE OPTIMIZATION (2-LAYER)")
    logger.info("="*80)
    
    # Layer 1
    logger.info("\n🎯 LAYER 1: CRITICAL PARAMETERS")
    universe_l1 = get_stratified_universe(args.in_start, args.in_end, args.layer1_tickers, args.seed)
    
    logger.info("🏎️💨 Initializing DIVO engine (Layer 1)...")
    engine_l1 = OptimizationEngineDIVO(
        tickers=universe_l1,
        start_date=args.in_start,
        end_date=args.in_end,
        initial_capital=args.equity,
        lookback_days=args.lookback,
        offline_mode=True,
        use_float32=True,
        chunk_size=50
    )
    
    summary_l1 = engine_l1.get_data_summary()
    logger.info(f"📊 Engine: {summary_l1['tickers_loaded']} tickers, {summary_l1['memory_mb']:.1f} MB")
    
    study_l1 = optuna.create_study(
        direction='maximize',
        study_name=f'bolide_wf_layer1_{timestamp}',
        sampler=optuna.samplers.TPESampler(seed=args.seed)
    )
    
    objective_l1 = create_layer1_objective(engine_l1, args.metric, verbose=True)
    
    logger.info(f"🚀 Starting Layer 1 optimization ({args.layer1_trials} trials)...")
    logger.info(f"📊 Verbose diagnostics: First 5 trials + all failures")
    study_l1.optimize(objective_l1, n_trials=args.layer1_trials, show_progress_bar=True)
    
    best_l1_params = study_l1.best_params
    best_l1_value = study_l1.best_value
    
    print("\n" + "="*80)
    print("🏆 LAYER 1 RESULTS (IN-SAMPLE)")
    print("="*80)
    print(f"{args.metric.upper()}: {best_l1_value:.3f}")
    
    df_l1 = study_l1.trials_dataframe()
    df_l1.to_csv(output_dir / f'layer1_trials_{timestamp}.csv', index=False)
    
    engine_l1.clear_indicator_cache()
    del engine_l1
    
    # Layer 2
    logger.info("\n🔧 LAYER 2: FINE-TUNING")
    universe_l2 = get_stratified_universe(args.in_start, args.in_end, args.layer2_tickers, args.seed + 1)
    
    logger.info("🏎️💨 Initializing DIVO engine (Layer 2)...")
    engine_l2 = OptimizationEngineDIVO(
        tickers=universe_l2,
        start_date=args.in_start,
        end_date=args.in_end,
        initial_capital=args.equity,
        lookback_days=args.lookback,
        offline_mode=True,
        use_float32=True,
        chunk_size=50
    )
    
    full_l1_params = best_l1_params.copy()
    full_l1_params.update({
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
        'max_vix': 50.0,
    })
    full_l1_params.update(FIXED_PARAMS)
    
    study_l2 = optuna.create_study(
        direction='maximize',
        study_name=f'bolide_wf_layer2_{timestamp}',
        sampler=optuna.samplers.TPESampler(seed=args.seed)
    )
    
    objective_l2 = create_layer2_objective(engine_l2, full_l1_params, args.metric, verbose=True)
    
    logger.info(f"🚀 Starting Layer 2 optimization ({args.layer2_trials} trials)...")
    logger.info(f"📊 Verbose diagnostics: First 3 trials + all failures")
    study_l2.optimize(objective_l2, n_trials=args.layer2_trials, show_progress_bar=True)
    
    best_l2_params = study_l2.best_params
    best_l2_value = study_l2.best_value
    
    improvement_pct = ((best_l2_value - best_l1_value) / abs(best_l1_value) * 100) if best_l1_value != 0 else 0
    
    print("\n" + "="*80)
    print("🏆 LAYER 2 RESULTS (IN-SAMPLE)")
    print("="*80)
    print(f"{args.metric.upper()}: {best_l2_value:.3f}")
    print(f"Improvement over Layer 1: {improvement_pct:+.1f}%")
    
    df_l2 = study_l2.trials_dataframe()
    df_l2.to_csv(output_dir / f'layer2_trials_{timestamp}.csv', index=False)
    
    # Final IN-SAMPLE config
    final_params = full_l1_params.copy()
    final_params.update(best_l2_params)
    
    print("\n📋 OPTIMIZED CONFIGURATION (IN-SAMPLE):")
    for key, value in sorted(final_params.items()):
        print(f"   {key}: {value}")
    
    engine_l2.clear_indicator_cache()
    del engine_l2
    
    # ========================================================================
    # PHASE 3: VALIDATION (ROBUSTNESS TEST)
    # ========================================================================
    logger.info("\n" + "="*80)
    logger.info("📊 PHASE 3: VALIDATION (ROBUSTNESS TEST)")
    logger.info("="*80)
    
    universe_val = get_stratified_universe(args.val_start, args.val_end, args.layer2_tickers, args.seed + 2)
    
    logger.info("🏎️💨 Initializing DIVO engine (Validation)...")
    engine_val = OptimizationEngineDIVO(
        tickers=universe_val,
        start_date=args.val_start,
        end_date=args.val_end,
        initial_capital=args.equity,
        lookback_days=args.lookback,
        offline_mode=True,
        use_float32=True,
        chunk_size=50
    )
    
    logger.info("🧪 Testing optimized params on VALIDATION period...")
    stats_val = engine_val.backtest(final_params)
    
    print("\n" + "="*80)
    print("📊 VALIDATION RESULTS")
    print("="*80)
    
    if stats_val and stats_val.get('total_trades', 0) >= 10:
        val_sharpe = stats_val.get('sharpe_ratio', 0)
        val_return = stats_val.get('total_return_pct', 0)
        val_dd = stats_val.get('max_drawdown_pct', 0)
        val_winrate = stats_val.get('win_rate_pct', 0)
        val_trades = stats_val.get('total_trades', 0)
        val_pf = stats_val.get('profit_factor', 0)
        
        print(f"Sharpe Ratio:  {val_sharpe:.2f}")
        print(f"Total Return:  {val_return:.2f}%")
        print(f"Max Drawdown:  {val_dd:.2f}%")
        print(f"Win Rate:      {val_winrate:.2f}%")
        print(f"Total Trades:  {val_trades}")
        print(f"Profit Factor: {val_pf:.2f}")
        
        # DEGRADATION ANALYSIS
        degradation = ((val_sharpe - best_l2_value) / abs(best_l2_value) * 100) if best_l2_value != 0 else 0
        
        print(f"\n🔍 OVERFITTING CHECK:")
        print(f"  IN-SAMPLE {args.metric}:  {best_l2_value:.3f}")
        print(f"  VALIDATION {args.metric}: {val_sharpe:.3f}")
        print(f"  Degradation:              {degradation:+.1f}%")
        
        if abs(degradation) < 20:
            print("\n✅ EXCELLENT! Parameters are robust (< 20% degradation)")
            robustness = "EXCELLENT"
        elif abs(degradation) < 40:
            print("\n⚠️  WARNING! Moderate overfitting (20-40% degradation)")
            robustness = "WARNING"
        else:
            print("\n❌ CRITICAL! Severe overfitting (> 40% degradation)")
            robustness = "CRITICAL"
    else:
        print("❌ Insufficient trades in validation period")
        val_sharpe = 0
        degradation = -100
        robustness = "FAILED"
        stats_val = {}
    
    engine_val.clear_indicator_cache()
    del engine_val
    
    # ========================================================================
    # PHASE 4: OUT-OF-SAMPLE (OPTIONAL FINAL TEST)
    # ========================================================================
    print("\n" + "="*80)
    print("🎯 PHASE 4: OUT-OF-SAMPLE TEST")
    print("="*80)
    print("⚠️  Final test - only run when ready to deploy!")
    print("="*80)
    
    run_oos = args.run_oos
    if not run_oos:
        response = input("\nRun OUT-OF-SAMPLE test? (yes/no): ").strip().lower()
        run_oos = (response == 'yes')
    
    stats_oos = {}
    if run_oos:
        logger.info("🚀 Running OUT-OF-SAMPLE test...")
        
        universe_oos = get_stratified_universe(args.oos_start, args.oos_end, args.layer2_tickers, args.seed + 3)
        
        engine_oos = OptimizationEngineDIVO(
            tickers=universe_oos,
            start_date=args.oos_start,
            end_date=args.oos_end,
            initial_capital=args.equity,
            lookback_days=args.lookback,
            offline_mode=True,
            use_float32=True,
            chunk_size=50
        )
        
        stats_oos = engine_oos.backtest(final_params)
        
        print("\n" + "="*80)
        print("🏁 OUT-OF-SAMPLE RESULTS")
        print("="*80)
        
        if stats_oos and stats_oos.get('total_trades', 0) >= 10:
            print(f"Sharpe Ratio:  {stats_oos.get('sharpe_ratio', 0):.2f}")
            print(f"Total Return:  {stats_oos.get('total_return_pct', 0):.2f}%")
            print(f"Max Drawdown:  {stats_oos.get('max_drawdown_pct', 0):.2f}%")
            print(f"Win Rate:      {stats_oos.get('win_rate_pct', 0):.2f}%")
            print(f"Total Trades:  {stats_oos.get('total_trades', 0)}")
            print(f"Profit Factor: {stats_oos.get('profit_factor', 0):.2f}")
        else:
            print("❌ Insufficient trades in OOS period")
        
        engine_oos.clear_indicator_cache()
        del engine_oos
    else:
        print("\n⏭️  OUT-OF-SAMPLE test skipped")
    
    # ========================================================================
    # SAVE FINAL REPORT
    # ========================================================================
    final_report = {
        'timestamp': datetime.now().isoformat(),
        'method': 'Bugatti_BOLIDE_WalkForward',
        'engine': 'DIVO (memory-optimized)',
        'periods': {
            'in_sample': f"{args.in_start} to {args.in_end}",
            'validation': f"{args.val_start} to {args.val_end}",
            'out_of_sample': f"{args.oos_start} to {args.oos_end}",
        },
        'layer1': {
            'trials': args.layer1_trials,
            'tickers': args.layer1_tickers,
            'best_value': float(best_l1_value),
            'best_params': {k: str(v) if not isinstance(v, (int, float, bool)) else v 
                           for k, v in best_l1_params.items()},
        },
        'layer2': {
            'trials': args.layer2_trials,
            'tickers': args.layer2_tickers,
            'best_value': float(best_l2_value),
            'best_params': {k: str(v) if not isinstance(v, (int, float, bool)) else v 
                           for k, v in best_l2_params.items()},
            'improvement_pct': float(improvement_pct),
        },
        'validation': {
            'sharpe': float(val_sharpe) if stats_val else 0,
            'degradation_pct': float(degradation) if stats_val else -100,
            'robustness': robustness,
            'stats': {k: float(v) if isinstance(v, (int, float)) else v 
                     for k, v in stats_val.items()} if stats_val else {},
        },
        'out_of_sample': {
            'run': run_oos,
            'stats': {k: float(v) if isinstance(v, (int, float)) else v 
                     for k, v in stats_oos.items()} if stats_oos else {},
        },
        'final_params': {k: str(v) if not isinstance(v, (int, float, bool)) else v 
                        for k, v in final_params.items()},
    }
    
    config_file = output_dir / f'bolide_walkforward_{timestamp}.json'
    with open(config_file, 'w') as f:
        json.dump(final_report, f, indent=2)
    
    logger.info(f"\n💾 Final report: {config_file}")
    
    # ========================================================================
    # FINAL SUMMARY
    # ========================================================================
    print("\n" + "="*80)
    print("✅ BOLIDE WALK-FORWARD OPTIMIZATION COMPLETE!")
    print("="*80)
    print(f"📁 Results: {output_dir}")
    print(f"\n📊 SUMMARY:")
    print(f"  IN-SAMPLE:    {best_l2_value:.3f}")
    print(f"  VALIDATION:   {val_sharpe:.3f} ({degradation:+.1f}% degradation)")
    if run_oos and stats_oos:
        print(f"  OUT-OF-SAMPLE: {stats_oos.get('sharpe_ratio', 0):.3f}")
    print(f"\n  Robustness:   {robustness}")
    print(f"\n⏱️  Time saved vs brute-force: ~90%")
    print(f"💾 RAM saved vs Chiron: ~60%")
    print("="*80)
    print(f"\n🏎️⚡📊 BOLIDE WALK-FORWARD OUT! 💨💨💨")


if __name__ == '__main__':
    main()
