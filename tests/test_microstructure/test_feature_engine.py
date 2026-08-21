"""Tests del feature engine: extracción de features en instantes de ruptura.

Contrato bajo test (todos los valores esperados están calculados a mano):
- Filas = TODOS los instantes de ruptura de precio crudos (cláusula de banda
  de Bollinger de cada pipeline SIN sus filtros de validación extra), unión
  de Pipeline A y Pipeline B, deduplicada por timestamp con prioridad A.
- ``dist_to_last_volbar_close_pct``: origen A -> (close_i - close_{i-1}) /
  close_{i-1} * 100; origen B -> (close_time_bar - último cierre de barra de
  volumen completada <= instante) / ese cierre * 100 (join as-of backward).
- ``volbar_speed_ms``: end - start en milisegundos si el frame trae la
  columna opcional start_timestamp; si no, proxy documentado = diferencia de
  timestamps consecutivos de cierre. Origen B hereda la velocidad de la
  barra de volumen referenciada.
- ``vol_buzz_z`` / ``dist_vs_avwap_pct``: tomados de la ÚLTIMA time bar
  COMPLETADA (end_timestamp <= instante), join as-of backward.
- ``recent_adr_pct``: media móvil de N días PREVIOS del rango diario
  (high-low)/cierre_último * 100 sobre time bars; PIT estricto: el día del
  instante jamás entra en su propia media.
- Contexto: frame opcional con columna 'timestamp' y columnas libres
  (RS, health_score...) unido por join as-of backward, nombres preservados.
"""

from __future__ import annotations

import math
from datetime import datetime, timedelta

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
    build_feature_frame,
)


def _vb_frame(
    starts: list[datetime] | None,
    ends: list[datetime],
    closes: list[float],
    volumes: list[float] | None = None,
) -> pl.DataFrame:
    """Construye un DF de barras de volumen; start_timestamp es OPCIONAL."""
    data: dict[str, object] = {
        "end_timestamp": ends,
        "open": list(closes),
        "high": list(closes),
        "low": list(closes),
        "close": pl.Series(closes, dtype=pl.Float64),
        "volume": pl.Series(volumes if volumes is not None else [100.0] * len(closes)),
    }
    if starts is not None:
        data["start_timestamp"] = starts
    return pl.DataFrame(data)


def _tb_enriched(
    rows: list[dict[str, float | datetime]],
) -> pl.DataFrame:
    """Construye un DF de time bars enriquecido a partir de dicts por fila."""
    return pl.DataFrame(rows).sort("bar_timestamp")


def _main_vb() -> pl.DataFrame:
    """Barras A: cierres [100,102,105,106], ruptura solo en i3 (a mano).

    P=3 D=1: upper[2]=102.333333+sqrt(((2.333)^2+(0.333)^2+(2.667)^2)/3)
            =104.388138 < 106. Velocidad i3 = end-start = 30 s = 30000 ms.
    """
    day = datetime(2024, 1, 8)
    return _vb_frame(
        starts=[
            day.replace(hour=9, minute=58),
            day.replace(hour=9, minute=59, second=30),
            day.replace(hour=10, minute=2),
            day.replace(hour=10, minute=3),
        ],
        ends=[
            day.replace(hour=10),
            day.replace(hour=10, minute=1),
            day.replace(hour=10, minute=3),
            day.replace(hour=10, minute=3, second=30),
        ],
        closes=[100.0, 102.0, 105.0, 106.0],
    )


