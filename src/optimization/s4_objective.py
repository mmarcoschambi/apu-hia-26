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

Steering Calmar/CAGR (opcional):
- Si se provee `calmar`, el score recibe un bonus multiplicativo
  `(1 + CALMAR_BONUS * max(calmar - CALMAR_MIN_REWARD, 0))` que recompensa
  de forma creciente los Calmar positivos y con fuerza los >= 1.0 (umbral
  del gate), sin castigar configuraciones con Calmar bajo.
- Si se provee `cagr` (fracción, ej. 0.25 = 25%), se suma un término
  aditivo menor `CAGR_WEIGHT * max(cagr, 0)` como desempate entre
  configuraciones de Calmar similar.
- Ambos parámetros son opcionales: con `calmar=None` y `cagr=None` el
  comportamiento es idéntico a la versión anterior (backward compatible).
"""

import logging
import math
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

# Calmar / CAGR steering
CALMAR_MIN_REWARD = 0.0  # Calmar por debajo de este umbral no recibe bonus
CALMAR_BONUS = 0.5  # score *= (1 + CALMAR_BONUS * max(calmar - CALMAR_MIN_REWARD, 0))
CAGR_WEIGHT = 0.25  # score += CAGR_WEIGHT * max(cagr, 0), cagr como fracción


def compute_score_composed(
    trades: int,
    sharpe: float,
    mdd: float,
    win_rate: float,
    profit_factor: float,
    is_sharpe: Optional[float] = None,
    val_sharpe: Optional[float] = None,
    calmar: Optional[float] = None,
    cagr: Optional[float] = None,
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
        calmar: Calmar ratio (optional). Si se provee, aplica bonus
            multiplicativo creciente: score *= (1 + CALMAR_BONUS * max(calmar - CALMAR_MIN_REWARD, 0))
        cagr: CAGR como fracción (optional, ej. 0.25 = 25%). Si se provee,
            suma término aditivo menor: score += CAGR_WEIGHT * max(cagr, 0)

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

    # Steering: bonus multiplicativo por Calmar positivo
    if calmar is not None and not math.isnan(calmar) and math.isfinite(calmar):
        calmar_excess = max(calmar - CALMAR_MIN_REWARD, 0.0)
        if calmar_excess > 0:
            multiplier = 1.0 + CALMAR_BONUS * calmar_excess
            if score >= 0:
                score *= multiplier
            else:
                # Si el score base es negativo, multiplicar por > 1 lo haría aún más negativo (castigo).
                # Dividir lo acerca a 0, lo cual es matemáticamente un bonus o atenuación.
                score /= multiplier
            meta["calmar_bonus"] = True
        meta["calmar"] = round(calmar, 4)

    # Steering: término aditivo menor por CAGR (fracción)
    if cagr is not None and not math.isnan(cagr) and math.isfinite(cagr):
        score += CAGR_WEIGHT * max(cagr, 0.0)
        meta["cagr_term_applied"] = True
        meta["cagr"] = round(cagr, 4)

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

    # Case 6: Steering Calmar - mismo Sharpe, mayor Calmar -> mayor score
    score6a, meta6a = compute_score_composed(
        trades=150, sharpe=1.5, mdd=0.15, win_rate=0.55, profit_factor=2.0, calmar=0.4
    )
    score6b, meta6b = compute_score_composed(
        trades=150, sharpe=1.5, mdd=0.15, win_rate=0.55, profit_factor=2.0, calmar=1.2
    )
    print(
        f"Calmar 0.4: score={score6a} | Calmar 1.2: score={score6b} | steering={score6b > score6a}"
    )

    # Case 7: Backward compat - calmar=None identico al comportamiento base
    score7a, meta7a = compute_score_composed(
        trades=150, sharpe=1.5, mdd=0.15, win_rate=0.55, profit_factor=2.0
    )
    score7b, meta7b = compute_score_composed(
        trades=150, sharpe=1.5, mdd=0.15, win_rate=0.55, profit_factor=2.0, calmar=None
    )
    print(f"Backward compat: score7a={score7a}, score7b={score7b}, equal={score7a == score7b}")

    # Case 8: Steering CAGR - termino aditivo aplica
    score8a, meta8a = compute_score_composed(
        trades=150, sharpe=1.5, mdd=0.15, win_rate=0.55, profit_factor=2.0, cagr=0.20
    )
    score8b, meta8b = compute_score_composed(
        trades=150, sharpe=1.5, mdd=0.15, win_rate=0.55, profit_factor=2.0, cagr=0.40
    )
    print(
        f"CAGR 0.20: score={score8a} | CAGR 0.40: score={score8b} | "
        f"cagr_term={meta8b.get('cagr_term_applied')} | steering={score8b > score8a}"
    )
