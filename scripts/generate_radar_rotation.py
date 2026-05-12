import sqlite3
import pandas as pd
from pathlib import Path
import json
import logging
from datetime import datetime
from typing import Dict, Optional

logger = logging.getLogger(__name__)

def get_radar_data(date_str: Optional[str] = None) -> Dict:
    """
    Returns structured radar rotation data for a given date.
    If date_str is None, uses the latest available date.
    """
    db_path = Path("data/ticker_cache.db")
    if not db_path.exists():
        logger.warning(f"Database not found at {db_path}")
        return {}

    conn = sqlite3.connect(db_path)
    
    try:
        if date_str is None:
            cursor = conn.cursor()
            cursor.execute("SELECT MAX(date) FROM sector_cohort")
            res = cursor.fetchone()
            if not res or not res[0]:
                return {}
            date_str = res[0]
        
        # 1. Sector Momentum
        query_sectors = """
        SELECT sector_etf, score_mean, score_delta_5d, rank_today, rank_delta, ticker_count, new_entrants, dropped
        FROM sector_cohort
        WHERE date = ?
        ORDER BY score_delta_5d DESC
        """
        df_sectors = pd.read_sql_query(query_sectors, conn, params=(date_str,))
        
        if df_sectors.empty:
            return {"date": date_str, "sectors": []}

        sectors_data = []
        for _, row in df_sectors.iterrows():
            sectors_data.append({
                "sector_etf": row["sector_etf"],
                "score_mean": float(row["score_mean"]),
                "score_delta_5d": float(row["score_delta_5d"]),
                "rank_today": int(row["rank_today"]),
                "rank_delta": int(row["rank_delta"]),
                "ticker_count": int(row["ticker_count"]),
                "new_entrants": json.loads(row["new_entrants"]) if row["new_entrants"] else [],
                "dropped": json.loads(row["dropped"]) if row["dropped"] else []
            })

        # 2. Top Candidates
        query_candidates = """
        SELECT ticker, sector_etf, score, status, breakout_gap, rvol, theme_tags, htf_candidate
        FROM candidate_state
        WHERE date = ? AND status = 'NEAR'
        ORDER BY score DESC
        LIMIT 10
        """
        df_candidates = pd.read_sql_query(query_candidates, conn, params=(date_str,))
        candidates_data = []
        for _, row in df_candidates.iterrows():
            candidates_data.append({
                "ticker": row["ticker"],
                "sector_etf": row["sector_etf"],
                "score": float(row["score"]),
                "breakout_gap": float(row["breakout_gap"]) if row["breakout_gap"] else 0.0,
                "rvol": float(row["rvol"]) if row["rvol"] else None,
                "themes": json.loads(row["theme_tags"]) if row["theme_tags"] else [],
                "htf_candidate": int(row["htf_candidate"]) if pd.notna(row.get("htf_candidate")) else 0
            })

        return {
            "date": date_str,
            "sectors": sectors_data,
            "candidates": candidates_data
        }
    except Exception as e:
        logger.error(f"Error fetching radar data: {e}")
        return {}
    finally:
        conn.close()

def format_radar_text(radar_data: Dict) -> str:
    """Formats radar data into a Telegram-friendly string."""
    if not radar_data or not radar_data.get("sectors"):
        return "🧭 Radar Rotation: No data available for today."

    date_str = radar_data["date"]
    lines = [f"🧭 *RADAR ROTATION - {date_str}*"]
    
    # Momentum Sectors
    lines.append("\n📊 *MOMENTUM SECTORS*")
    # Top 3 accelerating
    accel = [s for s in radar_data["sectors"] if s["score_delta_5d"] > 0][:3]
    for s in accel:
        delta_str = f"+{s['score_delta_5d']:.1f}"
        lines.append(f"• *{s['sector_etf']}*: Score {s['score_mean']:.1f} ({delta_str}) | Rank {s['rank_today']}")
        if s["new_entrants"]:
            entrants = ", ".join(s["new_entrants"][:3])
            lines.append(f"  [dim]In: {entrants}{'...' if len(s['new_entrants']) > 3 else ''}[/dim]")

    # Top 2 cooling
    cooling = [s for s in radar_data["sectors"] if s["score_delta_5d"] < 0][-2:]
    if cooling:
        lines.append("\n🧊 *COOLING*")
        for s in reversed(cooling):
            lines.append(f"• *{s['sector_etf']}*: Score {s['score_mean']:.1f} ({s['score_delta_5d']:.1f})")

    # Candidates
    if radar_data.get("candidates"):
        lines.append("\n🚀 *NEAR BREAKOUT*")
        for c in radar_data["candidates"][:5]:
            theme_str = f"| {', '.join(c['themes'])}" if c['themes'] else ""
            htf_str = " 🔥" if c.get("htf_candidate") == 1 else ""
            lines.append(f"• {c['ticker']} ({c['sector_etf']}){htf_str} {theme_str}")

    return "\n".join(lines)

def generate_report(date_str=None):
    """Legacy print-based report for CLI use."""
    data = get_radar_data(date_str)
    print(format_radar_text(data))

if __name__ == "__main__":
    generate_report()
