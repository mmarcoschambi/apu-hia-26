#!/usr/bin/env python3
"""check_playbook_smells.py — Valida que el playbook no contenga olores de bypass de gates.

Lee ÚNICAMENTE docs/playbook_sdd_scrumban.md y dispara error si encuentra
"--no-verify" o "cuotas de API" (excusas operativas de bypass de calidad).
Retorna exit code 0 si está limpio, 1 en caso contrario.
"""
import sys
from pathlib import Path

# Salvaguarda para prevenir UnicodeEncodeError en terminales de Windows
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except (AttributeError, IOError):
        pass

PLAYBOOK = Path(__file__).resolve().parent.parent / "docs" / "playbook_sdd_scrumban.md"
FORBIDDEN_TOKENS = ("--no-verify", "cuotas de API")


def main() -> int:
    text = PLAYBOOK.read_text(encoding="utf-8")
    hits = [token for token in FORBIDDEN_TOKENS if token in text]
    if hits:
        for token in hits:
            print(f"❌ Playbook contiene el token prohibido: {token!r}", file=sys.stderr)
        return 1
    print("✅ Playbook limpio: sin --no-verify ni excusas de cuotas de API.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
