"""Módulo de microestructura: validación cruzada intraday (Issue #69).

Pipeline A (volume bars + Bollinger breakout), Pipeline B (time bars +
Vol Buzz Z-Score + AVWAP + Signal B) y el feature engine del dataset
híbrido. Capa de ingesta lazy DuckDB -> Polars incluida. El modelo híbrido
LightGBM y los kernels Numba se implementan en slices posteriores.
"""

from src.microstructure.data_pipeline import load_tick_data
from src.microstructure.feature_engine import (
    FEATURE_OUTPUT_COLUMNS,
    build_feature_frame,
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
    "DEFAULT_THRESHOLD_Z",
    "FEATURE_OUTPUT_COLUMNS",
    "TIME_BAR_OUTPUT_COLUMNS",
    "build_feature_frame",
    "build_time_bars",
    "build_volume_bars",
    "compute_avwap",
    "compute_bollinger_bands",
    "compute_vol_buzz_z",
    "generate_signal_a",
    "generate_signal_b",
    "load_tick_data",
]
