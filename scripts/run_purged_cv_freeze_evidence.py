#!/usr/bin/env python3
"""
run_purged_cv_freeze_evidence.py

Ejecuta la Fase 2b (Purged Walk-Forward CV) contra el motor real y persiste
un artefacto JSON auditable. Este script NO modifica research_gate.py ni
purged_walk_forward.py — solo los invoca y serializa el resultado.

Uso (correr en Windows, entorno del proyecto):
    python scripts/run_purged_cv_freeze_evidence.py
        --universe-file universe.txt
        --params-json config/validated_production_params.json
        --train-start 2019-01-01
        --train-end 2023-12-31
        --test-start 2024-01-01
        --test-end 2025-12-31
        --n-folds 4
        --purge-days 10
        --embargo-days 5

ADVERTENCIA: esta corrida es pesada (n_folds × IS+OOS backtest sobre el
universo completo). No ejecutar dentro de un ciclo de auditoría automatizado.

Salida: artifacts/purged_cv/purged_cv_report_<timestamp>.json
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# ── imports del proyecto ──────────────────────────────────────────────
from src.backtest.vectorbt_engine_advanced import AdvancedVectorBTEngine
from src.validation.research_gate import ResearchGate

# ── constantes ────────────────────────────────────────────────────────
OUTPUT_DIR = Path("artifacts/purged_cv")
_DEGRADATION_GATE_PCT = 25  # gate mirror del que usa research_gate.py


def _git_commit_hash() -> str:
    """Determinismo: el artefacto queda atado al commit exacto que lo generó."""
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], text=True, encoding="utf-8"
        ).strip()
    except Exception:
        return "UNKNOWN_GIT_HASH"


def _load_universe(path: str) -> list[str]:
    with open(path, "r", encoding="utf-8") as f:
        tickers = [line.strip() for line in f if line.strip()]
    # Determinismo: orden estable, sin depender de iteración de sets/dicts
    return sorted(tickers)


def _load_params(path: str | None) -> dict[str, Any]:
    if path is None:
        return {}
    with open(path, "r", encoding="utf-8") as f:
        raw = json.load(f)
    # validated_production_params.json anida params bajo "parameters"
    if "parameters" in raw and isinstance(raw["parameters"], dict):
        return raw["parameters"]
    return raw


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run Purged Walk-Forward CV and persist evidence artifact"
    )
    parser.add_argument("--universe-file", required=True,
                        help="Path to text file with one ticker per line")
    parser.add_argument("--params-json", default=None,
                        help="Path to JSON with strategy params (e.g. validated_production_params.json)")
    parser.add_argument("--train-start", default="2019-01-01",
                        help="Training period start date (YYYY-MM-DD)")
    parser.add_argument("--train-end", default="2023-12-31",
                        help="Training period end date (YYYY-MM-DD)")
    parser.add_argument("--test-start", default="2024-01-01",
                        help="Test/OOS period start date (YYYY-MM-DD)")
    parser.add_argument("--test-end", default="2025-12-31",
                        help="Test/OOS period end date (YYYY-MM-DD)")
    parser.add_argument("--n-folds", type=int, default=4,
                        help="Number of walk-forward folds")
    parser.add_argument("--purge-days", type=int, default=10,
                        help="Purge window in trading days")
    parser.add_argument("--embargo-days", type=int, default=5,
                        help="Embargo window in trading days")
    args = parser.parse_args()

    universe = _load_universe(args.universe_file)
    params = _load_params(args.params_json)

    purged_cv_config = {
        "n_folds": args.n_folds,
        "purge_days": args.purge_days,
        "embargo_days": args.embargo_days,
    }

    print(f"[RUN] Universe: {len(universe)} tickers")
    print(f"[RUN] Params:   {list(params.keys())[:10]}{'...' if len(params) > 10 else ''}")
    print(f"[RUN] Train:    {args.train_start} → {args.train_end}")
    print(f"[RUN] Test:     {args.test_start} → {args.test_end}")
    print(f"[RUN] Purged CV: {purged_cv_config}")
    print()

    gate = ResearchGate()
    result = gate.validate_strategy(
        engine_class=AdvancedVectorBTEngine,
        params=params,
        universe=universe,
        train_dates=(args.train_start, args.train_end),
        test_dates=(args.test_start, args.test_end),
        verbose=True,
        purged_cv_config=purged_cv_config,
    )

    # ── construir payload ──────────────────────────────────────────────
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_path = OUTPUT_DIR / f"purged_cv_report_{ts}.json"

    # Parseamos degradation desde el ValidationResult
    degradation_pct = result.purged_wf_degradation_pct
    gate_passed = result.purged_wf_passed

    payload: dict[str, Any] = {
        "generated_at_utc": ts,
        "git_commit": _git_commit_hash(),
        "universe_size": len(universe),
        "universe_sorted_first10": universe[:10],
        "train_period": f"{args.train_start}→{args.train_end}",
        "test_period": f"{args.test_start}→{args.test_end}",
        "purged_cv_config": purged_cv_config,
        "params_json_source": args.params_json,
        "degradation_pct": degradation_pct,
        "gate_passed": gate_passed,
        "gate_threshold_pct": _DEGRADATION_GATE_PCT,
        "rejection_reasons": result.rejection_reasons,
        "validation_passed": result.validation_passed,
        "sharpe_ratio": result.sharpe_ratio,
        "profit_factor": result.profit_factor,
        "total_trades": result.total_trades,
        "max_drawdown_pct": result.max_drawdown_pct,
    }

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False, sort_keys=True)

    print(f"\n{'=' * 60}")
    print(f"[OK] Artefacto persistido en: {out_path}")
    print(f"[OK] Degradation: {degradation_pct:.1f}%  |  Gate: {'PASS' if gate_passed else 'REJECT'}")
    print(f"[OK] Validation passed: {result.validation_passed}")
    print(f"[OK] Sharpe: {result.sharpe_ratio:.3f}  |  Trades: {result.total_trades}")
    if result.rejection_reasons:
        print(f"[!] Rejection reasons: {result.rejection_reasons}")
    print(f"[OK] Commit: {payload['git_commit'][:12]}")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()