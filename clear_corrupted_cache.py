#!/usr/bin/env python3
"""
Script para limpiar el cache corrupto de yfinance y regenerarlo con OpenBB

Uso:
    # Limpiar ticker específico
    python3 clear_corrupted_cache.py DIS AAPL TSLA
    
    # Limpiar todo el cache (tarda varios minutos)
    python3 clear_corrupted_cache.py --all
    
    # Limpiar y regenerar datos para un rango de fechas
    python3 clear_corrupted_cache.py DIS --refetch --start 2018-01-01 --end 2018-12-31
"""

import sqlite3
import sys
import argparse
from pathlib import Path
from src.data.ticker_cache import TickerCache
import logging

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

def clear_all_cache(db_path):
    """Limpia todo el cache OHLCV"""
    conn = sqlite3.connect(str(db_path))
    cursor = conn.execute('SELECT COUNT(*) FROM ohlcv_cache')
    before = cursor.fetchone()[0]
    
    logger.info(f'Registros en cache: {before:,}')
    logger.info('⚠️  Limpiando todo el cache... esto puede tardar varios minutos')
    
    conn.execute('DELETE FROM ohlcv_cache')
    conn.commit()
    
    cursor = conn.execute('SELECT COUNT(*) FROM ohlcv_cache')
    after = cursor.fetchone()[0]
    
    logger.info(f'✓ Cache limpiado. Registros eliminados: {before:,}')
    conn.close()

def clear_tickers_cache(db_path, tickers):
    """Limpia cache para tickers específicos"""
    conn = sqlite3.connect(str(db_path))
    
    deleted_total = 0
    for ticker in tickers:
        result = conn.execute('DELETE FROM ohlcv_cache WHERE ticker = ?', (ticker,))
        deleted = result.rowcount
        deleted_total += deleted
        if deleted > 0:
            logger.info(f'✓ {ticker}: {deleted:,} registros eliminados')
        else:
            logger.info(f'  {ticker}: no tenía datos en cache')
    
    conn.commit()
    conn.close()
    logger.info(f'\n✓ Total eliminado: {deleted_total:,} registros')

def refetch_data(tickers, start_date, end_date):
    """Re-descarga datos usando OpenBB"""
    logger.info(f'\nDescargando datos desde {start_date} hasta {end_date}...')
    cache = TickerCache()
    
    for ticker in tickers:
        logger.info(f'Descargando {ticker}...')
        df = cache.get_ohlcv(ticker, start_date, end_date)
        if df is not None and not df.empty:
            logger.info(f'  ✓ {ticker}: {len(df)} días descargados')
        else:
            logger.warning(f'  ✗ {ticker}: no se pudo descargar')
    
    cache.close()
    logger.info('\n✓ Descarga completada')

def main():
    parser = argparse.ArgumentParser(description='Limpiar cache corrupto de yfinance')
    parser.add_argument('tickers', nargs='*', help='Tickers a limpiar (o --all para todo)')
    parser.add_argument('--all', action='store_true', help='Limpiar todo el cache')
    parser.add_argument('--refetch', action='store_true', help='Re-descargar datos después de limpiar')
    parser.add_argument('--start', default='2018-01-01', help='Fecha inicio para re-descarga')
    parser.add_argument('--end', default='2024-12-31', help='Fecha fin para re-descarga')
    
    args = parser.parse_args()
    
    db_path = Path('data/ticker_cache.db')
    if not db_path.exists():
        logger.error(f'Error: Database no encontrada en {db_path}')
        return 1
    
    if args.all:
        response = input('⚠️  Esto borrará TODO el cache (~12M registros). ¿Continuar? (yes/no): ')
        if response.lower() != 'yes':
            logger.info('Operación cancelada')
            return 0
        clear_all_cache(db_path)
    elif args.tickers:
        tickers = [t.upper() for t in args.tickers]
        logger.info(f'Limpiando cache para: {", ".join(tickers)}')
        clear_tickers_cache(db_path, tickers)
        
        if args.refetch:
            refetch_data(tickers, args.start, args.end)
    else:
        parser.print_help()
        return 1
    
    logger.info('\n✓ Operación completada')
    logger.info('Los datos se regenerarán automáticamente con OpenBB cuando sean necesarios')
    return 0

if __name__ == '__main__':
    sys.exit(main())
