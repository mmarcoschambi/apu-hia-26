#!/usr/bin/env python3
"""
safe_db_delete.py

Wrapper seguro para ejecutar sentencias DELETE o DROP en la base de datos.
Realiza un backup automático con timestamp en data/backups/ antes de ejecutar.

Uso:
    python3 scripts/safe_db_delete.py --query "DELETE FROM daily_rs_rankings WHERE date = '2026-06-15'"
"""

import argparse
import os
import shutil
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB = ROOT / "data" / "ticker_cache.db"
BACKUP_DIR = ROOT / "data" / "backups"


def backup_database(db_path: Path) -> Path:
    """
    Crea una copia física de la base de datos en el directorio de backups con un timestamp.
    
    Args:
        db_path: Ruta a la base de datos de origen.
        
    Returns:
        Ruta del archivo de backup creado.
    """
    if not db_path.exists():
        raise FileNotFoundError(f"Base de datos no encontrada en: {db_path}")
        
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = BACKUP_DIR / f"{db_path.stem}_{timestamp}{db_path.suffix}"
    
    shutil.copy2(db_path, backup_path)
    return backup_path


def execute_destructive_query(db_path: Path, query: str, dry_run: bool = False) -> None:
    """
    Ejecuta una consulta SQL en la base de datos especificada de forma transaccional,
    realizando un backup frío previo.
    
    Args:
        db_path: Ruta a la base de datos sqlite.
        query: Sentencia SQL a ejecutar.
        dry_run: Si es True, no ejecuta la consulta ni hace el backup.
    """
    query_upper = query.upper().strip()
    is_destructive = any(word in query_upper for word in ["DELETE", "DROP", "UPDATE"])
    
    if not is_destructive:
        print(f"[Aviso] La consulta no parece destructiva (DELETE/DROP/UPDATE), pero se procesará igual.")
        
    if dry_run:
        print(f"[Dry Run] Se habría ejecutado sobre {db_path}:")
        print(f"  SQL: {query}")
        return

    # 1. Realizar backup frío obligatorio
    print("[Safe DB] Creando backup frío preventivo...")
    try:
        backup_path = backup_database(db_path)
        print(f"  ✅ Backup creado con éxito en: {backup_path}")
    except Exception as e:
        print(f"  ❌ Error crítico al crear el backup: {e}. Operación abortada.")
        sys.exit(1)

    # 2. Ejecución de la consulta
    print(f"[Safe DB] Ejecutando query en {db_path.name}...")
    conn = None
    try:
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        cursor.execute(query)
        conn.commit()
        
        rowcount = cursor.rowcount
        print(f"  ✅ Query ejecutada con éxito.")
        if rowcount >= 0:
            print(f"  📊 Filas afectadas: {rowcount}")
            
    except Exception as e:
        print(f"  ❌ Error al ejecutar la query: {e}")
        if conn:
            print("  ↩️  Realizando rollback...")
            conn.rollback()
        sys.exit(1)
    finally:
        if conn:
            conn.close()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Ejecuta consultas DELETE/DROP de forma segura con backup previo."
    )
    parser.add_argument(
        "--query",
        required=True,
        help="Sentencia SQL destructiva a ejecutar (e.g., DELETE FROM ...)",
    )
    parser.add_argument(
        "--db",
        default=str(DEFAULT_DB),
        help=f"Ruta a la base de datos (default: {DEFAULT_DB})",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simula la ejecución sin realizar backup ni modificar la base de datos.",
    )
    args = parser.parse_args()
    
    db_path = Path(args.db).resolve()
    execute_destructive_query(db_path, args.query, args.dry_run)


if __name__ == "__main__":
    main()
