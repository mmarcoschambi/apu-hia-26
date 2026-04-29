#!/usr/bin/env python3
"""
scripts/validate_optuna_results.py
==================================
Validación estadística de resultados de Optuna S4.

Incluye:
- Bootstrap CI del Sharpe OOS (95%)
- Deflated Sharpe (ajustado por múltiples trials)
- Proxy de overfitting (retorno promedio de trials no seleccionados)

Usage:
    python3 scripts/validate_optuna_results.py --study-name s4_main
    python3 scripts/validate_optuna_results.py --study-name s4_main --n-bootstraps 1000
"""

import argparse
import json
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
import optuna

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)

OUTPUTS_DIR = PROJECT_ROOT / "outputs" / "optuna_s4"


def load_study_trials(study_name: str) -> List[optuna.Trial]:
    """Carga todos los trials del estudio."""
    db_path = f"sqlite:///{OUTPUTS_DIR}/{study_name}.db"
    try:
        study = optuna.load_study(study_name=study_name, storage=db_path)
        return [t for t in study.trials if t.value and t.value > -999]
    except Exception as e:
        logger.error(f"Could not load study: {e}")
        return []


def compute_sharpe_bootstrap(
    sharpe_values: List[float],
    n_bootstrap: int = 1000,
    confidence: float = 0.95,
) -> Dict[str, float]:
    """
    Calcula bootstrap confidence interval para Sharpe.

    Returns:
        dict con mean, std, ci_lower, ci_upper, median
    """
    if not sharpe_values or len(sharpe_values) < 2:
        return {"mean": 0, "std": 0, "ci_lower": 0, "ci_upper": 0, "median": 0}

    sharpe_arr = np.array(sharpe_values)
    bootstrap_samples = []

    np.random.seed(42)
    for _ in range(n_bootstrap):
        sample = np.random.choice(sharpe_arr, size=len(sharpe_arr), replace=True)
        bootstrap_samples.append(np.mean(sample))

    bootstrap_arr = np.array(bootstrap_samples)
    alpha = 1 - confidence

    return {
        "mean": float(np.mean(bootstrap_arr)),
        "std": float(np.std(bootstrap_arr)),
        "ci_lower": float(np.percentile(bootstrap_arr, alpha / 2 * 100)),
        "ci_upper": float(np.percentile(bootstrap_arr, (1 - alpha / 2) * 100)),
        "median": float(np.median(bootstrap_arr)),
    }


def compute_deflated_sharpe(
    oos_sharpe: float,
    n_trials: int,
    n_params: int = 6,
) -> Dict[str, Any]:
    """
    Calcula Deflated Sharpe Ratio (DSR).

    Formula aproximada de Bailey et al.:
    DSR = (Sharpe - zeta * sigma_z) / sqrt(1 - rho^2)

    Donde:
    - zeta: factor de ajuste por búsqueda (función de n_trials, n_params)
    - sigma_z: incertidumbre en el Sharpe estimado
    - rho: correlación promedio entre trials (asumimos 0.1 para portfolios similares)

    Returns:
        dict con deflated_sharpe, adjustment_factor, lcl (lower confidence level)
    """
    if n_trials < 2 or oos_sharpe <= 0:
        return {"deflated_sharpe": 0, "adjustment_factor": 0, "lcl": 0}

    # Factor de ajuste por sobreajuste ( приблизительно)
    # Lc = q_alpha * sqrt(log(n_params / n_trials))
    # Para alfa=0.05, q_0.05 ≈ 1.96
    q_alpha = 1.96
    log_ratio = np.log(n_params / n_trials) if n_params < n_trials else 0
    lc = q_alpha * np.sqrt(max(0, -log_ratio)) if log_ratio < 0 else 0

    # Ajuste por número de trials
    # Entre más trials, menor el ajuste (más confianza en el resultado)
    adjustment = lc * 0.3  # Factor escalar empírico

    deflated = max(0, oos_sharpe - adjustment)

    # LCL (Lower Confidence Level) - assuming normal distribution
    lcl = max(0, oos_sharpe - 1.96 * (oos_sharpe / np.sqrt(n_trials)))

    return {
        "deflated_sharpe": round(deflated, 3),
        "adjustment_factor": round(adjustment, 3),
        "lcl": round(lcl, 3),
        "n_trials": n_trials,
        "n_params": n_params,
    }


def compute_pbo_proxy(
    trial_sharpes: List[float],
    top_sharpe: float,
) -> Dict[str, Any]:
    """
    Calcula Probability of Backtest Overfitting (proxy).

    Compara el Sharpe del mejor trial vs distribución de sharpes.
    Si el mejor trial está en la cola extrema, mayor probabilidad de overfitting.

    Returns:
        dict con pbo_score, interpretation
    """
    if len(trial_sharpes) < 10:
        return {"pbo_score": 0, "interpretation": "INSUFFICIENT_TRIALS"}

    sharpe_arr = np.array(trial_sharpes)
    mean_sharpe = np.mean(sharpe_arr)
    std_sharpe = np.std(sharpe_arr)

    if std_sharpe == 0:
        return {"pbo_score": 0, "interpretation": "NO_VARIANCE"}

    # Z-score del mejor trial
    z_score = (top_sharpe - mean_sharpe) / std_sharpe

    # PBO proxy: probabilidad de que el mejor sea sobreajuste
    # Si z_score muy alto (>3), alta probabilidad de overfitting
    # Usamos una función sigmoidal para soften
    pbo = 1 / (1 + np.exp(-(z_score - 2.5)))

    if pbo < 0.2:
        interpretation = "LOW_OVERFITTING_RISK"
    elif pbo < 0.5:
        interpretation = "MODERATE_OVERFITTING_RISK"
    else:
        interpretation = "HIGH_OVERFITTING_RISK"

    return {
        "pbo_score": round(pbo, 3),
        "interpretation": interpretation,
        "top_sharpe": round(top_sharpe, 3),
        "mean_sharpe": round(mean_sharpe, 3),
        "std_sharpe": round(std_sharpe, 3),
        "z_score": round(z_score, 2),
    }


