import pandas as pd
import numpy as np
from pathlib import Path
import logging
import argparse
import sys
import json
from datetime import datetime

# Setup Project Root
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.backtest.vectorbt_engine_advanced import AdvancedVectorBTEngine
from src.data.pit_universe import PointInTimeUniverse

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# Constants
START_DATE = "2025-01-01"
END_DATE = "2026-04-30"
INITIAL_CAPITAL = 100_000
FIXED_RISK = 1000.0

SECTOR_MAP = {
    "weak": 0.50,
    "low": 0.75,
    "mid": 1.00,
    "high": 1.25,
    "extreme": 1.10
}

def run_experiment(name, use_filter, multiplier_map):
    logger.info(f"Running Experiment: {name}")
    
    # Get universe for the period
    pit = PointInTimeUniverse()
    superset = pit.get_superset(START_DATE, END_DATE)
    logger.info(f"Using superset of {len(superset)} tickers for {name}")

    # We use a standard set of parameters for all experiments
    engine = AdvancedVectorBTEngine(
        universe=superset,
        start_date=START_DATE,
        end_date=END_DATE,
        initial_capital=INITIAL_CAPITAL,
        use_fixed_dollar_risk=True,
        risk_dollars=FIXED_RISK,
        max_positions=15,
        use_sector_etf_filter=use_filter,
        sector_multiplier_map=multiplier_map,
        fee_rate=0.001,
        slippage_rate=0.001,
        # Standard pure momentum setup
        rs_threshold=58,
        use_vcp_filter=False,
        rank_by="rs_composite",
        benchmark_ticker="SPY"
    )
    
    # Run backtest
    try:
        # Verified via probe: engine returns a dictionary
        results = engine.run_backtest()
        
        if not isinstance(results, dict):
            # Fallback if somehow it returns a tuple in different conditions
            return {"name": name, "error": f"Unexpected return type: {type(results)}"}
            
        return {
            "name": name,
            "total_return": results.get("total_return", 0),
            "sharpe": results.get("sharpe_ratio", 0),
            "max_drawdown": results.get("max_drawdown", 0),
            "trades": results.get("total_trades", 0),
            "win_rate": results.get("win_rate", 0),
            "profit_factor": results.get("profit_factor", 0)
        }
    except Exception as e:
        logger.error(f"Error running experiment {name}: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return {"name": name, "error": str(e)}

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--configs", nargs="+", default=["S0", "S1", "S2"])
    args = parser.parse_args()

    results_all = []

    if "S0" in args.configs:
        results_all.append(run_experiment("S0_Baseline", False, None))
    
    if "S1" in args.configs:
        results_all.append(run_experiment("S1_BinaryFilter", True, None))
        
    if "S2" in args.configs:
        results_all.append(run_experiment("S2_DynamicSizing", True, SECTOR_MAP))

    # Summary
    df = pd.DataFrame(results_all)
    print("\n" + "="*60)
    print("SANDBOX VALIDATION RESULTS")
    print("="*60)
    print(df.to_string(index=False))
    print("-" * 60)
    
    # Decision logic
    if len(df) >= 3 and "error" not in df.columns:
        try:
            s0 = df[df["name"] == "S0_Baseline"]["sharpe"].values[0]
            s1 = df[df["name"] == "S1_BinaryFilter"]["sharpe"].values[0]
            s2 = df[df["name"] == "S2_DynamicSizing"]["sharpe"].values[0]
            
            if s2 > s1 > s0:
                print(f"DECISION: Hypothesis A SUCCESSFUL (S2:{s2:.3f} > S1:{s1:.3f} > S0:{s0:.3f})")
            elif s2 > s1:
                print(f"DECISION: Hypothesis A PROMOTED (S2:{s2:.3f} > S1:{s1:.3f})")
            else:
                print(f"DECISION: Hypothesis A FAILED (S2:{s2:.3f} <= S1:{s1:.3f})")
        except:
            pass
    
    # Save report
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = PROJECT_ROOT / "outputs" / "experiments" / f"sandbox_results_{ts}.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(results_all, f, indent=2, default=str)
    logger.info(f"Report saved to {output_path}")

if __name__ == "__main__":
    main()