def _main_tb() -> pl.DataFrame:
    """Time bars enriquecidas: cierres [100,100,100,100,110], ruptura solo i4.

    P=3 D=1 sobre serie plana: upper=100 y la comparación es ESTRICTA, así
    que i2/i3 no rompen (100 > 100 es False); solo i4 (110 > upper[3]=100).
    Las velas b0..b3 cierran ANTES del instante A (10:03:30) para que el
    join as-of encuentre una vela completada con z=NaN y avwap=100.
    """
    day = datetime(2024, 1, 8)
    flat_rows = []
    plan_flat = [(9, 40), (9, 45), (9, 50), (9, 55)]
    for hour, minute in plan_flat:
        start = day.replace(hour=hour, minute=minute)
        flat_rows.append(
            {
                "bar_timestamp": start,
                "end_timestamp": start + timedelta(minutes=5),
                "open": 100.0,
                "high": 100.5,
                "low": 99.5,
                "close": 100.0,
                "volume": 10.0,
                "vol_buzz_z": float("nan"),
                "avwap": 100.0,
            }
        )
    breakout_row = {
        "bar_timestamp": day.replace(hour=10, minute=15),
        "end_timestamp": day.replace(hour=10, minute=20),
        "open": 100.0,
        "high": 110.5,
        "low": 100.0,
        "close": 110.0,
        "volume": 16.0,
        "vol_buzz_z": 3.0,
        "avwap": 102.0,
    }
    return _tb_enriched([*flat_rows, breakout_row])


# ---------------------------------------------------------------------------
# Unión de instantes + features principales
# ---------------------------------------------------------------------------


def test_union_of_breakout_instants_from_both_pipelines_sorted() -> None:
    """Fixture principal: dos instantes (A y B) ordenados y bien poblados.

    Fila 10:03:30 (origen A): dist A=(106-105)/105*100=0.952381;
        velocidad=30000 ms; as-of tb -> vela completada 10:00
        (z NaN, avwap 100) => dist_avwap=(100-100)/100*100=0.0.
    Fila 10:20 (origen B, vela i4 del fixture): referencia vb close 106
        y cierre tb 110 => dist=(110-106)/106*100=3.773585;
        velocidad heredada de la barra referenciada = 30000 ms;
        as-of tb -> la propia vela (z 3.0)
        => dist_avwap=(110-102)/102*100=7.843137.
    """
    frame = build_feature_frame(
        _main_vb(),
        _main_tb(),
        bb_period_a=3,
        bb_num_std_a=1.0,
        bb_period_b=3,
        bb_num_std_b=1.0,
    )

    assert frame.columns == list(FEATURE_OUTPUT_COLUMNS)
    assert len(frame) == 2
    assert frame[FEATURE_TIMESTAMP].to_list() == [
        datetime(2024, 1, 8, 10, 3, 30),
        datetime(2024, 1, 8, 10, 20),
    ]

    row_a = frame.row(0, named=True)
    assert row_a[FEATURE_DIST_LAST_VOLBAR_CLOSE_PCT] == pytest.approx(100.0 / 105)
    assert row_a[FEATURE_VOLBAR_SPEED_MS] == pytest.approx(30000.0)
    assert math.isnan(row_a[FEATURE_VOL_BUZZ_Z])
    assert row_a[FEATURE_DIST_VS_AVWAP_PCT] == pytest.approx(0.0)

    row_b = frame.row(1, named=True)
    assert row_b[FEATURE_DIST_LAST_VOLBAR_CLOSE_PCT] == pytest.approx(400.0 / 106)
    assert row_b[FEATURE_VOLBAR_SPEED_MS] == pytest.approx(30000.0)
    assert row_b[FEATURE_VOL_BUZZ_Z] == pytest.approx(3.0)
    assert row_b[FEATURE_DIST_VS_AVWAP_PCT] == pytest.approx(800.0 / 102)


def test_identical_instant_deduplicates_with_pipeline_a_priority() -> None:
    """Si A y B rompen en el MISMO timestamp queda UNA fila con features A."""
    day = datetime(2024, 1, 8)
    ends = [
        day.replace(hour=9, minute=31),
        day.replace(hour=9, minute=32),
        day.replace(hour=9, minute=33),
        day.replace(hour=9, minute=34),
        day.replace(hour=9, minute=35),
    ]
    vb = _vb_frame(starts=None, ends=ends, closes=[2.0, 4.0, 6.0, 8.0, 10.0])
    tb = _tb_enriched(
        [
            {
                "bar_timestamp": end - timedelta(minutes=1),
                "end_timestamp": end,
                "open": c,
                "high": c,
                "low": c,
                "close": c,
                "volume": 100.0,
                "vol_buzz_z": 3.0,
                "avwap": 1.0,
            }
            for end, c in zip(ends, [2.0, 4.0, 6.0, 8.0, 10.0])
        ]
    )

    frame = build_feature_frame(vb, tb, bb_period_a=3, bb_num_std_a=1.0, bb_period_b=3, bb_num_std_b=1.0)

    assert len(frame) == 2
    assert frame[FEATURE_TIMESTAMP].to_list() == [ends[3], ends[4]]
    # Features de origen A: distancia contra el cierre previo del pipeline A.
    assert frame[FEATURE_DIST_LAST_VOLBAR_CLOSE_PCT].to_list()[0] == pytest.approx(200.0 / 6)
    assert frame[FEATURE_DIST_LAST_VOLBAR_CLOSE_PCT].to_list()[1] == pytest.approx(200.0 / 8)


