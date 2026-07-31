"""
scratch/mc_bootstrap_combo_neutral.py
Bootstrap de Sharpe (per-trade) + Monte Carlo sobre combo_neutral,
en los escenarios de costo realistic_ibkr (50bps) y realistic_retail (80bps).
No optimiza nada, no toca src/ salvo por import de lectura.
"""
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from walk_forward_combos import get_universe_from_db, load_combo_params, build_engine_kwargs
from src.backtest.vectorbt_engine_advanced import AdvancedVectorBTEngine
from src.analytics.simulation_pack import run_monte_carlo_full

COMBO = "combo_neutral"
PERIOD_START, PERIOD_END = "2019-01-01", "2024-12-31"

SCENARIOS = {
    "realistic_ibkr": {"fees": 0.0010, "slippage": 0.0015},   # 50bps RT
    "realistic_retail": {"fees": 0.0020, "slippage": 0.0020}, # 80bps RT
}

OUT_DIR = ROOT / "outputs" / "mc_bootstrap"
OUT_DIR.mkdir(parents=True, exist_ok=True)


def bootstrap_trade_sharpe(trade_returns: np.ndarray, n_boot: int = 2000, seed: int = 42) -> dict:
    """Bootstrap sobre retornos por-trade (no sobre Sharpe agregado de un solo run)."""
    if len(trade_returns) < 10:
        return {"error": "insufficient_trades", "n": len(trade_returns)}
    rng = np.random.default_rng(seed)
    n = len(trade_returns)
    boot_sharpes = []
    for _ in range(n_boot):
        sample = rng.choice(trade_returns, size=n, replace=True)
        mu, sigma = sample.mean(), sample.std(ddof=1)
        boot_sharpes.append(0.0 if sigma == 0 else (mu / sigma) * np.sqrt(252))
    arr = np.array(boot_sharpes)
    return {
        "n_trades": n,
        "n_boot": n_boot,
        "mean": float(arr.mean()),
        "std": float(arr.std()),
        "ci_lower_5": float(np.percentile(arr, 5)),
        "ci_upper_95": float(np.percentile(arr, 95)),
        "pct_positive": float((arr > 0).mean() * 100),
    }


def main():
    universe = get_universe_from_db(PERIOD_START, PERIOD_END)
    params = load_combo_params(COMBO)

    results = {}
    for label, cost in SCENARIOS.items():
        kwargs = build_engine_kwargs(COMBO, params)
        kwargs["fees"] = cost["fees"]
        kwargs["slippage"] = cost["slippage"]

        engine = AdvancedVectorBTEngine(
            universe=universe,
            start_date=PERIOD_START,
            end_date=PERIOD_END,
            initial_capital=100_000,
            **kwargs,
        )
        try:
            result = engine.run_backtest()
            trades_df = result.get("trades_df")
            equity_curve = result.get("equity_curve")

            print(f"[DEBUG {label}] len(trades_df)={len(trades_df) if trades_df is not None else 0} sharpe_from_result={result.get('sharpe_ratio')}")

            if trades_df is not None and len(trades_df) > 0:
                if "return_pct" in trades_df.columns:
                    trade_returns = trades_df["return_pct"].to_numpy()
                elif "pnl_pct" in trades_df.columns:
                    trade_returns = trades_df["pnl_pct"].to_numpy()
                elif "pnl" in trades_df.columns:
                    trade_returns = trades_df["pnl"].to_numpy()
                else:
                    trade_returns = np.array([])
            else:
                trade_returns = np.array([])

            boot = bootstrap_trade_sharpe(trade_returns)
            mc = run_monte_carlo_full(equity_curve, n_sims=1000, projection_days=252)

            results[label] = {
                "reported_sharpe": result.get("sharpe_ratio"),
                "reported_pf": result.get("profit_factor"),
                "bootstrap": boot,
                "monte_carlo_summary": {
                    k: v for k, v in mc.items() if k not in ("mc_paths",)
                },
            }
            print(f"[{label}] sharpe={result.get('sharpe_ratio'):.3f} "
                  f"boot_ci=({boot.get('ci_lower_5'):.3f}, {boot.get('ci_upper_95'):.3f}) "
                  f"pct_positive={boot.get('pct_positive'):.1f}%")
        finally:
            engine.cleanup()

    out_f = OUT_DIR / f"{COMBO}_bootstrap_mc.json"
    with open(out_f, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, default=str)
    print(f"Guardado: {out_f}")


if __name__ == "__main__":
    main()
