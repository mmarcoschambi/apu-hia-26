"""Tests de Pipeline A: Volume Bars + Bandas de Bollinger + Signal A.

Contrato bajo test (todos los valores esperados están calculados a mano):
- ``build_volume_bars`` agrupa ticks consecutivos hasta acumular volumen >= V;
  el tick que dispara el cierre pertenece a la barra que cierra (un tick nunca
  se divide entre barras). La última barra parcial (< V al agotarse los ticks)
  SE CONSERVA: política determinista documentada en el módulo.
- ``compute_bollinger_bands`` usa desvío estándar poblacional (ddof=0,
  convención TA-Lib/TradingView) y ventanas incompletas -> null.
- ``generate_signal_a``: close[i] > upper[i-1] Y close[i] > close[i-1]
  (comparaciones ESTRICTAS; sin filtro de volumen). Sin barra previa o con
  banda aún nula -> False.
"""

from __future__ import annotations

from datetime import datetime

import polars as pl
import pytest

from src.microstructure.volume_bars import (
    build_volume_bars,
    compute_bollinger_bands,
    generate_signal_a,
)

BAR_COLUMNS = ["end_timestamp", "open", "high", "low", "close", "volume"]


def _ticks(prices: list[float], volumes: list[int]) -> pl.DataFrame:
    """Construye un DF de ticks sintético con timestamps secuenciales."""
    base = datetime(2024, 1, 10, 14, 30, 0)
    stamps = [base.replace(second=i) for i in range(len(prices))]
    return pl.DataFrame(
        {
            "Timestamp": stamps,
            "Price": pl.Series(prices, dtype=pl.Float64),
            "Volume": pl.Series(volumes, dtype=pl.Int64),
        }
    )


# ---------------------------------------------------------------------------
# build_volume_bars
# ---------------------------------------------------------------------------


def test_volume_threshold_aggregation_exact_ohlcv() -> None:
    """Agregación exacta con V=100 (valores calculados a mano).

    Ticks (precio, volumen): (100,40) (101,30) (99,35) | (102,50) (103,60)
    Barra 0: t0..t2, vol=105>=100 -> O=100 H=101 L=99 C=99
    Barra 1: t3..t4, vol=110>=100 -> O=102 H=103 L=102 C=103
    """
    ticks = _ticks(
        [100.0, 101.0, 99.0, 102.0, 103.0],
        [40, 30, 35, 50, 60],
    )

    bars = build_volume_bars(ticks, volume_threshold=100)

    assert bars.columns == BAR_COLUMNS
    assert len(bars) == 2
    row0 = bars.row(0, named=True)
    assert (row0["open"], row0["high"], row0["low"], row0["close"]) == (
        100.0,
        101.0,
        99.0,
        99.0,
    )
    assert row0["volume"] == 105
    assert row0["end_timestamp"] == datetime(2024, 1, 10, 14, 30, 2)

    row1 = bars.row(1, named=True)
    assert (row1["open"], row1["high"], row1["low"], row1["close"]) == (
        102.0,
        103.0,
        102.0,
        103.0,
    )
    assert row1["volume"] == 110
    assert row1["end_timestamp"] == datetime(2024, 1, 10, 14, 30, 4)


def test_trailing_partial_bar_is_kept() -> None:
    """La barra parcial final (< V) se conserva con su contenido real.

    Se agrega un tick (104, 20) que queda a volumen parcial al agotarse los
    datos: se emite como tercera barra O=H=L=C=104, vol=20 (política
    documentada: conservar, no descartar).
    """
    ticks = _ticks(
        [100.0, 101.0, 99.0, 102.0, 103.0, 104.0],
        [40, 30, 35, 50, 60, 20],
    )

    bars = build_volume_bars(ticks, volume_threshold=100)

    assert len(bars) == 3
    partial = bars.row(2, named=True)
    assert (partial["open"], partial["high"], partial["low"], partial["close"]) == (
        104.0,
        104.0,
        104.0,
        104.0,
    )
    assert partial["volume"] == 20
    assert partial["end_timestamp"] == datetime(2024, 1, 10, 14, 30, 5)


