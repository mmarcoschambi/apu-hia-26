"""Tests de Pipeline B: Time Bars + Vol Buzz (Z-Score) + AVWAP + Signal B.

Contrato bajo test (todos los valores esperados están calculados a mano):
- ``build_time_bars`` remuestrea ticks a velas de T minutos sobre una grilla
  anclada al reloj (buckets [k*T, (k+1)*T)), con etiqueta left y borde
  inferior inclusivo. La vela parcial final SE CONSERVA (misma política que
  las barras parciales del slice 1) y los buckets sin datos no se emiten.
- ``compute_vol_buzz_z`` agrupa el volumen por hora-del-día del bucket a lo
  largo de los días previos: Z = (vol_actual - media_previa) / std_previa,
  con std POBLACIONAL (ddof=0). Historia insuficiente (< min_days días
  previos) -> NaN tratado como no-señal; std cero exacto -> z = 0.0. El día
  actual NUNCA entra en su propia estadística (sin fuga temporal).
- ``compute_avwap`` ancla la VWAP en la primera vela de cada día de sesión y
  acumula precio típico * volumen reiniciando cada día; barra sin volumen
  acumulado cae al precio típico propio (fallback documentado).
- ``generate_signal_b`` reutiliza ``compute_bollinger_bands`` del slice 1
  (convención ddof=0 compartida): close > upper_prev Y z > threshold_z Y
  close > avwap, comparaciones ESTRICTAS; null/NaN en cualquier cláusula ->
  False.
"""

from __future__ import annotations

import math
from datetime import date, datetime, time, timedelta

import polars as pl
import pytest

from src.microstructure.time_bars import (
    DEFAULT_THRESHOLD_Z,
    TIME_BAR_OUTPUT_COLUMNS,
    build_time_bars,
    compute_avwap,
    compute_vol_buzz_z,
    generate_signal_b,
)


def _ticks(
    stamps: list[datetime],
    prices: list[float],
    volumes: list[int],
) -> pl.DataFrame:
    """Construye un DF de ticks sintético ya ordenado por timestamp."""
    return pl.DataFrame(
        {
            "Timestamp": stamps,
            "Price": pl.Series(prices, dtype=pl.Float64),
            "Volume": pl.Series(volumes, dtype=pl.Int64),
        }
    )


def _tb_frame(
    bar_timestamps: list[datetime],
    closes: list[float],
    volumes: list[float],
    *,
    highs: list[float] | None = None,
    lows: list[float] | None = None,
    interval_minutes: int = 5,
) -> pl.DataFrame:
    """Construye un DF de time bars tipado para tests de features derivadas."""
    highs = highs if highs is not None else list(closes)
    lows = lows if lows is not None else list(closes)
    ends = [ts + timedelta(minutes=interval_minutes) for ts in bar_timestamps]
    return pl.DataFrame(
        {
            "bar_timestamp": bar_timestamps,
            "end_timestamp": ends,
            "open": list(closes),
            "high": highs,
            "low": lows,
            "close": pl.Series(closes, dtype=pl.Float64),
            "volume": pl.Series(volumes, dtype=pl.Float64),
        }
    )


# ---------------------------------------------------------------------------
# build_time_bars — remuestreo
# ---------------------------------------------------------------------------


