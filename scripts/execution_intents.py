#!/usr/bin/env python3
"""
execution_intents.py - Genera intents canónicos desde señales.

Hoy sirve como capa intermedia persistible entre señales y ejecución.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

logger = logging.getLogger(__name__)

from src.integration.execution_ledger import (
    ExecutionIntent,
    intent_from_signal,
    write_csv,
    write_jsonl,
)

LIVE_DIR = PROJECT_ROOT / "outputs" / "live_signals"
OUT_DIR = PROJECT_ROOT / "outputs" / "execution_intents"


def load_signals(date: str) -> pd.DataFrame:
    path = LIVE_DIR / date / "combined.csv"
    if not path.exists():
        logger.info(f"No signals file for {date}: {path}")
        return pd.DataFrame()
    return pd.read_csv(path)


def build_intents(
    date: str, source_universe: str = "local_db"
) -> list[ExecutionIntent]:
    df = load_signals(date)
    if df.empty:
        return []
    intents: list[ExecutionIntent] = []
    for _, row in df.iterrows():
        signal = row.to_dict()
        signal["signal_date"] = date
        signal.setdefault(
            "combo_name",
            signal.get("combo_name") or signal.get("agent_name") or "unknown",
        )
        intent = intent_from_signal(
            signal,
            source_universe=source_universe,
            decision_source="system",
            risk_budget_usd=float(signal.get("risk_budget_usd", 1000.0) or 1000.0),
            risk_per_trade_usd=float(
                signal.get("risk_per_trade_usd", 1000.0) or 1000.0
            ),
            signal_date=date,
        )
        intents.append(intent)
    return intents


def main() -> None:
    parser = argparse.ArgumentParser(description="Build execution intents")
    parser.add_argument("--date", required=True)
    parser.add_argument("--source-universe", default="local_db")
    parser.add_argument("--json-only", action="store_true")
    args = parser.parse_args()

    intents = build_intents(args.date, source_universe=args.source_universe)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    day_dir = OUT_DIR / args.date
    day_dir.mkdir(parents=True, exist_ok=True)
    jsonl_path = day_dir / "execution_intents.jsonl"
    csv_path = day_dir / "execution_intents.csv"
    write_jsonl(jsonl_path, intents)
    write_csv(csv_path, intents)

    payload = {
        "date": args.date,
        "generated_at": datetime.now().isoformat(),
        "count": len(intents),
        "source_universe": args.source_universe,
        "jsonl": str(jsonl_path),
        "csv": str(csv_path),
    }
    (day_dir / "execution_intents_meta.json").write_text(json.dumps(payload, indent=2))
    if not args.json_only:
        print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
