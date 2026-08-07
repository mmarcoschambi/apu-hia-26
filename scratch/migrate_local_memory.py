#!/usr/bin/env python3
"""migrate_local_memory.py — Migración atómica de .cache/local_memory.json a schema v1.0.

Escribe la nueva estructura ({"schema_version": "1.0", "entries": [...]}) en un
archivo .tmp y lo renombra (os.replace) sobre el original, preservando las 24
entradas históricas tal cual y agregando 3 reglas nuevas:
  - rules/promotion
  - rules/look-ahead
  - rules/live-status

Uso: python scratch/migrate_local_memory.py
"""
import json
import sys
from pathlib import Path

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except (AttributeError, IOError):
        pass

SCHEMA_VERSION = "1.0"
MEMORY_FILE = Path(__file__).resolve().parent.parent / ".cache" / "local_memory.json"
TMP_FILE = MEMORY_FILE.with_suffix(".json.tmp")

NEW_RULES = [
    {
        "timestamp": "2026-08-07T00:00:00Z",
        "title": "Regla: Promoción de shadow/experimentos a producción",
        "type": "pattern",
        "scope": "project",
        "topic_key": "rules/promotion",
        "content": (
            "Una estrategia en shadow/experimento solo se promueve a producción tras "
            "evidencia empírica suficiente (n>=30 señales reales) y sin degradar el "
            "baseline oficial (Return >= 96%, MDD <= -36%)."
        ),
    },
    {
        "timestamp": "2026-08-07T00:00:00Z",
        "title": "Regla: Prohibición de look-ahead bias en datos PIT",
        "type": "pattern",
        "scope": "project",
        "topic_key": "rules/look-ahead",
        "content": (
            "Toda señal debe computarse con datos point-in-time (PIT) disponibles al "
            "momento de la decisión; queda prohibido usar información futura en el "
            "pipeline de backtest o validación."
        ),
    },
    {
        "timestamp": "2026-08-07T00:00:00Z",
        "title": "Regla: Verdad canónica live vs simulación",
        "type": "pattern",
        "scope": "project",
        "topic_key": "rules/live-status",
        "content": (
            "La verdad canónica del sistema es el estado LIVE (producción/VPS); la "
            "simulación y el shadow son aproximaciones que deben reconciliarse contra "
            "live antes de promover cualquier cambio."
        ),
    },
]


def main() -> int:
    try:
        historical = json.loads(MEMORY_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"❌ No se pudo leer {MEMORY_FILE}: {exc}", file=sys.stderr)
        return 1

    if not isinstance(historical, list):
        print(f"❌ Formato inesperado: se esperaba una lista en {MEMORY_FILE}", file=sys.stderr)
        return 1

    migrated = {"schema_version": SCHEMA_VERSION, "entries": historical + NEW_RULES}

    # Escritura atómica: .tmp + rename sobre el original
    TMP_FILE.write_text(
        json.dumps(migrated, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    TMP_FILE.replace(MEMORY_FILE)

    print(
        f"✅ Migrado a schema v{SCHEMA_VERSION}: {len(historical)} históricas + "
        f"{len(NEW_RULES)} reglas = {len(migrated['entries'])} entradas."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
