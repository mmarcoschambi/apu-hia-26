"""Tests del barrido Optuna V/T/Z con objetivo Sortino + penalización (slice 3B).

Contrato bajo test (valores esperados calculados a mano):
- ``sortino_with_drawdown_penalty``: objetivo documentado del proposal
  ("Sharpe o Sortino penalizando drawdowns profundos"):
      downside_dev = sqrt(mean(min(r_i, 0)^2))           (target 0)
      sortino      = mean(r)/downside_dev                si downside_dev > 0
                   = ZERO_DOWNSIDE_SORTINO_SCORE         si downside_dev==0 y mean>0
                   = 0.0                                 si downside_dev==0 y mean<=0
      mdd_r        = máx(running_max(equity) - equity_t)  en unidades R
      penalty      = DRAWDOWN_PENALTY_WEIGHT * max(0, mdd_r - DEEP_DRAWDOWN_R_THRESHOLD)^2
      value        = sortino - penalty
- ``evaluate_configuration``: cablea el pipeline real (volume bars ->
  Signal A; time bars -> Vol Buzz Z + AVWAP -> Signal B; unión A|B llevada a
  la grilla de ejecución as-of backward; kernel Numba de ``numba_kernels``).
- ``run_sweep``: estudio Optuna in-memory, sampler TPESampler(seed),
  pruner MedianPruner, dirección MAXIMIZE y espacio V/T/Z exacto del issue.
"""

from __future__ import annotations

from datetime import datetime, timedelta

import numpy as np
import optuna
import polars as pl
import pytest

from src.microstructure.sweep import (
    DEEP_DRAWDOWN_R_THRESHOLD,
    EMPTY_TRADES_OBJECTIVE,
    SWEEP_RANDOM_SEED,
    SWEEP_SMOKE_N_TRIALS,
    TIME_BAR_MINUTE_CHOICES,
    VOLUME_BAR_CHOICES,
    ZERO_DOWNSIDE_SORTINO_SCORE,
    ConfigurationEvaluation,
    evaluate_configuration,
    run_sweep,
    sortino_with_drawdown_penalty,
)

# Fixture de ticks sintéticos: 25 días RTH, 13 ticks/día cada 30 minutos.
SWEEP_TEST_DAYS = 25
RAMP_START_DAY_INDEX = 20
TICKS_PER_DAY = 13
FLAT_PRICE = 100.0
FLAT_VOLUME_EVEN = 3000.0
FLAT_VOLUME_ODD = 5000.0
RAMP_VOLUME = 12000.0
RAMP_STEP_PER_TICK = 0.5


# ---------------------------------------------------------------------------
# Helpers de fixtures sintéticas deterministas
# ---------------------------------------------------------------------------


def _sweep_ticks() -> pl.DataFrame:
    """Ticks deterministas con régimen plano (días 1..20) y rampa (21..25).

    Días planos: volumen alternante 3000/5000 por minuto-del-día -> media
    previa 4000 y std poblacional 1000 EXACTAS. Días de rampa: volumen
    12000 -> Vol Buzz Z = (12000 - 4000) / 1000 = 8.0 (> cualquier umbral
    del espacio 1..3) y precios estrictamente crecientes -> señales A y B.
    """
    rows: list[tuple[datetime, float, float]] = []
    base = datetime(2024, 1, 1, 9, 30)
    for day in range(SWEEP_TEST_DAYS):
        for slot in range(TICKS_PER_DAY):
            stamp = base + timedelta(days=day, minutes=30 * slot)
            if day >= RAMP_START_DAY_INDEX:
                ticks_since_ramp = (day - RAMP_START_DAY_INDEX) * TICKS_PER_DAY + slot
                rows.append(
                    (stamp, FLAT_PRICE + RAMP_STEP_PER_TICK * ticks_since_ramp, RAMP_VOLUME)
                )
            else:
                volume = FLAT_VOLUME_EVEN if slot % 2 == 0 else FLAT_VOLUME_ODD
                rows.append((stamp, FLAT_PRICE, volume))
    return pl.DataFrame(rows, schema=["Timestamp", "Price", "Volume"], orient="row")


def _empty_ticks() -> pl.DataFrame:
    """Frame vacío con el esquema obligatorio del contrato de ingesta."""
    return pl.DataFrame(
        schema={
            "Timestamp": pl.Datetime("us"),
            "Price": pl.Float64,
            "Volume": pl.Float64,
        }
    )


# ---------------------------------------------------------------------------
# Objetivo Sortino + penalización de drawdowns profundos (matemática a mano)
# ---------------------------------------------------------------------------