def test_tick_hitting_threshold_exactly_opens_new_bar() -> None:
    """Un tick que deja el acumulado exactamente en V cierra la barra ahí.

    Volúmenes [100, 100]: dos barras de volumen exacto 100, sin mezclar.
    """
    ticks = _ticks([10.0, 11.0], [100, 100])

    bars = build_volume_bars(ticks, volume_threshold=100)

    assert len(bars) == 2
    assert bars["volume"].to_list() == [100, 100]
    assert bars["close"].to_list() == [10.0, 11.0]


def test_oversized_tick_never_splits_across_bars() -> None:
    """Un tick cuyo volumen solo excede V obtiene barra propia.

    Volúmenes [250, 95, 10]: barra0={t0} vol=250; barra1={t1,t2} vol=105.
    Verifica que la numeración interna con huecos no corrompa el agrupado.
    """
    ticks = _ticks([5.0, 6.0, 7.0], [250, 95, 10])

    bars = build_volume_bars(ticks, volume_threshold=100)

    assert len(bars) == 2
    assert bars["volume"].to_list() == [250, 105]
    assert bars["open"].to_list() == [5.0, 6.0]
    assert bars["close"].to_list() == [5.0, 7.0]


def test_empty_ticks_return_empty_bars_with_schema() -> None:
    """Entrada vacía -> salida vacía pero tipada (precondición explícita)."""
    empty = pl.DataFrame(
        schema={
            "Timestamp": pl.Datetime("us"),
            "Price": pl.Float64,
            "Volume": pl.Int64,
        }
    )

    bars = build_volume_bars(empty, volume_threshold=100)

    assert isinstance(bars, pl.DataFrame)
    assert bars.columns == BAR_COLUMNS
    assert len(bars) == 0


def test_zero_total_volume_yields_single_partial_bar() -> None:
    """Ticks con volumen cero nunca alcanzan V -> una sola barra parcial."""
    ticks = _ticks([10.0, 10.5], [0, 0])

    bars = build_volume_bars(ticks, volume_threshold=100)

    assert len(bars) == 1
    only = bars.row(0, named=True)
    assert only["volume"] == 0


def test_missing_required_tick_column_raises() -> None:
    """Falta una columna obligatoria del tick -> ValueError."""
    bad = pl.DataFrame({"Timestamp": [datetime(2024, 1, 10)], "Volume": [1]})

    with pytest.raises(ValueError):
        build_volume_bars(bad, volume_threshold=100)


def test_non_positive_threshold_raises() -> None:
    """Umbral V <= 0 es inválido -> ValueError."""
    ticks = _ticks([10.0], [5])

    with pytest.raises(ValueError):
        build_volume_bars(ticks, volume_threshold=0)


# ---------------------------------------------------------------------------
# compute_bollinger_bands
# ---------------------------------------------------------------------------


def test_bollinger_matches_hand_computed_values() -> None:
    """Bandas vs cálculo manual: closes [2,4,6,8,10], P=3, D=1, ddof=0.

    idx2: media 4, var=(4+0+4)/3, std=sqrt(8/3)~1.632993
          upper~5.632993 lower~2.367007
    idx3: media 6 -> upper~7.632993 lower~4.367007
    idx4: media 8 -> upper~9.632993 lower~6.367007
    """
    closes = pl.Series("close", [2.0, 4.0, 6.0, 8.0, 10.0])

    bands = compute_bollinger_bands(closes, period=3, num_std=1.0)

    assert bands.columns == ["middle", "upper", "lower"]
    assert bands["middle"].to_list()[:2] == [None, None]
    assert bands["upper"].to_list()[:2] == [None, None]
    assert bands["middle"][2] == pytest.approx(4.0)
    assert bands["upper"][2] == pytest.approx(5.632993161855452)
    assert bands["lower"][2] == pytest.approx(2.367006838144548)
    assert bands["middle"][3] == pytest.approx(6.0)
    assert bands["upper"][3] == pytest.approx(7.632993161855452)
    assert bands["middle"][4] == pytest.approx(8.0)
    assert bands["upper"][4] == pytest.approx(9.632993161855452)


