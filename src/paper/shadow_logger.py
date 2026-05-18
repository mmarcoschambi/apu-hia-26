import json
import sqlite3
import logging
from pathlib import Path
from datetime import datetime, timedelta
import pandas as pd
import numpy as np
from src.signals.thematic_logic import calculate_equal_weighted_index, evaluate_variant_e

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

class ShadowLogger:
    def __init__(self, output_dir=None, db_path=None):
        self.output_dir = Path(output_dir) if output_dir else PROJECT_ROOT / "outputs" / "shadow_theme_filter"
        self.db_path = Path(db_path) if db_path else PROJECT_ROOT / "data" / "ticker_cache.db"
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Load taxonomy
        try:
            from src.data.theme_taxonomy import THEME_MAP
            self.theme_map = THEME_MAP
        except ImportError:
            self.theme_map = {}
            logger.warning("Could not import THEME_MAP from src.data.theme_taxonomy")
        
        # Load sector map
        try:
            from src.utils.sector_rotation import SECTOR_MAP
            self.sector_map = SECTOR_MAP
        except ImportError:
            self.sector_map = {}
            logger.warning("Could not import SECTOR_MAP from src.utils.sector_rotation")

    def evaluate_variant_e(self, ticker: str, date: str, sector_etf: str = None) -> dict:
        """
        Calculates if Variant E would accept the signal.
        Variant E: Theme strong (Index > SMA20).
        """
        themes = self.theme_map.get(ticker, [])
        if not themes:
            return {
                "variant_e_would_accept": False,
                "reason": "no_theme",
                "theme_above_sma20": False,
                "theme_vs_sector_20d": 0.0,
                "themes": [],
                "best_theme": None
            }
            
        if not sector_etf:
            sector_etf = self.sector_map.get(ticker)
            
        # 1. Get all members for these themes
        all_members = []
        for t, th_list in self.theme_map.items():
            if any(th in themes for th in th_list):
                all_members.append(t)
        all_members = list(set(all_members))
        
        # 2. Fetch prices for members + sector_etf
        lookback = 40
        needed = all_members + ([sector_etf] if sector_etf else [])
        
        try:
            if not self.db_path.exists():
                return {"variant_e_would_accept": False, "reason": "db_not_found"}

            conn = sqlite3.connect(self.db_path)
            placeholders = ",".join(["?"] * len(needed))
            # Get data for members + ETF
            query = f"""
                SELECT ticker, date, close 
                FROM ohlcv_cache 
                WHERE ticker IN ({placeholders}) AND date <= ?
                ORDER BY date DESC
                LIMIT ?
            """
            # We need enough rows to cover lookback for each ticker
            df = pd.read_sql_query(query, conn, params=needed + [date, len(needed) * (lookback + 5)])
            conn.close()
            
            if df.empty:
                return {"variant_e_would_accept": False, "reason": "no_data"}
                
            pivot = df.pivot(index="date", columns="ticker", values="close").sort_index()
            
            # 3. Calculate Theme Index (EW)
            member_cols = [c for c in pivot.columns if c in all_members]
            theme_index = calculate_equal_weighted_index(pivot, member_cols)
            
            if theme_index.empty or len(theme_index) < 2:
                return {"variant_e_would_accept": False, "reason": "too_few_members_or_history"}
            
            # 4. Evaluate Divergence
            sector_prices = None
            if sector_etf and sector_etf in pivot.columns:
                sector_prices = pivot[sector_etf]
                
            eval_res = evaluate_variant_e(theme_index, sector_prices)
            
            return {
                "variant_e_would_accept": eval_res["variant_e_accepted"],
                "theme_above_sma20": eval_res["theme_above_sma"],
                "theme_dist": round(eval_res["theme_dist"], 4),
                "sector_etf_ok": eval_res["sector_ok"],
                "sector_dist": round(eval_res["sector_dist"], 4),
                "theme_vs_sector_20d": round(eval_res["theme_vs_sector_20d"], 4),
                "themes": themes,
                "best_theme": themes[0],
                "members_count": len(member_cols)
            }
            
        except Exception as e:
            logger.error(f"Error in evaluate_variant_e for {ticker}: {e}")
            return {"variant_e_would_accept": False, "reason": f"error: {str(e)}"}

    def log_round(self, accepted_signals, date):
        results = []
        for rs in accepted_signals:
            # Handle both RoutedSignal and UnifiedSignal/dict
            if hasattr(rs, 'signal'):
                ticker = rs.signal.ticker
                entry_price = rs.signal.entry_price_ref
                stop_price = rs.signal.stop_price
            elif isinstance(rs, dict):
                ticker = rs.get('ticker')
                entry_price = rs.get('entry_price_ref', rs.get('entry_price'))
                stop_price = rs.get('stop_price')
            else:
                ticker = getattr(rs, 'ticker', None)
                entry_price = getattr(rs, 'entry_price_ref', getattr(rs, 'entry_price', None))
                stop_price = getattr(rs, 'stop_price', None)

            if not ticker: continue
            
            eval_e = self.evaluate_variant_e(ticker, date)
            
            results.append({
                "ticker": ticker,
                "sector_etf": self.sector_map.get(ticker),
                "themes": eval_e.get("themes", []),
                "best_theme": eval_e.get("best_theme"),
                "theme_above_sma20": eval_e.get("theme_above_sma20", False),
                "theme_dist": eval_e.get("theme_dist", 0.0),
                "sector_etf_ok": eval_e.get("sector_etf_ok", False),
                "sector_dist": eval_e.get("sector_dist", 0.0),
                "theme_vs_sector_20d": eval_e.get("theme_vs_sector_20d", 0.0),
                "variant_e_would_accept": eval_e.get("variant_e_would_accept", False),
                "signal_accepted_by_router": True,
                "entry_price": entry_price,
                "stop_price": stop_price,
                "fwd_5d": None,
                "fwd_10d": None,
                "fwd_20d": None
            })
            
        summary = {
            "total_signals": len(accepted_signals),
            "variant_e_accepts": sum(1 for r in results if r["variant_e_would_accept"]),
            "variant_e_rejects": sum(1 for r in results if not r["variant_e_would_accept"]),
            "retention_pct": round(sum(1 for r in results if r["variant_e_would_accept"]) / len(results) * 100, 1) if results else 0
        }
        
        output_file = self.output_dir / f"{date}.json"
        payload = {
            "date": date,
            "signals": results,
            "summary": summary
        }
        
        with open(output_file, "w") as f:
            json.dump(payload, f, indent=2)
            
        logger.info(f"✅ Shadow round logged to {output_file}")
        return output_file

    def fill_forward_returns(self, lookback_rounds=30):
        """Fills missing forward returns for logged signals."""
        json_files = sorted(list(self.output_dir.glob("*.json")), reverse=True)[:lookback_rounds]
        
        if not json_files: return
        
        try:
            conn = sqlite3.connect(self.db_path)
            
            for f in json_files:
                with open(f, "r") as jf:
                    data = json.load(jf)
                
                date_str = data["date"]
                dt = pd.to_datetime(date_str)
                changed = False
                
                for sig in data["signals"]:
                    ticker = sig["ticker"]
                    entry_price = sig["entry_price"]
                    if not entry_price: continue
                    
                    for days in [5, 10, 20]:
                        key = f"fwd_{days}d"
                        if sig.get(key) is None:
                            # Try to find price at date + days
                            target_dt = dt + timedelta(days=days)
                            target_str = target_dt.strftime("%Y-%m-%d")
                            
                            # Find first available price on or after target date
                            query = "SELECT close FROM ohlcv_cache WHERE ticker = ? AND date >= ? ORDER BY date LIMIT 1"
                            res = conn.execute(query, (ticker, target_str)).fetchone()
                            
                            if res:
                                exit_price = res[0]
                                sig[key] = round((exit_price / entry_price) - 1, 4)
                                changed = True
                
                if changed:
                    with open(f, "w") as jf:
                        json.dump(data, jf, indent=2)
                    logger.info(f"Updated forward returns for {f.name}")
                    
            conn.close()
        except Exception as e:
            logger.error(f"Error filling forward returns: {e}")

    def get_paper_summary(self, min_rounds=15) -> dict:
        """Aggregates shadow mode metrics for go/no-go decision."""
        json_files = sorted(list(self.output_dir.glob("*.json")))
        if len(json_files) < min_rounds:
            return {"status": "insufficient_data", "rounds": len(json_files)}
            
        all_signals = []
        for f in json_files:
            with open(f, "r") as jf:
                data = json.load(jf)
                all_signals.extend(data["signals"])
        
        df = pd.DataFrame(all_signals)
        if df.empty: return {"status": "empty"}
        
        # Metrics for Variant E accepts
        e_accepted = df[df["variant_e_would_accept"] == True].copy()
        
        if e_accepted.empty:
            return {"status": "no_variant_e_signals", "rounds": len(json_files)}
            
        # Calculate Win Rate and PF if forward returns exist
        # Using fwd_20d as proxy for performance
        if "fwd_20d" in e_accepted.columns:
            perf = e_accepted["fwd_20d"].dropna()
            if not perf.empty:
                wr = (perf > 0).mean() * 100
                wins = perf[perf > 0].sum()
                losses = abs(perf[perf < 0].sum())
                pf = wins / losses if losses > 0 else 99.9
                
                return {
                    "status": "ready",
                    "rounds": len(json_files),
                    "total_signals": len(df),
                    "variant_e_signals": len(e_accepted),
                    "retention_pct": round(len(e_accepted) / len(df) * 100, 1),
                    "win_rate_20d": round(wr, 1),
                    "profit_factor_20d": round(pf, 2),
                    "avg_return_20d": round(perf.mean() * 100, 2)
                }
                
        return {"status": "awaiting_fwd_returns", "rounds": len(json_files)}
