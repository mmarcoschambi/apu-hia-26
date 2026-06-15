import pytest
import pandas as pd
import numpy as np
from src.signals.signal_engine import evaluate_ticker, Tier2Metrics, SignalMode
from src.data.theme_taxonomy import TAXONOMY_VERSION

def test_theme_filter_above_sma20():
    # Mock data
    df = pd.DataFrame({
        "open": [100]*70,
        "high": [105]*70,
        "low": [95]*70,
        "close": [101]*70,
        "volume": [1000000]*70
    })
    
    combo_cfg = {
        "tier2_filters": {
            "use_theme_group_filter": True,
            "theme_filter_mode": "above_sma20",
            "theme_dist_threshold": 0.0
        }
    }
    
    # Theme below SMA20 (dist = -0.01)
    res_fail = evaluate_ticker(
        ticker="AAPL",
        df=df,
        spy_df=None,
        combo_cfg=combo_cfg,
        theme_dist=-0.01
    )
    assert res_fail.passed is False
    assert "tier2_fail:theme_group:dist" in res_fail.reject_reason
    
    # Theme above SMA20 (dist = 0.01)
    res_pass = evaluate_ticker(
        ticker="AAPL",
        df=df,
        spy_df=None,
        combo_cfg=combo_cfg,
        theme_dist=0.01
    )
    assert res_pass.passed is True

def test_theme_filter_divergence():
    # Mock data
    df = pd.DataFrame({
        "open": [100]*70,
        "high": [105]*70,
        "low": [95]*70,
        "close": [101]*70,
        "volume": [1000000]*70
    })
    
    combo_cfg = {
        "tier2_filters": {
            "use_theme_group_filter": True,
            "theme_filter_mode": "divergence"
        }
    }
    
    # Theme OK (0.02), Sector OK (0.01) -> No divergence (sector must be <= 0)
    res_fail = evaluate_ticker(
        ticker="AAPL",
        df=df,
        spy_df=None,
        combo_cfg=combo_cfg,
        theme_dist=0.02,
        sector_etf_dist=0.01,
        target_hold_days=20
    )
    assert res_fail.passed is False
    assert "tier2_fail:theme_divergence:no_divergence" in res_fail.reject_reason
    
    # Theme OK (0.02), Sector NOT OK (-0.01) -> Divergence OK
    res_pass = evaluate_ticker(
        ticker="AAPL",
        df=df,
        spy_df=None,
        combo_cfg=combo_cfg,
        theme_dist=0.02,
        sector_etf_dist=-0.01,
        target_hold_days=20
    )
    assert res_pass.passed is True

def test_theme_divergence_horizon_skip():
    # Mock data
    df = pd.DataFrame({
        "open": [100]*70, "high": [105]*70, "low": [95]*70, "close": [101]*70, "volume": [1000000]*70
    })
    
    combo_cfg = {
        "tier2_filters": {
            "use_theme_group_filter": True,
            "theme_filter_mode": "divergence"
        }
    }
    
    # Divergence exists BUT hold_days = 5 -> Filter should SKIP (pass transparently)
    res_skip = evaluate_ticker(
        ticker="AAPL",
        df=df,
        spy_df=None,
        combo_cfg=combo_cfg,
        theme_dist=0.02,
        sector_etf_dist=0.01, # This would fail if horizon was >= 10
        target_hold_days=5
    )
    assert res_skip.passed is True
    assert res_skip.target_hold_days == 5

def test_theme_feature_flag_off():
    # Mock data
    df = pd.DataFrame({
        "open": [100]*70, "high": [105]*70, "low": [95]*70, "close": [101]*70, "volume": [1000000]*70
    })
    
    combo_cfg = {
        "tier2_filters": {
            "use_theme_group_filter": False, # OFF
            "theme_filter_mode": "above_sma20"
        }
    }
    
    # Theme weak, but filter is OFF -> should PASS
    res = evaluate_ticker(
        ticker="AAPL",
        df=df,
        spy_df=None,
        combo_cfg=combo_cfg,
        theme_dist=-0.05
    )
    assert res.passed is True

def test_taxonomy_version():
    assert TAXONOMY_VERSION == "v2.0-PIT-MultiYear"

if __name__ == "__main__":
    pytest.main([__file__])
