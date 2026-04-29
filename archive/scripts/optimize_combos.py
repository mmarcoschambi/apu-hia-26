#!/usr/bin/env python3
"""
Optimize and rank combo strategies.

Runs predefined combo candidates, collects OOS metrics, and exports a top-K
ranking for Streamlit production selection.
"""

from __future__ import annotations

import argparse
import json
import logging
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from optimize_combo import list_available_combos, run_combo_optimization

logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parent
RESULTS_DIR = ROOT / "config" / "combo_results"
TOP5_PATH = ROOT / "config" / "combos" / "top5.json"


def _combo_score(item: Dict[str, Any]) -> float:
    """Score compuesto para rankear combos en el torneo.

    Componentes:
      - sharpe_adj : Sharpe penalizado por PBO y DD (base del score)
      - trade_factor: bonus por volumen de trades (estrategias con mas trades son mas confiables)
      - pf_bonus   : profit_factor > 1.0 agrega hasta +0.3 al score
      - wr_bonus   : win_rate > 40% agrega hasta +0.2

    Con sharpe negativo el score es negativo pero sigue siendo comparable entre combos.
    """
    v = item.get("validation", {})
    sharpe = float(v.get("sharpe_ratio", 0.0))
    trades = max(int(v.get("total_trades", 0)), 0)
    pbo = float(v.get("pbo_score", 1.0))
    dd = float(v.get("max_drawdown_pct", 100.0))
    pf = float(v.get("profit_factor", 0.0))
    wr = float(v.get("win_rate_pct", 0.0)) / 100.0  # normalizar a 0..1

    # Factores multiplicativos (todos en 0..1)
    trade_factor = min(1.0, (trades / 100.0) ** 0.5)  # satura en 100 trades
    pbo_factor = max(0.0, 1.0 - pbo)  # 0% PBO = factor 1.0
    dd_factor = max(0.0, 1.0 - min(dd, 100.0) / 100.0)

    # Score base: Sharpe ajustado por robustez
    base = sharpe * trade_factor * (0.5 + 0.5 * pbo_factor) * (0.5 + 0.5 * dd_factor)

    # Bonos aditivos: recompensan calidad independientemente del Sharpe
    pf_bonus = max(0.0, min(0.3, (pf - 1.0) * 0.15))  # pf=3.0 -> +0.30
    wr_bonus = max(0.0, min(0.2, (wr - 0.40) * 1.0))  # wr=60% -> +0.20

    return base + pf_bonus + wr_bonus


