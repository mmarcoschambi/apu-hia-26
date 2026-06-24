#!/usr/bin/env python3
"""
finviz_monitor.py - Finviz radar y briefs para VPS.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from scripts.paper_finviz import run_pre
from src.utils.telegram_client import send_message_with_buttons
from src.utils.terminal_gui import build_telegram_brief, print_terminal_brief
from scripts.generate_radar_rotation import get_radar_data, format_radar_text
from src.data.candidate_tracker import CandidateTracker
from src.data.sector_cohort import SectorCohortManager

OUT_DIR = PROJECT_ROOT / "outputs" / "telegram_monitor"


def _save(date: str, name: str, payload: dict) -> Path:
    day_dir = OUT_DIR / date
    day_dir.mkdir(parents=True, exist_ok=True)
    path = day_dir / name
    path.write_text(json.dumps(payload, indent=2, default=str))
    return path


def refresh_cohort_data(date: str) -> None:
    """Populates candidate_state and sector_cohort for the given date."""
    try:
        tracker = CandidateTracker()
        tracker.populate_day(date)
        
        manager = SectorCohortManager()
        manager.calculate_day(date)
    except Exception as e:
        print(f"⚠️ Error refreshing cohort data: {e}")


def build_prealerts(snapshot: dict) -> dict:
    signals = snapshot.get("signals", [])
    top = sorted(signals, key=lambda s: str(s.get("ticker", "")))[:10]
    return {
        "date": snapshot["date"],
        "signals": top,
        "signals_count": len(signals),
        "generated_at": datetime.now().isoformat(),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Finviz monitor")
    parser.add_argument("--date", default=None)
    parser.add_argument("--cohort-mode", choices=["off", "shadow", "active"], default="shadow")
    parser.add_argument("--skip-cohort-refresh", action="store_true")
    args = parser.parse_args()
    
    date = args.date or datetime.now().strftime("%Y-%m-%d")

    snapshot = run_pre(date, drift_override=100.0)
    if not snapshot:
        payload = {"date": date, "status": "failed", "generated_at": datetime.now().isoformat()}
        _save(date, "market_status.json", payload)
        return

    # 🧭 RADAR ROTATION / COHORT MOMENTUM
    radar_payload = {}
    radar_text = ""
    effective_date = date # Use the date we are processing
    
    if args.cohort_mode != "off":
        if not args.skip_cohort_refresh:
            refresh_cohort_data(effective_date)
        
        radar_payload = get_radar_data(effective_date)
        if radar_payload:
            radar_text = format_radar_text(radar_payload)
            _save(date, "radar_rotation.json", radar_payload)
            
            # ── Cohort Priority Ranking ──────────────────────────────────────────────
            # Edge validado (sandbox): +0.62% en 10d (p=0.024)
            # Sectores donde aplica: XLE, XLI, XLV, XLY, XLF, XLRE
            # Sectores donde NO aplica: XLK, XLC (growth/tech invierten el efecto)
            COHORT_POSITIVE_SECTORS = {"XLE","XLI","XLV","XLY","XLF","XLRE","XLB","XLU"}
            COHORT_NEGATIVE_SECTORS = {"XLK","XLC","XLP"}  # no penalizar, no priorizar

            signals = snapshot.get("signals", [])
            blocked_tickers = []     # sectores con delta < 0 en sectores ciclicos
            boosted_tickers = []     # sectores con delta > 0 en sectores ciclicos

            sector_deltas = {s["sector_etf"]: s["score_delta_5d"] for s in radar_payload.get("sectors", [])}

            from src.utils.sector_rotation import SECTOR_MAP
            tracker = CandidateTracker()

            for s in signals:
                ticker = s.get("ticker")
                etf = SECTOR_MAP.get(ticker)
                if not etf:
                    try:
                        conn = tracker.get_connection()
                        res = conn.execute(
                            "SELECT sector_etf FROM candidate_state WHERE ticker=? ORDER BY date DESC LIMIT 1",
                            (ticker,)).fetchone()
                        conn.close()
                        if res: etf = res[0]
                    except Exception:
                        pass

                if etf:
                    delta = sector_deltas.get(etf, 0)
                    s["sector_etf"]   = etf
                    s["cohort_delta"] = round(delta, 2)
                    if etf in COHORT_POSITIVE_SECTORS:
                        if delta < 0:
                            blocked_tickers.append(f"{ticker} ({etf} {delta:+.1f})")
                            s["cohort_priority"] = "LOW"
                        elif delta > 2:
                            boosted_tickers.append(f"{ticker} ({etf} {delta:+.1f})")
                            s["cohort_priority"] = "HIGH"
                        else:
                            s["cohort_priority"] = "NEUTRAL"
                    else:
                        s["cohort_priority"] = "NEUTRAL"  # growth: no ajustar

            # Reordenar señales: HIGH primero, luego NEUTRAL, LOW al final
            priority_order = {"HIGH": 0, "NEUTRAL": 1, "LOW": 2}
            signals.sort(key=lambda x: priority_order.get(x.get("cohort_priority","NEUTRAL"), 1))
            snapshot["signals"] = signals

            if boosted_tickers:
                radar_text += f"\n\n🚀 *COHORT BOOST (sector acelerando)*\n{', '.join(boosted_tickers)}"
            if blocked_tickers:
                radar_text += f"\n\n🛡️ *SHADOW BLOCKS (sector frenando)*\n{', '.join(blocked_tickers)}"
            radar_payload["shadow_blocked"] = blocked_tickers
            radar_payload["cohort_boosted"] = boosted_tickers

    brief, buttons = build_telegram_brief(snapshot)
    
    # Append Radar Rotation to Telegram brief
    if radar_text:
        brief += "\n" + "-"*30 + "\n" + radar_text

    prealerts = build_prealerts(snapshot)
    
    # Update market_status with radar info
    snapshot["radar_rotation_shadow"] = radar_payload

    _save(date, "market_status.json", snapshot)
    _save(date, "premarket_brief.json", {"date": date, "brief": brief, "buttons": buttons})
    _save(date, "prealerts.json", prealerts)
    _save(
        date,
        "close_summary.json",
        {
            "date": date,
            "status": "pending_close_summary",
            "signals_count": len(snapshot.get("signals", [])),
            "generated_at": datetime.now().isoformat(),
        },
    )

    monitor_chat_id = os.getenv("TELEGRAM_CHAT_ID")
    if monitor_chat_id:
        send_message_with_buttons(
            brief,
            buttons=buttons,
            chat_id=monitor_chat_id,
        )

    # OUTPUT TERMINAL GUI
    print_terminal_brief(snapshot)


if __name__ == "__main__":
    main()
