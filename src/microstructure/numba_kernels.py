"""Kernels Numba de backtesting vectorizado (Issue #69, slice 3B).

Propósito
---------
Motor de simulación LONG sobre series OHLC de microestructura: entrada con
señal, stop estructural por ATR, take-profit escalonado y trailing stop para
el resto de la posición. Es la pieza "Vectorized Backtesting Engine" de la
sección 4 del proposal; el barrido Optuna V/T/Z vive en ``sweep.py``.

Frontera de vectorización (documentada)
---------------------------------------
El proposal exige "zero native Python loops" en el hot path. La frontera
elegida es: preparación 100% vectorizada (NumPy/Polars FUERA) + bucle de
simulación COMPILADO dentro de un kernel ``@numba.njit`` (los bucles dentro
de njit son código máquina, idiomáticos y permitidos; lo vetado es el bucle
interpretado de Python recorriendo barras/ticks). Solo arrays NumPy
float64/int64 cruzan la frontera JIT: ningún objeto pandas/polars entra al
kernel. El wrapper ``simulate_trades`` valida y coerceiona una sola vez y
llama al kernel; nunca recorre los datos en Python.

Semántica de la simulación (determinista, documentada)
------------------------------------------------------
- UNA posición abierta por vez. Orden por barra: PRIMERO se gestiona la
  posición abierta; DESPUÉS, si quedó plano, se evalúa la señal de esa barra
  (reentrada el mismo día de cierre solo si la barra emite señal). Las
  señales recibidas durante una posición abierta se consumen y se ignoran.
- Entrada al CLOSE de la barra con señal (última COMPLETADA, mismo criterio
  PIT que el etiquetado del modelo híbrido). Sin barras posteriores que
  gestionar -> la señal se descarta.
- R = stop_atr_mult * ATR[barra_señal]; ATR no finito o R <= 0 -> señal
  descartada (consistente con las etiquetas nulas de ``hybrid_model``).
- SL estructural = entrada - sl_r_mult * R; el TOQUE cuenta (low <= SL).
- TP = entrada + tp_r_mult * R con comparación ESTRICTA (high > TP), espejo
  del ">2R" del proposal. Al primer toque se vende ``tp_exit_fraction`` de
  la posición a precio TP (UN único evento parcial por operación).
- Empate SL+TP en la MISMA barra -> SL primero (conservador, igual que el
  etiquetado del modelo híbrido).
- Resto tras el TP parcial: trailing stop determinista =
  máx(SL estructural, máximo high acumulado HASTA LA BARRA PREVIA -
  trail_r_mult * R). El trail jamás usa el high de la propia barra evaluada
  (sin ambigüedad intrabar; PIT dentro de la vela).
- Horizonte: si sigue abierto en ``entry_index + max_hold_bars`` (capado a
  la última barra disponible), sale completo al CLOSE de esa barra.
- Contabilidad en unidades R: pnl_r = f * tp_r + resto * (salida - entrada)
  / R; el precio medio de salida es el promedio ponderado por fracciones
  vendidas (procede de sumar patas sobre peso total 1.0).
- Curva de equity: PnL realizado acumulado en unidades R por barra; queda
  constante entre cierres (las entradas no alteran el realizado).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numba import njit

# ---------------------------------------------------------------------------
# Constantes nombradas (defaults del proposal sección 4)
# ---------------------------------------------------------------------------

# Stop estructural: SL <= 50% del ATR (proposal sección 4).
DEFAULT_STOP_ATR_MULT = 0.5
# Take profit escalonado a +2R (proposal: "33% of position at 2R").
DEFAULT_TP_R_MULT = 2.0
DEFAULT_SL_R_MULT = 1.0
DEFAULT_TP_EXIT_FRACTION = 0.33
# Trail del remanente post-TP: máximo high previo - 1R (regla documentada).
DEFAULT_TRAIL_R_MULT = 1.0
# Horizonte máximo de gestión (espeja el horizonte de etiquetado default).
DEFAULT_MAX_HOLD_BARS = 20

# Códigos de desenlace por operación (columna TRADE_OUTCOME).
OUTCOME_STOPPED = 0
OUTCOME_TP_THEN_STOPPED = 1
OUTCOME_TP_THEN_HORIZON = 2
OUTCOME_HORIZON = 3

# Layout de la matriz de trades (float64, una fila por operación cerrada).
TRADE_ENTRY_INDEX = 0
TRADE_EXIT_INDEX = 1
TRADE_ENTRY_PRICE = 2
TRADE_AVG_EXIT_PRICE = 3
TRADE_PNL_R = 4
TRADE_OUTCOME = 5
TRADE_RISK_UNIT = 6
TRADE_FIELDS = 7


@dataclass
class BacktestResult:
    """Salida del backtest: trades cerrados y curva de equity realizada.

    Atributos:
        trades: matriz float64 (n_trades, TRADE_FIELDS); columnas según las
            constantes TRADE_* (índices de entrada/salida, precios, pnl_r,
            código de desenlace y unidad de riesgo usada).
        equity: PnL realizado acumulado en unidades R por barra (float64).
    """

    trades: np.ndarray
    equity: np.ndarray

    @property
    def n_trades(self) -> int:
        """Cantidad de operaciones cerradas."""
        return int(self.trades.shape[0])


# ---------------------------------------------------------------------------
# Kernel JIT: TODO el bucle de gestión vive aquí dentro (compilado)
# ---------------------------------------------------------------------------


@njit(cache=True)
def simulate_trades_kernel(
    highs: np.ndarray,
    lows: np.ndarray,
    closes: np.ndarray,
    atr_values: np.ndarray,
    signal_indices: np.ndarray,
    stop_atr_mult: float,
    tp_r_mult: float,
    sl_r_mult: float,
    tp_exit_fraction: float,
    trail_r_mult: float,
    max_hold_bars: int,
):
    """Simula todas las operaciones LONG sobre las series (kernel compilado).

    Parámetros: arrays NumPy 1-D (highs/lows/closes/atr float64) e índices
    int64 de señales; multiplicadores y horizonte como escalares.

    Retorno: tupla (trades, equity, n_cerrados) — trades es la matriz
    preasignada de tamaño (n_signals, TRADE_FIELDS) cuyas primeras
    ``n_cerrados`` filas quedan escritas; equity es el PnL realizado
    acumulado en R por barra.
    """
    n_bars = closes.shape[0]
    n_signals = signal_indices.shape[0]
    trades = np.full((n_signals, TRADE_FIELDS), np.nan, dtype=np.float64)
    equity = np.zeros(n_bars, dtype=np.float64)

    trade_count = 0
    realized_cum = 0.0
    signal_ptr = 0
    in_position = False
    state_partial = False
    entry_idx = 0
    exit_deadline = 0
    entry_price = 0.0
    risk_unit = 0.0
    stop_price = 0.0
    take_profit_price = 0.0
    running_max_high = 0.0
    realized_proceeds = 0.0

    for bar in range(n_bars):
        # --- 1) Gestión de la posición abierta (orden documentado) ---
        if in_position:
            stop_effective = stop_price
            if state_partial:
                trail_price = running_max_high - trail_r_mult * risk_unit
                if trail_price > stop_effective:
                    stop_effective = trail_price

            weight_rest = 1.0 - tp_exit_fraction if state_partial else 1.0
            exited = False
            exit_bar = 0
            outcome = OUTCOME_STOPPED
            proceeds = 0.0

            if lows[bar] <= stop_effective:
                # El toque del stop cuenta (consistente con el etiquetado);
                # en empate SL+TP de la misma barra gana el stop.
                proceeds = realized_proceeds + weight_rest * stop_effective
                outcome = OUTCOME_TP_THEN_STOPPED if state_partial else OUTCOME_STOPPED
                exit_bar = bar
                exited = True
            elif (not state_partial) and highs[bar] > take_profit_price:
                realized_proceeds += tp_exit_fraction * take_profit_price
                if bar == exit_deadline:
                    proceeds = (
                        realized_proceeds + (1.0 - tp_exit_fraction) * closes[bar]
                    )
                    outcome = OUTCOME_TP_THEN_HORIZON
                    exit_bar = bar
                    exited = True
                else:
                    state_partial = True
            elif bar == exit_deadline:
                proceeds = realized_proceeds + weight_rest * closes[bar]
                outcome = OUTCOME_TP_THEN_HORIZON if state_partial else OUTCOME_HORIZON
                exit_bar = bar
                exited = True

            if exited:
                pnl_r = (proceeds - entry_price) / risk_unit
                trades[trade_count, TRADE_ENTRY_INDEX] = entry_idx
                trades[trade_count, TRADE_EXIT_INDEX] = exit_bar
                trades[trade_count, TRADE_ENTRY_PRICE] = entry_price
                trades[trade_count, TRADE_AVG_EXIT_PRICE] = proceeds
                trades[trade_count, TRADE_PNL_R] = pnl_r
                trades[trade_count, TRADE_OUTCOME] = outcome
                trades[trade_count, TRADE_RISK_UNIT] = risk_unit
                trade_count += 1
                realized_cum += pnl_r
                in_position = False
                state_partial = False
                realized_proceeds = 0.0
            elif highs[bar] > running_max_high:
                # Se actualiza DESPUÉS de evaluar la barra: el trail nunca
                # mira el high de la vela que está siendo gestionada.
                running_max_high = highs[bar]

        # --- 2) Entrada si quedó plano y la barra trae señal ---
        if (
            (not in_position)
            and signal_ptr < n_signals
            and signal_indices[signal_ptr] == bar
        ):
            signal_ptr += 1
            if bar < n_bars - 1:
                atr_here = atr_values[bar]
                risk_candidate = stop_atr_mult * atr_here
                if np.isfinite(atr_here) and risk_candidate > 0.0:
                    in_position = True
                    entry_idx = bar
                    entry_price = closes[bar]
                    risk_unit = risk_candidate
                    stop_price = entry_price - sl_r_mult * risk_unit
                    take_profit_price = entry_price + tp_r_mult * risk_unit
                    exit_deadline = bar + max_hold_bars
                    if exit_deadline > n_bars - 1:
                        exit_deadline = n_bars - 1
                    running_max_high = highs[bar]

        equity[bar] = realized_cum

    return trades, equity, trade_count


# ---------------------------------------------------------------------------
# Wrapper público: validación + coerción vectorizada (sin loops de Python)
# ---------------------------------------------------------------------------


def _coerce_float64_array(values: object, name: str) -> np.ndarray:
    """Convierte la entrada a NumPy 1-D float64 contiguo o lanza ValueError.

    Parámetros: values — array-like; name — nombre para el error.
    Retorno: array float64 1-D. Lanza ValueError si no es 1-D.
    """
    array = np.asarray(values)
    if array.ndim != 1:
        raise ValueError(f"'{name}' debe ser un array 1-D; recibida dimensión {array.ndim}")
    return np.ascontiguousarray(array, dtype=np.float64)


def simulate_trades(
    highs: object,
    lows: object,
    closes: object,
    atr_values: object,
    signal_mask: object,
    *,
    stop_atr_mult: float = DEFAULT_STOP_ATR_MULT,
    tp_r_mult: float = DEFAULT_TP_R_MULT,
    sl_r_mult: float = DEFAULT_SL_R_MULT,
    tp_exit_fraction: float = DEFAULT_TP_EXIT_FRACTION,
    trail_r_mult: float = DEFAULT_TRAIL_R_MULT,
    max_hold_bars: int = DEFAULT_MAX_HOLD_BARS,
) -> BacktestResult:
    """Ejecuta el backtest vectorizado sobre series OHLC + ATR + señales.

    Punto de entrada público del motor: acepta array-like NumPy (o listas),
    valida el contrato, convierte la máscara booleana a índices int64 con
    ``flatnonzero`` (vectorizado) y delega TODO el bucle de gestión al kernel
    JIT ``simulate_trades_kernel``. Ningún pandas/polars cruza la frontera.

    Parámetros:
        highs / lows / closes: series de precios (float, mismas longitudes).
        atr_values: ATR alineado (admite NaN de warmup -> señal descartada).
        signal_mask: máscara booleana de entradas alineada a las barras.
        stop_atr_mult / tp_r_mult / sl_r_mult: múltiplos de R (todos > 0).
        tp_exit_fraction: fracción vendida al TP, en (0, 1) excluyente.
        trail_r_mult: retroceso del trailing stop post-TP en múltiplos de R.
        max_hold_bars: horizonte de gestión en barras (>= 1).

    Retorno: BacktestResult(trades, equity) — ver semántica del módulo.

    Lanza ValueError ante longitudes inconsistentes, dimensiones no 1-D,
    precios no finitos (el ATR admite NaN de warmup) o parámetros inválidos.
    """
    price_arrays = [
        _coerce_float64_array(array, name)
        for name, array in (("highs", highs), ("lows", lows), ("closes", closes))
    ]
    atr_array = _coerce_float64_array(atr_values, "atr_values")
    mask_array = np.asarray(signal_mask)
    if mask_array.ndim != 1:
        raise ValueError(f"'signal_mask' debe ser un array 1-D; recibida dimensión {mask_array.ndim}")

    lengths = {array.shape[0] for array in price_arrays}
    lengths.add(atr_array.shape[0])
    lengths.add(mask_array.shape[0])
    if len(lengths) > 1:
        raise ValueError(
            "Todos los arrays de entrada deben tener la misma longitud; "
            f"recibidas: {sorted(lengths)}."
        )
    non_finite = [
        name
        for name, array in zip(("highs", "lows", "closes"), price_arrays)
        if not np.all(np.isfinite(array))
    ]
    if non_finite:
        raise ValueError(f"Los precios deben ser finitos; arrays con no-finitos: {non_finite}.")

    if not 0.0 < tp_exit_fraction < 1.0:
        raise ValueError(f"tp_exit_fraction debe estar en (0, 1), recibido: {tp_exit_fraction}")
    for name, value in (
        ("stop_atr_mult", stop_atr_mult),
        ("tp_r_mult", tp_r_mult),
        ("sl_r_mult", sl_r_mult),
        ("trail_r_mult", trail_r_mult),
    ):
        if value <= 0.0:
            raise ValueError(f"{name} debe ser > 0, recibido: {value}")
    if max_hold_bars < 1:
        raise ValueError(f"max_hold_bars debe ser >= 1, recibido: {max_hold_bars}")

    signal_indices = np.flatnonzero(mask_array).astype(np.int64)

    trades_full, equity, closed_count = simulate_trades_kernel(
        price_arrays[0],
        price_arrays[1],
        price_arrays[2],
        atr_array,
        signal_indices,
        float(stop_atr_mult),
        float(tp_r_mult),
        float(sl_r_mult),
        float(tp_exit_fraction),
        float(trail_r_mult),
        int(max_hold_bars),
    )
    return BacktestResult(trades=trades_full[:closed_count].copy(), equity=equity)