def _passes_gates(
    item: Dict[str, Any],
    min_trades: int,
    max_dd: float,
    max_pbo: float,
    strict: bool = True,
) -> bool:
    """Gate de calidad para el ranking.

    strict=True  (default): exige validation_passed y profit_factor>=1.0
    strict=False (fallback): solo filtra basura obvia (sharpe<0, DD extremo)
    Esto evita que top5.json quede vacio cuando todos fallan ResearchGate.
    """
    v = item.get("validation", {})
    sharpe = float(v.get("sharpe_ratio", 0.0))
    trades = int(v.get("total_trades", 0))
    dd = float(v.get("max_drawdown_pct", 100.0))
    pbo = float(v.get("pbo_score", 1.0))
    pf = float(v.get("profit_factor", 0.0))

    if strict:
        return (
            bool(item.get("validation_passed", False))
            and sharpe > 0.0
            and trades >= min_trades
            and dd <= max_dd
            and pbo <= max_pbo
            and pf >= 1.0
        )
    # Modo relajado: solo descarta combinaciones claramente malas
    return (
        sharpe > -1.0  # no catastroficos
        and trades >= max(10, min_trades // 3)  # algo de actividad
        and dd <= max_dd * 2  # drawdown no extremo
    )


def _diversify(
    items: List[Dict[str, Any]], max_same_pattern: int = 2, max_same_screener: int = 2
) -> List[Dict[str, Any]]:
    selected: List[Dict[str, Any]] = []
    by_pattern: Dict[str, int] = {}
    by_screener: Dict[str, int] = {}
    for item in items:
        pattern = item.get("pattern", "unknown")
        screener = item.get("screener", "unknown")
        if by_pattern.get(pattern, 0) >= max_same_pattern:
            continue
        if by_screener.get(screener, 0) >= max_same_screener:
            continue
        selected.append(item)
        by_pattern[pattern] = by_pattern.get(pattern, 0) + 1
        by_screener[screener] = by_screener.get(screener, 0) + 1
    return selected


def run_tournament(args) -> List[Dict[str, Any]]:
    # Solo combos canonicos en el torneo de produccion (sin sufijo _v1/_v2/_w1/etc).
    # Las variantes de experimento se corren con --combo <nombre_variante> explicitamente.
    # Whitelist explicita: solo combos canonicos de produccion en el torneo.
    # Variantes de experimento (_v1/_v2/_w1/etc) se corren con --combo explicito.
    _CANONICAL_COMBOS = {
        "combo_pullback_entry",
        # "combo_ideal_setup",          # RETIRADO 2026-04-13: 0 trades OOS estructural (VCP+Minervini demasiado selectivo)
        "combo_stage2_breakout",
        "combo_pure_momentum",
        # "combo_aggressive_momentum",  # RETIRADO 2026-04-13: 0 trades OOS estructural (pocket_pivot+Minervini demasiado selectivo)
        "combo_universal_any",
    }
    combos = [c for c in list_available_combos() if c in _CANONICAL_COMBOS]
    if args.combo:
        combos = [args.combo]

    results: List[Dict[str, Any]] = []
    for combo_name in combos:
        logger.info("Running combo %s", combo_name)
        if args.isolate_combo:
            result = _run_combo_optimization_isolated(combo_name, args)
        else:
            result = run_combo_optimization(
                combo_name=combo_name,
                start_date=args.start,
                end_date=args.end,
                n_trials=args.trials,
                n_jobs=args.jobs,
                tickers_limit=args.tickers,
                skip_validation=args.skip_validation,
                skip_optimization=args.skip_optimization,
                seed=args.seed,
                liquidity_stratified=not args.no_stratified,
            )
        results.append(result)
    return results


def _build_isolated_cmd(
    combo_name: str, args, *, retry_mode: bool = False
) -> List[str]:
    cmd = [
        sys.executable,
        str(ROOT / "optimize_combo.py"),
        "--combo",
        combo_name,
        "--start",
        args.start,
        "--end",
        args.end,
        "--trials",
        str(args.retry_trials if retry_mode else args.trials),
        "--njobs",
        str(args.jobs),
        "--tickers",
        str(args.retry_tickers if retry_mode else args.tickers),
        "--seed",
        str(args.seed),
    ]
    if args.skip_validation or (retry_mode and args.retry_skip_validation):
        cmd.append("--skip-validation")
    if args.skip_optimization:
        cmd.append("--skip-optimization")
    if args.no_stratified:
        cmd.append("--no-stratified-universe")
    return cmd


def _load_isolated_result(combo_name: str) -> Dict[str, Any]:
    export_path = RESULTS_DIR / f"{combo_name}_optimized.json"
    if not export_path.exists():
        raise FileNotFoundError(f"Expected result file not found: {export_path}")

    with open(export_path, "r", encoding="utf-8") as f:
        payload = json.load(f)

    validation = payload.get("validation", {})
    return {
        "combo": combo_name,
        "score": float(payload.get("optimization_score", 0.0)),
        "oos_score": float(validation.get("sharpe_ratio", 0.0)),
        "validation_passed": bool(payload.get("validation_passed", False)),
        "validation": validation,
        "tier1": payload.get("tier1_exits", {}),
        "tier2": payload.get("tier2_filters", {}),
        "export_path": str(export_path),
    }


ISOLATED_TIMEOUT_SECONDS = 600


def _run_combo_optimization_isolated(combo_name: str, args) -> Dict[str, Any]:
    def _attempt_run(
        cmd: List[str], timeout: int
    ) -> Tuple[bool, Optional[subprocess.CompletedProcess]]:
        try:
            proc = subprocess.run(cmd, cwd=str(ROOT), check=False, timeout=timeout)
            return (proc.returncode == 0, proc)
        except subprocess.TimeoutExpired:
            logger.error("  Combo %s timed out after %ds", combo_name, timeout)
            return (False, None)

    def _try_load_result() -> Optional[Dict[str, Any]]:
        try:
            return _load_isolated_result(combo_name)
        except FileNotFoundError as e:
            logger.error("  Result file missing for %s: %s", combo_name, e)
        except json.JSONDecodeError as e:
            logger.error("  Result file malformed for %s: %s", combo_name, e)
        except Exception as e:
            logger.error("  Failed to load result for %s: %s", combo_name, e)
        return None

    retry_count = max(0, args.retry_on_crash)
    last_error = None

    for attempt in range(retry_count + 1):
        is_retry = attempt > 0
        cmd = _build_isolated_cmd(combo_name, args, retry_mode=is_retry)
        timeout = (
            ISOLATED_TIMEOUT_SECONDS
            if not is_retry
            else (ISOLATED_TIMEOUT_SECONDS // 2)
        )

        logger.info(
            "  %s (attempt %d/%d): %s",
            "Retry" if is_retry else "Isolated run",
            attempt + 1,
            retry_count + 1,
            " ".join(cmd),
        )

        success, proc = _attempt_run(cmd, timeout)
        if success:
            result = _try_load_result()
            if result is not None:
                return result
            last_error = "process succeeded but result file invalid/missing"

        exit_code = proc.returncode if proc else -1
        logger.error(
            "  Combo %s failed (attempt %d, exit code=%s)",
            combo_name,
            attempt + 1,
            exit_code,
        )
        last_error = f"exit code={exit_code}"

    return {
        "combo": combo_name,
        "score": -999.0,
        "oos_score": -999.0,
        "validation_passed": False,
        "validation": {},
        "tier1": {},
        "tier2": {},
        "export_path": "",
        "error": f"failed after {retry_count + 1} attempts: {last_error}",
    }


def export_topk(results: List[Dict[str, Any]], top_k: int = 5) -> List[Dict[str, Any]]:
    """Exporta los mejores combos con fallback de dos niveles.

    Nivel 1 (strict): pasan ResearchGate + profit_factor>=1.0
    Nivel 2 (relajado): fallback si ningun combo pasa el nivel 1
    Siempre exporta algo util al top5.json (nunca lista vacia si hay resultados).
    """
    # --- Scoring de todos los resultados (antes de filtrar) ---
    for r in results:
        r["combo_score"] = round(_combo_score(r), 4)
        v = r.get("validation", {})
        logger.info(
            "  [SCORE] %s | score=%.4f | sharpe=%.2f | pf=%.2f | pbo=%.2f | "
            "dd=%.1f%% | trades=%d | passed=%s",
            r.get("combo", "?"),
            r["combo_score"],
            float(v.get("sharpe_ratio", 0.0)),
            float(v.get("profit_factor", 0.0)),
            float(v.get("pbo_score", 1.0)),
            float(v.get("max_drawdown_pct", 0.0)),
            int(v.get("total_trades", 0)),
            r.get("validation_passed", False),
        )

    # --- Nivel 1: gate estricto (ResearchGate aprobado) ---
    strict_pass = [
        r
        for r in results
        if _passes_gates(r, min_trades=30, max_dd=25.0, max_pbo=0.50, strict=True)
    ]

    if strict_pass:
        logger.info(
            "Gate estricto: %d/%d combos aprobados", len(strict_pass), len(results)
        )
        pool = strict_pass
        gate_label = "strict"
    else:
        # --- Nivel 2: fallback relajado ---
        relaxed_pass = [
            r
            for r in results
            if _passes_gates(r, min_trades=30, max_dd=25.0, max_pbo=0.50, strict=False)
        ]
        if relaxed_pass:
            logger.warning(
                "Ningun combo paso el gate estricto. Usando fallback relajado "
                "(%d candidatos). Los combos no son production-ready.",
                len(relaxed_pass),
            )
            pool = relaxed_pass
            gate_label = "relaxed"
        else:
            logger.error(
                "TODOS los combos fallaron incluso el gate relajado. top5.json vacio."
            )
            TOP5_PATH.parent.mkdir(parents=True, exist_ok=True)
            with open(TOP5_PATH, "w", encoding="utf-8") as f:
                json.dump([], f, indent=2)
            return []

    pool.sort(key=lambda x: x["combo_score"], reverse=True)
    diversified = _diversify(pool)
    top = diversified[:top_k]

    # Agregar metadata del gate aplicado
    for r in top:
        r["_gate"] = gate_label

    TOP5_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(TOP5_PATH, "w", encoding="utf-8") as f:
        json.dump(top, f, indent=2, default=str)

    logger.info(
        "Exported top %d combos (%s gate) to %s", len(top), gate_label, TOP5_PATH
    )
    return top


def main() -> None:
    parser = argparse.ArgumentParser(description="Tournament of combo strategies")
    parser.add_argument("--combo", type=str, default=None, help="Run a single combo")
    parser.add_argument("--start", type=str, default="2019-01-01")
    parser.add_argument("--end", type=str, default="2024-12-31")
    parser.add_argument("--trials", type=int, default=50)
    parser.add_argument("--jobs", type=int, default=1)
    parser.add_argument("--tickers", type=int, default=200)
    parser.add_argument("--skip-validation", action="store_true")
    parser.add_argument("--skip-optimization", action="store_true")
    parser.add_argument("--list-combos", action="store_true")
    parser.add_argument(
        "--seed", type=int, default=42, help="Random seed for universe sampling"
    )
    parser.add_argument(
        "--no-stratified",
        action="store_true",
        default=False,
        help="Use legacy top-by-count universe (default: stratified)",
    )
    parser.add_argument(
        "--isolate-combo",
        dest="isolate_combo",
        action="store_true",
        default=True,
        help="Run each combo in a subprocess to isolate native crashes (default: enabled)",
    )
    parser.add_argument(
        "--no-isolate-combo",
        dest="isolate_combo",
        action="store_false",
        help="Run combos in-process (legacy behavior)",
    )
    parser.add_argument(
        "--retry-on-crash",
        type=int,
        default=1,
        help="Retry count per combo when subprocess exits with native crash (default: 1)",
    )
    parser.add_argument(
        "--retry-tickers",
        type=int,
        default=80,
        help="Ticker cap used by retry profile (default: 80)",
    )
    parser.add_argument(
        "--retry-trials",
        type=int,
        default=10,
        help="Trial cap used by retry profile (default: 10)",
    )
    parser.add_argument(
        "--retry-skip-validation",
        action="store_true",
        default=True,
        help="Skip validation in retry profile to reduce memory pressure (default: enabled)",
    )
    parser.add_argument(
        "--no-retry-skip-validation",
        dest="retry_skip_validation",
        action="store_false",
        help="Keep validation enabled in retry profile",
    )
    args = parser.parse_args()

    if args.list_combos:
        for combo in list_available_combos():
            print(combo)
        return

    results = run_tournament(args)
    top = export_topk(results, top_k=5)
    logger.info("Top combos:")
    for idx, item in enumerate(top, 1):
        logger.info(
            "%s. %s | score=%.4f | sharpe=%.2f | trades=%s",
            idx,
            item.get("combo"),
            item.get("combo_score", 0.0),
            item.get("validation", {}).get("sharpe_ratio", 0.0),
            item.get("validation", {}).get("total_trades", 0),
        )


if __name__ == "__main__":
    main()
