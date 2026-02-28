#!/usr/bin/env python3
"""
CACHE FIX SIMPLE
===============

Versión simplificada que maneja MultiIndex correctamente.
"""

import sys
from pathlib import Path
import yfinance as yf
import sqlite3
import time

sys.path.insert(0, str(Path(__file__).resolve().parent))


def fix_cache_simple():
    """Fix cache simple y directo"""
    print("=" * 80)
    print("🧹 CACHE FIX SIMPLE")
    print("=" * 80)

    # Tickers
    tickers = [
        "AAPL",
        "MSFT",
        "GOOGL",
        "NVDA",
        "TSLA",
        "META",
        "AMZN",
        "NFLX",
        "AMD",
        "AVGO",
        "QCOM",
        "INTC",
        "TXN",
        "ADBE",
        "CRM",
        "COST",
        "CSCO",
        "AMAT",
        "MU",
        "LRCX",
        "PYPL",
        "ADP",
        "BKNG",
        "INTU",
        "PANW",
        "VRTX",
        "REGN",
        "KLAC",
        "SNPS",
        "CDNS",
        "MAR",
        "FTNT",
        "MELI",
        "ORLY",
        "CTAS",
        "PCAR",
        "NVDA",
        "TSLA",
        "META",
        "AMZN",
        "NFLX",
        "AMD",
        "AVGO",
    ]

    start_date = "2021-01-01"
    end_date = "2026-01-01"

    print(f"\n🎯 TICKERS: {len(tickers)}")
    print(f"📅 PERÍODO: {start_date} a {end_date}")

    cache_file = Path("data/ticker_cache.db")
    if not cache_file.exists():
        print("❌ ERROR: Cache no existe")
        return False

    conn = sqlite3.connect(cache_file)
    cursor = conn.cursor()

    # Limpiar data antigua
    print(f"\n🔧 1. LIMPIANDO CACHE ANTIGUO")
    ticker_list = ", ".join([f"'{t}'" for t in tickers])
    cursor.execute(f"""
        DELETE FROM ohlcv_cache
        WHERE ticker IN ({ticker_list})
    """)
    conn.commit()
    print(f"   ✅ Eliminados: {cursor.rowcount:,} registros")

    # Descargar datos
    print(f"\n🔧 2. DESCARGANDO DATOS ({len(tickers)} tickers)")

    success = 0
    error = 0

    start_time = time.time()

    for idx, ticker in enumerate(tickers, 1):
        if idx % 10 == 0:
            elapsed = time.time() - start_time
            remaining = (len(tickers) - idx) / (idx / elapsed) if elapsed > 0 else 0
            print(
                f"   📊 Progreso: {idx}/{len(tickers)} ({idx / len(tickers) * 100:.1f}%)"
            )
            print(
                f"      ✅ {success} | ❌ {error} | ⏱️  {elapsed / 60:.1f}min | ETA: {remaining / 60:.1f}min"
            )

        try:
            # Download
            data = yf.download(ticker, start=start_date, end=end_date, progress=False)

            if data is None or data.empty:
                error += 1
                continue

            # Convert MultiIndex DataFrame
            df = data.reset_index()

            # Fix column names (remove MultiIndex)
            df.columns = [
                col[0] if isinstance(col, tuple) else col for col in df.columns
            ]

            # Convertir columnas a lowercase
            df.columns = df.columns.str.lower()

            # Insertar en cache
            for _, row in df.iterrows():
                try:
                    cursor.execute(
                        """
                        INSERT OR REPLACE INTO ohlcv_cache (ticker, date, open, high, low, close, volume)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                        (
                            ticker,
                            str(row["date"]).split("T")[0]
                            if pd.notna(row.get("date"))
                            else None,
                            float(row.get("open", 0))
                            if pd.notna(row.get("open"))
                            else 0,
                            float(row.get("high", 0))
                            if pd.notna(row.get("high"))
                            else 0,
                            float(row.get("low", 0)) if pd.notna(row.get("low")) else 0,
                            float(row.get("close", 0))
                            if pd.notna(row.get("close"))
                            else 0,
                            int(row.get("volume", 0))
                            if pd.notna(row.get("volume"))
                            else 0,
                        ),
                    )
                except:
                    pass

            success += 1

        except Exception as e:
            error += 1

        # Commit cada 100 tickers
        if idx % 100 == 0:
            conn.commit()

    conn.commit()

    # SPY Data
    print(f"\n🔧 3. ASEGURANDO SPY DATA")

    cursor.execute("DELETE FROM ohlcv_cache WHERE ticker = 'SPY'")

    try:
        data = yf.download("SPY", start=start_date, end=end_date, progress=False)

        if data is not None and not data.empty:
            df = data.reset_index()
            df.columns = [
                col[0] if isinstance(col, tuple) else col for col in df.columns
            ]
            df.columns = df.columns.str.lower()

            for _, row in df.iterrows():
                try:
                    cursor.execute(
                        """
                        INSERT OR REPLACE INTO ohlcv_cache (ticker, date, open, high, low, close, volume)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                        (
                            "SPY",
                            str(row["date"]).split("T")[0]
                            if pd.notna(row.get("date"))
                            else None,
                            float(row.get("open", 0))
                            if pd.notna(row.get("open"))
                            else 0,
                            float(row.get("high", 0))
                            if pd.notna(row.get("high"))
                            else 0,
                            float(row.get("low", 0)) if pd.notna(row.get("low")) else 0,
                            float(row.get("close", 0))
                            if pd.notna(row.get("close"))
                            else 0,
                            int(row.get("volume", 0))
                            if pd.notna(row.get("volume"))
                            else 0,
                        ),
                    )
                except:
                    pass

            conn.commit()
            print(f"   ✅ SPY data completado ({len(df):,} días)")
        else:
            print(f"   ⚠️  SPY sin datos")

    except Exception as e:
        print(f"   ❌ Error SPY: {e}")
        conn.rollback()

    conn.close()

    # Stats
    total_time = time.time() - start_time

    print(f"\n📊 RESULTADOS:")
    print(f"   Exitosos:  {success:,}")
    print(f"   Errores:   {error:,}")
    print(f"   Tiempo:    {total_time / 60:.1f} minutos")

    # Verify
    cursor = sqlite3.connect("data/ticker_cache.db").cursor()
    cursor.execute("SELECT COUNT(*) FROM ohlcv_cache")
    total_count = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(DISTINCT ticker) FROM ohlcv_cache")
    unique_tickers = cursor.fetchone()[0]

    print(f"\n✅ VERIFICACIÓN:")
    print(f"   Registros: {total_count:,}")
    print(f"   Tickers:   {unique_tickers}")

    return True


if __name__ == "__main__":
    # Importar pandas
    import pandas as pd

    success = fix_cache_simple()

    if success:
        print("\n✅ CACHE FIX COMPLETADO")
        print("\n📋 PRÓXIMOS PASOS:")
        print("   1. Ejecutar backtest: python3 example_quick_backtest.py")
        print("   2. Limpiar cache: En Streamlit, click '🧹 Limpiar Cache' button")
        print("   3. Cargar validated params: Click '📥 Load Validated Params' button")
        print("   4. Validar convergencia: python3 convergence_test_streamlit_cli.py")
    else:
        print("\n❌ ERROR: No se pudo completar")
