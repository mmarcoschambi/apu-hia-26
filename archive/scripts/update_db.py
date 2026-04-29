#!/usr/bin/env python3
"""
Script inteligente para actualizar la base de datos
- Obtiene tickers actualizados de la web
- Detecta nuevos tickers
- Detecta tickers desactualizados
- Procesa solo lo necesario usando populate_historical_openbb.py
"""

import sqlite3
import subprocess
import sys
from pathlib import Path
from datetime import datetime

def get_tickers_from_file():
    """Lee tickers de top_global_tickers.txt"""
    ticker_file = Path("top_global_tickers.txt")
    if not ticker_file.exists():
        print("❌ No se encontró top_global_tickers.txt")
        return None
    with open(ticker_file, 'r') as f:
        return [line.strip() for line in f if line.strip()]

def get_db_tickers_with_dates(db_path='data/ticker_cache.db'):
    """Obtiene tickers de la DB con su última fecha de datos"""
    conn = sqlite3.connect(db_path)
    cursor = conn.execute('''
        SELECT ticker, MAX(date) as last_date
        FROM ohlcv_cache
        GROUP BY ticker
    ''')
    db_data = {row[0]: row[1] for row in cursor.fetchall()}
    conn.close()
    return db_data

def update_ticker_list():
    """Actualiza la lista de tickers desde la web"""
    print("🌍 Actualizando lista de tickers desde la web...")
    try:
        result = subprocess.run(
            [sys.executable, "get_top_liquidity_tickers.py"],
            capture_output=True,
            text=True,
            timeout=120  # 2 minutos para dar tiempo a la descarga
        )
        if result.returncode == 0:
            print("✅ Lista actualizada exitosamente")
            return True
        else:
            print(f"⚠️ Error actualizando lista: {result.stderr}")
            print("   ℹ️  Usando lista existente...")
            return False
    except subprocess.TimeoutExpired:
        print("⚠️ Timeout descargando lista (conexión lenta)")
        print("   ℹ️  Usando lista existente...")
        return False
    except Exception as e:
        print(f"❌ Error actualizando lista: {e}")
        print("   ℹ️  Usando lista existente...")
        return False

def check_staleness(db_data, ticker, max_days_old=7):
    """Verifica si un ticker necesita actualización"""
    if ticker not in db_data:
        return True
    
    last_date_str = db_data[ticker]
    try:
        last_date = datetime.strptime(last_date_str, '%Y-%m-%d').date()
        days_old = (datetime.now().date() - last_date).days
        return days_old > max_days_old
    except:
        return True

def main():
    parser = argparse.ArgumentParser(description='Actualizar base de datos inteligentemente')
    parser.add_argument('--years', type=int, default=2, help='Años de historia para nuevos tickers')
    parser.add_argument('--max-days-old', type=int, default=7, help='Días sin actualizar para considerar obsoleto')
    parser.add_argument('--skip-web', action='store_true', help='No actualizar lista desde web')
    
    args = parser.parse_args()
    
    # 1. Actualizar lista de tickers desde la web
    if not args.skip_web:
        update_ticker_list()
    
    # 2. Leer tickers del archivo
    file_tickers = get_tickers_from_file()
    if not file_tickers:
        return
    
    print(f"📊 {len(file_tickers)} tickers en top_global_tickers.txt")
    
    # 3. Obtener tickers de la DB
    db_data = get_db_tickers_with_dates()
    print(f"💾 {len(db_data)} tickers en la base de datos")
    
    # 4. Identificar qué procesar
    new_tickers = []
    stale_tickers = []
    
    for ticker in file_tickers:
        if ticker not in db_data:
            new_tickers.append(ticker)
        elif check_staleness(db_data, ticker, args.max_days_old):
            stale_tickers.append(ticker)
    
    print(f"\n📋 Análisis:")
    print(f"   ✅ Actualizados: {len(file_tickers) - len(new_tickers) - len(stale_tickers)}")
    print(f"   🆕 Nuevos: {len(new_tickers)}")
    print(f"   ⚠️ Desactualizados (> {args.max_days_old} días): {len(stale_tickers)}")
    
    # 5. Procesar
    tickers_to_process = new_tickers + stale_tickers
    
    if not tickers_to_process:
        print("\n✅ Todo está actualizado. Nada que procesar.")
        return
    
    print(f"\n🚀 Procesando {len(tickers_to_process)} tickers...")
    
    # Usar populate_historical_openbb.py (el completo con todas las métricas)
    cmd = [
        sys.executable,
        "populate_historical_openbb.py",
        "--tickers"
    ] + tickers_to_process + [
        "--years", str(args.years),
        "--delay", "0.3"
    ]
    
    try:
        subprocess.run(cmd, check=True)
        print("\n✅ Actualización completada")
    except KeyboardInterrupt:
        print("\n🛑 Interrumpido por usuario")
    except subprocess.CalledProcessError as e:
        print(f"\n❌ Error: {e}")

if __name__ == "__main__":
    import argparse
    main()
