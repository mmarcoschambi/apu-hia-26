#!/usr/bin/env python3
"""
OPTIMIZACIÓN: Agregar Índices a SQLite
=======================================
Crea índices para acelerar queries de liquidez
Reduce tiempo de query de minutos a milisegundos
"""

import sqlite3
import time
from datetime import datetime

DB_PATH = "data/ticker_cache.db"

def create_indexes():
    """
    Crea índices optimizados para queries de liquidez
    """
    print("="*80)
    print("  ⚡ OPTIMIZACIÓN: Creando Índices en SQLite")
    print("="*80)
    print(f"\nBase de datos: {DB_PATH}")
    print(f"Fecha: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Lista de índices a crear
    indexes = [
        {
            'name': 'idx_ohlcv_date',
            'table': 'ohlcv_cache',
            'columns': 'date',
            'reason': 'Acelera filtros por fecha (WHERE date = ?)'
        },
        {
            'name': 'idx_ohlcv_rolling_dvol',
            'table': 'ohlcv_cache',
            'columns': 'rolling_dollar_vol_20',
            'reason': 'Acelera filtros por liquidez (WHERE rolling_dollar_vol_20 >= ?)'
        },
        {
            'name': 'idx_ohlcv_date_ticker',
            'table': 'ohlcv_cache',
            'columns': 'date, ticker',
            'reason': 'Índice compuesto para queries comunes'
        },
        {
            'name': 'idx_ohlcv_date_rolling',
            'table': 'ohlcv_cache',
            'columns': 'date, rolling_dollar_vol_20 DESC',
            'reason': 'Optimiza ordenamiento por liquidez en fecha específica'
        },
        {
            'name': 'idx_ohlcv_ticker_date',
            'table': 'ohlcv_cache',
            'columns': 'ticker, date',
            'reason': 'Acelera GROUP BY ticker + filtros de fecha'
        },
        {
            'name': 'idx_ohlcv_dollar_volume',
            'table': 'ohlcv_cache',
            'columns': 'dollar_volume DESC',
            'reason': 'Optimiza ordenamiento por dollar_volume (All Market query)'
        }
    ]
    
    print("\n📊 Índices a crear:")
    for idx in indexes:
        print(f"  • {idx['name']}: {idx['reason']}")
    
    # Verificar índices existentes
    cursor.execute("SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='ohlcv_cache'")
    existing = [row[0] for row in cursor.fetchall()]
    print(f"\n📋 Índices existentes: {existing}")
    
    # Crear cada índice
    print("\n⏳ Creando índices...")
    created = 0
    skipped = 0
    
    for idx in indexes:
        if idx['name'] in existing:
            print(f"  ⏭️  {idx['name']}: Ya existe")
            skipped += 1
            continue
        
        try:
            start_time = time.time()
            
            sql = f"CREATE INDEX {idx['name']} ON {idx['table']} ({idx['columns']})"
            cursor.execute(sql)
            conn.commit()
            
            elapsed = time.time() - start_time
            print(f"  ✅ {idx['name']}: Creado en {elapsed:.2f}s")
            created += 1
            
        except Exception as e:
            print(f"  ❌ {idx['name']}: Error - {e}")
    
    conn.close()
    
    print("\n" + "="*80)
    print("  📊 RESUMEN")
    print("="*80)
    print(f"\n✅ Índices creados: {created}")
    print(f"⏭️  Índices omitidos (ya existían): {skipped}")
    
    return created, skipped


def benchmark_queries():
    """
    Prueba velocidad de queries antes y después de índices
    """
    print("\n" + "="*80)
    print("  🏎️  BENCHMARK: Velocidad de Queries")
    print("="*80)
    
    conn = sqlite3.connect(DB_PATH)
    
    # Query 1: Filtrar por fecha
    print("\n📊 Query 1: Filtrar por fecha")
    query1 = "SELECT COUNT(*) FROM ohlcv_cache WHERE date = '2024-01-02'"
    
    start = time.time()
    cursor = conn.execute(query1)
    result = cursor.fetchone()[0]
    elapsed = time.time() - start
    
    print(f"  Resultado: {result} filas")
    print(f"  Tiempo: {elapsed*1000:.2f}ms")
    
    # Query 2: Filtrar por liquidez
    print("\n📊 Query 2: Filtrar por liquidez")
    query2 = """
        SELECT ticker, rolling_dollar_vol_20 
        FROM ohlcv_cache 
        WHERE date = '2024-01-02' 
        AND rolling_dollar_vol_20 >= 15000000
        ORDER BY rolling_dollar_vol_20 DESC
        LIMIT 50
    """
    
    start = time.time()
    cursor = conn.execute(query2)
    results = cursor.fetchall()
    elapsed = time.time() - start
    
    print(f"  Resultado: {len(results)} tickers")
    print(f"  Tiempo: {elapsed*1000:.2f}ms")
    if len(results) > 0:
        print(f"  Top ticker: {results[0][0]} (${results[0][1]/1e9:.2f}B)")
    
    # Query 3: Join complejo (como en get_active_tickers)
    print("\n📊 Query 3: Join con universe")
    query3 = """
        SELECT o.ticker
        FROM ohlcv_cache o
        JOIN universe u ON o.ticker = u.ticker
        WHERE o.date = '2024-01-02'
        AND o.close >= 5
        AND o.rolling_dollar_vol_20 >= 15000000
        ORDER BY o.rolling_dollar_vol_20 DESC
        LIMIT 50
    """
    
    start = time.time()
    cursor = conn.execute(query3)
    results = cursor.fetchall()
    elapsed = time.time() - start
    
    print(f"  Resultado: {len(results)} tickers")
    print(f"  Tiempo: {elapsed*1000:.2f}ms")
    
    # Análisis
    print("\n" + "="*80)
    print("  📈 ANÁLISIS")
    print("="*80)
    
    if elapsed < 0.1:  # < 100ms
        print("\n✅ EXCELENTE: Queries en < 100ms")
        print("   • Índices funcionando correctamente")
        print("   • Backtest será rápido")
    elif elapsed < 0.5:  # < 500ms
        print("\n⚠️  ACEPTABLE: Queries en 100-500ms")
        print("   • Índices ayudando pero se puede mejorar")
        print("   • Considera VACUUM para optimizar")
    else:  # > 500ms
        print("\n❌ LENTO: Queries en > 500ms")
        print("   • Índices no están siendo usados correctamente")
        print("   • Ejecuta ANALYZE para actualizar estadísticas")
    
    conn.close()


def optimize_database():
    """
    Ejecuta comandos de optimización adicionales
    """
    print("\n" + "="*80)
    print("  🔧 OPTIMIZACIÓN ADICIONAL")
    print("="*80)
    
    conn = sqlite3.connect(DB_PATH)
    
    # ANALYZE: Actualiza estadísticas para el query planner
    print("\n⏳ Ejecutando ANALYZE...")
    start = time.time()
    conn.execute("ANALYZE")
    elapsed = time.time() - start
    print(f"  ✅ Completado en {elapsed:.2f}s")
    
    # VACUUM: Reorganiza base de datos y libera espacio
    print("\n⏳ Ejecutando VACUUM (esto puede tardar)...")
    start = time.time()
    conn.execute("VACUUM")
    elapsed = time.time() - start
    print(f"  ✅ Completado en {elapsed:.2f}s")
    
    conn.close()
    
    print("\n✅ Optimización completada")


def main():
    print("\n" + "="*80)
    print("  🚀 INICIO DE OPTIMIZACIÓN")
    print("="*80)
    
    # Crear índices
    created, skipped = create_indexes()
    
    # Si se crearon nuevos índices, ejecutar optimizaciones
    if created > 0:
        print("\n💡 Nuevos índices creados, ejecutando optimizaciones adicionales...")
        optimize_database()
    
    # Benchmark
    benchmark_queries()
    
    # Conclusión
    print("\n" + "="*80)
    print("  🎉 OPTIMIZACIÓN COMPLETADA")
    print("="*80)
    
    print("\n✅ Base de datos optimizada")
    print("✅ Queries deberían ser 10-100x más rápidas")
    
    print("\n💡 Próximos pasos:")
    print("   1. Ejecuta un backtest con SQLite")
    print("   2. Debería tardar segundos en vez de minutos")
    print("   3. Si sigue lento, ejecuta este script de nuevo")
    
    print("\n📊 Estadísticas:")
    print(f"   • Índices creados: {created}")
    print(f"   • Total índices: {created + skipped}")


if __name__ == "__main__":
    main()