def test_resampling_boundaries_hand_computed() -> None:
    """Grilla T=5 con valores calculados a mano.

    Ticks NY: (09:31,100,v10)(09:34:59,102,v5) | (09:35:00,103,v8)
              | (09:40,101,v4)(09:41,104,v2)
    - El tick 09:34:59 cae en el bucket [09:30,09:35); el 09:35:00 abre el
      bucket siguiente (borde izquierdo inclusivo).
    - Vela final [09:40,09:45) queda parcial pero SE CONSERVA.
    """
    base = datetime(2024, 1, 8)
    stamps = [
        base.replace(hour=9, minute=31),
        base.replace(hour=9, minute=34, second=59),
        base.replace(hour=9, minute=35),
        base.replace(hour=9, minute=40),
        base.replace(hour=9, minute=41),
    ]
    ticks = _ticks(stamps, [100.0, 102.0, 103.0, 101.0, 104.0], [10, 5, 8, 4, 2])

    bars = build_time_bars(ticks, bar_minutes=5)

    assert bars.columns == list(TIME_BAR_OUTPUT_COLUMNS)
    assert len(bars) == 3

    b0 = bars.row(0, named=True)
    assert b0["bar_timestamp"] == base.replace(hour=9, minute=30)
    assert b0["end_timestamp"] == base.replace(hour=9, minute=35)
    assert (b0["open"], b0["high"], b0["low"], b0["close"]) == (
        100.0,
        102.0,
        100.0,
        102.0,
    )
    assert b0["volume"] == 15

    b1 = bars.row(1, named=True)
    assert b1["bar_timestamp"] == base.replace(hour=9, minute=35)
    assert b1["end_timestamp"] == base.replace(hour=9, minute=40)
    assert (b1["open"], b1["high"], b1["low"], b1["close"]) == (103.0,) * 4
    assert b1["volume"] == 8

    b2 = bars.row(2, named=True)
    assert b2["bar_timestamp"] == base.replace(hour=9, minute=40)
    assert b2["end_timestamp"] == base.replace(hour=9, minute=45)
    assert (b2["open"], b2["high"], b2["low"], b2["close"]) == (
        101.0,
        104.0,
        101.0,
        104.0,
    )
    assert b2["volume"] == 6


def test_trailing_partial_candle_is_kept_and_empty_buckets_are_sparse() -> None:
    """La vela parcial final se conserva; los buckets vacíos NO se emiten."""
    base = datetime(2024, 3, 5)
    # Solo dos ticks dentro de [10:00,10:05); nada después: la grilla sigue
    # hasta el cierre pero no hay datos -> ninguna vela adicional.
    stamps = [
        base.replace(hour=10, minute=1),
        base.replace(hour=10, minute=4),
    ]
    ticks = _ticks(stamps, [50.0, 51.5], [7, 3])

    bars = build_time_bars(ticks, bar_minutes=5)

    assert len(bars) == 1
    only = bars.row(0, named=True)
    assert only["bar_timestamp"] == base.replace(hour=10)
    assert only["end_timestamp"] == base.replace(hour=10, minute=5)
    assert only["volume"] == 10
    assert only["close"] == 51.5


def test_bar_minutes_configurable_grid_alignment() -> None:
    """T configurable fuera de {5}: con T=3 la grilla cae en 09:30/09:33.

    Ticks NY 09:30(v1),09:32(v2) | 09:33(v4),09:35(v8): dos buckets, el
    segundo con etiqueta 09:33 y fin 09:36.
    """
    base = datetime(2024, 1, 8)
    stamps = [
        base.replace(hour=9, minute=30),
        base.replace(hour=9, minute=32),
        base.replace(hour=9, minute=33),
        base.replace(hour=9, minute=35),
    ]
    ticks = _ticks(stamps, [10.0, 11.0, 12.0, 13.0], [1, 2, 4, 8])

    bars = build_time_bars(ticks, bar_minutes=3)

    assert len(bars) == 2
    assert bars["bar_timestamp"].to_list() == [
        base.replace(hour=9, minute=30),
        base.replace(hour=9, minute=33),
    ]
    assert bars["end_timestamp"].to_list() == [
        base.replace(hour=9, minute=33),
        base.replace(hour=9, minute=36),
    ]
    assert bars["volume"].to_list() == [3, 12]
    assert bars["close"].to_list() == [11.0, 13.0]


def test_session_date_follows_bucket_label_not_last_tick() -> None:
    """session_date proviene del día calendario del bucket (etiqueta)."""
    day = datetime(2024, 1, 8)
    stamps = [
        day.replace(hour=15, minute=58),
        day.replace(hour=15, minute=59, second=30),
    ]
    ticks = _ticks(stamps, [20.0, 21.0], [1, 1])

    bars = build_time_bars(ticks, bar_minutes=5)

    assert len(bars) == 1
    assert bars["session_date"].to_list() == [date(2024, 1, 8)]


