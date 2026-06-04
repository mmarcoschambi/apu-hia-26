import json
import pandas as pd
import numpy as np
from pathlib import Path
import logging
from src.backtest.vectorbt_engine_advanced import AdvancedVectorBTEngine
from src.data.ticker_cache import TickerCache

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def run_validation():
    # 1. Setup Period and Universe
    # We use the last 90 days which we backfilled
    end_date = "2026-04-30"
    start_date = "2026-02-01" 
    
    import sqlite3
    conn = sqlite3.connect("data/ticker_cache.db")
    # Get top 1000 tickers by RS composite from the start date to have a stable sample
    query = """
    SELECT ticker FROM daily_rs_rankings 
    WHERE date <= ? 
    ORDER BY date DESC, rs_composite DESC 
    LIMIT 1000
    """
    df_tickers = pd.read_sql_query(query, conn, params=(start_date,))
    universe = df_tickers['ticker'].tolist()
    conn.close()
    
    logger.info(f"Loaded universe of {len(universe)} tickers.")
    
    # 2. Load Production Config as Baseline
    config_path = Path("config/production_config.json")
    with open(config_path, 'r') as f:
        config = json.load(f)
    
    # Extract params from config (flattening nested structure if necessary)
    params = config.get('params', {})
    if not params: # Some configs might be flat
        params = {k: v for k, v in config.items() if not k.startswith('_')}

    # 3. BASELINE RUN
    logger.info("--- RUNNING BASELINE ---")
    baseline_engine = AdvancedVectorBTEngine(
        universe=universe,
        start_date=start_date,
        end_date=end_date,
        **params
    )
    # Ensure cohort filter is OFF for baseline
    baseline_engine.use_cohort_momentum_filter = False
    
    baseline_results = baseline_engine.run_backtest()
    
    # 4. EXPERIMENT RUN (Cohort Momentum)
    logger.info("--- RUNNING COHORT MOMENTUM EXPERIMENT ---")
    exp_engine = AdvancedVectorBTEngine(
        universe=universe,
        start_date=start_date,
        end_date=end_date,
        **params
    )
    exp_engine.use_cohort_momentum_filter = True
    exp_engine.min_cohort_score_delta = 0.0 # Hypothesis: positive momentum only
    
    exp_results = exp_engine.run_backtest()
    
    # 5. COMPARE RESULTS
    print("\n" + "="*40)
    print("VALIDATION RESULTS: Sector Cohort Momentum")
    print("="*40)
    
    metrics = ['total_return', 'sharpe_ratio', 'max_drawdown', 'win_rate', 'total_trades']
    
    comparison = []
    for m in metrics:
        b_val = baseline_results.get(m, 0)
        e_val = exp_results.get(m, 0)
        
        if m in ['total_return', 'max_drawdown', 'win_rate']:
            b_str = f"{b_val*100:.2f}%"
            e_str = f"{e_val*100:.2f}%"
        else:
            b_str = f"{b_val:.2f}"
            e_str = f"{e_val:.2f}"
            
        diff = e_val - b_val
        comparison.append({
            'Metric': m,
            'Baseline': b_str,
            'Experiment': e_str,
            'Delta': f"{diff*100:.2f}%" if m in ['total_return', 'win_rate'] else f"{diff:.2f}"
        })
    
    df_comp = pd.DataFrame(comparison)
    print(df_comp.to_string(index=False))
    
    # GO / NO-GO Decision
    sharpe_diff = exp_results['sharpe_ratio'] - baseline_results['sharpe_ratio']
    if sharpe_diff > 0:
        print("\n✅ GO: Experiment improved Sharpe Ratio.")
    else:
        print("\n❌ NO-GO: Experiment did not improve Sharpe Ratio.")

if __name__ == "__main__":
    run_validation()
