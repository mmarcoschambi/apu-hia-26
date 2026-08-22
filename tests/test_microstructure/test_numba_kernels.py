"""Tests de los kernels Numba de backtesting vectorizado (Issue #69, slice 3B).

Contrato bajo test (todos los valores esperados están calculados a mano):
- ``simulate_trades`` / ``simulate_trades_kernel``: simulación LONG sobre
  arrays NumPy float64/int64 (nada de pandas/polars cruza la frontera JIT).
  Semántica por barra documentada en el módulo:
    * Entrada al CLOSE de la barra con señal, solo si no hay posición abierta
      (una posición por vez; señales durante una operación se ignoran; el
      manejo de la posición abierta va PRIMERO, después la entrada si quedó
      plano).
    * R = stop_atr_mult * ATR[barra_señal]; ATR no finito o R degenerado ->
      la señal se descarta (sin trade).
    * SL estructural = entrada - sl_r_mult * R (el TOQUE cuenta: low <= SL).
    * TP = entrada + tp_r_mult * R (ESTRICTO: high > TP); al primer toque se
      vende tp_exit_fraction de la posición a precio TP.
    * Empate SL+TP en la MISMA barra -> SL primero (conservador, espeja el
      etiquetado del modelo híbrido).
    * Resto de la posición tras el TP parcial: trailing stop =
      máx(SL estructural, máximo high HASTA LA BARRA PREVIA - trail_r_mult*R);
      el trail nunca usa el high de la propia barra evaluada (PIT intrabar).
    * Horizonte: si sigue abierto en entry_index + max_hold_bars, sale al
      close de esa barra.
    * Salidas en R: pnl_r = fracción_vendida*(tp_r) + resto*(salida-entrada)/R.
    * Curva de equity: PnL realizado acumulado en unidades R por barra
      (constante entre cierres de operaciones).
"""

from __future__ import annotations

import numpy as np
import pytest
from numba.core.dispatcher import Dispatcher

from src.microstructure.numba_kernels import (
    DEFAULT_SL_R_MULT,
    DEFAULT_STOP_ATR_MULT,
    DEFAULT_TP_EXIT_FRACTION,
    OUTCOME_HORIZON,
    OUTCOME_STOPPED,
    OUTCOME_TP_THEN_HORIZON,
    OUTCOME_TP_THEN_STOPPED,
    TRADE_AVG_EXIT_PRICE,
    TRADE_ENTRY_INDEX,
    TRADE_ENTRY_PRICE,
    TRADE_EXIT_INDEX,
    TRADE_FIELDS,
    TRADE_OUTCOME,
    TRADE_PNL_R,
    TRADE_RISK_UNIT,
    simulate_trades,
    simulate_trades_kernel,
)

# ATR constante de los fixtures -> con stop_atr_mult default 0.5, R = 1.0.
FIXTURE_ATR = 2.0


# ---------------------------------------------------------------------------
# Helpers de fixtures sintéticas deterministas (valores calculados a mano)
# ---------------------------------------------------------------------------


