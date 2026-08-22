"""Pipeline A (Microstructure Motor): Volume Bars + Bollinger + Signal A.

Propósito
---------
Construir barras por volumen a partir de ticks, calcular Bandas de Bollinger
sobre la serie de cierres de las barras y generar la señal de ruptura pura
(Signal A) definida en la especificación del Issue #69.

Decisiones documentadas
-----------------------
- Agrupado por volumen: los ticks consecutivos se acumulan hasta alcanzar el
  umbral V; el tick que dispara el cierre PERTENECE a la barra que cierra
  (un tick nunca se divide entre dos barras).
- Barra parcial final (< V al agotarse los datos) SE CONSERVA: refleja
  actividad real del cierre y mantiene determinismo en la frontera temporal.
- Bollinger: desvío estándar POBLACIONAL (ddof=0), convención TA-Lib /
  TradingView; ventanas incompletas -> null.
- Signal A: ``close[i] > upper[i-1] AND close[i] > close[i-1]`` con
  comparaciones ESTRICTAS y SIN filtro de volumen (el umbral V ya garantiza
  participación institucional). Sin barra previa o banda nula -> False.
- Rendimiento: la asignación de barras usa una pasada única O(n) sobre arrays
  NumPy; el kernel JIT (Numba) llega en un slice posterior.
"""

from __future__ import annotations

import numpy as np
import polars as pl

REQUIRED_BAR_INPUT_COLUMNS: tuple[str, ...] = ("Timestamp", "Price", "Volume")
BAR_OUTPUT_COLUMNS: tuple[str, ...] = (
    "end_timestamp",
    "open",
    "high",
    "low",
    "close",
    "volume",
)

# Convención de desvío estándar poblacional para Bollinger Bands.
BBANDS_STD_DDOF = 0
# Nombre de la serie booleana de salida de Pipeline A.
SIGNAL_A_COLUMN = "signal_a"


def build_volume_bars(ticks: pl.DataFrame, volume_threshold: float) -> pl.DataFrame:
    """Agrupa ticks consecutivos en barras por volumen acumulado >= umbral.

    Parámetros:
        ticks: polars.DataFrame con columnas Timestamp, Price, Volume,
            ordenado por tiempo (contrato de salida de data_pipeline).
        volume_threshold: volumen objetivo V por barra (> 0). Candidatos del
            issue: {10_000, 25_000, 50_000}.

    Retorno:
        polars.DataFrame con columnas end_timestamp, open, high, low, close,
        volume (una fila por barra, en orden temporal).

    Lanza ValueError si faltan columnas o el umbral no es positivo.
    """
    _validate_tick_input(ticks)
    if volume_threshold <= 0:
        raise ValueError(f"volume_threshold debe ser > 0, recibido: {volume_threshold}")

    if ticks.is_empty():
        return pl.DataFrame(
            schema={
                "end_timestamp": pl.Datetime("us"),
                "open": pl.Float64,
                "high": pl.Float64,
                "low": pl.Float64,
                "close": pl.Float64,
                "volume": pl.Float64,
            }
        )

    volumes = ticks["Volume"].cast(pl.Float64).to_numpy()
    bar_ids = _assign_bar_ids(volumes=volumes, volume_threshold=volume_threshold)

    tagged = ticks.with_columns(pl.Series("_bar_id", bar_ids))
    bars = (
        tagged.group_by("_bar_id", maintain_order=True)
        .agg(
            pl.col("Timestamp").last().alias("end_timestamp"),
            pl.col("Price").first().alias("open"),
            pl.col("Price").max().alias("high"),
            pl.col("Price").min().alias("low"),
            pl.col("Price").last().alias("close"),
            pl.col("Volume").cast(pl.Float64).sum().alias("volume"),
        )
        .select(list(BAR_OUTPUT_COLUMNS))
    )
    return bars


