#!/usr/bin/env python3
"""
scripts/generate_simulation_report.py
=====================================
CLI standalone para generar reporte de simulación desde analytics JSON.

Usage:
    python3 scripts/generate_simulation_report.py --start 2026-01-01 --end 2026-04-09
    python3 scripts/generate_simulation_report.py --date 2026-04-09
    python3 scripts/generate_simulation_report.py --last 30
"""

import argparse
import json
import logging
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)

OUTPUTS_DIR = PROJECT_ROOT / "outputs" / "paper_trading"


def load_analytics_range(start_date: str, end_date: str) -> List[Dict]:
    """Carga analytics para un rango de fechas."""
    results = []
    start = datetime.strptime(start_date, "%Y-%m-%d")
    end = datetime.strptime(end_date, "%Y-%m-%d")

    current = start
    while current <= end:
        date_str = current.strftime("%Y-%m-%d")
        path = OUTPUTS_DIR / f"analytics_{date_str}.json"

        if path.exists():
            try:
                data = json.load(open(path))
                results.append(data)
            except Exception as e:
                logger.warning(f"Could not load {path}: {e}")

        current += timedelta(days=1)

    return results


def aggregate_simulation_pack(analytics_list: List[Dict]) -> Dict[str, Any]:
    """Agrega simulation_pack de múltiples días."""
    mc_sims = []
    risk_losses = []
    median_outcomes = []
    conf_low_count = 0
    has_simulation_pack = 0

    for data in analytics_list:
        sim_pack = data.get("simulation_pack", {})
        mc_full = sim_pack.get("mc_full", {})

        if mc_full:
            has_simulation_pack += 1
            summary = mc_full.get("summary", {})
            if summary:
                mc_sims.append(summary.get("expected_growth", 0))
                risk_losses.append(summary.get("risk_of_loss", 0))
                median_outcomes.append(summary.get("median_outcome", 0))

            if mc_full.get("confidence_low"):
                conf_low_count += 1

    if not mc_sims:
        return {"note": "no_simulation_data"}

    return {
        "days_analyzed": len(analytics_list),
        "days_with_simulation": has_simulation_pack,
        "avg_expected_growth": sum(mc_sims) / len(mc_sims) if mc_sims else 0,
        "avg_risk_of_loss": sum(risk_losses) / len(risk_losses) if risk_losses else 0,
        "avg_median_outcome": sum(median_outcomes) / len(median_outcomes)
        if median_outcomes
        else 0,
        "confidence_low_days": conf_low_count,
        "confidence_coverage": 1 - (conf_low_count / has_simulation_pack)
        if has_simulation_pack > 0
        else 0,
    }


def generate_report(
    start_date: str = None,
    end_date: str = None,
    date: str = None,
    last: int = None,
) -> Dict[str, Any]:
    """Genera el reporte de simulación."""
    # Determine date range
    if last:
        end = datetime.now()
        start = end - timedelta(days=last)
        start_date = start.strftime("%Y-%m-%d")
        end_date = end.strftime("%Y-%m-%d")
    elif date:
        start_date = date
        end_date = date
    elif start_date and end_date:
        pass
    else:
        raise ValueError("Must specify --start/--end, --date, or --last")

    logger.info(f"Loading analytics from {start_date} to {end_date}...")

    analytics_list = load_analytics_range(start_date, end_date)

    if not analytics_list:
        logger.warning("No analytics data found for the specified period")
        return {"error": "no_data"}

    logger.info(f"Loaded {len(analytics_list)} analytics files")

    # Aggregate
    sim_agg = aggregate_simulation_pack(analytics_list)

    # Build report
    report = {
        "generated_at": datetime.now().isoformat(),
        "period": {
            "start": start_date,
            "end": end_date,
            "days": len(analytics_list),
        },
        "simulation_summary": sim_agg,
    }

    # Save
    report_path = (
        OUTPUTS_DIR / f"simulation_report_{datetime.now().strftime('%Y%m%d')}.json"
    )
    with open(report_path, "w") as f:
        json.dump(report, f, indent=2)

    logger.info(f"✅ Report saved: {report_path}")

    # Print summary
    logger.info(f"\n=== Simulation Report Summary ===")
    logger.info(f"Period: {start_date} to {end_date}")
    logger.info(f"Days analyzed: {len(analytics_list)}")

    if sim_agg.get("note"):
        logger.info(f"Simulation data: {sim_agg['note']}")
    else:
        logger.info(f"Days with simulation: {sim_agg.get('days_with_simulation')}")
        logger.info(
            f"Avg Expected Growth: {sim_agg.get('avg_expected_growth', 0) * 100:.1f}%"
        )
        logger.info(
            f"Avg Risk of Loss: {sim_agg.get('avg_risk_of_loss', 0) * 100:.1f}%"
        )
        logger.info(f"Avg Median Outcome: ${sim_agg.get('avg_median_outcome', 0):,.0f}")
        logger.info(
            f"Confidence coverage: {sim_agg.get('confidence_coverage', 0) * 100:.1f}%"
        )

    return report


def main():
    parser = argparse.ArgumentParser(description="Generate Simulation Report")
    parser.add_argument("--start", type=str, help="Start date (YYYY-MM-DD)")
    parser.add_argument("--end", type=str, help="End date (YYYY-MM-DD)")
    parser.add_argument("--date", type=str, help="Single date (YYYY-MM-DD)")
    parser.add_argument("--last", type=int, help="Last N days")

    args = parser.parse_args()

    generate_report(
        start_date=args.start,
        end_date=args.end,
        date=args.date,
        last=args.last,
    )


if __name__ == "__main__":
    main()