def test_objective_normal_case_hand_math() -> None:
    """Sortino clásico sin drawdown profundo: penalty nula y value = sortino."""
    breakdown = sortino_with_drawdown_penalty(
        per_trade_returns_r=np.array([1.0, 2.0, -0.5]),
        equity_curve_r=np.array([1.0, 3.0, 2.5]),
    )
    expected_sortino = (2.5 / 3.0) / np.sqrt(0.25 / 3.0)
    assert breakdown.sortino == pytest.approx(expected_sortino)
    assert breakdown.max_drawdown_r == pytest.approx(0.5)
    assert breakdown.drawdown_penalty == pytest.approx(0.0)
    assert breakdown.objective_value == pytest.approx(expected_sortino)


def test_deep_drawdown_penalty_is_quadratic_over_threshold() -> None:
    """MDD 8R supera el umbral 5R por 3R: penalty = peso * 3^2 = 0.45."""
    breakdown = sortino_with_drawdown_penalty(
        per_trade_returns_r=np.array([10.0, -8.0]),
        equity_curve_r=np.array([10.0, 2.0]),
    )
    expected_sortino = 1.0 / np.sqrt(64.0 / 2.0)
    expected_penalty = 0.05 * (8.0 - DEEP_DRAWDOWN_R_THRESHOLD) ** 2
    assert breakdown.sortino == pytest.approx(expected_sortino)
    assert breakdown.max_drawdown_r == pytest.approx(8.0)
    assert breakdown.drawdown_penalty == pytest.approx(expected_penalty)
    assert breakdown.objective_value == pytest.approx(expected_sortino - expected_penalty)


def test_zero_downside_with_positive_mean_uses_documented_score() -> None:
    """Sin devoluciones negativas y media positiva -> score techo documentado."""
    breakdown = sortino_with_drawdown_penalty(
        per_trade_returns_r=np.array([1.0, 2.0]),
        equity_curve_r=np.array([1.0, 3.0]),
    )
    assert breakdown.sortino == ZERO_DOWNSIDE_SORTINO_SCORE
    assert breakdown.drawdown_penalty == pytest.approx(0.0)
    assert breakdown.objective_value == ZERO_DOWNSIDE_SORTINO_SCORE


def test_empty_objective_inputs_raise_value_error() -> None:
    """El objetivo exige al menos un retorno; el caso vacío lo maneja evaluate."""
    with pytest.raises(ValueError, match="al menos un retorno"):
        sortino_with_drawdown_penalty(np.array([]), np.array([0.0]))


def test_mismatched_objective_lengths_raise_value_error() -> None:
    """Retornos y curva de equity deben tener longitudes compatibles."""
    with pytest.raises(ValueError, match="misma longitud"):
        sortino_with_drawdown_penalty(np.array([1.0]), np.array([1.0, 2.0]))


# ---------------------------------------------------------------------------
# evaluate_configuration: cableado completo del pipeline A|B -> kernel
# ---------------------------------------------------------------------------


def test_evaluate_configuration_runs_pipeline_and_produces_trades() -> None:
    """La rampa engineered dispara señales y el kernel cierra operaciones."""
    ticks = _sweep_ticks()
    evaluation = evaluate_configuration(
        ticks, volume_threshold=10_000.0, bar_minutes=5, threshold_z=2.0
    )

    assert isinstance(evaluation, ConfigurationEvaluation)
    assert evaluation.n_signals >= 1
    assert evaluation.n_trades >= 1
    assert np.isfinite(evaluation.total_pnl_r)
    assert np.isfinite(evaluation.objective_value)
    assert evaluation.sortino is not None

    # Determinismo puro del pipeline (sin RNG dentro de la evaluación).
    repeat = evaluate_configuration(
        ticks, volume_threshold=10_000.0, bar_minutes=5, threshold_z=2.0
    )
    assert repeat.n_signals == evaluation.n_signals
    assert repeat.n_trades == evaluation.n_trades
    assert repeat.total_pnl_r == pytest.approx(evaluation.total_pnl_r)
    assert repeat.objective_value == pytest.approx(evaluation.objective_value)


def test_evaluate_configuration_on_empty_ticks_degrades_gracefully() -> None:
    """Ticks vacíos -> evaluación vacía documentada, nunca excepción."""
    evaluation = evaluate_configuration(
        _empty_ticks(), volume_threshold=10_000.0, bar_minutes=5, threshold_z=2.0
    )
    assert evaluation.n_signals == 0
    assert evaluation.n_trades == 0
    assert evaluation.total_pnl_r == pytest.approx(0.0)
    assert evaluation.sortino is None
    assert evaluation.objective_value == EMPTY_TRADES_OBJECTIVE


