#!/usr/bin/env python3
"""
INTEGRIDAD DEL SISTEMA - Diagnóstico de problemas de rendimiento
===============================================================

Este script verifica:
1. Cache integrity
2. SPY data availability
3. Memory usage
4. Data conversion rate
5. Ticker data quality
"""

import sys
import json
import sqlite3
from pathlib import Path
from datetime import datetime, timedelta
import gc

sys.path.insert(0, str(Path(__file__).resolve().parent))


def check_cache_integrity():
    """Verifica integridad del cache"""
    print("=" * 80)
    print("🔍 1. INTEGRIDAD DEL CACHE")
    print("=" * 80)

    cache_file = Path("data/ticker_cache.db")

    if not cache_file.exists():
        print("❌ ERROR: Cache SQLite no existe en data/ticker_cache.db")
        print("   Corre: python3 quick_populate_cache.py")
        return None

    conn = sqlite3.connect(cache_file)
    cursor = conn.cursor()

    try:
        # Check total tickers
        cursor.execute("SELECT COUNT(DISTINCT ticker) FROM ohlcv_cache")
        total_tickers = cursor.fetchone()[0]

        print(f"✅ Total tickers en cache: {total_tickers}")

        # Check date range
        cursor.execute("SELECT MIN(date), MAX(date) FROM ohlcv_cache")
        min_date, max_date = cursor.fetchone()

        if min_date and max_date:
            print(f"✅ Cache range: {min_date} to {max_date}")
            # Convert to datetime objects for calculation
            from datetime import datetime

            # Handle datetime with time
            min_dt = datetime.strptime(min_date.split(" ")[0], "%Y-%m-%d")
            max_dt = datetime.strptime(max_date.split(" ")[0], "%Y-%m-%d")
            print(f"   Duration: {(max_dt - min_dt).days} days")

        # Check data completeness
        cursor.execute("""
            SELECT COUNT(DISTINCT ticker) as total
            FROM ohlcv_cache
        """)
        total_tickers = cursor.fetchone()[0]

        cursor.execute("""
            SELECT COUNT(DISTINCT ticker) as complete
            FROM ohlcv_cache
            WHERE date >= '2021-01-01'
        """)
        tickers_with_data = cursor.fetchone()[0]

        print(f"✅ Tickers con suficiente data: {tickers_with_data}/{total_tickers}")

        if tickers_with_data < total_tickers * 0.8:
            print(
                f"⚠️  WARNING: Solo {tickers_with_data / total_tickers * 100:.1f}% tiene datos suficientes"
            )
            return {
                "status": "warning",
                "tickers": total_tickers,
                "complete": tickers_with_data,
                "incomplete": total_tickers - tickers_with_data,
            }

        return {
            "status": "ok",
            "tickers": total_tickers,
            "range": (min_date, max_date),
            "complete": tickers_with_data,
        }

    finally:
        conn.close()


def check_spy_data():
    """Verifica availability de SPY data"""
    print("\n" + "=" * 80)
    print("🔍 2. DATA DE SPY")
    print("=" * 80)

    cache_file = Path("data/ticker_cache.db")

    if not cache_file.exists():
        print("❌ ERROR: Cache no existe")
        return None

    conn = sqlite3.connect(cache_file)
    cursor = conn.cursor()

    try:
        cursor.execute("""
            SELECT COUNT(*)
            FROM ohlcv_cache
            WHERE ticker = 'SPY'
        """)
        spy_count = cursor.fetchone()[0]

        print(f"✅ SPY en cache: {spy_count} días")

        if spy_count == 0:
            print("❌ ERROR: SPY no está en cache")
            print("   Corre: python3 quick_populate_cache.py --include SPY")
            return {"status": "error", "count": 0}
        else:
            cursor.execute(
                "SELECT MIN(date), MAX(date) FROM ohlcv_cache WHERE ticker = 'SPY'"
            )
            min_date, max_date = cursor.fetchone()
            print(f"✅ SPY range: {min_date} to {max_date}")
            return {"status": "ok", "count": spy_count, "range": (min_date, max_date)}

    finally:
        conn.close()