def test_bollinger_constant_series_has_zero_spread() -> None:
    """Serie constante: std=0 -> upper==middle==lower (caso degenerado)."""
    closes = pl.Series("close", [5.0, 5.0, 5.0, 5.0])

    bands = compute_bollinger_bands(closes, period=3, num_std=2.0)

    assert bands["middle"][2] == pytest.approx(5.0)
    assert bands["upper"][2] == pytest.approx(5.0)
    assert bands["lower"][2] == pytest.approx(5.0)


def test_bollinger_invalid_period_raises() -> None:
    """Periodo < 1 es inválido -> ValueError."""
    closes = pl.Series("close", [1.0, 2.0])

    with pytest.raises(ValueError):
        compute_bollinger_bands(closes, period=0, num_std=2.0)


# ---------------------------------------------------------------------------
# generate_signal_a
# ---------------------------------------------------------------------------


def _bars_from_closes(closes: list[float]) -> pl.DataFrame:
    return pl.DataFrame(
        {
            "end_timestamp": [
                datetime(2024, 1, 10, 14, 30, i) for i in range(len(closes))
            ],
            "open": closes,
            "high": closes,
            "low": closes,
            "close": closes,
            "volume": [100.0] * len(closes),
        }
    )


def test_signal_a_true_only_on_breakout_rows() -> None:
    """Closes [2,4,6,8,10]: breakout en i3 e i4; warmup y arranque en False."""
    bars = _bars_from_closes([2.0, 4.0, 6.0, 8.0, 10.0])

    signal = generate_signal_a(bars, period=3, num_std=1.0)

    assert isinstance(signal, pl.Series)
    assert signal.to_list() == [False, False, False, True, True]


def test_signal_a_rejects_when_not_above_previous_close() -> None:
    """i5: close 9.9 supera la banda previa (9.63299) pero NO a close_prev
    (10.0). Comparación ESTRICTA con la barra anterior -> False aislado.
    """
    bars = _bars_from_closes([2.0, 4.0, 6.0, 8.0, 10.0, 9.9])

    signal = generate_signal_a(bars, period=3, num_std=1.0)

    assert bool(signal[-1]) is False


def test_signal_a_rejects_when_below_upper_band() -> None:
    """i6: close 10.0 supera a close_prev (9.9) pero queda bajo la banda
    previa (upper en i5 ~10.2201) -> False aislado por cláusula de banda.
    """
    bars = _bars_from_closes([2.0, 4.0, 6.0, 8.0, 10.0, 9.9, 10.0])

    signal = generate_signal_a(bars, period=3, num_std=1.0)

    assert bool(signal[6]) is False


def test_signal_a_on_empty_bars_is_empty_boolean_series() -> None:
    """Barras vacías -> serie booleana vacía (precondición explícita)."""
    empty_bars = pl.DataFrame(schema={col: pl.Float64 for col in BAR_COLUMNS})

    signal = generate_signal_a(empty_bars, period=3, num_std=2.0)

    assert isinstance(signal, pl.Series)
    assert signal.dtype == pl.Boolean
    assert len(signal) == 0


def test_signal_a_missing_close_column_raises() -> None:
    """Sin columna 'close' en las barras -> ValueError."""
    bad = pl.DataFrame({"volume": [1.0]})

    with pytest.raises(ValueError):
        generate_signal_a(bad, period=3, num_std=2.0)


def test_signal_a_invalid_num_std_raises() -> None:
    """Multiplicador D <= 0 inválido -> ValueError."""
    bars = _bars_from_closes([1.0, 2.0, 3.0])

    with pytest.raises(ValueError):
        generate_signal_a(bars, period=3, num_std=0.0)
