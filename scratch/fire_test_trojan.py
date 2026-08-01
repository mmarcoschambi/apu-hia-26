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

Cada escenario verifica ADEMÁS el MOTIVO del rechazo (mensaje de
RejectedConfigError) para pinchar la rama exacta ejercitada: "sin recibo" vs
"recibo RECHAZADO". Así no se puede reportar un PASS si el gate bloqueó por una
rama distinta a la que el escenario dice cubrir (p.ej. cuando faltan los
recibos y ambas caen en "Sin recibo: no existe").

Exit code: 0 si el gate bloqueó a cada troyano por la rama esperada; 1 si
algún troyano pasó o fue bloqueado por una rama no esperada.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.validation.param_gate import ParamGate, RejectedConfigError

# oos_metrics falsificadas: superan todos los umbrales numéricos de producción.
TROJAN_METRICS = {"trades": 250, "dsr": 0.85, "mdd_pct": -18.0}

# Substrings que distinguen las ramas de rechazo en el mensaje de
# RejectedConfigError (ver assert_params_cleared en src/validation/param_gate.py).
# La comparación es case-insensitive: el mensaje real usa "Sin recibo:" (S
# mayúscula) y "Recibo RECHAZADO", mientras los pins van en minúscula.
# - REASON_SIN_RECIBO: no existe recibo de Purged CV para el params_json_source.
# - REASON_RECIBO_RECHAZADO: existe recibo pero fue rechazado explícitamente.
REASON_SIN_RECIBO = "sin recibo"
REASON_RECIBO_RECHAZADO = "rechazado"


def make_trojan(source: str) -> dict:
    return {
        "validation_passed": True,
        "params_json_source": source,
        "oos_metrics": dict(TROJAN_METRICS),
    }


def expect_blocked(name: str, config: dict, expected_reason: str) -> bool:
    """
    Verifica que el gate rechace al troyano y que el motivo sea el esperado.

    Args:
        name: identificador del escenario.
        config: candidato troyano a evaluar.
        expected_reason: substring (en minúscula) que debe aparecer en el
            mensaje de RejectedConfigError (comparado case-insensitive) para
            confirmar la rama de rechazo ejercitada (sin recibo vs recibo
            rechazado).

    Returns:
        True si el gate bloqueó al troyano con el motivo esperado.
    """
    try:
        ParamGate.assert_promotable(config)
        print(f"[FAIL] {name}: el troyano fue AUTORIZADO -- el gate fallo.")
        return False
    except RejectedConfigError as exc:
        reason_ok = expected_reason in str(exc).lower()
        print(f"[{'PASS' if reason_ok else 'FAIL'}] {name}: bloqueado -> {exc}")
        if not reason_ok:
            print(
                f"       Se esperaba '{expected_reason}' en el mensaje; "
                f"el gate bloqueó por OTRA rama y la cobertura quedó sin ejercitar."
            )
        return reason_ok


def main() -> int:
    scenarios = [
        (
            "trojan_sin_recibo",
            make_trojan("config/params/trojan_fake_params.json"),
            REASON_SIN_RECIBO,
        ),
        (
            "trojan_recibo_rechazado",
            make_trojan("config/validated_production_params.json"),
            REASON_RECIBO_RECHAZADO,
        ),
    ]
    results = [expect_blocked(name, cfg, reason) for name, cfg, reason in scenarios]
    ok = all(results)
    print()
    print(
        "FIRE TEST: PASSED - el ParamGate bloquea a los troyanos por la rama esperada"
        if ok
        else "FIRE TEST: FAILED - hay una fuga en el gate o una rama no ejercitada"
    )
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
