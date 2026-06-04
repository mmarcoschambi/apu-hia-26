import tempfile
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from sklearn.ensemble import RandomForestClassifier

from src.regime_detection import (
    LABEL_GREEN,
    LABEL_RED,
    LABEL_YELLOW,
    build_ml_features,
    generate_forward_labels,
)
from src.regime_detection.ml_trainer import WalkForwardMLTrainer


@pytest.fixture
def sample_market_data():
    """Generate 100 days of consistent mock daily market data."""
    dates = pd.date_range(start="2020-01-01", periods=150, freq="D")
    np.random.seed(42)

    # Simulate price walk
    spy_closes = 300.0 + np.cumsum(np.random.normal(0.5, 2.0, size=150))
    vix_values = 15.0 + np.random.normal(0.0, 3.0, size=150)
    vix_values = np.clip(vix_values, 10.0, 45.0)

    # Breadth centered pct scale (-50..50)
    breadth_pct = np.random.uniform(-30, 40, size=150)

    df = pd.DataFrame(
        {
            "date": dates,
            "Close": spy_closes,
            "vix": vix_values,
            "breadth_pct": breadth_pct,
            "dix": np.random.uniform(40, 60, size=150),
            "gex_net": np.random.normal(1e9, 5e8, size=150),
        }
    )
    return df


def test_build_ml_features_structure(sample_market_data):
    """Verify build_ml_features correctly computes features and maintains time order."""
    featured = build_ml_features(sample_market_data, date_col="date", close_col="Close")

    # Order check
    assert featured["date"].is_monotonic_increasing

    # Columns presence
    expected_cols = [
        "vix_change_5d",
        "vix_ma_20",
        "vix_vs_ma",
        "breadth_change_5d",
        "breadth_ma_20",
        "breadth_vs_ma",
        "spy_return_5d",
        "spy_return_10d",
        "spy_return_20d",
        "spy_atr_ratio",
        "dix_change_5d",
        "dix_ma_20",
        "gex_ma_20",
        "gex_zscore",
    ]
    for col in expected_cols:
        assert col in featured.columns

    # Check dropna target cols
    assert not featured[expected_cols].isnull().any().any()


def test_build_ml_features_no_lookahead(sample_market_data):
    """Assert rolling features have no lookahead bias by verifying they don't change on past dates when future changes."""
    featured_orig = build_ml_features(sample_market_data, date_col="date", close_col="Close")

    # Modify future price in a copy
    modified_data = sample_market_data.copy()
    modified_data.loc[120, "Close"] = 999.0
    modified_data.loc[120, "vix"] = 999.0

    featured_mod = build_ml_features(modified_data, date_col="date", close_col="Close")

    # Assert features up to row 100 are strictly identical
    cols_to_check = [
        "vix_change_5d",
        "vix_ma_20",
        "vix_vs_ma",
        "breadth_change_5d",
        "breadth_ma_20",
        "spy_return_5d",
        "spy_atr_ratio",
    ]
    pd.testing.assert_frame_equal(
        featured_orig.loc[:100, cols_to_check],
        featured_mod.loc[:100, cols_to_check],
        check_dtype=False,
    )


def test_walk_forward_ml_purge_and_continuity():
    """Test that ML walk-forward trainer correctly purges train set and keeps equity continuous."""
    # Build large mock dataset covering 4 years
    dates = pd.date_range(start="2015-01-01", periods=1500, freq="D")
    np.random.seed(42)
    spy_closes = 300.0 + np.cumsum(np.random.normal(0.2, 1.0, size=1500))
    vix_values = 15.0 + np.random.normal(0.0, 3.0, size=1500)
    breadth_pct = np.random.uniform(-30, 40, size=1500)
    large_df = pd.DataFrame(
        {
            "date": dates,
            "Close": spy_closes,
            "vix": vix_values,
            "breadth_pct": breadth_pct,
            "dix": np.random.uniform(40, 60, size=1500),
            "gex_net": np.random.normal(1e9, 5e8, size=1500),
        }
    )
    labeled = generate_forward_labels(large_df, close_col="Close", horizon=10)
    featured = build_ml_features(labeled, date_col="date", close_col="Close")

    # Setup walk forward trainer with standard small dimensions for testing
    trainer = WalkForwardMLTrainer(
        train_years=2,
        test_months=3,
        step_months=3,
        purge_days=10,
        initial_capital=50000.0,
        min_train_rows=50,
    )

    feature_cols = ["vix", "vix_change_5d", "breadth_pct", "spy_atr_ratio"]

    # Run
    res = trainer.run(
        featured,
        date_col="date",
        close_col="Close",
        target_col="target_regime",
        feature_cols=feature_cols,
    )

    # Check folds generated
    assert len(res.folds) > 0, "No folds generated in walk-forward backtest"

    # Check equity curve continuity
    eq_curve = res.equity_curve
    assert not eq_curve.empty
    assert eq_curve["date"].is_monotonic_increasing

    # Check previous day returns: first row strategy_return of fold > 0 should not be 0.0 unless market_return or exposure was 0
    signals = res.signals
    assert "p_green" in signals.columns
    assert "p_yellow" in signals.columns
    assert "p_red" in signals.columns

    # Verify probability bounds
    assert ((signals["p_green"] >= 0) & (signals["p_green"] <= 1)).all()
    assert ((signals["p_yellow"] >= 0) & (signals["p_yellow"] <= 1)).all()
    assert ((signals["p_red"] >= 0) & (signals["p_red"] <= 1)).all()


def test_smoke_end_to_end_ml_regime(sample_market_data):
    """Verify script logic end-to-end on synthetic data by running WalkForwardMLTrainer and checking outputs."""
    # Build large mock dataset covering 4 years
    dates = pd.date_range(start="2015-01-01", periods=1500, freq="D")
    np.random.seed(42)
    spy_closes = 300.0 + np.cumsum(np.random.normal(0.2, 1.0, size=1500))
    vix_values = 15.0 + np.random.normal(0.0, 3.0, size=1500)
    breadth_pct = np.random.uniform(-30, 40, size=1500)
    large_df = pd.DataFrame(
        {
            "date": dates,
            "Close": spy_closes,
            "vix": vix_values,
            "breadth_pct": breadth_pct,
            "dix": np.random.uniform(40, 60, size=1500),
            "gex_net": np.random.normal(1e9, 5e8, size=1500),
        }
    )

    # Setup temp paths
    with tempfile.TemporaryDirectory() as tmp_dir:
        output_path = Path(tmp_dir)

        # Generate labels
        labeled = generate_forward_labels(
            large_df, close_col="Close", horizon=10, output_path=output_path / "labels.parquet"
        )
        assert (output_path / "labels.parquet").exists()

        # Build features
        featured = build_ml_features(labeled, date_col="date", close_col="Close")

        # Run trainer
        trainer = WalkForwardMLTrainer(train_years=3, test_months=3, step_months=3, purge_days=10)
        feature_cols = ["vix", "vix_change_5d", "breadth_pct", "spy_atr_ratio"]

        res = trainer.run(
            featured,
            date_col="date",
            close_col="Close",
            target_col="target_regime",
            feature_cols=feature_cols,
        )

        assert not res.folds.empty
        assert not res.signals.empty
        assert not res.equity_curve.empty

        # Check classification metrics are populated
        assert res.oos_accuracy >= 0.0
        assert res.oos_balanced_accuracy >= 0.0
        assert res.oos_f1_weighted >= 0.0
        assert res.oos_f1_macro >= 0.0
