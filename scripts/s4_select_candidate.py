#!/usr/bin/env python3
"""
scripts/s4_select_candidate.py
=============================
Selecciona el candidato final de S4 y genera reporte de trazabilidad.

Criterio de selección (en orden de prioridad):
1. Si existe validación OOS: selecciona por OOS Sharpe estable
   (Val > 0 AND OOS > 0, ordenado por oos_sharpe desc)
2. Si no hay OOS: selecciona por score_composed IS (comportamiento anterior)

Usage:
    python3 scripts/s4_select_candidate.py --study-name s4_main_v2
    python3 scripts/s4_select_candidate.py --study-name s4_main_v2 --from-json
"""

import argparse
import glob
import json
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

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


# === LOADERS ===


def load_results_json(study_name: str) -> Dict[str, Any]:
    """Carga el results JSON más reciente para el estudio."""
    pattern = str(OUTPUTS_DIR / f"results_{study_name}_*.json")
    matches = sorted(glob.glob(pattern), reverse=True)
    if matches:
        try:
            with open(matches[0]) as f:
                data = json.load(f)
            logger.info(f"Loaded results from: {matches[0]}")
            return data
        except Exception as e:
            logger.warning(f"Could not load {matches[0]}: {e}")
    return {}


def load_oos_validation(study_name: str) -> Optional[Dict[str, Any]]:
    """Carga el JSON de validación OOS más reciente, si existe."""
    pattern = str(OUTPUTS_DIR / f"optuna_validation_oos_{study_name}_*.json")
    matches = sorted(glob.glob(pattern), reverse=True)
    if matches:
        try:
            with open(matches[0]) as f:
                data = json.load(f)
            logger.info(f"Loaded OOS validation from: {matches[0]}")
            return data
        except Exception as e:
            logger.warning(f"Could not load OOS validation: {e}")
    return None


def load_study_from_db(study_name: str, top_n: int = 10) -> List[Dict]:
    """Fallback: carga trials desde Optuna DB."""
    db_path = f"sqlite:///{OUTPUTS_DIR}/{study_name}.db"
    try:
        study = optuna.load_study(study_name=study_name, storage=db_path)
        results = []
        for trial in study.trials:
            if trial.value and trial.value > -999:
                results.append({
                    "trial_id": trial.number,
                    "score": trial.value,
                    "score_composed": trial.value,
                    "params": trial.params,
                    "user_attrs": trial.user_attrs,
                })
        return sorted(results, key=lambda x: x["score"], reverse=True)[:top_n]
    except Exception as e:
        logger.error(f"Could not load DB {study_name}: {e}")
        return []


# === SELECTION LOGIC ===


