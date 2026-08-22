"""Tests de la capa de ingesta lazy con DuckDB (src.microstructure.data_pipeline).

Contrato bajo test:
- Entrada: CSV/Parquet de ticks con columnas Timestamp, Price, Volume, Bid, Ask.
- Filtrado RTH en SQL sobre disco (sin cargar el archivo completo a pandas).
- Sesión RTH = [09:30:00, 16:00:00) en America/New_York (límite inferior
  inclusivo, superior exclusivo).
- Timestamps naive se interpretan en ``source_tz`` (default UTC) y se convierten
  a hora de Nueva York respetando DST.
- Salida: polars.DataFrame ordenado por Timestamp.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import polars as pl
import pytest

from src.microstructure.data_pipeline import (
    DEFAULT_SOURCE_TZ,
    REQUIRED_TICK_COLUMNS,
    load_tick_data,
)


def _base_ticks() -> pl.DataFrame:
    """Ticks sintéticos de un día invernal (EST = UTC-5).

    | Timestamp (UTC)  | Hora NY   | Esperado            |
    |------------------|-----------|---------------------|
    | 13:15:00         | 08:15     | excluido pre-market |
    | 14:29:59         | 09:29:59  | excluido            |
    | 14:30:00         | 09:30:00  | INCLUÍDO (borde)    |
    | 15:00:00         | 10:00     | incluido            |
    | 20:59:59         | 15:59:59  | incluido            |
    | 21:00:00         | 16:00:00  | excluido (borde sup. exclusivo) |
    """
    return pl.DataFrame(
        {
            "Timestamp": [
                datetime(2024, 1, 10, 13, 15, 0),
                datetime(2024, 1, 10, 14, 29, 59),
                datetime(2024, 1, 10, 14, 30, 0),
                datetime(2024, 1, 10, 15, 0, 0),
                datetime(2024, 1, 10, 20, 59, 59),
                datetime(2024, 1, 10, 21, 0, 0),
            ],
            "Price": [100.0, 100.5, 101.0, 101.5, 102.0, 102.5],
            "Volume": [100, 50, 200, 300, 400, 500],
            "Bid": [99.98, 100.48, 100.98, 101.48, 101.98, 102.48],
            "Ask": [100.02, 100.52, 101.02, 101.52, 102.02, 102.52],
        }
    )


def test_csv_rth_filter_and_boundary_inclusion(tmp_path: Path) -> None:
    """Filtra pre/after-market en SQL e incluye el borde de apertura 09:30."""
    path = tmp_path / "ticks.csv"
    _base_ticks().write_csv(path)

    result = load_tick_data(path)

    assert isinstance(result, pl.DataFrame)
    assert result.columns == list(REQUIRED_TICK_COLUMNS)
    assert result["Timestamp"].to_list() == [
        datetime(2024, 1, 10, 14, 30, 0),  # 09:30:00 NY — borde inclusivo
        datetime(2024, 1, 10, 15, 0, 0),
        datetime(2024, 1, 10, 20, 59, 59),  # 15:59:59 NY — último segundo RTH
    ]
    # El tick de apertura conserva sus valores intactos.
    open_row = result.row(0, named=True)
    assert open_row["Price"] == 101.0
    assert open_row["Volume"] == 200


def test_parquet_source_matches_csv(tmp_path: Path) -> None:
    """Parquet y CSV producen el mismo resultado para el mismo contenido."""
    csv_path = tmp_path / "ticks.csv"
    parquet_path = tmp_path / "ticks.parquet"
    ticks = _base_ticks()
    ticks.write_csv(csv_path)
    ticks.write_parquet(parquet_path)

    from_csv = load_tick_data(csv_path)
    from_parquet = load_tick_data(parquet_path)

    assert from_parquet.equals(from_csv)


def test_dst_summer_offset_is_honored(tmp_path: Path) -> None:
    """En verano (EDT = UTC-4), el borde 09:30 NY equivale a 13:30 UTC.

    Una conversión con offset fijo (-5 todo el año) fallaría este caso.
    """
    path = tmp_path / "summer.parquet"
    pl.DataFrame(
        {
            "Timestamp": [datetime(2024, 7, 10, 13, 29, 59), datetime(2024, 7, 10, 13, 30, 0)],
            "Price": [50.0, 50.5],
            "Volume": [10, 20],
            "Bid": [49.99, 50.49],
            "Ask": [50.01, 50.51],
        }
    ).write_parquet(path)

    result = load_tick_data(path)

    assert result["Timestamp"].to_list() == [datetime(2024, 7, 10, 13, 30, 0)]


def test_naive_wall_clock_with_source_tz_new_york(tmp_path: Path) -> None:
    """Con source_tz=America/New_York los stamps ya están en hora local NY."""
    path = tmp_path / "local.csv"
    pl.DataFrame(
        {
            "Timestamp": [
                datetime(2024, 1, 10, 9, 29, 59),
                datetime(2024, 1, 10, 9, 30, 0),
                datetime(2024, 1, 10, 16, 0, 0),
            ],
            "Price": [10.0, 11.0, 12.0],
            "Volume": [1, 2, 3],
            "Bid": [9.99, 10.99, 11.99],
            "Ask": [10.01, 11.01, 12.01],
        }
    ).write_csv(path)

    result = load_tick_data(path, source_tz="America/New_York")

    assert result["Timestamp"].to_list() == [datetime(2024, 1, 10, 9, 30, 0)]


def test_missing_required_column_raises_value_error(tmp_path: Path) -> None:
    """Faltan columnas obligatorias -> ValueError nombrándolas todas."""
    path = tmp_path / "broken.csv"
    pl.DataFrame(
        {
            "Timestamp": [datetime(2024, 1, 10, 15, 0, 0)],
            "Price": [1.0],
        }
    ).write_csv(path)

    with pytest.raises(ValueError) as exc_info:
        load_tick_data(path)

    message = str(exc_info.value)
    assert "Volume" in message
    assert "Bid" in message
    assert "Ask" in message


def test_all_ticks_outside_rth_returns_empty_with_schema(tmp_path: Path) -> None:
    """Si ningún tick cae en RTH devuelve un DF vacío pero tipado."""
    path = tmp_path / "premarket_only.csv"
    pl.DataFrame(
        {
            "Timestamp": [datetime(2024, 1, 10, 13, 15, 0)],
            "Price": [100.0],
            "Volume": [100],
            "Bid": [99.98],
            "Ask": [100.02],
        }
    ).write_csv(path)

    result = load_tick_data(path)

    assert isinstance(result, pl.DataFrame)
    assert result.columns == list(REQUIRED_TICK_COLUMNS)
    assert len(result) == 0


def test_unsupported_extension_raises_value_error(tmp_path: Path) -> None:
    """Extensión no soportada -> ValueError inmediato."""
    path = tmp_path / "ticks.xlsx"

    with pytest.raises(ValueError):
        load_tick_data(path)


def test_default_source_tz_constant_is_utc() -> None:
    """El timezone por defecto de entrada es UTC (contrato documentado)."""
    assert DEFAULT_SOURCE_TZ == "UTC"