def test_empty_ticks_return_empty_typed_bars() -> None:
    """Entrada vacía -> salida vacía pero tipada (precondición explícita)."""
    empty = pl.DataFrame(
        schema={
            "Timestamp": pl.Datetime("us"),
            "Price": pl.Float64,
            "Volume": pl.Int64,
        }
    )

    bars = build_time_bars(empty, bar_minutes=5)

    assert isinstance(bars, pl.DataFrame)
    assert bars.columns == list(TIME_BAR_OUTPUT_COLUMNS)
    assert len(bars) == 0


def test_missing_required_tick_column_raises() -> None:
    """Falta una columna obligatoria del tick -> ValueError."""
    bad = pl.DataFrame({"Timestamp": [datetime(2024, 1, 8)], "Price": [1.0]})

    with pytest.raises(ValueError):
        build_time_bars(bad, bar_minutes=5)


@pytest.mark.parametrize("bad_interval", [0, -5])
def test_non_positive_bar_minutes_raises(bad_interval: int) -> None:
    """Intervalo T <= 0 es inválido -> ValueError."""
    ticks = _ticks([datetime(2024, 1, 8, 9, 31)], [10.0], [5])

    with pytest.raises(ValueError):
        build_time_bars(ticks, bar_minutes=bad_interval)


# ---------------------------------------------------------------------------
# compute_vol_buzz_z — Z-Score por minuto-del-día
# ---------------------------------------------------------------------------


def _buzz_fixture_volumes() -> tuple[list[datetime], list[float]]:
    """3 días x 2 buckets (10:00 y 10:05), volúmenes elegidos a mano.

    Bucket 10:00: d1=100, d2=200, d3=250.
    Bucket 10:05: d1=d2=d3=50 (std histórica cero desde el día 3).
    """
    stamps: list[datetime] = []
    volumes: list[float] = []
    plan = [
        (date(2024, 1, 8), [(time(10, 0), 100.0), (time(10, 5), 50.0)]),
        (date(2024, 1, 9), [(time(10, 0), 200.0), (time(10, 5), 50.0)]),
        (date(2024, 1, 10), [(time(10, 0), 250.0), (time(10, 5), 50.0)]),
    ]
    for session_day, rows in plan:
        for bucket_time, volume in rows:
            stamps.append(datetime.combine(session_day, bucket_time))
            volumes.append(volume)
    return stamps, volumes


def test_volume_buzz_z_matches_hand_computed_values() -> None:
    """Z calculado a mano con min_days=2 (std ddof=0).

    Bucket 10:00 día 3: previos=[100,200]; media=150;
    var=((100-150)^2+(200-150)^2)/2=2500 -> std=50; Z=(250-150)/50=2.0.
    Días 1-2 de ambos buckets y día 2 con 1 solo previo -> NaN.
    """
    stamps, volumes = _buzz_fixture_volumes()
    tb = _tb_frame(stamps, [10.0] * 6, volumes)

    z = compute_vol_buzz_z(tb, min_days=2)

    expected = [float("nan"), float("nan"), float("nan"), float("nan"), 2.0, 0.0]
    assert z.name == "vol_buzz_z"
    for got, want in zip(z.to_list(), expected):
        if math.isnan(want):
            assert math.isnan(got)
        else:
            assert got == pytest.approx(want)


def test_volume_buzz_zero_std_returns_exact_zero() -> None:
    """Std histórica cero (volúmenes idénticos) -> z = 0.0, nunca NaN/inf."""
    stamps, volumes = _buzz_fixture_volumes()
    tb = _tb_frame(stamps, [10.0] * 6, volumes)

    z = compute_vol_buzz_z(tb, min_days=2)

    assert z.to_list()[5] == 0.0


