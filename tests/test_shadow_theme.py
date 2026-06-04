
import pytest
import pandas as pd
import numpy as np
import sqlite3
from src.paper.shadow_logger import ShadowLogger
from src.signals.thematic_logic import calculate_equal_weighted_index, evaluate_variant_e
from unittest.mock import MagicMock, patch

def test_thematic_logic_index_nan_masking():
    """
    Verifica que calculate_equal_weighted_index invalide correctamente los días sin data.
    """
    prices = pd.DataFrame({
        "A": [100, 101, np.nan, 103],
        "B": [50, 51, 52, np.nan]
    }, index=pd.date_range("2026-01-01", periods=4))
    
    # Con min_members=2, el día 3 y 4 deberían ser NaN
    idx = calculate_equal_weighted_index(prices, ["A", "B"], min_members=2)
    assert pd.isna(idx.iloc[2])
    assert pd.isna(idx.iloc[3])
    assert not pd.isna(idx.iloc[0])
    assert not pd.isna(idx.iloc[1])
    assert idx.iloc[0] == 100.0

def test_evaluate_variant_e_math():
    """
    Test directo de la lógica matemática de divergencia.
    """
    # Case: Theme Strong (Index > SMA20), Sector Weak (ETF <= SMA20)
    theme_idx = pd.Series([100.0]*19 + [110.0], index=pd.date_range("2026-01-01", periods=20))
    # Theme SMA20 approx 100.5, current 110 -> Theme Strong
    
    sector_prices = pd.Series([100.0]*19 + [95.0], index=pd.date_range("2026-01-01", periods=20))
    # Sector SMA20 approx 99.75, current 95 -> Sector Weak
    
    res = evaluate_variant_e(theme_idx, sector_prices, sma_period=20)
    assert res["variant_e_accepted"] == True
    assert res["theme_above_sma"] == True
    assert res["sector_ok"] == False

    # Case: Both Strong -> Reject
    sector_strong = pd.Series([100.0]*19 + [105.0], index=pd.date_range("2026-01-01", periods=20))
    res2 = evaluate_variant_e(theme_idx, sector_strong, sma_period=20)
    assert res2["variant_e_accepted"] == False

def test_shadow_logger_integration():
    """
    Verifica que ShadowLogger use correctamente la lógica de thematic_logic.
    """
    with patch("src.paper.shadow_logger.sqlite3.connect") as mock_connect:
        logger = ShadowLogger()
        # Ambos deben estar en el theme_map para ser contados como miembros del tema "AI"
        logger.theme_map = {"AAPL": ["AI"], "NVDA": ["AI"]}
        logger.sector_map = {"AAPL": "XLK", "NVDA": "XLK"}
        
        # Mock DB return with enough data for SMA20
        # We need at least 20 + 21 (for RS 20d) = 41 points or so
        dates = pd.date_range("2026-01-01", periods=60).strftime("%Y-%m-%d")
        mock_df = pd.DataFrame({
            "ticker": ["AAPL"]*60 + ["XLK"]*60 + ["NVDA"]*60,
            "date": list(dates)*3,
            "close": [150.0]*60 + [200.0]*60 + [100.0]*60
        })
        
        # Simulate Divergence: Theme up, Sector down at the end
        mock_df.loc[(mock_df["ticker"] == "AAPL") & (mock_df["date"] == dates[-1]), "close"] = 180.0
        mock_df.loc[(mock_df["ticker"] == "NVDA") & (mock_df["date"] == dates[-1]), "close"] = 120.0
        mock_df.loc[(mock_df["ticker"] == "XLK") & (mock_df["date"] == dates[-1]), "close"] = 180.0
        
        with patch("pandas.read_sql_query", return_value=mock_df):
            res = logger.evaluate_variant_e("AAPL", dates[-1])
            assert res["variant_e_would_accept"] == True
            assert res["theme_above_sma20"] == True
            assert res["sector_etf_ok"] == False
            assert "AI" in res["themes"]

if __name__ == "__main__":
    pytest.main([__file__])
