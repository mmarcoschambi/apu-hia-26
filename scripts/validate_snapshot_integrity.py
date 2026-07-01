#!/usr/bin/env python3
"""
validate_snapshot_integrity.py

Validador de integridad del snapshot del día.
Corre post-sync para asegurar que los datos descargados del VPS son válidos.

Uso:
    python3 scripts/validate_snapshot_integrity.py
    python3 scripts/validate_snapshot_integrity.py --date 2026-06-30
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TODAY = datetime.now().strftime("%Y-%m-%d")


def validate(snapshot_path: Path) -> int:
    print(f"[Integrity Check] Validando snapshot en: {snapshot_path}")

    if not snapshot_path.exists():
        print(f"  ❌ CRITICAL ERROR: El snapshot de hoy no existe en disco.")
        print(f"     Esperado: {snapshot_path}")
        return 1

    try:
        with open(snapshot_path) as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        print(f"  ❌ CRITICAL ERROR: El snapshot no es un JSON válido: {e}")
        return 1

    watchlist = data.get("watchlist_detail", {})
    ticker_count = len(watchlist)
    print(f"[Integrity Check] Tickers encontrados en el snapshot: {ticker_count}")

    MIN_EXPECTED_TICKERS = 50
    if ticker_count < MIN_EXPECTED_TICKERS:
        print(
            f"  ❌ CRITICAL ERROR: Watchlist sospechosamente vacía. "
            f"Tickers: {ticker_count} (Mínimo esperado: {MIN_EXPECTED_TICKERS})"
        )
        return 1

    print("  ✅ INTEGRITY CHECK PASSED: Snapshot saludable.")
    return 0


def main():
    parser = argparse.ArgumentParser(
        description="Valida la integridad del snapshot del día."
    )
    parser.add_argument(
        "--date",
        default=TODAY,
        help=f"Fecha del snapshot a validar (default: {TODAY})",
    )
    args = parser.parse_args()

    snap_path = ROOT / "outputs" / "paper_finviz" / args.date / "snapshot.json"
    exit_code = validate(snap_path)
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
