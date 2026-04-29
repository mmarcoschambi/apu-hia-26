#!/usr/bin/env python3
"""
UNIVERSE MANAGER CLI - Gestión del universo de tickers
========================================================
Herramienta para agregar/ver/actualizar el universo de acciones

Uso:
    # Ver info actual
    python manage_universe.py --info
    
    # Agregar tickers
    python manage_universe.py --add "ASMB, CYTK, BBNX, ISSC"
    
    # Actualizar universo (forzar descarga)
    python manage_universe.py --refresh
    
    # Ver cache disponible
    python manage_universe.py --cache-info
"""

import sys
from pathlib import Path
import argparse
from datetime import datetime
import json

project_root = Path(__file__).resolve().parent
sys.path.insert(0, str(project_root))

from src.data.universe_manager import UniverseManager
from src.data.market_data import MarketDataProvider


def print_header(text):
    """Imprime header bonito"""
    print("\n" + "="*80)
    print(f"  {text}")
    print("="*80)


def show_info(manager):
    """Muestra información del universo actual"""
    print_header("📊 INFORMACIÓN DEL UNIVERSO")
    
    info = manager.get_info()
    
    print(f"\n{'Total Tickers:':<25} {info['total_tickers']}")
    print(f"{'Tickers Custom:':<25} {info['custom_tickers']}")
    print(f"{'Última Actualización:':<25} {info['last_updated']}")
    print(f"{'Cache Existe:':<25} {'✅ Sí' if info['cache_exists'] else '❌ No'}")
    
    # Mostrar algunos tickers de ejemplo
    universe = manager.load_universe()
    if len(universe) > 0:
        print(f"\n📋 Primeros 20 tickers:")
        print("  ", ", ".join(universe[:20]))
        
        if info['custom_tickers'] > 0:
            custom = manager.load_custom_tickers()
            print(f"\n🎯 Tickers custom ({len(custom)}):")
            print("  ", ", ".join(custom))


def add_tickers(manager, tickers_str):
    """Agrega tickers al universo"""
    print_header("➕ AGREGAR TICKERS")
    
    print(f"\nTickers a agregar: {tickers_str}")
    confirm = input("\n¿Confirmar? (s/n): ")
    
    if confirm.lower() != 's':
        print("❌ Cancelado")
        return
    
    # Agregar
    custom = manager.add_custom_tickers(tickers_str)
    
    # Reconstruir universo
    print("\n🔄 Reconstruyendo universo...")
    universe = manager.build_universe(force_refresh=True)
    
    print(f"\n✅ Universo actualizado: {len(universe)} tickers totales")


def refresh_universe(manager):
    """Fuerza actualización del universo"""
    print_header("🔄 ACTUALIZAR UNIVERSO")
    
    print("\nEsto descargará S&P 500 y NASDAQ 100 frescos")
    confirm = input("¿Continuar? (s/n): ")
    
    if confirm.lower() != 's':
        print("❌ Cancelado")
        return
    
    universe = manager.build_universe(force_refresh=True)
    print(f"\n✅ Universo actualizado: {len(universe)} tickers")


def show_cache_info():
    """Muestra información del cache de datos"""
    print_header("💾 INFORMACIÓN DEL CACHE")
    
    cache_dir = Path("data/cache")
    
    if not cache_dir.exists():
        print("\n❌ No existe directorio de cache")
        return
    
    # Contar archivos
    cache_files = list(cache_dir.glob("*.parquet"))
    
    if len(cache_files) == 0:
        print("\n📭 Cache vacío - no hay datos descargados")
        return
    
    print(f"\n📦 Archivos en cache: {len(cache_files)}")
    
    # Agrupar por fecha
    by_date = {}
    total_size = 0
    
    for file in cache_files:
        stat = file.stat()
        total_size += stat.st_size
        mod_date = datetime.fromtimestamp(stat.st_mtime).strftime('%Y-%m-%d')
        
        if mod_date not in by_date:
            by_date[mod_date] = []
        by_date[mod_date].append(file.stem)
    
    print(f"💾 Tamaño total: {total_size / (1024*1024):.1f} MB")
    print(f"\n📅 Datos por fecha de descarga:")
    
    for date in sorted(by_date.keys(), reverse=True)[:10]:  # Últimos 10 días
        tickers = by_date[date]
        print(f"  {date}: {len(tickers)} tickers")
    
    # Rango de fechas en los datos
    print(f"\n🗓️  Tickers en cache:")
    print(f"  Total: {len(cache_files)}")
    print(f"  Ejemplos: {', '.join([f.stem for f in cache_files[:10]])}")
    
    if len(cache_files) > 10:
        print(f"  ... y {len(cache_files) - 10} más")


