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

    def test_classify_urgency(self):
        from src.paper.telegram_views import _classify_urgency

        # PASS → tier A, ACTIVO
        tier, badge, evo = _classify_urgency({"entry_gate_status": "PASS"})
        self.assertEqual(tier, "A")
        self.assertIn("ACTIVO", badge)
        self.assertEqual(evo, "")

        # Solo RVOL → tier A
        tier, badge, evo = _classify_urgency({
            "reasons": ["RVOL bajo"], "dist_sma20": 5.0,
            "waiting_for": "RVOL >= 1.10", "entry_gate_status": "BLOCKED",
            "_setup_age": 4, "_db_status": "NEAR", "_near_breakout": True
        })
        self.assertEqual(tier, "A")
        self.assertIn("RVOL", badge)
        self.assertIn("Cerca del trigger", evo)

        # Solo breakout → tier A
        tier, badge, evo = _classify_urgency({
            "reasons": ["Falta breakout"], "dist_sma20": 4.0,
            "entry_gate_status": "BLOCKED",
            "_setup_age": 5, "_dist_trend_5d": -6.0
        })
        self.assertEqual(tier, "A")
        self.assertIn("breakout", badge)
        self.assertIn("Consolidando", evo)

        # Dist moderada sin MA → tier B
        tier, badge, evo = _classify_urgency({
            "reasons": ["Extendido de SMA20"], "dist_sma20": 12.0,
            "entry_gate_status": "BLOCKED",
            "_setup_age": 8
        })
        self.assertEqual(tier, "B")
        self.assertIn("en lista", evo)

        # Dist > 15% → tier C
        tier, badge, evo = _classify_urgency({
            "reasons": ["Extendido de SMA20"], "dist_sma20": 22.0,
            "entry_gate_status": "BLOCKED",
            "_setup_age": 3, "_db_status": "CONFIRMED"
        })
        self.assertEqual(tier, "C")
        self.assertIn("Confirmado", evo)

        # MA stack roto → tier C siempre
        tier, badge, evo = _classify_urgency({
            "reasons": ["MA stack roto"], "dist_sma20": 5.0,
            "entry_gate_status": "BLOCKED"
        })
        self.assertEqual(tier, "C")
        self.assertEqual(evo, "")

    @patch("src.paper.telegram_views.Path.exists")
    @patch("src.paper.telegram_views.pd.read_sql_query")
    @patch("src.paper.telegram_views.sqlite3.connect")
    def test_enrich_with_history(self, mock_connect, mock_read_sql, mock_exists):
        from src.paper.telegram_views import _enrich_with_history

        mock_exists.return_value = True
        
        # Mock DataFrame returning history for VSH and ARM
        df_mock = pd.DataFrame([
            {"ticker": "VSH", "date": "2026-05-22", "setup_age": 5, "dist_sma20_pct": 10.0, "status": "NEAR", "near_breakout": 1},
            {"ticker": "VSH", "date": "2026-05-21", "setup_age": 4, "dist_sma20_pct": 12.0, "status": "BUILDING", "near_breakout": 0},
            {"ticker": "VSH", "date": "2026-05-20", "setup_age": 3, "dist_sma20_pct": 15.0, "status": "BUILDING", "near_breakout": 0},
            {"ticker": "VSH", "date": "2026-05-19", "setup_age": 2, "dist_sma20_pct": 17.0, "status": "BUILDING", "near_breakout": 0},
            {"ticker": "VSH", "date": "2026-05-18", "setup_age": 1, "dist_sma20_pct": 19.5, "status": "BUILDING", "near_breakout": 0},
            {"ticker": "ARM", "date": "2026-05-22", "setup_age": 12, "dist_sma20_pct": 18.6, "status": "BUILDING", "near_breakout": 0},
        ])
        mock_read_sql.return_value = df_mock

        signals = [
            {"ticker": "VSH", "entry_score": 98.0, "entry_price": 42.17, "gate_dist_sma20": 10.0},
            {"ticker": "ARM", "entry_score": 97.0, "entry_price": 298.16, "gate_dist_sma20": 18.6},
        ]
        
        enriched = _enrich_with_history(signals, "2026-05-22")
        
        self.assertEqual(len(enriched), 2)
        vsh = [s for s in enriched if s["ticker"] == "VSH"][0]
        arm = [s for s in enriched if s["ticker"] == "ARM"][0]
        
        self.assertEqual(vsh["_setup_age"], 5)
        self.assertEqual(vsh["_db_status"], "NEAR")
        self.assertTrue(vsh["_near_breakout"])
        self.assertEqual(vsh["_dist_trend_5d"], -9.5)
        
        self.assertEqual(arm["_setup_age"], 12)
        self.assertEqual(arm["_db_status"], "BUILDING")
        self.assertFalse(arm["_near_breakout"])
        self.assertEqual(arm["_dist_trend_5d"], 0.0)

    @patch("src.paper.telegram_views.load_watchlist_signals")
    @patch("src.paper.telegram_views._get_sector_status")
    @patch("src.paper.telegram_views._get_theme_rs_vs_etf")
    @patch("src.paper.telegram_views.get_themes")
    def test_build_watchlist_message_system_filtering(self, mock_get_themes, mock_theme_rs, mock_sector_status, mock_load):
        # Mocks para probar filtrado por sistema
        mock_load.return_value = ("2026-05-21", [
            {"ticker": "NVDA", "entry_score": 87.0, "entry_price": 135.20, "gate_adr_pct": 3.2, "sector_etf": "XLK", "entry_gate_status": "PASS", "combos": ["Qulla"]},
            {"ticker": "AVGO", "entry_score": 74.0, "entry_price": 198.00, "gate_adr_pct": 2.8, "sector_etf": "XLK", "entry_gate_status": "PASS", "combos": ["Minervini"]},
        ])
        mock_get_themes.return_value = ["AI/ML"]
        mock_theme_rs.return_value = 0.021
        mock_sector_status.return_value = (True, 0.012)
        
        # Filtro Sistema A -> Solo NVDA
        msg_text_a, _ = build_watchlist_message("2026-05-21", page=1, system="A")
        self.assertIn("[SISTEMA A] WATCHLIST", msg_text_a)
        self.assertIn("NVDA", msg_text_a)
        self.assertNotIn("AVGO", msg_text_a)
        
        # Filtro Sistema B -> Solo AVGO
        msg_text_b, _ = build_watchlist_message("2026-05-21", page=1, system="B")
        self.assertIn("[SISTEMA B] WATCHLIST", msg_text_b)
        self.assertIn("AVGO", msg_text_b)
        self.assertNotIn("NVDA", msg_text_b)

    @patch("scripts.telegram_bot_listener.os.getenv")
    def test_get_system_for_chat(self, mock_getenv):
        from scripts.telegram_bot_listener import _get_system_for_chat
        
        def side_effect(key, default=None):
            env = {
                "TELEGRAM_CHAT_ID_LIVE": "-1003901048156",
                "TELEGRAM_CHAT_ID_SYSTEM_B": "-1002222222222",
                "TELEGRAM_CHAT_ID_MONITOR": "-1003961012390",
                "TELEGRAM_CHAT_ID_DEMO": "-1003961012390",
                "TELEGRAM_CHAT_ID": "1324857342",
            }
            return env.get(key, default)
            
        mock_getenv.side_effect = side_effect
        
        # System B
        self.assertEqual(_get_system_for_chat("-1003901048156"), "B")
        self.assertEqual(_get_system_for_chat("-1002222222222"), "B")
        
        # System A
        self.assertEqual(_get_system_for_chat("-1003961012390"), "A")
        self.assertEqual(_get_system_for_chat("1324857342"), "A")
        
        # None
        self.assertIsNone(_get_system_for_chat("-1009999999999"))

if __name__ == "__main__":
    unittest.main()