def test_volume_buzz_min_days_one_uses_population_std_of_single_obs() -> None:
    """min_days=1: un único día previo basta y std(ddof=0)=0 -> z=0.0.

    Fija la convención poblacional: con UNA observación previa el desvío es
    exactamente 0 (no NaN como en ddof=1).
    """
    stamps, volumes = _buzz_fixture_volumes()
    tb = _tb_frame(stamps, [10.0] * 6, volumes)

    z = compute_vol_buzz_z(tb, min_days=1)

    got = z.to_list()
    assert math.isnan(got[0]) and math.isnan(got[1])
    assert got[2] == pytest.approx(0.0)
    assert got[3] == pytest.approx(0.0)
    assert got[4] == pytest.approx(2.0)
    assert got[5] == pytest.approx(0.0)


def test_volume_buzz_default_min_days_marks_thin_history_as_nan() -> None:
    """Con el default MIN_DAYS del módulo, 2 días de historia son pocos.

    Pin del comportamiento por defecto: toda la serie sale en NaN cuando la
    historia disponible es menor al mínimo configurado globalmente.
    """
    stamps = [
        datetime(2024, 1, 8, 10, 0),
        datetime(2024, 1, 9, 10, 0),
    ]
    tb = _tb_frame(stamps, [10.0, 11.0], [100.0, 300.0])

    z = compute_vol_buzz_z(tb)

    assert all(math.isnan(value) for value in z.to_list())


def test_volume_buzz_on_empty_bars_is_empty_float_series() -> None:
    """Barras vacías -> serie Float64 vacía nombrada (precondición explícita)."""
    empty = pl.DataFrame(schema={"bar_timestamp": pl.Datetime("us"), "volume": pl.Float64})

    z = compute_vol_buzz_z(empty, min_days=1)

    assert isinstance(z, pl.Series)
    assert z.dtype == pl.Float64
    assert z.name == "vol_buzz_z"
    assert len(z) == 0


def test_volume_buzz_missing_column_raises() -> None:
    """Sin columna 'volume' en las barras -> ValueError."""
    bad = pl.DataFrame({"bar_timestamp": [datetime(2024, 1, 8, 10, 0)]})

    with pytest.raises(ValueError):
        compute_vol_buzz_z(bad, min_days=1)


# ---------------------------------------------------------------------------
# compute_avwap — VWAP anclada al open RTH de cada día
# ---------------------------------------------------------------------------


def test_avwap_accumulates_within_day_hand_computed() -> None:
    """Acumulación intradía calculada a mano con precio típico (H+L+C)/3.

    b1 10:00 flat 100 v10 -> typ=100, avwap=100.
    b2 10:05 H=110 L=105 C=110 v10 -> typ=108.333...;
       avwap=(100*10 + (325/3)*10) / 20 = 104.16666...
    """
    day = datetime(2024, 1, 8)
    tb = _tb_frame(
        [day.replace(hour=10), day.replace(hour=10, minute=5)],
        [100.0, 110.0],
        [10.0, 10.0],
        highs=[100.0, 110.0],
        lows=[100.0, 105.0],
    )

    avwap = compute_avwap(tb)

    assert avwap.name == "avwap"
    assert avwap[0] == pytest.approx(100.0)
    assert avwap[1] == pytest.approx(2083.333333333333 / 20)


def test_avwap_resets_each_new_session() -> None:
    """La ancla se reinicia cada día de sesión: día 2 ignora al día 1."""
    day1 = datetime(2024, 1, 8, 10, 0)
    day2 = datetime(2024, 1, 9, 10, 0)
    tb = _tb_frame([day1, day1.replace(minute=5), day2], [100.0, 120.0, 90.0], [10.0, 10.0, 5.0])

    avwap = compute_avwap(tb)

    # Día 1 acumula: (100*10 + 120*10)/20 = 110. Día 2 arranca fresco en 90.
    assert avwap[1] == pytest.approx(110.0)
    assert avwap[2] == pytest.approx(90.0)