def list_tickers(manager, pattern=None):
    """Lista todos los tickers o filtra por patrón"""
    print_header("📋 LISTA DE TICKERS")
    
    universe = manager.load_universe()
    
    if pattern:
        filtered = [t for t in universe if pattern.upper() in t]
        print(f"\nTickers que contienen '{pattern}':")
        for ticker in filtered:
            print(f"  {ticker}")
        print(f"\nTotal: {len(filtered)} tickers")
    else:
        print(f"\nTotal: {len(universe)} tickers")
        print("\nUsa --list <patron> para filtrar")
        print("Ejemplo: python manage_universe.py --list AA")


def remove_custom_tickers(manager, tickers_str):
    """Elimina tickers custom"""
    print_header("➖ ELIMINAR TICKERS CUSTOM")
    
    tickers_to_remove = [t.strip().upper() for t in tickers_str.split(',')]
    
    custom = manager.load_custom_tickers()
    removed = []
    
    for ticker in tickers_to_remove:
        if ticker in custom:
            custom.remove(ticker)
            removed.append(ticker)
    
    if len(removed) == 0:
        print("\n❌ Ningún ticker encontrado en la lista custom")
        return
    
    print(f"\nTickers a eliminar: {', '.join(removed)}")
    confirm = input("¿Confirmar? (s/n): ")
    
    if confirm.lower() != 's':
        print("❌ Cancelado")
        return
    
    # Guardar
    custom_file = Path("data/universe/custom_tickers.json")
    with open(custom_file, 'w') as f:
        json.dump({
            'tickers': sorted(custom),
            'updated': datetime.now().isoformat()
        }, f, indent=2)
    
    # Reconstruir universo
    print("\n🔄 Reconstruyendo universo...")
    manager.build_universe(force_refresh=True)
    
    print(f"\n✅ Eliminados {len(removed)} tickers")


def main():
    parser = argparse.ArgumentParser(
        description='Gestión del universo de tickers',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos:
  # Ver información
  python manage_universe.py --info
  
  # Agregar tickers
  python manage_universe.py --add "ASMB, CYTK, BBNX, ISSC, GOLD, RKLB"
  
  # Ver cache
  python manage_universe.py --cache-info
  
  # Actualizar universo
  python manage_universe.py --refresh
  
  # Listar tickers
  python manage_universe.py --list
  
  # Buscar ticker
  python manage_universe.py --list AA
  
  # Eliminar custom
  python manage_universe.py --remove "ASMB, CYTK"
        """
    )
    
    parser.add_argument('--info', action='store_true', help='Mostrar información del universo')
    parser.add_argument('--add', type=str, help='Agregar tickers (separados por comas)')
    parser.add_argument('--remove', type=str, help='Eliminar tickers custom')
    parser.add_argument('--refresh', action='store_true', help='Actualizar universo completo')
    parser.add_argument('--cache-info', action='store_true', help='Información del cache')
    parser.add_argument('--list', nargs='?', const='', help='Listar tickers (opcional: patrón de búsqueda)')
    
    args = parser.parse_args()
    
    # Si no hay argumentos, mostrar ayuda
    if not any(vars(args).values()):
        parser.print_help()
        return
    
    manager = UniverseManager()
    
    if args.info:
        show_info(manager)
    
    if args.add:
        add_tickers(manager, args.add)
    
    if args.remove:
        remove_custom_tickers(manager, args.remove)
    
    if args.refresh:
        refresh_universe(manager)
    
    if args.cache_info:
        show_cache_info()
    
    if args.list is not None:
        list_tickers(manager, args.list if args.list != '' else None)


if __name__ == "__main__":
    main()
