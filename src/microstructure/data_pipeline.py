"""Capa de ingesta lazy de ticks: DuckDB sobre disco -> Polars en RAM.

Propósito
---------
Leer datos tick-a-tick (CSV/Parquet) con consultas SQL *lazy* de DuckDB,
filtrar la sesión Regular Trading Hours (RTH) dentro del motor de base de
datos ANTES de materializar filas, y devolver un ``polars.DataFrame`` para el
procesamiento vectorizado aguas abajo. El archivo nunca se carga completo a
pandas: DuckDB proyecta y filtra sobre disco en streaming, manteniendo el uso
de memoria acotado incluso con archivos de millones de filas.

Convención temporal
-------------------
- La columna ``Timestamp`` debe ser naive y se interpreta en la zona horaria
  ``source_tz`` (default UTC). Luego se convierte a hora de pared de
  ``America/New_York`` respetando DST (DuckDB ``AT TIME ZONE``).
- Ventana RTH = [09:30:00, 16:00:00): el borde inferior es inclusivo (print de
  apertura de las 09:30) y el superior exclusivo, para no mezclar operaciones
  estampadas después del cierre.
"""

from __future__ import annotations

from datetime import time
from pathlib import Path

import duckdb
import polars as pl

DEFAULT_SOURCE_TZ = "UTC"
RTH_TIMEZONE = "America/New_York"
RTH_START: time = time(9, 30)  # límite inferior INCLUSIVO
RTH_END: time = time(16, 0)  # límite superior EXCLUSIVO

REQUIRED_TICK_COLUMNS: tuple[str, ...] = ("Timestamp", "Price", "Volume", "Bid", "Ask")
SUPPORTED_EXTENSIONS: frozenset[str] = frozenset({".csv", ".parquet"})

# Formato SQL del rango horario RTH (constantes nombradas, sin magic strings).
_SQL_RTH_START = f"TIME '{RTH_START.strftime('%H:%M:%S')}'"
_SQL_RTH_END = f"TIME '{RTH_END.strftime('%H:%M:%S')}'"


def _escape_sql_literal(value: str) -> str:
    """Escapa comillas simples para usar el valor como literal SQL.

    Parámetros: value — texto a interpolar en una consulta DuckDB.
    Retorno: texto seguro entre comillas simples.
    """
    return value.replace("'", "''")


def _build_scan_expression(path: Path) -> str:
    """Construye la expresión de escaneo lazy de DuckDB según la extensión.

    Parámetros: path — ruta al archivo de ticks (.csv o .parquet).
    Retorno: expresión FROM válida para DuckDB (lectura directa desde disco).
    Lanza ValueError si la extensión no está soportada.
    """
    suffix = path.suffix.lower()
    if suffix == ".parquet":
        return f"'{_escape_sql_literal(str(path))}'"
    if suffix == ".csv":
        return f"read_csv('{_escape_sql_literal(str(path))}', header=true)"
    raise ValueError(
        f"Extensión de archivo no soportada: '{suffix}'. "
        f"Soportadas: {sorted(SUPPORTED_EXTENSIONS)}"
    )


def _validate_required_columns(connection: duckdb.DuckDBPyConnection, scan_expr: str) -> None:
    """Verifica que el archivo exponga todas las columnas obligatorias.

    Usa una consulta de solo esquema (WHERE 1=0), sin mover datos.
    Parámetros: connection — conexión DuckDB activa; scan_expr — expresión FROM.
    Retorno: None. Lanza ValueError nombrando TODAS las columnas faltantes.
    """
    schema_relation = connection.sql(f"SELECT * FROM {scan_expr} WHERE 1=0")
    available = set(schema_relation.columns)
    missing = [column for column in REQUIRED_TICK_COLUMNS if column not in available]
    if missing:
        raise ValueError(
            f"El archivo de ticks no contiene las columnas requeridas: {missing}. "
            f"Requeridas: {list(REQUIRED_TICK_COLUMNS)}. Encontradas: {sorted(available)}"
        )


def _build_ingestion_query(scan_expr: str, source_tz: str) -> str:
    """Arma la consulta SQL completa: proyección + filtro RTH + orden.

    Todo el filtrado ocurre dentro de DuckDB (pushdown al escaneo); nunca se
    materializan filas fuera de sesión RTH.

    Parámetros: scan_expr — expresión FROM; source_tz — zona horaria en que
    están estampados los timestamps naive de entrada.
    Retorno: string SQL listo para ejecutar.
    """
    # Naive ts interpretado en source_tz -> TIMESTAMPTZ -> hora de pared NY.
    local_wall_clock = (
        f"CAST(\"Timestamp\" AS TIMESTAMP) "
        f"AT TIME ZONE '{source_tz}' AT TIME ZONE '{RTH_TIMEZONE}'"
    )
    columns_projection = ", ".join(
        [
            'CAST("Timestamp" AS TIMESTAMP) AS "Timestamp"',
            'CAST("Price" AS DOUBLE) AS "Price"',
            'CAST("Volume" AS BIGINT) AS "Volume"',
            'CAST("Bid" AS DOUBLE) AS "Bid"',
            'CAST("Ask" AS DOUBLE) AS "Ask"',
        ]
    )
    return f"""
    SELECT {columns_projection}
    FROM {scan_expr}
    WHERE CAST(({local_wall_clock}) AS TIME) >= {_SQL_RTH_START}
      AND CAST(({local_wall_clock}) AS TIME) < {_SQL_RTH_END}
    ORDER BY "Timestamp" ASC
    """


def load_tick_data(
    path: str | Path,
    *,
    source_tz: str = DEFAULT_SOURCE_TZ,
    memory_limit: str | None = None,
) -> pl.DataFrame:
    """Carga ticks en sesión RTH desde CSV/Parquet a un polars.DataFrame.

    Ejecuta una consulta DuckDB lazy contra el archivo en disco: valida
    columnas por esquema, filtra la ventana RTH [09:30, 16:00) de
    America/New_York y devuelve solo las filas sobrevivientes, ordenadas por
    timestamp. Adecuado para archivos de millones de filas sin colapsar la
    memoria física.

    Parámetros:
        path: ruta al archivo de ticks (.csv o .parquet).
        source_tz: zona horaria asumida para timestamps naive (default UTC).
        memory_limit: límite de memoria DuckDB (ej. '2GB'); None usa el
            default de DuckDB (~80% de la RAM).

    Retorno: polars.DataFrame con columnas Timestamp, Price, Volume, Bid, Ask.

    Lanza ValueError si la extensión no es soportada o faltan columnas.
    """
    file_path = Path(path)
    scan_expr = _build_scan_expression(file_path)

    connection = duckdb.connect()
    try:
        if memory_limit is not None:
            connection.execute(f"SET memory_limit='{memory_limit}'")
        _validate_required_columns(connection, scan_expr)
        query = _build_ingestion_query(scan_expr, source_tz)
        return connection.sql(query).pl()
    finally:
        connection.close()
