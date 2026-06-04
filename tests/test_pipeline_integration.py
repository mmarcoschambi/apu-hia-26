import sys
from pathlib import Path
import pytest
import pandas as pd
import numpy as np

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.screeners.base import ScreenerResult
from src.screeners.pipeline import ScreenerPipeline
from src.screeners.registry import ScreenerRegistry
from src.signals.signal_engine import evaluate_ticker, SignalDecision

def _make_trending_df(n: int = 150, start: float = 20.0, slope: float = 0.3) -> pd.DataFrame:
    np.random.seed(42)
    dates = pd.date_range("2026-01-01", periods=n, freq="B")
    close = start + slope * np.arange(n) + np.random.randn(n) * 0.5
    close = np.maximum(close, 1.0)
    high = close * 1.01
    low = close * 0.99
    
    df = pd.DataFrame(
        {
            "open": close * 0.995,
            "high": high,
            "low": low,
            "close": close,
            "volume": np.random.randint(1_000_000, 5_000_000, n).astype(float),
            "adr_pct": np.full(n, 4.5),
        },
        index=dates,
    )
    df["sma20"] = df["close"].rolling(20).mean()
    df["sma50"] = df["close"].rolling(50).mean()
    return df

def test_screener_pipeline_integration():
    """Validates full integration flow: signal_engine -> ScreenerPipeline -> ScreenerResult"""
    df = _make_trending_df()
    spy_df = _make_trending_df()
    
    # We want a pipeline of preset adapted screeners
    # Let's use our new ll_hl_confirmed screener
    config_ll = ScreenerRegistry.load_config("ll_hl_confirmed")
    screener_ll = ScreenerRegistry.get("ll_hl_confirmed", config_ll)
    
    # Chaining it inside a sequential pipeline
    pipeline = ScreenerPipeline([screener_ll], mode="sequential")
    res = pipeline.scan("AAPL", df, spy_df)
    
    # It must evaluate without errors
    assert isinstance(res, ScreenerResult)
    assert res.screener_name == "pipeline_sequential[ll_hl_confirmed]"
    
    # Test through evaluate_ticker in signal_engine
    combo_cfg = {
        "name": "combo_system_b_presets",
        "screener": {
            "name": "ll_hl_confirmed",
            "mode": "sequential"
        },
        "pattern": {
            "signal_type": "any"
        },
        "tier2_filters": {
            "min_rvol": 0.5,
            "min_adr": 1.0,
            "min_consolidation_days": 1
        }
    }
    
    decision = evaluate_ticker(
        ticker="AAPL",
        df=df,
        spy_df=spy_df,
        combo_cfg=combo_cfg,
        mode="A"
    )
    
    assert isinstance(decision, SignalDecision)
    print("[PASS] test_screener_pipeline_integration")
