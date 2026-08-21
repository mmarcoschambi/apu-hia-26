"""Módulo de microestructura: validación cruzada intraday (Issue #69).

Capa de ingesta lazy de ticks con DuckDB -> Polars. Pipeline A (volume bars),
Pipeline B, feature engineering, modelo híbrido y kernels Numba se integran en
slices posteriores.
"""
