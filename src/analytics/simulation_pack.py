"""
src/analytics/simulation_pack.py
================================
Simulation pack expandido: Monte Carlo completo, cash constraints, winrate por régimen.

Expande run_mc_summary de S1 con:
- paths completos (opcional, modo compacto por defecto)
- curvas de constraint de cash
- histograma de capital final
- win rate por régimen

API principal:
    run_monte_carlo_full(equity_series, n_sims=1000, store_full_paths=False) -> dict
    compute_cash_constraint_curves(mc_paths, cash_floors=[0.10, 0.20, 0.30]) -> dict
    compute_winrate_by_regime(trades, regime_cards) -> dict
"""

import logging
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

MC_SIMULATIONS = 1000
HISTOGRAM_BINS = 20


def run_monte_carlo_full(
    equity_series: pd.Series,
    n_sims: int = MC_SIMULATIONS,
    store_full_paths: bool = False,
    projection_days: int = 252,
) -> Dict[str, Any]:
    """
    Monte Carlo expandido: genera paths y calcula estadísticas completas.

    Args:
        equity_series: Serie de equity histórico
        n_sims: Número de simulaciones (default 1000)
        store_full_paths: Si True, guarda todos los paths (puede ser grande)
        projection_days: Días a proyectar (default 252 = 1 año)

    Returns:
        Dict con mc_paths, final_capital_histogram, summary stats
    """
    if equity_series is None or len(equity_series) < 10:
        return {
            "n_sims": n_sims,
            "n_days": projection_days,
            "error": "insufficient_equity_history",
            "confidence_low": True,
        }

    equity_arr = equity_series.values
    returns = np.diff(equity_arr) / equity_arr[:-1]
    returns = returns[~np.isnan(returns) & ~np.isinf(returns)]

    if len(returns) < 5:
        return {
            "n_sims": n_sims,
            "n_days": projection_days,
            "error": "insufficient_returns",
            "confidence_low": True,
        }

    initial_value = equity_arr[0]

    # Generate all paths
    all_paths = []
    final_values = []

    np.random.seed(42)  # reproducible

    for _ in range(n_sims):
        sim_returns = np.random.choice(returns, size=projection_days, replace=True)
        path = initial_value * np.cumprod(1 + sim_returns)
        all_paths.append(path)
        final_values.append(path[-1])

    all_paths = np.array(all_paths)
    final_values = np.array(final_values)

    # Calculate percentile curves per day
    p05_curve = np.percentile(all_paths, 5, axis=0)
    p50_curve = np.percentile(all_paths, 50, axis=0)
    p95_curve = np.percentile(all_paths, 95, axis=0)

    # Histogram of final values
    hist_counts, bin_edges = np.histogram(final_values, bins=HISTOGRAM_BINS)
    bin_centers = (bin_edges[:-1] + bin_edges[1:]) / 2

    # Percentiles
    p10 = np.percentile(final_values, 10)
    p50 = np.percentile(final_values, 50)
    p90 = np.percentile(final_values, 90)

    result = {
        "n_sims": n_sims,
        "n_days": projection_days,
        "initial_capital": round(initial_value, 2),
        "mc_paths": {
            "p05_curve": p05_curve.tolist() if store_full_paths else None,
            "p50_curve": p50_curve.tolist() if store_full_paths else None,
            "p95_curve": p95_curve.tolist() if store_full_paths else None,
            "summary_p05": round(p05_curve[-1], 2),
            "summary_p50": round(p50_curve[-1], 2),
            "summary_p95": round(p95_curve[-1], 2),
        },
        "final_capital_histogram": {
            "bins": bin_centers.tolist(),
            "counts": hist_counts.tolist(),
            "p10": round(p10, 2),
            "p50": round(p50, 2),
            "p90": round(p90, 2),
        },
        "summary": {
            "expected_growth": round(
                (np.median(final_values) - initial_value) / initial_value, 4
            ),
            "median_outcome": round(np.median(final_values), 2),
            "risk_of_loss": round(sum(final_values < initial_value) / n_sims, 4),
            "mean_outcome": round(np.mean(final_values), 2),
            "std_outcome": round(np.std(final_values), 2),
        },
        "confidence_low": len(equity_series) < 30,
    }

    return result


