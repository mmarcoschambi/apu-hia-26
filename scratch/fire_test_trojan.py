"""
scratch/fire_test_trojan.py — Prueba de fuego del ParamGate endurecido (Bloque D).

Verifica que el contrato dual (métricas OOS + recibo físico de Purged CV) bloquea
candidatos "troyanos" con oos_metrics falsificadas pero SIN recibo físico en disco.

Escenarios:
  1. trojan_sin_recibo:       métricas falsificadas + params_json_source novel (nunca
                              evaluado por Purged CV) -> debe bloquear "sin recibo".
  2. trojan_recibo_rechazado: métricas falsificadas + params_json_source con reporte
                              gate_passed=False (config/validated_production_params.json,
                              incidente 2026-07-30) -> debe bloquear "recibo rechazado".

Las métricas falsificadas (trades=250, dsr=0.85, mdd_pct=-18.0) superan los umbrales
de producción (MIN_TRADES=150, MIN_DSR=0.35, MAX_MDD=-30.0) a propósito: si el gate
de recibo no existiera, este candidato pasaría la validación numérica.

Exit code: 0 si el gate bloqueó a los troyanos (esperado); 1 si algún troyano pasó.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.validation.param_gate import ParamGate, RejectedConfigError

# oos_metrics falsificadas: superan todos los umbrales numéricos de producción.
TROJAN_METRICS = {"trades": 250, "dsr": 0.85, "mdd_pct": -18.0}


def make_trojan(source: str) -> dict:
    return {
        "validation_passed": True,
        "params_json_source": source,
        "oos_metrics": dict(TROJAN_METRICS),
    }


def expect_blocked(name: str, config: dict) -> bool:
    try:
        ParamGate.assert_promotable(config)
        print(f"[FAIL] {name}: el troyano fue AUTORIZADO -- el gate fallo.")
        return False
    except RejectedConfigError as exc:
        print(f"[PASS] {name}: bloqueado -> {exc}")
        return True


def main() -> int:
    scenarios = [
        ("trojan_sin_recibo", make_trojan("config/params/trojan_fake_params.json")),
        ("trojan_recibo_rechazado", make_trojan("config/validated_production_params.json")),
    ]
    ok = all(expect_blocked(name, cfg) for name, cfg in scenarios)
    print()
    print(
        "FIRE TEST: PASSED - el ParamGate bloquea a los troyanos"
        if ok
        else "FIRE TEST: FAILED - hay una fuga en el gate"
    )
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
