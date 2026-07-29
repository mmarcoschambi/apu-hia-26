"""
run_dynamic_switch_backtest.py — Three-Way Mode Comparison (Track C)

Runs 3 backtest modes and compares:
  Mode A: always ATTACK       (risk_mult=1.0, no theme filter)
  Mode B: always DEFENSE_FULL (risk_mult=0.35, theme filter ON)
  Mode C: dynamic switching   (uses daily_health_scores regime_mode)

Output: JSON with CAGR, Sharpe, MDD per mode + regression verdict.

Usage:
  # Quick mode profile analysis:
  python3 scripts/run_dynamic_switch_backtest.py --start 2023-01-01 --end 2024-12-31

  # Full backtest (requires run_backtest from backtest_via_signal_engine):
  python3 scripts/run_dynamic_switch_backtest.py --start 2023-01-01 --end 2024-12-31 --run-backtest
"""

import argparse
import json
import sqlite3
import sys
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

REGRESSION_THRESHOLD: float = 0.10
"""Maximum allowable relative return regression vs best static mode (10%)."""

RISK_MULT_MAP: dict[str, float] = {
    "ATTACK": 1.0,
    "DEFENSE_PARTIAL": 0.75,
    "DEFENSE_FULL": 0.35,
}
"""Risk multiplier per mode from DRS-REQ-01."""

THEME_FILTER_MAP: dict[str, bool] = {
    "ATTACK": False,
    "DEFENSE_PARTIAL": True,
    "DEFENSE_FULL": True,
}
"""Theme filter state per mode from DRS-REQ-01."""

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = PROJECT_ROOT / "data" / "ticker_cache.db"


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------

@dataclass
class ModeAssignment:
    """Per-date mode assignment for one of the three strategies."""
    date: str
    mode: str
    risk_multiplier: float
    use_theme_group_filter: bool


@dataclass
class ComparisonVerdict:
    """Result of comparing dynamic vs best static mode."""
    best_static_mode: str
    best_static_return: float
    dynamic_return: float
    dynamic_regression_pct: float
    passed: bool


# ---------------------------------------------------------------------------
# Health score → mode mapping (DRS-REQ-01 compliant)
# ---------------------------------------------------------------------------

def _score_to_mode(health_score: int) -> str:
    """
    Map health_score (0-7) to mode name per DRS-REQ-01.

    >= 6 → ATTACK
    4-5  → DEFENSE_PARTIAL
    < 4  → DEFENSE_FULL
    """
    if health_score >= 6:
        return "ATTACK"
    elif health_score >= 4:
        return "DEFENSE_PARTIAL"
    else:
        return "DEFENSE_FULL"


# ---------------------------------------------------------------------------
# Core logic (pure functions — testable without DB)
# ---------------------------------------------------------------------------

def compute_mode_assignments(records: list[dict[str, Any]]) -> dict[str, list[ModeAssignment]]:
    """
    Compute three mode profiles from health score records.

    Args:
        records: List of dicts with 'date' (str) and 'health_score' (int).

    Returns:
        dict with keys:
          - attack_profile:  all-ATTACK assignments
          - defense_profile: all-DEFENSE_FULL assignments
          - dynamic_profile:  mode per date based on health_score
    """
    attack_profile: list[ModeAssignment] = []
    defense_profile: list[ModeAssignment] = []
    dynamic_profile: list[ModeAssignment] = []

    for rec in records:
        date = rec["date"]
        score = rec["health_score"]

        # Mode A: always ATTACK
        attack_profile.append(ModeAssignment(
            date=date,
            mode="ATTACK",
            risk_multiplier=RISK_MULT_MAP["ATTACK"],
            use_theme_group_filter=THEME_FILTER_MAP["ATTACK"],
        ))

        # Mode B: always DEFENSE_FULL
        defense_profile.append(ModeAssignment(
            date=date,
            mode="DEFENSE_FULL",
            risk_multiplier=RISK_MULT_MAP["DEFENSE_FULL"],
            use_theme_group_filter=THEME_FILTER_MAP["DEFENSE_FULL"],
        ))

        # Mode C: dynamic per health_score
        mode = _score_to_mode(score)
        dynamic_profile.append(ModeAssignment(
            date=date,
            mode=mode,
            risk_multiplier=RISK_MULT_MAP[mode],
            use_theme_group_filter=THEME_FILTER_MAP[mode],
        ))

    return {
        "attack_profile": attack_profile,
        "defense_profile": defense_profile,
        "dynamic_profile": dynamic_profile,
    }


