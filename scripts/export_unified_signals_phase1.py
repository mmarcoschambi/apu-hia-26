#!/usr/bin/env python3
"""Fase 1 CLI: Export unified signals from A and B sources."""

from __future__ import annotations

import argparse
import glob
import sys
from datetime import date
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


def _build_price_lookup(trades_paths: list[Path]) -> dict[tuple, float]:
    """Construye un dict (preset_id, ticker, signal_date) -> entry_price.

    Los trades CSV de B tienen entry_date (= signal_date + 1 sesion) y
    entry_price. Usamos entry_price como proxy para entry_price_ref en el
    signal, ya que el signal CSV no lo incluye.
    """
    lookup: dict[tuple, float] = {}
    for path in trades_paths:
        if not path.exists():
            continue
        try:
            df = pd.read_csv(path)
            if df.empty:
                continue
            for _, row in df.iterrows():
                preset_id = str(row.get("preset_id", "")).strip()
                ticker = str(row.get("ticker", "")).strip().upper()
                # entry_date en trades = signal_date + 1; pero como no tenemos
                # signal_date directamente en trades, usamos entry_date - 1 seria
                # complicado. En cambio, buscamos por (preset_id, ticker) y tomamos
                # el primer precio disponible para ese par en el backtest.
                # Para el modo live/paper lo que importa es que haya un precio
                # de referencia no nulo; la hidratacion real la hace price_hydrator.
                entry_price = float(row.get("entry_price", 0.0))
                if entry_price > 0:
                    key = (preset_id, ticker)
                    if key not in lookup:
                        lookup[key] = entry_price
        except Exception:
            pass
    return lookup


def load_b_signals(b_inputs: list[Path], trades_paths: list[Path]) -> list[dict]:
    """Carga senales de B e inyecta entry_price_ref desde los trades CSV."""
    price_lookup = _build_price_lookup(trades_paths)

    rows = []
    for path in b_inputs:
        if not path.exists():
            continue
        df = pd.read_csv(path)
        for _, row in df.iterrows():
            d = row.to_dict()
            preset_id = str(d.get("preset_id", "")).strip()
            ticker = str(d.get("ticker", "")).strip().upper()
            # Si el signal CSV no trae entry_price_ref, lo buscamos en trades
            if not d.get("entry_price_ref") or float(d.get("entry_price_ref", 0)) <= 0:
                key = (preset_id, ticker)
                if key in price_lookup:
                    d["entry_price_ref"] = price_lookup[key]
            rows.append(d)
    return rows


def main():
    parser = argparse.ArgumentParser(description="Export unified signals Phase 1")
    parser.add_argument("--date", required=True, help="Date for output naming (YYYY-MM-DD)")
    parser.add_argument("--a-input", required=True, help="Path to A signals CSV")
    parser.add_argument(
        "--b-input", required=True, help="Glob pattern for B signals CSV"
    )
    parser.add_argument(
        "--b-trades",
        default=None,
        help=(
            "Glob pattern for B trades CSV (para hidratar entry_price_ref). "
            "Si se omite, se infiere del mismo directorio que --b-input."
        ),
    )
    parser.add_argument(
        "--b-summary", required=True, help="Glob pattern for B summary CSV"
    )
    parser.add_argument("--out", required=True, help="Output path for JSONL")
    # FIX 1: fecha operativa para alinear B con A
    parser.add_argument(
        "--execution-date",
        default=None,
        help=(
            "Fecha operativa para las senales de B (YYYY-MM-DD). "
            "Si se omite, usa --date o today() como fallback."
        ),
    )
    parser.add_argument(
        "--historical-mode",
        action="store_true",
        help="Si se activa, no alinea fechas de B y marca como historical_plan."
    )
    args = parser.parse_args()

    # Resolver execution_date
    execution_date: str = (
        args.execution_date
        if args.execution_date
        else (args.date if args.date else date.today().isoformat())
    )

    a_input = Path(args.a_input)
    b_input_pattern = args.b_input
    b_summary_pattern = args.b_summary
    output_path = Path(args.out)

    b_inputs = [Path(p) for p in glob.glob(b_input_pattern)]
    b_summaries = [Path(p) for p in glob.glob(b_summary_pattern)]

    # Inferir patron de trades si no se pasa explicitamente
    if args.b_trades:
        b_trades_pattern = args.b_trades
    else:
        # Mismo directorio que las senales, pero con *_trades.csv
        b_dir = str(Path(b_input_pattern).parent)
        b_trades_pattern = b_dir + "/*_trades.csv"

    b_trades_paths = [Path(p) for p in glob.glob(b_trades_pattern)]

    a_rows = load_a_signals(a_input)
    # FIX precio: enriquece con entry_price_ref desde trades
    b_rows = load_b_signals(b_inputs, b_trades_paths)
    preset_lookup = load_preset_summary(b_summaries)

    signals_a, discarded_a = adapt_batch_a(a_rows)

    # FIX 1 (fecha) + FIX 2 (stop/target)
    signals_b, discarded_b = adapt_batch_b(
        b_rows,
        preset_lookup,
        execution_date=execution_date,
        historical_mode=args.historical_mode,
    )

    all_signals = signals_a + signals_b
    sorted_signals = sort_signals(all_signals)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    jsonl_path = output_path
    csv_path = output_path.with_suffix(".csv")

    export_to_jsonl(sorted_signals, jsonl_path)
    export_to_csv(sorted_signals, csv_path)

    discarded_total = len(discarded_a) + len(discarded_b)

    # Contar cuantas senales B tuvieron precio inyectado
    b_with_price = sum(
        1 for r in b_rows
        if float(r.get("entry_price_ref", 0) or 0) > 0
    )

    print("=== Phase 1 Export Report ===")
    print(f"Date:              {args.date}")
    print(f"Execution date:    {execution_date}  (fecha operativa de B)")
    print(f"Signals A:         {len(signals_a)}")
    print(f"Signals B:         {len(signals_b)}  (con precio: {b_with_price}/{len(b_rows)})")
    print(f"Discarded A:       {len(discarded_a)}")
    print(f"Discarded B:       {len(discarded_b)}")
    print(f"Total discarded:   {discarded_total}")
    print(f"Total unified:     {len(sorted_signals)}")
    print(f"Output JSONL:      {jsonl_path}")
    print(f"Output CSV:        {csv_path}")

    if discarded_a or discarded_b:
        print("\n=== Discarded Rows (sample) ===")
        for d in discarded_a[:3]:
            print(f"  A: {d}")
        for d in discarded_b[:3]:
            print(f"  B: {d}")


if __name__ == "__main__":
    main()
