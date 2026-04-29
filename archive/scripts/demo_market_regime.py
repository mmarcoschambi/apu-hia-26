#!/usr/bin/env python3
"""
Bugatti Market Regime Demo
Demo de Market Regime Filter integrado con Bugatti EVO

Compara 3 escenarios:
1. Baseline (sin filtro de régimen)
2. Conservative (bloquea Stage 3-4)
3. Adaptive (solo ajusta riesgo, no bloquea)
"""

import pandas as pd
import logging
from datetime import datetime
from src.backtest.vectorbt_engine_advanced import AdvancedVectorBTEngine
from src.data.ticker_cache import TickerCache

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def load_bugatti_universe(cache, min_tickers=20):
    """Load universe from bugatti_ready_tickers.txt"""
    try:
        with open('bugatti_ready_tickers.txt', 'r') as f:
            universe = [line.strip() for line in f if line.strip()]
        
        if len(universe) < min_tickers:
            logger.warning(f"Only {len(universe)} tickers in file, loading from cache...")
            universe = cache.get_all_tickers()[:100]  # Top 100 by data quality
        
        logger.info(f"✅ Universe loaded: {len(universe)} tickers")
        return universe
    
    except FileNotFoundError:
        logger.warning("bugatti_ready_tickers.txt not found, using cache...")
        cache = TickerCache()
        universe = cache.get_all_tickers()[:100]
        return universe


