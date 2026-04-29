"""
tests/test_multi_asset_isolation.py
====================================

Valida que el screening y backtesting de múltiples activos NO tenga
fugas de estado entre tickers.

Escenarios:
  1. Screener isolation: 3 activos sintéticos (FLAT, TREND, DOWN) screened
     en secuencia — el resultado de uno NO debe afectar al siguiente.
  2. Engine clone isolation: clone_with_params no debe compartir estado
     mutable (rejection_stats, regime_risk_multipliers) entre clones.
  3. DataFrame reference safety: DataFrames OHLCV compartidos no deben
     ser modificados por run_backtest().

Ejecutar:
    cd /home/marcos/trade/momentum-v2
    python -m pytest tests/test_multi_asset_isolation.py -v
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import unittest
import numpy as np
import pandas as pd
from unittest.mock import patch, MagicMock

from src.screeners import ScreenerRegistry, ScreenerResult
from src.screeners.base import ScreenerConfig


# ──────────────────────────────────────────────
# Synthetic OHLCV data generators
# ──────────────────────────────────────────────


def _make_trending_df(n: int = 300, start: float = 50.0) -> pd.DataFrame:
    """Strong uptrend → should pass trend-based screeners."""
    np.random.seed(42)
    dates = pd.date_range("2023-01-01", periods=n, freq="B")
    close = start + 0.15 * np.arange(n) + np.random.randn(n) * 0.3
    close = np.maximum(close, 5.0)
    return pd.DataFrame(
        {
            "open": close * 0.995,
            "high": close * 1.012,
            "low": close * 0.988,
            "close": close,
            "volume": np.random.uniform(2_000_000, 8_000_000, n),
            "adr_pct": np.full(n, 3.5),
        },
        index=dates,
    )


def _make_declining_df(n: int = 300, start: float = 80.0) -> pd.DataFrame:
    """Downtrend → should fail trend-based screeners."""
    np.random.seed(7)
    dates = pd.date_range("2023-01-01", periods=n, freq="B")
    close = start - 0.12 * np.arange(n) + np.random.randn(n) * 0.4
    close = np.maximum(close, 5.0)
    return pd.DataFrame(
        {
            "open": close * 0.995,
            "high": close * 1.01,
            "low": close * 0.99,
            "close": close,
            "volume": np.random.uniform(500_000, 2_000_000, n),
            "adr_pct": np.full(n, 2.0),
        },
        index=dates,
    )


def _make_flat_df(n: int = 300, price: float = 30.0) -> pd.DataFrame:
    """Sideways / flat → should fail momentum screeners."""
    np.random.seed(99)
    dates = pd.date_range("2023-01-01", periods=n, freq="B")
    close = price + np.random.randn(n) * 0.15
    close = np.maximum(close, 5.0)
    return pd.DataFrame(
        {
            "open": close * 0.998,
            "high": close * 1.005,
            "low": close * 0.995,
            "close": close,
            "volume": np.random.uniform(100_000, 500_000, n),
            "adr_pct": np.full(n, 0.8),
        },
        index=dates,
    )


# ──────────────────────────────────────────────
# Test 1: Screener isolation
# ──────────────────────────────────────────────


class TestScreenerIsolation(unittest.TestCase):
    """
    Three synthetic assets screened sequentially:
      - FLAT: sideways, low volume → should FAIL
      - TREND: strong uptrend, high volume → should PASS
      - DOWN: downtrend → should FAIL

    The result of one must NOT affect the next.
    """

    def setUp(self):
        self.df_flat = _make_flat_df()
        self.df_trend = _make_trending_df()
        self.df_down = _make_declining_df()

    def test_screener_results_are_independent(self):
        """Each ticker's screener result is independent of prior calls."""
        screener = ScreenerRegistry.get("minervini_trend")

        results = {}
        for ticker, df in [
            ("FLAT", self.df_flat),
            ("TREND", self.df_trend),
            ("DOWN", self.df_down),
        ]:
            result = screener.scan(ticker, df)
            self.assertIsInstance(result, ScreenerResult)
            self.assertEqual(result.ticker, ticker)
            results[ticker] = result

        # TREND should pass (strong uptrend, good volume)
        self.assertTrue(
            results["TREND"].passed, "TREND should pass minervini_trend screener"
        )

        # FLAT should fail (no trend, low volume)
        self.assertFalse(
            results["FLAT"].passed, "FLAT should fail minervini_trend screener"
        )

        # DOWN should fail (downtrend)
        self.assertFalse(
            results["DOWN"].passed, "DOWN should fail minervini_trend screener"
        )

    def test_screener_new_instance_per_get(self):
        """ScreenerRegistry.get() returns a fresh instance each time."""
        s1 = ScreenerRegistry.get("minervini_trend")
        s2 = ScreenerRegistry.get("minervini_trend")
        self.assertIsNot(s1, s2, "Each get() should return a new instance")

    def test_screener_no_state_leakage(self):
        """Screening TREND first, then FLAT — FLAT must still fail."""
        screener = ScreenerRegistry.get("minervini_trend")

        result_trend = screener.scan("TREND", self.df_trend)
        self.assertTrue(result_trend.passed)

        result_flat = screener.scan("FLAT", self.df_flat)
        self.assertFalse(
            result_flat.passed,
            "FLAT must fail even after TREND passed — no state leakage",
        )

    def test_screener_ticker_field_is_correct(self):
        """Each ScreenerResult has the correct ticker field."""
        screener = ScreenerRegistry.get("minervini_trend")
        for ticker, df in [
            ("FLAT", self.df_flat),
            ("TREND", self.df_trend),
            ("DOWN", self.df_down),
        ]:
            result = screener.scan(ticker, df)
            self.assertEqual(result.ticker, ticker)


