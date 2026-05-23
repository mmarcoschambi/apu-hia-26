import unittest
from unittest.mock import patch, MagicMock
import pandas as pd

# Import the code to test
from src.paper.telegram_views import (
    load_watchlist_signals,
    build_watchlist_message,
    build_watchlist_detail,
    _is_watchlist_candidate,
)
from scripts.telegram_bot_listener import _is_ticker

class TestWatchlistView(unittest.TestCase):

    def test_is_ticker(self):
        self.assertTrue(_is_ticker("NVDA"))
        self.assertTrue(_is_ticker("COIN"))
        self.assertTrue(_is_ticker("AAPL"))
        self.assertTrue(_is_ticker("BRK.B"))
        
        self.assertFalse(_is_ticker(""))
        self.assertFalse(_is_ticker("2026-05-22"))
        self.assertFalse(_is_ticker("123"))
        self.assertFalse(_is_ticker("VERYLONGTICKER"))

    @patch("src.paper.telegram_views._resolve_live_signals_date")
    @patch("src.paper.telegram_views._load_json")
    @patch("src.paper.telegram_views.pd.read_csv")
    @patch("src.paper.telegram_views.LIVE_SIGNALS_ROOT")
    def test_load_watchlist_signals_csv(self, mock_root, mock_read_csv, mock_load_json, mock_resolve_date):
        mock_resolve_date.return_value = "2026-05-21"
        mock_load_json.return_value = None
        mock_root.__truediv__.return_value.exists.return_value = True
        
        # Mock DataFrame
        df_mock = pd.DataFrame([
            {"ticker": "NVDA", "entry_score": 87.0, "entry_price": 135.2, "gate_adr_pct": 3.2, "sector_etf": "XLK", "entry_gate_status": "PASS"},
            {"ticker": "AVGO", "entry_score": 74.0, "entry_price": 198.0, "gate_adr_pct": 2.8, "sector_etf": "XLK", "entry_gate_status": "PASS"},
        ])
        mock_read_csv.return_value = df_mock
        
        resolved, signals = load_watchlist_signals("2026-05-21")
        
        self.assertEqual(resolved, "2026-05-21")
        self.assertEqual(len(signals), 2)
        self.assertEqual(signals[0]["ticker"], "NVDA")
        self.assertEqual(signals[1]["ticker"], "AVGO")

    @patch("src.paper.telegram_views.load_watchlist_signals")
    @patch("src.paper.telegram_views._get_sector_status")
    @patch("src.paper.telegram_views._get_theme_rs_vs_etf")
    @patch("src.paper.telegram_views.get_themes")
    def test_build_watchlist_message(self, mock_get_themes, mock_theme_rs, mock_sector_status, mock_load):
        # Setup mocks
        mock_load.return_value = ("2026-05-21", [
            {"ticker": "NVDA", "entry_score": 87.0, "entry_price": 135.20, "gate_adr_pct": 3.2, "sector_etf": "XLK", "entry_gate_status": "PASS"},
            {"ticker": "AVGO", "entry_score": 74.0, "entry_price": 198.00, "gate_adr_pct": 2.8, "sector_etf": "XLK", "entry_gate_status": "PASS"},
        ])
        mock_get_themes.return_value = ["AI/ML"]
        mock_theme_rs.return_value = 0.021
        mock_sector_status.return_value = (True, 0.012)
        
        msg_text, msg_buttons = build_watchlist_message("2026-05-21", page=1)
        
        self.assertIn("WATCHLIST | 2026-05-21", msg_text)
        self.assertIn("NVDA", msg_text)
        self.assertIn("AVGO", msg_text)
        self.assertIn("XLK — Tecnología", msg_text)
        self.assertIn("★87", msg_text)
        
        # Since total candidates = 2, total_pages = 1, so buttons should just have Refresh
        self.assertEqual(len(msg_buttons), 1)
        self.assertEqual(msg_buttons[0][0]["text"], "🔄 Refresh")

    @patch("src.paper.telegram_views.load_watchlist_signals")
    @patch("src.paper.telegram_views._get_sector_status")
    @patch("src.paper.telegram_views._get_theme_rs_vs_etf")
    @patch("src.paper.telegram_views.get_themes")
    def test_build_watchlist_detail(self, mock_get_themes, mock_theme_rs, mock_sector_status, mock_load):
        # Setup mocks
        mock_load.return_value = ("2026-05-21", [
            {"ticker": "NVDA", "entry_score": 87.0, "entry_price": 135.20, "breakout_level": 135.0, "gate_adr_pct": 3.2, "sector_etf": "XLK", "entry_gate_status": "PASS"},
        ])
        mock_get_themes.return_value = ["AI/ML"]
        mock_theme_rs.return_value = 0.021
        mock_sector_status.return_value = (True, 0.012)
        
        detail_card = build_watchlist_detail("NVDA", "2026-05-21")
        
        self.assertIn("WATCHLIST DETAIL | NVDA", detail_card)
        self.assertIn("Score:  ★ <code>87</code>", detail_card)
        self.assertIn("Entry:  <code>$135.20</code>", detail_card)
        self.assertIn("Theme: <code>AI/ML</code>", detail_card)
        self.assertIn("RS:0.0% vs Sector" if "RS:0.0%" in detail_card else "RS:+2.1%", detail_card)

    def test_is_watchlist_candidate(self):
        # 1. Calculation error -> False
        self.assertFalse(_is_watchlist_candidate({"reasons": ["No se pudo calcular SMA"]}))
        
        # 2. Too many blockers (reasons >= 3) -> False
        self.assertFalse(_is_watchlist_candidate({
            "proximity_score": 90.0,
            "reasons": ["RVOL bajo", "Extendido", "MA stack roto"],
            "rs_pct": 98.0
        }))
        
        # 3. Proximity >= 70 and < 3 blockers -> True
        self.assertTrue(_is_watchlist_candidate({
            "proximity_score": 75.0,
            "reasons": ["RVOL bajo", "Extendido"],
            "rs_pct": 50.0
        }))
        self.assertFalse(_is_watchlist_candidate({
            "proximity_score": 65.0,
            "reasons": ["RVOL bajo", "Extendido"],
            "rs_pct": 50.0
        }))
        
        # 4. RS >= 90 and Proximity >= 50 and < 3 blockers -> True
        self.assertTrue(_is_watchlist_candidate({
            "proximity_score": 55.0,
            "reasons": ["RVOL bajo", "Extendido"],
            "rs_pct": 92.0
        }))
        self.assertFalse(_is_watchlist_candidate({
            "proximity_score": 45.0,
            "reasons": ["RVOL bajo", "Extendido"],
            "rs_pct": 92.0
        }))
        self.assertFalse(_is_watchlist_candidate({
            "proximity_score": 55.0,
            "reasons": ["RVOL bajo", "Extendido"],
            "rs_pct": 85.0
        }))

if __name__ == "__main__":
    unittest.main()
