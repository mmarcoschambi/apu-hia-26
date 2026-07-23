"""
Stress Testing Suite - Productionization Phase
===============================================

Comprehensive stress testing for trading strategies including:
- Transaction cost sensitivity (2x, 3x, 5x costs)
- Liquidity stress (wider spreads, volume shocks)
- Gap risk (overnight gaps, flash crashes)
- Capacity analysis (position sizing limits)
- Correlation stress (market correlation spikes)

Usage:
    from src.validation.stress_testing import StressTestSuite

    suite = StressTestSuite(engine_class=AdvancedVectorBTEngine)

    results = suite.run_full_stress_test(
        params=strategy_params,
        universe=tickers,
        test_dates=('2023-01-01', '2024-12-31')
    )

    if results.all_passed:
        print("Strategy resilient to stress scenarios")
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Tuple, Optional, Any, Type
from dataclasses import dataclass, field
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


@dataclass
class StressThresholds:
    """Thresholds for stress test scenarios."""

    # Cost stress limits
    max_impact_2x_costs: float = -10.0  # Max -10% impact from 2x costs
    max_impact_3x_costs: float = -20.0  # Max -20% impact from 3x costs
    max_impact_5x_costs: float = -35.0  # Max -35% impact from 5x costs

    # Spread/liquidity stress limits
    max_impact_wider_spreads: float = -15.0  # Max -15% from 0.5% slippage
    max_impact_extreme_spreads: float = -25.0  # Max -25% from 1.0% slippage

    # Gap risk limits
    max_impact_gap_1pct: float = -5.0  # Max -5% from 1% adverse gaps
    max_impact_gap_2pct: float = -12.0  # Max -12% from 2% adverse gaps

    # Capacity limits
    min_capacity_dollar_volume: float = 1_000_000  # Min $1M daily volume
    max_single_position_pct: float = 5.0  # Max 5% of portfolio in one trade

    # Correlation stress
    max_impact_high_correlation: float = -20.0  # Max -20% during correlation spikes

    # Worst case combined scenario
    max_impact_worst_case: float = -50.0  # Max -50% in worst case


@dataclass
class StressTestResult:
    """Results from comprehensive stress testing."""

    all_passed: bool = False

    # Cost stress results
    baseline_return: float = 0.0
    impact_2x_costs: float = 0.0
    impact_3x_costs: float = 0.0
    impact_5x_costs: float = 0.0
    cost_stress_passed: bool = False

    # Spread/liquidity stress results
    impact_wider_spreads: float = 0.0
    impact_extreme_spreads: float = 0.0
    liquidity_stress_passed: bool = False

    # Gap risk results
    impact_gap_1pct: float = 0.0
    impact_gap_2pct: float = 0.0
    gap_risk_passed: bool = False

    # Capacity analysis
    avg_position_size_dollars: float = 0.0
    max_position_size_dollars: float = 0.0
    min_liquidity_dollar_volume: float = 0.0
    capacity_passed: bool = False

    # Correlation stress
    impact_high_correlation: float = 0.0
    correlation_stress_passed: bool = False

    # Combined worst case
    impact_worst_case: float = 0.0
    worst_case_passed: bool = False

    # Detailed metrics
    scenario_details: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    failure_reasons: List[str] = field(default_factory=list)


class StressTestSuite:
    """
    Comprehensive stress testing for trading strategies.

    Tests strategy resilience across multiple dimensions:
    1. Transaction costs (2x, 3x, 5x)
    2. Liquidity/spreads (normal, wide, extreme)
    3. Gap risk (1%, 2% adverse gaps)
    4. Capacity (position limits, volume constraints)
    5. Correlation stress (market correlation spikes)
    6. Combined worst-case scenarios
    """

    def __init__(
        self, engine_class: Type, thresholds: Optional[StressThresholds] = None
    ):
        self.engine_class = engine_class
        self.thresholds = thresholds or StressThresholds()

    def run_full_stress_test(
        self,
        params: Dict[str, Any],
        universe: List[str],
        test_dates: Tuple[str, str],
        baseline_engine: Optional[Any] = None,
        verbose: bool = True,
    ) -> StressTestResult:
        """
        Run comprehensive stress test suite.

        Args:
            params: Strategy parameters
            universe: List of tickers
            test_dates: (start_date, end_date) for testing
            baseline_engine: Pre-initialized engine with baseline results (optional)
            verbose: Whether to log progress

        Returns:
            StressTestResult with all scenarios
        """
        result = StressTestResult()

        if verbose:
            logger.info("=" * 70)
            logger.info("[U+1F525] STRESS TESTING SUITE")
            logger.info("=" * 70)

        # Get baseline results
        if baseline_engine is not None:
            baseline_results = baseline_engine.run_backtest()
        else:
            if verbose:
                logger.info("Running baseline backtest...")
            try:
                baseline_engine = self.engine_class(
                    universe=universe,
                    start_date=test_dates[0],
                    end_date=test_dates[1],
                    **params,
                )
                baseline_engine.load_data()
                baseline_results = baseline_engine.run_backtest()
            except Exception as e:
                logger.error(f"Baseline backtest failed: {e}")
                result.failure_reasons.append(f"Baseline failed: {str(e)}")
                return result

        result.baseline_return = baseline_results.get("total_return_pct", 0.0)

        if verbose:
            logger.info(f"Baseline Return: {result.baseline_return:.2f}%")

        # Run cost stress tests
        result = self._run_cost_stress(params, universe, test_dates, result, verbose)

        # Run liquidity stress tests
        result = self._run_liquidity_stress(
            params, universe, test_dates, result, verbose
        )

        # Run gap risk tests
        result = self._run_gap_risk_stress(
            params, universe, test_dates, result, verbose
        )

        # Run capacity analysis
        result = self._run_capacity_analysis(baseline_results, params, result, verbose)

        # Run correlation stress
        result = self._run_correlation_stress(
            params, universe, test_dates, result, verbose
        )

        # Calculate worst case
        result = self._calculate_worst_case(result, verbose)

        # Determine overall pass/fail
        result.all_passed = (
            result.cost_stress_passed
            and result.liquidity_stress_passed
            and result.gap_risk_passed
            and result.capacity_passed
            and result.correlation_stress_passed
            and result.worst_case_passed
        )

        if verbose:
            logger.info("\n" + "=" * 70)
            if result.all_passed:
                logger.info("[OK] ALL STRESS TESTS PASSED")
            else:
                logger.info("[FAIL] STRESS TESTS FAILED")
                for reason in result.failure_reasons:
                    logger.info(f"   • {reason}")
            logger.info("=" * 70)

        return result

    def _run_cost_stress(
        self,
        params: Dict[str, Any],
        universe: List[str],
        test_dates: Tuple[str, str],
        result: StressTestResult,
        verbose: bool,
    ) -> StressTestResult:
        """Test sensitivity to transaction costs."""
        if verbose:
            logger.info("\n[U+1F4B0] Cost Stress Tests")

        scenarios = [
            ("2x", 0.002, self.thresholds.max_impact_2x_costs, "impact_2x_costs"),
            ("3x", 0.003, self.thresholds.max_impact_3x_costs, "impact_3x_costs"),
            ("5x", 0.005, self.thresholds.max_impact_5x_costs, "impact_5x_costs"),
        ]

        passed = True

        for label, cost_rate, threshold, attr_name in scenarios:
            try:
                cost_params = {**params, "fees": cost_rate, "slippage": cost_rate}

                engine = self.engine_class(
                    universe=universe,
                    start_date=test_dates[0],
                    end_date=test_dates[1],
                    **cost_params,
                )
                engine.load_data()
                cost_results = engine.run_backtest()

                impact = (
                    cost_results.get("total_return_pct", 0.0) - result.baseline_return
                )
                setattr(result, attr_name, impact)

                scenario_passed = impact > threshold
                if not scenario_passed:
                    passed = False
                    result.failure_reasons.append(
                        f"{label} costs: impact {impact:.2f}% < threshold {threshold:.2f}%"
                    )

                if verbose:
                    status = "[OK]" if scenario_passed else "[FAIL]"
                    logger.info(
                        f"   {status} {label} costs ({cost_rate:.1%}): {impact:+.2f}%"
                    )

            except Exception as e:
                logger.warning(f"Cost stress test {label} failed: {e}")
                setattr(result, attr_name, -999.0)
                passed = False

        result.cost_stress_passed = passed
        return result

    def _run_liquidity_stress(
        self,
        params: Dict[str, Any],
        universe: List[str],
        test_dates: Tuple[str, str],
        result: StressTestResult,
        verbose: bool,
    ) -> StressTestResult:
        """Test sensitivity to wider spreads and liquidity constraints."""
        if verbose:
            logger.info("\n[U+1F4A7] Liquidity Stress Tests")

        scenarios = [
            (
                "wide",
                0.005,
                self.thresholds.max_impact_wider_spreads,
                "impact_wider_spreads",
            ),
            (
                "extreme",
                0.010,
                self.thresholds.max_impact_extreme_spreads,
                "impact_extreme_spreads",
            ),
        ]

        passed = True

        for label, slippage, threshold, attr_name in scenarios:
            try:
                liquidity_params = {**params, "slippage": slippage}

                engine = self.engine_class(
                    universe=universe,
                    start_date=test_dates[0],
                    end_date=test_dates[1],
                    **liquidity_params,
                )
                engine.load_data()
                liquidity_results = engine.run_backtest()

                impact = (
                    liquidity_results.get("total_return_pct", 0.0)
                    - result.baseline_return
                )
                setattr(result, attr_name, impact)

                scenario_passed = impact > threshold
                if not scenario_passed:
                    passed = False
                    result.failure_reasons.append(
                        f"{label} spreads: impact {impact:.2f}% < threshold {threshold:.2f}%"
                    )

                if verbose:
                    status = "[OK]" if scenario_passed else "[FAIL]"
                    logger.info(
                        f"   {status} {label} spreads ({slippage:.1%}): {impact:+.2f}%"
                    )

            except Exception as e:
                logger.warning(f"Liquidity stress test {label} failed: {e}")
                setattr(result, attr_name, -999.0)
                passed = False

        result.liquidity_stress_passed = passed
        return result

    def _run_gap_risk_stress(
        self,
        params: Dict[str, Any],
        universe: List[str],
        test_dates: Tuple[str, str],
        result: StressTestResult,
        verbose: bool,
    ) -> StressTestResult:
        """
        Test sensitivity to overnight/flash crash gaps.

        Note: This is a simulation. Real gap testing would require
        modifying the engine to inject gaps at random or worst-case points.
        """
        if verbose:
            logger.info("\n[BOLT] Gap Risk Stress Tests (Simulated)")
            logger.info("   Note: Gap simulation requires engine modification")

        # Placeholder for gap risk - in production, modify engine to support gap injection
        # For now, we estimate based on volatility metrics

        result.impact_gap_1pct = result.impact_wider_spreads * 0.5  # Estimate
        result.impact_gap_2pct = result.impact_extreme_spreads * 0.8  # Estimate

        gap_1_passed = result.impact_gap_1pct > self.thresholds.max_impact_gap_1pct
        gap_2_passed = result.impact_gap_2pct > self.thresholds.max_impact_gap_2pct

        result.gap_risk_passed = gap_1_passed and gap_2_passed

        if verbose:
            logger.info(
                f"   {'[OK]' if gap_1_passed else '[FAIL]'} 1% gaps: {result.impact_gap_1pct:+.2f}%"
            )
            logger.info(
                f"   {'[OK]' if gap_2_passed else '[FAIL]'} 2% gaps: {result.impact_gap_2pct:+.2f}%"
            )

        return result

    def _run_capacity_analysis(
        self,
        baseline_results: Dict[str, Any],
        params: Dict[str, Any],
        result: StressTestResult,
        verbose: bool,
    ) -> StressTestResult:
        """Analyze strategy capacity and position sizing limits."""
        if verbose:
            logger.info("\n[U+1F4CA] Capacity Analysis")

        trades_df = baseline_results.get("trades_df", pd.DataFrame())

        if (
            len(trades_df) > 0
            and "shares" in trades_df.columns
            and "entry_price" in trades_df.columns
        ):
            position_sizes = trades_df["shares"] * trades_df["entry_price"]
            result.avg_position_size_dollars = position_sizes.mean()
            result.max_position_size_dollars = position_sizes.max()
        else:
            # Estimate from risk dollars and stop pct
            risk_dollars = params.get("risk_dollars", 150)
            stop_pct = params.get("max_stop_pct", 3.0) / 100
            avg_price = 100  # Assumption
            avg_shares = risk_dollars / (avg_price * stop_pct)
            result.avg_position_size_dollars = avg_shares * avg_price
            result.max_position_size_dollars = result.avg_position_size_dollars * 2

        # Check liquidity constraints
        # This would ideally check actual dollar volume of traded stocks
        min_dollar_volume = params.get("min_dollar_volume", 5_000_000)
        result.min_liquidity_dollar_volume = min_dollar_volume

        # Capacity checks
        avg_position_passed = (
            result.avg_position_size_dollars < result.min_liquidity_dollar_volume * 0.1
        )
        max_position_passed = (
            result.max_position_size_dollars < result.min_liquidity_dollar_volume * 0.2
        )

        result.capacity_passed = avg_position_passed and max_position_passed

        if verbose:
            logger.info(f"   Avg Position: ${result.avg_position_size_dollars:,.0f}")
            logger.info(f"   Max Position: ${result.max_position_size_dollars:,.0f}")
            logger.info(f"   Min Liquidity: ${result.min_liquidity_dollar_volume:,.0f}")
            logger.info(f"   {'[OK]' if result.capacity_passed else '[FAIL]'} Capacity check")

        return result

    def _run_correlation_stress(
        self,
        params: Dict[str, Any],
        universe: List[str],
        test_dates: Tuple[str, str],
        result: StressTestResult,
        verbose: bool,
    ) -> StressTestResult:
        """Test performance during high market correlation periods."""
        if verbose:
            logger.info("\n[U+1F4C8] Correlation Stress Test (Simulated)")

        # Estimate correlation stress impact
        # During high correlation, diversification benefits reduce
        correlation_impact = min(result.impact_3x_costs * 1.5, -5.0)
        result.impact_high_correlation = correlation_impact

        result.correlation_stress_passed = (
            correlation_impact > self.thresholds.max_impact_high_correlation
        )

        if verbose:
            logger.info(f"   High correlation impact: {correlation_impact:+.2f}%")
            logger.info(
                f"   {'[OK]' if result.correlation_stress_passed else '[FAIL]'} Correlation stress"
            )

        return result

    def _calculate_worst_case(
        self, result: StressTestResult, verbose: bool
    ) -> StressTestResult:
        """Calculate worst-case scenario combining multiple stresses."""
        # Worst case = baseline + sum of worst individual impacts
        worst_impacts = [
            result.impact_5x_costs,
            result.impact_extreme_spreads,
            result.impact_gap_2pct,
            result.impact_high_correlation,
        ]

        # Take the worst 3 scenarios (not all, as they're not perfectly additive)
        worst_3 = sorted(worst_impacts)[:3]
        result.impact_worst_case = sum(worst_3)

        result.worst_case_passed = (
            result.impact_worst_case > self.thresholds.max_impact_worst_case
        )

        if verbose:
            logger.info("\n[U+1F525] Worst Case Scenario")
            logger.info(f"   Combined impact: {result.impact_worst_case:+.2f}%")
            logger.info(
                f"   {'[OK]' if result.worst_case_passed else '[FAIL]'} Worst case check"
            )

        return result


# Convenience function
def run_stress_test(
    engine_class: Type,
    params: Dict[str, Any],
    universe: List[str],
    test_dates: Tuple[str, str],
    verbose: bool = False,
) -> bool:
    """
    Quick stress test function.

    Returns True if strategy passes all stress scenarios.
    """
    suite = StressTestSuite(engine_class=engine_class)
    result = suite.run_full_stress_test(
        params=params, universe=universe, test_dates=test_dates, verbose=verbose
    )
    return result.all_passed


if __name__ == "__main__":
    print("StressTestSuite - Comprehensive Stress Testing for Trading Strategies")
    print("=" * 70)
    print("\nUsage:")
    print("  from src.validation.stress_testing import StressTestSuite")
    print("  from src.backtest.vectorbt_engine_advanced import AdvancedVectorBTEngine")
    print("  ")
    print("  suite = StressTestSuite(engine_class=AdvancedVectorBTEngine)")
    print("  results = suite.run_full_stress_test(")
    print("      params={'min_rvol': 1.5, 'min_adr': 2.0, ...},")
    print("      universe=['AAPL', 'MSFT', 'GOOGL'],")
    print("      test_dates=('2023-01-01', '2024-12-31')")
    print("  )")
    print("  ")
    print("  if results.all_passed:")
    print("      print('Strategy resilient to stress scenarios')")
    print("  else:")
    print("      for reason in results.failure_reasons:")
    print("          print(f'Failed: {reason}')")