# ──────────────────────────────────────────────
# Test 2: Engine clone isolation
# ──────────────────────────────────────────────


class TestEngineCloneIsolation(unittest.TestCase):
    """
    Validates that clone_with_params creates isolated clones
    without sharing mutable state.
    """

    def test_clone_resets_rejection_stats(self):
        """clone_with_params resets rejection_stats_tier to empty dict."""
        try:
            from src.backtest.vectorbt_engine_advanced import AdvancedVectorBTEngine
        except ImportError:
            self.skipTest("AdvancedVectorBTEngine not available")

        engine = AdvancedVectorBTEngine(
            universe=["AAPL"],
            start_date="2023-01-01",
            end_date="2023-12-31",
            initial_capital=100_000,
        )
        # Simulate accumulated state from a prior run
        engine.rejection_stats_tier = {"TIER1": 42, "TIER2": 17}
        engine.rejection_details_df = pd.DataFrame({"dummy": [1, 2, 3]})
        engine.regime_risk_multipliers = {"2023-01-01": 1.5, "2023-02-01": 0.8}

        clone = engine.clone_with_params(min_rvol=1.0)

        self.assertEqual(clone.rejection_stats_tier, {})
        self.assertIsNone(clone.rejection_details_df)
        self.assertEqual(clone.regime_risk_multipliers, {})

        # Original must be untouched
        self.assertEqual(engine.rejection_stats_tier, {"TIER1": 42, "TIER2": 17})
        self.assertIsNotNone(engine.rejection_details_df)
        self.assertEqual(len(engine.regime_risk_multipliers), 2)

    def test_clone_does_not_share_mutable_dicts(self):
        """Mutating clone's rejection_stats doesn't affect original."""
        try:
            from src.backtest.vectorbt_engine_advanced import AdvancedVectorBTEngine
        except ImportError:
            self.skipTest("AdvancedVectorBTEngine not available")

        engine = AdvancedVectorBTEngine(
            universe=["AAPL"],
            start_date="2023-01-01",
            end_date="2023-12-31",
            initial_capital=100_000,
        )
        clone = engine.clone_with_params(min_rvol=1.0)

        # Mutate clone
        clone.rejection_stats_tier["TIER1"] = 100

        # Original must be empty
        self.assertEqual(engine.rejection_stats_tier, {})

    def test_clone_preserves_new_params(self):
        """clone_with_params correctly applies new parameters."""
        try:
            from src.backtest.vectorbt_engine_advanced import AdvancedVectorBTEngine
        except ImportError:
            self.skipTest("AdvancedVectorBTEngine not available")

        engine = AdvancedVectorBTEngine(
            universe=["AAPL"],
            start_date="2023-01-01",
            end_date="2023-12-31",
            initial_capital=100_000,
            min_rvol=1.5,
        )
        clone = engine.clone_with_params(min_rvol=2.5, tp1_r=2.0)

        self.assertEqual(clone.min_rvol, 2.5)
        self.assertEqual(clone.tp1_r, 2.0)
        # Original unchanged
        self.assertEqual(engine.min_rvol, 1.5)


