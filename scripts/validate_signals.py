#!/usr/bin/env python3
"""
validate_signals.py - Valida que un archivo de señales tenga el schema mínimo.

Uso:
    python3 scripts/validate_signals.py outputs/live_signals/2026-04-24/combined.csv
    python3 scripts/validate_signals.py outputs/live_signals/2026-04-24/ --date 2026-04-24

Exit codes:
    0 = válido
    1 = error de schema
    2 = archivo no encontrado
"""

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


REQUIRED_COLS = {
    "agent_name",
    "ticker",
    "signal_date",
    "entry_score",
    "entry_price",
}

OPTIONAL_COLS = {
    "combo_name",
    "screener_score",
    "screener_reason",
    "pattern_signal",
    "tier2_filter",
    "rvol",
    "adr_pct",
    "dist_sma20",
    "consol_days",
    "volume",
    "dollar_vol_M",
}


def validate_file(path: Path, verbose: bool = False) -> dict:
    import pandas as pd

    errors = []
    warnings = []

    if not path.exists():
        return {"ok": False, "error": f"File not found: {path}", "code": 2}

    try:
        df = pd.read_csv(path)
    except Exception as e:
        return {"ok": False, "error": f"Cannot read CSV: {e}", "code": 1}

    if df.empty:
        warnings.append("DataFrame is empty")

    missing_req = REQUIRED_COLS - set(df.columns)
    if missing_req:
        errors.append(f"Missing required columns: {sorted(missing_req)}")

    extra_cols = set(df.columns) - REQUIRED_COLS - OPTIONAL_COLS
    if extra_cols and verbose:
        warnings.append(f"Extra columns (ignored): {sorted(extra_cols)}")

    null_counts = df[list(REQUIRED_COLS & set(df.columns))].isnull().sum()
    null_cols = null_counts[null_counts > 0]
    if not null_cols.empty:
        errors.append(f"Required columns with nulls: {null_cols.to_dict()}")

    duplicates = df["ticker"].duplicated().sum()
    if duplicates:
        warnings.append(f"Duplicate tickers: {duplicates}")

    has_score = "entry_score" in df.columns and not df.empty
    if has_score:
        low_score = (df["entry_score"] < 0).sum()
        if low_score:
            warnings.append(f"Tickers with entry_score < 0: {low_score}")

    result = {
        "ok": len(errors) == 0,
        "file": str(path),
        "rows": len(df),
        "tickers": int(df["ticker"].nunique()) if "ticker" in df.columns else 0,
        "agents": sorted(df["agent_name"].unique().tolist())
        if "agent_name" in df.columns
        else [],
        "errors": errors,
        "warnings": warnings,
        "code": 1 if errors else 0,
    }

    if verbose or not result["ok"]:
        _print_report(result)

    return result


def _print_report(r: dict) -> None:
    sep = "=" * 60
    print(f"\n{sep}")
    print(f"  VALIDATE SIGNALS  |  {r['file']}")
    print(f"{sep}")
    print(f"  Rows:       {r['rows']}")
    print(f"  Tickers:    {r['tickers']}")
    print(f"  Agents:     {len(r.get('agents', []))}")
    if r.get("agents"):
        for a in r["agents"]:
            print(f"    - {a}")
    if r["errors"]:
        print(f"\n  ERRORS ({len(r['errors'])}):")
        for e in r["errors"]:
            print(f"    ✗ {e}")
    if r["warnings"]:
        print(f"\n  WARNINGS ({len(r['warnings'])}):")
        for w in r["warnings"]:
            print(f"    ⚠ {w}")
    if r["ok"]:
        print("\n  ✅ VALID")
    print(f"{sep}\n")


def main():
    parser = argparse.ArgumentParser(description="Validate signals CSV")
    parser.add_argument("path", type=str, help="Path to signals CSV or date directory")
    parser.add_argument(
        "--date", type=str, help="Date for auto-resolution (YYYY-MM-DD)"
    )
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    path = Path(args.path)

    if path.is_dir():
        date = args.date or path.name
        candidates = [
            path / "combined.csv",
            path / f"signals_{date}.csv",
        ]
        chosen = next((p for p in candidates if p.exists()), None)
        if not chosen:
            print(f"No signals CSV found in {path}")
            sys.exit(2)
        path = chosen

    result = validate_file(path, verbose=args.verbose)

    if result["code"] == 2:
        print(f"❌ File not found: {path}")
    elif not result["ok"]:
        print(f"❌ VALIDATION FAILED ({len(result['errors'])} errors)")

    sys.exit(result["code"])


if __name__ == "__main__":
    main()
