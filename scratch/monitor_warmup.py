#!/usr/bin/env python3
"""
monitor_warmup.py — Monitorea el progreso de la descarga del histórico limpio.
Muestra cuántos tickers van procesados, el porcentaje y el estado de actividad.
"""

import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).parent.parent
PROGRESS_FILE = ROOT / "scratch" / "warmup_progress.json"
DB_PATH = ROOT / "data" / "ticker_cache.db"
OUT_DIR = ROOT / "outputs" / "paper_finviz"


def get_total_tickers() -> int:
    """Extrae el total de tickers del universo Finviz de los snapshots."""
    tickers = set()
    for path in OUT_DIR.iterdir():
        if not path.is_dir():
            continue
        snap_path = path / "snapshot.json"
        if snap_path.exists():
            try:
                with open(snap_path) as f:
                    data = json.load(f)
                    wl = data.get("watchlist_detail", {})
                    for t in wl.keys():
                        tickers.add(t.upper().replace(".", "-"))
            except Exception:
                pass
    return len(tickers) if tickers else 1022


def main():
    if not PROGRESS_FILE.exists():
        print("\n" + "=" * 60)
        print("  MONITOR DE WARMUP HISTÓRICO")
        print("=" * 60)
        print("  [Estado] ⏸️  No hay archivo de progreso en scratch/warmup_progress.json")
        print("           (El warmup no está corriendo o ya se completó al 100%).")
        print("=" * 60 + "\n")
        return

    # Cargar progreso
    try:
        with open(PROGRESS_FILE) as f:
            data = json.load(f)
            completed = data.get("completed", [])
    except Exception as e:
        print(f"  [ERROR] No se pudo leer {PROGRESS_FILE}: {e}")
        return

    total = get_total_tickers()
    completed_count = len(completed)
    pct = (completed_count / total) * 100 if total else 0

    # Medir inactividad
    mtime = PROGRESS_FILE.stat().st_mtime
    elapsed = time.time() - mtime

    print("\n" + "=" * 60)
    print("  📊 MONITOR DE WARMUP HISTÓRICO")
    print("=" * 60)
    print(f"  Progreso:          {completed_count} / {total} tickers ({pct:.2f}%)")
    
    # Renderizar barra de progreso visual
    bar_width = 30
    filled = int(bar_width * completed_count // total) if total else 0
    bar = "█" * filled + "░" * (bar_width - filled)
    print(f"  Progreso visual:   |{bar}|")
    
    # Mostrar últimos tickers procesados
    if completed:
        print(f"  Últimos guardados: {', '.join(completed[-8:])}")
        
    print("-" * 60)
    print(f"  Último cambio hace: {elapsed:.1f} segundos")
    
    # Determinar estado
    if elapsed > 45:
        print("  Estado:            ⚠️  INACTIVO o ESPERANDO RED (más de 45s sin avances)")
        print("                     Posible rate limit o descarga muy lenta.")
    else:
        print("  Estado:            ✅  PROCESANDO ACTIVAMENTE (descargas en curso)")
        
    print("=" * 60 + "\n")


if __name__ == "__main__":
    main()
