"""
scratch/diag_db.py - Diagnostico del estado de la base de datos OHLCV.

Uso:
    python scratch/diag_db.py
    python scratch/diag_db.py --db data/ticker_cache.db
    python scratch/diag_db.py --fresh-cutoff 2026-07-01

Imprime:
  1. Total de tickers unicos en la DB
  2. Distribucion de frescura por mes (ultima fecha por ticker)
  3. Split US vs INTL (tickers con sufijos -KS / -SZ / -HK / -T / ^prefijo / .punto)
  4. Top 10 tickers mas stale vs mas frescos
  5. Cantidad de tickers "usables" para CV (MAX(date) >= cutoff)
  6. Escribe data/universe_fresh.txt con los tickers usables
"""

import argparse
import sqlite3
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB = PROJECT_ROOT / "data" / "ticker_cache.db"

INTL_PATTERNS = ("%-KS", "%-SZ", "%-HK", "%-T", "^-%", "%.")


def is_intl(ticker: str) -> bool:
    return any(ticker.like(p) if hasattr(ticker, "like") else False for p in INTL_PATTERNS) \
        if False else any(
            ticker.startswith(p.replace("%", "")) or p.replace("%", "") in ticker
            for p in INTL_PATTERNS
        )


def main() -> int:
    parser = argparse.ArgumentParser(description="Diagnostico DB OHLCV")
    parser.add_argument("--db", type=str, default=str(DEFAULT_DB))
    parser.add_argument("--fresh-cutoff", type=str, default="2026-07-01",
                        help="Fecha minima para considerar un ticker 'usable'")
    args = parser.parse_args()

    db_path = Path(args.db)
    if not db_path.exists():
        print(f"[ERROR] DB no encontrada: {db_path}")
        return 1

    conn = sqlite3.connect(str(db_path))
    print(f"DB: {db_path}")
    print("=" * 70)

    # 1. Total tickers
    total = conn.execute("SELECT COUNT(DISTINCT ticker) FROM ohlcv_cache").fetchone()[0]
    print(f"\n[1] Total tickers unicos: {total}")

    # 2. Distribucion de frescura por mes
    # Por cada ticker, su MAX(date); despues agrupo por mes de esa fecha.
    print(f"\n[2] Frescura por mes (MAX(date) por ticker, agrupado por YYYY-MM):")
    rows = conn.execute(
        """
        WITH max_per_ticker AS (
            SELECT MAX(date) AS max_date
            FROM ohlcv_cache
            GROUP BY ticker
        )
        SELECT substr(max_date, 1, 7) AS ym, COUNT(*) AS n
        FROM max_per_ticker
        GROUP BY substr(max_date, 1, 7)
        ORDER BY ym DESC
        """
    ).fetchall()
    for ym, n in rows[:24]:
        bar = "#" * min(60, n // 50)
        print(f"  {ym}: {n:>5} tickers  {bar}")

    # 3. US vs INTL
    # Patterns en INTL_PATTERNS son de la forma %SUFIJO (ends with) o ^PREFIJO (starts with)
    # Traducimos a SQL LIKE correctamente.
    intl_clauses = []
    for p in INTL_PATTERNS:
        if p.startswith("^"):
            # ^-X  =>  empieza con '-X'  =>  ticker LIKE '-X%'
            prefix = p[1:].rstrip("%")
            intl_clauses.append(f"ticker LIKE '{prefix}%'")
        elif p.startswith("%") and p.endswith("%"):
            # %X%  =>  contiene 'X'  =>  ticker LIKE '%X%'
            mid = p.strip("%")
            intl_clauses.append(f"ticker LIKE '%{mid}%'")
        elif p.startswith("%"):
            # %X  =>  termina con 'X'  =>  ticker LIKE '%X'
            suffix = p.lstrip("%")
            intl_clauses.append(f"ticker LIKE '%{suffix}'")
        else:
            intl_clauses.append(f"ticker LIKE '{p}'")
    intl_clause = " OR ".join(intl_clauses)

    sql_geo = f"""
        SELECT
            CASE WHEN {intl_clause} THEN 'INTL' ELSE 'US' END AS geo,
            COUNT(DISTINCT ticker) AS n
        FROM ohlcv_cache
        GROUP BY geo
    """
    print(f"\n[3] Split US vs INTL:")
    rows = conn.execute(sql_geo).fetchall()
    for geo, n in rows:
        print(f"  {geo}: {n} tickers")

    # 4. Stale vs fresh (top 10)
    print(f"\n[4] Top 10 mas STALE (mas alejados de 'hoy'):")
    rows = conn.execute(
        "SELECT ticker, MAX(date) AS last FROM ohlcv_cache "
        "GROUP BY ticker ORDER BY last ASC LIMIT 10"
    ).fetchall()
    for t, d in rows:
        print(f"  {t}: {d}")

    print(f"\n[5] Top 10 mas FRESCOS:")
    rows = conn.execute(
        "SELECT ticker, MAX(date) AS last FROM ohlcv_cache "
        "GROUP BY ticker ORDER BY last DESC LIMIT 10"
    ).fetchall()
    for t, d in rows:
        print(f"  {t}: {d}")

    # 6. Tickers usables para CV
    cutoff = args.fresh_cutoff
    rows = conn.execute(
        "SELECT DISTINCT ticker FROM ohlcv_cache WHERE date >= ? ORDER BY ticker",
        (cutoff,),
    ).fetchall()
    fresh_n = len(rows)
    print(f"\n[6] Tickers con MAX(date) >= {cutoff}: {fresh_n}")

    out_path = PROJECT_ROOT / "data" / "universe_fresh.txt"
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(r[0] for r in rows) + "\n")
    print(f"     Escritos en: {out_path}")

    # Resumen
    print("\n" + "=" * 70)
    print(f"RESUMEN: {total} tickers totales | {fresh_n} usables para CV "
          f"(cutoff={cutoff})")
    if fresh_n < 100:
        print("[!] Pocos tickers usables — refresh de data necesario antes de CV")
    elif fresh_n < 500:
        print("[i] Subset manejable, OK para CV inicial")
    else:
        print("[i] Subset grande, considerar filtro adicional por ADV/liquidez")

    conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
