"""
Parallel Scanner - Multiprocessing para análisis de tickers
===========================================================

Usa todos los cores del CPU para procesar múltiples tickers en paralelo.

Performance:
- Serial: 200 tickers x 2 seg = 400 seg
- Parallel (8 cores): 200/8 x 2 seg = 50 seg

Mejora: 8x más rápido
"""

import multiprocessing as mp
from multiprocessing import Pool
from functools import partial
import pandas as pd
from typing import List, Dict, Optional
import logging
from tqdm import tqdm

logger = logging.getLogger(__name__)


def _analyze_ticker_worker(args):
    """
    Worker function para procesar un ticker
    
    Debe ser función top-level para poder ser pickleada por multiprocessing
    """
    ticker, date, market_context, data_cache, pattern_screener_class, data_provider_class = args
    
    try:
        # Recrear objetos en el worker (no se pueden pasar directamente)
        from datetime import timedelta
        
        # Obtener datos del cache
        start_date = date - timedelta(days=90)
        
        df = data_cache.get(
            ticker,
            start_date=start_date.strftime('%Y-%m-%d'),
            end_date=date.strftime('%Y-%m-%d')
        )
        
        if df is None or df.empty or len(df) < 30:
            return None
        
        # Verificar fecha correcta
        if df.index[-1].date() != date.date():
            return None
        
        # Crear screener en el worker
        data_provider = data_provider_class()
        pattern_screener = pattern_screener_class(data_provider)
        
        # Detectar patrones
        signal = pattern_screener.screen_stock(ticker, df, market_context)
        
        if signal and signal.action in ['BUY_STOP', 'MANUAL_WATCH']:
            # Calcular ATR
            high_low = df['High'] - df['Low']
            high_close = abs(df['High'] - df['Close'].shift())
            low_close = abs(df['Low'] - df['Close'].shift())
            
            ranges = pd.concat([high_low, high_close, low_close], axis=1)
            true_range = ranges.max(axis=1)
            atr = true_range.rolling(14).mean().iloc[-1] if len(true_range) > 14 else None
            
            return {
                'ticker': ticker,
                'date': date,
                'signal': signal,
                'current_price': df['Close'].iloc[-1],
                'volume': df['Volume'].iloc[-1],
                'atr': atr
            }
    
    except Exception as e:
        logger.debug(f"Error analyzing {ticker}: {e}")
        return None
    
    return None


class ParallelScanner:
    """
    Scanner que usa multiprocessing para procesar tickers en paralelo
    """
    
    def __init__(self, data_cache, n_workers: Optional[int] = None):
        """
        Args:
            data_cache: DataCache instance
            n_workers: Número de workers. Si None, usa CPU cores - 1
        """
        self.data_cache = data_cache
        
        if n_workers is None:
            # Dejar 1 core libre para el sistema
            self.n_workers = max(1, mp.cpu_count() - 1)
        else:
            self.n_workers = n_workers
        
        logger.info(f"🚀 ParallelScanner initialized with {self.n_workers} workers")
    
    def scan_universe(self, tickers: List[str], date, market_context, 
                     pattern_screener_class, data_provider_class) -> List[dict]:
        """
        Escanea múltiples tickers en paralelo
        
        Args:
            tickers: Lista de símbolos
            date: Fecha específica del backtest
            market_context: Contexto del mercado
            pattern_screener_class: Clase PatternScreener (no instance)
            data_provider_class: Clase MarketDataProvider (no instance)
            
        Returns:
            Lista de setups encontrados
        """
        logger.info(f"🔍 Scanning {len(tickers)} tickers with {self.n_workers} workers...")
        
        # Preparar argumentos para workers
        args_list = [
            (ticker, date, market_context, self.data_cache, 
             pattern_screener_class, data_provider_class)
            for ticker in tickers
        ]
        
        # Procesar en paralelo con progress bar
        setups = []
        
        with Pool(processes=self.n_workers) as pool:
            # imap_unordered es más eficiente que map
            results = list(tqdm(
                pool.imap_unordered(_analyze_ticker_worker, args_list),
                total=len(args_list),
                desc="Scanning",
                unit="ticker"
            ))
            
            # Filtrar None results
            setups = [r for r in results if r is not None]
        
        logger.info(f"✅ Found {len(setups)} setups")
        
        return setups


