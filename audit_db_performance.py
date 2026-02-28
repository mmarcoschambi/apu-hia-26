import sqlite3
import os
import sys

db_path = 'data/intraday_cache.db'

print("=== 1. AUDITORÍA DE SISTEMA DE ARCHIVOS ===")
# Verificar si es un link o archivo real
if os.path.islink(db_path):
    print(f"⚠️ PELIGRO: {db_path} es un ENLACE SIMBÓLICO.")
    print(f"Apunta a: {os.readlink(db_path)}")
else:
    print(f"✅ OK: {db_path} es un archivo físico.")

# Verificar sistema de archivos (stat)
stat_info = os.stat(db_path)
print(f"Tamaño: {stat_info.st_size / (1024*1024*1024):.2f} GB")
print(f"Ubicación absoluta: {os.path.abspath(db_path)}")

if "/mnt/" in os.path.abspath(db_path):
    print("❌ ALERTA CRÍTICA: La base de datos está en /mnt (Windows FS). MOVER INMEDIATAMENTE.")
else:
    print("✅ OK: La base de datos está en el sistema de archivos de Linux.")

print("\n=== 2. AUDITORÍA INTERNA SQLITE ===")
try:
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Obtener tablas
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = cursor.fetchall()
    print(f"Tablas encontradas: {[t[0] for t in tables]}")

    for table in tables:
        t_name = table[0]
        print(f"\n--- Tabla: {t_name} ---")
        
        # Verificar Schema para ver tipos de datos
        cursor.execute(f"PRAGMA table_info({t_name})")
        cols = cursor.fetchall()
        col_names = [c[1] for c in cols]
        print(f"Columnas: {col_names}")

        # Verificar Índices
        cursor.execute(f"PRAGMA index_list({t_name})")
        indexes = cursor.fetchall()
        
        if not indexes:
            print(f"❌ ALERTA: La tabla '{t_name}' NO TIENE ÍNDICES EXPLÍCITOS. Las consultas serán lentas.")
        else:
            print(f"ℹ️ Índices encontrados ({len(indexes)}):")
            for idx in indexes:
                idx_name = idx[1]
                cursor.execute(f"PRAGMA index_info({idx_name})")
                idx_cols = cursor.fetchall()
                col_names_idx = [c[2] for c in idx_cols]
                print(f"   - {idx_name}: {col_names_idx}")

    print("\n=== 3. CONFIGURACIÓN DE RENDIMIENTO (PRAGMAS) ===")
    
    cursor.execute("PRAGMA journal_mode")
    journal = cursor.fetchone()[0]
    print(f"Journal Mode: {journal} {'✅ (Rápido)' if journal.upper() == 'WAL' else '⚠️ (Lento, cambiar a WAL)'}")

    cursor.execute("PRAGMA synchronous")
    sync = cursor.fetchone()[0]
    # 0=OFF, 1=NORMAL, 2=FULL
    print(f"Synchronous: {sync} {'✅ (Optimizado)' if sync < 2 else '⚠️ (Seguro pero lento)'}")

    cursor.execute("PRAGMA cache_size")
    cache = cursor.fetchone()[0]
    print(f"Cache Size: {cache} páginas")

    cursor.execute("PRAGMA page_size")
    page_size = cursor.fetchone()[0]
    print(f"Page Size: {page_size} bytes")

    conn.close()

except Exception as e:
    print(f"Error al leer la DB: {e}")
