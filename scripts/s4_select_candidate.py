#!/usr/bin/env python3
"""
scripts/s4_select_candidate.py
=============================
Selecciona el candidato final de S4 y genera reporte de trazabilidad.

Usage:
    python3 scripts/s4_select_candidate.py --study-name s4_main
    python3 scripts/s4_select_candidate.py --study-name s4_main --top 5
"""

import argparse
import json
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

import optuna

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)

OUTPUTS_DIR = PROJECT_ROOT / "outputs" / "optuna_s4"

from src.optimization.s4_gates import (
    check_acceptance_gates,
    rank_candidates,
    _normalize_cost_label,
)


def load_study_results(study_name: str) -> List[Dict]:
    """Carga resultados del estudio Optuna."""
    db_path = f"sqlite:///{OUTPUTS_DIR}/{study_name}.db"

    try:
        study = optuna.load_study(study_name=study_name, storage=db_path)
        trials = study.trials

        results = []
        for trial in trials:
            if trial.value and trial.value > -999:
                results.append(
                    {
                        "trial_id": trial.number,
                        "score": trial.value,
                        "params": trial.params,
                        "user_attrs": trial.user_attrs,
                        "state": trial.state.name,
                    }
                )

        return sorted(results, key=lambda x: x["score"], reverse=True)
    except Exception as e:
        logger.error(f"Could not load study: {e}")
        return []


def select_final_candidate(
    candidates: List[Dict],
    gate_results: Dict[str, Dict],
) -> Dict[str, Any]:
    """Selecciona el candidato final (top ranked que pasó gates)."""
    for cand in candidates:
        tid = str(cand.get("trial_id", 0))
        gr = gate_results.get(tid, {})

        if gr.get("passed", False):
            score = cand.get("score_composed", cand.get("score", 0))
            logger.info(f"SELECTED: Trial {tid} - Score {score}")
            return {
                "selected_trial_id": tid,
                "score_composed": score,
                "params": cand.get("params", {}),
                "metrics": cand.get("user_attrs", {}),
                "gate_results": gr,
            }

    logger.warning("No candidate passed all gates!")
    return {"error": "NO_CANDIDATE_PASSED"}


def generate_promotion_report(
    candidate: Dict[str, Any],
    study_name: str,
    output_dir: Path,
) -> Path:
    """Genera reporte de promoción."""
    report = {
        "generated_at": datetime.now().isoformat(),
        "study_name": study_name,
        "promoted_candidate": candidate,
        "trazability": {
            "optuna_db": str(output_dir / f"{study_name}.db"),
            "gate_results": candidate.get("gate_results", {}),
            "params_used": candidate.get("params", {}),
        },
        "next_steps": [
            "1. Generate canonical analytics with backtest_analytics_bridge",
            "2. Update production_config.json with promoted params",
            "3. Enable paper trading with new config",
            "4. Monitor paper performance for 30 days",
        ],
    }

    report_path = (
        output_dir
        / f"promotion_report_{study_name}_{datetime.now().strftime('%Y%m%d')}.json"
    )
    with open(report_path, "w") as f:
        json.dump(report, f, indent=2)

    return report_path


def load_results_json(study_name: str) -> Dict[str, Any]:
    """Carga resultados guardados en JSON (prioridad) o intenta desde Optuna DB."""
    # Buscar el JSON más reciente para este estudio
    import glob

    json_pattern = str(OUTPUTS_DIR / f"results_{study_name}_*.json")
    matches = sorted(glob.glob(json_pattern), reverse=True)

    if matches:
        try:
            with open(matches[0], "r") as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"Could not load JSON {matches[0]}: {e}")

    return {}


def main():
    parser = argparse.ArgumentParser(description="S4 Candidate Selection")
    parser.add_argument("--study-name", type=str, default="s4_main", help="Study name")
    parser.add_argument("--top", type=int, default=10, help="Top N to consider")
    parser.add_argument("--output-dir", type=str, default=None, help="Output directory")
    parser.add_argument(
        "--from-json", action="store_true", help="Force load from JSON results file"
    )

    args = parser.parse_args()

    output_dir = Path(args.output_dir) if args.output_dir else OUTPUTS_DIR

    logger.info(f"Loading study: {args.study_name}")

    # Try loading from JSON first (auto mode), or force from JSON with --from-json
    results_json = load_results_json(args.study_name)
    candidates = results_json.get("candidates", [])
    gate_results = results_json.get("gate_results", {})

    if args.from_json:
        # FORCE JSON: error if not found
        if not candidates or not gate_results:
            logger.error("--from-json set but results JSON not found or incomplete")
            return
        logger.info(f"FORCED from JSON: {len(candidates)} candidates")
    elif candidates and gate_results:
        # AUTO: JSON first
        logger.info(f"Loaded {len(candidates)} candidates from JSON")
    else:
        # AUTO FALLBACK: JSON unavailable → DB
        logger.info("JSON unavailable, falling back to Optuna DB")
        results = load_study_results(args.study_name)
        logger.info(f"Loaded {len(results)} trials")

        if not results:
            logger.error("No results found")
            return

        candidates = results[: args.top]

        # Apply real gates
        gate_results = {}
        for cand in candidates:
            tid = str(cand["trial_id"])
            m = cand.get("user_attrs", {})
            is_metrics = {
                "profit_factor": m.get("pf", 0),
                "calmar": m.get("calmar", 0),
                "max_drawdown_90d": m.get("mdd", 0) * 100,
                "sharpe": m.get("sharpe_raw", 0),
                "win_rate": m.get("win_rate", 0) * 100,
                "trades": m.get("trades", 0),
                "risk_checks": {"hard_ruin_50": 0.03},
            }
            cost_robust = m.get("cost_robustness", "ROBUSTO")
            cost_robust_normalized = _normalize_cost_label(cost_robust)
            passed, gates = check_acceptance_gates(
                is_metrics, None, None, cost_robust_normalized
            )
            gate_results[tid] = gates
            gate_results[tid]["passed"] = passed

    # Select final candidate
    selected = select_final_candidate(candidates, gate_results)

    if "error" in selected:
        logger.error("No candidate passed all gates!")
    else:
        logger.info(f"Final candidate: Trial {selected['selected_trial_id']}")

    # Generate promotion report
    report_path = generate_promotion_report(selected, args.study_name, output_dir)
    logger.info(f"Promotion report: {report_path}")

    # Print summary
    logger.info(f"\n=== S4 SELECTION SUMMARY ===")
    logger.info(f"Study: {args.study_name}")
    logger.info(f"Top considered: {len(candidates)}")
    logger.info(f"Selected: {selected.get('selected_trial_id', 'NONE')}")
    logger.info(f"Report: {report_path}")


if __name__ == "__main__":
    main()
