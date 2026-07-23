"""
src/analytics/paper_analytics_engine.py
=========================================
Motor de analytics unificado para paper/live/backtest.

Calcula métricas diarias de position sizing, riesgo, calidad, y simulación.
El output es un schema canónico `analytics_YYYY-MM-DD.json`.

API principal:
    compute_daily_analytics(date, trades, equity, market_ctx, actual_snapshot) -> dict
"""

import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

# === CONSTANTS ===

DEFAULT_CAPITAL = 100_000  # default si no hay snapshot
MIN_TRADE_PCT = -0.50  # -50% max loss per trade
MAX_TRADE_PCT = 1.00  # 100% max gain per trade
MC_SIMULATIONS = 1000  # número de simulaciones para MVP


# === REGIME CLASSIFICATION ===


def classify_regime_bin(market_score: float) -> str:
    """Clasifica market_score en bins."""
    if market_score is None or pd.isna(market_score):
        return "UNKNOWN"
    if market_score < 25:
        return "BEAR"
    elif market_score < 50:
        return "NEUTRAL_WEAK"
    elif market_score <= 80:
        return "FAVORABLE"
    else:
        return "STRONG"


def classify_kelly_tier(
    market_score: float, regime_quality: str = "OK"
) -> Tuple[str, float]:
    """
    Calcula Kelly tier y fracción.

    - 50-80 + calidad OK: Half Kelly (0.5)
    - Fuera de rango o calidad LOW: Quarter Kelly (0.25)
    """
    if market_score is None or pd.isna(market_score):
        return "UNKNOWN", 0.25

    if 50 <= market_score <= 80 and regime_quality == "OK":
        return "HALF", 0.5
    else:
        return "QUARTER", 0.25


# === POSITION SIZING ===


def compute_position_sizing(
    capital: float,
    kelly_tier: str,
    kelly_fraction: float,
    risk_per_trade_pct: float = 0.02,
    max_positions: int = 10,
    max_deployed_pct: float = 0.65,
) -> Dict[str, Any]:
    """
    Calcula position sizing basado en Kelly y límites de riesgo.
    """
    per_position_risk = capital * risk_per_trade_pct * kelly_fraction
    positions_recommended = min(
        max_positions, int(capital * max_deployed_pct / (per_position_risk * 2))
    )
    deployed = per_position_risk * positions_recommended
    deployed_pct = deployed / capital

    return {
        "kelly_tier": kelly_tier,
        "kelly_fraction": kelly_fraction,
        "per_position_risk_usd": round(per_position_risk, 2),
        "per_position_max_usd": round(per_position_risk * 2, 2),  # max loss 2R
        "positions_recommended": positions_recommended,
        "deployed_max_usd": round(deployed, 2),
        "deployed_pct": round(deployed_pct, 3),
        "cash_reserve_usd": round(capital - deployed, 2),
    }


# === RISK CHECKS ===


def compute_ruin_probabilities(
    equity_series: pd.Series,
    n_sims: int = MC_SIMULATIONS,
) -> Tuple[float, float]:
    """
    Estima probabilidad de soft ruin (>=30% DD) y hard ruin (>=50% DD).
    Usa bootstrap resampling del equity curve.
    """
    if equity_series is None or len(equity_series) < 10:
        return 0.0, 0.0

    equity_arr = equity_series.values
    returns = np.diff(equity_arr) / equity_arr[:-1]
    returns = returns[~np.isnan(returns) & ~np.isinf(returns)]

    if len(returns) < 5:
        return 0.0, 0.0

    sim_ends = []
    for _ in range(n_sims):
        sim_returns = np.random.choice(returns, size=len(returns), replace=True)
        sim_path = np.concatenate(
            [[equity_arr[0]], equity_arr[0] * np.cumprod(1 + sim_returns)]
        )
        final_dd = (sim_path.max() - sim_path.min()) / sim_path.max()
        sim_ends.append(final_dd)

    soft_ruin = sum(1 for dd in sim_ends if dd >= 0.30) / n_sims
    hard_ruin = sum(1 for dd in sim_ends if dd >= 0.50) / n_sims

    return round(soft_ruin, 4), round(hard_ruin, 4)


