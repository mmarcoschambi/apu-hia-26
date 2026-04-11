"""
src/optimization/s4_objective.py
================================
Función objetivo compuesta para Optuna S4.

Combina Sharpe con penalizaciones por:
- Max Drawdown > 25%
- Win rate < 40%
- Profit Factor < 1.2

Hard reject:
- Trades < 30
- PF < 1.0
"""

import logging
from typing import Any, Dict, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)


# === CONSTANTS ===

MIN_TRADES = 30
MIN_PF_HARD = 1.0
MIN_PF_SOFT = 1.2
MAX_MDD_SOFT = 0.25
MIN_WIN_RATE = 0.40

# Penalization multipliers
MDD_PENALTY = 0.5
WIN_RATE_PENALTY = 0.7
PF_PENALTY = 0.6


def compute_score_composed(
    trades: int,
    sharpe: float,
    mdd: float,
    win_rate: float,
    profit_factor: float,
    is_sharpe: Optional[float] = None,
    val_sharpe: Optional[float] = None,
) -> Tuple[float, Dict[str, Any]]:
    """
    Computa score compuesto para Optuna.

    Args:
        trades: Número de trades
        sharpe: Sharpe ratio (can be OOS or combined)
        mdd: Max drawdown (decimal, e.g., 0.20 = 20%)
        win_rate: Win rate (decimal, e.g., 0.45 = 45%)
        profit_factor: Profit factor
        is_sharpe: Sharpe in-sample (optional, for stability bonus)
        val_sharpe: Sharpe validation (optional, for degradation check)

    Returns:
        (score, metadata) donde metadata incluye break_reason y componentes
    """
    meta = {
        "trades": trades,
        "sharpe_raw": sharpe,
        "mdd": mdd,
        "win_rate": win_rate,
        "pf": profit_factor,
    }

    # Hard reject: trades insufficient
    if trades < MIN_TRADES:
        meta["break_reason"] = f"TRADES_TOO_LOW:{trades}"
        return -999.0, meta

    # Hard reject: PF too low
    if profit_factor < MIN_PF_HARD:
        meta["break_reason"] = f"PF_HARD_REJECT:{profit_factor:.2f}"
        return -999.0, meta

    # Base score
    score = sharpe

    # Penalization: MDD > 25%
    if mdd > MAX_MDD_SOFT:
        score *= MDD_PENALTY
        meta["mdd_penalty"] = True

    # Penalization: win_rate < 40%
    if win_rate < MIN_WIN_RATE:
        score *= WIN_RATE_PENALTY
        meta["win_rate_penalty"] = True

    # Penalization: PF < 1.2 (soft)
    if profit_factor < MIN_PF_SOFT:
        score *= PF_PENALTY
        meta["pf_penalty"] = True

    # Optional stability bonus (IS -> Val degradation)
    if is_sharpe is not None and val_sharpe is not None and is_sharpe > 0:
        degradation = (is_sharpe - val_sharpe) / is_sharpe
        if degradation <= 0.20:
            # Bonus: apply minor boost for stable configs
            score *= 1.05
            meta["stability_bonus"] = True
        elif degradation > 0.50:
            # Heavy penalty for unstable configs
            score *= 0.7
            meta["instability_penalty"] = True
        meta["degradation_pct"] = round(degradation * 100, 1)

    meta["break_reason"] = "PASSED"
    meta["score_raw"] = round(score, 4)

    return round(score, 4), meta


def reject_candidate(metrics: Dict[str, Any], mode: str = "OOS") -> Tuple[bool, str]:
    """
    Checkea si un candidato debe ser rechazado por métricas límite.

    Args:
        metrics: Dict con keys trades, pf, calmar, mdd, win_rate, etc.
        mode: "IS", "VAL", o "OOS" para logs

    Returns:
        (rejected: bool, reason: str)
    """
    trades = metrics.get("trades", 0)
    pf = metrics.get("profit_factor", 0)
    calmar = metrics.get("calmar", 0)
    mdd = metrics.get("max_drawdown_90d", 0) / 100  # convert to decimal
    win_rate = metrics.get("win_rate", 0) / 100

    # Trade count
    if trades < MIN_TRADES:
        return True, f"TRADES_TOO_LOW:{trades}"

    # Profit Factor
    if pf < MIN_PF_HARD:
        return True, f"PF_HARD_REJECT:{pf:.2f}"

    # Max DD (soft, para OOS y VAL)
    if mode in ["OOS", "VAL"] and mdd > MAX_MDD_SOFT:
        return True, f"MDD_EXCEEDS:{mdd * 100:.1f}%"

    # Win rate (soft)
    if mode in ["OOS", "VAL"] and win_rate < MIN_WIN_RATE:
        return True, f"WIN_RATE_LOW:{win_rate * 100:.1f}%"

    return False, "PASSED"


def get_hard_limits() -> Dict[str, Any]:
    """Retorna los límites hard para documentación."""
    return {
        "min_trades": MIN_TRADES,
        "min_pf_hard": MIN_PF_HARD,
        "min_pf_soft": MIN_PF_SOFT,
        "max_mdd_soft": MAX_MDD_SOFT,
        "min_win_rate": MIN_WIN_RATE,
    }


# === CLI TEST ===

if __name__ == "__main__":
    # Test cases
    print("=== Testing s4_objective ===")

    # Case 1: Good candidate
    score1, meta1 = compute_score_composed(
        trades=150, sharpe=1.8, mdd=0.15, win_rate=0.55, profit_factor=2.2
    )
    print(f"Good candidate: score={score1}, reason={meta1['break_reason']}")

    # Case 2: High MDD penalty
    score2, meta2 = compute_score_composed(
        trades=150, sharpe=2.0, mdd=0.35, win_rate=0.55, profit_factor=2.2
    )
    print(
        f"High MDD: score={score2}, reason={meta2['break_reason']}, penalty={meta2.get('mdd_penalty')}"
    )

    # Case 3: Hard reject - low PF
    score3, meta3 = compute_score_composed(
        trades=150, sharpe=1.5, mdd=0.10, win_rate=0.45, profit_factor=0.8
    )
    print(f"Low PF: score={score3}, reason={meta3['break_reason']}")

    # Case 4: Hard reject - low trades
    score4, meta4 = compute_score_composed(
        trades=20, sharpe=1.5, mdd=0.10, win_rate=0.45, profit_factor=1.5
    )
    print(f"Low trades: score={score4}, reason={meta4['break_reason']}")

    # Case 5: With stability bonus
    score5, meta5 = compute_score_composed(
        trades=150,
        sharpe=1.5,
        mdd=0.12,
        win_rate=0.50,
        profit_factor=1.8,
        is_sharpe=1.6,
        val_sharpe=1.4,
    )
    print(
        f"Stable: score={score5}, reason={meta5['break_reason']}, bonus={meta5.get('stability_bonus')}"
    )
