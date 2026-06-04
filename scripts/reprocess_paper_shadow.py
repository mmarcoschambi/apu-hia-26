#!/usr/bin/env python3
"""
scripts/reprocess_paper_shadow.py
Backfills the last 10 trading days of observation for the Thematic Divergence filter.
This script uses the existing daily_scan.py logic to generate shadow audits.
"""

import sys
from pathlib import Path
import logging
import pandas as pd
from unittest.mock import patch

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from scripts.daily_scan import run_daily_scan
from src.config.dynamic_config import load_production_config

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

def mocked_load():
    cfg = load_production_config()
    cfg["tier2_filters"]["use_theme_group_filter"] = True
    return cfg

def main():
    # Dates to reprocess with higher signal density
    dates = [
        "2026-03-02",
        "2026-03-04",
        "2026-03-06",
        "2026-03-10",
        "2026-03-12",
        "2026-03-31",
        "2026-04-10",
        "2026-04-20",
        "2026-04-29",
        "2026-04-30"
    ]
    
    logger.info(f"Starting Shadow Backfill for {len(dates)} days...")
    
    results_summary = []
    
    with patch("scripts.daily_scan.load_production_config", side_effect=mocked_load):
        for d in dates:
            logger.info(f"\nProcessing shadow day: {d}")
            try:
                # We run the scan
                run_daily_scan(d)
                
                # Read back the audit to summarize
                audit_path = PROJECT_ROOT / "outputs" / "live_signals" / d / "rejection_audit.csv"
                if audit_path.exists():
                    df_audit = pd.read_csv(audit_path)
                    allowed = (df_audit["passed_with_filter"] & df_audit["best_theme"].notna()).sum()
                    blocked = df_audit["blocked_by_theme"].sum()
                    results_summary.append({
                        "date": d,
                        "allowed": allowed,
                        "blocked": blocked,
                        "total_eligible": allowed + blocked
                    })
            except Exception as e:
                logger.error(f"Error reprocessing {d}: {e}")

    # Print final execution report
    print("\n" + "="*60)
    print("SHADOW REPROCESSING SUMMARY (Last 10 Days)")
    print("="*60)
    df_res = pd.DataFrame(results_summary)
    if not df_res.empty:
        print(df_res.to_string(index=False))
        total_allowed = df_res["allowed"].sum()
        total_eligible = df_res["total_eligible"].sum()
        avg_retention = (total_allowed / total_eligible * 100) if total_eligible > 0 else 0
        print(f"\nAggregate Shadow Retention: {avg_retention:.1f}% ({total_allowed}/{total_eligible})")
    else:
        print("No results generated.")
    print("="*60 + "\n")

if __name__ == "__main__":
    main()
