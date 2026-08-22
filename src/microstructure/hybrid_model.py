"""Modelo híbrido LightGBM walk-forward: dataset, target PIT e inferencia (Issue #69).

Propósito
---------
Tercera pieza del subsistema de validación cruzada intraday: convierte los
instantes de ruptura del ``feature_engine`` en un dataset etiquetado (target
binario 2R/1R PIT), entrena un clasificador binario LightGBM con walk-forward
CV (ventana expansiva estrictamente ordenada por timestamp) y expone una API
de inferencia con gate de capital por umbral de confianza.

Decisiones documentadas
-----------------------
- R (unidad de riesgo): distancia del stop estructural = ``stop_atr_mult *
  ATR``, con mult default 0.5 según la sección 4 del proposal ("SL <= 50%
  ATR"). El ATR usa la convención canónica del sistema (media móvil simple de
  N True Ranges, como ``signal_engine.compute_tier2_metrics``), con la
  variante documentada de PRIMERA barra: TR_0 = high - low (sin cierre
  previo). Primer valor válido en el índice ``atr_period - 1``.
- Etiquetado PIT por instante: la barra de ENTRADA es la última COMPLETADA
  (``end_timestamp <= instante``, join as-of backward). Se escanean las N
  ventanas posteriores sobre la serie de evaluación (time bars):
    * TP gana si ``high[j] > entrada + tp_r_mult * R`` (comparación ESTRICTA,
      el proposal exige "reach > 2R").
    * SL pierde si ``low[j] <= entrada - sl_r_mult * R`` (el TOQUE cuenta).
    * Ambos niveles en la MISMA ventana -> 0 (empate conservador; SL se
      evalúa primero).
    * Sin resolución dentro del horizonte -> 0 ("never resolves").
  ATR indefinido (warmup), R degenerado (<= 0 o no finito) o instantes sin
  barra de entrada previa -> etiqueta NULA (se excluye del entrenamiento).
  La función jamás lee ventanas más allá del horizonte ni barras futuras
  fuera de él (verificado por invarianza al truncamiento en los tests).
- Contexto: ``build_context_frame`` es un adaptador FINO que LLAMA funciones
  públicas existentes SIN modificarlas: ``signal_engine.compute_tier2_metrics``
  (RS como retorno relativo vs SPY) y ``utils.market_health.calculate_health_
  score_pit`` (score 0-7). Recorta SOLO días estrictamente PREVIOS al día del
  instante (PIT: una ruptura intraday no puede ver el cierre diario de su
  propio día). Import perezoso para no arrastrar la cadena pesada de screeners
  al importar microestructura. Cualquier fallo del API externo degrada a NULL
  (el contexto es OPCIONAL por diseño; nunca rompe el etiquetado).
- Entrenamiento: walk-forward con ventana EXPANSIVA: K folds => K+1 chunks
  contiguos ordenados por timestamp; el fold k entrena con chunks 0..k y testa
  el chunk k+1. Por construcción todo timestamp de train es < todo timestamp
  de test (sin fuga temporal). Desbalance de clases vía ``scale_pos_weight``
  (default automático n_neg/n_pos por fold, documentado). NaN legítimos de
  features (vol_buzz_z sin historia) se delegan al manejo nativo de LightGBM.
- Artefacto: saver NATIVO de LightGBM (texto) + sidecar JSON con las columnas
  de features. Default bajo ``outputs/microstructure/`` (gitignored:
  ``outputs/*``), nunca dentro de src/.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any

import lightgbm as lgb
import numpy as np
import pandas as pd
import polars as pl
from sklearn.metrics import precision_score, recall_score, roc_auc_score

from src.microstructure.feature_engine import (
    FEATURE_OUTPUT_COLUMNS,
    FEATURE_TIMESTAMP,
)

# ---------------------------------------------------------------------------
# Constantes nombradas (defaults del proposal/spec)
# ---------------------------------------------------------------------------

# Trade management (proposal sección 4): stop estructural <= 50% ATR.
DEFAULT_STOP_ATR_MULT = 0.5
DEFAULT_TP_R_MULT = 2.0
DEFAULT_SL_R_MULT = 1.0
# Horizonte de etiquetado: cantidad de ventanas forward a escanear.
DEFAULT_LABEL_HORIZON_WINDOWS = 20
# Convención canónica de ATR del sistema (14 períodos, como signal_engine).
DEFAULT_ATR_PERIOD = 14
# Gate de capital: despliega solo con probabilidad ESTRICTAMENTE mayor.
DEFAULT_CONFIDENCE_THRESHOLD = 0.75
# Walk-forward CV.
DEFAULT_K_FOLDS = 5
MIN_TRAIN_ROWS_PER_FOLD = 10
MIN_TEST_ROWS_PER_FOLD = 4
METRICS_DECISION_THRESHOLD = 0.5
DEFAULT_NUM_BOOST_ROUND = 200
DEFAULT_LEARNING_RATE = 0.05
DEFAULT_NUM_LEAVES = 31
DEFAULT_RANDOM_SEED = 42

# Columna de etiqueta binaria y directorio default de artefactos (gitignored).
LABEL_COLUMN = "label"
CONTEXT_RS_COLUMN = "rs_ret"
CONTEXT_HEALTH_COLUMN = "health_score"
ATR_COLUMN = "atr"
DEFAULT_MODEL_DIR = Path("outputs") / "microstructure"
DEFAULT_ARTIFACT_FILENAME = "hybrid_lightgbm.txt"
DEFAULT_RS_LOOKBACK = 60

REQUIRED_LABEL_BARS_COLUMNS: tuple[str, ...] = ("end_timestamp", "high", "low", "close")
_REQUIRED_DATASET_CORE_COLUMNS: tuple[str, ...] = tuple(FEATURE_OUTPUT_COLUMNS)

_NUMERIC_DTYPES: tuple[pl.DataType, ...] = (
    pl.Int8, pl.Int16, pl.Int32, pl.Int64,
    pl.UInt8, pl.UInt16, pl.UInt32, pl.UInt64,
    pl.Float32, pl.Float64,
)


def _validate_columns(
    frame: pl.DataFrame, required: tuple[str, ...], context: str
) -> None:
    """Valida presencia de columnas obligatorias nombrando TODAS las faltantes.

    Parámetros: frame — DataFrame a validar; required — columnas exigidas;
    context — etiqueta del error. Retorno: None. Lanza ValueError si falta
    alguna.
    """
    missing = [column for column in required if column not in frame.columns]
    if missing:
        raise ValueError(
            f"Faltan columnas obligatorias ({context}): {missing}. "
            f"Encontradas: {frame.columns}."
        )


# ---------------------------------------------------------------------------
# ATR canónico
# ---------------------------------------------------------------------------


def compute_atr_series(bars: pl.DataFrame, atr_period: int = DEFAULT_ATR_PERIOD) -> pl.Series:
    """Calcula el ATR (media móvil simple de True Range) alineado a las filas.

    TR_i = max(high-low, |high-prev_close|, |low-prev_close|); la primera
    barra no tiene cierre previo -> TR_0 = high - low (convención documentada
    del módulo). ATR = rolling_mean(TR, atr_period) con min_samples completo:
    primer valor válido en el índice ``atr_period - 1``.

    Parámetros: bars — DataFrame con high/low/close en orden temporal;
    atr_period — ventana (> 0). Default DEFAULT_ATR_PERIOD (canónico 14).

    Retorno: pl.Series Float64 llamada 'atr'. Barras vacías -> serie vacía.
    Lanza ValueError si faltan columnas o el período no es positivo.
    """
    _validate_columns(bars, ("high", "low", "close"), "barras para ATR")
    if atr_period < 1:
        raise ValueError(f"atr_period debe ser >= 1, recibido: {atr_period}")

    if bars.is_empty():
        return pl.Series(ATR_COLUMN, [], dtype=pl.Float64)

    high = pl.col("high")
    low = pl.col("low")
    close = pl.col("close")
    prev_close = close.shift(1)
    true_range = (
        pl.when(prev_close.is_null())
        .then(high - low)
        .otherwise(
            pl.max_horizontal(high - low, (high - prev_close).abs(), (low - prev_close).abs())
        )
    )
    atr = bars.select(true_range.alias("_tr")).select(
        pl.col("_tr").rolling_mean(window_size=atr_period, min_samples=atr_period).alias(ATR_COLUMN)
    )
    return atr.to_series()


# ---------------------------------------------------------------------------
# Target labeling (PIT-safe)
# ---------------------------------------------------------------------------


def label_breakout_instants(
    feature_frame: pl.DataFrame,
    evaluation_bars: pl.DataFrame,
    *,
    stop_atr_mult: float = DEFAULT_STOP_ATR_MULT,
    tp_r_mult: float = DEFAULT_TP_R_MULT,
    sl_r_mult: float = DEFAULT_SL_R_MULT,
    horizon_windows: int = DEFAULT_LABEL_HORIZON_WINDOWS,
    atr_period: int = DEFAULT_ATR_PERIOD,
) -> pl.DataFrame:
    """Etiqueta cada instante de ruptura con el desenlace 2R/1R (PIT).

    Parámetros:
        feature_frame: salida del feature engine (columna 'timestamp'
            obligatoria; las demás columnas se ignoran aquí).
        evaluation_bars: serie de precios para evaluar el horizonte (time
            bars del Pipeline B) con end_timestamp/high/low/close.
        stop_atr_mult: multiplicador del ATR que define R (default 0.5,
            propuesta sección 4).
        tp_r_mult / sl_r_mult: niveles de TP (> 2R, comparación ESTRICTA) y
            SL (1R, el toque cuenta) en múltiplos de R.
        horizon_windows: cantidad de ventanas forward a escanear (N).
        atr_period: ventana del ATR canónico que define R.

    Retorno: DataFrame [timestamp, label] ordenado por timestamp. label es
    Int64 con posibles NULOS (ATR indefinido, R degenerado o sin barra de
    entrada previa). Política de empate: SL y TP en la misma ventana -> 0.

    Lanza ValueError ante columnas faltantes, timestamps duplicados o
    parámetros no positivos.
    """
    _validate_columns(feature_frame, (FEATURE_TIMESTAMP,), "feature frame para labeling")
    _validate_columns(evaluation_bars, REQUIRED_LABEL_BARS_COLUMNS, "barras de evaluación")
    if stop_atr_mult <= 0 or tp_r_mult <= 0 or sl_r_mult <= 0:
        raise ValueError("stop_atr_mult, tp_r_mult y sl_r_mult deben ser > 0")
    if horizon_windows < 1:
        raise ValueError(f"horizon_windows debe ser >= 1, recibido: {horizon_windows}")
    if atr_period < 1:
        raise ValueError(f"atr_period debe ser >= 1, recibido: {atr_period}")
    if feature_frame[FEATURE_TIMESTAMP].n_unique() != len(feature_frame):
        raise ValueError("El frame de features contiene timestamps duplicados")

    if feature_frame.is_empty() or evaluation_bars.is_empty():
        return pl.DataFrame(
            schema={FEATURE_TIMESTAMP: pl.Datetime("us"), LABEL_COLUMN: pl.Int64}
        )

    bars = evaluation_bars.sort("end_timestamp")
    ends = bars["end_timestamp"].to_numpy()
    highs = bars["high"].to_numpy()
    lows = bars["low"].to_numpy()
    closes = bars["close"].to_numpy()
    atr_values = compute_atr_series(bars, atr_period=atr_period).to_numpy()

    instants_frame = feature_frame.sort(FEATURE_TIMESTAMP)
    instants = instants_frame[FEATURE_TIMESTAMP].to_numpy()
    entry_indices = np.searchsorted(ends, instants, side="right") - 1

    labels: list[int | None] = []
    for position, entry_index in enumerate(entry_indices):
        if entry_index < 0:
            labels.append(None)
            continue
        atr_here = atr_values[entry_index]
        if not np.isfinite(atr_here):
            labels.append(None)
            continue
        risk_unit = stop_atr_mult * float(atr_here)
        if risk_unit <= 0.0:
            labels.append(None)
            continue
        entry_price = float(closes[entry_index])
        take_profit = entry_price + tp_r_mult * risk_unit
        stop_loss = entry_price - sl_r_mult * risk_unit

        label = 0
        upper = min(entry_index + horizon_windows + 1, len(bars))
        for j in range(entry_index + 1, upper):
            # SL primero: si ambos niveles caen en la MISMA ventana el empate
            # se resuelve de forma conservadora como 0.
            if lows[j] <= stop_loss:
                break
            if highs[j] > take_profit:
                label = 1
                break
        labels.append(label)

    return pl.DataFrame(
        {
            FEATURE_TIMESTAMP: list(instants_frame[FEATURE_TIMESTAMP]),
            LABEL_COLUMN: pl.Series(labels, dtype=pl.Int64),
        }
    )


# ---------------------------------------------------------------------------
# Ensamblado del dataset
# ---------------------------------------------------------------------------


def assemble_dataset(
    feature_frame: pl.DataFrame,
    *,
    labels_frame: pl.DataFrame | None = None,
    context_frame: pl.DataFrame | None = None,
) -> pl.DataFrame:
    """Ensamblo el dataset de entrenamiento con contrato de columnas fijo.

    Filas = instantes de ruptura del feature engine (+ columnas de contexto
    ya fusionadas si corresponde). Determinista: salida ordenada por
    timestamp.

    Parámetros:
        feature_frame: frame de features con las seis columnas core
            (FEATURE_OUTPUT_COLUMNS); columnas extra numéricas se preservan
            como features adicionales.
        labels_frame: opcional [timestamp, label]; join EXACTO por timestamp.
            Instantes sin etiqueta sobreviven con label nulo.
        context_frame: opcional con columna 'timestamp' y features libres;
            join as-of backward (consistente con feature_engine).

    Retorno: DataFrame ordenado con [features..., contexto..., label].

    Lanza ValueError por columnas core faltantes, timestamps duplicados,
    colisión de nombres o labels duplicadas/malformadas.
    """
    _validate_columns(feature_frame, _REQUIRED_DATASET_CORE_COLUMNS, "feature frame")
    if LABEL_COLUMN in feature_frame.columns:
        raise ValueError(f"El frame de features ya contiene la columna reservada '{LABEL_COLUMN}'")
    if feature_frame[FEATURE_TIMESTAMP].n_unique() != len(feature_frame):
        raise ValueError("El frame de features contiene timestamps duplicados")

    dataset = feature_frame.sort(FEATURE_TIMESTAMP)

    if context_frame is not None:
        _validate_columns(context_frame, (FEATURE_TIMESTAMP,), "frame de contexto")
        context_columns = [
            column for column in context_frame.columns if column != FEATURE_TIMESTAMP
        ]
        collisions = sorted(set(context_columns) & set(dataset.columns))
        if collisions:
            raise ValueError(
                f"El frame de contexto colisiona con columnas del dataset: {collisions}."
            )
        dataset = dataset.join_asof(
            context_frame.sort(FEATURE_TIMESTAMP),
            on=FEATURE_TIMESTAMP,
            strategy="backward",
        )

    if labels_frame is not None:
        _validate_columns(labels_frame, (FEATURE_TIMESTAMP, LABEL_COLUMN), "frame de labels")
        if labels_frame[FEATURE_TIMESTAMP].n_unique() != len(labels_frame):
            raise ValueError("El frame de labels contiene timestamps duplicados")
        dataset = dataset.join(labels_frame, on=FEATURE_TIMESTAMP, how="left")
    else:
        dataset = dataset.with_columns(pl.lit(None, dtype=pl.Int64).alias(LABEL_COLUMN))

    return dataset


# ---------------------------------------------------------------------------
# Adaptadores de contexto hacia módulos existentes (SIN modificarlos)
# ---------------------------------------------------------------------------


def _normalized_daily(frame: pd.DataFrame, name: str) -> pd.DataFrame:
    """Normaliza un OHLCV diario a copia lowercase ordenada por fecha.

    Contrato: DatetimeIndex O alguna columna date/datetime/timestamp. Las
    APIs externas mutan nombres de columna (p. ej. market_health hace
    ``df.columns = [...]``), por eso SIEMPRE se trabaja sobre copias.
    """
    if frame is None or len(frame) == 0:
        return pd.DataFrame()
    normalized = frame.copy()
    normalized.columns = [str(column).lower() for column in normalized.columns]
    if not isinstance(normalized.index, pd.DatetimeIndex):
        for key in ("date", "datetime", "timestamp"):
            if key in normalized.columns:
                normalized = normalized.set_index(
                    pd.DatetimeIndex(pd.to_datetime(normalized[key]))
                ).drop(columns=[key])
                break
        else:
            raise ValueError(
                f"{name} debe traer DatetimeIndex o una columna de fecha "
                "(date/datetime/timestamp)."
            )
    return normalized.sort_index()


def _prior_days(frame: pd.DataFrame, day: date) -> pd.DataFrame | None:
    """Recorte PIT: filas con fecha ESTRICTAMENTE anterior a ``day``."""
    if frame.empty:
        return None
    prior = frame[[index_date < day for index_date in frame.index.date]]
    return prior if len(prior) > 0 else None


def _rs_value(prior_ticker: pd.DataFrame | None, prior_spy: pd.DataFrame | None, lookback: int) -> float | None:
    """RS vía signal_engine.compute_tier2_metrics (retorno relativo vs SPY).

    Degradación elegante: historia insuficiente o cualquier fallo -> None
    (la columna de contexto es opcional por diseño).
    """
    if prior_ticker is None or prior_spy is None:
        return None
    try:
        from src.signals.signal_engine import compute_tier2_metrics

        metrics = compute_tier2_metrics(prior_ticker, prior_spy, rs_lookback=lookback)
        value = getattr(metrics, "rs_ret", None)
        return float(value) if value is not None else None
    except Exception:
        return None


def _health_value(prior_spy: pd.DataFrame | None, prior_vix: pd.DataFrame | None) -> int | None:
    """health_score 0-7 vía utils.market_health.calculate_health_score_pit."""
    if prior_spy is None:
        return None
    try:
        from src.utils.market_health import calculate_health_score_pit

        vix_arg = prior_vix.copy() if prior_vix is not None else None
        return int(calculate_health_score_pit(prior_spy.copy(), vix_arg))
    except Exception:
        return None


def build_context_frame(
    breakout_timestamps: list[datetime] | pl.Series,
    ticker_daily: pd.DataFrame,
    spy_daily: pd.DataFrame,
    vix_daily: pd.DataFrame | None = None,
    *,
    rs_lookback: int = DEFAULT_RS_LOOKBACK,
) -> pl.DataFrame:
    """Construye el frame de contexto (rs_ret, health_score) por instante.

    Parámetros:
        breakout_timestamps: instantes de ruptura (uno por fila de salida).
        ticker_daily / spy_daily / vix_daily: OHLCV diarios (pandas) con
            DatetimeIndex o columna de fecha; se normalizan a copias
            lowercase internas.
        rs_lookback: ventana del RS relativo (60 días default del sistema).

    Retorno: polars.DataFrame [timestamp, rs_ret (Float64 nullable),
    health_score (Int64)]. Los valores se calculan UNA vez por fecha única y
    usan SOLO días estrictamente previos (PIT). Falta de historia o fallo del
    API externo -> valores nulos, nunca excepción.

    Lanza ValueError solo por parámetros inválidos (rs_lookback < 1) o frames
    sin información de fecha.
    """
    if rs_lookback < 1:
        raise ValueError(f"rs_lookback debe ser >= 1, recibido: {rs_lookback}")

    stamps = (
        breakout_timestamps.to_list()
        if isinstance(breakout_timestamps, pl.Series)
        else list(breakout_timestamps)
    )
    if not stamps:
        return pl.DataFrame(
            schema={
                FEATURE_TIMESTAMP: pl.Datetime("us"),
                CONTEXT_RS_COLUMN: pl.Float64,
                CONTEXT_HEALTH_COLUMN: pl.Int64,
            }
        )

    ticker_norm = _normalized_daily(ticker_daily, "ticker_daily")
    spy_norm = _normalized_daily(spy_daily, "spy_daily")
    vix_norm = _normalized_daily(vix_daily, "vix_daily") if vix_daily is not None else pd.DataFrame()

    cache: dict[date, tuple[float | None, int | None]] = {}
    values: list[tuple[float | None, int | None]] = []
    for stamp in stamps:
        day = stamp.date()
        if day not in cache:
            prior_ticker = _prior_days(ticker_norm, day)
            prior_spy = _prior_days(spy_norm, day)
            prior_vix = _prior_days(vix_norm, day)
            cache[day] = (
                _rs_value(prior_ticker, prior_spy, rs_lookback),
                _health_value(prior_spy, prior_vix),
            )
        values.append(cache[day])

    return pl.DataFrame(
        {
            FEATURE_TIMESTAMP: stamps,
            CONTEXT_RS_COLUMN: pl.Series([pair[0] for pair in values], dtype=pl.Float64),
            CONTEXT_HEALTH_COLUMN: pl.Series([pair[1] for pair in values], dtype=pl.Int64),
        }
    )


# ---------------------------------------------------------------------------
# Walk-forward training (LightGBM)
# ---------------------------------------------------------------------------


@dataclass
class FoldReport:
    """Métricas y límites temporales de un fold walk-forward."""

    fold_id: int
    train_start: datetime
    train_end: datetime
    test_start: datetime
    test_end: datetime
    n_train: int
    n_test: int
    precision: float | None
    recall: float | None
    auc: float | None
    scale_pos_weight: float


@dataclass
class WalkForwardResult:
    """Resultado del entrenamiento: folds reportados + modelo final."""

    feature_columns: list[str]
    folds: list[FoldReport]
    model: Any  # lightgbm.Booster entrenado sobre TODO el dataset efectivo


@dataclass
class LoadedHybridModel:
    """Artefacto recargado: booster + contrato de columnas de features."""

    model: Any
    feature_columns: list[str]


def _feature_matrix(frame: pl.DataFrame, feature_columns: list[str]) -> np.ndarray:
    """Matriz numpy float64 de features; NaN nativos preservados (LightGBM)."""
    matrix = frame.select(feature_columns).to_numpy()
    return np.asarray(matrix, dtype=np.float64)


def _auto_scale_pos_weight(y: np.ndarray) -> float:
    """Peso automático n_neg/n_pos; sin positivos -> 1.0 (neutro)."""
    positives = int((y == 1).sum())
    negatives = int((y == 0).sum())
    if positives == 0:
        return 1.0
    return negatives / positives


def _train_booster(
    x_train: np.ndarray,
    y_train: np.ndarray,
    *,
    learning_rate: float,
    num_leaves: int,
    num_boost_round: int,
    scale_pos_weight: float,
) -> Any:
    """Entrena un Booster binario determinista (seed fijo, 1 thread)."""
    params = {
        "objective": "binary",
        "learning_rate": learning_rate,
        "num_leaves": num_leaves,
        "scale_pos_weight": scale_pos_weight,
        "verbosity": -1,
        "seed": DEFAULT_RANDOM_SEED,
        "num_threads": 1,
        "deterministic": True,
    }
    dataset = lgb.Dataset(x_train, label=y_train)
    return lgb.train(params, dataset, num_boost_round=num_boost_round)


def train_walk_forward(
    dataset: pl.DataFrame,
    *,
    k_folds: int = DEFAULT_K_FOLDS,
    num_boost_round: int = DEFAULT_NUM_BOOST_ROUND,
    learning_rate: float = DEFAULT_LEARNING_RATE,
    num_leaves: int = DEFAULT_NUM_LEAVES,
    scale_pos_weight: float | None = None,
) -> WalkForwardResult:
    """Entrena el híbrido con CV walk-forward expansiva ordenada por timestamp.

    K folds => K+1 chunks contiguos de filas ordenadas: el fold k entrena con
    los chunks 0..k y valida contra el chunk k+1 (todo train < todo test).
    Métricas por fold: precision/recall al umbral METRICS_DECISION_THRESHOLD
    (zero_division=0) y AUC cuando el fold tiene ambas clases (si no, None).

    Parámetros:
        dataset: salida de assemble_dataset ([timestamp, features..., label]).
        k_folds: cantidad de folds (>= 1). Default DEFAULT_K_FOLDS.
        num_boost_round / learning_rate / num_leaves: hiperparámetros base
            (la búsqueda Optuna llega en el slice 3B).
        scale_pos_weight: None -> automático por fold (n_neg/n_pos del split
            de entrenamiento); valor explícito se respeta tal cual.

    Retorno: WalkForwardResult con folds[] y modelo FINAL entrenado sobre
    todas las filas efectivas (label no nula).

    Lanza ValueError ante argumentos inválidos, columnas faltantes, features
    no numéricas o datasets demasiado chicos para los mínimos por fold.
    """
    required = (FEATURE_TIMESTAMP, LABEL_COLUMN)
    missing = [column for column in required if column not in dataset.columns]
    if missing:
        raise ValueError(
            f"Faltan columnas obligatorias (dataset): {missing}. "
            f"Encontradas: {dataset.columns}."
        )
    if k_folds < 1:
        raise ValueError(f"k_folds debe ser >= 1, recibido: {k_folds}")
    if dataset[FEATURE_TIMESTAMP].n_unique() != len(dataset):
        raise ValueError("El dataset contiene timestamps duplicados")

    feature_columns = [
        column for column in dataset.columns if column not in required
    ]
    if not feature_columns:
        raise ValueError("El dataset no tiene columnas de features además de timestamp/label")
    non_numeric = [
        column for column in feature_columns if dataset.schema[column] not in _NUMERIC_DTYPES
    ]
    if non_numeric:
        raise ValueError(
            f"Las features deben ser numéricas; columnas no numéricas: {non_numeric}."
        )

    effective = dataset.filter(pl.col(LABEL_COLUMN).is_not_null()).sort(FEATURE_TIMESTAMP)
    n_effective = len(effective)
    chunks = np.array_split(np.arange(n_effective), k_folds + 1)

    initial_train = len(chunks[0])
    if initial_train < MIN_TRAIN_ROWS_PER_FOLD or any(
        len(chunk) < MIN_TEST_ROWS_PER_FOLD for chunk in chunks[1:]
    ):
        raise ValueError(
            "Dataset demasiado chico para walk-forward: se requieren >= "
            f"{MIN_TRAIN_ROWS_PER_FOLD} filas de train inicial y >= "
            f"{MIN_TEST_ROWS_PER_FOLD} por fold de test; recibidas "
            f"{n_effective} filas efectivas para k_folds={k_folds}."
        )

    stamps = effective[FEATURE_TIMESTAMP].to_list()
    x_all = _feature_matrix(effective, feature_columns)
    y_all = effective[LABEL_COLUMN].cast(pl.Int64).to_numpy()

    folds: list[FoldReport] = []
    for fold_id in range(1, k_folds + 1):
        train_idx = np.concatenate(chunks[:fold_id])
        test_idx = chunks[fold_id]
        x_train, y_train = x_all[train_idx], y_all[train_idx]
        x_test, y_test = x_all[test_idx], y_all[test_idx]

        spw = scale_pos_weight if scale_pos_weight is not None else _auto_scale_pos_weight(y_train)
        booster = _train_booster(
            x_train,
            y_train,
            learning_rate=learning_rate,
            num_leaves=num_leaves,
            num_boost_round=num_boost_round,
            scale_pos_weight=float(spw),
        )
        probabilities = booster.predict(x_test)
        predicted = (probabilities > METRICS_DECISION_THRESHOLD).astype(int)

        auc: float | None
        try:
            auc = float(roc_auc_score(y_test, probabilities))
        except ValueError:
            auc = None  # fold con una sola clase: AUC indefinida

        folds.append(
            FoldReport(
                fold_id=fold_id,
                train_start=stamps[train_idx[0]],
                train_end=stamps[train_idx[-1]],
                test_start=stamps[test_idx[0]],
                test_end=stamps[test_idx[-1]],
                n_train=int(len(train_idx)),
                n_test=int(len(test_idx)),
                precision=float(precision_score(y_test, predicted, zero_division=0)),
                recall=float(recall_score(y_test, predicted, zero_division=0)),
                auc=auc,
                scale_pos_weight=float(spw),
            )
        )

    spw_final = scale_pos_weight if scale_pos_weight is not None else _auto_scale_pos_weight(y_all)
    final_model = _train_booster(
        x_all,
        y_all,
        learning_rate=learning_rate,
        num_leaves=num_leaves,
        num_boost_round=num_boost_round,
        scale_pos_weight=float(spw_final),
    )
    return WalkForwardResult(
        feature_columns=list(feature_columns), folds=folds, model=final_model
    )


# ---------------------------------------------------------------------------
# Inferencia, gate de capital y artefactos
# ---------------------------------------------------------------------------


def predict_probability(
    bundle: WalkForwardResult | LoadedHybridModel, feature_frame: pl.DataFrame
) -> list[float]:
    """API estilo predict_proba: probabilidad de éxito por fila en [0, 1].

    Parámetros: bundle — resultado de entrenamiento o artefacto recargado
    (ambos exponen .model y .feature_columns); feature_frame — filas a
    puntuar (selecciona SOLO feature_columns; timestamp/label se ignoran).

    Retorno: lista de floats en [0, 1] (objetivo binario => sigmoide).
    """
    matrix = _feature_matrix(feature_frame, list(bundle.feature_columns))
    return [float(value) for value in bundle.model.predict(matrix)]


def should_deploy_capital(
    probability: float, threshold: float = DEFAULT_CONFIDENCE_THRESHOLD
) -> bool:
    """Gate de capital: despliega SOLO si probabilidad > umbral (estricto).

    Parámetros: probability — salida de predict_probability; threshold —
    umbral de confianza (default DEFAULT_CONFIDENCE_THRESHOLD = 0.75).

    Retorno: bool. Lanza ValueError si la probabilidad no está en [0, 1] o el
    umbral fuera de (0, 1).
    """
    if not np.isfinite(probability) or not (0.0 <= probability <= 1.0):
        raise ValueError(f"probability debe estar en [0, 1], recibido: {probability}")
    if not (0.0 < threshold < 1.0):
        raise ValueError(f"threshold debe estar en (0, 1), recibido: {threshold}")
    return bool(probability > threshold)


def save_model(
    result: WalkForwardResult, path: str | Path | None = None
) -> Path:
    """Persiste el modelo con el saver NATIVO de LightGBM + sidecar JSON.

    El sidecar guarda el contrato de columnas de features para que la carga
    sea autónoma. Directorio default: DEFAULT_MODEL_DIR (outputs/microstructure/,
    gitignored — los artefactos son locales, nunca dentro de src/).

    Parámetros: result — WalkForwardResult; path — destino explícito u omitir
    para usar el default.

    Retorno: Path del archivo escrito.
    """
    artifact_path = Path(path) if path is not None else DEFAULT_MODEL_DIR / DEFAULT_ARTIFACT_FILENAME
    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    result.model.save_model(str(artifact_path))
    meta_path = artifact_path.with_name(artifact_path.name + ".meta.json")
    meta_path.write_text(
        json.dumps({"feature_columns": result.feature_columns}), encoding="utf-8"
    )
    return artifact_path


def load_model(path: str | Path) -> LoadedHybridModel:
    """Recarga un artefacto guardado con save_model (booster + sidecar).

    Parámetros: path — archivo del booster escrito por save_model.

    Retorno: LoadedHybridModel listo para predict_probability.
    """
    artifact_path = Path(path)
    meta_path = artifact_path.with_name(artifact_path.name + ".meta.json")
    metadata = json.loads(meta_path.read_text(encoding="utf-8"))
    booster = lgb.Booster(model_file=str(artifact_path))
    return LoadedHybridModel(model=booster, feature_columns=list(metadata["feature_columns"]))
