"""Feature Engine: extracción de features por instante de ruptura (Issue #69).

Propósito
---------
Construir el dataset tidy (Polars) del modelo híbrido: una fila por cada
instante de ruptura de precio crudo, con features de ambos pipelines y un
punto de inyección OPCIONAL para features de contexto (RS, health_score)
que el slice 3 cableará desde ``src/signals/signal_engine.py`` y
``src/utils/market_health.py`` SIN modificar esos módulos.

Decisiones documentadas
-----------------------
- Instante de ruptura crudo: ``close > Bollinger_Upper_previo`` sobre los
  cierres de CADA pipeline con su propia banda (se ignoran las cláusulas de
  validación extra de Signal A / Signal B: las filas son todos los candidatos,
  "regardless of validation", según la especificación).
- Deduplicación: si A y B rompen en el mismo timestamp sobrevive la fila de
  origen A (microestructura manda como referencia primaria).
- ``dist_to_last_volbar_close_pct``:
    * origen A -> ``(close[i] - close[i-1]) / close[i-1] * 100`` (referencia:
      cierre previo de barra de volumen).
    * origen B -> distancia entre el cierre de la última time bar completada
      y el cierre de la última barra de volumen COMPLETADA <= instante
      (joins as-of backward, sin mirar barras futuras).
- ``volbar_speed_ms``: ``end - start`` en milisegundos si el frame trae la
  columna opcional ``start_timestamp``; si no, proxy determinista =
  ``end[i] - end[i-1]`` (tiempo entre cierres consecutivos; primera fila ->
  null). El origen B hereda la velocidad de la barra referenciada.
- ``vol_buzz_z`` y ``dist_vs_avwap_pct``: leídos de la última TIME BAR
  COMPLETADA (``end_timestamp <= instante``, join as-of backward).
- ``recent_adr_pct``: media móvil de N días PREVIOS del rango diario
  ``(high-low)/cierre_del_día * 100`` sobre time bars. PIT estricto: el día
  del instante jamás entra en su propia media; con menos de 1 día previo ->
  null.
- Contexto: ``context_frame`` opcional con columna obligatoria ``timestamp``
  y columnas libres; se une as-of backward conservando sus nombres. Colisión
  de nombres con features propias -> ValueError explícito.
"""

from __future__ import annotations

import polars as pl

from src.microstructure.time_bars import AVWAP_COLUMN, VOL_BUZZ_COLUMN
from src.microstructure.volume_bars import compute_bollinger_bands

FEATURE_TIMESTAMP = "timestamp"
FEATURE_DIST_LAST_VOLBAR_CLOSE_PCT = "dist_to_last_volbar_close_pct"
FEATURE_VOLBAR_SPEED_MS = "volbar_speed_ms"
FEATURE_VOL_BUZZ_Z = VOL_BUZZ_COLUMN
FEATURE_DIST_VS_AVWAP_PCT = "dist_vs_avwap_pct"
FEATURE_RECENT_ADR_PCT = "recent_adr_pct"

FEATURE_OUTPUT_COLUMNS: tuple[str, ...] = (
    FEATURE_TIMESTAMP,
    FEATURE_DIST_LAST_VOLBAR_CLOSE_PCT,
    FEATURE_VOLBAR_SPEED_MS,
    FEATURE_VOL_BUZZ_Z,
    FEATURE_DIST_VS_AVWAP_PCT,
    FEATURE_RECENT_ADR_PCT,
)

# Defaults clásicos de Bollinger y ventana ADR (constantes nombradas).
DEFAULT_BB_PERIOD = 20
DEFAULT_BB_NUM_STD = 2.0
DEFAULT_ADR_LOOKBACK_DAYS = 10

REQUIRED_VOLBAR_FEATURE_COLUMNS: tuple[str, ...] = ("end_timestamp", "close")
OPTIONAL_VOLBAR_START_COLUMN = "start_timestamp"
REQUIRED_TIMEBAR_FEATURE_COLUMNS: tuple[str, ...] = (
    "bar_timestamp",
    "end_timestamp",
    "close",
    "high",
    "low",
    VOL_BUZZ_COLUMN,
    AVWAP_COLUMN,
)

CONTEXT_KEY_COLUMN = FEATURE_TIMESTAMP

ORIGIN_A = "A"
ORIGIN_B = "B"
_ORIGIN_COLUMN = "_origin"
_A_DIST = "_a_dist"
_A_SPEED = "_a_speed"
_TB_CLOSE = "_tb_close"
_TB_AVWAP = "_tb_avwap"
_VB_CLOSE = "_vb_close"
_VB_SPEED = "_vb_speed"


def _validate_columns(
    frame: pl.DataFrame, required: tuple[str, ...], context: str
) -> None:
    """Valida presencia de columnas obligatorias.

    Parámetros: frame — DataFrame a validar; required — columnas exigidas;
    context — etiqueta para identificar el llamado en el error.
    Retorno: None. Lanza ValueError nombrando TODAS las faltantes.
    """
    missing = [column for column in required if column not in frame.columns]
    if missing:
        raise ValueError(
            f"Faltan columnas obligatorias ({context}): {missing}. "
            f"Requeridas: {list(required)}. Encontradas: {frame.columns}."
        )


