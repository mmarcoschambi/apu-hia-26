"""
src/integration/hybrid_gate.py
Promotion gate para sistema A/B/A+B.

Evalúa métricas de OOS para decidir PROMOTE / HOLD / REJECT.
Usa umbrales configurables por modo.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal, Optional


PromotionDecision = Literal["PROMOTE", "HOLD", "REJECT"]


@dataclass
class HybridGateThresholds:
    min_trades: int = 15
    min_profit_factor: float = 1.20
    min_win_rate: float = 0.35
    min_sharpe: float = 0.60
    max_drawdown: float = 0.18
    min_expectancy: float = 0.0
    min_oos_folds: int = 2
    min_oos_verdicts: int = 1


@dataclass
class FoldMetrics:
    oos_profit_factor: float
    oos_sharpe: float
    oos_win_rate: float
    oos_max_drawdown: float
    oos_trades: int
    oos_expectancy: float
    is_profit_factor: float
    is_sharpe: float
    gate_verdict: str


@dataclass
class HybridPromotionResult:
    mode: str
    decision: PromotionDecision
    reasons: list = field(default_factory=list)
    fold_details: list = field(default_factory=list)
    aggregate_oos_pf: float = 0.0
    aggregate_oos_sharpe: float = 0.0
    aggregate_oos_trades: int = 0


def default_thresholds() -> HybridGateThresholds:
    return HybridGateThresholds()


def load_thresholds(config_path: Optional[str] = None) -> HybridGateThresholds:
    if config_path and Path(config_path).exists():
        with open(config_path, "r") as f:
            data = json.load(f)
        return HybridGateThresholds(
            min_trades=data.get("min_trades", 15),
            min_profit_factor=data.get("min_profit_factor", 1.20),
            min_win_rate=data.get("min_win_rate", 0.35),
            min_sharpe=data.get("min_sharpe", 0.60),
            max_drawdown=data.get("max_drawdown", 0.18),
            min_expectancy=data.get("min_expectancy", 0.0),
            min_oos_folds=data.get("min_oos_folds", 2),
            min_oos_verdicts=data.get("min_oos_verdicts", 1),
        )
    return HybridGateThresholds()


def evaluate_fold(
    fold: FoldMetrics, thresholds: HybridGateThresholds
) -> tuple[PromotionDecision, list[str]]:
    reasons = []
    verdict = "REJECT"

    if fold.oos_trades < thresholds.min_trades:
        reasons.append(
            f"insufficient_oos_trades:{fold.oos_trades}<{thresholds.min_trades}"
        )
    if fold.oos_profit_factor < thresholds.min_profit_factor:
        reasons.append(
            f"oos_pf:{fold.oos_profit_factor:.3f}<{thresholds.min_profit_factor}"
        )
    if fold.oos_win_rate < thresholds.min_win_rate:
        reasons.append(
            f"oos_win_rate:{fold.oos_win_rate:.3f}<{thresholds.min_win_rate}"
        )
    if fold.oos_sharpe < thresholds.min_sharpe:
        reasons.append(f"oos_sharpe:{fold.oos_sharpe:.3f}<{thresholds.min_sharpe}")
    if fold.oos_max_drawdown > thresholds.max_drawdown:
        reasons.append(f"oos_dd:{fold.oos_max_drawdown:.4f}>{thresholds.max_drawdown}")
    if fold.oos_expectancy <= thresholds.min_expectancy:
        reasons.append(
            f"oos_expectancy:{fold.oos_expectancy:.4f}<={thresholds.min_expectancy}"
        )

    if not reasons:
        verdict = "PROMOTE"
    elif fold.oos_trades < thresholds.min_trades:
        verdict = "HOLD"
    else:
        verdict = "REJECT"

    return verdict, reasons


def evaluate_hybrid_mode(
    mode: str,
    fold_results: list[dict],
    thresholds: HybridGateThresholds | None = None,
) -> HybridPromotionResult:
    """
    Evalúa todos los folds de un modo y decide PROMOTE/HOLD/REJECT.

    Reglas de decisión:
      - PROMOTE: >= min_oos_verdicts folds PROMOTE, total trades >= min_trades * folds
      - HOLD:    ninguno PROMOTE pero >= 1 fold tiene trades suficientes
      - REJECT:  todos los folds REJECT o muy pocos trades
    """
    if thresholds is None:
        thresholds = HybridGateThresholds()

    fold_details = []
    promote_count = 0
    hold_count = 0
    reject_count = 0
    total_oos_trades = 0
    total_oos_pf_sum = 0.0
    total_oos_sharpe_sum = 0.0
    valid_pf_count = 0
    valid_sharpe_count = 0

    for fr in fold_results:
        oos_m = fr.get("oos_metrics", {})
        is_m = fr.get("is_metrics", {})

        fm = FoldMetrics(
            oos_profit_factor=oos_m.get("profit_factor", 0.0),
            oos_sharpe=oos_m.get("sharpe", 0.0),
            oos_win_rate=oos_m.get("win_rate", 0.0),
            oos_max_drawdown=oos_m.get("max_drawdown", 1.0),
            oos_trades=oos_m.get("trades", 0),
            oos_expectancy=oos_m.get("expectancy", 0.0),
            is_profit_factor=is_m.get("profit_factor", 0.0),
            is_sharpe=is_m.get("sharpe", 0.0),
            gate_verdict=fr.get("gate", {}).get("verdict", "HOLD"),
        )

        verdict, reasons = evaluate_fold(fm, thresholds)
        fold_details.append(
            {"fold": fr.get("fold"), "verdict": verdict, "reasons": reasons}
        )

        if verdict == "PROMOTE":
            promote_count += 1
        elif verdict == "HOLD":
            hold_count += 1
        else:
            reject_count += 1

        total_oos_trades += oos_m.get("trades", 0)
        if oos_m.get("profit_factor", 0) > 0:
            total_oos_pf_sum += oos_m.get("profit_factor", 0)
            valid_pf_count += 1
        if oos_m.get("sharpe", 0) != 0:
            total_oos_sharpe_sum += oos_m.get("sharpe", 0)
            valid_sharpe_count += 1

    avg_oos_pf = total_oos_pf_sum / valid_pf_count if valid_pf_count > 0 else 0.0
    avg_oos_sharpe = (
        total_oos_sharpe_sum / valid_sharpe_count if valid_sharpe_count > 0 else 0.0
    )

    reasons_out: list[str] = []
    if promote_count >= thresholds.min_oos_verdicts:
        decision: PromotionDecision = "PROMOTE"
        reasons_out.append(
            f"{promote_count} folds PROMOTE (>= {thresholds.min_oos_verdicts} required)"
        )
    elif hold_count > 0 and reject_count == 0:
        decision = "HOLD"
        reasons_out.append(f"{hold_count} folds HOLD, {reject_count} REJECT")
    elif promote_count > 0:
        decision = "HOLD"
        reasons_out.append(
            f"only {promote_count} folds PROMOTE (< {thresholds.min_oos_verdicts})"
        )
    else:
        decision = "REJECT"
        reasons_out.append(f"{reject_count} folds REJECT, {promote_count} PROMOTE")

    if total_oos_trades < thresholds.min_trades * len(fold_results):
        reasons_out.append(
            f"total_oos_trades:{total_oos_trades}<{thresholds.min_trades * len(fold_results)}"
        )

    return HybridPromotionResult(
        mode=mode,
        decision=decision,
        reasons=reasons_out,
        fold_details=fold_details,
        aggregate_oos_pf=round(avg_oos_pf, 3),
        aggregate_oos_sharpe=round(avg_oos_sharpe, 3),
        aggregate_oos_trades=total_oos_trades,
    )


def evaluate_all_modes(
    walkforward_report: dict,
    thresholds: HybridGateThresholds | None = None,
) -> list[HybridPromotionResult]:
    results = []
    for res in walkforward_report.get("results", []):
        result = evaluate_hybrid_mode(res["mode"], res.get("folds", []), thresholds)
        results.append(result)
    return results


# Constante exportable para uso en otros módulos sin instanciar HybridGateThresholds
DEFAULT_MIN_OOS_TRADES: int = default_thresholds().min_trades
