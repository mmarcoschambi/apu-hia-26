"""Pipeline B (Temporal Motor + Proxy Institucional): Time Bars + Vol Buzz + AVWAP + Signal B.

Propósito
---------
Remuestrear ticks a velas temporales de T minutos, calcular el Z-Score de
volumen por minuto-del-día (Vol Buzz), la VWAP anclada a la apertura RTH de
cada sesión (AVWAP) y generar la señal de ruptura condicionada (Signal B)
definida en la especificación del Issue #69.

Decisiones documentadas
-----------------------
- Grilla temporal: buckets ``[k*T, (k+1)*T)`` anclados al reloj sobre la
  línea de tiempo de los stamps de entrada (contrato de salida de
  ``data_pipeline``, que ya filtró RTH [09:30, 16:00) NY). Etiqueta left y
  borde inferior inclusivo: el tick exactamente en el borde abre vela nueva.
- Vela parcial final (< T al agotarse los datos) SE CONSERVA: misma política
  determinista que las barras parciales del Pipeline A (volume_bars).
- Buckets sin datos NO se emiten (salida rala, una fila por bucket con
  actividad real).
- Vol Buzz: para cada bucket se comparan los días PREVIOS del mismo
  minuto-de-inicio; Z = (vol_actual - media_previa) / std_previa con std
  POBLACIONAL (ddof=0), convención compartida con las Bandas de Bollinger
  del slice 1. El día actual nunca entra en su propia estadística (sin fuga
  temporal). Historia insuficiente (< ``min_days`` días previos) -> NaN,
  tratado como no-señal aguas abajo. Std histórica cero -> Z = 0.0.
- AVWAP: ancla en la primera vela de cada día calendario (la ingesta garantiza
  que sea el open RTH); acumula ``precio_típico * volumen`` reiniciando por
  día. Se usa precio típico ``(high + low + close) / 3`` como aproximación
  documentada del precio representativo de la vela. Vela sin volumen
  acumulado -> fallback al precio típico propio (evita división por cero).
- Signal B reutiliza ``compute_bollinger_bands`` del Pipeline A para que
  ambas pipelines compartan UNA única convención de Bollinger (ddof=0).
  Comparaciones ESTRICTAS; cualquier cláusula con null/NaN vale False.
"""

from __future__ import annotations

import polars as pl

from src.microstructure.volume_bars import (
    REQUIRED_BAR_INPUT_COLUMNS,
    compute_bollinger_bands,
)

TIME_BAR_OUTPUT_COLUMNS: tuple[str, ...] = (
    "bar_timestamp",
    "end_timestamp",
    "session_date",
    "open",
    "high",
    "low",
    "close",
    "volume",
)

# Columnas mínimas para derivar Vol Buzz / AVWAP sobre time bars.
REQUIRED_TIMEBAR_BASE_COLUMNS: tuple[str, ...] = ("bar_timestamp", "volume")
# Columnas de enriquecimiento exigidas por Signal B.
REQUIRED_SIGNAL_B_COLUMNS: tuple[str, ...] = ("close", "vol_buzz_z", "avwap")

# Mínimo de días previos por bucket para considerar válido el Z-Score.
DEFAULT_MIN_DAYS = 20
# Umbral default del Z-Score para habilitar Signal B (barrido Optuna llega luego).
DEFAULT_THRESHOLD_Z = 2.0

VOL_BUZZ_COLUMN = "vol_buzz_z"
AVWAP_COLUMN = "avwap"
SIGNAL_B_COLUMN = "signal_b"


def _validate_columns(frame: pl.DataFrame, required: tuple[str, ...], context: str) -> None:
    """Valida presencia de columnas obligatorias.

    Parámetros: frame — DataFrame a validar; required — columnas exigidas;
    context — etiqueta del error para identificar el llamado.
    Retorno: None. Lanza ValueError nombrando TODAS las faltantes.
    """
    missing = [column for column in required if column not in frame.columns]
    if missing:
        raise ValueError(
            f"Faltan columnas obligatorias ({context}): {missing}. "
            f"Requeridas: {list(required)}. Encontradas: {frame.columns}."
        )


