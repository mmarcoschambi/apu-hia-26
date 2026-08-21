"""Barrido Optuna V/T/Z con objetivo Sortino + penalización de drawdowns (Issue #69).

Propósito
---------
Cuarta pieza del subsistema de microestructura: optimiza los hiperparámetros
de la sección 4 del proposal — umbral de volumen V, ancho temporal T y umbral
Z del Vol Buzz — evaluando cada candidato con el pipeline REAL (volume bars +
Signal A; time bars + Vol Buzz + AVWAP + Signal B) y el kernel Numba de
``numba_kernels``. Los runs a escala real quedan fuera del alcance del CI:
el smoke del suite usa pocos trials sobre datos sintéticos.

Decisiones documentadas
-----------------------
- Espacio de búsqueda exacto del issue: V ∈ {10k, 25k, 50k}, T ∈ {1m, 3m,
  5m} (categóricas) y Z continuo en [1.0, 3.0] con paso 0.25 (grilla
  discreta generada por Optuna).
- Objetivo ("Sharpe o Sortino penalizando drawdowns profundos"): Sortino por
  operación en unidades R con downside deviation contra target 0, MENOS una
  penalización CUADRÁTICA del exceso de drawdown máximo sobre el umbral:
      downside = sqrt(mean(min(r_i, 0)^2))
      sortino  = mean(r)/downside            si downside > 0
               = ZERO_DOWNSIDE_SORTINO_SCORE si downside == 0 y mean(r) > 0
               = 0.0                         si downside == 0 y mean(r) <= 0
      mdd_r    = máx(running_max(equity_por_operación) - equity)
      penalty  = DRAWDOWN_PENALTY_WEIGHT * max(0, mdd_r - DEEP_DRAWDOWN_R_THRESHOLD)^2
      value    = sortino - penalty   (dirección MAXIMIZE)
- Curva de equity para el MDD: acumulado POR OPERACIÓN de los pnl_r (misma
  longitud que los retornos; la curva por barra vive en el BacktestResult).
- Sin trades en un candidato -> valor piso EMPTY_TRADES_OBJECTIVE (peor que
  cualquier configuración con operaciones: el sampler aprende a evitarla).
- Grilla de ejecución: las time bars del Pipeline B. La Signal A se traslada
  a esa grilla AS-OF BACKWARD por ``end_timestamp`` (última barra de volumen
  completada al cierre de cada vela de ejecución) y la señal combinada es la
  UNIÓN A|B. El gating fino por probabilidad pertenece al modelo híbrido;
  el motor mide el techo de la estrategia cruda.
- Optuna in-memory (``storage=None``), sampler TPESampler con semilla fija
  (reproducible) y pruner MedianPruner según criterio del issue; como el
  objetivo se evalúa una vez por trial (sin reportes intermedios), el pruner
  queda configurado pero sin puntos de corte.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import optuna
import polars as pl

from src.microstructure.feature_engine import DEFAULT_BB_NUM_STD, DEFAULT_BB_PERIOD
from src.microstructure.hybrid_model import DEFAULT_ATR_PERIOD, compute_atr_series
from src.microstructure.numba_kernels import (
    DEFAULT_MAX_HOLD_BARS,
    DEFAULT_SL_R_MULT,
    DEFAULT_STOP_ATR_MULT,
    DEFAULT_TP_EXIT_FRACTION,
    DEFAULT_TP_R_MULT,
    DEFAULT_TRAIL_R_MULT,
    TRADE_PNL_R,
    simulate_trades,
)
from src.microstructure.time_bars import (
    AVWAP_COLUMN,
    VOL_BUZZ_COLUMN,
    build_time_bars,
    compute_avwap,
    compute_vol_buzz_z,
    generate_signal_b,
)
from src.microstructure.volume_bars import (
    REQUIRED_BAR_INPUT_COLUMNS,
    build_volume_bars,
    generate_signal_a,
)

# ---------------------------------------------------------------------------
# Constantes nombradas del espacio de búsqueda y del objetivo
# ---------------------------------------------------------------------------

# Umbrales de volumen candidatos (proposal sección 2).
VOLUME_BAR_CHOICES: tuple[float, ...] = (10_000.0, 25_000.0, 50_000.0)
# Anchos temporales candidatos en minutos (proposal sección 3).
TIME_BAR_MINUTE_CHOICES: tuple[int, ...] = (1, 3, 5)
# Umbral Z continuo sobre grilla de 0.25 entre 1.0 y 3.0.
Z_THRESHOLD_LOW = 1.0
Z_THRESHOLD_HIGH = 3.0
Z_THRESHOLD_STEP = 0.25

# Presupuesto default modesto; los runs reales los lanza el usuario.
SWEEP_DEFAULT_N_TRIALS = 50
# Trials del smoke de tests (< 1 minuto sobre datos sintéticos chicos).
SWEEP_SMOKE_N_TRIALS = 4
# Semilla fija para reproducibilidad del TPESampler.
SWEEP_RANDOM_SEED = 42

# Penalización de drawdowns profundos (unidades R): exceso cuadrático.
DEEP_DRAWDOWN_R_THRESHOLD = 5.0
DRAWDOWN_PENALTY_WEIGHT = 0.05
# Score documentado cuando no hay devoluciones negativas y la media es > 0.
ZERO_DOWNSIDE_SORTINO_SCORE = 100.0
# Piso para candidatos sin ninguna operación cerrada.
EMPTY_TRADES_OBJECTIVE = -100.0


@dataclass
class ObjectiveBreakdown:
    """Desglose del objetivo: sortino, drawdown máximo, penalty y valor."""

    sortino: float | None
    max_drawdown_r: float
    drawdown_penalty: float
    objective_value: float


@dataclass
class ConfigurationEvaluation:
    """Resultado de evaluar UNA configuración (V, T, Z) end-to-end."""

    n_signals: int
    n_trades: int
    total_pnl_r: float
    sortino: float | None
    max_drawdown_r: float
    drawdown_penalty: float
    objective_value: float


@dataclass
class SweepResult:
    """Salida del barrido: mejor candidato + estudio Optuna completo."""

    best_params: dict[str, Any]
    best_value: float
    study: Any


# ---------------------------------------------------------------------------
# Objetivo Sortino con penalización explícita de drawdowns profundos
# ---------------------------------------------------------------------------


def sortino_with_drawdown_penalty(
    per_trade_returns_r: object, equity_curve_r: object
) -> ObjectiveBreakdown:
    """Calcula Sortino por operación menos la penalización cuadrática de MDD.

    Parámetros:
        per_trade_returns_r: retornos por operación en unidades R (>= 1).
        equity_curve_r: curva de equity POR OPERACIÓN (cumplado de los
            retornos); misma longitud que los retornos.

    Retorno: ObjectiveBreakdown con la fórmula documentada del módulo.
    Lanza ValueError ante entradas vacías o longitudes inconsistentes.
    """
    returns = np.asarray(per_trade_returns_r, dtype=np.float64)
    equity = np.asarray(equity_curve_r, dtype=np.float64)
    if returns.size == 0:
        raise ValueError("El objetivo exige al menos un retorno por operación")
    if equity.size != returns.size:
        raise ValueError(
            "Retornos y curva de equity deben tener la misma longitud; recibidas "
            f"{returns.size} y {equity.size}."
        )

    mean_return = float(returns.mean())
    downside_deviation = float(np.sqrt(np.mean(np.minimum(returns, 0.0) ** 2)))
    if downside_deviation > 0.0:
        sortino = mean_return / downside_deviation
    elif mean_return > 0.0:
        sortino = ZERO_DOWNSIDE_SORTINO_SCORE
    else:
        sortino = 0.0

    running_max = np.maximum.accumulate(equity)
    max_drawdown_r = float(np.max(running_max - equity))
    excess = max(0.0, max_drawdown_r - DEEP_DRAWDOWN_R_THRESHOLD)
    penalty = DRAWDOWN_PENALTY_WEIGHT * excess * excess

    return ObjectiveBreakdown(
        sortino=sortino,
        max_drawdown_r=max_drawdown_r,
        drawdown_penalty=penalty,
        objective_value=sortino - penalty,
    )


# ---------------------------------------------------------------------------
# Evaluación end-to-end de una configuración (pipeline real A|B -> kernel)
# ---------------------------------------------------------------------------


def _combined_execution_mask(
    volume_bars: pl.DataFrame,
    signal_a_series: pl.Series,
    time_bars_enriched: pl.DataFrame,
    signal_b_series: pl.Series,
) -> np.ndarray:
    """Une Signal A (trasladada as-of backward) con Signal B en la grilla B.

    Para cada vela de ejecución se toma la ÚLTIMA barra de volumen completada
    al momento de su cierre (``searchsorted`` right sobre end_timestamp) y su
    flag de Signal A; la combinación final es la unión booleana A | B.
    Todo vectorizado NumPy/Polars: cero bucles interpretados.
    """
    volume_ends = volume_bars["end_timestamp"].to_numpy()
    time_ends = time_bars_enriched["end_timestamp"].to_numpy()
    carried_a = np.zeros(len(time_ends), dtype=bool)
    if len(volume_ends) > 0:
        source_index = np.searchsorted(volume_ends, time_ends, side="right") - 1
        valid = source_index >= 0
        carried_a[valid] = np.asarray(signal_a_series.to_numpy(), dtype=bool)[
            source_index[valid]
        ]
    return carried_a | np.asarray(signal_b_series.to_numpy(), dtype=bool)


def evaluate_configuration(
    ticks: pl.DataFrame,
    *,
    volume_threshold: float,
    bar_minutes: int,
    threshold_z: float,
    bb_period: int = DEFAULT_BB_PERIOD,
    bb_num_std: float = DEFAULT_BB_NUM_STD,
    atr_period: int = DEFAULT_ATR_PERIOD,
    stop_atr_mult: float = DEFAULT_STOP_ATR_MULT,
    tp_r_mult: float = DEFAULT_TP_R_MULT,
    sl_r_mult: float = DEFAULT_SL_R_MULT,
    tp_exit_fraction: float = DEFAULT_TP_EXIT_FRACTION,
    trail_r_mult: float = DEFAULT_TRAIL_R_MULT,
    max_hold_bars: int = DEFAULT_MAX_HOLD_BARS,
) -> ConfigurationEvaluation:
    """Corre el pipeline completo para (V, T, Z) y devuelve el objetivo.

    Parámetros:
        ticks: frame del contrato de ingesta (Timestamp, Price, Volume),
            RTH filtrado y ordenado.
        volume_threshold / bar_minutes / threshold_z: candidatos V/T/Z.
        bb_period / bb_num_std: Bollinger compartida de ambas señales
            (defaults clásicos del feature engine).
        atr_period y parámetros de gestión: defaults canónicos de
            ``hybrid_model`` / ``numba_kernels``.

    Retorno: ConfigurationEvaluation con señales combinadas, trades cerrados,
    PnL total en R y desglose del objetivo. Ticks vacíos -> evaluación vacía
    con EMPTY_TRADES_OBJECTIVE (nunca excepción).

    Lanza ValueError ante columnas faltantes o parámetros no positivos.
    """
    missing = [column for column in REQUIRED_BAR_INPUT_COLUMNS if column not in ticks.columns]
    if missing:
        raise ValueError(
            f"Faltan columnas obligatorias en los ticks: {missing}. "
            f"Requeridas: {list(REQUIRED_BAR_INPUT_COLUMNS)}."
        )
    if volume_threshold <= 0:
        raise ValueError(f"volume_threshold debe ser > 0, recibido: {volume_threshold}")
    if bar_minutes <= 0:
        raise ValueError(f"bar_minutes debe ser > 0, recibido: {bar_minutes}")
    if threshold_z <= 0:
        raise ValueError(f"threshold_z debe ser > 0, recibido: {threshold_z}")

    if ticks.is_empty():
        return ConfigurationEvaluation(
            n_signals=0,
            n_trades=0,
            total_pnl_r=0.0,
            sortino=None,
            max_drawdown_r=0.0,
            drawdown_penalty=0.0,
            objective_value=EMPTY_TRADES_OBJECTIVE,
        )

    volume_bars = build_volume_bars(ticks, volume_threshold)
    signal_a_series = generate_signal_a(volume_bars, period=bb_period, num_std=bb_num_std)

    time_bars = build_time_bars(ticks, bar_minutes)
    enriched = time_bars.with_columns(
        compute_vol_buzz_z(time_bars).alias(VOL_BUZZ_COLUMN),
        compute_avwap(time_bars).alias(AVWAP_COLUMN),
    )
    signal_b_series = generate_signal_b(
        enriched, period=bb_period, num_std=bb_num_std, threshold_z=threshold_z
    )

    combined_mask = _combined_execution_mask(
        volume_bars, signal_a_series, enriched, signal_b_series
    )
    atr_values = compute_atr_series(enriched, atr_period=atr_period)

    backtest = simulate_trades(
        enriched["high"].to_numpy(),
        enriched["low"].to_numpy(),
        enriched["close"].to_numpy(),
        atr_values.to_numpy(),
        combined_mask,
        stop_atr_mult=stop_atr_mult,
        tp_r_mult=tp_r_mult,
        sl_r_mult=sl_r_mult,
        tp_exit_fraction=tp_exit_fraction,
        trail_r_mult=trail_r_mult,
        max_hold_bars=max_hold_bars,
    )

    returns_r = backtest.trades[:, TRADE_PNL_R]
    n_signals = int(np.count_nonzero(combined_mask))
    if returns_r.size == 0:
        return ConfigurationEvaluation(
            n_signals=n_signals,
            n_trades=0,
            total_pnl_r=0.0,
            sortino=None,
            max_drawdown_r=0.0,
            drawdown_penalty=0.0,
            objective_value=EMPTY_TRADES_OBJECTIVE,
        )

    breakdown = sortino_with_drawdown_penalty(returns_r, np.cumsum(returns_r))
    return ConfigurationEvaluation(
        n_signals=n_signals,
        n_trades=int(returns_r.size),
        total_pnl_r=float(returns_r.sum()),
        sortino=breakdown.sortino,
        max_drawdown_r=breakdown.max_drawdown_r,
        drawdown_penalty=breakdown.drawdown_penalty,
        objective_value=breakdown.objective_value,
    )


# ---------------------------------------------------------------------------
# Barrido Optuna (in-memory, seed fija, MedianPruner)
# ---------------------------------------------------------------------------


def run_sweep(
    ticks: pl.DataFrame,
    *,
    n_trials: int = SWEEP_DEFAULT_N_TRIALS,
    seed: int = SWEEP_RANDOM_SEED,
) -> SweepResult:
    """Optimiza (V, T, Z) maximizando Sortino - penalización de drawdowns.

    Parámetros:
        ticks: frame del contrato de ingesta; todos los trials comparten el
            mismo dataset (la construcción de barras es lo que varía).
        n_trials: presupuesto del estudio (default SWEEP_DEFAULT_N_TRIALS).
        seed: semilla del TPESampler (reproducibilidad exacta).

    Retorno: SweepResult(best_params, best_value, study) con el estudio
    in-memory completo para auditoría (todos los trials respetan el espacio).

    Lanza ValueError si n_trials < 1 o el frame no cumple el contrato.
    """
    if n_trials < 1:
        raise ValueError(f"n_trials debe ser >= 1, recibido: {n_trials}")
    missing = [column for column in REQUIRED_BAR_INPUT_COLUMNS if column not in ticks.columns]
    if missing:
        raise ValueError(f"Faltan columnas obligatorias en los ticks: {missing}.")

    optuna.logging.set_verbosity(optuna.logging.WARNING)
    study = optuna.create_study(
        direction="maximize",
        sampler=optuna.samplers.TPESampler(seed=seed),
        pruner=optuna.pruners.MedianPruner(),
        study_name="microstructure_vtz",
    )

    def _objective(trial: optuna.trial.Trial) -> float:
        volume_threshold = trial.suggest_categorical("V", list(VOLUME_BAR_CHOICES))
        bar_minutes = trial.suggest_categorical("T", list(TIME_BAR_MINUTE_CHOICES))
        threshold_z = trial.suggest_float(
            "Z", Z_THRESHOLD_LOW, Z_THRESHOLD_HIGH, step=Z_THRESHOLD_STEP
        )
        evaluation = evaluate_configuration(
            ticks,
            volume_threshold=float(volume_threshold),
            bar_minutes=int(bar_minutes),
            threshold_z=float(threshold_z),
        )
        trial.set_user_attr("n_trades", evaluation.n_trades)
        trial.set_user_attr("total_pnl_r", evaluation.total_pnl_r)
        return evaluation.objective_value

    study.optimize(_objective, n_trials=n_trials, show_progress_bar=False)

    best_trial = study.best_trial
    return SweepResult(
        best_params=dict(best_trial.params), best_value=float(best_trial.value), study=study
    )
