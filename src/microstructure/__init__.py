"""Módulo de microestructura: validación cruzada intraday (Issue #69).

Pipeline A (volume bars + Bollinger breakout), Pipeline B (time bars +
Vol Buzz Z-Score + AVWAP + Signal B), el feature engine del dataset híbrido
y el modelo LightGBM walk-forward (etiquetado PIT 2R/1R, CV expansiva,
inferencia con gate de capital). Capa de ingesta lazy DuckDB -> Polars
incluida. Los kernels Numba vectorizados llegan en el slice siguiente.
"""

from src.microstructure.data_pipeline import load_tick_data
from src.microstructure.feature_engine import (
    FEATURE_OUTPUT_COLUMNS,
    build_feature_frame,
)
from src.microstructure.hybrid_model import (
    DEFAULT_CONFIDENCE_THRESHOLD,
    LABEL_COLUMN,
    assemble_dataset,
    build_context_frame,
    compute_atr_series,
    label_breakout_instants,
    load_model,
    predict_probability,
    save_model,
    should_deploy_capital,
    train_walk_forward,
)
from src.microstructure.time_bars import (
    DEFAULT_THRESHOLD_Z,
    TIME_BAR_OUTPUT_COLUMNS,
    build_time_bars,
    compute_avwap,
    compute_vol_buzz_z,
    generate_signal_b,
)
from src.microstructure.volume_bars import (
    build_volume_bars,
    compute_bollinger_bands,
    generate_signal_a,
)

__all__ = [
    "DEFAULT_CONFIDENCE_THRESHOLD",
    "DEFAULT_THRESHOLD_Z",
    "FEATURE_OUTPUT_COLUMNS",
    "LABEL_COLUMN",
    "TIME_BAR_OUTPUT_COLUMNS",
    "assemble_dataset",
    "build_context_frame",
    "build_feature_frame",
    "build_time_bars",
    "build_volume_bars",
    "compute_atr_series",
    "compute_avwap",
    "compute_bollinger_bands",
    "compute_vol_buzz_z",
    "generate_signal_a",
    "generate_signal_b",
    "label_breakout_instants",
    "load_model",
    "load_tick_data",
    "predict_probability",
    "save_model",
    "should_deploy_capital",
    "train_walk_forward",
]