def build_time_bars(ticks: pl.DataFrame, bar_minutes: int) -> pl.DataFrame:
    """Remuestrea ticks a velas OHLCV de T minutos sobre grilla anclada al reloj.

    Parámetros:
        ticks: polars.DataFrame con columnas Timestamp, Price, Volume ya
            filtrado en sesión RTH y ordenado (contrato de data_pipeline).
        bar_minutes: ancho de vela T en minutos (> 0). Candidatos del issue:
            {1, 3, 5}.

    Retorno:
        polars.DataFrame con columnas bar_timestamp (inicio de bucket),
        end_timestamp (fin exclusivo), session_date, open, high, low, close,
        volume. La vela parcial final se conserva; buckets sin ticks no se
        emiten.

    Lanza ValueError si faltan columnas o T no es positivo.
    """
    _validate_columns(ticks, REQUIRED_BAR_INPUT_COLUMNS, "ticks de entrada")
    if bar_minutes <= 0:
        raise ValueError(f"bar_minutes debe ser > 0, recibido: {bar_minutes}")

    if ticks.is_empty():
        return pl.DataFrame(
            schema={
                "bar_timestamp": pl.Datetime("us"),
                "end_timestamp": pl.Datetime("us"),
                "session_date": pl.Date,
                "open": pl.Float64,
                "high": pl.Float64,
                "low": pl.Float64,
                "close": pl.Float64,
                "volume": pl.Float64,
            }
        )

    bars = (
        ticks.sort("Timestamp")
        .group_by_dynamic(
            "Timestamp",
            every=f"{bar_minutes}m",
            closed="left",
            label="left",
        )
        .agg(
            pl.col("Price").first().alias("open"),
            pl.col("Price").max().alias("high"),
            pl.col("Price").min().alias("low"),
            pl.col("Price").last().alias("close"),
            pl.col("Volume").cast(pl.Float64).sum().alias("volume"),
        )
        .rename({"Timestamp": "bar_timestamp"})
    )

    bars = bars.with_columns(
        (pl.col("bar_timestamp") + pl.duration(minutes=bar_minutes)).alias("end_timestamp"),
        pl.col("bar_timestamp").dt.date().alias("session_date"),
    )
    return bars.select(list(TIME_BAR_OUTPUT_COLUMNS))


def _add_bucket_keys(bars: pl.DataFrame) -> pl.DataFrame:
    """Agrega claves auxiliares de partición (_tod = hora del bucket, _date).

    Parámetros: bars — DataFrame de time bars con bar_timestamp.
    Retorno: DataFrame con columnas _tod (Time) y _date (Date) extra.
    """
    return bars.with_columns(
        pl.col("bar_timestamp").dt.time().alias("_tod"),
        pl.col("bar_timestamp").dt.date().alias("_date"),
    )


def compute_vol_buzz_z(time_bars: pl.DataFrame, min_days: int = DEFAULT_MIN_DAYS) -> pl.Series:
    """Calcula el Z-Score de volumen por bucket contra los días previos.

    Para cada barra agrupa el volumen de SU mismo minuto-de-inicio en los
    días anteriores y devuelve Z = (vol_actual - media_previa) / std_previa
    con std poblacional (ddof=0).

    Parámetros:
        time_bars: DataFrame con columnas bar_timestamp y volume (salida de
            build_time_bars; una fila por bucket-día por construcción).
        min_days: días previos mínimos para emitir un Z válido (< ->
            NaN tratado como no-señal). Default: DEFAULT_MIN_DAYS.

    Retorno: pl.Series Float64 llamada 'vol_buzz_z', alineada a las filas de
    entrada. Historia insuficiente -> NaN; std histórica cero -> 0.0.

    Lanza ValueError si faltan columnas o min_days < 1.
    """
    _validate_columns(
        time_bars, REQUIRED_TIMEBAR_BASE_COLUMNS, "time bars para vol buzz"
    )
    if min_days < 1:
        raise ValueError(f"min_days debe ser >= 1, recibido: {min_days}")

    if time_bars.is_empty():
        return pl.Series(VOL_BUZZ_COLUMN, [], dtype=pl.Float64)

    keyed = _add_bucket_keys(time_bars)
    volume = pl.col("volume")

    # Estadísticas de los días PREVIOS dentro de cada bucket (orden por fecha;
    # el día actual queda excluido de su propia media/desvío).
    n_prior = pl.int_range(pl.len()).over("_tod", order_by="_date")
    prior_sum = volume.cum_sum().over("_tod", order_by="_date") - volume
    prior_sq_sum = (volume.pow(2)).cum_sum().over("_tod", order_by="_date") - volume.pow(2)

    prior_mean = pl.when(n_prior > 0).then(prior_sum / n_prior)
    prior_var = (prior_sq_sum / n_prior - prior_mean.pow(2)).clip(0.0, None)
    prior_std = prior_var.sqrt()

    z_expr = (
        pl.when(n_prior < min_days)
        .then(float("nan"))
        .when(prior_std == 0.0)
        .then(0.0)
        .otherwise((volume - prior_mean) / prior_std)
    )

    z = keyed.with_columns(z_expr.alias(VOL_BUZZ_COLUMN))
    return z[VOL_BUZZ_COLUMN]