# ──────────────────────────────────────────────
# Test 3: DataFrame reference safety
# ──────────────────────────────────────────────


class TestDataFrameReferenceSafety(unittest.TestCase):
    """
    Validates that shared DataFrames between template and clones
    are not mutated by run_backtest().
    """

    def test_template_close_not_mutated_by_clone(self):
        """Template's close DataFrame hash is unchanged after clone operations."""
        try:
            from src.backtest.vectorbt_engine_advanced import AdvancedVectorBTEngine
        except ImportError:
            self.skipTest("AdvancedVectorBTEngine not available")

        # Create a minimal engine with synthetic data
        close_data = pd.DataFrame(
            {"AAPL": np.linspace(100, 150, 50)},
            index=pd.date_range("2023-01-01", periods=50, freq="B"),
        )
        high_data = close_data * 1.01
        low_data = close_data * 0.99
        open_data = close_data * 0.998
        volume_data = pd.DataFrame(
            {"AAPL": np.full(50, 5_000_000.0)},
            index=close_data.index,
        )

        engine = AdvancedVectorBTEngine(
            universe=["AAPL"],
            start_date="2023-01-01",
            end_date="2023-12-31",
            initial_capital=100_000,
        )
        # Inject synthetic data directly (skip cache/DB)
        engine.close = close_data.copy()
        engine.high = high_data.copy()
        engine.low = low_data.copy()
        engine.open = open_data.copy()
        engine.volume = volume_data.copy()

        # Record original state
        original_close_hash = hash(engine.close.values.tobytes())
        original_close_sum = engine.close["AAPL"].sum()

        # Clone and mutate clone's rejection stats (simulating run_backtest behavior)
        clone = engine.clone_with_params(min_rvol=1.0)
        clone.rejection_stats_tier["TIER1"] = 50
        clone.rejection_details_df = pd.DataFrame({"test": [1]})

        # Template must be completely unchanged
        self.assertEqual(hash(engine.close.values.tobytes()), original_close_hash)
        self.assertAlmostEqual(engine.close["AAPL"].sum(), original_close_sum)
        self.assertEqual(engine.rejection_stats_tier, {})

    def test_template_survives_clone_run_backtest(self):
        """Smoke test: clone.run_backtest() does NOT mutate template DataFrames.

        This is a regression test: if run_backtest ever does df.fillna(inplace=True)
        or any in-place mutation on a shared DataFrame, this test will catch it.
        """
        try:
            from src.backtest.vectorbt_engine_advanced import AdvancedVectorBTEngine
        except ImportError:
            self.skipTest("AdvancedVectorBTEngine not available")

        n_days = 250
        tickers = ["AAPL", "MSFT", "GOOGL"]
        dates = pd.date_range("2023-01-03", periods=n_days, freq="B")

        np.random.seed(42)
        close = pd.DataFrame(
            np.random.uniform(100, 200, (n_days, len(tickers))).astype(np.float32),
            index=dates,
            columns=tickers,
        )
        high = (close * 1.012).astype(np.float32)
        low = (close * 0.988).astype(np.float32)
        volume = pd.DataFrame(
            np.random.uniform(1e6, 1e7, (n_days, len(tickers))).astype(np.float32),
            index=dates,
            columns=tickers,
        )

        template = AdvancedVectorBTEngine(
            universe=tickers,
            start_date="2023-01-03",
            end_date="2023-12-31",
            initial_capital=100_000,
            mode="convergence",
            offline_mode=True,
            use_pit_universe=False,
            use_market_regime_filter=False,
            require_spy_above_sma50=False,
            use_dynamic_thresholds=False,
            use_adaptive_filtering=False,
            require_positive_rs=False,
            use_rs_percentile=False,
            use_sma50_atr_filter=False,
            use_pattern_filter=False,
            use_earnings_calendar=False,
            signal_type="breakout",
        )
        template.close = close.copy()
        template.high = high.copy()
        template.low = low.copy()
        template.open = (close * 0.998).astype(np.float32)
        template.volume = volume.copy()

        avg_vol_20 = (
            volume.rolling(20, min_periods=1).mean().fillna(1).astype(np.float32)
        )
        template.sma_20 = close.rolling(20, min_periods=1).mean().astype(np.float32)
        template.sma_50 = close.rolling(50, min_periods=1).mean().astype(np.float32)
        template.avg_volume_20 = avg_vol_20
        template.rvol = (volume / avg_vol_20).fillna(1.0).astype(np.float32)
        template.adr_pct = (
            ((high - low) / low * 100)
            .rolling(20, min_periods=1)
            .mean()
            .fillna(0)
            .astype(np.float32)
        )
        template.ema_8 = (
            close.ewm(span=8, adjust=False, min_periods=1).mean().astype(np.float32)
        )
        template.ema_10 = (
            close.ewm(span=10, adjust=False, min_periods=1).mean().astype(np.float32)
        )
        template.ema_21 = (
            close.ewm(span=21, adjust=False, min_periods=1).mean().astype(np.float32)
        )
        template.spy_close = pd.Series(
            np.full(n_days, 450.0, dtype=np.float32), index=dates
        )
        template.vix_close = pd.Series(
            np.full(n_days, 15.0, dtype=np.float32), index=dates
        )
        template.spy_sma50 = pd.Series(
            np.full(n_days, 440.0, dtype=np.float32), index=dates
        )

        # Consolidation metrics (BB-based)
        high_20 = high.rolling(20, min_periods=1).max()
        low_20 = low.rolling(20, min_periods=1).min()
        template.consolidation_range = (
            ((high_20 - low_20) / low_20 * 100).fillna(0).astype(np.float32)
        )
        sma_20_for_bb = close.rolling(20, min_periods=1).mean().fillna(0)
        bb_std = close.rolling(20).std().fillna(0)
        bb_upper = sma_20_for_bb + (bb_std * 2)
        bb_lower = sma_20_for_bb - (bb_std * 2)
        inside_bb = (close >= bb_lower) & (close <= bb_upper)
        template.consolidation_days = (
            inside_bb.rolling(20, min_periods=1).sum().fillna(0).astype(np.float32)
        )
        template.high_20 = high_20.astype(np.float32)
        template.low_20 = low_20.astype(np.float32)
        template.trend_aligned = pd.DataFrame(0, index=dates, columns=tickers).astype(
            np.float32
        )

        # Snapshot all shared DataFrames BEFORE clone backtest
        snapshot = {
            "close": (
                hash(template.close.values.tobytes()),
                template.close.values.copy(),
            ),
            "high": (hash(template.high.values.tobytes()), template.high.values.copy()),
            "low": (hash(template.low.values.tobytes()), template.low.values.copy()),
            "volume": (
                hash(template.volume.values.tobytes()),
                template.volume.values.copy(),
            ),
            "sma_20": (
                hash(template.sma_20.values.tobytes()),
                template.sma_20.values.copy(),
            ),
            "avg_volume_20": (
                hash(template.avg_volume_20.values.tobytes()),
                template.avg_volume_20.values.copy(),
            ),
            "rvol": (hash(template.rvol.values.tobytes()), template.rvol.values.copy()),
            "adr_pct": (
                hash(template.adr_pct.values.tobytes()),
                template.adr_pct.values.copy(),
            ),
            "ema_8": (
                hash(template.ema_8.values.tobytes()),
                template.ema_8.values.copy(),
            ),
            "ema_10": (
                hash(template.ema_10.values.tobytes()),
                template.ema_10.values.copy(),
            ),
            "ema_21": (
                hash(template.ema_21.values.tobytes()),
                template.ema_21.values.copy(),
            ),
        }

        # Clone and run full backtest
        clone = template.clone_with_params(
            min_rvol=0.5,
            min_adr=1.0,
            max_dist_sma20=20.0,
            min_dollar_volume=500_000,
            min_volume=50_000,
            min_consolidation_days=3,
            tp1_r=1.5,
            tp2_r=3.0,
            tp1_pct=0.5,
            tp2_pct=0.3,
            runner_pct=0.2,
            risk_dollars=500,
            use_fixed_dollar_risk=True,
            use_atr_stop=True,
            atr_stop_multiplier=1.5,
            max_stop_pct=8.0,
            use_trailing_stop=False,
            atr_trailing_multiplier=1.0,
            max_exposure_pct=0.5,
            require_spy_above_sma50=False,
            use_market_regime_filter=False,
            use_dynamic_thresholds=False,
            use_adaptive_filtering=False,
            require_positive_rs=False,
            use_rs_percentile=False,
            use_pattern_filter=False,
            log_rejections=False,
        )
        results = clone.run_backtest()

        # Verify clone produced some output (not necessarily profitable)
        self.assertIsInstance(results, dict)
        self.assertIn("total_trades", results)

        # Verify template DataFrames are byte-identical after clone's run_backtest
        for attr_name, (orig_hash, orig_values) in snapshot.items():
            df = getattr(template, attr_name)
            after_hash = hash(df.values.tobytes())
            self.assertEqual(
                after_hash,
                orig_hash,
                f"Template.{attr_name} was MUTATED by clone.run_backtest()! "
                f"hash changed: {orig_hash} -> {after_hash}",
            )
            np.testing.assert_array_equal(
                df.values,
                orig_values,
                err_msg=f"Template.{attr_name} values changed after clone.run_backtest()",
            )


