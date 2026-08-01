"""
Regresión: filtro de umbrales dinámicos (RVOL / ADR / stop) — OLD vs NEW.

Contexto
--------
El commit ab7c44d ("perf(backtest): vectorización de motor") reescribió el
filtro de umbrales dinámicos en `src/backtest/vectorbt_engine_advanced.py`. El
cambio de comportamiento es REAL sobre fechas con huecos:

  OLD (loop por fecha):
      si la fecha NO está en el índice dinámico:
          - low_rvol / low_adr: NO aplica umbral (máscara = False)
          - stop: cae al umbral estático self.max_stop_pct
  NEW (reindex + ffill):
      - fechas con hueco heredan el ÚLTIMO umbral dinámico conocido (ffill)
      - stop: solo fechas que NUNCA tuvieron valor usan el estático

PIN DE PRODUCCIÓN: el lado NEW de este test NO es una réplica local. Ejercita
directamente las funciones de producción `vectorized_low_mask` y
`vectorized_wide_stop_mask` (`src/backtest/vectorbt_engine_advanced.py`), que
son las que consume el motor en `run_backtest` para aplicar los filtros de
liquidez. Si la producción vuelve al loop OLD (lookup exacto de fecha), la
máscara emitida difiere de la referencia NEW y este test falla ruidosamente.

LÍNEA BASE LOCAL: el lado OLD SÍ es una réplica local (`_old_low_mask` /
`_old_wide_stop_mask`): es la referencia histórica contra la que se protege el
test, no código que la producción deba ejecutar.

DECISIÓN (correcto): NEW (ffill) es el comportamiento correcto. Un umbral de
régimen dinámico (p. ej. min RVOL elevado en régimen volátil) debe seguir
aplicando los días posteriores hasta que cambie explícitamente: las fechas con
hueco (feriados, faltantes) son días de trading donde el régimen sigue vigente.
Caer al estático en un hueco dejaría pasar trades que la regla de régimen
quería bloquear.
"""

from typing import Dict, List, Sequence, Tuple

import pandas as pd
import pytest

from src.backtest.vectorbt_engine_advanced import (
    vectorized_low_mask,
    vectorized_wide_stop_mask,
)

START_DATE = pd.Timestamp("2026-01-05")
END_DATE = pd.Timestamp("2026-04-03")
TICKERS: Tuple[str, ...] = ("AAA", "BBB", "CCC")

# Huecos intencionales en el índice dinámico.
HOLIDAY_DATES: Tuple[pd.Timestamp, ...] = (
    pd.Timestamp("2026-01-19"),  # MLK Day (lunes, día bursátil omitido)
    pd.Timestamp("2026-02-16"),  # Presidents Day (lunes, día bursátil omitido)
)
RANDOM_GAP_DATE = pd.Timestamp("2026-03-18")  # Hueco aleatorio mid-week
TRAILING_GAP_DATE = pd.Timestamp("2026-04-03")  # Hueco al final de la muestra
LEADING_GAP_DATES: Tuple[pd.Timestamp, ...] = (
    pd.Timestamp("2026-01-05"),  # Antes del primer umbral dinámico
    pd.Timestamp("2026-01-06"),
)
REVERSE_EDGE_DATE = pd.Timestamp("2026-02-14")  # Fecha en índice dinámico que NO está en el principal

# Ventana de régimen estricto (VIX alto -> umbrales más exigentes).
STRICT_START = pd.Timestamp("2026-02-09")
STRICT_END = pd.Timestamp("2026-03-31")

# Umbrales por régimen.
STRICT_RVOL = 2.0
STRICT_ADR = 3.0
STRICT_STOP = 0.05
RELAXED_RVOL = 1.0
RELAXED_ADR = 2.0
RELAXED_STOP = 0.08
ANOMALOUS_REVERSE_RVOL = 5.0  # Valor anómalo en la fecha fuera del índice principal

# Umbral estático de stop (fallback).
STATIC_MAX_STOP = 0.08

# Valores base por métrica (el resto de celdas usa estos).
BASE_RVOL = 1.0
BASE_ADR = 3.5
BASE_STOP_DIST = 0.03

