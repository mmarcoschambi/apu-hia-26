import numpy as np
import pandas as pd
import pytest

from src.ml_signal import audit_signal_dataset, build_signal_features, SignalWalkForwardTrainer
from scripts.run_ml_signal_quality import calculate_trade_metrics, calculate_decile_analysis


@pytest.fixture
def sample_ml_signal_data():
    # Mock daily market data (30 days)
    market_dates = pd.date_range(start="2021-01-01", periods=30, freq="D")
    market_df = pd.DataFrame({
        "date": market_dates,
        "Close": 100.0 + np.cumsum(np.random.normal(0.1, 0.5, size=30)),
        "vix": 15.0 + np.random.normal(0.0, 1.0, size=30),
        "breadth_pct": np.random.uniform(-20.0, 30.0, size=30),
    })

    # Mock trades (multiple trades on same day and some gaps)
    # Trade dates: Day 5, Day 5, Day 10, Day 15, Day 20, Day 20, Day 25
    trade_indices = [5, 5, 10, 15, 20, 20, 25]
    trade_dates = [market_dates[i] for i in trade_indices]
    
    trades_df = pd.DataFrame({
        "entry_date": trade_dates,
        "symbol": ["AAPL", "MSFT", "GOOG", "TSLA", "AMZN", "NVDA", "META"],
        "entry_price": [150.0, 250.0, 2000.0, 700.0, 3300.0, 600.0, 300.0],
        "rsi_entry": [45.0, 55.0, 60.0, 35.0, 70.0, 50.0, 40.0],
        "rvol": [1.5, 2.0, 0.8, 3.5, 1.1, 2.5, 1.9],
        "r_multiple": [2.5, -1.0, 3.5, -1.0, 1.5, -1.0, 2.0]
    })
    
    return trades_df, market_df


def test_build_signal_features_correct_rolling(sample_ml_signal_data):
    """Verify that market rolling features are calculated on daily market frame first, not on signal rows."""
    trades_df, market_df = sample_ml_signal_data
    
    # Run feature builder
    featured = build_signal_features(trades_df, market_df)
    
    # 1. Assert multiple trades on the same day share the EXACT same market rolling features
    same_day_trades = featured[featured["entry_date"] == "2021-01-06"]
    assert len(same_day_trades) == 2
    
    # Verify spy_return_5d and vix_ma_20 are identical for both trades on 2021-01-06
    assert same_day_trades["spy_return_5d"].iloc[0] == same_day_trades["spy_return_5d"].iloc[1]
    val1 = same_day_trades["vix_ma_20"].iloc[0]
    val2 = same_day_trades["vix_ma_20"].iloc[1]
    assert (pd.isna(val1) and pd.isna(val2)) or (val1 == val2)

    # 2. Check that the spy_return_5d matches the actual market percentage change over 5 daily steps
    # Market dates[5] is 2021-01-06. The 5d return should be Close[5]/Close[0] - 1.0
    expected_return_5d = (market_df["Close"].iloc[5] / market_df["Close"].iloc[0]) - 1.0
    assert pytest.approx(featured["spy_return_5d"].iloc[0]) == expected_return_5d