def compute_risk_checks(
    capital: float,
    equity_series: pd.Series,
    market_score: float,
    deployed_pct: float,
    cash_reserve_usd: float,
) -> Dict[str, Any]:
    """
    Calcula risk checks: cash reserve, ruin probabilities.
    """
    cash_reserve_pct = cash_reserve_usd / capital if capital > 0 else 0.0

    soft_ruin, hard_ruin = compute_ruin_probabilities(equity_series)

    # Cash floor based on market score
    if market_score is not None and 50 <= market_score <= 80:
        cash_floor = 0.10  # 10% mínimo
    else:
        cash_floor = 0.20  # 20% mínimo en régimen desfavorable

    # MDD floor (estimate from equity series)
    mdd_floor = 0.15
    cvar_floor = 0.10

    cash_reserve_pct = max(cash_reserve_pct, cash_floor, mdd_floor, cvar_floor)
    cash_reserve_pct = min(cash_reserve_pct, 1.0)

    return {
        "cash_reserve_pct": round(cash_reserve_pct, 3),
        "cash_target_usd": round(capital * cash_reserve_pct, 2),
        "soft_ruin_30": soft_ruin,
        "hard_ruin_50": hard_ruin,
    }


# === TRADE STATS ===


def compute_trade_stats(trades: List[Dict]) -> Dict[str, Any]:
    """
    Calcula estadísticas de trades: CAGR, WR, R/R, avg win/loss.

    Nota: CAGR se calcula aquí desde R-múltiples (para backward compatibility),
    pero en compute_overall_quality se recalcula desde equity_curve si hay suficientes datos.
    """
    if not trades:
        return {
            "trades": 0,
            "cagr_r": 0.0,
            "win_rate": 0.0,
            "rr": 0.0,
            "avg_win": 0.0,
            "avg_loss": 0.0,
            "gross_profit": 0.0,
            "gross_loss": 0.0,
        }

    wins = [t.get("pnl_r", 0) for t in trades if t.get("pnl_r", 0) > 0]
    losses = [t.get("pnl_r", 0) for t in trades if t.get("pnl_r", 0) < 0]

    n_wins = len(wins)
    n_losses = len(losses)
    n_trades = n_wins + n_losses

    win_rate = n_wins / n_trades if n_trades > 0 else 0.0

    avg_win = np.mean(wins) if wins else 0.0
    avg_loss = abs(np.mean(losses)) if losses else 0.0

    rr = avg_win / avg_loss if avg_loss > 0 else 0.0

    gross_profit = sum(wins)
    gross_loss = abs(sum(losses))

    # CAGR from R-múltiples (legacy, para compatibilidad)
    total_r = sum(t.get("pnl_r", 0) for t in trades)
    years = max(1, len(trades) / 252)
    cagr_r = (total_r / years) if years > 0 else 0.0

    return {
        "trades": n_trades,
        "cagr_r": round(cagr_r, 4),
        "win_rate": round(win_rate * 100, 2),
        "rr": round(rr, 2),
        "avg_win": round(avg_win, 3),
        "avg_loss": round(avg_loss, 3),
        "gross_profit": round(gross_profit, 3),
        "gross_loss": round(gross_loss, 3),
    }


# === OVERALL QUALITY ===


def compute_overall_quality(
    trades: List[Dict],
    equity_series: pd.Series,
    capital: float,
) -> Dict[str, Any]:
    """
    Calcula métricas de calidad: expectancy, calmar, sharpe, PF, MDD 90d.

    Uses equity_curve for CAGR calculation (more accurate than R-múltiples).
    If insufficient equity history, uses R-based CAGR and marks quality flags.
    """
    trade_stats = compute_trade_stats(trades)

    # Expectancy
    win_rate_dec = trade_stats["win_rate"] / 100
    rr = trade_stats["rr"]
    expectancy = (win_rate_dec * trade_stats["avg_win"]) - (
        (1 - win_rate_dec) * trade_stats["avg_loss"]
    )

    # Profit Factor
    pf = (
        trade_stats["gross_profit"] / trade_stats["gross_loss"]
        if trade_stats["gross_loss"] > 0
        else 0.0
    )

    # Max Drawdown 90d (from equity series)
    max_dd_90d = 0.0
    has_equity = equity_series is not None and len(equity_series) >= 2

    if has_equity:
        window = min(90, len(equity_series))
        rolling_max = equity_series.rolling(window, min_periods=1).max()
        dd = (equity_series - rolling_max) / rolling_max
        max_dd_90d = abs(dd.min())

    # CAGR from equity (preferred) vs R-based (fallback)
    cagr_pct = None
    cagr_source = None

    if has_equity and len(equity_series) >= 30:
        # Calculate CAGR from equity curve
        equity_start = equity_series.iloc[0]
        equity_end = equity_series.iloc[-1]
        n_days = len(equity_series)

        if equity_start > 0 and equity_end > 0:
            cagr_pct = (equity_end / equity_start) ** (252 / n_days) - 1
            cagr_source = "equity_curve"
    else:
        # Fallback to R-based CAGR
        cagr_pct = trade_stats["cagr_r"] / capital if capital > 0 else 0.0
        cagr_source = "r_multiples"

    # Calmar: CAGR% / abs(MDD)
    # If using R-based CAGR, convert to % for consistency
    if cagr_source == "r_multiples":
        # R-based CAGR is already in R units, convert to approximate % by multiplying by avg position
        # This is approximate; prefer equity-based calculation when available
        cagr_pct_for_calmar = cagr_pct * 100 if cagr_pct is not None else 0.0
    else:
        cagr_pct_for_calmar = cagr_pct if cagr_pct is not None else 0.0

    calmar = cagr_pct_for_calmar / abs(max_dd_90d) if max_dd_90d > 0 else 0.0

    # Sharpe (simplified: annualized return / std of returns)
    sharpe = 0.0
    if has_equity:
        rets = equity_series.pct_change().dropna()
        if len(rets) > 5:
            mean_ret = rets.mean() * 252
            std_ret = rets.std() * np.sqrt(252)
            sharpe = mean_ret / std_ret if std_ret > 0 else 0.0

    return {
        "expectancy": round(expectancy, 4),
        "calmar": round(calmar, 2),
        "sharpe": round(sharpe, 2),
        "profit_factor": round(pf, 2),
        "max_drawdown_90d": round(max_dd_90d * 100, 2),
        "cagr_pct": round(cagr_pct * 100, 2) if cagr_pct is not None else None,
        "cagr_source": cagr_source,
    }


