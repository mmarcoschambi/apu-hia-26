import sys
from pathlib import Path
import optuna

PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from src.backtest.vectorbt_engine_advanced import AdvancedVectorBTEngine
from scripts.walk_forward_combos import get_universe_from_db
from scripts.validate_optuna_results_oos import build_engine_kwargs

def test_engine():
    study = optuna.load_study(study_name='pilot', storage='sqlite:///outputs/optuna_s4/pilot_study.db')
    trial = study.trials[-1]
    
    universe = get_universe_from_db("2019-01-01", "2024-12-31", 10)
    
    kwargs = build_engine_kwargs(trial.params)
    engine = AdvancedVectorBTEngine(
        universe=universe,
        start_date="2019-01-01",
        end_date="2023-12-31",
        initial_capital=100_000,
        **kwargs
    )
    result = engine.run_backtest()
    print("KEYS IN RESULT:", result.keys())
    
    print("total_return:", result.get("total_return"))
    print("annualized_return:", result.get("annualized_return"))
    print("calmar_ratio:", result.get("calmar_ratio"))

if __name__ == "__main__":
    test_engine()
