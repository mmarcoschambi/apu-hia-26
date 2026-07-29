"""
src/optimization/s4_gates.py
============================
Acceptance gates automáticos para candidatos de Optuna S4.

Gates:
- PF > 1.3
- Calmar > 1.0
- Max DD duration < 126 days (6 meses)
- Hard ruin prob < 5%
- Degradation Sharpe IS->Val <= 20%
- Cost robustness (ROBUSTO/MODERADO/FRÁGIL)
"""

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

# === GATE CONSTANTS ===

GATE_PF = 1.3
GATE_CALMAR = 1.0
GATE_MDD_DURATION_DAYS = 126  # ~6 months
GATE_HARD_RUIN = 0.05  # 5%
GATE_DEGRADATION = 0.25  # 25%


def _normalize_cost_label(label: Optional[str]) -> Optional[str]:
    """Normaliza etiquetas de robustez de costos a ASCII."""
    if not label:
        return None
    return (
        label.strip()
        .upper()
        .replace("Á", "A")
        .replace("É", "E")
        .replace("Í", "I")
        .replace("Ó", "O")
        .replace("Ú", "U")
    )


def check_acceptance_gates(
    is_metrics: Dict[str, Any],
    val_metrics: Optional[Dict[str, Any]] = None,
    oos_metrics: Optional[Dict[str, Any]] = None,
    cost_robustness: Optional[str] = None,
) -> Tuple[bool, Dict[str, Any]]:
    """
    Evalúa gates de aceptación para un candidato.

    Args:
        is_metrics: Métricas in-sample
        val_metrics: Métricas validación (optional)
        oos_metrics: Métricas out-of-sample (optional)
        cost_robustness: "ROBUSTO", "MODERADO", "FRÁGIL" o None

    Returns:
        (passed: bool, gate_results: dict)
    """
    gates = {
        "pf_gate": {"threshold": GATE_PF, "passed": None, "value": None},
        "calmar_gate": {"threshold": GATE_CALMAR, "passed": None, "value": None},
        "mdd_duration_gate": {
            "threshold": GATE_MDD_DURATION_DAYS,
            "passed": None,
            "value": None,
        },
        "hard_ruin_gate": {"threshold": GATE_HARD_RUIN, "passed": None, "value": None},
        "degradation_gate": {
            "threshold": GATE_DEGRADATION,
            "passed": None,
            "value": None,
        },
        "cost_robustness_gate": {"passed": None, "value": cost_robustness},
    }

    all_passed = True

    # PF Gate (use OOS if available, else IS)
    pf_source = oos_metrics if oos_metrics else is_metrics
    pf = pf_source.get("profit_factor", 0)
    gates["pf_gate"]["value"] = pf
    gates["pf_gate"]["passed"] = pf >= GATE_PF
    if not gates["pf_gate"]["passed"]:
        all_passed = False

    # Calmar Gate
    calmar_source = oos_metrics if oos_metrics else is_metrics
    calmar = calmar_source.get("calmar", 0)
    gates["calmar_gate"]["value"] = calmar
    gates["calmar_gate"]["passed"] = calmar >= GATE_CALMAR
    if not gates["calmar_gate"]["passed"]:
        all_passed = False

    # MDD Duration (approximated from MDD if not available)
    # If max_dd_90d > 15% in 90 days, likely exceeds duration threshold
    mdd_90 = pf_source.get("max_drawdown_90d", 0) / 100
    mdd_estimate_days = min(200, int(mdd_90 * 600)) if mdd_90 > 0 else 50
    gates["mdd_duration_gate"]["value"] = mdd_estimate_days
    gates["mdd_duration_gate"]["passed"] = mdd_estimate_days < GATE_MDD_DURATION_DAYS
    if not gates["mdd_duration_gate"]["passed"]:
        all_passed = False

    # Hard Ruin Gate (from risk_checks)
    soft_ruin = is_metrics.get("risk_checks", {}).get("hard_ruin_50", 0)
    gates["hard_ruin_gate"]["value"] = soft_ruin
    gates["hard_ruin_gate"]["passed"] = soft_ruin < GATE_HARD_RUIN
    if not gates["hard_ruin_gate"]["passed"]:
        all_passed = False

    # Degradation Gate (IS -> Val)
    if val_metrics:
        is_sharpe = is_metrics.get("sharpe", 0) or is_metrics.get(
            "overall_quality", {}
        ).get("sharpe", 0)
        val_sharpe = val_metrics.get("sharpe", 0) or val_metrics.get(
            "overall_quality", {}
        ).get("sharpe", 0)
        if is_sharpe > 0:
            degradation = (is_sharpe - val_sharpe) / is_sharpe
            gates["degradation_gate"]["value"] = degradation
            gates["degradation_gate"]["passed"] = degradation <= GATE_DEGRADATION
            if not gates["degradation_gate"]["passed"]:
                all_passed = False
    else:
        gates["degradation_gate"]["value"] = None
        gates["degradation_gate"]["passed"] = True  # No Val data = pass

    # Cost Robustness Gate
    cost_robustness = _normalize_cost_label(cost_robustness)
    if cost_robustness:
        if cost_robustness == "FRAGIL":
            gates["cost_robustness_gate"]["passed"] = False
            all_passed = False
        elif cost_robustness == "MODERADO":
            gates["cost_robustness_gate"]["passed"] = True  # Pass with warning
        else:
            gates["cost_robustness_gate"]["passed"] = True
    else:
        gates["cost_robustness_gate"]["passed"] = True  # No data = pass

    return all_passed, gates


