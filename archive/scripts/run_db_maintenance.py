import sqlite3
import time
import os

db_path = 'data/intraday_cache.db'

def optimize():
    print(f"🚀 Iniciando optimización física de {db_path}...")
    
    # Conectamos
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # 1. Cambiar a WAL (Persistente)
    # Esto permite leer y escribir al mismo tiempo y es mucho más rápido.
    print("1. Cambiando Journal Mode a WAL...")
    cursor.execute("PRAGMA journal_mode = WAL;")
    res = cursor.fetchone()
    print(f"   -> Resultado: {res[0]}")

    # 2. Configurar parámetros para el VACUUM
    cursor.execute("PRAGMA temp_store = MEMORY;")
    cursor.execute("PRAGMA cache_size = -1000000;") # Usar 1GB RAM para el proceso

    # 3. VACUUM (Defragmentar)
    # Reconstruye la base de datos, eliminando espacio muerto y ordenando las páginas.
    print("2. Ejecutando VACUUM (Puede tardar unos minutos)...")
    start_time = time.time()
    cursor.execute("VACUUM;")
    end_time = time.time()
    print(f"   -> VACUUM completado en {end_time - start_time:.2f} segundos.")

    # 4. ANALYZE
    # Actualiza las estadísticas para que SQLite sepa qué índices usar.
    print("3. Ejecutando ANALYZE (Estadísticas)...")
    cursor.execute("ANALYZE;")

    conn.close()
    print("✅ Optimización física completada.")

if __name__ == "__main__":
    optimize()