def _empty_feature_frame() -> pl.DataFrame:
    """Devuelve el frame de features vacío pero completamente tipado."""
    schema: dict[str, pl.DataType] = {FEATURE_TIMESTAMP: pl.Datetime("us")}
    for column in FEATURE_OUTPUT_COLUMNS[1:]:
        schema[column] = pl.Float64
    return pl.DataFrame(schema=schema)


def _speed_expr(with_start_column: bool) -> pl.Expr:
    """Expresión de velocidad de barra de volumen en milisegundos.

    Con start_timestamp: end - start exacto. Sin ella: proxy determinista =
    diferencia entre cierres consecutivos (primera fila -> null).

    Parámetros: with_start_column — si el frame trae start_timestamp.
    Retorno: expresión polars Float64 lista para usar en select.
    """
    if with_start_column:
        duration = pl.col("end_timestamp") - pl.col(OPTIONAL_VOLBAR_START_COLUMN)
    else:
        duration = pl.col("end_timestamp").diff()
    return duration.dt.total_milliseconds().cast(pl.Float64)


def _raw_breakout_instants(
    frame: pl.DataFrame,
    origin: str,
    period: int,
    num_std: float,
    with_start_column: bool,
) -> pl.DataFrame:
    """Extrae las filas de ruptura cruda de un pipeline con columnas internas.

    Parámetros: frame — barras (volume o time) con end_timestamp/close;
    origin — etiqueta interna A|B; period/num_std — parámetros Bollinger;
    with_start_column — habilita velocidad exacta end-start.
    Retorno: DataFrame con timestamp, _origin, _a_dist, _a_speed (vacío pero
    tipado si ninguna barra rompe).
    """
    closes = frame["close"]
    bands = compute_bollinger_bands(closes, period=period, num_std=num_std)
    breakout = (closes > bands["upper"].shift(1)).fill_null(False)

    prev_close = closes.shift(1)
    dist_pct = (closes - prev_close) / prev_close * 100.0

    return (
        frame.select(
            pl.col("end_timestamp").alias(FEATURE_TIMESTAMP),
            pl.lit(origin, dtype=pl.String).alias(_ORIGIN_COLUMN),
            pl.when(prev_close.is_not_null())
            .then(dist_pct)
            .alias(_A_DIST),
            _speed_expr(with_start_column).alias(_A_SPEED),
        )
        .with_columns()
        .filter(breakout)
    )


def _b_breakout_instants(time_bars: pl.DataFrame, period: int, num_std: float) -> pl.DataFrame:
    """Filas de ruptura cruda del pipeline B con features A aún nulas."""
    closes = time_bars["close"]
    bands = compute_bollinger_bands(closes, period=period, num_std=num_std)
    breakout = (closes > bands["upper"].shift(1)).fill_null(False)

    return time_bars.filter(breakout).select(
        pl.col("end_timestamp").alias(FEATURE_TIMESTAMP),
        pl.lit(ORIGIN_B, dtype=pl.String).alias(_ORIGIN_COLUMN),
        pl.lit(None, dtype=pl.Float64).alias(_A_DIST),
        pl.lit(None, dtype=pl.Float64).alias(_A_SPEED),
    )


def _prior_days_adr(time_bars: pl.DataFrame, lookback_days: int) -> pl.DataFrame:
    """ADR% por día usando SOLO días previos completados (PIT).

    Parámetros: time_bars — frame ordenado con high/low/close/end_timestamp;
    lookback_days — ventana N de la media móvil de rangos diarios.
    Retorno: DataFrame (_day, recent_adr_pct) con una fila por día.
    """
    daily = (
        time_bars.with_columns(pl.col("end_timestamp").dt.date().alias("_day"))
        .group_by("_day")
        .agg(
            pl.col("high").max().alias("_d_high"),
            pl.col("low").min().alias("_d_low"),
            pl.col("close").last().alias("_d_close"),
        )
        .sort("_day")
    )
    daily_range_pct = (pl.col("_d_high") - pl.col("_d_low")) / pl.col("_d_close") * 100.0
    return daily.select(
        pl.col("_day"),
        daily_range_pct.shift(1)
        .rolling_mean(window_size=lookback_days, min_samples=1)
        .alias(FEATURE_RECENT_ADR_PCT),
    )