def compute_avwap(time_bars: pl.DataFrame) -> pl.Series:
    """Calcula la VWAP anclada a la apertura RTH de cada día calendario.

    Acumula ``precio_típico * volumen`` desde la primera vela de cada
    session-day (el contrato de ingesta garantiza que sea el open RTH) y
    divide por el volumen acumulado del día. Precio típico =
    (high + low + close) / 3, aproximación documentada del módulo.

    Parámetros: time_bars — DataFrame con columnas bar_timestamp, high, low,
        close, volume.

    Retorno: pl.Series Float64 llamada 'avwap', alineada a las filas de
    entrada. Vela con volumen diario acumulado 0 -> precio típico propio.

    Lanza ValueError si faltan columnas.
    """
    _validate_columns(
        time_bars,
        ("bar_timestamp", "high", "low", "close", "volume"),
        "time bars para avwap",
    )

    if time_bars.is_empty():
        return pl.Series(AVWAP_COLUMN, [], dtype=pl.Float64)

    keyed = _add_bucket_keys(time_bars)
    typical = (pl.col("high") + pl.col("low") + pl.col("close")) / 3.0

    cum_pv = (typical * pl.col("volume")).cum_sum().over("_date", order_by="bar_timestamp")
    cum_v = pl.col("volume").cum_sum().over("_date", order_by="bar_timestamp")

    avwap_expr = pl.when(cum_v > 0).then(cum_pv / cum_v).otherwise(typical)

    out = keyed.with_columns(avwap_expr.alias(AVWAP_COLUMN))
    return out[AVWAP_COLUMN]


def generate_signal_b(
    time_bars: pl.DataFrame,
    period: int,
    num_std: float,
    threshold_z: float = DEFAULT_THRESHOLD_Z,
) -> pl.Series:
    """Genera Signal B (ruptura condicionada) alineada a las time bars.

    Condición por barra i (comparaciones ESTRICTAS):
        ``close[i] > upper[i-1] AND vol_buzz_z[i] > threshold_z AND
        close[i] > avwap[i]``
    Reutiliza la Bollinger del Pipeline A (ddof=0 compartido). Warmup de
    banda, z nulo/NaN o avwap insuficiente -> False (no-señal conservadora).

    Parámetros:
        time_bars: DataFrame ENRIQUECIDO con columnas close, vol_buzz_z
            (compute_vol_buzz_z) y avwap (compute_avwap).
        period: periodo P de Bollinger (>= 1).
        num_std: multiplicador D de desvíos (> 0).
        threshold_z: umbral estricto del Z-Score. Default DEFAULT_THRESHOLD_Z.

    Retorno: pl.Series booleana llamada 'signal_b', misma longitud que bars.
    Lanza ValueError si faltan columnas de enriquecimiento.
    """
    _validate_columns(time_bars, REQUIRED_SIGNAL_B_COLUMNS, "signal b")
    if threshold_z <= 0:
        raise ValueError(f"threshold_z debe ser > 0, recibido: {threshold_z}")

    closes = time_bars["close"]
    bands = compute_bollinger_bands(closes, period=period, num_std=num_std)

    breakout_over_band = closes > bands["upper"].shift(1)

    z = time_bars[VOL_BUZZ_COLUMN]
    breakout_over_threshold = z.is_not_null() & z.is_not_nan() & (z > threshold_z)

    breakout_over_avwap = closes > time_bars[AVWAP_COLUMN]

    signal = (breakout_over_band & breakout_over_threshold & breakout_over_avwap).fill_null(
        False
    )
    return signal.rename(SIGNAL_B_COLUMN)