def test_speed_falls_back_to_diff_of_end_timestamps_without_start_column() -> None:
    """Sin start_timestamp: proxy = end[i]-end[i-1]; aquí 10:05-10:02=180000ms."""
    day = datetime(2024, 1, 8)
    vb = _vb_frame(
        starts=None,
        ends=[
            day.replace(hour=10),
            day.replace(hour=10, minute=1),
            day.replace(hour=10, minute=2),
            day.replace(hour=10, minute=5),
        ],
        closes=[100.0, 102.0, 105.0, 106.0],
    )

    frame = build_feature_frame(vb, _main_tb(), bb_period_a=3, bb_num_std_a=1.0)

    a_rows = frame.filter(pl.col(FEATURE_TIMESTAMP) == day.replace(hour=10, minute=5))
    assert len(a_rows) == 1
    assert a_rows[FEATURE_VOLBAR_SPEED_MS][0] == pytest.approx(180000.0)


def test_recent_adr_pct_uses_only_prior_completed_days() -> None:
    """ADR PIT: día del instante excluido; media rolling de N días previos.

    Rangos diarios: d0=(105-95)/100*100=10.0; d1=(112-100)/108*100=11.111111;
    d2 (rango enorme 210-190) NO debe entrar. Instante en d2:
    lookback=1 -> 11.111111; lookback=2 -> media(10, 11.111111)=10.555556.
    """
    rows = []
    plan = [
        (datetime(2024, 1, 8), 105.0, 95.0, 100.0, 5.0),
        (datetime(2024, 1, 9), 112.0, 100.0, 108.0, 5.0),
        (datetime(2024, 1, 10), 210.0, 190.0, 200.0, 10.0),
    ]
    for day_start, high, low, close, volume in plan:
        rows.append(
            {
                "bar_timestamp": day_start.replace(hour=9),
                "end_timestamp": day_start.replace(hour=9, minute=5),
                "open": low,
                "high": high,
                "low": low,
                "close": close,
                "volume": volume,
                "vol_buzz_z": float("nan"),
                "avwap": 1.0,
            }
        )
    tb = _tb_enriched(rows)
    vb = pl.DataFrame(schema={"end_timestamp": pl.Datetime("us"), "close": pl.Float64})

    frame_lb1 = build_feature_frame(vb, tb, bb_period_b=2, bb_num_std_b=0.5, adr_lookback_days=1)
    frame_lb2 = build_feature_frame(vb, tb, bb_period_b=2, bb_num_std_b=0.5, adr_lookback_days=2)

    assert len(frame_lb1) == 1  # única ruptura: la vela de d2 (200 > 177)
    assert frame_lb1[FEATURE_TIMESTAMP][0] == datetime(2024, 1, 10, 9, 5)
    assert frame_lb1[FEATURE_RECENT_ADR_PCT][0] == pytest.approx(1200.0 / 108)
    assert frame_lb2[FEATURE_RECENT_ADR_PCT][0] == pytest.approx((10.0 + 1200.0 / 108) / 2)


# ---------------------------------------------------------------------------
# Inyección opcional de contexto (RS / health_score desde slice 3)
# ---------------------------------------------------------------------------


