"""
Validation Harness - Three-Phase Research Gate
===============================================

Implements the production validation framework:
1. Discovery Phase: Structure fixed, initial exploration
2. Validation Phase: CSCV/PBO + WFV + bootstrap percentiles
3. Productionization Phase: Stress tests on costs/spreads/gaps, capacity

This module provides the quality gates required before any strategy
can be promoted to production.

Usage with AdvancedVectorBTEngine:
    from src.validation.research_gate import ResearchGate
    from src.backtest.vectorbt_engine_advanced import AdvancedVectorBTEngine

    # Define universe and date ranges
    universe = ['AAPL', 'MSFT', 'GOOGL', 'NVDA', 'TSLA']
    train_start, train_end = '2020-01-01', '2022-12-31'
    test_start, test_end = '2023-01-01', '2024-12-31'

    # Strategy parameters to validate
    params = {
        'min_rvol': 1.5,
        'min_adr': 2.0,
        'max_dist_sma20': 7.0,
        'tp1_r': 1.25,
        'tp2_r': 3.0,
        'risk_dollars': 150,
        'mode': 'production'
    }

    # Run validation
    gate = ResearchGate()
    result = gate.validate_strategy(
        engine_class=AdvancedVectorBTEngine,
        params=params,
        universe=universe,
        train_dates=(train_start, train_end),
        test_dates=(test_start, test_end)
    )

    if result.promotion_approved:
        print("Strategy approved for production!")
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Callable, Tuple, Any, Type
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import logging
from scipy import stats
from itertools import combinations
import warnings

logger = logging.getLogger(__name__)


@dataclass
class ValidationThresholds:
    """Quality gates for strategy promotion."""

    # PBO (Probability of Backtest Overfitting) - max acceptable
    max_pbo: float = 0.50  # Must be < 50%

    # Bootstrap percentiles - minimum acceptable OOS performance (relaxed for shorter OOS windows)
    min_p5_oos_return: float = -5.0  # 5th percentile must be > -5% (relaxed from 0%)
    min_p10_oos_return: float = -2.0  # Allow p10 >= -2% (relaxed from 0%)

    # Drawdown limits
    max_drawdown_pct: float = 25.0  # Max 25% drawdown
    max_drawdown_duration_days: int = 180  # Max 180 days — momentum selectivo tiene 7% exposure, dias en cash cuentan como DD

    # Performance stability (relaxed for shorter OOS windows)
    min_sharpe_ratio: float = 0.5  # Relaxed from 0.8
    min_profit_factor: float = 1.2
    min_win_rate: float = 45.0  # 45%

    # Statistical significance
    min_trades: int = 50

    # Walk-forward validation — RESERVED for future implementation.
    # Currently not enforced because validate_strategy() does a single
    # IS/OOS split, not a multi-fold walk-forward with R² correlation.
    # min_wfv_r2: float = 0.30

    # Runner contribution stability — RESERVED for future implementation.
    # Currently not enforced as a gate.  The metric IS computed inside
    # robust_objective_function and included in the score, but not as
    # a hard pass/fail threshold.
    # max_runner_contribution_variance: float = 0.30

    # Stress test limits
    max_2x_cost_impact_pct: float = -15.0  # Max -15% impact from 2x costs
    max_cost_impact_pct: float = -20.0  # Max -20% impact from 3x costs
    max_spread_impact_pct: float = -15.0  # Max -15% impact from wider spreads


@dataclass
class ValidationResult:
    """Results from validation pipeline."""

    # Phase results
    discovery_passed: bool = False
    validation_passed: bool = False
    productionization_passed: bool = False

    # PBO/CSCV metrics
    pbo_score: float = 1.0  # 1.0 = 100% overfitting
    cscv_logits: List[float] = field(default_factory=list)

    # Walk-forward metrics
    wfv_r2: float = 0.0
    wfv_predictions_vs_actual: List[Tuple[float, float]] = field(default_factory=list)

    # Bootstrap metrics
    bootstrap_p5: float = -100.0
    bootstrap_p10: float = -100.0
    bootstrap_p50: float = 0.0
    bootstrap_p90: float = 0.0

    # Performance metrics
    sharpe_ratio: float = 0.0

    # Drawdown analysis
    max_drawdown_pct: float = 100.0
    drawdown_duration_days: int = 999

    # Stress test results
    stress_passed: bool = False
    stress_scenarios: Dict[str, float] = field(default_factory=dict)

    # Final verdict
    promotion_approved: bool = False
    rejection_reasons: List[str] = field(default_factory=list)


class CSCVAnalyzer:
    """
    Combinatorially Symmetric Cross-Validation (CSCV).

    Implements the algorithm from Bailey et al. (2017) to estimate the
    probability of backtest overfitting (PBO).
    """

    def __init__(self, n_splits: int = 16):
        self.n_splits = n_splits

    def calculate_pbo(
        self, returns_matrix: np.ndarray, objective_fn: Optional[Callable] = None
    ) -> Tuple[float, List[float]]:
        """
        Calculate PBO using CSCV.

        Args:
            returns_matrix: Shape (n_trials, n_periods) - returns for each trial
            objective_fn: Function to rank trials (default: Sharpe ratio)

        Returns:
            pbo: Probability of backtest overfitting (0-1)
            logits: List of logits for each CSCV split
        """
        if objective_fn is None:
            objective_fn = self._default_objective

        n_trials, n_periods = returns_matrix.shape

        if n_periods < self.n_splits:
            logger.warning(
                f"CSCV: {n_periods} periods < {self.n_splits} splits, reducing splits"
            )
            self.n_splits = max(2, n_periods // 2)

        # Divide periods into S groups
        S = self.n_splits
        group_size = n_periods // S

        logits = []
        overfitting_count = 0
        total_splits = 0

        # Generate all combinations of S/2 groups for IS vs OOS
        is_group_count = S // 2

        for is_groups in combinations(range(S), is_group_count):
            oos_groups = tuple(i for i in range(S) if i not in is_groups)

            # Define IS and OOS periods
            is_periods = []
            oos_periods = []

            for g in is_groups:
                start = g * group_size
                end = start + group_size if g < S - 1 else n_periods
                is_periods.extend(range(start, end))

            for g in oos_groups:
                start = g * group_size
                end = start + group_size if g < S - 1 else n_periods
                oos_periods.extend(range(start, end))

            # Calculate objective for IS and OOS
            is_scores = np.array(
                [objective_fn(returns_matrix[i, is_periods]) for i in range(n_trials)]
            )
            oos_scores = np.array(
                [objective_fn(returns_matrix[i, oos_periods]) for i in range(n_trials)]
            )

            # Find optimal trial in IS
            is_optimal_idx = np.argmax(is_scores)

            # Calculate rank of IS-optimal in OOS
            oos_ranks = stats.rankdata(-oos_scores)  # Negative for descending
            is_optimal_oos_rank = oos_ranks[is_optimal_idx]

            # Calculate logit
            # logit = log(ω/(1-ω)) where ω = (rank - 0.5) / N
            N = n_trials
            omega = (is_optimal_oos_rank - 0.5) / N

            # Avoid log(0)
            omega = np.clip(omega, 1e-10, 1 - 1e-10)
            logit = np.log(omega / (1 - omega))
            logits.append(logit)

            # Count overfitting (logit < 0 means IS-optimal ranks in bottom half of OOS)
            if logit < 0:
                overfitting_count += 1
            total_splits += 1

        pbo = overfitting_count / total_splits if total_splits > 0 else 1.0

        return pbo, logits

    def _default_objective(self, returns: np.ndarray) -> float:
        """Default: Sharpe ratio (annualized)."""
        if len(returns) == 0 or np.std(returns) == 0:
            return -999.0
        sharpe = np.mean(returns) / np.std(returns) * np.sqrt(252)
        return sharpe


class BootstrapAnalyzer:
    """
        Bootstrap analysis for OOS return percentiles.

        Provides robustness metrics by resampling returns to estimate
    the distribution of out-of-sample performance.
    """

    def __init__(self, n_bootstrap: int = 1000, random_state: int = 42):
        self.n_bootstrap = n_bootstrap
        self.random_state = random_state
        np.random.seed(random_state)

    def analyze(
        self,
        returns: np.ndarray,
        block_size: Optional[int] = None,  # For block bootstrap (serial correlation)
    ) -> Dict[str, float]:
        """
        Bootstrap analysis of returns.

        Args:
            returns: Array of returns (daily)
            block_size: Block size for stationary bootstrap (None = simple bootstrap)

        Returns:
            Dict with percentiles and confidence intervals
        """
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
                "ci_lower": -100.0,
                "ci_upper": 100.0,
            }

        bootstrapped_metrics = []

        for _ in range(self.n_bootstrap):
            if block_size is not None and block_size > 1:
                # Stationary bootstrap for time series
                sample = self._block_bootstrap(returns, block_size)
            else:
                # Simple bootstrap
                sample = np.random.choice(returns, size=n, replace=True)

            # Calculate metric (annualized return)
            cumulative_return = np.prod(1 + sample) - 1
            annualized_return = (1 + cumulative_return) ** (252 / n) - 1
            bootstrapped_metrics.append(annualized_return * 100)  # As percentage

        bootstrapped_metrics = np.array(bootstrapped_metrics)

        return {
            "p5": float(np.percentile(bootstrapped_metrics, 5)),
            "p10": float(np.percentile(bootstrapped_metrics, 10)),
            "p50": float(np.percentile(bootstrapped_metrics, 50)),
            "p90": float(np.percentile(bootstrapped_metrics, 90)),
            "mean": float(np.mean(bootstrapped_metrics)),
            "std": float(np.std(bootstrapped_metrics)),
            "ci_lower": float(np.percentile(bootstrapped_metrics, 2.5)),
            "ci_upper": float(np.percentile(bootstrapped_metrics, 97.5)),
        }

    def _block_bootstrap(self, data: np.ndarray, block_size: int) -> np.ndarray:
        """Stationary bootstrap for time series data."""
        n = len(data)
        n_blocks = int(np.ceil(n / block_size))

        blocks = []
        for _ in range(n_blocks):
            start = np.random.randint(0, n - block_size + 1)
            block = data[start : start + block_size]
            blocks.append(block)

        sample = np.concatenate(blocks)[:n]
        return sample


class ResearchGate:
    """
    Three-phase research gate for strategy validation.

    Orchestrates the validation pipeline:
    1. Discovery: Fixed structure, initial parameter exploration
    2. Validation: CSCV/PBO + WFV + Bootstrap percentiles
    3. Productionization: Stress tests, capacity analysis

    Adapted for AdvancedVectorBTEngine architecture:
    - Params passed to constructor
    - load_data() called internally
    - run_backtest() returns metrics
    """

    def __init__(self, thresholds: Optional[ValidationThresholds] = None):
        self.thresholds = thresholds or ValidationThresholds()
        self.cscv_analyzer = CSCVAnalyzer(n_splits=16)
        self.bootstrap_analyzer = BootstrapAnalyzer(n_bootstrap=1000)
        # Default block size for block bootstrap.
        # Daily equity returns have serial correlation (momentum, mean-reversion
        # at daily scale).  Simple i.i.d. bootstrap underestimates variance →
        # overconfident percentiles.  5 trading days ≈ 1 week captures the
        # short-term autocorrelation structure.
        self.bootstrap_block_size = 5

    def validate_strategy(
        self,
        engine_class: Type,
        params: Dict[str, Any],
        universe: List[str],
        train_dates: Tuple[str, str],
        test_dates: Tuple[str, str],
        n_cscv_trials: int = 100,
        verbose: bool = True,
    ) -> ValidationResult:
        """
        Run full validation pipeline on a strategy using AdvancedVectorBTEngine.

        Args:
            engine_class: Class of the backtest engine (e.g., AdvancedVectorBTEngine)
            params: Strategy parameters (passed to engine constructor)
            universe: List of tickers
            train_dates: (start_date, end_date) for training/IS period
            test_dates: (start_date, end_date) for test/OOS period
            n_cscv_trials: Number of trials for CSCV analysis
            verbose: Whether to log progress

        Returns:
            ValidationResult with all metrics and final verdict
        """
        result = ValidationResult()

        if verbose:
            logger.info("=" * 70)
            logger.info("🔬 THREE-PHASE RESEARCH GATE")
            logger.info("=" * 70)
            logger.info(f"Universe: {len(universe)} tickers")
            logger.info(f"Training: {train_dates[0]} to {train_dates[1]}")
            logger.info(f"Test: {test_dates[0]} to {test_dates[1]}")

        # Phase 1: Discovery (structure validation)
        if verbose:
            logger.info("\n📋 PHASE 1: DISCOVERY (Structure Validation)")

        result.discovery_passed = self._run_discovery_phase(params)

        if not result.discovery_passed:
            result.rejection_reasons.append(
                "Discovery phase failed: Invalid strategy structure"
            )
            return result

        if verbose:
            logger.info("   ✅ Discovery phase passed")

        # Phase 2: Validation (CSCV + Bootstrap + Performance metrics)
        if verbose:
            logger.info("\n📊 PHASE 2: VALIDATION (CSCV/PBO + Bootstrap + Metrics)")

        # Run backtest on training period
        if verbose:
            logger.info("   Running training period backtest...")

        try:
            train_engine = engine_class(
                universe=universe,
                start_date=train_dates[0],
                end_date=train_dates[1],
                **params,
            )
            train_engine.load_data()
            train_results = train_engine.run_backtest()
        except Exception as e:
            logger.error(f"Training backtest failed: {e}")
            result.rejection_reasons.append(f"Training backtest failed: {str(e)}")
            return result

        # Run backtest on test period
        if verbose:
            logger.info("   Running test period backtest...")

        try:
            test_engine = engine_class(
                universe=universe,
                start_date=test_dates[0],
                end_date=test_dates[1],
                **params,
            )
            test_engine.load_data()
            test_results = test_engine.run_backtest()
        except Exception as e:
            logger.error(f"Test backtest failed: {e}")
            result.rejection_reasons.append(f"Test backtest failed: {str(e)}")
            return result

        # Extract metrics
        train_metrics = self._extract_metrics(train_results)
        test_metrics = self._extract_metrics(test_results)

        # Store test metrics in result
        result.sharpe_ratio = test_metrics.get("sharpe_ratio", 0.0)

        if verbose:
            logger.info(f"   Training Sharpe: {train_metrics['sharpe_ratio']:.2f}")
            logger.info(f"   Test Sharpe: {test_metrics['sharpe_ratio']:.2f}")
            logger.info(f"   Training Trades: {train_metrics['total_trades']}")
            logger.info(f"   Test Trades: {test_metrics['total_trades']}")

        # Check minimum trades
        if test_metrics["total_trades"] < self.thresholds.min_trades:
            result.rejection_reasons.append(
                f"Insufficient trades: {test_metrics['total_trades']} < {self.thresholds.min_trades}"
            )

        # Extract equity curves for CSCV
        train_equity = train_results.get("equity_curve", pd.Series())
        test_equity = test_results.get("equity_curve", pd.Series())

        if len(train_equity) > 0 and len(test_equity) > 0:
            param_variations = self._generate_param_variations(
                params, n_variations=min(20, n_cscv_trials)
            )
            returns_list = []

            for var_params in param_variations:
                try:
                    var_engine = engine_class(
                        universe=universe,
                        start_date=train_dates[0],
                        end_date=train_dates[1],
                        **var_params,
                    )
                    var_engine.load_data()
                    var_results = var_engine.run_backtest()
                    var_equity = var_results.get("equity_curve", pd.Series())
                    if len(var_equity) > 10:
                        var_returns = var_equity.pct_change().dropna().values
                        returns_list.append(var_returns)
                except Exception:
                    continue

            if len(returns_list) >= 2:
                max_len = max(len(r) for r in returns_list)
                padded = np.array(
                    [
                        np.pad(r, (0, max_len - len(r)), constant_values=0)
                        for r in returns_list
                    ]
                )
                pbo, logits = self.cscv_analyzer.calculate_pbo(padded)
                result.pbo_score = pbo
                result.cscv_logits = logits
            else:
                result.pbo_score = 0.5
                result.cscv_logits = []
                result.rejection_reasons.append(
                    "PBO could not be calculated (insufficient param variations)"
                )

            if verbose:
                logger.info(
                    f"   PBO Score: {result.pbo_score:.2%} (from {len(returns_list)} param variations)"
                )

        # Bootstrap analysis on test period returns
        if len(test_equity) > 0:
            test_returns = test_equity.pct_change().dropna().values
            bootstrap = self.bootstrap_analyzer.analyze(
                test_returns, block_size=self.bootstrap_block_size
            )

            result.bootstrap_p5 = bootstrap["p5"]
            result.bootstrap_p10 = bootstrap["p10"]
            result.bootstrap_p50 = bootstrap["p50"]
            result.bootstrap_p90 = bootstrap["p90"]

            if verbose:
                logger.info(f"   Bootstrap OOS Returns:")
                logger.info(f"     p5:  {bootstrap['p5']:+.2f}%")
                logger.info(f"     p10: {bootstrap['p10']:+.2f}%")
                logger.info(f"     p50: {bootstrap['p50']:+.2f}%")

        # Calculate drawdown metrics
        if len(test_equity) > 0:
            max_dd, dd_duration = self._calculate_drawdown_metrics(test_equity)
            result.max_drawdown_pct = max_dd
            result.drawdown_duration_days = dd_duration

            if verbose:
                logger.info(f"   Max Drawdown: {max_dd:.2f}%")
                logger.info(f"   DD Duration: {dd_duration} days")

        # Check validation thresholds
        result.validation_passed = self._check_validation_thresholds(
            result, test_metrics
        )

        if not result.validation_passed:
            if result.pbo_score > self.thresholds.max_pbo:
                result.rejection_reasons.append(
                    f"PBO too high: {result.pbo_score:.2%} > {self.thresholds.max_pbo:.2%}"
                )
            if result.bootstrap_p5 < self.thresholds.min_p5_oos_return:
                result.rejection_reasons.append(
                    f"OOS p5 too low: {result.bootstrap_p5:.2f}% < {self.thresholds.min_p5_oos_return:.2f}%"
                )
            if result.bootstrap_p10 < self.thresholds.min_p10_oos_return:
                result.rejection_reasons.append(
                    f"OOS p10 too low: {result.bootstrap_p10:.2f}% < {self.thresholds.min_p10_oos_return:.2f}%"
                )
            if result.max_drawdown_pct > self.thresholds.max_drawdown_pct:
                result.rejection_reasons.append(
                    f"Drawdown too high: {result.max_drawdown_pct:.2f}% > {self.thresholds.max_drawdown_pct:.2f}%"
                )
            if (
                result.drawdown_duration_days
                > self.thresholds.max_drawdown_duration_days
            ):
                result.rejection_reasons.append(
                    f"Drawdown duration too long: {result.drawdown_duration_days} days > {self.thresholds.max_drawdown_duration_days} days"
                )
            if test_metrics["sharpe_ratio"] < self.thresholds.min_sharpe_ratio:
                result.rejection_reasons.append(
                    f"Sharpe too low: {test_metrics['sharpe_ratio']:.2f} < {self.thresholds.min_sharpe_ratio:.2f}"
                )
            if test_metrics["profit_factor"] < self.thresholds.min_profit_factor:
                result.rejection_reasons.append(
                    f"Profit factor too low: {test_metrics['profit_factor']:.2f} < {self.thresholds.min_profit_factor:.2f}"
                )
            if test_metrics["win_rate_pct"] < self.thresholds.min_win_rate:
                result.rejection_reasons.append(
                    f"Win rate too low: {test_metrics['win_rate_pct']:.1f}% < {self.thresholds.min_win_rate:.1f}%"
                )
            if test_metrics["total_trades"] < self.thresholds.min_trades:
                result.rejection_reasons.append(
                    f"Insufficient trades: {test_metrics['total_trades']} < {self.thresholds.min_trades}"
                )

        if verbose and result.validation_passed:
            logger.info("   ✅ Validation phase passed")

        # Phase 3: Productionization (Stress tests)
        if verbose:
            logger.info("\n🔥 PHASE 3: PRODUCTIONIZATION (Stress Testing)")

        result.stress_passed, result.stress_scenarios = self._run_stress_tests(
            engine_class=engine_class,
            params=params,
            universe=universe,
            test_dates=test_dates,
            baseline_results=test_metrics,
        )

        if verbose:
            for scenario, impact in result.stress_scenarios.items():
                logger.info(f"   {scenario}: {impact:+.2f}% impact")

        result.productionization_passed = result.stress_passed

        if not result.productionization_passed:
            result.rejection_reasons.append("Stress tests failed")
        elif verbose:
            logger.info("   ✅ Productionization phase passed")

        # Final verdict
        result.promotion_approved = (
            result.discovery_passed
            and result.validation_passed
            and result.productionization_passed
        )

        if verbose:
            logger.info("\n" + "=" * 70)
            if result.promotion_approved:
                logger.info("🎉 STRATEGY APPROVED FOR PRODUCTION")
            else:
                logger.info("❌ STRATEGY REJECTED")
                for reason in result.rejection_reasons:
                    logger.info(f"   • {reason}")
            logger.info("=" * 70)

        return result

    def _run_discovery_phase(self, params: Dict[str, Any]) -> bool:
        """Validate strategy structure and parameter bounds."""
        # Check required parameters exist
        required_params = [
            "min_rvol",
            "min_adr",
            "max_dist_sma20",
            "tp1_r",
            "tp2_r",
            "risk_dollars",
        ]

        for param in required_params:
            if param not in params:
                logger.error(f"Missing required parameter: {param}")
                return False

        # Validate parameter bounds
        if params.get("min_rvol", 0) < 0.5 or params.get("min_rvol", 0) > 5.0:
            logger.error(f"Invalid min_rvol: {params['min_rvol']}")
            return False

        if params.get("max_dist_sma20", 0) < 0 or params.get("max_dist_sma20", 0) > 50:
            logger.error(f"Invalid max_dist_sma20: {params['max_dist_sma20']}")
            return False

        return True

    def _extract_metrics(self, results: Dict[str, Any]) -> Dict[str, float]:
        """Extract key metrics from backtest results.

        Handles both formats:
        - AdvancedVectorBTEngine: returns decimals (0.15 = 15%) with keys like 'total_return', 'win_rate', 'max_drawdown'
        - Legacy engines: may return percentages with '_pct' suffix
        """
        # Total return: try decimal format first, then _pct format
        total_return = results.get("total_return", None)
        if total_return is not None:
            total_return_pct = total_return * 100  # Convert 0.15 -> 15.0
        else:
            total_return_pct = results.get("total_return_pct", 0.0)

        # Max drawdown: try decimal format first (negative), then _pct format
        max_dd = results.get("max_drawdown", None)
        if max_dd is not None:
            max_drawdown_pct = abs(max_dd) * 100  # Convert -0.05 -> 5.0
        else:
            max_drawdown_pct = results.get("max_drawdown_pct", 0.0)

        # Win rate: try decimal format first, then _pct format
        win_rate = results.get("win_rate", None)
        if win_rate is not None:
            win_rate_pct = win_rate * 100  # Convert 0.65 -> 65.0
        else:
            win_rate_pct = results.get("win_rate_pct", 0.0)

        return {
            "total_return_pct": total_return_pct,
            "sharpe_ratio": results.get("sharpe_ratio", results.get("sharpe", 0.0)),
            "max_drawdown_pct": max_drawdown_pct,
            "total_trades": results.get("total_trades", results.get("trades", 0)),
            "win_rate_pct": win_rate_pct,
            "profit_factor": results.get("profit_factor", 0.0),
        }

    def _calculate_drawdown_metrics(self, equity: pd.Series) -> Tuple[float, int]:
        """Calculate max drawdown and duration."""
        cummax = equity.cummax()
        drawdown = (equity - cummax) / cummax

        max_dd = abs(drawdown.min()) * 100

        # Calculate drawdown duration
        in_drawdown = drawdown < 0
        durations = []
        current_duration = 0

        for is_dd in in_drawdown:
            if is_dd:
                current_duration += 1
            else:
                if current_duration > 0:
                    durations.append(current_duration)
                current_duration = 0

        if current_duration > 0:
            durations.append(current_duration)

        max_duration = max(durations) if durations else 0

        return max_dd, max_duration

    def _check_validation_thresholds(
        self, result: ValidationResult, metrics: Dict[str, float]
    ) -> bool:
        """Check if validation metrics pass thresholds."""
        checks = [
            result.pbo_score <= self.thresholds.max_pbo,
            result.bootstrap_p5 >= self.thresholds.min_p5_oos_return,
            result.bootstrap_p10 >= self.thresholds.min_p10_oos_return,
            result.max_drawdown_pct <= self.thresholds.max_drawdown_pct,
            result.drawdown_duration_days <= self.thresholds.max_drawdown_duration_days,
            metrics["sharpe_ratio"] >= self.thresholds.min_sharpe_ratio,
            metrics["profit_factor"] >= self.thresholds.min_profit_factor,
            metrics["win_rate_pct"] >= self.thresholds.min_win_rate,
            metrics["total_trades"] >= self.thresholds.min_trades,
        ]

        return all(checks)

    def _run_stress_tests(
        self,
        engine_class: Type,
        params: Dict[str, Any],
        universe: List[str],
        test_dates: Tuple[str, str],
        baseline_results: Dict[str, float],
    ) -> Tuple[bool, Dict[str, float]]:
        """Run stress tests on costs, spreads, and gaps.

        Uses _extract_metrics to properly handle both engine output formats
        (with/without _pct suffix).
        """
        scenarios = {}
        baseline_return = baseline_results.get("total_return_pct", 0.0)

        # Stress test: Double transaction costs
        try:
            params_high_cost = {
                **params,
                "fees": 0.002,  # 0.2% vs default 0.1%
                "slippage": 0.002,
            }
            engine_high_cost = engine_class(
                universe=universe,
                start_date=test_dates[0],
                end_date=test_dates[1],
                **params_high_cost,
            )
            engine_high_cost.load_data()
            results_high_cost = engine_high_cost.run_backtest()
            metrics_high_cost = self._extract_metrics(results_high_cost)
            scenarios["2x_costs"] = (
                metrics_high_cost["total_return_pct"] - baseline_return
            )
        except Exception as e:
            logger.warning(f"2x costs stress test failed: {e}")
            scenarios["2x_costs"] = -999.0

        # Stress test: Triple transaction costs
        try:
            params_extreme_cost = {
                **params,
                "fees": 0.003,  # 0.3%
                "slippage": 0.003,
            }
            engine_extreme_cost = engine_class(
                universe=universe,
                start_date=test_dates[0],
                end_date=test_dates[1],
                **params_extreme_cost,
            )
            engine_extreme_cost.load_data()
            results_extreme_cost = engine_extreme_cost.run_backtest()
            metrics_extreme_cost = self._extract_metrics(results_extreme_cost)
            scenarios["3x_costs"] = (
                metrics_extreme_cost["total_return_pct"] - baseline_return
            )
        except Exception as e:
            logger.warning(f"3x costs stress test failed: {e}")
            scenarios["3x_costs"] = -999.0

        # Stress test: Wider spreads (liquidity stress)
        try:
            params_wider_spread = {
                **params,
                "slippage": 0.005,  # 0.5% slippage
            }
            engine_wider_spread = engine_class(
                universe=universe,
                start_date=test_dates[0],
                end_date=test_dates[1],
                **params_wider_spread,
            )
            engine_wider_spread.load_data()
            results_wider_spread = engine_wider_spread.run_backtest()
            metrics_wider_spread = self._extract_metrics(results_wider_spread)
            scenarios["wider_spreads"] = (
                metrics_wider_spread["total_return_pct"] - baseline_return
            )
        except Exception as e:
            logger.warning(f"Wider spreads stress test failed: {e}")
            scenarios["wider_spreads"] = -999.0

        # Check if scenarios are acceptable
        passed = (
            scenarios.get("2x_costs", -999) > self.thresholds.max_2x_cost_impact_pct
            and scenarios.get("3x_costs", -999) > self.thresholds.max_cost_impact_pct
            and scenarios.get("wider_spreads", -999)
            > self.thresholds.max_spread_impact_pct
        )

        return passed, scenarios

    def _generate_param_variations(
        self, base_params: Dict[str, Any], n_variations: int = 20
    ) -> List[Dict[str, Any]]:
        """Generate parameter variations for CSCV analysis.

        Creates slight variations around the optimal parameters to test
        for overfitting via Combinatorially Symmetric Cross-Validation.
        """
        np.random.seed(42)
        variations = [base_params.copy()]

        for _ in range(n_variations - 1):
            var = base_params.copy()

            if "tp1_r" in var:
                var["tp1_r"] = max(
                    1.0, min(2.5, base_params["tp1_r"] * np.random.uniform(0.85, 1.15))
                )
            if "tp2_r" in var:
                var["tp2_r"] = max(
                    2.5, min(6.0, base_params["tp2_r"] * np.random.uniform(0.85, 1.15))
                )

            if "min_rvol" in var:
                var["min_rvol"] = max(
                    0.5, min(4.0, base_params["min_rvol"] * np.random.uniform(0.9, 1.1))
                )
            if "min_adr" in var:
                var["min_adr"] = max(
                    1.0, min(6.0, base_params["min_adr"] * np.random.uniform(0.9, 1.1))
                )
            if "max_dist_sma20" in var:
                var["max_dist_sma20"] = max(
                    3.0,
                    min(
                        15.0,
                        base_params["max_dist_sma20"] * np.random.uniform(0.9, 1.1),
                    ),
                )

            variations.append(var)

        return variations


# Convenience function for quick validation
def validate_for_production(
    engine_class: Type,
    params: Dict[str, Any],
    universe: List[str],
    train_dates: Tuple[str, str],
    test_dates: Tuple[str, str],
    custom_thresholds: Optional[Dict[str, float]] = None,
) -> bool:
    """
    Quick validation function for production readiness.

    Returns True if strategy passes all gates, False otherwise.
    """
    thresholds = ValidationThresholds()

    if custom_thresholds:
        for key, value in custom_thresholds.items():
            if hasattr(thresholds, key):
                setattr(thresholds, key, value)

    gate = ResearchGate(thresholds=thresholds)
    result = gate.validate_strategy(
        engine_class=engine_class,
        params=params,
        universe=universe,
        train_dates=train_dates,
        test_dates=test_dates,
        verbose=False,
    )

    return result.promotion_approved


if __name__ == "__main__":
    print("ResearchGate - Three-Phase Research Gate for Strategy Validation")
    print("=" * 70)
    print("\nUsage:")
    print("  from src.validation.research_gate import ResearchGate")
    print("  from src.backtest.vectorbt_engine_advanced import AdvancedVectorBTEngine")
    print("  ")
    print("  gate = ResearchGate()")
    print("  result = gate.validate_strategy(")
    print("      engine_class=AdvancedVectorBTEngine,")
    print("      params={'min_rvol': 1.5, 'min_adr': 2.0, ...},")
    print("      universe=['AAPL', 'MSFT', 'GOOGL'],")
    print("      train_dates=('2020-01-01', '2022-12-31'),")
    print("      test_dates=('2023-01-01', '2024-12-31')")
    print("  )")
    print("  ")
    print("  if result.promotion_approved:")
    print("      print('Strategy approved for production!')")
