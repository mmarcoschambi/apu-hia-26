#!/usr/bin/env python3
"""verify_memory_rules.py — Verifica la estructura v1.0 de .cache/local_memory.json.

Comprueba:
  1. schema_version == "1.0"
  2. len(entries) == 27 (24 históricas conservadas + 3 reglas nuevas)
  3. Existencia de las 3 reglas: Promotion, Look-Ahead, Live Status

Retorna exit code 0 si todo es válido y 1 en caso contrario.
"""
import json
import sys
from pathlib import Path

# Salvaguarda para prevenir UnicodeEncodeError en terminales de Windows
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except (AttributeError, IOError):
        pass

EXPECTED_SCHEMA_VERSION = "1.0"
EXPECTED_ENTRY_COUNT = 27
REQUIRED_RULE_TOPICS = ("rules/promotion", "rules/look-ahead", "rules/live-status")
MEMORY_FILE = Path(__file__).resolve().parent.parent / ".cache" / "local_memory.json"


def main() -> int:
    try:
        data = json.loads(MEMORY_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"❌ No se pudo leer {MEMORY_FILE}: {exc}", file=sys.stderr)
        return 1

    failures: list[str] = []

    if not isinstance(data, dict):
        failures.append(
            f"raíz no es un objeto JSON (se esperaba {{'schema_version', 'entries'}}): {type(data).__name__}"
        )
    elif data.get("schema_version") != EXPECTED_SCHEMA_VERSION:
        failures.append(
            f"schema_version != {EXPECTED_SCHEMA_VERSION!r}: {data.get('schema_version')!r}"
        )

    entries = data.get("entries") if isinstance(data, dict) else None
    if not isinstance(entries, list):
        failures.append("entries no es una lista")
    else:
        if len(entries) != EXPECTED_ENTRY_COUNT:
            failures.append(
                f"len(entries) = {len(entries)}, se esperaba {EXPECTED_ENTRY_COUNT}"
            )
        topics = {entry.get("topic_key") for entry in entries}
        for topic in REQUIRED_RULE_TOPICS:
            if topic not in topics:
                failures.append(f"Regla faltante: topic_key {topic!r}")

    if failures:
        for msg in failures:
            print(f"❌ {msg}", file=sys.stderr)
        return 1

    print("✅ local_memory.json válido: schema_version=1.0, 27 entradas, 3 reglas presentes.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
