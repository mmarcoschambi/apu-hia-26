"""
Robustness Objective Functions
==============================

Standardized objective functions for strategy optimization that prioritize
robustness over raw performance.

Key metrics:
- Bootstrap percentiles (p5, p10, p50) of OOS returns
- Drawdown metrics (depth, duration, recovery)
- Probability of loss
- Stability of runner contribution
- Risk-adjusted returns (Sortino, Calmar)

These functions should be used instead of simple Sharpe maximization
to ensure strategies perform robustly in production.

Usage:
    from src.validation.robustness_metrics import (
        robust_objective_function,
        calculate_drawdown_robustness,
        calculate_sortino_ratio,
        calculate_calmar_ratio,
        RobustObjectiveConfig
    )

    # Configure objective
    config = RobustObjectiveConfig(
        p5_weight=1.0,
        p10_weight=0.5,
        sharpe_weight=0.3,
        max_dd_penalty=2.0
    )

    # Use in optimization
    def objective(trial):
        params = suggest_params(trial)
        backtest_result = engine.run_backtest(**params)

        return robust_objective_function(
            backtest_result,
            config=config
        )
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from scipy import stats
import logging

logger = logging.getLogger(__name__)


@dataclass
class RobustObjectiveConfig:
    """Configuration for robust objective functions."""

    # Weights for different metrics
    p5_weight: float = 1.0  # Weight for 5th percentile return
    p10_weight: float = 0.5  # Weight for 10th percentile return
    p50_weight: float = 0.2  # Weight for median return
    sharpe_weight: float = 0.3  # Weight for Sharpe ratio
    sortino_weight: float = 0.3  # Weight for Sortino ratio
    calmar_weight: float = 0.2  # Weight for Calmar ratio

    # Penalty weights
    max_dd_penalty: float = 2.0  # Multiplier for drawdown penalty
    dd_duration_penalty: float = 1.0  # Multiplier for DD duration penalty
    loss_prob_penalty: float = 1.5  # Multiplier for loss probability penalty

    # Thresholds
    min_p5_acceptable: float = -5.0  # Min acceptable p5 return
    min_p10_acceptable: float = 0.0  # Min acceptable p10 return
    max_dd_acceptable: float = 25.0  # Max acceptable drawdown
    max_dd_duration_acceptable: int = 60  # Max acceptable DD duration

    # Runner stability
    runner_stability_weight: float = 0.1  # Weight for runner contribution stability

    # Bootstrap normalization scale.
    # Bootstrap percentiles are in annualized % (range ~-50 to +100).
    # Without normalization they dominate the score (p5*1.0 can be ~30 points)
    # while Sharpe (0-3)*0.3 = ~0.9 is decorative.
    # Dividing by this scale puts bootstrap on the same order as risk-adjusted ratios.
    # 20% annualized = "good" → contributes 1.0 before weighting.
    bootstrap_normalization_scale: float = 20.0


class RobustnessMetrics:
    """Collection of robustness-focused metrics."""

    @staticmethod
    def calculate_bootstrap_percentiles(
        returns: np.ndarray, n_bootstrap: int = 1000, random_state: int = 42
    ) -> Dict[str, float]:
        """
        Calculate bootstrap percentiles of returns.

        Returns:
            Dict with p5, p10, p50, p90, mean, std
        """
        np.random.seed(random_state)
        returns = np.array(returns)
        n = len(returns)

        if n == 0:
            return {
                "p5": -100.0,
                "p10": -100.0,
                "p50": 0.0,
                "p90": 0.0,
                "mean": 0.0,
                "std": 0.0,
            }

        bootstrapped = []
        for _ in range(n_bootstrap):
            sample = np.random.choice(returns, size=n, replace=True)
            cumulative = np.prod(1 + sample) - 1
            annualized = (1 + cumulative) ** (252 / n) - 1
            bootstrapped.append(annualized * 100)

        bootstrapped = np.array(bootstrapped)

        return {
            "p5": float(np.percentile(bootstrapped, 5)),
            "p10": float(np.percentile(bootstrapped, 10)),
            "p50": float(np.percentile(bootstrapped, 50)),
            "p90": float(np.percentile(bootstrapped, 90)),
            "mean": float(np.mean(bootstrapped)),
            "std": float(np.std(bootstrapped)),
        }

    @staticmethod
    def calculate_drawdown_metrics(equity: pd.Series) -> Dict[str, float]:
        """
        Calculate comprehensive drawdown metrics.

        Returns:
            Dict with max_dd_pct, avg_dd_pct, dd_duration, recovery_time
        """
        if len(equity) == 0:
            return {
                "max_dd_pct": 100.0,
                "avg_dd_pct": 100.0,
                "dd_duration": 999,
                "recovery_time": 999,
                "dd_frequency": 1.0,
            }

        cummax = equity.cummax()
        drawdown = (equity - cummax) / cummax

        max_dd = abs(drawdown.min()) * 100
        avg_dd = abs(drawdown.mean()) * 100

        # Calculate drawdown durations
        in_dd = drawdown < 0
        durations = []
        current_duration = 0

        for is_dd in in_dd:
            if is_dd:
                current_duration += 1
            else:
                if current_duration > 0:
                    durations.append(current_duration)
                current_duration = 0

        if current_duration > 0:
            durations.append(current_duration)

        max_duration = max(durations) if durations else 0
        avg_duration = np.mean(durations) if durations else 0

        # Calculate recovery times (time from max DD to new high)
        recovery_times = []
        peak_idx = 0

        for i in range(len(equity)):
            if equity.iloc[i] >= equity.iloc[peak_idx]:
                if i > peak_idx and drawdown.iloc[i - 1] < -0.01:  # Was in DD
                    recovery_times.append(i - peak_idx)
                peak_idx = i

        avg_recovery = np.mean(recovery_times) if recovery_times else 0

        # Drawdown frequency (% of time in drawdown)
        dd_frequency = sum(in_dd) / len(in_dd)

        return {
            "max_dd_pct": float(max_dd),
            "avg_dd_pct": float(avg_dd),
            "dd_duration": int(max_duration),
            "avg_dd_duration": float(avg_duration),
            "recovery_time": float(avg_recovery),
            "dd_frequency": float(dd_frequency),
        }

    # Maximum clamp values for risk-adjusted ratios.
    # Unbounded values (e.g. 999.0 when no downside) hijack the objective
    # function — Optuna would favor pathological strategies with zero losing
    # days (few trades, all tiny winners).  A Sortino of 5.0 annualized is
    # already world-class; anything above that is noise, not signal.
    MAX_SORTINO: float = 5.0
    MAX_CALMAR: float = 5.0

    @staticmethod
    def calculate_sortino_ratio(
        returns: np.ndarray, target_return: float = 0.0, annualize: bool = True
    ) -> float:
        """
        Calculate Sortino ratio (downside risk adjusted return).

        Uses downside deviation instead of standard deviation.
        Clamped to [-MAX_SORTINO, MAX_SORTINO] to prevent unbounded values
        from dominating the optimization objective.
        """
        returns = np.array(returns)

        if len(returns) == 0:
            return -RobustnessMetrics.MAX_SORTINO

        excess_return = np.mean(returns) - target_return

        # Downside deviation (only negative returns)
        downside_returns = returns[returns < target_return]
        if len(downside_returns) == 0:
            # No downside at all — clamp to max instead of returning 999
            return RobustnessMetrics.MAX_SORTINO

        downside_deviation = np.std(downside_returns)

        if downside_deviation == 0:
            return RobustnessMetrics.MAX_SORTINO

        sortino = excess_return / downside_deviation

        if annualize:
            sortino *= np.sqrt(252)

        return float(
            np.clip(
                sortino, -RobustnessMetrics.MAX_SORTINO, RobustnessMetrics.MAX_SORTINO
            )
        )

    @staticmethod
    def calculate_calmar_ratio(returns: np.ndarray, max_drawdown_pct: float) -> float:
        """
        Calculate Calmar ratio (return / max drawdown).

        Uses annualized return divided by maximum drawdown.
        Clamped to [-MAX_CALMAR, MAX_CALMAR] to prevent tiny drawdowns
        from producing unbounded ratios that hijack the objective.
        """
        if len(returns) == 0 or max_drawdown_pct <= 0:
            return -RobustnessMetrics.MAX_CALMAR

        # Annualized return
        cumulative = np.prod(1 + returns) - 1
        n_years = len(returns) / 252
        annualized_return = (1 + cumulative) ** (1 / n_years) - 1 if n_years > 0 else 0

        calmar = (annualized_return * 100) / max_drawdown_pct

        return float(
            np.clip(calmar, -RobustnessMetrics.MAX_CALMAR, RobustnessMetrics.MAX_CALMAR)
        )

    @staticmethod
    def calculate_probability_of_loss(
        returns: np.ndarray, bootstrap_samples: int = 1000
    ) -> float:
        """
        Calculate probability of negative annual return via bootstrap.

        Returns probability (0-1) of losing money in a given year.
        """
        returns = np.array(returns)
        n = len(returns)

        if n == 0:
            return 1.0

        negative_count = 0

        for _ in range(bootstrap_samples):
            sample = np.random.choice(returns, size=n, replace=True)
            cumulative = np.prod(1 + sample) - 1
            if cumulative < 0:
                negative_count += 1

        return negative_count / bootstrap_samples

    @staticmethod
    def calculate_runner_stability(trades_df: pd.DataFrame) -> Dict[str, float]:
        """
        Calculate stability of runner phase contribution.

        Analyzes the consistency of runner (Phase 3) exits.
        """
        if len(trades_df) == 0 or "exit_phase" not in trades_df.columns:
            return {
                "stability_score": 0.0,
                "runner_pct": 0.0,
                "runner_consistency": 0.0,
            }

        # Filter runner trades (exit_phase == 3)
        runner_trades = trades_df[trades_df["exit_phase"] == 3]
        total_trades = len(trades_df)

        if len(runner_trades) == 0:
            return {
                "stability_score": 0.0,
                "runner_pct": 0.0,
                "runner_consistency": 0.0,
            }

        runner_pct = len(runner_trades) / total_trades * 100

        # Calculate consistency (low variance in runner performance)
        if "pnl" in runner_trades.columns:
            runner_pnl_std = runner_trades["pnl"].std()
            runner_pnl_mean = runner_trades["pnl"].mean()

            # Coefficient of variation (lower is more consistent)
            if runner_pnl_mean != 0:
                cv = runner_pnl_std / abs(runner_pnl_mean)
                consistency = max(0, 1 - cv)
            else:
                consistency = 0.0
        else:
            consistency = 0.5  # Neutral if no PnL data

        # Stability score combines percentage and consistency
        stability_score = (runner_pct / 100) * consistency

        return {
            "stability_score": float(stability_score),
            "runner_pct": float(runner_pct),
            "runner_consistency": float(consistency),
        }

    @staticmethod
    def calculate_omega_ratio(returns: np.ndarray, threshold: float = 0.0) -> float:
        """
        Calculate Omega ratio (probability-weighted upside/downside).

        Ratio of gains above threshold to losses below threshold.
        """
        returns = np.array(returns)

        if len(returns) == 0:
            return 0.0

        gains = returns[returns > threshold] - threshold
        losses = threshold - returns[returns < threshold]

        if len(losses) == 0 or sum(losses) == 0:
            return 10.0  # Clamped — no losses is great but shouldn't be unbounded

        omega = sum(gains) / sum(losses)

        return float(min(omega, 10.0))

    @staticmethod
    def calculate_tail_ratio(returns: np.ndarray, percentile: float = 5.0) -> float:
        """
        Calculate tail ratio (p95 / |p5|).

        Measures symmetry of extreme returns.
        Higher is better (larger right tail relative to left tail).
        """
        returns = np.array(returns)

        if len(returns) == 0:
            return 0.0

        p_upper = np.percentile(returns, 100 - percentile)
        p_lower = abs(np.percentile(returns, percentile))

        if p_lower == 0:
            return 10.0  # Clamped — avoid unbounded ratio

        return float(min(p_upper / p_lower, 10.0))


def robust_objective_function(
    backtest_result: Dict[str, Any], config: Optional[RobustObjectiveConfig] = None
) -> float:
    """
    Calculate robust objective function score.

    Combines multiple robustness metrics into a single score
    for optimization. Higher is better.

    Args:
        backtest_result: Dict with backtest metrics
        config: Configuration for weights and thresholds

    Returns:
        Robustness score (can be negative if fails critical thresholds)
    """
    if config is None:
        config = RobustObjectiveConfig()

    metrics = RobustnessMetrics()
    score = 0.0
    penalties = 0.0

    # Extract data
    equity = backtest_result.get("equity_curve", pd.Series())
    returns = equity.pct_change().dropna().values if len(equity) > 0 else np.array([])
    trades_df = backtest_result.get("trades_df", pd.DataFrame())

    if len(returns) == 0:
        return -999.0

    # Bootstrap percentiles
    percentiles = metrics.calculate_bootstrap_percentiles(returns)

    # Normalize bootstrap percentiles so they're on a comparable scale
    # to risk-adjusted ratios (Sharpe ~0-3, Sortino ~0-5).
    # Without this, raw percentages (e.g. p5=30%) dominate the score.
    norm = config.bootstrap_normalization_scale

    # Add percentile contributions (weighted, normalized)
    score += (percentiles["p5"] / norm) * config.p5_weight
    score += (percentiles["p10"] / norm) * config.p10_weight
    score += (percentiles["p50"] / norm) * config.p50_weight

    # Check critical thresholds (raw values, not normalized)
    if percentiles["p5"] < config.min_p5_acceptable:
        penalties += abs(config.min_p5_acceptable - percentiles["p5"]) / norm * 2

    if percentiles["p10"] < config.min_p10_acceptable:
        penalties += abs(config.min_p10_acceptable - percentiles["p10"]) / norm

    # Risk-adjusted metrics
    sharpe = backtest_result.get("sharpe_ratio", 0.0)
    score += sharpe * config.sharpe_weight

    sortino = metrics.calculate_sortino_ratio(returns)
    score += sortino * config.sortino_weight

    # Drawdown penalties (normalized to same scale)
    dd_metrics = metrics.calculate_drawdown_metrics(equity)

    if dd_metrics["max_dd_pct"] > config.max_dd_acceptable:
        penalty = (
            (dd_metrics["max_dd_pct"] - config.max_dd_acceptable) / norm
        ) * config.max_dd_penalty
        penalties += penalty

    if dd_metrics["dd_duration"] > config.max_dd_duration_acceptable:
        penalty = (
            (dd_metrics["dd_duration"] - config.max_dd_duration_acceptable)
            / 10
            * config.dd_duration_penalty
        )
        penalties += penalty

    # Calmar ratio (only if drawdown is reasonable)
    if (
        dd_metrics["max_dd_pct"] > 0
        and dd_metrics["max_dd_pct"] < config.max_dd_acceptable
    ):
        calmar = metrics.calculate_calmar_ratio(returns, dd_metrics["max_dd_pct"])
        score += calmar * config.calmar_weight

    # Probability of loss penalty (scale: prob_loss is 0-1, multiply by 5 to put on ~0-5 range)
    prob_loss = metrics.calculate_probability_of_loss(returns)
    if prob_loss > 0.5:
        penalties += (prob_loss - 0.5) * 5 * config.loss_prob_penalty

    # Runner stability (stability_score is 0-1, scale to ~0-1 range with weight)
    runner_metrics = metrics.calculate_runner_stability(trades_df)
    score += runner_metrics["stability_score"] * 5 * config.runner_stability_weight

    # Final score
    final_score = score - penalties

    return final_score


def calculate_comprehensive_robustness_report(
    backtest_result: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Generate a comprehensive robustness report for a strategy.

    Returns all robustness metrics in a structured format.
    """
    metrics = RobustnessMetrics()

    equity = backtest_result.get("equity_curve", pd.Series())
    returns = equity.pct_change().dropna().values if len(equity) > 0 else np.array([])
    trades_df = backtest_result.get("trades_df", pd.DataFrame())

    report = {
        "bootstrap_percentiles": metrics.calculate_bootstrap_percentiles(returns),
        "drawdown_metrics": metrics.calculate_drawdown_metrics(equity),
        "risk_adjusted": {
            "sharpe": backtest_result.get("sharpe_ratio", 0.0),
            "sortino": metrics.calculate_sortino_ratio(returns),
            "calmar": metrics.calculate_calmar_ratio(
                returns, backtest_result.get("max_drawdown_pct", 100.0)
            ),
            "omega": metrics.calculate_omega_ratio(returns),
            "tail_ratio": metrics.calculate_tail_ratio(returns),
        },
        "stability": metrics.calculate_runner_stability(trades_df),
        "probability_of_loss": metrics.calculate_probability_of_loss(returns),
        "total_trades": backtest_result.get("total_trades", 0),
        "win_rate": backtest_result.get("win_rate_pct", 0.0),
        "profit_factor": backtest_result.get("profit_factor", 0.0),
    }

    return report


if __name__ == "__main__":
    print("RobustnessMetrics - Standardized Robustness Objective Functions")
    print("=" * 70)
    print("\nKey Functions:")
    print("  • robust_objective_function() - Main objective for optimization")
    print("  • calculate_comprehensive_robustness_report() - Full report")
    print("  • RobustnessMetrics class - Individual metric calculations")
    print("\nUsage:")
    print("  from src.validation.robustness_metrics import robust_objective_function")
    print("  score = robust_objective_function(backtest_result)")