def compare_mode_metrics(
    metrics_attack: dict[str, float],
    metrics_defense: dict[str, float],
    metrics_dynamic: dict[str, float],
    threshold: float = REGRESSION_THRESHOLD,
) -> ComparisonVerdict:
    """
    Compare dynamic mode CAGR vs the best static mode.

    The no-regression gate:
        regression = (dynamic_return - best_static_return) / abs(best_static_return)
        PASS if regression >= -threshold (i.e. not worse than threshold % relative drawdown)

    Args:
        metrics_attack:  CAGR, Sharpe, MDD for always-ATTACK mode.
        metrics_defense: CAGR, Sharpe, MDD for always-DEFENSE_FULL mode.
        metrics_dynamic: CAGR, Sharpe, MDD for dynamic-switching mode.
        threshold:       Maximum allowed regression (0.10 = 10%).

    Returns:
        ComparisonVerdict with best static mode and pass/fail.
    """
    attack_return = metrics_attack.get("CAGR", 0.0)
    defense_return = metrics_defense.get("CAGR", 0.0)
    dynamic_return = metrics_dynamic.get("CAGR", 0.0)

    # Determine best static by CAGR
    if attack_return >= defense_return:
        best_static_mode = "ATTACK"
        best_static_return = attack_return
    else:
        best_static_mode = "DEFENSE_FULL"
        best_static_return = defense_return

    # Compute relative regression
    if best_static_return == 0:
        # If best static returned 0, dynamic >= 0 is an improvement → pass
        regression_pct = 0.0 if dynamic_return >= 0 else -1.0
    else:
        regression_pct = (dynamic_return - best_static_return) / abs(best_static_return)

    passed = regression_pct >= -threshold

    return ComparisonVerdict(
        best_static_mode=best_static_mode,
        best_static_return=best_static_return,
        dynamic_return=dynamic_return,
        dynamic_regression_pct=round(regression_pct, 6),
        passed=passed,
    )


def format_comparison_output(
    metrics_attack: dict[str, float],
    metrics_defense: dict[str, float],
    metrics_dynamic: dict[str, float],
    verdict: ComparisonVerdict,
) -> dict[str, Any]:
    """
    Format comparison results into a JSON-serializable dict.

    Args:
        metrics_attack:  CAGR, Sharpe, MDD for Mode A.
        metrics_defense: CAGR, Sharpe, MDD for Mode B.
        metrics_dynamic: CAGR, Sharpe, MDD for Mode C.
        verdict:         ComparisonVerdict from compare_mode_metrics().

    Returns:
        Dict ready for json.dump().
    """
    return {
        "mode_a_attack": {
            "CAGR": round(metrics_attack.get("CAGR", 0.0), 2),
            "Sharpe": round(metrics_attack.get("Sharpe", 0.0), 3),
            "MDD": round(metrics_attack.get("MDD", 0.0), 2),
        },
        "mode_b_defense": {
            "CAGR": round(metrics_defense.get("CAGR", 0.0), 2),
            "Sharpe": round(metrics_defense.get("Sharpe", 0.0), 3),
            "MDD": round(metrics_defense.get("MDD", 0.0), 2),
        },
        "mode_c_dynamic": {
            "CAGR": round(metrics_dynamic.get("CAGR", 0.0), 2),
            "Sharpe": round(metrics_dynamic.get("Sharpe", 0.0), 3),
            "MDD": round(metrics_dynamic.get("MDD", 0.0), 2),
        },
        "verdict": {
            "best_static_mode": verdict.best_static_mode,
            "best_static_return": round(verdict.best_static_return, 2),
            "dynamic_return": round(verdict.dynamic_return, 2),
            "dynamic_regression_pct": round(verdict.dynamic_regression_pct, 4),
            "passed": verdict.passed,
            "no_regression_gate": f"Dynamic must not regress >{REGRESSION_THRESHOLD:.0%} vs best static",
        },
    }


# ---------------------------------------------------------------------------
# DB I/O
# ---------------------------------------------------------------------------

def load_health_scores(
    db_path: str | Path,
    start_date: str,
    end_date: str,
) -> list[dict[str, Any]]:
    """
    Load health score records from the daily_health_scores table.

    Args:
        db_path:    Path to the SQLite database.
        start_date: Inclusive start date (YYYY-MM-DD).
        end_date:   Inclusive end date (YYYY-MM-DD).

    Returns:
        List of dicts with 'date' and 'health_score'.
    """
    conn = sqlite3.connect(str(db_path))
    try:
        rows = conn.execute(
            "SELECT date, health_score FROM daily_health_scores "
            "WHERE date >= ? AND date <= ? || ' 23:59:59' "
            "ORDER BY date",
            (start_date, end_date),
        ).fetchall()
        return [{"date": row[0], "health_score": int(row[1])} for row in rows]
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Mode profile statistics
# ---------------------------------------------------------------------------

