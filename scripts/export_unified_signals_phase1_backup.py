#!/usr/bin/env python3
"""Fase 1 CLI: Export unified signals from A and B sources."""

from __future__ import annotations

import argparse
import glob
import sys
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.integration.signal_adapter_a import adapt_batch_a
from src.integration.signal_adapter_b import adapt_batch_b
from src.integration.signal_exporter import export_to_csv, export_to_jsonl, sort_signals


def load_preset_summary(summary_paths: list[Path]) -> dict[str, float]:
    lookup = {}
    for path in summary_paths:
        df = pd.read_csv(path)
        for _, row in df.iterrows():
            preset_id = str(row.get("preset_id", ""))
            score = float(row.get("expectancy", 0.0))
            if preset_id and preset_id not in lookup:
                lookup[preset_id] = score
    return lookup


def load_a_signals(a_input: Path) -> list[dict]:
    if not a_input.exists():
        return []
    df = pd.read_csv(a_input)
    return df.to_dict(orient="records")


def load_b_signals(b_inputs: list[Path]) -> list[dict]:
    rows = []
    for path in b_inputs:
        if not path.exists():
            continue
        df = pd.read_csv(path)
        rows.extend(df.to_dict(orient="records"))
    return rows


def main():
    parser = argparse.ArgumentParser(description="Export unified signals Phase 1")
    parser.add_argument("--date", required=True, help="Date for output naming")
    parser.add_argument("--a-input", required=True, help="Path to A signals CSV")
    parser.add_argument(
        "--b-input", required=True, help="Glob pattern for B signals CSV"
    )
    parser.add_argument(
        "--b-summary", required=True, help="Glob pattern for B summary CSV"
    )
    parser.add_argument("--out", required=True, help="Output path for JSONL")
    args = parser.parse_args()

    a_input = Path(args.a_input)
    b_input_pattern = args.b_input
    b_summary_pattern = args.b_summary
    output_path = Path(args.out)

    b_inputs = [Path(p) for p in glob.glob(b_input_pattern)]
    b_summaries = [Path(p) for p in glob.glob(b_summary_pattern)]

    a_rows = load_a_signals(a_input)
    b_rows = load_b_signals(b_inputs)
    preset_lookup = load_preset_summary(b_summaries)

    signals_a, discarded_a = adapt_batch_a(a_rows)
    signals_b, discarded_b = adapt_batch_b(b_rows, preset_lookup)

    all_signals = signals_a + signals_b
    sorted_signals = sort_signals(all_signals)

    jsonl_path = output_path
    csv_path = output_path.with_suffix(".csv")

    export_to_jsonl(sorted_signals, jsonl_path)
    export_to_csv(sorted_signals, csv_path)

    discarded_total = len(discarded_a) + len(discarded_b)

    print("=== Phase 1 Export Report ===")
    print(f"Date: {args.date}")
    print(f"Signals A: {len(signals_a)}")
    print(f"Signals B: {len(signals_b)}")
    print(f"Discarded A: {len(discarded_a)}")
    print(f"Discarded B: {len(discarded_b)}")
    print(f"Total discarded: {discarded_total}")
    print(f"Total unified: {len(sorted_signals)}")
    print(f"Output JSONL: {jsonl_path}")
    print(f"Output CSV: {csv_path}")

    if discarded_a or discarded_b:
        print("\n=== Discarded Rows (sample) ===")
        for d in discarded_a[:3]:
            print(f"  A: {d}")
        for d in discarded_b[:3]:
            print(f"  B: {d}")


if __name__ == "__main__":
    main()