def run_comparison():
    """Run 3 backtests with different regime configurations"""
    
    logger.info("="*80)
    logger.info("BUGATTI MARKET REGIME COMPARISON")
    logger.info("="*80)
    
    # Configuration
    start_date = '2022-01-01'
    end_date = '2024-12-31'
    initial_capital = 100000
    risk_dollars = 150
    
    # Load universe
    cache = TickerCache()
    universe = load_bugatti_universe(cache)
    
    # Base parameters (shared across all scenarios)
    base_params = {
        'universe': universe[:50],  # Limit to 50 for faster testing
        'start_date': start_date,
        'end_date': end_date,
        'initial_capital': initial_capital,
        'risk_dollars': risk_dollars,
        'max_exposure_pct': 0.25,
        
        # Quality filters
        'min_rvol': 1.5,
        'min_adr': 2.0,
        'min_volume': 500000,
        'min_dollar_volume': 10000000,
        'max_dist_sma20': 10.0,
        
        # Exit parameters
        'max_stop_pct': 8.0,
        'use_earnings_calendar': True,
        'earnings_days': 5,
        'earnings_cushion': 10.0,
    }
    
    results = {}
    
    # ===================================================================
    # SCENARIO 1: BASELINE (No Market Regime Filter)
    # ===================================================================
    logger.info("\n" + "="*80)
    logger.info("SCENARIO 1: BASELINE (No Market Regime Filter)")
    logger.info("="*80)
    
    engine_baseline = AdvancedVectorBTEngine(
        **base_params,
        use_market_regime_filter=False,  # ❌ Disabled
    )
    
    try:
        results['baseline'] = engine_baseline.run_backtest()
        logger.info(f"✅ Baseline complete: {results['baseline']['total_trades']} trades")
    except Exception as e:
        logger.error(f"❌ Baseline failed: {e}")
        results['baseline'] = None
    
    # ===================================================================
    # SCENARIO 2: CONSERVATIVE (Block Stage 3-4)
    # ===================================================================
    logger.info("\n" + "="*80)
    logger.info("SCENARIO 2: CONSERVATIVE (Block Stage 3-4)")
    logger.info("="*80)
    
    engine_conservative = AdvancedVectorBTEngine(
        **base_params,
        use_market_regime_filter=True,   # ✅ Enabled
        block_trades_in_stage3=True,     # ✅ Block Stage 3
        block_trades_in_stage4=True,     # ✅ Block Stage 4
        adjust_risk_by_regime=True,      # ✅ Adjust risk
    )
    
    try:
        results['conservative'] = engine_conservative.run_backtest()
        logger.info(f"✅ Conservative complete: {results['conservative']['total_trades']} trades")
    except Exception as e:
        logger.error(f"❌ Conservative failed: {e}")
        results['conservative'] = None
    
    # ===================================================================
    # SCENARIO 3: ADAPTIVE (Adjust Risk Only, Don't Block)
    # ===================================================================
    logger.info("\n" + "="*80)
    logger.info("SCENARIO 3: ADAPTIVE (Adjust Risk Only)")
    logger.info("="*80)
    
    engine_adaptive = AdvancedVectorBTEngine(
        **base_params,
        use_market_regime_filter=True,   # ✅ Enabled
        block_trades_in_stage3=False,    # ❌ Don't block
        block_trades_in_stage4=False,    # ❌ Don't block
        adjust_risk_by_regime=True,      # ✅ Adjust risk
    )
    
    try:
        results['adaptive'] = engine_adaptive.run_backtest()
        logger.info(f"✅ Adaptive complete: {results['adaptive']['total_trades']} trades")
    except Exception as e:
        logger.error(f"❌ Adaptive failed: {e}")
        results['adaptive'] = None
    
    # ===================================================================
    # COMPARISON TABLE
    # ===================================================================
    logger.info("\n" + "="*80)
    logger.info("RESULTS COMPARISON")
    logger.info("="*80)
    
    # Create comparison table
    comparison = []
    metrics = [
        ('Total Return', 'total_return', lambda x: f"{x*100:.2f}%"),
        ('Sharpe Ratio', 'sharpe_ratio', lambda x: f"{x:.2f}"),
        ('Max Drawdown', 'max_drawdown', lambda x: f"{x*100:.2f}%"),
        ('Win Rate', 'win_rate', lambda x: f"{x*100:.1f}%"),
        ('Total Trades', 'total_trades', lambda x: f"{x}"),
    ]
    
    for metric_name, metric_key, formatter in metrics:
        row = {'Metric': metric_name}
        for scenario in ['baseline', 'conservative', 'adaptive']:
            if results[scenario] is not None:
                value = results[scenario].get(metric_key, 0)
                row[scenario.title()] = formatter(value)
            else:
                row[scenario.title()] = 'N/A'
        comparison.append(row)
    
    df_comparison = pd.DataFrame(comparison)
    print("\n" + df_comparison.to_string(index=False))
    
    # ===================================================================
    # ANALYSIS & RECOMMENDATIONS
    # ===================================================================
    logger.info("\n" + "="*80)
    logger.info("ANALYSIS")
    logger.info("="*80)
    
    if all(results.values()):
        # Calculate improvements
        baseline_return = results['baseline']['total_return']
        baseline_dd = results['baseline']['max_drawdown']
        baseline_sharpe = results['baseline']['sharpe_ratio']
        
        for scenario in ['conservative', 'adaptive']:
            scenario_return = results[scenario]['total_return']
            scenario_dd = results[scenario]['max_drawdown']
            scenario_sharpe = results[scenario]['sharpe_ratio']
            
            return_delta = ((scenario_return - baseline_return) / abs(baseline_return)) * 100
            dd_delta = ((scenario_dd - baseline_dd) / abs(baseline_dd)) * 100
            sharpe_delta = ((scenario_sharpe - baseline_sharpe) / baseline_sharpe) * 100 if baseline_sharpe != 0 else 0
            
            logger.info(f"\n{scenario.upper()} vs BASELINE:")
            logger.info(f"   Return: {return_delta:+.1f}%")
            logger.info(f"   Drawdown: {dd_delta:+.1f}% ({'better' if dd_delta > 0 else 'worse'})")
            logger.info(f"   Sharpe: {sharpe_delta:+.1f}%")
            logger.info(f"   Trades: {results[scenario]['total_trades']} vs {results['baseline']['total_trades']}")
    
    # ===================================================================
    # RECOMMENDATIONS
    # ===================================================================
    logger.info("\n" + "="*80)
    logger.info("RECOMMENDATIONS")
    logger.info("="*80)
    
    logger.info("""
    📊 BASELINE: Sin filtro de régimen
       ✅ Ventajas: Más trades, captura todos los rallies
       ❌ Desventajas: Mayor drawdown en bear markets
       🎯 Usar si: Quieres maximizar retorno absoluto
    
    🛡️  CONSERVATIVE: Bloquea Stage 3-4
       ✅ Ventajas: Protección en bear markets, mejor Sharpe
       ❌ Desventajas: Menos trades, posibles rallies perdidos
       🎯 Usar si: Priorizas protección de capital
    
    📈 ADAPTIVE: Solo ajusta riesgo
       ✅ Ventajas: Balance entre protección y oportunidad
       ❌ Desventajas: Complejidad adicional
       🎯 Usar si: Quieres adaptación automática sin perder trades
    
    💡 RECOMENDACIÓN GENERAL:
       - Swing Trading (2-10 días): CONSERVATIVE
       - Position Trading (10-30 días): ADAPTIVE
       - Day Trading: BASELINE (régimen intraday diferente)
    """)
    
    logger.info("="*80)
    logger.info("✅ Comparison Complete!")
    logger.info("="*80)
    
    return results


if __name__ == "__main__":
    results = run_comparison()
