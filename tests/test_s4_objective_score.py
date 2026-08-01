"""
tests/test_s4_objective_score.py
================================
Tests de la función objetivo compuesta S4 y su steering Calmar/CAGR.
"""

import pytest

from src.optimization.s4_objective import (
    CAGR_WEIGHT,
    CALMAR_BONUS,
    MAX_MDD_SOFT,
    MIN_PF_HARD,
    MIN_TRADES,
    compute_score_composed,
)


def _base_score(calmar=None, cagr=None, **overrides):
    """Score compuesto sobre métricas de referencia con overrides opcionales."""
    kwargs = {
        "trades": 150,
        "sharpe": 1.5,
        "mdd": 0.15,
        "win_rate": 0.55,
        "profit_factor": 2.0,
    }
    kwargs.update(overrides)
    return compute_score_composed(
        trades=kwargs["trades"],
        sharpe=kwargs["sharpe"],
        mdd=kwargs["mdd"],
        win_rate=kwargs["win_rate"],
        profit_factor=kwargs["profit_factor"],
        calmar=calmar,
        cagr=cagr,
    )


def test_same_metrics_higher_calmar_higher_score():
    """Con métricas idénticas, mayor Calmar implica mayor score."""
    score_low, _ = _base_score(calmar=0.4)
    score_mid, _ = _base_score(calmar=0.6)
    score_high, _ = _base_score(calmar=1.2)

    assert score_low < score_mid < score_high
    assert score_high > score_low


def test_calmar_none_matches_baseline():
    """calmar=None conserva el comportamiento base (sin steering)."""
    score_without, _ = _base_score(calmar=None, cagr=None)
    score_with, _ = _base_score(calmar=0.0, cagr=None)

    expected = round(1.5, 4)
    assert score_without == expected
    assert score_with == expected


def test_calmar_bonus_is_multiplicative_and_tunable():
    """El bonus Calmar es multiplicativo y recompensa fuerte cerca de 1.0."""
    score_base, _ = _base_score(calmar=None)
    score_at_gate, _ = _base_score(calmar=1.0)

    expected_mult = 1.0 + CALMAR_BONUS
    assert score_at_gate == pytest.approx(score_base * expected_mult, abs=1e-3)


def test_negative_calmar_not_punished():
    """Calmar negativo no resta al score (solo se premia lo positivo)."""
    score_zero, _ = _base_score(calmar=0.0)
    score_neg, _ = _base_score(calmar=-0.5)

    assert score_zero == score_neg


def test_cagr_term_additive_and_normalized():
    """El término CAGR es aditivo y se normaliza como fracción."""
    score_no_cagr, _ = _base_score(cagr=None)
    score_cagr, _ = _base_score(cagr=0.20)

    assert score_cagr == pytest.approx(score_no_cagr + CAGR_WEIGHT * 0.20, abs=1e-3)


def test_cagr_with_calmar_combine():
    """Calmar y CAGR se combinan: multiplicativo + aditivo."""
    score_no, meta_no = _base_score(calmar=None, cagr=None)
    score_combo, meta_combo = _base_score(calmar=1.0, cagr=0.20)

    expected = score_no * (1.0 + CALMAR_BONUS) + CAGR_WEIGHT * 0.20
    assert score_combo == pytest.approx(expected, abs=1e-3)
    assert meta_combo["calmar_bonus"] is True
    assert meta_combo["cagr_term_applied"] is True


def test_meta_contains_calmar_and_cagr_when_provided():
    """Metadata expone calmar, cagr y las flags de componente aplicado."""
    score, meta = _base_score(calmar=1.2, cagr=0.35)

    assert meta["calmar"] == pytest.approx(1.2)
    assert meta["cagr"] == pytest.approx(0.35)
    assert meta["calmar_bonus"] is True
    assert meta["cagr_term_applied"] is True


def test_meta_omits_calmar_cagr_when_not_provided():
    """Sin calmar/cagr, metadata no incluye flags de steering."""
    score, meta = _base_score(calmar=None, cagr=None)

    assert "calmar_bonus" not in meta
    assert "cagr_term_applied" not in meta


def test_hard_reject_low_trades():
    """Trades < MIN_TRADES sigue rechazando de forma dura."""
    score, meta = _base_score(trades=MIN_TRADES - 1)

    assert score == -999.0
    assert meta["break_reason"].startswith("TRADES_TOO_LOW")


def test_hard_reject_low_pf():
    """PF < MIN_PF_HARD sigue rechazando de forma dura."""
    score, meta = _base_score(profit_factor=MIN_PF_HARD - 0.2)

    assert score == -999.0
    assert meta["break_reason"].startswith("PF_HARD_REJECT")


def test_hard_reject_applies_before_steering():
    """El steering no rescata configuraciones que fallan hard reject."""
    score, meta = _base_score(trades=20, calmar=1.2, cagr=0.30)

    assert score == -999.0
    assert "calmar_bonus" not in meta
    assert "cagr_term_applied" not in meta


def test_mdd_penalty_intact():
    """Penalización por MDD > MAX_MDD_SOFT permanece intacta."""
    score_base, _ = _base_score(calmar=None)
    score_mdd, meta_mdd = _base_score(mdd=MAX_MDD_SOFT + 0.10, calmar=None)

    assert meta_mdd["mdd_penalty"] is True
    assert score_mdd == pytest.approx(score_base * 0.5, abs=1e-3)
