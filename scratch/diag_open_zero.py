"""
scratch/diag_open_zero.py - Diagnostico SOLO-LECTURA del patron open=0/NaN en OHLCV.

Objetivo:
    Validar la hipotesis de que el ZeroDivisionError en src/backtest/numba_core.py
    (linea ~288, division por entry_fill = open del dia siguiente) se explica por
    filas con open invalido (0, negativo, NULL/NaN) en ohlcv_cache, y determinar
    si ese patron esta contenido en el chunk 1 del backtest multi-chunk o disperso.

Contexto del backtest que reporto el error (logs run1/run2.txt):
    - Periodo: 2019-01-01 a 2024-12-31, 1510 dias de trading
    - Multi-chunk: n_chunks = ceil(1510 / 378) = 4 chunks de 378 dias
    - entry_fill = open_arr[t+1, i]; max_shares divide por (entry_fill * (1 + slippage))

Restricciones:
    - Conexion SQLite en modo READ-ONLY (mode=ro con uri=True) + PRAGMA query_only=ON
    - No escribe nada en la DB ni en el repo (output a stdout)

Uso:
    python scratch/diag_open_zero.py
    python scratch/diag_open_zero.py --db data/ticker_cache.db --start 2019-01-01 --end 2024-12-31
"""

import argparse
import sqlite3
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB = PROJECT_ROOT / "data" / "ticker_cache.db"

# Periodo del backtest multi-chunk que reporto el ZeroDivisionError
BACKTEST_START = "2019-01-01"
BACKTEST_END = "2024-12-31"
CHUNK_TRADING_DAYS = 378  # ceil(1510 / 4) del run que crasheo
TOP_N = 20

OHLC_COLS = ["ticker", "date", "open", "high", "low", "close"]


def connect_ro(db_path: Path) -> sqlite3.Connection:
    """Conexion SQLite estrictamente de solo lectura."""
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    conn.execute("PRAGMA query_only = ON")
    return conn


def is_invalid(s: pd.Series) -> pd.Series:
    """Mascara de valores invalidos: NULL/NaN, 0, o negativos."""
    return s.isna() | (s <= 0)


