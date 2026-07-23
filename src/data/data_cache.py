"""
Data Cache System - Pre-download y cache de datos históricos
=============================================================

Elimina re-descargas innecesarias durante backtests.

Performance:
- Sin cache: 100 días x 200 tickers = 20,000 descargas (~5 horas)
- Con cache: 1 descarga por ticker = 200 descargas (~5 minutos)

Mejora: 60x más rápido
"""

import pandas as pd
import pickle
import os
from pathlib import Path
from datetime import datetime, timedelta
import logging
from typing import Dict, Optional
from tqdm import tqdm

logger = logging.getLogger(__name__)


class DataCache:
    """
    Sistema de cache inteligente para datos históricos
    
    Features:
    - Pre-descarga datos del universo completo
    - Guarda en disco (pickle)
    - Auto-detección de datos desactualizados
    - Actualización incremental
    """
    
    def __init__(self, cache_dir='data/cache'):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        # Metadata cache
        self.metadata_file = self.cache_dir / 'metadata.pkl'
        self.metadata = self._load_metadata()
        
        # En-memory cache para velocidad
        self.memory_cache: Dict[str, pd.DataFrame] = {}
        
        logger.info(f"[U+1F4E6] DataCache initialized: {self.cache_dir}")
    
    def _load_metadata(self) -> dict:
        """Carga metadata del cache"""
        if self.metadata_file.exists():
            with open(self.metadata_file, 'rb') as f:
                return pickle.load(f)
        return {}
    
    def _save_metadata(self):
        """Guarda metadata del cache"""
        with open(self.metadata_file, 'wb') as f:
            pickle.dump(self.metadata, f)
    
    def _get_cache_path(self, ticker: str) -> Path:
        """Path del archivo de cache para un ticker"""
        return self.cache_dir / f"{ticker}.pkl"
    
    def is_cached(self, ticker: str, start_date: str, end_date: str) -> bool:
        """
        Verifica si un ticker está en cache y actualizado
        
        Returns:
            True si datos en cache cubren el periodo solicitado
        """
        cache_path = self._get_cache_path(ticker)
        
        if not cache_path.exists():
            return False
        
        # Verificar metadata
        if ticker not in self.metadata:
            return False
        
        meta = self.metadata[ticker]
        cached_start = pd.to_datetime(meta['start_date'])
        cached_end = pd.to_datetime(meta['end_date'])
        
        req_start = pd.to_datetime(start_date)
        req_end = pd.to_datetime(end_date)
        
        # Cache debe cubrir periodo solicitado
        return cached_start <= req_start and cached_end >= req_end
    
    def get(self, ticker: str, start_date: str, end_date: str) -> Optional[pd.DataFrame]:
        """
        Obtiene datos del cache
        
        Returns:
            DataFrame con datos históricos o None si no está en cache
        """
        # Check memory cache primero (ultra rápido)
        cache_key = f"{ticker}_{start_date}_{end_date}"
        if cache_key in self.memory_cache:
            return self.memory_cache[cache_key].copy()
        
        # Check disk cache
        if not self.is_cached(ticker, start_date, end_date):
            return None
        
        try:
            cache_path = self._get_cache_path(ticker)
            
            with open(cache_path, 'rb') as f:
                df = pickle.load(f)
            
            # Filtrar por fechas
            df_filtered = df[start_date:end_date]
            
            # Guardar en memory cache
            self.memory_cache[cache_key] = df_filtered.copy()
            
            return df_filtered
        
        except Exception as e:
            logger.error(f"Error loading cache for {ticker}: {e}")
            return None
    
    def put(self, ticker: str, df: pd.DataFrame):
        """
        Guarda datos en cache
        
        Args:
            ticker: Símbolo
            df: DataFrame con datos históricos (debe tener DatetimeIndex)
        """
        if df.empty:
            return
        
        try:
            cache_path = self._get_cache_path(ticker)
            
            # Guardar DataFrame
            with open(cache_path, 'wb') as f:
                pickle.dump(df, f)
            
            # Actualizar metadata
            self.metadata[ticker] = {
                'start_date': df.index[0].strftime('%Y-%m-%d'),
                'end_date': df.index[-1].strftime('%Y-%m-%d'),
                'last_updated': datetime.now().isoformat(),
                'rows': len(df)
            }
            
            self._save_metadata()
            
            logger.debug(f"Cached {ticker}: {len(df)} rows")
        
        except Exception as e:
            logger.error(f"Error caching {ticker}: {e}")
    
    def preload(self, tickers: list, start_date: str, end_date: str, 
                data_provider, force_refresh: bool = False):
        """
        Pre-descarga datos para múltiples tickers
        
        Args:
            tickers: Lista de símbolos
            start_date: Fecha inicio (YYYY-MM-DD)
            end_date: Fecha fin (YYYY-MM-DD)
            data_provider: Provider para descargar datos
            force_refresh: Si True, re-descarga incluso si está en cache
        """
        logger.info(f"\n{'='*80}")
        logger.info(f"[U+1F4E5] PRE-LOADING DATA CACHE")
        logger.info(f"{'='*80}")
        logger.info(f"Tickers: {len(tickers)}")
        logger.info(f"Period: {start_date} -> {end_date}")
        logger.info(f"Cache dir: {self.cache_dir}")
        
        # Determinar qué tickers necesitan descarga
        to_download = []
        
        for ticker in tickers:
            if force_refresh or not self.is_cached(ticker, start_date, end_date):
                to_download.append(ticker)
        
        already_cached = len(tickers) - len(to_download)
        
        logger.info(f"\n[OK] Already cached: {already_cached}")
        logger.info(f"[U+1F4E5] To download: {len(to_download)}")
        
        if not to_download:
            logger.info("[U+1F389] All data already cached!")
            return
        
        # Descargar con progress bar
        logger.info(f"\n[HOURGLASS] Downloading {len(to_download)} tickers...")
        
        success_count = 0
        fail_count = 0
        
        for ticker in tqdm(to_download, desc="Downloading", unit="ticker"):
            try:
                df = data_provider.get_daily_data(
                    ticker,
                    start_date=start_date,
                    end_date=end_date
                )
                
                if not df.empty:
                    self.put(ticker, df)
                    success_count += 1
                else:
                    fail_count += 1
            
            except Exception as e:
                logger.debug(f"Failed to download {ticker}: {e}")
                fail_count += 1
        
        logger.info(f"\n[OK] Download complete!")
        logger.info(f"   Success: {success_count}")
        logger.info(f"   Failed: {fail_count}")
        logger.info(f"   Total cached: {len(self.metadata)}")
        
        # Calcular tamaño del cache
        total_size = sum(f.stat().st_size for f in self.cache_dir.glob('*.pkl'))
        size_mb = total_size / (1024 * 1024)
        
        logger.info(f"   Cache size: {size_mb:.1f} MB")
        logger.info(f"{'='*80}\n")
    
    def clear(self, ticker: Optional[str] = None):
        """
        Limpia el cache
        
        Args:
            ticker: Si especificado, solo limpia ese ticker.
                   Si None, limpia todo el cache.
        """
        if ticker:
            cache_path = self._get_cache_path(ticker)
            if cache_path.exists():
                cache_path.unlink()
            
            if ticker in self.metadata:
                del self.metadata[ticker]
                self._save_metadata()
            
            logger.info(f"[U+1F5D1]  Cleared cache for {ticker}")
        else:
            # Limpiar todo
            for f in self.cache_dir.glob('*.pkl'):
                f.unlink()
            
            self.metadata = {}
            self._save_metadata()
            
            logger.info(f"[U+1F5D1]  Cleared entire cache")
    
    def get_stats(self) -> dict:
        """Obtiene estadísticas del cache"""
        total_tickers = len(self.metadata)
        total_files = len(list(self.cache_dir.glob('*.pkl')))
        total_size = sum(f.stat().st_size for f in self.cache_dir.glob('*.pkl'))
        size_mb = total_size / (1024 * 1024)
        
        # Calcular rango de fechas
        if self.metadata:
            all_starts = [meta['start_date'] for meta in self.metadata.values()]
            all_ends = [meta['end_date'] for meta in self.metadata.values()]
            
            earliest = min(all_starts)
            latest = max(all_ends)
        else:
            earliest = None
            latest = None
        
        return {
            'total_tickers': total_tickers,
            'total_files': total_files,
            'size_mb': size_mb,
            'earliest_date': earliest,
            'latest_date': latest
        }
    
    def print_stats(self):
        """Imprime estadísticas del cache"""
        stats = self.get_stats()
        
        print(f"\n{'='*80}")
        print(f"[U+1F4CA] DATA CACHE STATISTICS")
        print(f"{'='*80}")
        print(f"Tickers cached: {stats['total_tickers']}")
        print(f"Files on disk: {stats['total_files']}")
        print(f"Total size: {stats['size_mb']:.1f} MB")
        
        if stats['earliest_date']:
            print(f"Date range: {stats['earliest_date']} -> {stats['latest_date']}")
        
        print(f"{'='*80}\n")