# === SIMULATION ===


def run_mc_summary(
    equity_series: pd.Series,
    n_sims: int = MC_SIMULATIONS,
    initial_capital: float = 100_000,
) -> Dict[str, Any]:
    """
    Monte Carlo MVP: genera 1000 paths y calcula expected growth, median outcome, risk of loss.
    No genera charts (es MVP).

    Note: With <30 days of equity history, results are not statistically reliable.
    Caller should check confidence_low flag in returned dict.
    """
    if equity_series is None or len(equity_series) < 10:
        return {
            "expected_growth_1y": 0.0,
            "median_outcome_1y": initial_capital,
            "risk_of_loss_1y": 0.0,
            "n_sims": n_sims,
            "confidence_5": 0.0,
            "confidence_95": 0.0,
        }

    equity_arr = equity_series.values
    returns = np.diff(equity_arr) / equity_arr[:-1]
    returns = returns[~np.isnan(returns) & ~np.isinf(returns)]

    if len(returns) < 5:
        return {
            "expected_growth_1y": 0.0,
            "median_outcome_1y": initial_capital,
            "risk_of_loss_1y": 0.0,
            "n_sims": n_sims,
            "confidence_5": initial_capital,
            "confidence_95": initial_capital,
        }

    # Project 252 days
    sim_finals = []
    for _ in range(n_sims):
        sim_returns = np.random.choice(returns, size=252, replace=True)
        final_value = equity_arr[-1] * np.prod(1 + sim_returns)
        sim_finals.append(final_value)

    sim_finals = np.array(sim_finals)

    median_outcome = np.median(sim_finals)
    expected_growth = (median_outcome - initial_capital) / initial_capital
    risk_of_loss = sum(1 for v in sim_finals if v < initial_capital) / n_sims

    p5 = np.percentile(sim_finals, 5)
    p95 = np.percentile(sim_finals, 95)

    return {
        "expected_growth_1y": round(expected_growth, 4),
        "median_outcome_1y": round(median_outcome, 2),
        "risk_of_loss_1y": round(risk_of_loss, 4),
        "n_sims": n_sims,
        "confidence_5": round(p5, 2),
        "confidence_95": round(p95, 2),
    }


# === SYSTEM VS ACTUAL ===


def compute_system_edge(
    system_value: float,
    actual_value: Optional[float] = None,
) -> Dict[str, Any]:
    """
    Calcula system edge vs actual portfolio.
    """
    if actual_value is None:
        return {
            "system_value": round(system_value, 2),
            "actual_value": None,
            "system_edge": None,
            "system_return": None,
            "actual_return": None,
            "has_actual": False,
        }

    actual_return = (
        (actual_value - system_value) / system_value if system_value > 0 else 0.0
    )
    system_return = 0.0  # relative to baseline

    return {
        "system_value": round(system_value, 2),
        "actual_value": round(actual_value, 2),
        "system_edge": round(actual_return, 4),
        "system_return": 0.0,
        "actual_return": round(actual_return * 100, 2),
        "has_actual": True,
    }


# === MAIN API ===