def test_avwap_zero_cumulative_volume_falls_back_to_typical_price() -> None:
    """Primera barra del día con volumen 0 -> avwap = precio típico propio."""
    day = datetime(2024, 1, 8, 10, 0)
    tb = _tb_frame([day], [99.0], [0.0], highs=[101.0], lows=[98.0])

    avwap = compute_avwap(tb)

    assert avwap[0] == pytest.approx((101.0 + 98.0 + 99.0) / 3)


def test_avwap_on_empty_bars_is_empty_float_series() -> None:
    """Barras vacías -> serie Float64 vacía nombrada (precondición explícita)."""
    empty = pl.DataFrame(
        schema={
            "bar_timestamp": pl.Datetime("us"),
            "high": pl.Float64,
            "low": pl.Float64,
            "close": pl.Float64,
            "volume": pl.Float64,
        }
    )

    avwap = compute_avwap(empty)

    assert isinstance(avwap, pl.Series)
    assert avwap.dtype == pl.Float64
    assert avwap.name == "avwap"
    assert len(avwap) == 0


# ---------------------------------------------------------------------------
# generate_signal_b — ruptura condicionada
# ---------------------------------------------------------------------------


def _enriched_for_signals(
    closes: list[float],
    z_values: list[float],
    avwap_values: list[float],
) -> pl.DataFrame:
    """Frame enriquecido (z y avwap adjuntos) con timestamps sintéticos."""
    start = datetime(2024, 1, 8, 9, 30)
    stamps = [start + timedelta(minutes=5 * i) for i in range(len(closes))]
    frame = _tb_frame(stamps, closes, [100.0] * len(closes))
    return frame.with_columns(
        pl.Series("vol_buzz_z", z_values, dtype=pl.Float64),
        pl.Series("avwap", avwap_values, dtype=pl.Float64),
    )


def test_signal_b_true_only_when_all_conditions_hold() -> None:
    """Closes [2,4,6,8,10], P=3 D=1, z=[NaN,NaN,NaN,3,0.5], avwap=5.

    - i0..i2: warmup (upper_prev nulo y z NaN) -> False.
    - i3: 8>5.632993 (banda previa), z=3>2, 8>5 (avwap) -> True.
    - i4: banda y avwap pasan pero z=0.5<2 -> False (rechazo SOLO por z).
    """
    tb = _enriched_for_signals(
        [2.0, 4.0, 6.0, 8.0, 10.0],
        [float("nan"), float("nan"), float("nan"), 3.0, 0.5],
        [5.0] * 5,
    )

    signal = generate_signal_b(tb, period=3, num_std=1.0)

    assert signal.name == "signal_b"
    assert signal.to_list() == [False, False, False, True, False]


def test_signal_b_rejects_when_below_previous_upper_band() -> None:
    """i5 close=9.5 < upper_prev(i4)=9.632993: falla SOLO la cláusula banda
    (z=3 pasa, avwap pasa) -> False aislado."""
    tb = _enriched_for_signals(
        [2.0, 4.0, 6.0, 8.0, 10.0, 9.5],
        [float("nan"), float("nan"), float("nan"), 3.0, 3.0, 3.0],
        [5.0] * 6,
    )

    signal = generate_signal_b(tb, period=3, num_std=1.0)

    assert signal.to_list()[-1] is False


def test_signal_b_rejects_nan_z_even_with_valid_band_and_avwap() -> None:
    """i6: banda previa válida (12>10.016504) y avwap ok, pero z=NaN ->
    False: NaN se trata como no-señal, nunca como señal."""
    tb = _enriched_for_signals(
        [2.0, 4.0, 6.0, 8.0, 10.0, 9.5, 12.0],
        [float("nan")] * 6 + [float("nan")],
        [5.0, 5.0, 5.0, 5.0, 5.0, 5.0, 11.0],
    )

    signal = generate_signal_b(tb, period=3, num_std=1.0)

    assert signal.to_list()[6] is False


