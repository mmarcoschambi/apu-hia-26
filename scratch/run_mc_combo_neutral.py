"""
scratch/run_mc_combo_neutral.py
===============================
Monte Carlo + bootstrap de significancia estadistica para combo_neutral
(phase-7 OOS rederivation).

Proposito:
    Validar OOS la evidencia post-fix del combo contra el veredicto ResearchGate
    de PBO 53.34% (artifacts/purged_cv/purged_cv_report_20260730T114632Z.json),
    que fue emitido sobre la evidencia PRE-fix (481 trades, sharpe 0.16, PF 1.098).

Fuente de la equity curve:
    Prioridad 1 (curva guardada): NO disponible.
      - outputs/cost_sensitivity/combo_neutral_costs.json solo guarda metricas por
        escenario (sharpe/pf/trades/return), NO la curva diaria.
      - run3_post_fix.txt es un log de consola, sin curva persistida.
    Prioridad 2 (re-derivar): se corre el backtest del combo con AdvancedVectorBTEngine
    (mismo patron que scratch/mc_bootstrap_combo_neutral.py y scripts/walk_forward_combos.py),
    en los escenarios realistic_ibkr (50bps RT) y realistic_retail (80bps RT).

Metricas:
    - run_monte_carlo_full(equity_series, n_sims, projection_days) de src.analytics.simulation_pack
    - Bootstrap (n_boot, seed 42) del Sharpe anualizado per-position (417 trades aprox).
    - PSR (Probabilistic Sharpe Ratio, Bailey & Lopez de Prado 2014) vs benchmark 0.
    - DSR (Deflated Sharpe Ratio) deflactado por n_trials de la busqueda Optuna
      (s4_main_v2 registro 250 trials totales).
    - pbo_mc_equiv = 1 - DSR (prob. de que el alfa observado sea indistinguible del
      mejor-of-N bajo la hipotesis nula) -> comparable directo al PBO 53.34% de ResearchGate.

No optimiza nada. No escribe en la DB (solo lectura via SELECT en walk_forward_combos).

Uso:
    .venv\\Scripts\\python.exe scratch/run_mc_combo_neutral.py [--n-sims 1000] [--n-boot 2000]
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import norm

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from walk_forward_combos import get_universe_from_db, load_combo_params, build_engine_kwargs
from src.backtest.vectorbt_engine_advanced import AdvancedVectorBTEngine
from src.analytics.simulation_pack import run_monte_carlo_full

COMBO = "combo_neutral"
PERIOD_START, PERIOD_END = "2019-01-01", "2024-12-31"

# Escenarios de costo realistas (iguales a run3_post_fix.txt y cost_sensitivity).
SCENARIOS = {
    "realistic_ibkr": {"fees": 0.0010, "slippage": 0.0015},   # 50bps RT
    "realistic_retail": {"fees": 0.0020, "slippage": 0.0020}, # 80bps RT
}

# s4_main_v2.db registro trials_total=250 en la busqueda Optuna que produjo los params.
DEFAULT_N_TRIALS = 250

OUT_DIR = ROOT / "outputs" / "mc_combo_neutral"
OUT_DIR.mkdir(parents=True, exist_ok=True)


def aggregate_positions(trades_df: pd.DataFrame) -> np.ndarray:
    """Agrupa exits parciales por posicion (symbol, entry_date) -> retorno por posicion."""
    pos = (
        trades_df.groupby(["symbol", "entry_date"], as_index=False)
        .agg(
            total_pnl=("pnl", "sum"),
            total_shares=("shares", "sum"),
            entry_price=("entry_price", "first"),
        )
    )
    capital = pos["total_shares"] * pos["entry_price"]
    return (pos["total_pnl"] / capital).to_numpy(dtype=float)


def bootstrap_sharpe(position_returns: np.ndarray, n_boot: int, seed: int = 42) -> dict:
    """Bootstrap del Sharpe anualizado per-position (media/std * sqrt(252))."""
    rng = np.random.default_rng(seed)
    n = len(position_returns)
    ann = np.sqrt(252)
    boot_sharpes = np.empty(n_boot)
    for i in range(n_boot):
        sample = rng.choice(position_returns, size=n, replace=True)
        mu, sigma = sample.mean(), sample.std(ddof=1)
        boot_sharpes[i] = 0.0 if sigma == 0 else (mu / sigma) * ann
    return {
        "n_positions": n,
        "n_boot": n_boot,
        "seed": seed,
        "mean": float(boot_sharpes.mean()),
        "std": float(boot_sharpes.std()),
        "ci_lower_5": float(np.percentile(boot_sharpes, 5)),
        "ci_upper_95": float(np.percentile(boot_sharpes, 95)),
        "pct_positive": float((boot_sharpes > 0).mean() * 100),
        "prob_alpha_positive": float((boot_sharpes > 0).mean()),
    }


def probabilistic_sharpe_ratio(returns: np.ndarray, sr_benchmark: float) -> float:
    """PSR (Bailey & Lopez de Prado 2014): P[SR_hat > SR_benchmark] ajustado por skew/kurtosis."""
    n = len(returns)
    mu, sigma = returns.mean(), returns.std(ddof=1)
    if sigma == 0:
        return 0.0
    sr_hat = mu / sigma
    skew = float(pd.Series(returns).skew())
    kurt = float(pd.Series(returns).kurt())  # exceso de kurtosis
    var_term = 1.0 - skew * sr_hat + (kurt / 4.0) * sr_hat**2
    var_term = max(var_term, 1e-12)
    z = (sr_hat - sr_benchmark) * np.sqrt(n - 1) / np.sqrt(var_term)
    return float(norm.cdf(z))


def expected_max_sharpe_null(n_trials: int, n_obs: int) -> float:
    """E[max SR_N] bajo nula: sqrt(V) * ((1-g)Phi^-1(1-1/N) + g*Phi^-1(1-1/(N*e)))."""
    euler_gamma = 0.5772156649
    V = 1.0 / (n_obs - 1)
    term = (1.0 - euler_gamma) * norm.ppf(1 - 1.0 / n_trials) + euler_gamma * norm.ppf(
        1 - 1.0 / (n_trials * np.e)
    )
    return float(np.sqrt(V) * term)


def compute_psr_dsr(position_returns: np.ndarray, n_trials: int) -> dict:
    """PSR vs 0 y DSR deflactado por el numero de trials de la busqueda."""
    n = len(position_returns)
    if n < 2:
        return {"error": "insufficient_positions"}
    mu, sigma = position_returns.mean(), position_returns.std(ddof=1)
    sr_hat = 0.0 if sigma == 0 else mu / sigma
    sr_hat_ann = sr_hat * np.sqrt(252)
    expected_max = expected_max_sharpe_null(n_trials, n)
    return {
        "n_trials": n_trials,
        "sharpe_hat_non_annualized": round(sr_hat, 5),
        "sharpe_hat_annualized": round(sr_hat_ann, 4),
        "expected_max_sharpe_null": round(expected_max, 5),
        "psr_vs_zero": round(probabilistic_sharpe_ratio(position_returns, 0.0), 5),
        "dsr": round(probabilistic_sharpe_ratio(position_returns, expected_max), 5),
        "pbo_mc_equiv": round(1 - probabilistic_sharpe_ratio(position_returns, expected_max), 5),
    }


def daily_sharpe_annualized(equity_curve: pd.Series) -> float:
    """Sharpe anualizado de los retornos diarios de la curva (cross-check con engine)."""
    rets = equity_curve.pct_change().dropna().to_numpy(dtype=float)
    if len(rets) < 2 or rets.std(ddof=1) == 0:
        return 0.0
    return float(rets.mean() / rets.std(ddof=1) * np.sqrt(252))


def analyze_scenario(label, cost, universe, params, n_sims, n_boot, n_trials) -> dict:
    """Corre el backtest del combo en un escenario de costo y computa todas las metricas."""
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

        if trades_df is None or len(trades_df) == 0:
            return {"label": label, "error": "empty_trades_df"}

        position_returns = aggregate_positions(trades_df)
        boot = bootstrap_sharpe(position_returns, n_boot=n_boot)
        psr_dsr = compute_psr_dsr(position_returns, n_trials=n_trials)
        mc = run_monte_carlo_full(
            equity_curve, n_sims=n_sims, projection_days=252
        )
        mc_summary = {k: v for k, v in mc.items() if k not in ("mc_paths",)}

        return {
            "label": label,
            "period": {"start": PERIOD_START, "end": PERIOD_END},
            "roundtrip_bps": int(round((cost["fees"] + cost["slippage"]) * 2 * 10_000)),
            "reported": {
                "sharpe_ratio": result.get("sharpe_ratio"),
                "profit_factor": result.get("profit_factor"),
                "total_exits": int(result.get("total_trades", 0)),
                "n_positions": int(len(position_returns)),
            },
            "equity": {
                "initial": round(float(equity_curve.iloc[0]), 2),
                "final": round(float(equity_curve.iloc[-1]), 2),
                "n_days": int(len(equity_curve)),
                "daily_sharpe_ann": round(daily_sharpe_annualized(equity_curve), 4),
            },
            "bootstrap_sharpe": boot,
            "psr_dsr": psr_dsr,
            "monte_carlo_full": mc_summary,
        }
    finally:
        engine.cleanup()


def main():
    parser = argparse.ArgumentParser(description="MC validation combo_neutral")
    parser.add_argument("--n-sims", type=int, default=1000, help="Simulaciones MC")
    parser.add_argument("--n-boot", type=int, default=2000, help="Bootstrap reps")
    parser.add_argument("--n-trials", type=int, default=DEFAULT_N_TRIALS, help="Trials Optuna para DSR")
    args = parser.parse_args()

    universe = get_universe_from_db(PERIOD_START, PERIOD_END)
    params = load_combo_params(COMBO)
    print(f"[combo={COMBO}] universe={len(universe)} n_sims={args.n_sims} "
          f"n_boot={args.n_boot} n_trials={args.n_trials}")

    scenarios = {}
    for label, cost in SCENARIOS.items():
        print(f"\n=== {label} ===")
        scenarios[label] = analyze_scenario(
            label, cost, universe, params, args.n_sims, args.n_boot, args.n_trials
        )
        s = scenarios[label]
        if "error" in s:
            print(f"  ERROR: {s['error']}")
            continue
        print(f"  positions={s['reported']['n_positions']} "
              f"exits={s['reported']['total_exits']} "
              f"sharpe_reported={s['reported']['sharpe_ratio']:.3f} "
              f"pf={s['reported']['profit_factor']:.3f}")
        print(f"  daily_sharpe_ann={s['equity']['daily_sharpe_ann']:.3f}")
        print(f"  boot_sharpe_ann: mean={s['bootstrap_sharpe']['mean']:.3f} "
              f"CI95=({s['bootstrap_sharpe']['ci_lower_5']:.3f}, "
              f"{s['bootstrap_sharpe']['ci_upper_95']:.3f}) "
              f"P(>0)={s['bootstrap_sharpe']['prob_alpha_positive']:.1%}")
        print(f"  PSR={s['psr_dsr']['psr_vs_zero']:.3f} "
              f"DSR={s['psr_dsr']['dsr']:.3f} "
              f"PBO_mc_equiv={s['psr_dsr']['pbo_mc_equiv']:.3f}")
        mc_sum = s["monte_carlo_full"]
        print(f"  MC: median_outcome=${mc_sum['summary']['median_outcome']:,.0f} "
              f"risk_of_loss={mc_sum['summary']['risk_of_loss']:.1%} "
              f"expected_growth={mc_sum['summary']['expected_growth']:.1%}")

    output = {
        "combo": COMBO,
        "generated_at": datetime.now().isoformat(),
        "n_sims": args.n_sims,
        "n_boot": args.n_boot,
        "n_trials": args.n_trials,
        "seed": 42,
        "sources": {
            "equity_curve": "RE-DERIVED running AdvancedVectorBTEngine (no stored curve in "
                            "outputs/cost_sensitivity/combo_neutral_costs.json nor run3_post_fix.txt)",
            "pbo_researchgate_reference": "artifacts/purged_cv/purged_cv_report_20260730T114632Z.json",
        },
        "scenarios": scenarios,
    }

    out_f = OUT_DIR / f"combo_neutral_mc_statistical_validation_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(out_f, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, default=str)
    print(f"\nGuardado: {out_f}")


if __name__ == "__main__":
    main()
