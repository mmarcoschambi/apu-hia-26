#!/usr/bin/env python3
"""
ADD TICKERS FROM JSON - Validación e integración desde JSON
===========================================================
Lee tickers desde scripts/universe/tickers_universo.json y valida
contra el universo existente para evitar duplicados.

Usage:
    python3 add_tickers_from_json.py --source scripts/universe/tickers_universo.json
    python3 add_tickers_from_json.py --source scripts/universe/tickers_universo.json --output new_tickers.txt
"""

import sys
import json
import argparse
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).resolve().parent))

from src.data.ticker_cache import TickerCache
from src.data.universe_manager import UniverseManager


def load_json_tickers(filepath: str):
    """Carga tickers desde archivo JSON"""
    with open(filepath, 'r') as f:
        tickers = json.load(f)
    
    # Normalizar a mayúsculas y limpiar
    tickers = [t.upper().strip() for t in tickers if t.strip()]
    tickers = sorted(set(tickers))  # Eliminar duplicados
    
    return tickers


def get_existing_tickers():
    """Obtiene tickers ya presentes en la base de datos"""
    cache = TickerCache()
    query = "SELECT DISTINCT ticker FROM ohlcv_cache"
    existing = set([row[0] for row in cache.conn.execute(query).fetchall()])
    cache.close()
    return existing


def filter_new_tickers(json_tickers, existing_tickers):
    """Filtra tickers nuevos que no están en DB"""
    new_tickers = [t for t in json_tickers if t not in existing_tickers]
    duplicate_count = len(json_tickers) - len(new_tickers)
    
    return new_tickers, duplicate_count


def main():
    parser = argparse.ArgumentParser(description='Add tickers from JSON with validation')
    parser.add_argument('--source', required=True, help='Path to JSON file with tickers')
    parser.add_argument('--output', default='new_tickers_to_add.txt', 
                       help='Output file with new tickers to add')
    parser.add_argument('--no-validate', action='store_true', 
                       help='Skip duplicate checking (not recommended)')
    
    args = parser.parse_args()
    
    source_path = Path(args.source)
    
    if not source_path.exists():
        print(f"❌ Error: File not found: {source_path}")
        return 1
    
    print("=" * 80)
    print("📦 ADD TICKERS FROM JSON")
    print("=" * 80)
    print(f"Source: {source_path}")
    print()
    
    # Cargar tickers desde JSON
    print("📂 Loading tickers from JSON...", end=" ", flush=True)
    json_tickers = load_json_tickers(source_path)
    print(f"✅ {len(json_tickers)} tickers found")
    
    # Validar duplicados
    if not args.no_validate:
        print("🔍 Checking for duplicates in database...", end=" ", flush=True)
        existing = get_existing_tickers()
        print(f"✅ {len(existing)} tickers already in DB")
        
        new_tickers, duplicate_count = filter_new_tickers(json_tickers, existing)
        
        print()
        print("=" * 80)
        print("📊 VALIDATION RESULTS")
        print("=" * 80)
        print(f"Total in JSON:     {len(json_tickers)}")
        print(f"Already in DB:     {duplicate_count}")
        print(f"New to add:        {len(new_tickers)}")
        print()
        
        if len(new_tickers) == 0:
            print("✅ All tickers from JSON are already in the database!")
            print("   Nothing to add.")
            return 0
    else:
        new_tickers = json_tickers
        print(f"⚠️  Skipping validation (--no-validate)")
    
    # Mostrar muestra de tickers a agregar
    print("📋 Sample of new tickers to add:")
    print(f"   {', '.join(new_tickers[:30])}")
    if len(new_tickers) > 30:
        print(f"   ... and {len(new_tickers) - 30} more")
    print()
    
    # Guardar lista de nuevos tickers
    output_path = Path(args.output)
    with open(output_path, 'w') as f:
        f.write(f"# New tickers to add - {datetime.now()}\n")
        f.write(f"# Total: {len(new_tickers)}\n")
        for ticker in new_tickers:
            f.write(f"{ticker}\n")
    
    print(f"💾 New tickers list saved to: {output_path}")
    print()
    print("=" * 80)
    print("✅ VALIDATION COMPLETE")
    print("=" * 80)
    print()
    print("🚀 Next steps:")
    print(f"   1. Download data:")
    print(f"      python3 expand_universe.py --ticker-file {output_path} --workers 5")
    print()
    print(f"   2. Precompute indicators:")
    print(f"      python3 precompute_all_indicators.py --tickers-file {output_path}")
    print()
    print(f"   3. Precompute patterns:")
    print(f"      python3 precompute_patterns.py --tickers-file {output_path} --merge")
    print()
    print(f"   OR run the complete automated pipeline:")
    print(f"      ./expand_universe_complete.sh --tickers-file {output_path}")
    print()
    
    return 0


if __name__ == '__main__':
    sys.exit(main())