def compute_mode_profile_stats(
    profiles: dict[str, list[ModeAssignment]],
) -> dict[str, dict[str, Any]]:
    """
    Compute summary statistics for each mode profile.

    Returns per-profile: total days, mode distribution, average risk_mult.
    """
    stats: dict[str, dict[str, Any]] = {}
    for key, profile in profiles.items():
        total = len(profile)
        if total == 0:
            stats[key] = {
                "total_days": 0,
                "mode_distribution": {},
                "avg_risk_multiplier": 0.0,
            }
            continue

        from collections import Counter
        mode_counts = Counter(ma.mode for ma in profile)
        avg_risk = sum(ma.risk_multiplier for ma in profile) / total

        stats[key] = {
            "total_days": total,
            "mode_distribution": dict(mode_counts),
            "avg_risk_multiplier": round(avg_risk, 4),
        }
    return stats


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Three-way mode comparison: always-ATTACK vs always-DEFENSE vs dynamic.",
    )
    parser.add_argument("--start", default="2023-01-01", help="Start date (YYYY-MM-DD)")
    parser.add_argument("--end", default="2024-12-31", help="End date (YYYY-MM-DD)")
    parser.add_argument(
        "--universe-size",
        type=int,
        default=50,
        help="Backtest universe size (used with --run-backtest)",
    )
    parser.add_argument(
        "--run-backtest",
        action="store_true",
        help="Run full backtest engine (requires DB + market data)",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    start, end = args.start, args.end

    # Phase 1: Load health scores and compute mode profiles
    records = load_health_scores(DB_PATH, start, end)
    if not records:
        print(json.dumps({"error": f"No health scores found for {start} to {end}"}, indent=2))
        sys.exit(1)

    profiles = compute_mode_assignments(records)
    stats = compute_mode_profile_stats(profiles)

    output: dict[str, Any] = {
        "range": {"start": start, "end": end, "trading_days": len(records)},
        "profile_statistics": stats,
    }

    if args.run_backtest:
        # Full backtest mode — requires backtest_via_signal_engine
        try:
            _run_full_backtest_comparison(start, end, args.universe_size, records, output)
        except ImportError as e:
            print(json.dumps({"error": f"Backtest engine unavailable: {e}"}, indent=2))
            sys.exit(1)
    else:
        # Profile-only mode (no actual backtest)
        output["verdict"] = {
            "mode": "profile_only",
            "message": "Run with --run-backtest for full CAGR/Sharpe/MDD comparison",
        }

    print(json.dumps(output, indent=2))


def _run_full_backtest_comparison(
    start: str,
    end: str,
    universe_size: int,
    records: list[dict[str, Any]],
    output: dict[str, Any],
) -> None:
    """
    Full three-way backtest comparison using run_backtest.
    Temporarily overwrites health_scores table for static modes.
    """
    from scripts.backtest_via_signal_engine import run_backtest

    conn = sqlite3.connect(str(DB_PATH))
    try:
        # Backup original health scores
        original = conn.execute(
            "SELECT date, health_score, regime_mode FROM daily_health_scores "
            "WHERE date >= ? AND date <= ? || ' 23:59:59' ORDER BY date",
            (start, end),
        ).fetchall()

        # Mode A: all ATTACK
        conn.executemany(
            "UPDATE daily_health_scores SET health_score=?, regime_mode=? WHERE date=?",
            [(7, "ATTACK", row[0]) for row in original],
        )
        conn.commit()
        run_backtest(start, end, 100000.0, universe_size, "mode_a_attack",
                     use_variant_e=False, index_name="RUSSELL1000")
        # Read back metrics
        metrics_a = _read_metrics("mode_a_attack")

        # Mode B: all DEFENSE_FULL
        conn.executemany(
            "UPDATE daily_health_scores SET health_score=?, regime_mode=? WHERE date=?",
            [(1, "DEFENSE_FULL", row[0]) for row in original],
        )
        conn.commit()
        run_backtest(start, end, 100000.0, universe_size, "mode_b_defense",
                     use_variant_e=True, index_name="RUSSELL1000")
        metrics_b = _read_metrics("mode_b_defense")

        # Mode C: restore original
        conn.executemany(
            "UPDATE daily_health_scores SET health_score=?, regime_mode=? WHERE date=?",
            [(row[1], row[2], row[0]) for row in original],
        )
        conn.commit()
        run_backtest(start, end, 100000.0, universe_size, "mode_c_dynamic",
                     use_variant_e=True, index_name="RUSSELL1000")
        metrics_c = _read_metrics("mode_c_dynamic")

    finally:
        # Restore original in all cases
        conn.executemany(
            "UPDATE daily_health_scores SET health_score=?, regime_mode=? WHERE date=?",
            [(row[1], row[2], row[0]) for row in original],
        )
        conn.commit()
        conn.close()

    # Compare
    verdict = compare_mode_metrics(metrics_a, metrics_b, metrics_c)
    comparison = format_comparison_output(metrics_a, metrics_b, metrics_c, verdict)
    output.update(comparison)


def _read_metrics(tag: str) -> dict[str, float]:
    """Read backtest metrics from saved JSON output."""
    metrics_path = PROJECT_ROOT / "outputs" / "backtests" / f"{tag}_metrics.json"
    if not metrics_path.exists():
        return {"CAGR": 0.0, "Sharpe": 0.0, "MDD": 0.0}
    with open(metrics_path) as f:
        data = json.load(f)
    return {
        "CAGR": data.get("annualized_return", data.get("total_return", 0.0)),
        "Sharpe": data.get("sharpe_ratio", 0.0),
        "MDD": data.get("max_drawdown", 0.0),
    }


if __name__ == "__main__":
    main()