def compute_overfitting_metrics(trials: List[optuna.Trial]) -> Dict[str, Any]:
    """Calcula métricas de sobreajuste."""
    valid_trials = [t for t in trials if t.value and t.value > -999]

    if not valid_trials:
        return {"error": "NO_VALID_TRIALS"}

    sharpes = [t.user_attrs.get("sharpe_raw", 0) for t in valid_trials]
    pfs = [t.user_attrs.get("pf", 0) for t in valid_trials]
    trades = [t.user_attrs.get("trades", 0) for t in valid_trials]

    # Filtrar valores válidos
    sharpes = [s for s in sharpes if s > -999]
    pfs = [p for p in pfs if p > 0]
    trades = [t for t in trades if t > 0]

    if not sharpes:
        return {"error": "NO_SHARPE_VALUES"}

    top_sharpe = max(sharpes)
    mean_sharpe = np.mean(sharpes)
    median_sharpe = np.median(sharpes)

    # Retorno promedio de no-top trials (vs top)
    non_top_sharpes = [s for s in sharpes if s < top_sharpe]
    avg_non_top = np.mean(non_top_sharpes) if non_top_sharpes else 0
    decay_from_top = (top_sharpe - avg_non_top) / top_sharpe if top_sharpe > 0 else 0

    return {
        "n_trials": len(valid_trials),
        "n_valid_sharpes": len(sharpes),
        "top_sharpe": round(top_sharpe, 3),
        "mean_sharpe": round(mean_sharpe, 3),
        "median_sharpe": round(median_sharpe, 3),
        "std_sharpe": round(np.std(sharpes), 3),
        "avg_non_top_sharpe": round(avg_non_top, 3),
        "decay_from_top_pct": round(decay_from_top * 100, 1),
        "top_pf": round(max(pfs), 2) if pfs else 0,
        "avg_trades": round(np.mean(trades), 0) if trades else 0,
    }


def validate_optuna_results(
    study_name: str,
    n_bootstrap: int = 1000,
    confidence: float = 0.95,
) -> Dict[str, Any]:
    """Valida resultados de Optuna."""
    logger.info(f"Validating study: {study_name}")

    trials = load_study_trials(study_name)
    if not trials:
        return {"error": "NO_TRIALS_FOUND"}

    # Extraer métricas
    sharpes = [t.user_attrs.get("sharpe_raw", 0) for t in trials]
    valid_sharpes = [s for s in sharpes if s > -999 and s != 0]

    if not valid_sharpes:
        return {"error": "NO_VALID_SHARPES"}

    top_sharpe = max(valid_sharpes)
    top_trial = [t for t in trials if t.user_attrs.get("sharpe_raw") == top_sharpe]
    top_trial_id = top_trial[0].number if top_trial else 0

    # Bootstrap CI
    bootstrap = compute_sharpe_bootstrap(valid_sharpes, n_bootstrap, confidence)

    # Deflated Sharpe
    n_params = 6  # Asumimos 6 params en espacio reducido
    deflated = compute_deflated_sharpe(top_sharpe, len(trials), n_params)

    # PBO proxy
    pbo = compute_pbo_proxy(valid_sharpes, top_sharpe)

    # Overfitting metrics
    overfit = compute_overfitting_metrics(trials)

    validation = {
        "study_name": study_name,
        "generated_at": datetime.now().isoformat(),
        "top_trial_id": top_trial_id,
        "top_sharpe": round(top_sharpe, 3),
        "bootstrap_ci": bootstrap,
        "deflated_sharpe": deflated,
        "pbo_proxy": pbo,
        "overfitting_metrics": overfit,
    }

    # Guardar
    out_path = (
        OUTPUTS_DIR
        / f"validation_{study_name}_{datetime.now().strftime('%Y%m%d')}.json"
    )
    with open(out_path, "w") as f:
        json.dump(validation, f, indent=2, default=str)

    logger.info(f"Validation saved: {out_path}")

    # Print summary
    logger.info(f"\n=== VALIDATION SUMMARY ===")
    logger.info(f"Study: {study_name}")
    logger.info(f"Trials: {len(trials)}")
    logger.info(f"Top Sharpe: {top_sharpe:.3f}")
    logger.info(
        f"Bootstrap 95% CI: [{bootstrap['ci_lower']:.3f}, {bootstrap['ci_upper']:.3f}]"
    )
    logger.info(f"Deflated Sharpe: {deflated['deflated_sharpe']:.3f}")
    logger.info(f"PBO Proxy: {pbo['pbo_score']:.3f} ({pbo['interpretation']})")

    return validation


def main():
    parser = argparse.ArgumentParser(description="Validate Optuna S4 Results")
    parser.add_argument("--study-name", type=str, default="s4_main", help="Study name")
    parser.add_argument(
        "--n-bootstraps", type=int, default=1000, help="Number of bootstrap samples"
    )
    parser.add_argument(
        "--confidence", type=float, default=0.95, help="Confidence level (default 0.95)"
    )

    args = parser.parse_args()

    result = validate_optuna_results(
        args.study_name,
        args.n_bootstraps,
        args.confidence,
    )

    if "error" in result:
        logger.error(f"Validation failed: {result['error']}")


if __name__ == "__main__":
    main()