def test_signal_b_rejects_when_not_above_avwap() -> None:
    """i5: banda y z pasan pero close=12 < avwap=20 -> False aislado."""
    tb = _enriched_for_signals(
        [2.0, 4.0, 6.0, 8.0, 10.0, 12.0],
        [float("nan"), float("nan"), float("nan"), 3.0, 3.0, 3.0],
        [5.0, 5.0, 5.0, 5.0, 5.0, 20.0],
    )

    signal = generate_signal_b(tb, period=3, num_std=1.0)

    got = signal.to_list()
    assert got[4] is True
    assert got[5] is False


def test_signal_b_threshold_z_is_configurable() -> None:
    """Bajar threshold_z a 0.25 convierte el rechazo por z en True."""
    tb = _enriched_for_signals(
        [2.0, 4.0, 6.0, 8.0, 10.0],
        [float("nan"), float("nan"), float("nan"), 3.0, 0.5],
        [5.0] * 5,
    )

    signal = generate_signal_b(tb, period=3, num_std=1.0, threshold_z=0.25)

    assert signal.to_list() == [False, False, False, True, True]


def test_signal_b_uses_strict_inequalities_at_boundaries() -> None:
    """Igualdad EXACTA no dispara: z==threshold ni close==avwap valen."""
    # Caso A: z exactamente igual al threshold (2.0) con todo lo demás ok.
    equal_z = _enriched_for_signals(
        [2.0, 4.0, 6.0, 8.0],
        [float("nan"), float("nan"), float("nan"), 2.0],
        [5.0] * 4,
    )
    assert bool(generate_signal_b(equal_z, period=3, num_std=1.0)[3]) is False

    # Caso B: close exactamente igual al avwap con banda y z ok.
    equal_avwap = _enriched_for_signals(
        [2.0, 4.0, 6.0, 8.0],
        [float("nan"), float("nan"), float("nan"), 3.0],
        [5.0, 5.0, 5.0, 8.0],
    )
    assert bool(generate_signal_b(equal_avwap, period=3, num_std=1.0)[3]) is False


def test_signal_b_default_threshold_is_named_constant() -> None:
    """El default de threshold_z proviene de la constante nombrada del módulo."""
    assert DEFAULT_THRESHOLD_Z > 0

    tb = _enriched_for_signals(
        [2.0, 4.0, 6.0, 8.0, 10.0],
        [float("nan"), float("nan"), float("nan"), DEFAULT_THRESHOLD_Z + 1.0, DEFAULT_THRESHOLD_Z - 1.0],
        [5.0] * 5,
    )
    signal_default = generate_signal_b(tb, period=3, num_std=1.0)
    signal_explicit = generate_signal_b(
        tb, period=3, num_std=1.0, threshold_z=DEFAULT_THRESHOLD_Z
    )

    assert signal_default.to_list() == signal_explicit.to_list()


def test_signal_b_missing_enrichment_columns_raise() -> None:
    """Falta 'vol_buzz_z' o 'avwap' -> ValueError con las columnas justas."""
    raw_tb = _tb_frame(
        [datetime(2024, 1, 8, 9, 30)], [10.0], [100.0]
    )

    with pytest.raises(ValueError):
        generate_signal_b(raw_tb, period=3, num_std=2.0)

    missing_avwap = raw_tb.with_columns(pl.Series("vol_buzz_z", [1.0]))
    with pytest.raises(ValueError):
        generate_signal_b(missing_avwap, period=3, num_std=2.0)


def test_signal_b_on_empty_bars_is_empty_boolean_series() -> None:
    """Barras vacías enriquecidas -> serie booleana vacía."""
    empty = pl.DataFrame(
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

    signal = generate_signal_b(empty, period=3, num_std=2.0)

    assert isinstance(signal, pl.Series)
    assert signal.dtype == pl.Boolean
    assert signal.name == "signal_b"
    assert len(signal) == 0