# Sobreescrituras puntuales por (fecha, ticker) para forzar el delta.
RVOL_OVERRIDES: List[Tuple[str, str, float]] = [
    ("2026-01-19", "CCC", 0.7),
    ("2026-02-16", "AAA", 1.3),
    ("2026-02-16", "BBB", 1.6),
    ("2026-02-16", "CCC", 2.5),
    ("2026-03-18", "AAA", 1.5),
    ("2026-03-18", "BBB", 0.8),
    ("2026-03-18", "CCC", 2.2),
    ("2026-04-03", "BBB", 0.9),
]
ADR_OVERRIDES: List[Tuple[str, str, float]] = [
    ("2026-01-19", "BBB", 1.8),
    ("2026-02-16", "AAA", 2.5),
    ("2026-03-18", "BBB", 1.5),
]
STOP_OVERRIDES: List[Tuple[str, str, float]] = [
    ("2026-02-16", "BBB", 0.06),
    ("2026-03-18", "AAA", 0.06),
]

GAP_DATES = (
    HOLIDAY_DATES
    + (RANDOM_GAP_DATE, TRAILING_GAP_DATE)
    + LEADING_GAP_DATES
)


def _make_frame(
    index: pd.DatetimeIndex, base: float, overrides: Sequence[Tuple[str, str, float]]
) -> pd.DataFrame:
    """Construye un DataFrame de métricas (fecha x ticker) con sobreescrituras."""
    df = pd.DataFrame(base, index=index, columns=TICKERS)
    for date, ticker, value in overrides:
        df.loc[pd.Timestamp(date), ticker] = value
    return df


def _regime_value(
    date: pd.Timestamp,
    strict_start: pd.Timestamp,
    strict_end: pd.Timestamp,
    strict_value: float,
    relaxed_value: float,
) -> float:
    """Devuelve el umbral del régimen vigente para la fecha."""
    if strict_start <= date <= strict_end:
        return strict_value
    return relaxed_value


def _build_dynamic_series(
    index: pd.DatetimeIndex,
    extra: Sequence[Tuple[pd.Timestamp, float]],
    strict_value: float,
    relaxed_value: float,
) -> pd.Series:
    """Construye la Serie de umbrales dinámicos omitiendo los huecos del fixture."""
    present = [
        d
        for d in index
        if d not in GAP_DATES and d != TRAILING_GAP_DATE and d not in LEADING_GAP_DATES
    ]
    series = pd.Series(
        {
            d: _regime_value(d, STRICT_START, STRICT_END, strict_value, relaxed_value)
            for d in present
        },
        dtype=float,
    )
    for date, value in extra:
        series.loc[date] = value
    return series.sort_index()


def _old_low_mask(df: pd.DataFrame, dynamic: pd.Series) -> pd.DataFrame:
    """Replica el loop por fecha de ab7c44d^ (lookup exacto de fecha)."""
    mask = pd.DataFrame(False, index=df.index, columns=df.columns)
    for date in df.index:
        if date in dynamic.index:
            threshold = dynamic.loc[date]
            mask.loc[date] = df.loc[date] < threshold
    return mask


def _old_wide_stop_mask(
    stop_df: pd.DataFrame, dynamic: pd.Series, static_default: float
) -> pd.DataFrame:
    """Replica el loop OLD de stop: fallback al estático si la fecha falta."""
    mask = pd.DataFrame(False, index=stop_df.index, columns=stop_df.columns)
    for date in stop_df.index:
        if date in dynamic.index:
            threshold = dynamic.loc[date]
        else:
            threshold = static_default
        mask.loc[date] = stop_df.loc[date] > threshold
    return mask


@pytest.fixture
def thresholds() -> Dict[str, pd.DataFrame]:
    """Fixture con DataFrames de métricas y Series de umbrales dinámicos."""
    index = pd.bdate_range(START_DATE, END_DATE)
    rvol_df = _make_frame(index, BASE_RVOL, RVOL_OVERRIDES)
    adr_df = _make_frame(index, BASE_ADR, ADR_OVERRIDES)
    stop_df = _make_frame(index, BASE_STOP_DIST, STOP_OVERRIDES)

    min_rvol_dynamic = _build_dynamic_series(
        index, [(REVERSE_EDGE_DATE, ANOMALOUS_REVERSE_RVOL)], STRICT_RVOL, RELAXED_RVOL
    )
    min_adr_dynamic = _build_dynamic_series(index, [], STRICT_ADR, RELAXED_ADR)
    max_stop_dynamic = _build_dynamic_series(index, [], STRICT_STOP, RELAXED_STOP)

    return {
        "rvol": rvol_df,
        "adr_pct": adr_df,
        "stop_dist": stop_df,
        "min_rvol_dynamic": min_rvol_dynamic,
        "min_adr_dynamic": min_adr_dynamic,
        "max_stop_pct_dynamic": max_stop_dynamic,
        "static_max_stop": STATIC_MAX_STOP,
    }


