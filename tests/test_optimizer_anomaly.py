"""
Regression tests for Issue #53: Optimizer anomaly - profit_factor=999 / win_rate=100%

Tests the REAL production function compute_profit_factor() extracted from
src/backtest/vectorbt_engine_advanced.py.

Decision criteria (documented in DECISIONS.md):
- profit_factor = 999.0 is an INTENTIONAL sentinel when total_loss == 0.
- With <= 5 trades it signals expected HPO overfitting, NOT data leakage.
- With > 20 trades and win_rate == 1.0 it must be escalated for leakage review.
"""

import unittest
import pandas as pd

from src.backtest.vectorbt_engine_advanced import compute_profit_factor


def _trades(pnl_values: list) -> pd.DataFrame:
    """Helper: build a minimal trades_df from a list of pnl values."""
    return pd.DataFrame({"pnl": pnl_values})


class TestComputeProfitFactor(unittest.TestCase):
    """
    Unit tests for compute_profit_factor() — the canonical profit-factor
    calculation extracted from AdvancedVectorBTEngine (Issue #53 fix).
    """

    def test_sentinel_all_winners_small_sample(self):
        """
        Sentinel: total_loss == 0 and total_profit > 0 with a tiny sample
        (<= 5 trades) must return 999.0.
        """
        trades = _trades([100.0, 200.0, 150.0])  # 3 winners, 0 losers
        pf = compute_profit_factor(trades)
        self.assertEqual(pf, 999.0)

    def test_sentinel_all_winners_boundary(self):
        """Boundary: exactly 5 all-winner trades still returns the sentinel."""
        trades = _trades([50.0, 60.0, 70.0, 80.0, 90.0])
        pf = compute_profit_factor(trades)
        self.assertEqual(pf, 999.0)

    def test_sentinel_large_sample_still_999(self):
        """
        With > 20 all-winner trades compute_profit_factor still returns 999.0.
        Detection of potential leakage is the CALLER's responsibility, not this function.
        """
        trades = _trades([100.0] * 25)
        pf = compute_profit_factor(trades)
        self.assertEqual(pf, 999.0)

    def test_normal_ratio_when_losses_exist(self):
        """Real ratio returned when both winners and losers exist."""
        trades = _trades([300.0, 200.0, -100.0, -50.0])
        pf = compute_profit_factor(trades)
        self.assertAlmostEqual(pf, 500.0 / 150.0, places=4)
        self.assertNotEqual(pf, 999.0)

    def test_zero_when_all_losers(self):
        """Returns 0.0 when there are only losses (total_profit == 0)."""
        trades = _trades([-100.0, -200.0])
        pf = compute_profit_factor(trades)
        self.assertEqual(pf, 0.0)

    def test_zero_on_empty_dataframe(self):
        """Returns 0.0 for an empty trades_df (no trades at all)."""
        trades = _trades([])
        pf = compute_profit_factor(trades)
        self.assertEqual(pf, 0.0)

    def test_zero_on_none(self):
        """Returns 0.0 gracefully when trades_df is None."""
        pf = compute_profit_factor(None)
        self.assertEqual(pf, 0.0)

    def test_leakage_detection_criterion(self):
        """
        Documents the leakage escalation rule: profit_factor == 999.0 AND
        trade_count > 20 is what the optimizer layer should flag for review.
        compute_profit_factor() itself does not raise; the caller checks.
        """
        trades = _trades([100.0] * 25)
        pf = compute_profit_factor(trades)
        trade_count = len(trades)

        is_potential_leakage = pf == 999.0 and trade_count > 20
        self.assertTrue(
            is_potential_leakage,
            f"profit_factor=999.0 with {trade_count} trades must be escalated by the caller",
        )

    def test_not_leakage_small_sample(self):
        """
        profit_factor == 999.0 with <= 5 trades must NOT be flagged as leakage.
        """
        trades = _trades([100.0] * 4)
        pf = compute_profit_factor(trades)
        trade_count = len(trades)

        is_potential_leakage = pf == 999.0 and trade_count > 20
        self.assertFalse(
            is_potential_leakage,
            f"profit_factor=999.0 with {trade_count} trades must NOT be escalated",
        )


if __name__ == "__main__":
    unittest.main()