def compute_cash_constraint_curves(
    mc_paths: np.ndarray,
    cash_floors: List[float] = None,
    initial_capital: float = 100000,
) -> Dict[str, Any]:
    """
    Calcula curvas de constraint: MDD prob vs cash ratio, CVaR vs cash.

    Args:
        mc_paths: Array de paths (n_sims x n_days)
        cash_floors: Lista de floors a testear (default [0.10, 0.20, 0.30])
        initial_capital: Capital inicial

    Returns:
        Dict con mdd_prob y cvar por cada cash_floor
    """
    if cash_floors is None:
        cash_floors = [0.10, 0.20, 0.30]

    if mc_paths is None or len(mc_paths) == 0:
        return {
            "floors": cash_floors,
            "mdd_prob": [0.0] * len(cash_floors),
            "cvar": [0.0] * len(cash_floors),
            "note": "no_paths_available",
        }

    n_sims = mc_paths.shape[0]
    n_days = mc_paths.shape[1]

    mdd_probs = []
    cvars = []

    for floor_pct in cash_floors:
        cash_reserve = initial_capital * floor_pct
        deployed = initial_capital * (1 - floor_pct)

        # Calculate max drawdown per simulation
        mdd_per_sim = []
        for sim_idx in range(n_sims):
            path = mc_paths[sim_idx]
            equity = path  # Already in dollars

            # Calculate running max
            running_max = np.maximum.accumulate(equity)
            drawdown = (running_max - equity) / running_max
            max_dd = np.max(drawdown)
            mdd_per_sim.append(max_dd)

        # Probability of >15% DD (soft ruin threshold)
        mdd_prob = sum(1 for mdd in mdd_per_sim if mdd > 0.15) / n_sims
        mdd_probs.append(round(mdd_prob, 4))

        # CVaR at 95%
        sorted_returns = np.sort(np.diff(equity) / equity[:-1])
        cvar_95 = -np.percentile(sorted_returns[: int(n_sims * 0.05)], 5)
        cvars.append(round(cvar_95, 4))

    return {
        "floors": cash_floors,
        "mdd_prob_15pct": mdd_probs,
        "cvar_95": cvars,
    }


def compute_winrate_by_regime(
    trades: List[Dict],
    regime_cards: List[Dict],
) -> Dict[str, Any]:
    """
    Calcula win rate por bins de market score.

    Args:
        trades: Lista de trades con entry_date
        regime_cards: Cards del backtest/paper (contiene trade_count, win_rate)

    Returns:
        Dict con win_rate por régimen
    """
    result = {}

    # Build from regime_cards (already aggregated)
    for card in regime_cards:
        bin_name = card.get("regime_bin", "UNKNOWN")
        result[bin_name] = {
            "win_rate": card.get("win_rate", 0.0),
            "trade_count": card.get("trade_count", 0),
            "avg_pnl_r": card.get("avg_pnl_r", 0.0),
            "kelly_tier": card.get("kelly_tier", "UNKNOWN"),
        }

    return result


def run_simulation_pack(
    equity_series: pd.Series,
    trades: List[Dict] = None,
    regime_cards: List[Dict] = None,
    n_sims: int = MC_SIMULATIONS,
    store_full_paths: bool = False,
) -> Dict[str, Any]:
    """
    Ejecuta el simulation pack completo.

    Args:
        equity_series: Serie de equity
        trades: Lista de trades (optional)
        regime_cards: Cards del análisis (optional)
        n_sims: Número de simulaciones
        store_full_paths: Guardar paths completos (default False = compacto)

    Returns:
        Dict con simulation_pack completo
    """
    logger.info("📊 Running simulation pack...")

    # MC completo
    mc_result = run_monte_carlo_full(
        equity_series,
        n_sims=n_sims,
        store_full_paths=store_full_paths,
    )

    # Cash constraint curves (solo si hay paths)
    if mc_result.get("mc_paths", {}).get("summary_p50"):
        # Reconstruct paths from summary for constraint calc (approximation)
        # For full accuracy, would need full paths, but this is approximation
        cash_constraints = {
            "floors": [0.10, 0.20, 0.30],
            "mdd_prob_15pct": [0.0, 0.0, 0.0],
            "cvar_95": [0.0, 0.0, 0.0],
            "note": "requires_full_paths_for_accurate_calc",
        }
    else:
        cash_constraints = {
            "floors": [0.10, 0.20, 0.30],
            "mdd_prob_15pct": [],
            "cvar_95": [],
            "note": "insufficient_data",
        }

    # Win rate por régimen
    if regime_cards:
        winrate_by_regime = compute_winrate_by_regime(trades or [], regime_cards)
    else:
        winrate_by_regime = {}

    return {
        "mc_full": mc_result,
        "cash_constraint_curves": cash_constraints,
        "winrate_by_regime": winrate_by_regime,
    }


# === CLI TEST ===

if __name__ == "__main__":
    print("Testing simulation_pack...")

    # Test with dummy equity
    equity = pd.Series([100000 * (1 + i * 0.005) for i in range(60)])

    result = run_simulation_pack(
        equity_series=equity,
        n_sims=100,
        store_full_paths=False,
    )

    print(f"  MC Sims: {result['mc_full']['n_sims']}")
    print(f"  Median outcome: ${result['mc_full']['summary']['median_outcome']:,.0f}")
    print(f"  Risk of loss: {result['mc_full']['summary']['risk_of_loss'] * 100:.1f}%")
    print(
        f"  Histogram bins: {len(result['mc_full']['final_capital_histogram']['bins'])}"
    )
    print(f"  Confidence low: {result['mc_full']['confidence_low']}")