def _validate_tick_input(ticks: pl.DataFrame) -> None:
    """Valida presencia de las columnas obligatorias del tick.

    Parámetros: ticks — DataFrame de entrada.
    Retorno: None. Lanza ValueError nombrando las faltantes.
    """
    missing = [column for column in REQUIRED_BAR_INPUT_COLUMNS if column not in ticks.columns]
    if missing:
        raise ValueError(
            f"Faltan columnas obligatorias en los ticks: {missing}. "
            f"Requeridas: {list(REQUIRED_BAR_INPUT_COLUMNS)}."
        )


def _assign_bar_ids(volumes: np.ndarray, volume_threshold: float) -> np.ndarray:
    """Asigna a cada tick el índice secuencial de su barra (pasada única O(n)).

    La barra cierra cuando SU volumen propio alcanza el umbral; el siguiente
    tick abre barra nueva. Un tick sobredimensionado no se divide nunca.

    Parámetros:
        volumes: array NumPy float64 con el volumen de cada tick.
        volume_threshold: umbral V (> 0).

    Retorno: array int64 de índices densos y monótonos, alineado a los ticks.
    """
    bar_ids = np.empty(len(volumes), dtype=np.int64)
    current_bar = 0
    accumulated = 0.0
    for index, volume in enumerate(volumes):
        if index > 0 and accumulated >= volume_threshold:
            current_bar += 1
            accumulated = 0.0
        bar_ids[index] = current_bar
        accumulated += volume
    return bar_ids


def compute_bollinger_bands(closes: pl.Series, period: int, num_std: float) -> pl.DataFrame:
    """Calcula Bandas de Bollinger sobre la serie de cierres.

    Media móvil de ``period`` ± ``num_std`` desvíos poblacionales (ddof=0);
    las primeras ``period - 1`` posiciones quedan en null (ventana incompleta).

    Parámetros:
        closes: serie polars con los cierres de las barras.
        period: ventana P (>= 1).
        num_std: multiplicador D de desvíos (> 0).

    Retorno: polars.DataFrame con columnas middle, upper, lower.
    Lanza ValueError si los parámetros son inválidos.
    """
    if period < 1:
        raise ValueError(f"period debe ser >= 1, recibido: {period}")
    if num_std <= 0:
        raise ValueError(f"num_std debe ser > 0, recibido: {num_std}")

    frame = pl.DataFrame({"close": closes.cast(pl.Float64)})
    return frame.select(
        pl.col("close").rolling_mean(window_size=period).alias("middle"),
        (
            pl.col("close").rolling_mean(window_size=period)
            + num_std * pl.col("close").rolling_std(window_size=period, ddof=BBANDS_STD_DDOF)
        ).alias("upper"),
        (
            pl.col("close").rolling_mean(window_size=period)
            - num_std * pl.col("close").rolling_std(window_size=period, ddof=BBANDS_STD_DDOF)
        ).alias("lower"),
    )


def generate_signal_a(bars: pl.DataFrame, period: int, num_std: float) -> pl.Series:
    """Genera Signal A (ruptura pura) alineada a las barras de volumen.

    Condición por barra i: ``close[i] > upper[i-1] AND close[i] > close[i-1]``
    (estricto, sin filtro de volumen). La primera barra y toda posición con
    banda aún nula valen False.

    Parámetros:
        bars: DataFrame de barras con columna 'close' (salida de
            build_volume_bars).
        period: periodo P de Bollinger (>= 1).
        num_std: multiplicador D de desvíos (> 0).

    Retorno: pl.Series booleana llamada 'signal_a', misma longitud que bars.
    Lanza ValueError si falta 'close' o los parámetros son inválidos.
    """
    if "close" not in bars.columns:
        raise ValueError(
            f"El DataFrame de barras debe contener la columna 'close'. "
            f"Columnas encontradas: {bars.columns}."
        )

    closes = bars["close"]
    bands = compute_bollinger_bands(closes, period=period, num_std=num_std)

    breakout_over_band = closes > bands["upper"].shift(1)
    breakout_over_prev_close = closes > closes.shift(1)
    signal = (breakout_over_band & breakout_over_prev_close).fill_null(False)

    return signal.rename(SIGNAL_A_COLUMN)
