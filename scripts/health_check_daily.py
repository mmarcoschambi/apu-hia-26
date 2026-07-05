#!/usr/bin/env python3
"""
health_check_daily.py

Health check unificado diario. Corre en VPS o local después del sync.
Verifica tres puntos críticos: Snapshot, Base de datos, Drift Gate.
Si algo falla, manda alerta por Telegram y sale con exit code 1.

Uso:
    python3 scripts/health_check_daily.py
    python3 scripts/health_check_daily.py --date 2026-06-30
    python3 scripts/health_check_daily.py --quiet   # solo exit code, sin print
"""

import argparse
import json
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "data" / "ticker_cache.db"
TODAY = datetime.now().strftime("%Y-%m-%d")

# Los audit files se guardan en paper_trading/universe_snapshots/<date>/
AUDIT_DIR = ROOT / "outputs" / "paper_trading" / "universe_snapshots"


def send_telegram_alert(msg: str) -> None:
    """Envía alerta por Telegram usando el cliente del sistema."""
    try:
        sys.path.insert(0, str(ROOT))
        from src.utils.telegram_client import telegram_send

        telegram_send(f"⚠️ [System Alert]\n{msg}")
        print("  Telegram alert sent.")
    except ImportError:
        print("  [Warn] src.utils.telegram_client no disponible. Alerta no enviada.")
    except Exception as e:
        print(f"  [Warn] Falló envío de Telegram: {e}")


def check_snapshot(snap_file: Path) -> list[str]:
    """Check 1: Snapshot de Finviz existe, es JSON válido y tiene tickers."""
    errors = []
    if not snap_file.exists():
        errors.append(f"Falta el snapshot de Finviz de hoy ({snap_file.name}).")
        return errors

    try:
        with open(snap_file) as f:
            data = json.load(f)
        watchlist = data.get("watchlist_detail", {})
        ticker_count = len(watchlist)
        print(f"  📸 Snapshot: {ticker_count} tickers")
        if ticker_count < 50:
            errors.append(f"Snapshot de hoy casi vacío ({ticker_count} tickers).")
    except Exception as e:
        errors.append(f"Snapshot corrupto al leer JSON: {e}")

    return errors


def check_database(db_path: Path, date_str: str) -> list[str]:
    """Check 2: Rankings en base de datos para la fecha especificada."""
    errors = []
    if not db_path.exists():
        errors.append("La base de datos ticker_cache.db no existe en local.")
        return errors

    try:
        conn = sqlite3.connect(str(db_path))
        row = conn.execute(
            "SELECT COUNT(*) FROM daily_rs_rankings WHERE date = ?",
            (date_str,),
        ).fetchone()
        conn.close()
        count = row[0] if row else 0
        print(f"  🗄️  DB rankings: {count} registros para {date_str}")
        if count == 0:
            errors.append(
                f"Faltan rankings en la base de datos para {date_str}."
            )
    except Exception as e:
        errors.append(f"Error consultando rankings en SQLite: {e}")

    return errors


def check_drift_gate(audit_file: Path) -> list[str]:
    """Check 3: Drift Gate — leyendo el último reporte de auditoría."""
    errors = []
    if not audit_file.exists():
        errors.append(
            f"No se encontró universe_audit ({audit_file.name}). "
            "Puede que el drift audit no se haya ejecutado hoy."
        )
        return errors

    try:
        with open(audit_file) as f:
            audit = json.load(f)
        gate_passed = audit.get("gate_passed", False)
        block_reason = audit.get("block_reason")
        divergence = audit.get("divergence_pct", "?")
        coverage = audit.get("live_coverage_pct", "?")

        print(f"  🚧 Drift Gate: {'PASSED' if gate_passed else 'BLOCKED'}"
              f" (div={divergence}%, coverage={coverage}%)")

        if not gate_passed:
            reason = block_reason or "unknown"
            errors.append(f"Drift Gate BLOCKED: {reason}")
    except Exception as e:
        errors.append(f"Error leyendo universe_audit.json: {e}")

    return errors


def run_health_check(date_str: str, quiet: bool = False) -> int:
    if not quiet:
        print(f"\n{'=' * 50}")
        print(f"  🩺 System Health Check  |  {date_str}")
        print(f"{'=' * 50}")

    snap_file = ROOT / "outputs" / "paper_finviz" / date_str / "snapshot.json"
    audit_file = AUDIT_DIR / date_str / f"universe_audit_{date_str}.json"

    all_errors = []
    all_errors.extend(check_snapshot(snap_file))
    all_errors.extend(check_database(DB_PATH, date_str))
    all_errors.extend(check_drift_gate(audit_file))

    if all_errors:
        error_msg = "\n  • ".join([""] + all_errors)
        full_msg = f"Fallas detectadas:\n{error_msg}"
        if not quiet:
            print(f"\n❌ HEALTH CHECK FAILED:{error_msg}")
        send_telegram_alert(full_msg)
        return 1

    if not quiet:
        print(f"\n✅ HEALTH CHECK PASSED: Todo en orden.\n")
    return 0


def main():
    parser = argparse.ArgumentParser(
        description="Health check unificado diario (Snapshot + DB + Drift Gate)."
    )
    parser.add_argument(
        "--date",
        default=TODAY,
        help=f"Fecha a verificar (default: {TODAY})",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Solo exit code, sin output a stdout",
    )
    args = parser.parse_args()

    exit_code = run_health_check(args.date, quiet=args.quiet)
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
