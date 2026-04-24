#!/usr/bin/env python3
"""Fase 4 CLI: Edge Analytics + Promotion Gate."""

from __future__ import annotations

import argparse
import csv
import glob
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.integration.edge_analytics import (
    PreflightResult,
    compute_metrics_from_trades,
    compute_preflight,
    compute_rolling_metrics,
)
from src.integration.promotion_gate import (
    evaluate_all,
    load_thresholds,
)
from src.integration.score_calibration import (
    calibrate_scores,
    detect_degradation,
)


def load_execution_plan(path: Path) -> list[dict]:
    rows = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def load_jsonl_rows(path: Path) -> list[dict]:
    rows = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def load_trades_from_presets(
    pattern: str,
) -> list[dict]:
    rows = []
    for path_str in glob.glob(pattern):
        path = Path(path_str)
        if not path.exists():
            continue
        with open(path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                row["source_system"] = "B"
                row["strategy_id"] = row.get(
                    "preset_id", path.stem.replace("preset_", "")
                )
                rows.append(row)
    return rows


def load_phase3_summary(path: Path) -> dict:
    if not path.exists():
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def metrics_to_dict(m) -> dict:
    return {
        "source_system": m.source_system,
        "strategy_id": m.strategy_id,
        "trades": m.trades,
        "win_rate": round(m.win_rate, 4),
        "avg_win": round(m.avg_win, 4),
        "avg_loss": round(m.avg_loss, 4),
        "expectancy": round(m.expectancy, 4),
        "profit_factor": round(m.profit_factor, 4),
        "payoff_ratio": round(m.payoff_ratio, 4),
        "max_drawdown": round(m.max_drawdown, 4),
        "sharpe": round(m.sharpe, 4),
        "expectancy_per_100usd": round(m.expectancy_per_100usd, 4),
    }


def preflight_to_dict(p: PreflightResult) -> dict:
    return {
        "passed": p.passed,
        "hydrated_rate_A": round(p.hydrated_rate_A, 4),
        "hydrated_rate_B": round(p.hydrated_rate_B, 4),
        "common_date_start": p.common_date_start,
        "common_date_end": p.common_date_end,
        "common_sessions": p.common_sessions,
        "errors": p.errors,
    }


def main():
    parser = argparse.ArgumentParser(description="Phase 4 Edge Gate")
    parser.add_argument("--phase3-summary", help="Path to phase3_summary.json")
    parser.add_argument(
        "--execution-plan", required=True, help="Path to execution_plan.jsonl"
    )
    parser.add_argument(
        "--preflight-input",
        help=(
            "Path to broader JSONL dataset for historical preflight/calibration "
            "(por ejemplo routed_f2.jsonl o signals_f1.jsonl). "
            "Si se omite, usa --execution-plan."
        ),
    )
    parser.add_argument("--trades", required=True, help="Glob pattern for trades CSV")
    parser.add_argument(
        "--gate-config",
        default="config/integration/promotion_gate_v1_1.json",
        help="Path to gate config",
    )
    parser.add_argument("--out", required=True, help="Output base path")
    args = parser.parse_args()

    plan_path = Path(args.execution_plan)
    preflight_input_path = Path(args.preflight_input) if args.preflight_input else plan_path
    trades_pattern = args.trades
    config_path = Path(args.gate_config)
    output_base = Path(args.out)

    execution_plan = load_execution_plan(plan_path)
    preflight_input = load_jsonl_rows(preflight_input_path)
    trades = load_trades_from_presets(trades_pattern)

    preflight = compute_preflight(preflight_input)

    if not preflight.passed:
        report = {
            "preflight": preflight_to_dict(preflight),
            "status": "BLOCKED_PRE_FLIGHT",
            "message": (
                "F4/F5 blocked until hydration and overlap "
                "thresholds are met. Run refresh_ticker_cache.py then retry."
            ),
        }
        report_json = output_base.parent / "edge_gate_report.json"
        with open(report_json, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2)

        print("=== Phase 4 Edge Gate Report ===")
        print(f"Preflight passed: {preflight.passed}")
        for err in preflight.errors:
            print(f"  Error: {err}")
        print(f"Report: {report_json}")
        return

    all_metrics = []

    grouped: dict[str, list[dict]] = {}
    for t in trades:
        key = (t.get("source_system", ""), t.get("strategy_id", ""))
        if key not in grouped:
            grouped[key] = []
        grouped[key].append(t)

    for (source, strategy_id), group_trades in grouped.items():
        if not group_trades:
            continue
        metrics = compute_metrics_from_trades(group_trades)
        metrics.source_system = source
        metrics.strategy_id = strategy_id
        all_metrics.append(metrics)

    rolling_metrics = compute_rolling_metrics(trades, 90)
    is_degraded, pct_drop = detect_degradation(rolling_metrics, 90)

    thresholds = load_thresholds(config_path)
    promotions = evaluate_all(all_metrics, thresholds)

    calibrated = calibrate_scores(preflight_input, 252)

    output_base.parent.mkdir(parents=True, exist_ok=True)

    edge_csv = output_base.parent / "edge_metrics.csv"
    with open(edge_csv, "w", newline="", encoding="utf-8") as f:
        if all_metrics:
            writer = csv.DictWriter(
                f, fieldnames=list(metrics_to_dict(all_metrics[0]).keys())
            )
            writer.writeheader()
            for m in all_metrics:
                writer.writerow(metrics_to_dict(m))

    by_strategy_csv = output_base.parent / "edge_metrics_by_strategy.csv"
    with open(by_strategy_csv, "w", newline="", encoding="utf-8") as f:
        if all_metrics:
            writer = csv.DictWriter(
                f, fieldnames=list(metrics_to_dict(all_metrics[0]).keys())
            )
            writer.writeheader()
            for m in all_metrics:
                writer.writerow(metrics_to_dict(m))

    promo_csv = output_base.parent / "promotion_decisions.csv"
    with open(promo_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["source_system", "strategy_id", "decision", "reasons"])
        for p in promotions:
            writer.writerow(
                [p.source_system, p.strategy_id, p.decision, "|".join(p.reasons)]
            )

    report = {
        "preflight": preflight_to_dict(preflight),
        "total_metrics": len(all_metrics),
        "total_promotions": len(promotions),
        "promote_count": sum(1 for p in promotions if p.decision == "PROMOTE"),
        "hold_count": sum(1 for p in promotions if p.decision == "HOLD"),
        "reject_count": sum(1 for p in promotions if p.decision == "REJECT"),
        "rolling_degradation_detected": is_degraded,
        "rolling_degradation_pct": round(pct_drop, 4),
        "edge_metrics": [metrics_to_dict(m) for m in all_metrics],
        "calibrated_signals": len(calibrated),
        "promotions": [
            {
                "source_system": p.source_system,
                "strategy_id": p.strategy_id,
                "decision": p.decision,
                "reasons": p.reasons,
            }
            for p in promotions
        ],
    }

    report_json = output_base.parent / "edge_gate_report.json"
    with open(report_json, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    print("=== Phase 4 Edge Gate Report ===")
    print(f"Preflight passed: {preflight.passed}")
    if preflight.errors:
        for err in preflight.errors:
            print(f"  Error: {err}")
    print(f"Strategies analyzed: {len(all_metrics)}")
    print(f"PROMOTE: {report['promote_count']}")
    print(f"HOLD: {report['hold_count']}")
    print(f"REJECT: {report['reject_count']}")
    print(
        f"Rolling degradation: {report['rolling_degradation_detected']} ({report['rolling_degradation_pct']:.2%})"
    )
    print(f"\nOutputs:")
    print(f"  Edge metrics CSV: {edge_csv}")
    print(f"  By strategy CSV: {by_strategy_csv}")
    print(f"  Promotions CSV: {promo_csv}")
    print(f"  Report JSON: {report_json}")


if __name__ == "__main__":
    main()