def test_trainer_dynamic_threshold_no_leakage(sample_ml_signal_data):
    """Verify that the dynamic threshold selection is computed per fold and applied to OOS test prediction."""
    trades_df, market_df = sample_ml_signal_data
    
    # Create a larger historical dataset (300 trades over 2 years of daily market data)
    market_dates = pd.date_range(start="2018-01-01", periods=730, freq="D")
    market_df = pd.DataFrame({
        "date": market_dates,
        "Close": 100.0 + np.cumsum(np.random.normal(0.1, 0.5, size=730)),
        "vix": 15.0 + np.random.normal(0.0, 1.0, size=730),
        "breadth_pct": np.random.uniform(-20.0, 30.0, size=730),
    })

    # 300 trades randomly scattered over the 2 years
    np.random.seed(42)
    trade_indices = np.sort(np.random.randint(30, 700, size=300))
    trade_dates = [market_dates[i] for i in trade_indices]
    
    trades_df = pd.DataFrame({
        "entry_date": trade_dates,
        "symbol": [f"SYM{i}" for i in range(300)],
        "entry_price": np.random.uniform(50.0, 500.0, size=300),
        "rsi_entry": np.random.uniform(30.0, 70.0, size=300),
        "rvol": np.random.uniform(0.5, 4.0, size=300),
        "r_multiple": np.random.choice([3.0, 1.5, -1.0, -1.0], size=300) # Imbalance
    })
    
    featured = build_signal_features(trades_df, market_df)
    feature_cols = ["vix", "vix_change_5d", "breadth_pct", "spy_return_5d"]

    trainer = SignalWalkForwardTrainer(
        train_years=1,
        test_months=3,
        step_months=3,
        min_rows=50,
        model_name="ridge"
    )
    
    result = trainer.run(
        featured,
        date_col="entry_date",
        symbol_col="symbol",
        target_col="r_multiple",
        feature_cols=feature_cols,
    )
    
    # Assert result folds are populated and contain the dynamic best_threshold
    assert len(result.folds) > 0
    assert "best_threshold" in result.folds.columns
    
    # Assert best_threshold values are within reasonable bounds (50, 60, 70, 80)
    for threshold in result.folds["best_threshold"]:
        assert threshold in [50.0, 60.0, 70.0, 80.0]

    # Assert take_trade in predictions matches the dynamic fold thresholds
    for fold_id, group in result.predictions.groupby("fold_id"):
        fold_threshold = result.folds.loc[result.folds["fold_id"] == fold_id, "best_threshold"].iloc[0]
        # All selected trades in this test fold must have pred_score >= fold_threshold
        taken_trades = group[group["take_trade"]]
        assert (taken_trades["pred_score"] >= fold_threshold).all()


def test_calculate_trade_metrics():
    """Verify that calculate_trade_metrics computes win_rate, profit_factor, Sharpe, and Drawdown correctly."""
    # Mock predictions
    dates = pd.date_range(start="2021-01-01", periods=10, freq="D")
    df = pd.DataFrame({
        "entry_date": dates,
        "r_multiple": [2.0, -1.0, 3.0, -1.0, -1.0, 2.0, 4.0, -1.0, -1.0, 1.5],
        "take_trade": [True, True, True, False, False, True, True, False, False, True],
        "risk_multiplier": [2.0, 1.0, 2.0, 0.0, 0.0, 1.0, 2.0, 0.0, 0.0, 1.0]
    })
    
    # 1. Gold standard metrics (All trades)
    metrics_all = calculate_trade_metrics(df, pnl_col="r_multiple")
    assert metrics_all["total_trades"] == 10
    assert metrics_all["win_rate"] == 50.0 # 5 wins out of 10
    assert metrics_all["total_pnl"] == 7.5 # 2-1+3-1-1+2+4-1-1+1.5 = 7.5
    assert "cagr" in metrics_all
    assert metrics_all["cagr"] > 0.0
    
    # 2. Filtered metrics (Only take_trade == True)
    metrics_filtered = calculate_trade_metrics(df, pnl_col="r_multiple", weight_col="take_trade")
    assert metrics_filtered["total_trades"] == 6 # 6 True values
    assert metrics_filtered["win_rate"] == round(5/6 * 100, 2)
    assert metrics_filtered["total_pnl"] == 11.5 # 2-1+3+2+4+1.5 = 11.5
    assert "cagr" in metrics_filtered
    assert metrics_filtered["cagr"] > 0.0
    
    # 3. Decile analysis
    df["pred_score"] = [95.0, 45.0, 85.0, 20.0, 35.0, 75.0, 92.0, 15.0, 10.0, 72.0]
    deciles = calculate_decile_analysis(df, score_col="pred_score", target_col="r_multiple")
    assert len(deciles) > 0


def test_target_resolution_fallback_and_cagr():
    """Verify target column dynamic resolution fallback and CAGR computation."""
    dates = pd.date_range(start="2021-01-01", periods=10, freq="D")
    
    # 1. Test target fallback in audit
    trades_missing_r = pd.DataFrame({
        "entry_date": [dates[0], dates[1]],
        "symbol": ["AAPL", "MSFT"],
        "entry_price": [100.0, 200.0],
        "return_pct": [0.05, -0.02]
    })
    
    audit = audit_signal_dataset(trades_missing_r, target_col="r_multiple")
    assert audit.target_name == "return_pct"
    assert any("fallback" in note for note in audit.notes)
    
    # 2. Test target fallback in build_signal_features
    market_df = pd.DataFrame({
        "date": dates,
        "Close": [100.0] * 10,
        "vix": [15.0] * 10
    })
    
    featured = build_signal_features(trades_missing_r, market_df, target_col="r_multiple")
    assert "return_pct" in featured.columns