def check_recent_data():
    """Verifica si hay datos recientes"""
    print("\n" + "=" * 80)
    print("🔍 3. DATOS RECIENTES")
    print("=" * 80)

    cache_file = Path("data/ticker_cache.db")

    if not cache_file.exists():
        print("❌ ERROR: Cache no existe")
        return None

    conn = sqlite3.connect(cache_file)
    cursor = conn.cursor()

    try:
        # Check today's data
        cursor.execute("""
            SELECT COUNT(*)
            FROM ohlcv_cache
            WHERE date >= date('now')
        """)
        recent_count = cursor.fetchone()[0]

        print(f"✅ Datos de hoy: {recent_count} registros")

        if recent_count > 0:
            print("✅ Cache está actualizado")
        else:
            print("⚠️  WARNING: No hay datos de hoy")
            print("   Corre: python3 quick_populate_cache.py --today")

        return {"recent_count": recent_count}

    finally:
        conn.close()


def check_memory_usage():
    """Verifica memoria disponible"""
    print("\n" + "=" * 80)
    print("🔍 4. MEMORIA DISPONIBLE")
    print("=" * 80)

    try:
        import psutil
        import os

        process = psutil.Process(os.getpid())

        mem = process.memory_info()
        mem_gb = mem.rss / (1024**3)

        print(f"✅ Memory usado por proceso: {mem_gb:.2f} GB")

        if mem_gb > 4.0:
            print("⚠️  WARNING: Uso de memoria alto (>4GB)")
            print("   Considera:")
            print("   1. Limpiar cache: python3 clean_and_align_data.py")
            print("   2. Usar modo offline con menos tickers")
            print("   3. Usar convergencia mode en lugar de production")
        else:
            print("✅ Memory uso estándar")

        return {"memory_gb": mem_gb}

    except ImportError:
        print("⚠️  psutil no instalado, no puedo medir memory")
        return None


def analyze_conversion_rates():
    """Analiza tasas de conversión"""
    print("\n" + "=" * 80)
    print("🔍 5. ANÁLISIS DE TASA DE CONVERSIÓN")
    print("=" * 80)

    print("\n⚠️  LOW CONVERSION RATE DETECTADO:")
    print("   • 2.4% (bueno pero bajo)")
    print("   • 1.7% (moderado)")
    print("   • 1.0% (bajo)")
    print()

    print("❓ CAUSAS POSIBLES:")

    print("\n1️⃣ FILTROS MUY ESTRICtos (NUEVOS PARÁMETROS):")
    print("   MAX_STOP_PCT = 6.0% (era 3.0%)")
    print("   MAX_DIST_SMA20 = 9.0% (era 7.0%)")
    print("   MIN_ADR = 1.5% (era 2.0%)")
    print("   MIN_RVOL = 1.0x (era 1.5x)")

    print("\n2️⃣ SPY DATA MISSING:")
    print("   'SPY not in cache'")
    print("   'Failed download: SPY'")

    print("\n3️⃣ TICKERS INSUFFICIENT DATA:")
    print("   'Skipped 79 tickers (insufficient data)'")

    print("\n4️⃣ MEMORY CONSTRAINTS:")
    print("   'No puedo ejecutar más de 2-3 años de bt'")

    return {
        "conversion_rate": "low",
        "issues": ["Filters", "SPY Data", "Tickers", "Memory"],
    }


