"""
Remove duplicate date records from ohlcv_cache
Keeps the most recent entry for each ticker/date combination
"""
import sqlite3
from pathlib import Path
import sys

def deduplicate_ohlcv():
    db_path = Path('data/ticker_cache.db')
    if not db_path.exists():
        print("❌ No se encontró data/ticker_cache.db")
        sys.exit(1)
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    print("🔍 Analizando duplicados en ohlcv_cache...")
    
    # Count total duplicates
    cursor.execute("""
        SELECT ticker, DATE(date) as day, COUNT(*) as cnt
        FROM ohlcv_cache
        GROUP BY ticker, day
        HAVING cnt > 1
    """)
    
    duplicates = cursor.fetchall()
    
    if not duplicates:
        print("✨ ¡No hay duplicados! Base de datos limpia.")
        conn.close()
        return
    
    print(f"⚠️  Encontrados {len(duplicates)} pares ticker/fecha duplicados")
    
    # Calculate impact
    total_dupes = sum(d[2] - 1 for d in duplicates)
    print(f"📊 Total de registros duplicados a eliminar: {total_dupes:,}")
    
    # Show examples
    print("\n📋 Ejemplos de duplicados:")
    for ticker, day, cnt in duplicates[:10]:
        print(f"   {ticker:<8} {day}  ({cnt} registros)")
    
    response = input("\n❓ ¿Proceder con la eliminación de duplicados? (y/n): ")
    
    if response.lower() != 'y':
        print("❌ Operación cancelada")
        conn.close()
        return
    
    print("\n🧹 Eliminando duplicados...")
    print("   (Manteniendo el registro más reciente por ticker/fecha)")
    
    # Create backup table
    print("📦 Creando backup...")
    cursor.execute("DROP TABLE IF EXISTS ohlcv_cache_backup")
    cursor.execute("CREATE TABLE ohlcv_cache_backup AS SELECT * FROM ohlcv_cache")
    conn.commit()
    
    # Delete duplicates keeping only the latest rowid
    cursor.execute("""
        DELETE FROM ohlcv_cache
        WHERE rowid NOT IN (
            SELECT MAX(rowid)
            FROM ohlcv_cache
            GROUP BY ticker, DATE(date)
        )
    """)
    
    deleted = cursor.rowcount
    conn.commit()
    
    print(f"\n✅ Eliminados {deleted:,} registros duplicados")
    print(f"💾 Backup guardado en tabla: ohlcv_cache_backup")
    
    # Verify
    cursor.execute("""
        SELECT ticker, DATE(date) as day, COUNT(*) as cnt
        FROM ohlcv_cache
        GROUP BY ticker, day
        HAVING cnt > 1
    """)
    
    remaining = cursor.fetchall()
    
    if remaining:
        print(f"⚠️  Aún quedan {len(remaining)} duplicados")
    else:
        print("✨ Base de datos completamente limpia")
    
    # Optimize database
    print("\n🔧 Optimizando base de datos...")
    cursor.execute("VACUUM")
    conn.commit()
    
    conn.close()
    print("✅ Proceso completado")

if __name__ == "__main__":
    deduplicate_ohlcv()