# ──────────────────────────────────────────────
# Test 4: End-to-end multi-asset screening
# ──────────────────────────────────────────────


class TestMultiAssetScreening(unittest.TestCase):
    """
    End-to-end test: screen 3 assets with a mocked MarketDataProvider
    and verify isolation.
    """

    def test_apply_screener_isolates_assets(self):
        """apply_screener_to_universe processes each ticker independently."""
        from optimize_3tier import apply_screener_to_universe

        df_trend = _make_trending_df()
        df_flat = _make_flat_df()
        df_down = _make_declining_df()

        mock_market_data = MagicMock()
        mock_market_data.get_daily_data.side_effect = lambda ticker, start, end: {
            "TREND": df_trend,
            "FLAT": df_flat,
            "DOWN": df_down,
        }.get(ticker)

        with patch("optimize_3tier.MarketDataProvider", return_value=mock_market_data):
            result = apply_screener_to_universe(
                universe=["FLAT", "TREND", "DOWN"],
                screener_name="minervini_trend",
                start_date="2023-01-01",
                end_date="2023-12-31",
            )

        # TREND should pass, others should fail
        self.assertIn("TREND", result)
        self.assertNotIn("FLAT", result)
        self.assertNotIn("DOWN", result)

    def test_apply_screener_handles_empty_data(self):
        """apply_screener_to_universe skips tickers with no data."""
        from optimize_3tier import apply_screener_to_universe

        mock_market_data = MagicMock()
        mock_market_data.get_daily_data.return_value = None

        with patch("optimize_3tier.MarketDataProvider", return_value=mock_market_data):
            result = apply_screener_to_universe(
                universe=["NO_DATA"],
                screener_name="minervini_trend",
                start_date="2023-01-01",
                end_date="2023-12-31",
            )

        # Falls back to raw universe when no ticker passes
        self.assertEqual(result, ["NO_DATA"])


if __name__ == "__main__":
    unittest.main()
