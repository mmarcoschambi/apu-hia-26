"""Tests del modelo híbrido LightGBM walk-forward (Issue #69, slice 3A).

Contrato bajo test (todos los valores esperados están calculados a mano):
- ``compute_atr_series``: TR canónico del sistema (como signal_engine) con
  convención documentada de primera barra (TR_0 = high - low) y media móvil
  simple de N períodos; primer valor válido en el índice ``atr_period - 1``.
- ``label_breakout_instants``: etiqueta binaria PIT por instante de ruptura.
  R = stop_atr_mult * ATR(instante); TP = entrada + tp_r * R (comparación
  ESTRICTA ">"); SL = entrada - sl_r * R (el toque cuenta como golpe).
  Ventanas j posteriores a la barra de entrada dentro del horizonte N:
  ambos lados en la MISMA ventana -> 0 (empate conservador); SL primero -> 0;
  TP primero -> 1; sin resolución -> 0. ATR indefinido / R degenerado /
  sin barra de entrada -> etiqueta nula. Sin lectura más allá del horizonte
  (invarianza por truncamiento) ni antes de la ventana de ATR.
- ``assemble_dataset``: filas = instantes de ruptura del feature engine +
  etiquetas por join exacto + contexto opcional as-of backward; salida
  determinista ordenada por timestamp; colisiones/duplicados -> ValueError.
- ``build_context_frame``: adaptadores finos que LLAMAN funciones públicas
  existentes (compute_tier2_metrics para RS, calculate_health_score_pit
  para health 0-7) recortando SOLO días PREVIOS al día del instante (PIT);
  degradación elegante a nulos si la historia es insuficiente.
- ``train_walk_forward``: K folds con ventana expansiva estrictamente
  ordenada por timestamp (todo train < todo test), métricas por fold,
  desbalance con scale_pos_weight documentado, errores en datasets mínimos.
- Inferencia: probabilidades en [0, 1], gate de capital estricto (>), artifact
  guardado/recargado predice idéntico.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import polars as pl
import pytest

from src.microstructure.feature_engine import (
    FEATURE_DIST_LAST_VOLBAR_CLOSE_PCT,
    FEATURE_DIST_VS_AVWAP_PCT,
    FEATURE_OUTPUT_COLUMNS,
    FEATURE_RECENT_ADR_PCT,
    FEATURE_TIMESTAMP,
    FEATURE_VOL_BUZZ_Z,
    FEATURE_VOLBAR_SPEED_MS,
)
from src.microstructure.hybrid_model import (
    DEFAULT_CONFIDENCE_THRESHOLD,
    DEFAULT_MODEL_DIR,
    LABEL_COLUMN,
    assemble_dataset,
    build_context_frame,
    compute_atr_series,
    label_breakout_instants,
    load_model,
    predict_probability,
    save_model,
    should_deploy_capital,
    train_walk_forward,
)

BASE_DAY = datetime(2024, 1, 8)


# ---------------------------------------------------------------------------
# Helpers de fixtures sintéticas deterministas
# ---------------------------------------------------------------------------


def _bars(ends: list[datetime], highs: list[float], lows: list[float], closes: list[float]) -> pl.DataFrame:
    """Construye un DF de barras de evaluación (time bars mínimas)."""
    return pl.DataFrame(
        {
            "end_timestamp": ends,
            "open": closes,
            "high": highs,
            "low": lows,
            "close": closes,
            "volume": [1000.0] * len(ends),
        }
    )


def _flat_bars(n: int, start_minute: int = 9 * 60 + 35, step_minutes: int = 5) -> pl.DataFrame:
    """Barras de rango constante h=101 / l=99 / c=100 -> TR=2 y ATR(N)=2.

    Con atr_period=3 el ATR vale exactamente 2.0 desde el índice 2 en
    adelante; R default = 0.5 * 2 = 1.0 -> TP = entry + 2, SL = entry - 1.
    """
    ends = [BASE_DAY + timedelta(minutes=start_minute + step_minutes * (i + 1)) for i in range(n)]
    return _bars(ends, [101.0] * n, [99.0] * n, [100.0] * n)


def _features(stamps: list[datetime], **overrides: object) -> pl.DataFrame:
    """Frame de features tipado con las seis columnas core del feature engine."""
    n = len(stamps)

    def column(name: str, default: float) -> list[float]:
        value = overrides.get(name)
        return [default] * n if value is None else list(value)  # type: ignore[arg-type]

    data = {
        FEATURE_TIMESTAMP: stamps,
        FEATURE_DIST_LAST_VOLBAR_CLOSE_PCT: column(FEATURE_DIST_LAST_VOLBAR_CLOSE_PCT, 1.0),
        FEATURE_VOLBAR_SPEED_MS: column(FEATURE_VOLBAR_SPEED_MS, 1000.0),
        FEATURE_VOL_BUZZ_Z: column(FEATURE_VOL_BUZZ_Z, float("nan")),
        FEATURE_DIST_VS_AVWAP_PCT: column(FEATURE_DIST_VS_AVWAP_PCT, 0.5),
        FEATURE_RECENT_ADR_PCT: column(FEATURE_RECENT_ADR_PCT, 2.0),
    }
    return pl.DataFrame(data)


def _instant_of(bars: pl.DataFrame, index: int) -> datetime:
    """Instante de ruptura = end_timestamp de la barra i."""
    return bars["end_timestamp"][index]


def _daily_pandas(
    n_days: int,
    base: float,
    drift: float,
    *,
    start: str = "2023-01-02",
    crash_on_last: bool = False,
    crash_factor: float = 0.7,
) -> pd.DataFrame:
    """OHLCV diario determinista (índice DatetimeIndex, columnas lowercase).

    Tendencia geométrica ``base * (1 + drift)^i``; con ``crash_on_last`` el
    último día cae ``crash_factor`` (para detectar fugas de PIT: incluir ese
    día cambia el resultado respecto de usar solo días previos).
    """
    index = pd.bdate_range(start=start, periods=n_days)
    closes = base * (1.0 + drift) ** np.arange(n_days)
    if crash_on_last:
        closes[-1] = closes[-1] * crash_factor
    opens = np.concatenate(([base], closes[:-1]))
    return pd.DataFrame(
        {
            "open": opens,
            "high": closes * 1.01,
            "low": closes * 0.99,
            "close": closes,
            "volume": [1_000_000.0] * n_days,
        },
        index=index,
    )


def _synthetic_labeled_dataset(n_rows: int = 96) -> pl.DataFrame:
    """Dataset sintético separable por regla determinista (pos <=> i % 4 == 0).

    Con n=96 y k_folds=4 el primer chunk de train tiene 20 filas con
    EXACTAMENTE 5 positivos y 15 negativos -> scale_pos_weight auto = 3.0.
    f3 incluye NaN estilo vol_buzz_z (no-señal) cada 5 filas: LightGBM los
    maneja nativamente y el contrato lo documenta.
    """
    stamps = [BASE_DAY + timedelta(minutes=5 * (i + 1)) for i in range(n_rows)]
    positive = [i % 4 == 0 for i in range(n_rows)]
    f1 = [(1.0 if p else 0.0) + ((i * 37) % 11) / 1000.0 for i, p in enumerate(positive)]
    f2 = [float((i * 7) % 13) for i in range(n_rows)]
    f3 = [float("nan") if i % 5 == 0 else float((i * 3) % 7) for i in range(n_rows)]
    frame = _features(stamps, **{FEATURE_DIST_LAST_VOLBAR_CLOSE_PCT: f1})
    frame = frame.with_columns(
        pl.Series("f2_aux", f2, dtype=pl.Float64),
        pl.Series("f3_aux", f3, dtype=pl.Float64),
        pl.Series(LABEL_COLUMN, [int(p) for p in positive], dtype=pl.Int64),
    )
    return frame


# ---------------------------------------------------------------------------
# compute_atr_series
# ---------------------------------------------------------------------------


def test_atr_constant_range_is_exact_two_from_index_period_minus_one() -> None:
    """Rango constante -> TR=2 siempre; ATR(3) válido desde índice 2."""
    bars = _flat_bars(5)

    atr = compute_atr_series(bars, atr_period=3)

    assert isinstance(atr, pl.Series)
    assert atr.name == "atr"
    assert len(atr) == 5
    values = atr.to_list()
    assert values[0] is None and values[1] is None
    for value in values[2:]:
        assert value == pytest.approx(2.0)


def test_atr_matches_hand_computed_true_ranges() -> None:
    """TRs a mano: [1.0, 1.5, 0.5, 0.7] -> ATR(3) = [None,None,1.0,0.9]."""
    day = BASE_DAY
    bars = _bars(
        ends=[day.replace(hour=10), day.replace(hour=10, minute=5),
              day.replace(hour=10, minute=10), day.replace(hour=10, minute=15)],
        highs=[10.0, 11.0, 10.4, 10.8],
        lows=[9.0, 9.5, 10.0, 10.1],
        closes=[9.5, 10.5, 10.2, 10.6],
    )

    atr = compute_atr_series(bars, atr_period=3)

    assert atr.to_list()[2] == pytest.approx((1.0 + 1.5 + 0.5) / 3)
    assert atr.to_list()[3] == pytest.approx((1.5 + 0.5 + 0.7) / 3)


def test_atr_empty_bars_return_empty_series() -> None:
    """Barras vacías -> serie vacía tipada, sin excepción."""
    empty = pl.DataFrame(schema={"high": pl.Float64, "low": pl.Float64, "close": pl.Float64})

    atr = compute_atr_series(empty, atr_period=3)

    assert len(atr) == 0 and atr.dtype == pl.Float64


# ---------------------------------------------------------------------------
# label_breakout_instants: escenarios calculados a mano
# ---------------------------------------------------------------------------


def _label_with_tail(tail_rows: list[tuple[float, float]], horizon_windows: int = 20) -> int | None:
    """Etiqueta del instante en la barra i=4 del fixture plano con cola dada.

    tail_rows: pares (high, low) de las ventanas POSTERIORES a la entrada.
    """
    bars = _flat_bars(5 + len(tail_rows))
    if tail_rows:
        highs = bars["high"].to_list()
        lows = bars["low"].to_list()
        for offset, (high, low) in enumerate(tail_rows, start=5):
            highs[offset] = high
            lows[offset] = low
        bars = bars.with_columns(pl.Series("high", highs), pl.Series("low", lows))
    features = _features([_instant_of(bars, 4)])
    labeled = label_breakout_instants(
        features, bars, horizon_windows=horizon_windows, atr_period=3
    )
    return labeled[LABEL_COLUMN].to_list()[0]


def test_label_win_reaching_2r_before_stop_is_one() -> None:
    """Ventana siguiente toca >2R (103 > 102) sin tocar SL -> etiqueta 1."""
    assert _label_with_tail([(103.0, 100.0)]) == 1


def test_label_stop_hit_first_is_zero() -> None:
    """Ventana siguiente perfora SL (98.9 <= 99) sin llegar a TP -> 0."""
    assert _label_with_tail([(100.0, 98.9)]) == 0


def test_label_same_window_both_sides_conservative_zero() -> None:
    """Ambos niveles tocados en la MISMA ventana -> 0 (empate conservador)."""
    assert _label_with_tail([(103.0, 98.5)]) == 0


def test_label_never_resolves_within_horizon_is_zero() -> None:
    """Dos ventanas laterales que no cruzan ningún nivel -> 0.

    Triangulación: una tercera ventana SÍ cruzaría TP pero queda FUERA del
    horizonte (N=2) -> sigue 0 (acota el horizonte por derecha).
    """
    flat_tail = [(101.5, 99.5)] * 2
    assert _label_with_tail(flat_tail, horizon_windows=2) == 0
    beyond = flat_tail + [(103.0, 100.0)]
    assert _label_with_tail(beyond, horizon_windows=2) == 0


def test_label_resolution_order_matters() -> None:
    """Dentro del horizonte manda QUIÉN se resuelve primero.

    SL en v1 y TP recién en v2 -> 0. Espejo: TP en v1 y SL en v2 -> 1.
    """
    sl_first = [(100.0, 98.9), (103.0, 100.0), (104.0, 101.0)]
    assert _label_with_tail(sl_first, horizon_windows=3) == 0
    tp_first = [(103.0, 100.0), (98.0, 97.0), (97.0, 96.0)]
    assert _label_with_tail(tp_first, horizon_windows=3) == 1


def test_exact_levels_strict_tp_and_touched_sl() -> None:
    """Convenciones de borde en una sola ventana: high == TP NO gana
    (comparación ESTRICTA '>'), low == SL SÍ pierde (el toque cuenta)."""
    assert _label_with_tail([(102.0, 99.0)]) == 0


def test_label_null_when_atr_undefined_or_degenerate() -> None:
    """ATR indefinido en la barra de entrada -> etiqueta nula.

    Instantes [fin b1, fin b4]: b1 tiene índice 1 < period-1=2 -> None;
    b4 -> numérica (ventana ganadora). Además R degenerado (ATR=0 sobre
    velas doji h=l=c) -> None.
    """
    bars = _flat_bars(6)
    features = _features([_instant_of(bars, 1), _instant_of(bars, 4)])
    labeled = label_breakout_instants(features, bars, atr_period=3)
    labels = labeled[LABEL_COLUMN].to_list()
    assert labels[0] is None
    assert isinstance(labels[1], int)

    doji = _bars(
        ends=[BASE_DAY + timedelta(minutes=35 + 5 * i) for i in range(6)],
        highs=[100.0] * 6,
        lows=[100.0] * 6,
        closes=[100.0] * 6,
    )
    doji_features = _features([doji["end_timestamp"][4]])
    assert label_breakout_instants(doji_features, doji, atr_period=3)[LABEL_COLUMN][0] is None


def test_label_null_when_no_entry_bar_exists() -> None:
    """Instante ANTERIOR a toda barra completada -> sin entrada -> None."""
    bars = _flat_bars(5)
    features = _features([BASE_DAY.replace(hour=9, minute=0)])

    labeled = label_breakout_instants(features, bars, atr_period=3)

    assert labeled[LABEL_COLUMN].to_list() == [None]


def test_labels_invariant_under_truncation_beyond_horizon() -> None:
    """Sin fuga futura: truncar barras MÁS ALLÁ del horizonte no cambia nada.

    Horizonte 2 desde b4: conservar hasta b6 basta. La vela b5 es ganadora
    (103/100 -> etiqueta 1) y b6 plana; la versión completa tiene b7 salvaje
    (h=200/l=5) que JAMÁS debe influir -> etiquetas idénticas.
    """
    bars = _flat_bars(8)
    highs = bars["high"].to_list()
    lows = bars["low"].to_list()
    highs[5], lows[5] = 103.0, 100.0
    highs[7], lows[7] = 200.0, 5.0
    bars = bars.with_columns(pl.Series("high", highs), pl.Series("low", lows))
    features = _features([_instant_of(bars, 4)])

    full = label_breakout_instants(features, bars, atr_period=3, horizon_windows=2)
    truncated_bars = bars.filter(pl.col("end_timestamp") <= _instant_of(bars, 6))
    truncated = label_breakout_instants(features, truncated_bars, atr_period=3, horizon_windows=2)

    expected = full[LABEL_COLUMN].to_list()
    assert expected == [1]
    assert truncated[LABEL_COLUMN].to_list() == expected


def test_labels_invariant_to_mutations_outside_atr_window() -> None:
    """Sin fuga pasada: mutar b0 (fuera de la ventana ATR(3)@b4 y del scan)
    deja la etiqueta intacta (TR2..TR4 solo dependen de c1..c3)."""
    bars = _flat_bars(6)
    highs = bars["high"].to_list()
    lows = bars["low"].to_list()
    highs[5], lows[5] = 103.0, 100.0
    bars = bars.with_columns(pl.Series("high", highs), pl.Series("low", lows))
    features = _features([_instant_of(bars, 4)])
    baseline = label_breakout_instants(features, bars, atr_period=3)[LABEL_COLUMN].to_list()

    mutated_highs = [300.0, *highs[1:]]
    mutated_lows = [1.0, *lows[1:]]
    mutated_closes = [250.0, *bars["close"].to_list()[1:]]
    mutated = bars.with_columns(
        pl.Series("high", mutated_highs),
        pl.Series("low", mutated_lows),
        pl.Series("close", mutated_closes),
    )
    after = label_breakout_instants(features, mutated, atr_period=3)[LABEL_COLUMN].to_list()

    assert baseline == [1]
    assert after == baseline


def test_duplicate_breakout_instants_raise() -> None:
    """Timestamps duplicados en el frame de features -> ValueError explícito."""
    bars = _flat_bars(5)
    stamp = _instant_of(bars, 4)

    with pytest.raises(ValueError):
        label_breakout_instants(_features([stamp, stamp]), bars)


# ---------------------------------------------------------------------------
# assemble_dataset: contrato de columnas y joins deterministas
# ---------------------------------------------------------------------------


def test_assemble_dataset_joins_labels_sorts_and_keeps_context_columns() -> None:
    """Filas ordenadas por timestamp, label por join exacto y columnas de
    contexto previamente fusionadas se preservan como features adicionales."""
    stamps = [
        BASE_DAY.replace(hour=10, minute=30),
        BASE_DAY.replace(hour=10, minute=10),
    ]
    features = _features(stamps).with_columns(
        pl.Series("rs_ret", [0.5, -0.2], dtype=pl.Float64),
    )
    labels = pl.DataFrame(
        {
            FEATURE_TIMESTAMP: [stamps[1], stamps[0]],
            LABEL_COLUMN: [0, 1],
        }
    )

    dataset = assemble_dataset(features, labels_frame=labels)

    assert dataset.columns == [*FEATURE_OUTPUT_COLUMNS, "rs_ret", LABEL_COLUMN]
    assert dataset[FEATURE_TIMESTAMP].to_list() == sorted(stamps)
    assert dataset[LABEL_COLUMN].to_list() == [0, 1]


def test_assemble_dataset_without_labels_emits_all_null_label_column() -> None:
    """Sin labels_frame igualmente existe la columna label (contrato uniforme)."""
    features = _features([BASE_DAY.replace(hour=10, minute=10)])

    dataset = assemble_dataset(features)

    assert dataset.columns == [*FEATURE_OUTPUT_COLUMNS, LABEL_COLUMN]
    assert dataset[LABEL_COLUMN].to_list() == [None]


def test_assemble_dataset_unmatched_instant_keeps_null_label() -> None:
    """Instante sin etiqueta correspondiente sobrevive con label nulo."""
    stamps = [BASE_DAY.replace(hour=10, minute=10), BASE_DAY.replace(hour=10, minute=30)]
    features = _features(stamps)
    labels = pl.DataFrame({FEATURE_TIMESTAMP: [stamps[0]], LABEL_COLUMN: [1]})

    dataset = assemble_dataset(features, labels_frame=labels)

    assert dataset[LABEL_COLUMN].to_list() == [1, None]


def test_assemble_dataset_missing_core_columns_raise() -> None:
    """Faltan columnas core del feature engine -> ValueError nombrándolas."""
    broken = _features([BASE_DAY.replace(hour=10, minute=10)]).drop(FEATURE_VOL_BUZZ_Z)

    with pytest.raises(ValueError, match="vol_buzz_z"):
        assemble_dataset(broken)


def test_assemble_dataset_duplicate_labels_raise() -> None:
    """Timestamps duplicados en labels_frame -> ValueError."""
    stamp = BASE_DAY.replace(hour=10, minute=10)
    dup = pl.DataFrame({FEATURE_TIMESTAMP: [stamp, stamp], LABEL_COLUMN: [1, 0]})

    with pytest.raises(ValueError):
        assemble_dataset(_features([stamp]), labels_frame=dup)


# ---------------------------------------------------------------------------
# build_context_frame: adaptadores finos PIT hacia módulos existentes
# ---------------------------------------------------------------------------

RS_LOOKBACK = 60


def test_context_rs_delegates_with_prior_days_only() -> None:
    """rs_ret delega en compute_tier2_metrics con días ESTRICTAMENTE previos.

    El ticker viene ganándole al SPY y el ÚLTIMO día se desploma: si el
    adaptador incluyera ese día el RS cambiaría de signo -> el valor correcto
    es el calculado a mano sobre el recorte previo.
    """
    from src.signals.signal_engine import compute_tier2_metrics

    n_days = 70
    ticker = _daily_pandas(n_days, 50.0, 0.004, crash_on_last=True)
    spy = _daily_pandas(n_days, 500.0, 0.001, start="2023-01-02")
    last_day = ticker.index[-1].date()
    stamps = [pd.Timestamp(last_day, tz=None).to_pydatetime().replace(hour=10, minute=30)]

    context = build_context_frame(stamps, ticker_daily=ticker, spy_daily=spy, rs_lookback=RS_LOOKBACK)

    prior_ticker = ticker[ticker.index.date < last_day]
    prior_spy = spy[spy.index.date < last_day]
    expected = compute_tier2_metrics(prior_ticker, prior_spy, rs_lookback=RS_LOOKBACK).rs_ret
    assert expected is not None and expected > 0.0
    assert context["rs_ret"].to_list() == [pytest.approx(expected)]

    including_crash = compute_tier2_metrics(ticker, spy, rs_lookback=RS_LOOKBACK).rs_ret
    assert including_crash != pytest.approx(expected)


def test_context_health_score_delegates_with_prior_days_only() -> None:
    """health_score delega en calculate_health_score_pit con días previos.

    Rally de 220 días y crash el día D: score_previo (alto) != score_con_día
    (colapsado). El adaptador debe devolver el PREVIO.
    """
    from src.utils.market_health import calculate_health_score_pit

    n_days = 220
    spy = _daily_pandas(n_days, 400.0, 0.0015, crash_on_last=True)
    ticker = _daily_pandas(n_days, 40.0, 0.002)
    last_day = spy.index[-1].date()
    stamps = [pd.Timestamp(last_day).to_pydatetime().replace(hour=11, minute=0)]

    context = build_context_frame(stamps, ticker_daily=ticker, spy_daily=spy)

    prior = spy[spy.index.date < last_day]
    expected_prior = calculate_health_score_pit(prior.copy())
    expected_full = calculate_health_score_pit(spy.copy())
    assert expected_prior != expected_full
    assert context["health_score"].to_list() == [expected_prior]
    assert 0 <= context["health_score"][0] <= 7


def test_context_vix_optional_shifts_health_by_one_point() -> None:
    """Con historia suficiente, VIX < 20 suma EXACTAMENTE un punto (+1)."""
    n_days = 220
    ticker = _daily_pandas(n_days, 40.0, 0.002)
    spy = _daily_pandas(n_days, 400.0, 0.0015)
    vix_low = _daily_pandas(n_days, 12.0, 0.0001)
    vix_high = _daily_pandas(n_days, 45.0, 0.0001)
    stamps = [pd.Timestamp(spy.index[-1].date()).to_pydatetime().replace(hour=11, minute=0)]

    with_low = build_context_frame(stamps, ticker_daily=ticker, spy_daily=spy, vix_daily=vix_low)
    with_high = build_context_frame(stamps, ticker_daily=ticker, spy_daily=spy, vix_daily=vix_high)

    assert with_low["health_score"].to_list()[0] == with_high["health_score"].to_list()[0] + 1


def test_context_insufficient_history_degrades_to_null_rs_default_health() -> None:
    """Historia corta (< 20 filas): rs_ret NULL sin lanzar excepción y health
    con el default documentado del propio API (= 3)."""
    ticker = _daily_pandas(15, 50.0, 0.004)
    spy = _daily_pandas(15, 500.0, 0.001)
    stamps = [datetime(2023, 1, 25, 10, 30)]

    context = build_context_frame(stamps, ticker_daily=ticker, spy_daily=spy, rs_lookback=60)

    assert context["rs_ret"].to_list() == [None]
    assert context["health_score"].to_list() == [3]


def test_context_same_date_timestamps_share_values_and_calls_are_deterministic() -> None:
    """Dos instantes del MISMO día comparten valores (cache por fecha) y dos
    ejecuciones producen frames idénticos."""
    n_days = 70
    ticker = _daily_pandas(n_days, 50.0, 0.004)
    spy = _daily_pandas(n_days, 500.0, 0.001)
    day = ticker.index[-1].date()
    stamps = [
        pd.Timestamp(day).to_pydatetime().replace(hour=10, minute=0),
        pd.Timestamp(day).to_pydatetime().replace(hour=14, minute=45),
    ]

    first = build_context_frame(stamps, ticker_daily=ticker, spy_daily=spy)
    second = build_context_frame(stamps, ticker_daily=ticker, spy_daily=spy)

    assert first["rs_ret"].to_list() == second["rs_ret"].to_list()
    assert first["health_score"].to_list() == second["health_score"].to_list()


def test_context_empty_timestamps_return_typed_empty_frame() -> None:
    """Lista vacía -> frame vacío tipado con el contrato completo."""
    ticker = _daily_pandas(5, 50.0, 0.004)
    spy = _daily_pandas(5, 500.0, 0.001)

    context = build_context_frame([], ticker_daily=ticker, spy_daily=spy)

    assert len(context) == 0
    assert context.columns == [FEATURE_TIMESTAMP, "rs_ret", "health_score"]


# ---------------------------------------------------------------------------
# train_walk_forward: folds expansivos ordenados + métricas + desbalance
# ---------------------------------------------------------------------------


def test_walk_forward_folds_are_strictly_time_ordered() -> None:
    """CADA fold: todo timestamp de train < todo timestamp de test."""
    dataset = _synthetic_labeled_dataset(96)

    result = train_walk_forward(dataset, k_folds=4)

    assert len(result.folds) == 4
    for fold in result.folds:
        assert fold.train_end < fold.test_start


def test_walk_forward_train_window_expands_and_test_chunks_partition() -> None:
    """Ventana expansiva (n_train creciente) y chunks de test disjuntos que
    particionan todas las filas efectivas tras el train inicial."""
    dataset = _synthetic_labeled_dataset(96)

    result = train_walk_forward(dataset, k_folds=4)

    train_sizes = [fold.n_train for fold in result.folds]
    assert train_sizes == sorted(train_sizes) and len(set(train_sizes)) == 4
    assert sum(fold.n_test for fold in result.folds) == 96 - train_sizes[0]


def test_walk_forward_metrics_present_and_auc_above_chance_on_final_fold() -> None:
    """Cada fold reporta precision/recall/auc/n_test; datos perfectamente
    separables + semilla fija -> AUC del último fold claramente > azar."""
    dataset = _synthetic_labeled_dataset(96)

    result = train_walk_forward(dataset, k_folds=4)

    final = result.folds[-1]
    assert final.auc is not None and final.auc > 0.8
    assert final.precision is not None and final.recall is not None
    assert final.n_test >= 4
    assert 0.0 <= final.precision <= 1.0 and 0.0 <= final.recall <= 1.0


def test_walk_forward_auto_scale_pos_weight_matches_fold_imbalance() -> None:
    """scale_pos_weight automático por fold = n_neg / n_pos de SU train
    (primer fold: 18 negativos / 6 positivos = 3.0)."""
    dataset = _synthetic_labeled_dataset(96)

    result = train_walk_forward(dataset, k_folds=4)

    assert result.folds[0].scale_pos_weight == pytest.approx(18.0 / 6.0)


def test_walk_forward_explicit_scale_pos_weight_is_recorded() -> None:
    """Valor explícito respeta y registra tal cual (documentación viva)."""
    dataset = _synthetic_labeled_dataset(48)

    result = train_walk_forward(dataset, k_folds=3, scale_pos_weight=2.5)

    assert all(fold.scale_pos_weight == pytest.approx(2.5) for fold in result.folds)


@pytest.mark.parametrize(
    ("n_rows", "k_folds"),
    [(12, 5), (16, 8)],
)
def test_walk_forward_tiny_dataset_raises_value_error(n_rows: int, k_folds: int) -> None:
    """Datasets demasiado chicos para K folds con mínimos por fold -> ValueError."""
    with pytest.raises(ValueError):
        train_walk_forward(_synthetic_labeled_dataset(n_rows), k_folds=k_folds)


@pytest.mark.parametrize(
    ("mutation", "match"),
    [
        ("zero_kfolds", "k_folds"),
        ("missing_label", "label"),
        ("non_numeric_feature", "numéric"),
    ],
)
def test_walk_forward_invalid_inputs_raise(mutation: str, match: str) -> None:
    """k<1, falta columna label o features no numéricas -> ValueError claro."""
    if mutation == "zero_kfolds":
        with pytest.raises(ValueError, match="k_folds"):
            train_walk_forward(_synthetic_labeled_dataset(48), k_folds=0)
        return
    dataset = _synthetic_labeled_dataset(48)
    if mutation == "missing_label":
        dataset = dataset.drop(LABEL_COLUMN)
    else:
        dataset = dataset.with_columns(pl.Series("txt", ["a"] * len(dataset), dtype=pl.String))
    with pytest.raises(ValueError, match=match):
        train_walk_forward(dataset, k_folds=3)


def test_predict_probability_bounds_and_length() -> None:
    """predict_probability devuelve floats en [0, 1] alineados a las filas."""
    dataset = _synthetic_labeled_dataset(96)
    result = train_walk_forward(dataset, k_folds=4)

    probs = predict_probability(result, dataset)

    assert len(probs) == len(dataset)
    assert all(0.0 <= p <= 1.0 for p in probs)
    assert all(isinstance(p, float) for p in probs)


def test_should_deploy_capital_gate_is_strictly_greater_than_threshold() -> None:
    """Gate de capital: SOLO probabilidad ESTRICTAMENTE mayor despliega."""
    assert should_deploy_capital(DEFAULT_CONFIDENCE_THRESHOLD + 0.01) is True
    assert should_deploy_capital(DEFAULT_CONFIDENCE_THRESHOLD) is False
    assert should_deploy_capital(DEFAULT_CONFIDENCE_THRESHOLD - 0.01) is False
    assert should_deploy_capital(0.55, threshold=0.5) is True
    assert should_deploy_capital(0.5, threshold=0.5) is False


def test_should_deploy_capital_rejects_invalid_probability() -> None:
    """Probabilidad fuera de [0, 1] -> ValueError (contrato defensivo)."""
    with pytest.raises(ValueError):
        should_deploy_capital(1.5)
    with pytest.raises(ValueError):
        should_deploy_capital(-0.1)


def test_save_load_round_trip_predicts_identical_probabilities(tmp_path: Path) -> None:
    """Artifact nativo de LightGBM: guardar -> recargar -> mismas probabilidades."""
    dataset = _synthetic_labeled_dataset(96)
    result = train_walk_forward(dataset, k_folds=4)
    artifact_path = tmp_path / "hybrid_model.txt"

    save_model(result, artifact_path)
    reloaded = load_model(artifact_path)

    assert artifact_path.exists()
    assert reloaded.feature_columns == result.feature_columns
    before = predict_probability(result, dataset)
    after = predict_probability(reloaded, dataset)
    assert before == after


def test_default_artifact_dir_is_gitignored_outputs() -> None:
    """El directorio default vive bajo outputs/ (gitignore: outputs/*)."""
    assert str(DEFAULT_MODEL_DIR).replace("\\", "/").startswith("outputs/")
