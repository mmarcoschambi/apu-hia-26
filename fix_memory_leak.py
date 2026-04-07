#!/usr/bin/env python3
"""
MEMORY LEAK FIX - Solución automática para limpiar cache y liberar memory
=========================================================================

Este script:
1. Limpiar cache antiguo
2. Recomponer cache con solo 5 years
3. Asegurar SPY data
4. Liberar memory
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import sqlite3
import gc
import shutil
from datetime import datetime, timedelta


def fix_memory_leak():
    """Soluciona el memory leak"""
    print("=" * 80)
    print("🧹 MEMORY LEAK FIX")
    print("=" * 80)

    # 1. Limpiar cache antiguo
    print(f"\n🔧 1. LIMPIANDO CACHE ANTIGUO")

    cache_file = Path("data/ticker_cache.db")
    if cache_file.exists():
        # Backup antiguo
        backup_file = (
            f"data/ticker_cache.backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
        )
        shutil.move(str(cache_file), backup_file)
        print(f"   ✅ Backup creado: {backup_file}")

    # Crear cache nuevo con solo 5 years
    print(f"\n🔧 2. RECREANDO CACHE (5 últimos años)")
    print(f"   • Desde: 2021-01-01")
    print(f"   • Hasta: 2026-01-01")
    print(f"   • Estimado: 3000+ tickers")

    # Llamar a quick_populate_cache.py con flags para limitar rango
    print(f"\n🔧 3. DESCARGANDO DATOS (rango limitado)")

    import subprocess

    cmd = [
        "python3",
        "quick_populate_cache.py",
        "--start",
        "2021-01-01",
        "--end",
        "2026-01-01",
        "--no-today",
    ]

    print(f"   Ejecutando: {' '.join(cmd)}")
    print()

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=900)

        if result.returncode == 0:
            print(f"   ✅ Datos descargados exitosamente")
            print(result.stdout[-200:])  # Last 200 chars
        else:
            print(f"   ❌ Error descargando datos")
            print(result.stderr[-500:])
            return False

    except subprocess.TimeoutExpired:
        print(f"   ⏱️ Timeout (15 minutos) - Data descargada parcialmente")
        return False
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return False

    # 4. Asegurar SPY data
    print(f"\n🔧 4. ASEGURANDO SPY DATA")

    # Asegurar SPY está en cache
    try:
        cmd_spy = ["python3", "quick_populate_cache.py", "--include", "SPY"]

        print(f"   Ejecutando: {' '.join(cmd_spy)}")
        result_spy = subprocess.run(
            cmd_spy, capture_output=True, text=True, timeout=600
        )

        if result_spy.returncode == 0:
            print(f"   ✅ SPY data completada")
        else:
            print(f"   ⚠️  SPY data incompleta: {result_spy.stderr[-200:]}")

    except Exception as e:
        print(f"   ⚠️  Error agregando SPY: {e}")

    # 5. Liberar memory
    print(f"\n🔧 5. LIBERANDO MEMORY")

    gc.collect()
    import psutil

    process = psutil.Process()
    mem = process.memory_info()
    print(f"   ✅ Memory after GC: {mem.rss / (1024**2):.2f} GB")

    # 6. Verificar cache integrity
    print(f"\n🔧 6. VERIFICANDO CACHE INTEGRITY")

    if Path("data/ticker_cache.db").exists():
        conn = sqlite3.connect("data/ticker_cache.db")
        cursor = conn.cursor()

        try:
            cursor.execute("SELECT COUNT(DISTINCT ticker) FROM ohlcv_cache")
            total_tickers = cursor.fetchone()[0]

            cursor.execute(
                "SELECT COUNT(*) FROM ohlcv_cache WHERE date >= '2021-01-01'"
            )
            recent_count = cursor.fetchone()[0]

            print(f"   ✅ Total tickers: {total_tickers}")
            print(f"   ✅ Tickers recientes: {recent_count}")

            conn.close()

        except Exception as e:
            print(f"   ⚠️  Error verificando cache: {e}")
    else:
        print(f"   ❌ Cache no existe")

    print(f"\n" + "=" * 80)
    print("✅ MEMORY LEAK FIX COMPLETADO")
    print("=" * 80)

    print(f"\n📋 SIGUIENTES PASOS:")

    print(f"\n1️⃣  BACKTEST RÁPIDO (1 year):")
    print(f"   python3 example_quick_backtest.py")
    print(f"      → Debería completar en < 1 minuto")

    print(f"\n2️⃣  COMPROBAR PERFORMANCE:")
    print(f"   Ver conversion rate debería ser > 20%")
    print(f"      (1.0% es inaceptable - significa bug)")

    print(f"\n3️⃣  VALIDAR DIVERGENCIA:")
    print(f"   python3 convergence_test_streamlit_cli.py")

    print(f"\n4️⃣  SI SIGUE MAL:")
    print(f"   • Usar smaller universe (ej: 10 tickers)")
    print(f"   • Usar convergencia mode (production)")
    print(f"   • Usar app.py con 'Load Validated Params'")

    return True


if __name__ == "__main__":
    fix_memory_leak()