def _arrays(
    highs: list[float],
    lows: list[float],
    closes: list[float],
    *,
    atr: list[float] | None = None,
    signals: list[int] | None = None,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Arrays NumPy float64/list->bool para el kernel; ATR plano FIXTURE_ATR."""
    n = len(closes)
    atr_values = np.full(n, FIXTURE_ATR) if atr is None else np.asarray(atr, dtype=np.float64)
    mask = np.zeros(n, dtype=bool) if signals is None else np.asarray(signals, dtype=bool)
    return (
        np.asarray(highs, dtype=np.float64),
        np.asarray(lows, dtype=np.float64),
        np.asarray(closes, dtype=np.float64),
        atr_values,
        mask,
    )


def _default_result(highs, lows, closes, atr, mask, **overrides):
    """Llama simulate_trades con defaults salvo overrides explícitos."""
    return simulate_trades(highs, lows, closes, atr, mask, **overrides)


def _win_trail_series() -> tuple[np.ndarray, ...]:
    """Serie ganadora: TP parcial en j=2 y salida del resto por trail en j=3.

    Con R=1.0: entrada 100, TP=102 (estricto), SL=99, trail tras TP =
    102.5 - 1.0 = 101.5. pnl_r = 0.33*2 + 0.67*(101.5-100)/1 = 1.665.
    """
    return _arrays(
        highs=[100.5, 100.8, 102.5, 101.8],
        lows=[99.5, 99.6, 100.9, 101.4],
        closes=[100.0, 101.0, 102.2, 101.6],
        signals=[1, 0, 0, 0],
    )


# ---------------------------------------------------------------------------
# Compilación Numba (evidencia de que el kernel es @njit real)
# ---------------------------------------------------------------------------


def test_kernel_is_njit_dispatcher_and_compiles_on_first_call() -> None:
    """El kernel expuesto debe ser un Dispatcher Numba compilado al primer uso."""
    assert isinstance(simulate_trades_kernel, Dispatcher)
    highs, lows, closes, atr, mask = _win_trail_series()
    before = len(simulate_trades_kernel.signatures)
    _default_result(highs, lows, closes, atr, mask)
    assert len(simulate_trades_kernel.signatures) >= 1
    assert len(simulate_trades_kernel.signatures) >= before


# ---------------------------------------------------------------------------
# Ciclo de vida de trades contra matemática a mano
# ---------------------------------------------------------------------------


def test_win_scenario_partial_tp_then_trailing_stop_hand_math() -> None:
    """TP parcial 33% a +2R, resto sale por trail 1R debajo del máximo."""
    highs, lows, closes, atr, mask = _win_trail_series()
    result = _default_result(highs, lows, closes, atr, mask)

    assert len(result.trades) == 1
    trade = result.trades[0]
    assert trade[TRADE_ENTRY_INDEX] == 0
    assert trade[TRADE_EXIT_INDEX] == 3
    assert trade[TRADE_ENTRY_PRICE] == pytest.approx(100.0)
    assert trade[TRADE_RISK_UNIT] == pytest.approx(DEFAULT_STOP_ATR_MULT * FIXTURE_ATR)
    expected_pnl = DEFAULT_TP_EXIT_FRACTION * 2.0 + (1.0 - DEFAULT_TP_EXIT_FRACTION) * 1.5
    assert trade[TRADE_PNL_R] == pytest.approx(expected_pnl)
    expected_avg_exit = DEFAULT_TP_EXIT_FRACTION * 102.0 + (1.0 - DEFAULT_TP_EXIT_FRACTION) * 101.5
    assert trade[TRADE_AVG_EXIT_PRICE] == pytest.approx(expected_avg_exit)
    assert trade[TRADE_OUTCOME] == OUTCOME_TP_THEN_STOPPED


def test_loss_scenario_full_stop_out_hand_math() -> None:
    """Stop directo antes de TP: pnl_r = -sl_r_mult y outcome STOPPED."""
    highs, lows, closes, atr, mask = _arrays(
        highs=[100.5, 99.4],
        lows=[99.5, 98.9],
        closes=[100.0, 99.2],
        signals=[1, 0],
    )
    result = _default_result(highs, lows, closes, atr, mask)

    assert len(result.trades) == 1
    trade = result.trades[0]
    assert trade[TRADE_ENTRY_INDEX] == 0
    assert trade[TRADE_EXIT_INDEX] == 1
    assert trade[TRADE_ENTRY_PRICE] == pytest.approx(100.0)
    assert trade[TRADE_PNL_R] == pytest.approx(-DEFAULT_SL_R_MULT)
    assert trade[TRADE_AVG_EXIT_PRICE] == pytest.approx(99.0)
    assert trade[TRADE_OUTCOME] == OUTCOME_STOPPED


def test_tie_sl_and_tp_same_bar_resolves_stop_first() -> None:
    """Empate conservador: SL y TP en la misma barra -> gana el stop (espeja labeling)."""
    highs, lows, closes, atr, mask = _arrays(
        highs=[100.5, 103.0],
        lows=[99.5, 98.9],
        closes=[100.0, 101.0],
        signals=[1, 0],
    )
    result = _default_result(highs, lows, closes, atr, mask)

    assert len(result.trades) == 1
    assert result.trades[0][TRADE_OUTCOME] == OUTCOME_STOPPED
    assert result.trades[0][TRADE_PNL_R] == pytest.approx(-DEFAULT_SL_R_MULT)


def test_tp_exit_fraction_custom_value_scales_partial_leg() -> None:
    """Triangulación de la fracción: con 0.5 la pata parcial domina el pnl."""
    highs, lows, closes, atr, mask = _win_trail_series()
    result = _default_result(highs, lows, closes, atr, mask, tp_exit_fraction=0.5)

    trade = result.trades[0]
    expected_pnl = 0.5 * 2.0 + 0.5 * 1.5
    assert trade[TRADE_PNL_R] == pytest.approx(expected_pnl)
    assert trade[TRADE_AVG_EXIT_PRICE] == pytest.approx(0.5 * 102.0 + 0.5 * 101.5)


def test_horizon_end_exits_full_position_at_close() -> None:
    """Sin TP ni SL dentro del horizonte: todo sale al close de la última barra."""
    highs, lows, closes, atr, mask = _arrays(
        highs=[100.5, 100.6, 100.8, 100.9],
        lows=[99.5, 100.1, 100.2, 100.5],
        closes=[100.0, 100.4, 100.6, 100.9],
        signals=[1, 0, 0, 0],
    )
    result = _default_result(
        highs, lows, closes, atr, mask, max_hold_bars=3, tp_exit_fraction=DEFAULT_TP_EXIT_FRACTION
    )

    trade = result.trades[0]
    assert trade[TRADE_EXIT_INDEX] == 3
    assert trade[TRADE_OUTCOME] == OUTCOME_HORIZON
    assert trade[TRADE_PNL_R] == pytest.approx((100.9 - 100.0) / 1.0)
    assert trade[TRADE_AVG_EXIT_PRICE] == pytest.approx(100.9)


def test_tp_then_horizon_exits_remainder_at_final_close() -> None:
    """Tras el TP parcial el resto sobrevive sin tocar el trail: sale al close final."""
    highs, lows, closes, atr, mask = _arrays(
        highs=[100.5, 100.8, 102.5, 102.6, 102.8],
        lows=[99.5, 99.6, 100.9, 102.2, 102.6],
        closes=[100.0, 101.0, 102.2, 102.5, 102.7],
        signals=[1, 0, 0, 0, 0],
    )
    result = _default_result(highs, lows, closes, atr, mask, max_hold_bars=4)

    trade = result.trades[0]
    assert trade[TRADE_EXIT_INDEX] == 4
    assert trade[TRADE_OUTCOME] == OUTCOME_TP_THEN_HORIZON
    expected_pnl = DEFAULT_TP_EXIT_FRACTION * 2.0 + (1.0 - DEFAULT_TP_EXIT_FRACTION) * 2.7
    assert trade[TRADE_PNL_R] == pytest.approx(expected_pnl)
    expected_avg = DEFAULT_TP_EXIT_FRACTION * 102.0 + (1.0 - DEFAULT_TP_EXIT_FRACTION) * 102.7
    assert trade[TRADE_AVG_EXIT_PRICE] == pytest.approx(expected_avg)


def test_no_signals_produce_flat_empty_backtest() -> None:
    """Máscara toda False: ningún trade registrado y equity plana en cero."""
    highs, lows, closes, atr, mask = _arrays(
        highs=[100.5, 101.0, 101.5],
        lows=[99.5, 99.0, 99.5],
        closes=[100.0, 100.5, 101.0],
        signals=[0, 0, 0],
    )
    result = _default_result(highs, lows, closes, atr, mask)

    assert result.trades.shape == (0, TRADE_FIELDS)
    np.testing.assert_array_equal(result.equity, np.zeros(3))


def test_signal_with_non_finite_atr_is_skipped_but_later_one_taken() -> None:
    """ATR NaN en la barra de señal -> trade descartado; señal posterior válida sí opera."""
    highs, lows, closes, atr, mask = _arrays(
        highs=[100.5, 100.6, 101.2, 101.6],
        lows=[99.5, 100.0, 100.4, 100.9],
        closes=[100.0, 100.2, 101.0, 101.5],
        atr=[float("nan"), FIXTURE_ATR, FIXTURE_ATR, FIXTURE_ATR],
        signals=[1, 0, 1, 0],
    )
    result = _default_result(highs, lows, closes, atr, mask, max_hold_bars=1)

    assert len(result.trades) == 1
    assert result.trades[0][TRADE_ENTRY_INDEX] == 2
    assert result.trades[0][TRADE_OUTCOME] == OUTCOME_HORIZON
    assert result.trades[0][TRADE_PNL_R] == pytest.approx((101.5 - 101.0) / 1.0)


def test_degenerate_zero_risk_unit_signal_is_skipped() -> None:
    """ATR cero => R degenerado => la señal no genera trade (consistente con labeling)."""
    highs, lows, closes, atr, mask = _arrays(
        highs=[100.5, 100.6],
        lows=[99.5, 100.0],
        closes=[100.0, 100.2],
        atr=[0.0, 0.0],
        signals=[1, 0],
    )
    result = _default_result(highs, lows, closes, atr, mask)

    assert result.trades.shape == (0, TRADE_FIELDS)
    np.testing.assert_array_equal(result.equity, np.zeros(2))


def test_signals_during_open_position_are_ignored() -> None:
    """Una posición por vez: señales mientras hay trade abierto no abren otro."""
    highs, lows, closes, atr, mask = _arrays(
        highs=[100.5, 100.6, 100.7, 100.8, 100.9],
        lows=[99.5, 99.2, 99.3, 99.4, 99.5],
        closes=[100.0, 100.2, 100.4, 100.6, 100.8],
        signals=[1, 1, 1, 0, 0],
    )
    result = _default_result(highs, lows, closes, atr, mask, max_hold_bars=3)

    assert len(result.trades) == 1
    assert result.trades[0][TRADE_ENTRY_INDEX] == 0
    assert result.trades[0][TRADE_EXIT_INDEX] == 3
    assert result.trades[0][TRADE_OUTCOME] == OUTCOME_HORIZON


def test_two_consecutive_losing_trades_accumulate_in_equity() -> None:
    """Reentrada tras cierre permitida; equity acumula PnL realizado en R."""
    highs, lows, closes, atr, mask = _arrays(
        highs=[100.5, 99.4, 100.5, 99.4],
        lows=[99.5, 98.9, 99.5, 98.9],
        closes=[100.0, 99.2, 100.0, 99.2],
        signals=[1, 0, 1, 0],
    )
    result = _default_result(highs, lows, closes, atr, mask)

    assert len(result.trades) == 2
    assert result.trades[0][TRADE_PNL_R] == pytest.approx(-1.0)
    assert result.trades[1][TRADE_PNL_R] == pytest.approx(-1.0)
    np.testing.assert_allclose(result.equity, [0.0, -1.0, -1.0, -2.0])


def test_equity_curve_constant_between_exits_and_final_equals_total_pnl() -> None:
    """La equity solo cambia en barras de cierre y termina en el PnL total."""
    highs, lows, closes, atr, mask = _win_trail_series()
    result = _default_result(highs, lows, closes, atr, mask)

    total = result.trades[:, TRADE_PNL_R].sum()
    assert result.equity[0] == pytest.approx(0.0)
    assert result.equity[1] == pytest.approx(0.0)
    assert result.equity[2] == pytest.approx(0.0)
    assert result.equity[3] == pytest.approx(total)
    assert len(result.equity) == len(closes)


# ---------------------------------------------------------------------------
# Validaciones, coerción de tipos y casos borde
# ---------------------------------------------------------------------------


def test_mismatched_array_lengths_raise_value_error() -> None:
    """Longitudes inconsistentes entre OHLC/ATR/máscara -> ValueError."""
    highs, lows, closes, atr, mask = _win_trail_series()
    with pytest.raises(ValueError, match="misma longitud"):
        _default_result(highs[:-1], lows, closes, atr, mask)


def test_invalid_trade_parameters_raise_value_error() -> None:
    """Fracciones fuera de (0,1), multiplicadores <= 0 u horizonte < 1 fallan."""
    highs, lows, closes, atr, mask = _win_trail_series()
    with pytest.raises(ValueError, match="tp_exit_fraction"):
        _default_result(highs, lows, closes, atr, mask, tp_exit_fraction=0.0)
    with pytest.raises(ValueError, match="stop_atr_mult"):
        _default_result(highs, lows, closes, atr, mask, stop_atr_mult=-0.5)
    with pytest.raises(ValueError, match="max_hold_bars"):
        _default_result(highs, lows, closes, atr, mask, max_hold_bars=0)


def test_inputs_are_coerced_to_float64_and_mask_to_indices() -> None:
    """Entradas float32/listas bool producen el MISMO resultado que float64."""
    highs64, lows64, closes64, atr64, mask64 = _win_trail_series()
    reference = _default_result(highs64, lows64, closes64, atr64, mask64)

    other = simulate_trades(
        highs64.astype(np.float32),
        lows64.astype(np.float32),
        closes64.astype(np.float32),
        atr64.astype(np.float32),
        [True, False, False, False],
    )
    np.testing.assert_allclose(other.trades, reference.trades)
    np.testing.assert_allclose(other.equity, reference.equity)
    assert other.trades.dtype == np.float64
    assert other.equity.dtype == np.float64


def test_tiny_data_edges_do_not_crash() -> None:
    """Arrays vacíos y señal en la última barra (sin barras siguientes) -> vacío."""
    empty = simulate_trades(
        np.array([], dtype=np.float64),
        np.array([], dtype=np.float64),
        np.array([], dtype=np.float64),
        np.array([], dtype=np.float64),
        np.array([], dtype=bool),
    )
    assert empty.trades.shape == (0, TRADE_FIELDS)
    assert empty.equity.shape == (0,)

    single = _arrays(highs=[100.5], lows=[99.5], closes=[100.0], signals=[1])
    result = _default_result(*single)
    assert result.trades.shape == (0, TRADE_FIELDS)
    np.testing.assert_array_equal(result.equity, np.zeros(1))


# ---------------------------------------------------------------------------
# Defaults fijados por spec (proposal sección 4)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("constant_name", "expected"),
    [
        ("DEFAULT_STOP_ATR_MULT", 0.5),
        ("DEFAULT_TP_R_MULT", 2.0),
        ("DEFAULT_SL_R_MULT", 1.0),
        ("DEFAULT_TP_EXIT_FRACTION", 0.33),
        ("DEFAULT_TRAIL_R_MULT", 1.0),
        ("DEFAULT_MAX_HOLD_BARS", 20),
        ("OUTCOME_STOPPED", 0),
        ("OUTCOME_TP_THEN_STOPPED", 1),
        ("OUTCOME_TP_THEN_HORIZON", 2),
        ("OUTCOME_HORIZON", 3),
    ],
)
def test_spec_default_constants_are_pinned(constant_name: str, expected: float) -> None:
    """Constantes nombradas del proposal sección 4 fijadas por test."""
    import src.microstructure.numba_kernels as kernels_module

    assert getattr(kernels_module, constant_name) == expected
