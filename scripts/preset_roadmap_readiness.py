#!/usr/bin/env python3
"""
Roadmap readiness checker for screener preset architecture.

This command does not require DB access.
It validates preset spec structure and reports implementation readiness.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Dict, List

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SPEC = PROJECT_ROOT / "config" / "presets" / "screener_presets_v1.json"

IMPLEMENTED_FILTERS = {
    "market_cap_min",
    "avg_volume_50_min",
    "adr_50_min",
    "rs_1m_percentile_min",
    "trend_base",
    "rel_volume_min",
    "power_play",
    "power_play_cluster_20d_min3",
    "vcs_score_min",
    "near_52w_high_band",
    "weekly_return_min",
}

SCAFFOLD_FILTERS = {
    "ll_hl_confirmed",
    "fib_0618_break_between_hl_and_swing_high",
    "second_pivot_break_swing_high",
    "downtrend_line_break",
}


def load_spec(path: Path) -> Dict:
    with open(path, "r", encoding="utf-8-sig") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError("Spec root must be a mapping")
    return data


def summarize(spec: Dict) -> Dict:
    presets: List[Dict] = spec.get("presets", [])
    total = len(presets)
    ready = 0
    blocked = 0

    missing_filters = []
    blockers = []

    for p in presets:
        reqs = p.get("requires", [])
        unresolved = [r for r in reqs if r not in IMPLEMENTED_FILTERS and r not in SCAFFOLD_FILTERS]
        if unresolved:
            missing_filters.append((p.get("id", "?"), unresolved))

        hard = [r for r in reqs if r in SCAFFOLD_FILTERS]
        if hard:
            blocked += 1
            blockers.append((p.get("id", "?"), hard))
        else:
            ready += 1

    return {
        "total": total,
        "ready_now": ready,
        "blocked_by_complex": blocked,
        "missing_filters": missing_filters,
        "blockers": blockers,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Check readiness of screener presets roadmap")
    parser.add_argument("--spec", type=str, default=str(DEFAULT_SPEC))
    args = parser.parse_args()

    spec_path = Path(args.spec)
    spec = load_spec(spec_path)
    result = summarize(spec)

    print("=" * 80)
    print("SCREENER PRESET ROADMAP READINESS")
    print("=" * 80)
    print(f"Spec: {spec_path}")
    print(f"Total presets: {result['total']}")
    print(f"Ready now (implementable): {result['ready_now']}")
    print(f"Blocked by complex filters: {result['blocked_by_complex']}")

    if result["missing_filters"]:
        print("\nMissing filter ids in library:")
        for pid, missing in result["missing_filters"]:
            print(f"  - {pid}: {', '.join(missing)}")

    if result["blockers"]:
        print("\nComplex blockers (expected for stage third):")
        for pid, hard in result["blockers"]:
            print(f"  - {pid}: {', '.join(hard)}")


if __name__ == "__main__":
    main()