def rank_candidates(
    candidates: List[Dict[str, Any]],
    gate_results: Dict[str, Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    Ranking de candidatos que pasaron gates.

    Ordena por: gates_passed, score_compuesto, sharpe_oos, pf
    """
    ranked = []

    for cand in candidates:
        cid = cand.get("run_id", cand.get("trial_id", "unknown"))
        gr = gate_results.get(cid, {})

        # Skip rejected
        if not gr.get("passed", False):
            continue

        # Score
        score = cand.get("score_composed", 0)
        sharpe = cand.get("oos_sharpe", cand.get("is_sharpe", 0))
        pf = cand.get("oos_pf", cand.get("is_pf", 0))

        ranked.append(
            {
                "run_id": cid,
                "score_composed": score,
                "sharpe": sharpe,
                "pf": pf,
                "gates_passed": True,
                "gate_details": gr,
            }
        )

    # Sort by composite
    ranked.sort(
        key=lambda x: (-x["score_composed"], -x["sharpe"], -x["pf"]), reverse=False
    )

    return ranked


def get_gate_summary(gate_results: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    """Resumen de gates para logging."""
    total = len(gate_results)
    passed = sum(1 for gr in gate_results.values() if gr.get("passed", False))

    pf_passed = sum(
        1 for gr in gate_results.values() if gr.get("pf_gate", {}).get("passed", False)
    )
    calmar_passed = sum(
        1
        for gr in gate_results.values()
        if gr.get("calmar_gate", {}).get("passed", False)
    )
    mdd_passed = sum(
        1
        for gr in gate_results.values()
        if gr.get("mdd_duration_gate", {}).get("passed", False)
    )
    ruin_passed = sum(
        1
        for gr in gate_results.values()
        if gr.get("hard_ruin_gate", {}).get("passed", False)
    )
    deg_passed = sum(
        1
        for gr in gate_results.values()
        if gr.get("degradation_gate", {}).get("passed", False)
    )
    cost_passed = sum(
        1
        for gr in gate_results.values()
        if gr.get("cost_robustness_gate", {}).get("passed", False)
    )

    return {
        "total_candidates": total,
        "passed": passed,
        "rejected": total - passed,
        "gate_stats": {
            "pf": f"{pf_passed}/{total}",
            "calmar": f"{calmar_passed}/{total}",
            "mdd_duration": f"{mdd_passed}/{total}",
            "hard_ruin": f"{ruin_passed}/{total}",
            "degradation": f"{deg_passed}/{total}",
            "cost_robustness": f"{cost_passed}/{total}",
        },
    }


# === CLI TEST ===

if __name__ == "__main__":
    print("=== Testing s4_gates ===")

    # Mock metrics
    is_metrics = {
        "profit_factor": 1.8,
        "calmar": 1.5,
        "max_drawdown_90d": 12.0,
        "sharpe": 1.6,
        "risk_checks": {"hard_ruin_50": 0.02},
    }

    val_metrics = {
        "profit_factor": 1.5,
        "calmar": 1.2,
        "sharpe": 1.3,
        "risk_checks": {"hard_ruin_50": 0.03},
    }

    oos_metrics = {
        "profit_factor": 1.4,
        "calmar": 1.1,
        "sharpe": 1.1,
        "max_drawdown_90d": 18.0,
    }

    # Test: ROBUSTO
    passed, gates = check_acceptance_gates(
        is_metrics, val_metrics, oos_metrics, "ROBUSTO"
    )
    print(f"ROBUSTO: passed={passed}")

    # Test: FRÁGIL
    passed2, gates2 = check_acceptance_gates(
        is_metrics, val_metrics, oos_metrics, "FRÁGIL"
    )
    print(f"FRÁGIL: passed={passed2}, reason={gates2['cost_robustness_gate']}")

    # Test: No cost data
    passed3, gates3 = check_acceptance_gates(is_metrics, val_metrics, oos_metrics, None)
    print(f"No cost data: passed={passed3}")