def estimate_speedup(n_tickers: int, n_days: int, 
                     avg_time_per_ticker: float = 2.0,
                     use_cache: bool = True,
                     use_parallel: bool = True,
                     n_workers: int = 8) -> dict:
    """
    Estima mejora de performance con cache y/o paralelización
    
    Args:
        n_tickers: Número de tickers
        n_days: Número de días
        avg_time_per_ticker: Tiempo promedio por ticker (segundos)
        use_cache: Si usa cache
        use_parallel: Si usa paralelización
        n_workers: Número de workers
        
    Returns:
        Dict con tiempos estimados y speedup
    """
    # Tiempo base (sin optimizaciones)
    base_time = n_tickers * n_days * avg_time_per_ticker
    
    # Con cache
    if use_cache:
        # Cache elimina re-descargas
        # Solo descarga 1 vez por ticker, luego es instantáneo
        download_time = n_tickers * avg_time_per_ticker  # Download inicial
        process_time = n_tickers * n_days * 0.01  # Processing rápido
        cache_time = download_time + process_time
    else:
        cache_time = base_time
    
    # Con paralelización
    if use_parallel:
        parallel_time = cache_time / n_workers
    else:
        parallel_time = cache_time
    
    # Con ambos
    optimized_time = parallel_time if use_cache else base_time / n_workers
    
    # Speedups
    cache_speedup = base_time / cache_time if use_cache else 1.0
    parallel_speedup = cache_time / parallel_time if use_parallel else 1.0
    total_speedup = base_time / optimized_time
    
    return {
        'base_time_sec': base_time,
        'base_time_str': _format_time(base_time),
        'cache_time_sec': cache_time,
        'cache_time_str': _format_time(cache_time),
        'parallel_time_sec': parallel_time,
        'parallel_time_str': _format_time(parallel_time),
        'optimized_time_sec': optimized_time,
        'optimized_time_str': _format_time(optimized_time),
        'cache_speedup': cache_speedup,
        'parallel_speedup': parallel_speedup,
        'total_speedup': total_speedup
    }


def _format_time(seconds: float) -> str:
    """Formatea segundos a string legible"""
    if seconds < 60:
        return f"{seconds:.1f} sec"
    elif seconds < 3600:
        return f"{seconds/60:.1f} min"
    else:
        return f"{seconds/3600:.1f} hours"


def print_performance_analysis(n_tickers: int = 200, n_days: int = 100):
    """
    Imprime análisis de performance con diferentes configuraciones
    """
    print("\n" + "="*80)
    print("📊 PERFORMANCE ANALYSIS")
    print("="*80)
    print(f"Configuration: {n_tickers} tickers x {n_days} days")
    print()
    
    configs = [
        ("No optimization", False, False, 1),
        ("Cache only", True, False, 1),
        ("Parallel only (4 cores)", False, True, 4),
        ("Parallel only (8 cores)", False, True, 8),
        ("Cache + Parallel (4 cores)", True, True, 4),
        ("Cache + Parallel (8 cores)", True, True, 8),
    ]
    
    print(f"{'Configuration':<30} {'Time':<15} {'Speedup':>10}")
    print("-"*80)
    
    for name, use_cache, use_parallel, n_workers in configs:
        result = estimate_speedup(
            n_tickers, n_days,
            use_cache=use_cache,
            use_parallel=use_parallel,
            n_workers=n_workers
        )
        
        print(f"{name:<30} {result['optimized_time_str']:<15} {result['total_speedup']:>9.1f}x")
    
    print("="*80)
    
    # Mostrar recomendación
    best = estimate_speedup(n_tickers, n_days, use_cache=True, use_parallel=True, n_workers=8)
    print(f"\n✅ RECOMMENDED: Cache + Parallel (8 cores)")
    print(f"   Time: {best['optimized_time_str']}")
    print(f"   Speedup: {best['total_speedup']:.0f}x faster")
    print()


if __name__ == "__main__":
    # Demo del análisis de performance
    print_performance_analysis(n_tickers=200, n_days=100)
