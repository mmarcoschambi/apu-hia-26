import sys
from pathlib import Path
import optuna

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from src.backtest.vectorbt_engine_advanced import AdvancedVectorBTEngine
from walk_forward_combos import get_universe_from_db
from scripts.validate_optuna_results_oos import build_engine_kwargs

def run_test(params, start_date, end_date, universe, label):
    kwargs = build_engine_kwargs(params)
    engine = AdvancedVectorBTEngine(
        universe=universe,
        start_date=start_date,
        end_date=end_date,
        initial_capital=100_000,
        **kwargs
    )
    result = engine.run_backtest()
    metrics = result
    
    trades = len(result.get("trades_df", []))
    print(f"Metrics keys: {list(metrics.keys())}")
    
    # Try different keys for sharpe
    sharpe = metrics.get("Sharpe Ratio", metrics.get("sharpe_ratio", 0))
    pf = metrics.get("Profit Factor", metrics.get("profit_factor", 0))
    mdd = metrics.get("Max Drawdown [%]", metrics.get("max_drawdown", 0))
    if "Max Drawdown [%]" not in metrics and "max_drawdown" in metrics:
        mdd *= 100
        
    calmar = metrics.get("Calmar Ratio", metrics.get("calmar_ratio", 0))
    cagr = metrics.get("Return [%]", metrics.get("annualized_return", metrics.get("cagr", 0)))
    
    print(f"--- {label} ({start_date} to {end_date}) ---")
    print(f"Trades: {trades}")
    print(f"Sharpe: {sharpe:.4f}")
    print(f"Profit Factor: {pf:.2f}")
    print(f"Max Drawdown: {mdd:.2f}%")
    print(f"Calmar: {calmar:.4f}")
    print(f"CAGR: {cagr:.4f}")
    
    return {
        "trades": trades,
        "sharpe": sharpe,
        "profit_factor": pf,
        "mdd_pct": mdd,
        "calmar": calmar,
        "cagr": cagr
    }

def main():
    import json
    import datetime
    
    print("Loading Trial 237 from pilot_study.db...")
    study = optuna.load_study(study_name='pilot', storage='sqlite:///outputs/optuna_s4/pilot_study.db')
    trial_237 = None
    for t in study.trials:
        if t.number == 237:
            trial_237 = t
            break
            
    if not trial_237:
        print("Trial 237 not found!")
        return
        
    print("Loading Universe...")
    universe = get_universe_from_db("2019-01-01", "2024-12-31", 1200)
    
    print("\nRunning IN-SAMPLE (2019-01-01 to 2023-12-31)...")
    is_metrics = run_test(trial_237.params, "2019-01-01", "2023-12-31", universe, "IN-SAMPLE")
    
    print("\nRunning OUT-OF-SAMPLE (2024-01-01 to 2024-07-31)...")
    oos_metrics = run_test(trial_237.params, "2024-01-01", "2024-07-31", universe, "OUT-OF-SAMPLE")
    
    is_sharpe = is_metrics["sharpe"]
    oos_sharpe = oos_metrics["sharpe"]
    
    evidence = {
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "trial": 237,
        "params": trial_237.params,
        "in_sample": is_metrics,
        "out_of_sample": oos_metrics,
        "verdict": "REJECTED (Curve Fitted)" if oos_sharpe <= 0 else "PASSED"
    }
    
    out_dir = PROJECT_ROOT / "artifacts"
    out_dir.mkdir(exist_ok=True)
    out_path = out_dir / "trial_237_oos_evidence.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(evidence, f, indent=4)
        
    print(f"\nEvidence saved to {out_path}")


if __name__ == '__main__':
    main()