def compute_daily_analytics(
    date: str,
    trades: List[Dict],
    equity_curve: Optional[pd.Series],
    market_score: Optional[float],
    regime_quality: str = "OK",
    actual_snapshot: Optional[Dict] = None,
    initial_capital: float = DEFAULT_CAPITAL,
) -> Dict[str, Any]:
    """
    Computa analytics completo para un día.

    Args:
        date: Fecha (YYYY-MM-DD)
        trades: Lista de trades del día (cada trade tiene pnl_r, etc.)
        equity_curve: Serie temporal de equity (puede ser None)
        market_score: Score 0-100 (None = desconocido)
        regime_quality: "OK" | "LOW"
        actual_snapshot: Dict con {"date": str, "equity": float}
        initial_capital: Capital inicial (default 100k)

    Returns:
        Dict con schema canónico de analytics
    """
    logger.info(f"[U+1F4CA] Computing analytics for {date}...")

    # Capital actual (de último snapshot si existe)
    capital = initial_capital
    if actual_snapshot:
        capital = actual_snapshot.get("equity", initial_capital)

    # Kelly tier
    kelly_tier, kelly_frac = classify_kelly_tier(market_score, regime_quality)

    # Position sizing
    pos_sizing = compute_position_sizing(
        capital=capital,
        kelly_tier=kelly_tier,
        kelly_fraction=kelly_frac,
    )

    # Risk checks
    risk_checks = compute_risk_checks(
        capital=capital,
        equity_series=equity_curve,
        market_score=market_score,
        deployed_pct=pos_sizing["deployed_pct"],
        cash_reserve_usd=pos_sizing["cash_reserve_usd"],
    )

    # Trade stats
    trade_stats = compute_trade_stats(trades)

    # Overall quality
    overall_quality = compute_overall_quality(trades, equity_curve, capital)

    # Simulation (MVP)
    simulation = run_mc_summary(
        equity_curve, n_sims=MC_SIMULATIONS, initial_capital=capital
    )

    # Market score y regime bin (preserve original for flag check)
    _original_market_score = market_score
    market_score = market_score if market_score is not None else 0.0
    regime_bin = classify_regime_bin(market_score)

    # System vs actual (use cagr from overall_quality for consistency)
    system_value = capital * (1 + (overall_quality.get("cagr_pct", 0) or 0) / 100)
    actual_value = actual_snapshot.get("equity") if actual_snapshot else None
    system_edge = compute_system_edge(system_value, actual_value)

    # Data quality flags
    quality_flags = []
    if equity_curve is None or len(equity_curve) < 10:
        quality_flags.append("NO_EQUITY_HISTORY")
    if _original_market_score is None:
        quality_flags.append("NO_MARKET_SCORE")
    if actual_snapshot is None:
        quality_flags.append("NO_ACTUAL_SNAPSHOT")
    if len(trades) == 0:
        quality_flags.append("NO_TRADES_TODAY")

    # Gap 3: Flags for insufficient data for statistical measures
    if equity_curve is not None and len(equity_curve) < 30:
        quality_flags.append("INSUFFICIENT_EQUITY_FOR_RUIN")
        quality_flags.append("INSUFFICIENT_EQUITY_FOR_MC")
        # Mark MC as low confidence
        simulation["confidence_low"] = True
    else:
        simulation["confidence_low"] = False

    # Build final payload
    payload = {
        "meta": {
            "date": date,
            "generated_at": datetime.now().isoformat(),
            "version": "1.0",
            "data_quality_flags": quality_flags,
        },
        "position_sizing": pos_sizing,
        "risk_checks": risk_checks,
        "trade_stats": trade_stats,
        "overall_quality": overall_quality,
        "simulation": simulation,
        "market": {
            "market_score": round(market_score, 1),
            "regime_bin": regime_bin,
        },
        "system_vs_actual": system_edge,
    }

    logger.info(
        f"  [OK] Analytics computed: {len(trades)} trades, WR={trade_stats['win_rate']}%, PF={overall_quality['profit_factor']}"
    )

    return payload


# === CLI TEST ===

if __name__ == "__main__":
    # Test with empty data
    print("Testing analytics engine with dummy data...")

    test_trades = [
        {"ticker": "AAPL", "combo": "test", "pnl_r": 1.5},
        {"ticker": "NVDA", "combo": "test", "pnl_r": -0.8},
        {"ticker": "TSLA", "combo": "test", "pnl_r": 2.0},
    ]

    test_equity = pd.Series([100000, 102000, 101500, 103000, 105000])

    result = compute_daily_analytics(
        date="2026-04-09",
        trades=test_trades,
        equity_curve=test_equity,
        market_score=65.0,
        regime_quality="OK",
    )

    print(json.dumps(result, indent=2))