def section(title: str) -> None:
    print(f"\n{'=' * 70}\n{title}\n{'=' * 70}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Diagnostico open=0/NaN en OHLCV (solo lectura)")
    parser.add_argument("--db", type=str, default=str(DEFAULT_DB))
    parser.add_argument("--start", type=str, default=BACKTEST_START)
    parser.add_argument("--end", type=str, default=BACKTEST_END)
    parser.add_argument("--top", type=int, default=TOP_N)
    args = parser.parse_args()

    db_path = Path(args.db)
    if not db_path.exists():
        print(f"[ERROR] DB no encontrada: {db_path}")
        return 1

    conn = connect_ro(db_path)
    cur = conn.cursor()
    print(f"DB (read-only): {db_path}")

    # 1. Meta
    section("1) SCHEMA OHLCV")
    tables = cur.execute(
        "SELECT type, name FROM sqlite_master WHERE type IN ('table','view') "
        "AND name LIKE '%ohlcv%' ORDER BY name"
    ).fetchall()
    for ttype, tname in tables:
        print(f"  {ttype}: {tname}")
    table_name = "ohlcv_cache"
    cols = cur.execute(f"PRAGMA table_info({table_name})").fetchall()
    print(f"  columnas: {[c[1] for c in cols]}")
    min_d, max_d, n_total = cur.execute(
        f"SELECT MIN(date), MAX(date), COUNT(*) FROM {table_name}"
    ).fetchone()
    print(f"  rango total: {min_d} -> {max_d} | filas: {n_total:,}")

    # 2. Totales por categoria (toda la DB, una sola pasada agrupada)
    section("2) TOTALES VALORES INVALIDOS")
    cats = {
        "open": "open",
        "high": "high",
        "low": "low",
        "close": "close",
    }
    for name, col in cats.items():
        for kind, expr in (
            ("null", f"SUM(CASE WHEN {col} IS NULL THEN 1 ELSE 0 END)"),
            ("zero", f"SUM(CASE WHEN {col} = 0 THEN 1 ELSE 0 END)"),
            ("neg", f"SUM(CASE WHEN {col} < 0 THEN 1 ELSE 0 END)"),
        ):
            n = cur.execute(f"SELECT {expr} FROM {table_name}").fetchone()[0]
            print(f"  {name:<6} {kind:<5} full-db = {n:>7,}")
        n_nan = cur.execute(
            f"SELECT COUNT(*) FROM {table_name} WHERE {col} != {col}"
        ).fetchone()[0]
        print(f"  {name:<6} nan   full-db = {n_nan:>7,}")

    # 3. Cargar ventana del backtest en memoria (una sola query)
    section("3) CARGA VENTANA EN MEMORIA")
    print(f"  leyendo {table_name} entre {args.start} y {args.end} (read-only)...")
    df = pd.read_sql_query(
        f"SELECT ticker, date, open, high, low, close FROM {table_name} "
        "WHERE date BETWEEN ? AND ? ORDER BY date",
        conn,
        params=(args.start, args.end),
    )
    df["date"] = pd.to_datetime(df["date"].astype(str).str[:10])
    print(f"  filas en ventana: {len(df):,} | tickers: {df['ticker'].nunique():,}")

    inv_open = is_invalid(df["open"])
    inv_high = is_invalid(df["high"])
    inv_low = is_invalid(df["low"])
    inv_close = is_invalid(df["close"])
    print(f"  ventana: open_inv={int(inv_open.sum()):>6}  high_inv={int(inv_high.sum()):>6}  "
          f"low_inv={int(inv_low.sum()):>6}  close_inv={int(inv_close.sum()):>6}")
    o = df["open"]
    print(f"  desglose open: null={int(o.isna().sum()):>6}  zero={int((o == 0).sum()):>6}  "
          f"neg={int((o < 0).sum()):>6}")

    # 4. Top tickers con open invalido
    section(f"4) TOP {args.top} TICKERS CON OPEN INVALIDO")
    totals = df.groupby("ticker").size().rename("total")
    bads = df.loc[inv_open].groupby("ticker").size().rename("bad")
    g = bads.to_frame().join(totals).sort_values("bad", ascending=False)
    if g.empty:
        print("  (sin filas con open invalido en la ventana)")
    else:
        for i, (ticker, row) in enumerate(g.head(args.top).iterrows(), 1):
            print(f"  {i:>2}. {ticker:<8} bad={int(row['bad']):>5} / {int(row['total']):>6} filas")
        print(f"  -- tickers con open invalido: {len(g)}")

    # 5. Distribucion temporal por ano y por mes
    section("5) DISTRIBUCION TEMPORAL (OPEN INVALIDO)")
    by_year = df.loc[inv_open, "date"].dt.year.value_counts().sort_index()
    for y, bad in by_year.items():
        bar = "#" * min(60, int(bad) // 5)
        print(f"  {y}: {int(bad):>5}  {bar}")
    by_month = df.loc[inv_open, "date"].dt.to_period("M").value_counts().sort_index()
    if len(by_month):
        print("  -- top 12 meses:")
        for ym, bad in by_month.sort_values(ascending=False).head(12).items():
            print(f"     {ym}: {int(bad)}")

    # 6. Distribucion por chunk de 378 dias de trading (equivalente al multi-chunk)
    section("6) OPEN INVALIDO POR CHUNK DE 378 DIAS DE TRADING (VENTANA BACKTEST)")
    uni = np.sort(df["date"].unique())
    n_days = len(uni)
    n_chunks = -(-n_days // CHUNK_TRADING_DAYS)
    print(f"  dias de trading en ventana: {n_days} -> {n_chunks} chunks de {CHUNK_TRADING_DAYS}")
    day_idx = np.searchsorted(uni, df["date"].values)
    chunk_idx = day_idx // CHUNK_TRADING_DAYS
    for ci in range(n_chunks):
        m = chunk_idx == ci
        lo = ci * CHUNK_TRADING_DAYS
        hi = min((ci + 1) * CHUNK_TRADING_DAYS, n_days)
        d0, d1 = uni[lo], uni[hi - 1]
        print(f"  chunk {ci + 1:>2}: {pd.Timestamp(d0).date()} -> {pd.Timestamp(d1).date()}  "
              f"open_inv={int(inv_open[m].sum()):>5}  high_inv={int(inv_high[m].sum()):>5}  "
              f"close_inv={int(inv_close[m].sum()):>5}  filas={int(m.sum()):>7}")

    # 7. Open invalido por chunk de 378 dias sobre TODA la DB (una sola query con window fn)
    section("7) OPEN INVALIDO POR CHUNK 378 DIAS SOBRE TODA LA DB")
    try:
        rows = cur.execute(
            f"""
            WITH dates AS (
                SELECT DISTINCT date FROM {table_name}
            ),
            dchunk AS (
                SELECT date, (ROW_NUMBER() OVER (ORDER BY date) - 1) / {CHUNK_TRADING_DAYS} AS chunk
                FROM dates
            ),
            inv AS (
                SELECT date FROM {table_name}
                WHERE open IS NULL OR open = 0 OR open < 0 OR open != open
            )
            SELECT d.chunk + 1, MIN(d.date), MAX(d.date), COUNT(*)
            FROM inv i JOIN dchunk d ON d.date = i.date
            GROUP BY d.chunk
            ORDER BY d.chunk
            """
        ).fetchall()
        for chunk_no, d0, d1, bad in rows:
            print(f"  chunk {chunk_no:>3}: {d0} -> {d1}  open_inv={bad:>6}")
    except sqlite3.Error as e:
        print(f"  [i] query chunks no disponible: {e}")

    # 8. Cruce con universo
    section("8) CRUCE CON UNIVERSO")
    univ = set(r[0] for r in cur.execute("SELECT ticker FROM universe").fetchall())
    mask_univ = df["ticker"].isin(univ)
    total_win = int(inv_open.sum())
    in_win = int((inv_open & mask_univ).sum())
    print(f"  open invalido en ventana: {total_win}")
    if total_win:
        print(f"  de los cuales en tabla universe: {in_win} ({100 * in_win / total_win:.1f}%)")
        top_univ = df.loc[inv_open & mask_univ, "ticker"].value_counts().head(10)
        print("  -- top 10 tickers invalidos QUE ESTAN en universe:")
        for t, bad in top_univ.items():
            print(f"     {t}: {int(bad)}")

    # 9. Verificacion read-only
    section("9) VERIFICACION READ-ONLY")
    try:
        cur.execute("BEGIN")
        cur.execute("DELETE FROM ohlcv_cache WHERE date = '1999-01-01'")
        cur.execute("ROLLBACK")
        print("  [WARN] la DB acepto escritura (no deberia)")
    except sqlite3.Error:
        print("  [OK] escritura rechazada (mode=ro + query_only=ON)")

    conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