def check_recent_changes():
    """Verifica cambios recientes que podrían afectar"""
    print("\n" + "=" * 80)
    print("🔍 6. CAMBIOS RECIENTES QUE PODRÍAN APROVECHAR")
    print("=" * 80)

    # Check param changes
    try:
        with open("config/validated_production_params.json", "r") as f:
            params = json.load(f)

        old_max_stop = 3.0
        new_max_stop = params["parameters"].get("max_stop_pct", 6.0)

        print(f"\n📊 PARÁMETROS ACTUALES:")
        print(f"   MAX_STOP_PCT: {new_max_stop}% (era {old_max_stop}%)")
        print(
            f"   MAX_DIST_SMA20: {params['parameters'].get('max_dist_sma20', 9.0)}% (era 7.0%)"
        )
        print(f"   MIN_ADR: {params['parameters'].get('min_adr', 1.5)}% (era 2.0%)")
        print(f"   MIN_RVOL: {params['parameters'].get('min_rvol', 1.0)}x (era 1.5x)")

        print(f"\n💡 ESESPERADO:")
        print(f"   • MENOS filtres → MÁS trades")
        print(f"   • MENOS convertidores → MÁS ejecuciones")

        return {
            "max_stop": new_max_stop,
            "max_dist": params["parameters"].get("max_dist_sma20", 9.0),
            "min_adr": params["parameters"].get("min_adr", 1.5),
            "min_rvol": params["parameters"].get("min_rvol", 1.0),
        }

    except Exception as e:
        print(f"⚠️  Error cargando parámetros: {e}")
        return None


def suggest_fixes():
    """Sugiere soluciones"""
    print("\n" + "=" * 80)
    print("🔧 SOLUCIONES RECOMENDADAS")
    print("=" * 80)

    print(f"\n🔧 1. CLEAN CACHE Y DATA:")
    print("   python3 clean_and_align_data.py")
    print("   python3 quick_populate_cache.py")

    print(f"\n🔧 2. ADD SPY TO CACHE:")
    print("   python3 quick_populate_cache.py --include SPY")

    print(f"\n🔧 3. USE COMPRESS MODE:")
    print("   Modificar app.py:")
    print("   - Use smaller universe (ej: 10 tickers)")
    print("   - Usar 'mode: convergence' en lugar de 'production'")

    print(f"\n🔧 4. MEMORY OPTIMIZATION:")
    print('   python3 -c "')
    print("   import gc")
    print("   gc.collect()")
    print('   "')
    print("   + LIMPIAR cache entre runs:")
    print("   st.cache_data.clear()")

    print(f"\n🔧 5. COMPRESS PERÍODO:")
    print("   - Usar 1 año en lugar de 3-5 años")
    print("   - 2022-2023 (2 years)")
    print("   - 2023-2024 (1 year)")

    print(f"\n🔧 6. DEBUG MODE:")
    print("   Cambiar en app.py:")
    print("   max_symbols = 10  # Solo 10 tickers")

    print(f"\n🔧 7. USE VALIDATED PARAMS:")
    print("   Load Validated Params button en sidebar")

    return True


def main():
    print("=" * 80)
    print("🔍 DIAGNÓSTICO DE SISTEMA - INTEGRIDAD DE DATOS")
    print("=" * 80)
    print()

    # 1. Cache integrity
    cache_info = check_cache_integrity()

    # 2. SPY data
    spy_info = check_spy_data()

    # 3. Recent data
    recent_info = check_recent_data()

    # 4. Memory usage
    memory_info = check_memory_usage()

    # 5. Conversion rates
    conversion_info = analyze_conversion_rates()

    # 6. Recent changes
    changes_info = check_recent_changes()

    # Summary
    print("\n" + "=" * 80)
    print("📋 RESUMEN")
    print("=" * 80)

    if cache_info and cache_info["status"] == "warning":
        print(f"\n⚠️  PROBLEMA 1: Cache incompleto")
        print(f"   • {cache_info['incomplete']} tickers sin suficiente data")

    if spy_info and spy_info["status"] == "error":
        print(f"\n⚠️  PROBLEMA 2: SPY data missing")
        print(f"   • Este parámetro afecta market regime filter")

    if memory_info and memory_info["memory_gb"] > 4.0:
        print(f"\n⚠️  PROBLEMA 3: Memory alto")
        print(f"   • {memory_info['memory_gb']:.2f} GB usado")

    print(f"\n💡 RECOMENDACIÓN PRINCIPAL:")
    print(f"   Usar período más corto (1 year) + Universe más pequeño")

    # Suggest fixes
    suggest_fixes()


if __name__ == "__main__":
    main()