def select_by_oos(
    candidates: List[Dict],
    gate_results: Dict[str, Any],
    oos_data: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    """
    Selección primaria: usa OOS Sharpe cuando existe validación OOS.

    Criterios en orden:
    1. gate passed = True
    2. val_sharpe > 0 (no colapsa en Val / mercado adverso)
    3. oos_sharpe > 0
    4. Ordenado por oos_sharpe desc
    """
    # Indexar OOS por trial_id
    oos_by_trial = {
        str(c["trial_id"]): c
        for c in oos_data.get("candidates", [])
    }

    scored = []
    for cand in candidates:
        tid = str(cand.get("trial_id", 0))
        gr = gate_results.get(tid, {})

        if not gr.get("passed", False):
            continue

        oos = oos_by_trial.get(tid)
        if oos is None:
            # Candidato sin datos OOS — lo incluimos con score bajo
            scored.append((cand, gr, -1.0, -1.0, -1.0))
            continue

        val_sharpe = oos.get("val_sharpe", -999)
        oos_sharpe = oos.get("oos_sharpe", -999)
        oos_calmar = oos.get("oos_calmar", 0)

        # Filtrar los que colapsan en Val o tienen OOS negativo
        if val_sharpe <= 0 or oos_sharpe <= 0:
            logger.info(
                f"  Trial {tid}: descartado por Val={val_sharpe:.2f} "
                f"OOS={oos_sharpe:.2f}"
            )
            continue

        scored.append((cand, gr, val_sharpe, oos_sharpe, oos_calmar))

    if not scored:
        logger.warning("Ningún candidato pasó filtro OOS (Val>0, OOS>0). "
                       "Relajando — incluyendo candidatos con OOS > 0 aunque Val <= 0.")
        # Fallback: solo OOS > 0
        for cand in candidates:
            tid = str(cand.get("trial_id", 0))
            gr = gate_results.get(tid, {})
            if not gr.get("passed", False):
                continue
            oos = oos_by_trial.get(tid)
            if oos and oos.get("oos_sharpe", -999) > 0:
                scored.append((
                    cand, gr,
                    oos.get("val_sharpe", -999),
                    oos.get("oos_sharpe", 0),
                    oos.get("oos_calmar", 0),
                ))

    if not scored:
        return None

    # Ordenar por OOS Sharpe desc, luego OOS Calmar
    scored.sort(key=lambda x: (x[3], x[4]), reverse=True)
    best_cand, best_gr, val_s, oos_s, oos_cal = scored[0]
    tid = str(best_cand.get("trial_id", 0))

    logger.info(
        f"  → OOS selection: Trial {tid} | "
        f"Val={val_s:.2f} OOS={oos_s:.2f} Calmar={oos_cal:.2f}"
    )

    return {
        "selected_trial_id": tid,
        "selection_method": "OOS_SHARPE",
        "score_composed": best_cand.get("score_composed", 0),
        "oos_sharpe": oos_s,
        "oos_calmar": oos_cal,
        "val_sharpe": val_s,
        "params": best_cand.get("params", {}),
        "metrics": best_cand.get("user_attrs", best_cand),
        "gate_results": best_gr,
    }


def select_by_is_score(
    candidates: List[Dict],
    gate_results: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    """
    Selección fallback: top IS score_composed que pasó gates.
    """
    for cand in sorted(
        candidates, key=lambda x: x.get("score_composed", x.get("score", 0)), reverse=True
    ):
        tid = str(cand.get("trial_id", 0))
        gr = gate_results.get(tid, {})
        if gr.get("passed", False):
            score = cand.get("score_composed", cand.get("score", 0))
            logger.info(f"  → IS selection: Trial {tid} | score={score:.4f}")
            return {
                "selected_trial_id": tid,
                "selection_method": "IS_SCORE_COMPOSED",
                "score_composed": score,
                "params": cand.get("params", {}),
                "metrics": cand.get("user_attrs", {}),
                "gate_results": gr,
            }
    return None


# === PROMOTION REPORT ===


def generate_promotion_report(
    candidate: Dict[str, Any],
    study_name: str,
    output_dir: Path,
    oos_data: Optional[Dict] = None,
) -> Path:
    """Genera reporte de promoción con trazabilidad completa."""
    report = {
        "generated_at": datetime.now().isoformat(),
        "study_name": study_name,
        "selection_method": candidate.get("selection_method", "UNKNOWN"),
        "promoted_candidate": candidate,
        "trazability": {
            "optuna_db": str(output_dir / f"{study_name}.db"),
            "results_json": str(
                sorted(glob.glob(str(output_dir / f"results_{study_name}_*.json")),
                       reverse=True)[0]
            ) if glob.glob(str(output_dir / f"results_{study_name}_*.json")) else None,
            "oos_validation_json": str(
                sorted(glob.glob(str(output_dir / f"optuna_validation_oos_{study_name}_*.json")),
                       reverse=True)[0]
            ) if glob.glob(str(output_dir / f"optuna_validation_oos_{study_name}_*.json")) else None,
            "gate_results": candidate.get("gate_results", {}),
            "params_used": candidate.get("params", {}),
        },
        "oos_summary": {
            "oos_sharpe": candidate.get("oos_sharpe"),
            "oos_calmar": candidate.get("oos_calmar"),
            "val_sharpe": candidate.get("val_sharpe"),
            "pbo_proxy": oos_data.get("pbo_proxy") if oos_data else None,
            "interpretation": oos_data.get("interpretation") if oos_data else None,
        } if oos_data else None,
        "next_steps": [
            "1. Actualizar production_config.json con params promovidos (tier2_filters + s4_params)",
            "2. Activar paper trading: python3 scripts/paper_trading_runbook.py --phase pre",
            "3. Monitorear 30 días en paper antes de live",
            "4. Gate de avance a live: >= 20 trades, Sharpe paper > 0.5, WR > 50%",
        ],
    }

    report_path = (
        output_dir
        / f"promotion_report_{study_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    )
    with open(report_path, "w") as f:
        json.dump(report, f, indent=2, default=str)

    return report_path


# === MAIN ===


def main():
    parser = argparse.ArgumentParser(description="S4 Candidate Selection")
    parser.add_argument("--study-name", type=str, default="s4_main_v2")
    parser.add_argument("--top", type=int, default=10)
    parser.add_argument("--output-dir", type=str, default=None)
    parser.add_argument("--from-json", action="store_true",
                        help="Forzar carga desde JSON (error si no existe)")
    parser.add_argument("--no-oos", action="store_true",
                        help="Ignorar OOS, seleccionar por IS score")

    args = parser.parse_args()
    output_dir = Path(args.output_dir) if args.output_dir else OUTPUTS_DIR

    logger.info(f"=== S4 Candidate Selection: {args.study_name} ===")

    # 1. Cargar results
    results_data = load_results_json(args.study_name)
    candidates = results_data.get("candidates", [])
    gate_results = results_data.get("gate_results", {})

    if args.from_json and (not candidates or not gate_results):
        logger.error("--from-json: results JSON no encontrado o incompleto")
        return

    if not candidates:
        logger.info("JSON no disponible, cargando desde DB...")
        candidates = load_study_from_db(args.study_name, args.top)
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
            cost_robust = _normalize_cost_label(m.get("cost_robustness", "ROBUSTO"))
            passed, gates = check_acceptance_gates(is_metrics, None, None, cost_robust)
            gate_results[tid] = {**gates, "passed": passed}

    logger.info(f"Candidates loaded: {len(candidates)}")
    logger.info(f"Gate results: {sum(1 for g in gate_results.values() if g.get('passed'))} passed")

    # 2. Cargar OOS si existe
    oos_data = None if args.no_oos else load_oos_validation(args.study_name)

    # 3. Seleccionar
    selected = None
    if oos_data and not args.no_oos:
        logger.info("Seleccionando por OOS Sharpe (Val>0, OOS>0)...")
        selected = select_by_oos(candidates, gate_results, oos_data)

    if selected is None:
        if oos_data:
            logger.warning("OOS selection falló, usando IS score como fallback")
        else:
            logger.info("Sin datos OOS, seleccionando por IS score_composed...")
        selected = select_by_is_score(candidates, gate_results)

    if selected is None:
        logger.error("No se pudo seleccionar ningún candidato")
        return

    # 4. Generar promotion report
    report_path = generate_promotion_report(selected, args.study_name, output_dir, oos_data)

    # 5. Summary
    logger.info(f"\n=== RESULTADO ===")
    logger.info(f"Método:    {selected['selection_method']}")
    logger.info(f"Trial:     {selected['selected_trial_id']}")
    logger.info(f"Score IS:  {selected.get('score_composed', 0):.4f}")
    if selected.get("oos_sharpe") is not None:
        logger.info(f"Val Sharpe: {selected.get('val_sharpe', 0):.3f}")
        logger.info(f"OOS Sharpe: {selected.get('oos_sharpe', 0):.3f}")
        logger.info(f"OOS Calmar: {selected.get('oos_calmar', 0):.3f}")
    logger.info(f"Report:    {report_path}")
    logger.info(f"\nParams a promover a production_config.json:")
    for k, v in selected.get("params", {}).items():
        logger.info(f"  {k}: {v}")


if __name__ == "__main__":
    main()