def test_evaluate_configuration_validates_parameters() -> None:
    """Parámetros fuera de contrato -> ValueError nombrando el parámetro."""
    ticks = _sweep_ticks()
    with pytest.raises(ValueError, match="volume_threshold"):
        evaluate_configuration(ticks, volume_threshold=0.0, bar_minutes=5, threshold_z=2.0)
    with pytest.raises(ValueError, match="bar_minutes"):
        evaluate_configuration(ticks, volume_threshold=10_000.0, bar_minutes=0, threshold_z=2.0)
    with pytest.raises(ValueError, match="threshold_z"):
        evaluate_configuration(ticks, volume_threshold=10_000.0, bar_minutes=5, threshold_z=-1.0)


# ---------------------------------------------------------------------------
# run_sweep: mecánica Optuna (espacio, dirección, pruner, seed)
# ---------------------------------------------------------------------------


def test_run_sweep_respects_search_space_and_optuna_configuration() -> None:
    """Smoke corto: params dentro del espacio V/T/Z, MAXIMIZE, MedianPruner."""
    result = run_sweep(_sweep_ticks(), n_trials=SWEEP_SMOKE_N_TRIALS)

    assert result.best_params.keys() == {"V", "T", "Z"}
    assert result.best_params["V"] in VOLUME_BAR_CHOICES
    assert result.best_params["T"] in TIME_BAR_MINUTE_CHOICES
    z_value = result.best_params["Z"]
    grid_slot = round((z_value - 1.0) / 0.25)
    assert 1.0 <= z_value <= 3.0
    assert z_value == pytest.approx(1.0 + grid_slot * 0.25)

    assert result.study.direction == optuna.study.StudyDirection.MAXIMIZE
    assert isinstance(result.study.pruner, optuna.pruners.MedianPruner)
    assert isinstance(result.study.sampler, optuna.samplers.TPESampler)
    assert len(result.study.trials) == SWEEP_SMOKE_N_TRIALS
    assert result.best_value is not None


def test_run_sweep_trial_values_stay_within_documented_bounds() -> None:
    """CADA trial respeta el espacio de búsqueda (no solo el mejor)."""
    result = run_sweep(_sweep_ticks(), n_trials=SWEEP_SMOKE_N_TRIALS + 2)

    assert len(result.study.trials) == SWEEP_SMOKE_N_TRIALS + 2
    for trial in result.study.trials:
        assert trial.params["V"] in VOLUME_BAR_CHOICES
        assert trial.params["T"] in TIME_BAR_MINUTE_CHOICES
        assert 1.0 <= trial.params["Z"] <= 3.0


def test_run_sweep_is_deterministic_with_fixed_seed() -> None:
    """Misma semilla -> mismo best_params y MISMA secuencia de valores."""
    first = run_sweep(_sweep_ticks(), n_trials=SWEEP_SMOKE_N_TRIALS, seed=SWEEP_RANDOM_SEED)
    second = run_sweep(_sweep_ticks(), n_trials=SWEEP_SMOKE_N_TRIALS, seed=SWEEP_RANDOM_SEED)

    assert first.best_params == second.best_params
    assert first.best_value == second.best_value
    values_first = [trial.value for trial in first.study.trials]
    values_second = [trial.value for trial in second.study.trials]
    assert values_first == values_second


# ---------------------------------------------------------------------------
# Constantes del espacio de búsqueda fijadas por spec (proposal secciones 2-4)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("constant_name", "expected"),
    [
        ("VOLUME_BAR_CHOICES", (10_000.0, 25_000.0, 50_000.0)),
        ("TIME_BAR_MINUTE_CHOICES", (1, 3, 5)),
        ("Z_THRESHOLD_LOW", 1.0),
        ("Z_THRESHOLD_HIGH", 3.0),
        ("Z_THRESHOLD_STEP", 0.25),
        ("SWEEP_DEFAULT_N_TRIALS", 50),
        ("SWEEP_RANDOM_SEED", 42),
        ("DEEP_DRAWDOWN_R_THRESHOLD", 5.0),
        ("DRAWDOWN_PENALTY_WEIGHT", 0.05),
        ("ZERO_DOWNSIDE_SORTINO_SCORE", 100.0),
        ("EMPTY_TRADES_OBJECTIVE", -100.0),
    ],
)
def test_sweep_constants_match_proposal_spec(constant_name: str, expected: object) -> None:
    """Constantes nombradas del barrido fijadas por test contra el proposal."""
    import src.microstructure.sweep as sweep_module

    assert getattr(sweep_module, constant_name) == expected
