"""Módulo de microestructura: validación cruzada intraday (Issue #69).

Pipeline A (volume bars + Bollinger breakout) y capa de ingesta lazy de ticks
con DuckDB -> Polars. Pipeline B, feature engineering, modelo híbrido y
kernels Numba se implementan en slices posteriores.
"""

from src.microstructure.data_pipeline import load_tick_data
from src.microstructure.volume_bars import (
    build_volume_bars,
    compute_bollinger_bands,
    generate_signal_a,
)

__all__ = [
    "build_volume_bars",
    "compute_bollinger_bands",
    "generate_signal_a",
    "load_tick_data",
]
