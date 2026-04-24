#!/usr/bin/env python3
"""Fase 3 CLI: Risk Gate + Sizing + Shadow Integration."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.integration.execution_plan import ExecutionPlanRow
from src.integration.price_hydrator import hydrate_prices
from src.integration.risk_gate import RiskGateConfig, apply_risk_gate, load_config
from src.integration.routed_signal import RoutedSignal
from src.integration.signal_router import SignalRouter


def load_routed_signals(input_path: Path) -> list[RoutedSignal]:
    from src.integration.unified_signal import UnifiedSignal

    signals = []
    with open(input_path, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                d = json.loads(line)
                signal = UnifiedSignal(
                    source_system=d["source_system"],
                    strategy_id=d["strategy_id"],
                    ticker=d["ticker"],
                    timeframe=d["timeframe"],
                    signal_time=d["signal_time"],
                    side=d["side"],
                    entry_type=d["entry_type"],
                    entry_price_ref=d["entry_price_ref"],
                    stop_price=d.get("stop_price"),
                    target_price=d.get("target_price"),
                    raw_score=d.get("raw_score", 0.0),
                    normalized_score=d.get("normalized_score", 0.0),
                    confidence=d.get("confidence", 0.5),
                    risk_unit=d.get("risk_unit"),
                    reason_codes=d.get("reason_codes", ""),
                    metadata=d.get("metadata", {}),
                )
                routed = RoutedSignal(
                    signal=signal,
                    router_decision=d.get("router_decision", "accepted"),
                    router_reason=d.get("router_reason", "won_by_score"),
                    collision_key=d.get("collision_key", ""),
                )
                signals.append(routed)
    return signals


def plan_to_dict(plan: ExecutionPlanRow) -> dict:
    return {
        "source_system": plan.source_system,
        "strategy_id": plan.strategy_id,
        "ticker": plan.ticker,
        "trade_date": plan.trade_date,
        "side": plan.side,
        "entry_type": plan.entry_type,
        "entry_price_ref": plan.entry_price_ref,
        "hydrated_price_source": plan.hydrated_price_source,
        "stop_price": plan.stop_price,
        "target_price": plan.target_price,
        "risk_budget_usd": plan.risk_budget_usd,
        "risk_per_trade_usd": plan.risk_per_trade_usd,
        "per_share_risk": plan.per_share_risk,
        "shares": plan.shares,
        "notional_usd": plan.notional_usd,
        "router_reason": plan.router_reason,
        "collision_key": plan.collision_key,
        "metadata": plan.metadata,
    }


def export_plan(
    plans: list[ExecutionPlanRow],
    output_path: Path,
    format: str = "jsonl",
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if format == "jsonl":
        with open(output_path, "w", encoding="utf-8") as f:
            for plan in plans:
                f.write(json.dumps(plan_to_dict(plan), ensure_ascii=False) + "\n")
    else:
        import csv

        if not plans:
            return
        fieldnames = list(plan_to_dict(plans[0]).keys())
        with open(output_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for plan in plans:
                writer.writerow(plan_to_dict(plan))


def export_rejected(
    rejected: list[dict],
    output_path: Path,
) -> None:
    if not rejected:
        return
    output_path.parent.mkdir(parents=True, exist_ok=True)
    import csv

    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["ticker", "reason", "details"])
        for r in rejected:
            writer.writerow(
                [r.get("signal", {}).signal.ticker, r.get("reason", ""), str(r)]
            )


def main():
    parser = argparse.ArgumentParser(description="Risk Gate Phase 3")
    parser.add_argument(
        "--router-accepted", required=True, help="Path to router accepted JSONL"
    )
    parser.add_argument(
        "--db-path", default="data/ticker_cache.db", help="Path to ticker cache DB"
    )
    parser.add_argument(
        "--capital", type=float, default=100000, help="Total capital USD"
    )
    parser.add_argument(
        "--risk-per-trade", type=float, default=1000, help="Risk per trade USD"
    )
    parser.add_argument("--config", help="Path to risk gate config JSON")
    parser.add_argument("--out", required=True, help="Output base path")
    args = parser.parse_args()

    accepted_path = Path(args.router_accepted)
    db_path = Path(args.db_path)
    output_base = Path(args.out)

    routed_signals = load_routed_signals(accepted_path)

    if not routed_signals:
        print("No accepted signals to process")
        return

    hydrated, price_rejected = hydrate_prices(routed_signals, db_path)

    if args.config:
        config = load_config(Path(args.config))
    else:
        config = RiskGateConfig(
            capital_total_usd=args.capital,
            risk_per_trade_usd=args.risk_per_trade,
        )

    plans, gate_rejected = apply_risk_gate(hydrated, config)

    all_rejected = price_rejected + gate_rejected

    export_plan(plans, output_base.with_suffix(".jsonl"), "jsonl")
    export_plan(plans, output_base.with_suffix(".csv"), "csv")
    export_rejected(all_rejected, output_base.parent / "risk_rejected.csv")

    exposure_a = sum(p.notional_usd for p in plans if p.source_system == "A")
    exposure_b = sum(p.notional_usd for p in plans if p.source_system == "B")

    summary = {
        "input_accepted": len(routed_signals),
        "hydrated": len(hydrated),
        "planned": len(plans),
        "rejected_by_price": len(price_rejected),
        "rejected_by_gate": len(gate_rejected),
        "total_rejected": len(all_rejected),
        "exposure_A": exposure_a,
        "exposure_B": exposure_b,
        "exposure_total": exposure_a + exposure_b,
        "positions_A": sum(1 for p in plans if p.source_system == "A"),
        "positions_B": sum(1 for p in plans if p.source_system == "B"),
        "positions_total": len(plans),
    }

    summary_path = output_base.parent / "phase3_summary.json"
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    print("=== Phase 3 Risk Gate Report ===")
    print(f"Input accepted: {summary['input_accepted']}")
    print(f"Hydrated: {summary['hydrated']}")
    print(f"Planned: {summary['planned']}")
    print(f"Rejected: {summary['total_rejected']}")
    print(f"  - By price: {summary['rejected_by_price']}")
    print(f"  - By gate: {summary['rejected_by_gate']}")
    print(f"Exposure A: ${summary['exposure_A']:.2f}")
    print(f"Exposure B: ${summary['exposure_B']:.2f}")
    print(f"Exposure total: ${summary['exposure_total']:.2f}")
    print(f"Positions A: {summary['positions_A']}")
    print(f"Positions B: {summary['positions_B']}")
    print(f"Positions total: {summary['positions_total']}")
    print(f"\nOutputs:")
    print(f"  Plan JSONL: {output_base.with_suffix('.jsonl')}")
    print(f"  Plan CSV: {output_base.with_suffix('.csv')}")
    print(f"  Rejected CSV: {output_base.parent / 'risk_rejected.csv'}")
    print(f"  Summary JSON: {summary_path}")


if __name__ == "__main__":
    main()
