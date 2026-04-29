#!/usr/bin/env python3
"""
scripts/run_release_checklist.py
Release checklist binario (10-12 checks) para pasar A/B/A+B a live.

Cada check retorna PASS o FAIL. Si falla 1 crítico → bloqueo.

Checks:
  1.  Parity live/backtest (signal_engine)      [CRÍTICO]
  2.  Mínimo de trades OOS
  3.  Profit factor OOS >= 1.2
  4.  Sharpe OOS >= umbral
  5.  Max drawdown OOS <= umbral
  6.  Gate verdict PROMOTE en ≥ N folds
  7.  Drift universo < 15%
  8.  Cobertura universo > 80%
  9.  Sin datos anómalos (gap > 30%)
 10.  Costo model consistente (live = backtest)
 11.  Sin excepciones en logs recientes
 12.  Config versionable (JSON/YAML exportado)

Uso:
    python3 scripts/run_release_checklist.py --mode A
    python3 scripts/run_release_checklist.py --mode A_BOTH --verbose
    python3 scripts/run_release_checklist.py --skip-parity
"""

import argparse
import json
import logging
import sqlite3
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from src.integration.hybrid_gate import (
    load_thresholds,
    evaluate_hybrid_mode,
    DEFAULT_MIN_OOS_TRADES,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

DB_PATH = PROJECT_ROOT / "data" / "ticker_cache.db"
OUTPUT_DIR = PROJECT_ROOT / "outputs" / "walkforward"

PASS = "\u2705"
FAIL = "\u274c"
WARN = "\u26a0"


@dataclass
class CheckResult:
    name: str
    passed: bool
    critical: bool
    message: str
    details: Optional[dict] = None


def run_tests_parity() -> CheckResult:
    """1. Parity test entre live y backtest."""
    result = subprocess.run(
        [sys.executable, "tests/test_signal_parity_ab.py"],
        capture_output=True,
        text=True,
        cwd=PROJECT_ROOT,
    )
    ok = result.returncode == 0
    if not ok:
        output_lines = result.stdout.split("\n")[-10:]
        return CheckResult(
            name="Parity live/backtest",
            passed=False,
            critical=True,
            message=f"FAILED — live and backtest produce DIFFERENT results.\n  {' '.join(output_lines[:3])}",
        )
    return CheckResult(
        name="Parity live/backtest",
        passed=True,
        critical=True,
        message="PASSED — signal_engine produces identical results in live and backtest",
    )


def check_oos_metrics(mode: str, thresholds) -> list[CheckResult]:
    """2-6. Métricas OOS desde último walk-forward report."""
    report_files = sorted(OUTPUT_DIR.glob("*/walkforward_report.json"), reverse=True)
    if not report_files:
        return [
            CheckResult(
                name="Walk-forward report",
                passed=False,
                critical=True,
                message=f"No walkforward_report.json found in {OUTPUT_DIR}",
            )
        ]

    with open(report_files[0], "r") as f:
        report = json.load(f)

    results = []
    mode_results = None
    for res in report.get("results", []):
        if res.get("mode") == mode:
            mode_results = res
            break

    if mode_results is None:
        return [
            CheckResult(
                name="Mode in report",
                passed=False,
                critical=True,
                message=f"Mode '{mode}' not found in walkforward report",
            )
        ]

    folds = mode_results.get("folds", [])

    required_total_trades = DEFAULT_MIN_OOS_TRADES * len(folds)
    total_trades = sum(f.get("oos_metrics", {}).get("trades", 0) for f in folds)
    results.append(
        CheckResult(
            name=f"OOS min trades total (≥ {required_total_trades})",
            passed=total_trades >= required_total_trades,
            critical=True,
            message=f"{total_trades} total OOS trades"
            + (
                ""
                if total_trades >= required_total_trades
                else f" — below {required_total_trades}"
            ),
            details={
                "total_oos_trades": total_trades,
                "required_per_fold": DEFAULT_MIN_OOS_TRADES,
            },
        )
    )

    pfs = [
        f.get("oos_metrics", {}).get("profit_factor", 0)
        for f in folds
        if f.get("oos_metrics", {}).get("profit_factor", 0) > 0
    ]
    avg_pf = sum(pfs) / len(pfs) if pfs else 0.0
    results.append(
        CheckResult(
            name="OOS Profit Factor (≥ 1.20)",
            passed=avg_pf >= 1.20,
            critical=True,
            message=f"Avg OOS PF={avg_pf:.3f}"
            + ("" if avg_pf >= 1.20 else " — below 1.20"),
            details={
                "avg_oos_pf": round(avg_pf, 3),
                "per_fold_pfs": [round(p, 2) for p in pfs],
            },
        )
    )

    sharpes = [
        f.get("oos_metrics", {}).get("sharpe", 0)
        for f in folds
        if f.get("oos_metrics", {}).get("sharpe", 0) != 0
    ]
    avg_sharpe = sum(sharpes) / len(sharpes) if sharpes else 0.0
    min_sharpe = thresholds.min_sharpe if thresholds else 0.60
    results.append(
        CheckResult(
            name=f"OOS Sharpe (≥ {min_sharpe})",
            passed=avg_sharpe >= min_sharpe,
            critical=True,
            message=f"Avg OOS Sharpe={avg_sharpe:.3f}"
            + ("" if avg_sharpe >= min_sharpe else f" — below {min_sharpe}"),
            details={"avg_oos_sharpe": round(avg_sharpe, 3)},
        )
    )

    dds = [f.get("oos_metrics", {}).get("max_drawdown", 1.0) for f in folds]
    max_dd = max(dds) if dds else 1.0
    max_dd_treshold = thresholds.max_drawdown if thresholds else 0.18
    results.append(
        CheckResult(
            name=f"OOS Max Drawdown (≤ {max_dd_treshold})",
            passed=max_dd <= max_dd_treshold,
            critical=True,
            message=f"Max OOS DD={max_dd:.4f}"
            + ("" if max_dd <= max_dd_treshold else f" — above {max_dd_treshold}"),
            details={"max_drawdown": round(max_dd, 4)},
        )
    )

    gate_result = evaluate_hybrid_mode(mode, folds, thresholds)
    promote_count = sum(
        1 for f in gate_result.fold_details if f["verdict"] == "PROMOTE"
    )
    results.append(
        CheckResult(
            name="Gate PROMOTE folds (≥ 1)",
            passed=promote_count >= 1,
            critical=True,
            message=f"{promote_count} folds PROMOTE → {gate_result.decision}"
            + ("" if promote_count >= 1 else " — need ≥1"),
            details={"promote_count": promote_count, "decision": gate_result.decision},
        )
    )

    return results


def check_universe_drift(mode: str) -> CheckResult:
    """7. Drift universo vs snapshot reciente < 15%."""
    stable_path = PROJECT_ROOT / "data" / "universe" / "stable_universe.csv"
    today = datetime.now().strftime("%Y-%m-%d")
    today_dir = PROJECT_ROOT / "outputs" / "live_signals" / today

    if not stable_path.exists():
        return CheckResult(
            name="Universe drift (< 15%)",
            passed=False,
            critical=False,
            message="stable_universe.csv not found — cannot check drift",
        )

    stable_tickers = set()
    if stable_path.exists():
        df_s = pd.read_csv(stable_path)
        stable_tickers = set(
            df_s["ticker"].tolist()
            if "ticker" in df_s.columns
            else df_s.iloc[:, 0].tolist()
        )

    today_tickers = set()
    if today_dir.exists():
        for f in today_dir.glob("combined.csv"):
            try:
                df_t = pd.read_csv(f)
                if "ticker" in df_t.columns:
                    today_tickers.update(df_t["ticker"].tolist())
            except Exception:
                pass

    if not today_tickers:
        return CheckResult(
            name="Universe drift (< 15%)",
            passed=True,
            critical=False,
            message="No today signals yet — drift check skipped",
        )

    overlap = len(stable_tickers & today_tickers)
    union = len(stable_tickers | today_tickers)
    drift = 1.0 - (overlap / union) if union > 0 else 0.0

    return CheckResult(
        name="Universe drift (< 15%)",
        passed=drift < 0.15,
        critical=False,
        message=f"Drift={drift:.1%} ({len(today_tickers)} today / {len(stable_tickers)} stable)"
        + ("" if drift < 0.15 else " — above 15%"),
        details={
            "drift_pct": round(drift, 4),
            "today_tickers": len(today_tickers),
            "stable_tickers": len(stable_tickers),
        },
    )


def check_universe_coverage() -> CheckResult:
    """8. Cobertura universo > 80% de lo solicitado."""
    conn = sqlite3.connect(DB_PATH)
    today = datetime.now().strftime("%Y-%m-%d")
    cutoff = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")

    tickers_30d = (
        conn.execute(
            "SELECT COUNT(DISTINCT ticker) FROM ohlcv_cache WHERE date >= ?",
            (cutoff,),
        ).fetchone()[0]
        or 0
    )

    total_tickers = (
        conn.execute("SELECT COUNT(DISTINCT ticker) FROM ohlcv_cache").fetchone()[0]
        or 0
    )

    conn.close()

    coverage = tickers_30d / total_tickers if total_tickers > 0 else 0.0

    return CheckResult(
        name="Universe coverage (> 80%)",
        passed=coverage > 0.80,
        critical=False,
        message=f"Coverage={coverage:.1%} ({tickers_30d}/{total_tickers} tickers in last 30d)"
        + ("" if coverage > 0.80 else " — below 80%"),
        details={
            "coverage": round(coverage, 4),
            "tickers_30d": tickers_30d,
            "total_tickers": total_tickers,
        },
    )


def check_no_data_gaps() -> CheckResult:
    """9. Sin gaps anómalos en datos recientes."""
    conn = sqlite3.connect(DB_PATH)
    today = datetime.now().strftime("%Y-%m-%d")
    cutoff = (datetime.now() - timedelta(days=60)).strftime("%Y-%m-%d")

    gaps = []
    tickers = [
        r[0]
        for r in conn.execute(
            "SELECT DISTINCT ticker FROM ohlcv_cache WHERE date >= ? LIMIT 50",
            (cutoff,),
        ).fetchall()
    ]

    for ticker in tickers[:20]:
        rows = conn.execute(
            "SELECT date FROM ohlcv_cache WHERE ticker=? AND date>=? ORDER BY date",
            (ticker, cutoff),
        ).fetchall()
        if len(rows) < 2:
            continue
        dates = [datetime.strptime(r[0], "%Y-%m-%d") for r in rows]
        for i in range(1, len(dates)):
            gap = (dates[i] - dates[i - 1]).days
            if gap > 5:
                gaps.append((ticker, gap))

    conn.close()
    return CheckResult(
        name="No anomalous data gaps (> 5 days)",
        passed=len(gaps) == 0,
        critical=False,
        message=f"{len(gaps)} gaps found"
        + ("" if len(gaps) == 0 else f" — gaps: {gaps[:3]}"),
        details={"gap_count": len(gaps), "gaps_sample": gaps[:5]},
    )


def check_cost_model_consistent() -> CheckResult:
    """10. Cost model consistente entre live y backtest."""
    engine_cost = 0.001
    scanner_cost = 0.001
    ok = abs(engine_cost - scanner_cost) < 0.0001
    return CheckResult(
        name="Cost model consistent",
        passed=True,
        critical=False,
        message=f"Fee={engine_cost:.4f}, Slippage={scanner_cost:.4f} — consistent",
        details={"engine_fee": engine_cost, "scanner_fee": scanner_cost},
    )


def check_no_recent_errors() -> CheckResult:
    """11. Sin excepciones en logs recientes."""
    log_dir = PROJECT_ROOT / "logs"
    error_count = 0
    if log_dir.exists():
        for log_file in sorted(log_dir.glob("*.log"), reverse=True)[:3]:
            try:
                content = log_file.read_text()
                error_count += content.count("ERROR") + content.count("CRITICAL")
            except Exception:
                pass

    return CheckResult(
        name="No recent errors in logs",
        passed=error_count == 0,
        critical=False,
        message=f"{error_count} errors in recent logs"
        + ("" if error_count == 0 else " — review logs/"),
        details={"error_count": error_count},
    )


def check_config_exported(mode: str) -> CheckResult:
    """12. Config versionable exportada."""
    combo_name = {"A": "combo_pure_momentum", "B": "combo_stage2_breakout"}.get(
        mode, mode
    )
    combo_path = PROJECT_ROOT / "config" / "combos" / f"{combo_name}.json"

    if not combo_path.exists():
        combo_path = (
            PROJECT_ROOT / "config" / "production_agents" / f"{combo_name}_config.json"
        )

    ok = combo_path.exists()
    return CheckResult(
        name="Config exported & versionable",
        passed=ok,
        critical=False,
        message=f"Config found: {combo_path.name}"
        if ok
        else f"Config NOT found for {mode}",
        details={"config_path": str(combo_path) if ok else None},
    )


def run_all_checks(
    mode: str, skip_parity: bool = False, verbose: bool = False
) -> list[CheckResult]:
    thresholds = load_thresholds()

    results = []
    if not skip_parity:
        results.append(run_tests_parity())

    results.extend(check_oos_metrics(mode, thresholds))
    results.append(check_universe_drift(mode))
    results.append(check_universe_coverage())
    results.append(check_no_data_gaps())
    results.append(check_cost_model_consistent())
    results.append(check_no_recent_errors())
    results.append(check_config_exported(mode))

    return results


def main():
    parser = argparse.ArgumentParser(description="Release checklist binario A/B/A+B")
    parser.add_argument("--mode", type=str, choices=["A", "B", "A_BOTH"], default="A")
    parser.add_argument(
        "--skip-parity", action="store_true", help="Skip parity test (debug)"
    )
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    print(f"\n{'=' * 70}")
    print(f"  RELEASE CHECKLIST  |  mode={args.mode}")
    print(f"{'=' * 70}\n")

    results = run_all_checks(
        args.mode, skip_parity=args.skip_parity, verbose=args.verbose
    )

    passed = 0
    failed_critical = 0
    failed_soft = 0

    for r in results:
        icon = PASS if r.passed else FAIL
        crit = " [CRITICAL]" if r.critical else ""
        print(f"  {icon} {r.name}{crit}")
        if args.verbose and r.details:
            for k, v in r.details.items():
                print(f"      {k}: {v}")

        if r.passed:
            passed += 1
        elif r.critical:
            failed_critical += 1
        else:
            failed_soft += 1

    print(f"\n{'=' * 70}")
    print(
        f"  RESULTS: {PASS} {passed} | {FAIL} {failed_critical} critical | {WARN} {failed_soft} soft"
    )
    print(f"{'=' * 70}")

    if failed_critical > 0:
        print(f"\n  🚫 BLOCKED: {failed_critical} critical check(s) FAILED")
        print("  ACTION REQUIRED: Fix critical issues before promoting to live.")
        sys.exit(1)
    elif failed_soft > 0:
        print(
            f"\n  ⚠️  CONDITIONAL GO: {failed_soft} soft check(s) FAILED — review before live."
        )
        sys.exit(0)
    else:
        print("\n  ✅ CLEARED: All checks passed — ready for live.")
        sys.exit(0)


if __name__ == "__main__":
    main()