def test_context_features_join_backward_and_preserve_names() -> None:
    """El frame de contexto se une as-of backward conservando sus nombres."""
    day = datetime(2024, 1, 8)
    vb = _vb_frame(
        starts=[day.replace(hour=7, minute=59), day.replace(hour=8, minute=29), day.replace(hour=8, minute=59)],
        ends=[day.replace(hour=8), day.replace(hour=8, minute=30), day.replace(hour=9)],
        closes=[10.0, 10.0, 20.0],
    )
    tb = _tb_enriched(
        [
            {
                "bar_timestamp": day.replace(hour=8, minute=30),
                "end_timestamp": day.replace(hour=8, minute=30),
                "open": 15.0,
                "high": 16.0,
                "low": 14.0,
                "close": 15.0,
                "volume": 5.0,
                "vol_buzz_z": 1.0,
                "avwap": 14.0,
            }
        ]
    )
    context = pl.DataFrame(
        {
            "timestamp": [day.replace(hour=7), day.replace(hour=8, minute=45)],
            "rs_vs_benchmark": [1.23, -0.5],
            "health_score": [5.0, 7.0],
        }
    )

    frame = build_feature_frame(vb, tb, bb_period_a=2, bb_num_std_a=0.5, context_frame=context)

    assert len(frame) == 1
    row = frame.row(0, named=True)
    # El instante 09:00 toma la última fila de contexto <= instante (08:45).
    assert row["rs_vs_benchmark"] == pytest.approx(-0.5)
    assert row["health_score"] == pytest.approx(7.0)
    assert "_origin" not in frame.columns


def test_context_frame_missing_key_column_raises() -> None:
    """Contexto sin columna 'timestamp' -> ValueError explícito."""
    day = datetime(2024, 1, 8)
    vb = _vb_frame(starts=None, ends=[day.replace(hour=9)], closes=[10.0])
    tb = pl.DataFrame(
        schema={
            "bar_timestamp": pl.Datetime("us"),
            "end_timestamp": pl.Datetime("us"),
            "open": pl.Float64,
            "high": pl.Float64,
            "low": pl.Float64,
            "close": pl.Float64,
            "volume": pl.Float64,
            "vol_buzz_z": pl.Float64,
            "avwap": pl.Float64,
        }
    )
    bad_context = pl.DataFrame({"when": [day.replace(hour=7)], "health_score": [5.0]})

    with pytest.raises(ValueError):
        build_feature_frame(vb, tb, context_frame=bad_context)


# ---------------------------------------------------------------------------
# Errores y entradas vacías
# ---------------------------------------------------------------------------


def test_empty_pipelines_return_typed_empty_feature_frame() -> None:
    """Ambos pipelines vacíos -> salida vacía pero tipada completa."""
    empty_vb = pl.DataFrame(schema={"end_timestamp": pl.Datetime("us"), "close": pl.Float64})
    empty_tb = pl.DataFrame(
        schema={
            "bar_timestamp": pl.Datetime("us"),
            "end_timestamp": pl.Datetime("us"),
            "open": pl.Float64,
            "high": pl.Float64,
            "low": pl.Float64,
            "close": pl.Float64,
            "volume": pl.Float64,
            "vol_buzz_z": pl.Float64,
            "avwap": pl.Float64,
        }
    )

    frame = build_feature_frame(empty_vb, empty_tb)

    assert isinstance(frame, pl.DataFrame)
    assert frame.columns == list(FEATURE_OUTPUT_COLUMNS)
    assert len(frame) == 0


@pytest.mark.parametrize(
    ("broken_side", "column_to_drop"),
    [("volume_bars", "close"), ("time_bars", "vol_buzz_z")],
)
def test_missing_required_columns_raise(broken_side: str, column_to_drop: str) -> None:
    """Faltan columnas obligatorias en cualquiera de los pipelines -> ValueError."""
    day = datetime(2024, 1, 8)
    if broken_side == "volume_bars":
        vb = _vb_frame(starts=None, ends=[day.replace(hour=9)], closes=[10.0]).drop(column_to_drop)
        tb = _main_tb()
    else:
        vb = _vb_frame(starts=None, ends=[day.replace(hour=9)], closes=[10.0])
        tb = _main_tb().drop(column_to_drop)

    with pytest.raises(ValueError):
        build_feature_frame(vb, tb, bb_period_a=3, bb_num_std_a=1.0)