def test_old_vs_new_differ_only_on_forward_gap_dates(thresholds):
    """
    DELTA OLD vs NEW: prueba que el comportamiento difiere SOLO en fechas con
    hueco posteriores al primer umbral dinámico (forward gap), y que en el resto
    son idénticas. Funciona como guard: si alguien revierte la producción al
    loop OLD, esta prueba falla ruidosamente.
    """
    old_rvol = _old_low_mask(thresholds["rvol"], thresholds["min_rvol_dynamic"])
    new_rvol = vectorized_low_mask(thresholds["rvol"], thresholds["min_rvol_dynamic"])
    old_adr = _old_low_mask(thresholds["adr_pct"], thresholds["min_adr_dynamic"])
    new_adr = vectorized_low_mask(thresholds["adr_pct"], thresholds["min_adr_dynamic"])
    old_stop = _old_wide_stop_mask(
        thresholds["stop_dist"], thresholds["max_stop_pct_dynamic"], STATIC_MAX_STOP
    )
    new_stop = vectorized_wide_stop_mask(
        thresholds["stop_dist"], thresholds["max_stop_pct_dynamic"], STATIC_MAX_STOP
    )

    rvol_diff = old_rvol != new_rvol
    adr_diff = old_adr != new_adr
    stop_diff = old_stop != new_stop

    # El delta aparece exactamente en los huecos forward (no en leading/reverse).
    rvol_diff_dates = set(rvol_diff.index[rvol_diff.any(axis=1)])
    assert rvol_diff_dates == {
        pd.Timestamp("2026-01-19"),
        pd.Timestamp("2026-02-16"),
        pd.Timestamp("2026-03-18"),
        pd.Timestamp("2026-04-03"),
    }
    adr_diff_dates = set(adr_diff.index[adr_diff.any(axis=1)])
    assert adr_diff_dates == {
        pd.Timestamp("2026-01-19"),
        pd.Timestamp("2026-02-16"),
        pd.Timestamp("2026-03-18"),
    }
    stop_diff_dates = set(stop_diff.index[stop_diff.any(axis=1)])
    assert stop_diff_dates == {
        pd.Timestamp("2026-02-16"),
        pd.Timestamp("2026-03-18"),
    }

    # Conteo de celdas que difieren (old False -> new True) por máscara.
    assert int(rvol_diff.sum().sum()) == 6
    assert int(adr_diff.sum().sum()) == 3
    assert int(stop_diff.sum().sum()) == 2

    # En fechas SIN hueco los umbrales dinámicos coinciden exactamente.
    non_gap = [d for d in thresholds["rvol"].index if d not in GAP_DATES]
    assert not rvol_diff.loc[non_gap].any().any()
    assert not adr_diff.loc[non_gap].any().any()
    assert not stop_diff.loc[non_gap].any().any()


