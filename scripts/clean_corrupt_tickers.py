#!/usr/bin/env python3
"""
clean_corrupt_tickers.py

Audita y purga los tickers de ohlcv_cache que sufren de cross-contamination
de precios (mismo patrón exacto de precios Close entre diferentes tickers
debido al bug del Issue #39).

Uso:
    python3 scripts/clean_corrupt_tickers.py --db data/ticker_cache.db
    python3 scripts/clean_corrupt_tickers.py --db data/ticker_cache.db --execute
"""

import argparse
import hashlib
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
    """Crea una copia física de la base de datos antes de la purga."""
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = BACKUP_DIR / f"{db_path.stem}_pre_clean_{timestamp}{db_path.suffix}"
    print(f"[Safe Clean] Copiando DB para backup en: {backup_path.name}...")
    shutil.copy2(db_path, backup_path)
    return backup_path


def audit_corrupt_tickers(db_path: Path, min_matching_days: int = 5) -> dict[str, list[str]]:
    """
    Escanea la base de datos buscando series de precios idénticas entre diferentes tickers.
    
    Returns:
        Un diccionario donde la clave es el hash de la serie de precios y el valor es la lista de tickers
        que comparten esa serie de precios idéntica.
    """
    print(f"[Audit] Analizando ohlcv_cache en {db_path.name}...")
    
    # 1. Cargar precios de junio 2026 (periodo de la corrupción)
    conn = sqlite3.connect(str(db_path))
    query = """
        SELECT ticker, date, close 
        FROM ohlcv_cache 
        WHERE date BETWEEN '2026-06-01' AND '2026-06-30'
        ORDER BY ticker, date
    """
    cursor = conn.cursor()
    cursor.execute(query)
    rows = cursor.fetchall()
    conn.close()
    
    # 2. Agrupar por ticker
    ticker_data = {}
    for ticker, date, close in rows:
        if ticker not in ticker_data:
            ticker_data[ticker] = []
        ticker_data[ticker].append((date, close))
        
    # 3. Generar hash de precios para cada ticker
    # Usamos Close ordenados por fecha. Solo consideramos series con un largo mínimo.
    price_groups = {}
    for ticker, data in ticker_data.items():
        # Filtrar días con Close nulo para evitar TypeErrors
        valid_data = [(d, c) for d, c in data if c is not None]
        if len(valid_data) < min_matching_days:
            continue
        # Crear firma de la serie: "date1:close1,date2:close2..."
        signature = ",".join(f"{d}:{c:.4f}" for d, c in valid_data)
        sig_hash = hashlib.md5(signature.encode("utf-8")).hexdigest()
        
        if sig_hash not in price_groups:
            price_groups[sig_hash] = []
        price_groups[sig_hash].append(ticker)
        
    # 4. Filtrar grupos colisionados (tamaño > 1)
    collisions = {h: tickers for h, tickers in price_groups.items() if len(tickers) > 1}
    return collisions


def purge_and_reloading_plan(db_path: Path, collisions: dict[str, list[str]], execute: bool) -> None:
    """
    Informa y ejecuta la purga de los tickers duplicados detectados.
    """
    if not collisions:
        print("✨ ¡Perfecto! No se detectaron colisiones de precios cruzados en la base de datos.")
        return
        
    tickers_to_purge = set()
    print("\n⚠️  COLISIONES DETECTADAS (Mismos precios entre tickers diferentes):")
    for sig_hash, tickers in collisions.items():
        print(f"  • Hash {sig_hash[:8]}: {', '.join(tickers)}")
        # Para estar seguros de limpiar la contaminación, purgamos todos los tickers del grupo
        # para que se vuelvan a descargar limpiamente desde yfinance.
        tickers_to_purge.update(tickers)
        
    print(f"\n📊 Total de tickers contaminados a purgar: {len(tickers_to_purge)}")
    
    if not execute:
        print("\n[Dry Run] Ejecución en modo simulación. No se borró ningún dato.")
        print("Usa la opción --execute para aplicar los cambios físicamente.")
        return

    # Realizar backup frío previo
    backup_path = backup_database(db_path)
    print(f"  ✅ Backup preventivo guardado con éxito.")

    # Ejecutar DELETE
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()
    
    tickers_list = list(tickers_to_purge)
    placeholders = ",".join("?" for _ in tickers_list)
    delete_query = f"DELETE FROM ohlcv_cache WHERE ticker IN ({placeholders})"
    
    try:
        print(f"[Purge] Eliminando registros de ohlcv_cache...")
        cursor.execute(delete_query, tickers_list)
        conn.commit()
        print(f"  ✅ Registros eliminados correctamente. Filas afectadas: {cursor.rowcount}")
    except Exception as e:
        print(f"  ❌ Error al borrar registros: {e}")
        conn.rollback()
        sys.exit(1)
    finally:
        conn.close()
        
    print("\n🚀 Purga completada.")
    print("Próximo paso: Ejecutar scripts/refresh_ticker_cache.py para recargar los tickers de forma limpia.")


def main():
    parser = argparse.ArgumentParser(
        description="Audita y limpia cross-contamination de precios en la base de datos."
    )
    parser.add_argument(
        "--db",
        default=str(DEFAULT_DB),
        help=f"Ruta a la base de datos (default: {DEFAULT_DB})",
    )
    parser.add_argument(
        "--min-days",
        type=int,
        default=10,
        help="Días mínimos en junio para comparar la firma de precios (default: 10)",
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Ejecuta físicamente el borrado de datos duplicados con backup previo.",
    )
    args = parser.parse_args()
    
    db_path = Path(args.db).resolve()
    if not db_path.exists():
        print(f"❌ La base de datos no existe: {db_path}")
        sys.exit(1)
        
    collisions = audit_corrupt_tickers(db_path, args.min_days)
    purge_and_reloading_plan(db_path, collisions, args.execute)


if __name__ == "__main__":
    main()
