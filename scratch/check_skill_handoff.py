#!/usr/bin/env python3
"""check_skill_handoff.py — Certifica que el SKILL de hand-off no referencia el skill fantasma.

Lee ÚNICAMENTE .agents/skills/codely-plan-create-github/SKILL.md y falla si
contiene "codely-plan_phase-implement-github" (adaptador local reemplazado por
comandos OpenSpec /sdd-ff y /sdd-new). Retorna 0 si está limpio.
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

SKILL_FILE = (
    Path(__file__).resolve().parent.parent
    / ".agents" / "skills" / "codely-plan-create-github" / "SKILL.md"
)
FORBIDDEN_REFERENCE = "codely-plan_phase-implement-github"


def main() -> int:
    text = SKILL_FILE.read_text(encoding="utf-8")
    count = text.count(FORBIDDEN_REFERENCE)
    if count:
        print(
            f"❌ SKILL.md contiene {count} referencia(s) a {FORBIDDEN_REFERENCE!r}.",
            file=sys.stderr,
        )
        return 1
    print("✅ SKILL.md sin referencias a codely-plan_phase-implement-github.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