def test_new_pins_forward_looking_regime_behavior(thresholds):
    """
    DECISIÓN: fija NEW (ffill) como correcto. Un umbral de régimen estricto debe
    seguir bloqueando en el día bursátil siguiente aunque falte la fecha en el
    índice dinámico (feriado / dato faltante): el régimen sigue vigente.
    """
    new_rvol = vectorized_low_mask(thresholds["rvol"], thresholds["min_rvol_dynamic"])
    new_adr = vectorized_low_mask(thresholds["adr_pct"], thresholds["min_adr_dynamic"])
    new_stop = vectorized_wide_stop_mask(
        thresholds["stop_dist"], thresholds["max_stop_pct_dynamic"], STATIC_MAX_STOP
    )

    # Hueco por feriado dentro del régimen estricto: el umbral estricto persiste.
    holiday = pd.Timestamp("2026-02-16")
    assert bool(new_rvol.loc[holiday, "AAA"])  # 1.3 < 2.0 (heredado)
    assert bool(new_rvol.loc[holiday, "BBB"])  # 1.6 < 2.0 (heredado)
    assert not bool(new_rvol.loc[holiday, "CCC"])  # 2.5 >= 2.0
    assert bool(new_adr.loc[holiday, "AAA"])  # 2.5 < 3.0 (heredado)
    assert bool(new_stop.loc[holiday, "BBB"])  # 0.06 > 0.05 (heredado)

    # Hueco aleatorio dentro del régimen estricto: mismo comportamiento.
    random_gap = pd.Timestamp("2026-03-18")
    assert bool(new_rvol.loc[random_gap, "BBB"])  # 0.8 < 2.0
    assert bool(new_stop.loc[random_gap, "AAA"])  # 0.06 > 0.05

    # Hueco al final de la muestra: el último régimen persiste.
    trailing = pd.Timestamp("2026-04-03")
    assert bool(new_rvol.loc[trailing, "BBB"])  # 0.9 < 1.0 (heredado relajado)

    # Contraste explícito con OLD: en los mismos huecos OLD deja pasar.
    old_rvol = _old_low_mask(thresholds["rvol"], thresholds["min_rvol_dynamic"])
    old_stop = _old_wide_stop_mask(
        thresholds["stop_dist"], thresholds["max_stop_pct_dynamic"], STATIC_MAX_STOP
    )
    assert not bool(old_rvol.loc[holiday, "AAA"])  # OLD no aplica umbral
    assert not bool(old_stop.loc[holiday, "BBB"])  # OLD usa el estático 0.08


def test_reverse_edge_date_does_not_leak_into_ffill(thresholds):
    """
    Edge case inverso: una fecha que está en el índice dinámico pero NO en el
    principal (p. ej. sábado) no debe colarse en el ffill. reindex() la descarta
    y la fecha con hueco siguiente hereda el valor del último día en AMBOS índices.
    """
    new_rvol = vectorized_low_mask(thresholds["rvol"], thresholds["min_rvol_dynamic"])
    old_rvol = _old_low_mask(thresholds["rvol"], thresholds["min_rvol_dynamic"])

    # Si el valor anómalo (5.0) del sábado se colara, CCC (2.5) quedaría bloqueado.
    holiday = pd.Timestamp("2026-02-16")
    assert not bool(new_rvol.loc[holiday, "CCC"])
    assert not bool(old_rvol.loc[holiday, "CCC"])

    # En la fecha del hueco ambos algoritmos usan el umbral del viernes (2.0).
    assert bool(new_rvol.loc[holiday, "AAA"])  # 1.3 < 2.0 -> bloqueado
    assert not bool(old_rvol.loc[holiday, "AAA"])  # OLD no aplica umbral


def test_leading_dates_have_no_lookahead(thresholds):
    """
    Fechas iniciales anteriores al primer umbral dinámico: ni OLD ni NEW deben
    bloquear (reindex+ffill deja NaN -> comparación False; OLD no tiene umbral).
    Esto garantiza que el ffill no produce lookahead hacia atrás.
    """
    new_rvol = vectorized_low_mask(thresholds["rvol"], thresholds["min_rvol_dynamic"])
    old_rvol = _old_low_mask(thresholds["rvol"], thresholds["min_rvol_dynamic"])
    new_stop = vectorized_wide_stop_mask(
        thresholds["stop_dist"], thresholds["max_stop_pct_dynamic"], STATIC_MAX_STOP
    )

    for date in LEADING_GAP_DATES:
        assert not new_rvol.loc[date].any()  # sin bloqueo -> sin lookahead
        assert not old_rvol.loc[date].any()
    # Para stop, el ffill fallback al estático coincide con OLD en las fechas leading.
    new_stop_leading = new_stop.loc[list(LEADING_GAP_DATES)]
    old_stop_leading = _old_wide_stop_mask(
        thresholds["stop_dist"], thresholds["max_stop_pct_dynamic"], STATIC_MAX_STOP
    ).loc[list(LEADING_GAP_DATES)]
    assert new_stop_leading.equals(old_stop_leading)
    assert not new_stop_leading.any().any()  # 0.03 > 0.08 es falso en ambos
