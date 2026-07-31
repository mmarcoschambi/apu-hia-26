import sqlite3
import argparse
from pathlib import Path

def main():
    parser = argparse.ArgumentParser(description="Purgar datos de precios invalidos de ohlcv_cache")
    parser.add_argument("--db", type=str, default="data/ticker_cache.db")
    args = parser.parse_args()
    
    db_path = Path(args.db)
    if not db_path.exists():
        print(f"[ERROR] DB no encontrada: {db_path}")
        return 1

    conn = sqlite3.connect(str(db_path))
    
    # Check rows to delete
    n_invalid = conn.execute("SELECT COUNT(*) FROM ohlcv_cache WHERE open <= 0 OR open IS NULL OR close <= 0 OR close IS NULL").fetchone()[0]
    print(f"Borrando {n_invalid} filas con precios invalidos (<=0 o NULL)...")
    
    n_deleted = conn.execute("DELETE FROM ohlcv_cache WHERE open <= 0 OR open IS NULL OR close <= 0 OR close IS NULL").rowcount
    conn.commit()
    
    print("Ejecutando VACUUM para liberar espacio...")
    conn.execute("VACUUM")
    
    conn.close()
    print(f"Limpieza completada. {n_deleted} filas borradas.")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