def build_feature_frame(
    volume_bars: pl.DataFrame,
    time_bars: pl.DataFrame,
    *,
    bb_period_a: int = DEFAULT_BB_PERIOD,
    bb_num_std_a: float = DEFAULT_BB_NUM_STD,
    bb_period_b: int = DEFAULT_BB_PERIOD,
    bb_num_std_b: float = DEFAULT_BB_NUM_STD,
    adr_lookback_days: int = DEFAULT_ADR_LOOKBACK_DAYS,
    context_frame: pl.DataFrame | None = None,
) -> pl.DataFrame:
    """Construye el dataset de features alineado por instante de ruptura.

    Parámetros:
        volume_bars: salida de Pipeline A (build_volume_bars); acepta la
            columna opcional start_timestamp para velocidad exacta.
        time_bars: salida de Pipeline B ENRIQUECIDA con vol_buzz_z y avwap.
        bb_period_a/bb_num_std_a: Bollinger de rupturas del pipeline A.
        bb_period_b/bb_num_std_b: Bollinger de rupturas del pipeline B.
        adr_lookback_days: ventana N de la ADR reciente (> 0).
        context_frame: frame opcional con columna 'timestamp' y features de
            contexto libres (RS, health_score); se une as-of backward.

    Retorno: polars.DataFrame tidy ordenado por timestamp con las columnas
    FEATURE_OUTPUT_COLUMNS (+ columnas de contexto si se inyectaron).

    Lanza ValueError si faltan columnas requeridas, si el lookback ADR no es
    positivo o si el contexto colisiona con nombres propios.
    """
    _validate_columns(volume_bars, REQUIRED_VOLBAR_FEATURE_COLUMNS, "volume bars")
    _validate_columns(time_bars, REQUIRED_TIMEBAR_FEATURE_COLUMNS, "time bars")
    if adr_lookback_days < 1:
        raise ValueError(f"adr_lookback_days debe ser >= 1, recibido: {adr_lookback_days}")

    context_columns: list[str] = []
    if context_frame is not None:
        _validate_columns(context_frame, (CONTEXT_KEY_COLUMN,), "frame de contexto")
        context_columns = [c for c in context_frame.columns if c != CONTEXT_KEY_COLUMN]
        collisions = sorted(set(context_columns) & set(FEATURE_OUTPUT_COLUMNS))
        if collisions:
            raise ValueError(
                f"El frame de contexto colisiona con columnas propias: {collisions}. "
                f"Renombre las columnas de contexto antes de inyectarlas."
            )

    if volume_bars.is_empty() and time_bars.is_empty():
        return _empty_feature_frame()

    time_bars = time_bars.sort("bar_timestamp")
    has_start = OPTIONAL_VOLBAR_START_COLUMN in volume_bars.columns

    instants = pl.concat(
        [
            _raw_breakout_instants(volume_bars, ORIGIN_A, bb_period_a, bb_num_std_a, has_start),
            _b_breakout_instants(time_bars, bb_period_b, bb_num_std_b),
        ],
        how="vertical",
    )
    if instants.is_empty():
        return _empty_feature_frame()

    # Deduplicación determinista: mismo timestamp -> gana el origen A.
    instants = (
        instants.sort([FEATURE_TIMESTAMP, _ORIGIN_COLUMN])
        .unique(subset=[FEATURE_TIMESTAMP], keep="first", maintain_order=True)
        .sort(FEATURE_TIMESTAMP)
    )

    time_ref = time_bars.select(
        pl.col("end_timestamp").alias(FEATURE_TIMESTAMP),
        pl.col("close").alias(_TB_CLOSE),
        pl.col(AVWAP_COLUMN).alias(_TB_AVWAP),
        pl.col(VOL_BUZZ_COLUMN),
    ).sort(FEATURE_TIMESTAMP)
    volbar_ref = volume_bars.select(
        pl.col("end_timestamp").alias(FEATURE_TIMESTAMP),
        pl.col("close").alias(_VB_CLOSE),
        _speed_expr(has_start).alias(_VB_SPEED),
    ).sort(FEATURE_TIMESTAMP)

    feats = instants.join_asof(time_ref, on=FEATURE_TIMESTAMP, strategy="backward")
    feats = feats.join_asof(volbar_ref, on=FEATURE_TIMESTAMP, strategy="backward")

    origin_is_a = pl.col(_ORIGIN_COLUMN) == ORIGIN_A
    feats = feats.with_columns(
        pl.when(origin_is_a)
        .then(pl.col(_A_DIST))
        .otherwise((pl.col(_TB_CLOSE) - pl.col(_VB_CLOSE)) / pl.col(_VB_CLOSE) * 100.0)
        .alias(FEATURE_DIST_LAST_VOLBAR_CLOSE_PCT),
        pl.when(origin_is_a)
        .then(pl.col(_A_SPEED))
        .otherwise(pl.col(_VB_SPEED))
        .alias(FEATURE_VOLBAR_SPEED_MS),
        ((pl.col(_TB_CLOSE) - pl.col(_TB_AVWAP)) / pl.col(_TB_AVWAP) * 100.0).alias(
            FEATURE_DIST_VS_AVWAP_PCT
        ),
    )

    adr_by_day = _prior_days_adr(time_bars, adr_lookback_days)
    feats = (
        feats.with_columns(pl.col(FEATURE_TIMESTAMP).dt.date().alias("_day"))
        .join(adr_by_day, on="_day", how="left")
        .drop("_day")
    )

    output = feats.select(list(FEATURE_OUTPUT_COLUMNS))

    if context_frame is not None:
        context_sorted = context_frame.sort(CONTEXT_KEY_COLUMN)
        joined = output.join_asof(context_sorted, on=FEATURE_TIMESTAMP, strategy="backward")
        return joined.select([*FEATURE_OUTPUT_COLUMNS, *context_columns])

    return output
