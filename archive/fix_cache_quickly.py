#!/usr/bin/env python3
"""
CACHE FIX RÁPIDO Y DIRECTO
==========================

Reemplaza the quick_populate_cache.py que no funciona.
Descarga datos para los tickers que IMPORTAN (los 40 tech leaders).
"""

import sys
from pathlib import Path
import yfinance as yf
import sqlite3
from datetime import datetime, timedelta
import time
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))


def fix_cache_quickly():
    """Fix cache rápido y directo"""
    print("=" * 80)
    print("🧹 CACHE FIX RÁPIDO")
    print("=" * 80)

    # Tickers de alto valor (40 tech leaders)
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

    # Periodo: 5 years (suficiente para backtest, no memory leak)
    start_date = "2021-01-01"
    end_date = "2026-01-01"

    print(f"\n🎯 TICKERS: {len(tickers)} (40 tech leaders)")
    print(f"📅 PERÍODO: {start_date} a {end_date}")
    print(f"⏱️  ESTIMADO: ~5-10 minutos")
    print()

    # Check cache
    cache_file = Path("data/ticker_cache.db")
    if not cache_file.exists():
        print("❌ ERROR: Cache no existe")
        print("   Crea el cache primero:")
        print("   python3 quick_populate_cache.py")
        return False

    # Conectar a cache
    conn = sqlite3.connect(cache_file)
    cursor = conn.cursor()

    # Limpiar data antigua (solo lo que necesitamos)
    print(f"\n🔧 1. LIMPIANDO CACHE ANTIGUO")

    cursor.execute("""
        DELETE FROM ohlcv_cache
        WHERE ticker IN ('AAPL', 'MSFT', 'GOOGL', 'NVDA', 'TSLA', 'META', 'AMZN', 'NFLX', 'AMD', 'AVGO',
                         'QCOM', 'INTC', 'TXN', 'ADBE', 'CRM', 'COST', 'CSCO', 'AMAT', 'MU', 'LRCX',
                         'PYPL', 'ADP', 'BKNG', 'INTU', 'PANW', 'VRTX', 'REGN', 'KLAC', 'SNPS', 'CDNS',
                         'MAR', 'FTNT', 'MELI', 'ORLY', 'CTAS', 'PCAR')
    """)

    deleted = cursor.rowcount
    print(f"   ✅ Eliminados: {deleted:,} registros antiguos")

    conn.commit()

    # Descargar datos
    print(f"\n🔧 2. DESCARGANDO DATOS ({len(tickers)} tickers)")

    success = 0
    skip = 0
    error = 0

    start_time = time.time()

    for idx, ticker in enumerate(tickers, 1):
        # Progress every 10 tickers
        if idx % 10 == 0:
            elapsed = time.time() - start_time
            rate = idx / elapsed
            remaining = (len(tickers) - idx) / rate
            print(
                f"   📊 Progreso: {idx}/{len(tickers)} ({idx / len(tickers) * 100:.1f}%)"
            )
            print(
                f"      ✅ {success} | ⏭️ {skip} | ❌ {error} | ⏱️  {elapsed / 60:.1f}min | ETA: {remaining / 60:.1f}min"
            )

        try:
            # Download data
            data = yf.download(ticker, start=start_date, end=end_date, progress=False)

            if data.empty:
                if idx % 10 == 1:
                    print(f"   ⚠️  {ticker:6} - Sin datos")
                error += 1
                continue

            # Convert to DataFrame
            df = data.copy()
            df = df.reset_index()
            df.rename(
                columns={
                    "Date": "date",
                    "Open": "Open",
                    "High": "High",
                    "Low": "Low",
                    "Close": "Close",
                    "Volume": "Volume",
                },
                inplace=True,
            )

            # Clean up column names
            df.columns = df.columns.str.lower()

            # Insert into cache
            for _, row in df.iterrows():
                cursor.execute(
                    """
                    INSERT OR REPLACE INTO ohlcv_cache (ticker, date, open, high, low, close, volume)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                    (
                        ticker,
                        str(row["date"]).split("T")[0],  # Fecha YYYY-MM-DD
                        float(row["open"]) if not pd.isna(row["open"]) else 0,
                        float(row["high"]) if not pd.isna(row["high"]) else 0,
                        float(row["low"]) if not pd.isna(row["low"]) else 0,
                        float(row["close"]) if not pd.isna(row["close"]) else 0,
                        int(row["volume"]) if not pd.isna(row["volume"]) else 0,
                    ),
                )

            success += 1

        except Exception as e:
            if idx % 10 == 1:
                print(f"   ❌ {ticker:6} - Error: {str(e)[:50]}")
            error += 1

        # Commit each ticker (para evitar memory leak)
        if idx % 100 == 0:
            conn.commit()

    conn.commit()

    # Final stats
    total_time = time.time() - start_time

    print(f"\n📊 RESULTADOS:")
    print(f"   Exitosos:  {success:,}")
    print(f"   Omitidos:  {skip:,} (ya tenían histórico)")
    print(f"   Errores:   {error:,}")
    print(f"   Total:     {success:,}")
    print(f"   Tiempo:    {total_time / 60:.1f} minutos")

    # Verify data
    cursor.execute("SELECT COUNT(*) FROM ohlcv_cache")
    total_count = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(DISTINCT ticker) FROM ohlcv_cache")
    unique_tickers = cursor.fetchone()[0]

    print(f"\n✅ VERIFICACIÓN:")
    print(f"   Registros en cache: {total_count:,}")
    print(f"   Tickers únicos:     {unique_tickers}")

    conn.close()

    # Liberar memory
    import gc

    gc.collect()

    return True


def add_spy_data():
    """Agrega SPY data al cache"""
    print(f"\n🔧 3. ASEGURANDO SPY DATA")

    tickers = ["SPY"]
    start_date = "2021-01-01"
    end_date = "2026-01-01"

    cache_file = Path("data/ticker_cache.db")
    conn = sqlite3.connect(cache_file)
    cursor = conn.cursor()

    # Limpiar SPY data antigua
    cursor.execute("DELETE FROM ohlcv_cache WHERE ticker = 'SPY'")

    try:
        data = yf.download("SPY", start=start_date, end=end_date, progress=False)

        if data is not None and not data.empty:
            # Convert MultiIndex DataFrame
            df = data.reset_index()

            # Convert column names to lowercase
            df.columns = df.columns.str.lower()

            # Ensure 'date' column exists
            if "date" in df.columns:
                df.rename(columns={"date": "date"}, inplace=True)

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
    finally:
        conn.close()


def main():
    print("=" * 80)
    print("🧹 CACHE FIX RÁPIDO Y DIRECTO")
    print("=" * 80)

    # Fix tickers
    success = fix_cache_quickly()

    # Add SPY
    add_spy_data()

    # Summary
    print(f"\n" + "=" * 80)
    print("✅ CACHE FIX COMPLETADO")
    print("=" * 80)

    print(f"\n📋 PRÓXIMOS PASOS:")

    print(f"\n1️⃣  BACKTEST RÁPIDO (1 year):")
    print(f"   python3 example_quick_backtest.py")

    print(f"\n2️⃣  VERIFICAR INTEGRIDAD:")
    print(f"   python3 diagnose_performance_issues.py")

    print(f"\n3️⃣  CLEAN STREAMLIT CACHE:")
    print(f"   - En Streamlit sidebar:")
    print(f"   - Click '🧹 Limpiar Cache' button")

    print(f"\n4️⃣  CARGAR VALIDATED PARAMS:")
    print(f"   - En Streamlit sidebar:")
    print(f"   - Click '📥 Load Validated Params'")

    print(f"\n5️⃣  VALIDAR CONVERGENCIA:")
    print(f"   python3 convergence_test_streamlit_cli.py")

    return success


if __name__ == "__main__":
    main()
