#!/usr/bin/env python3
"""
Indicator Cache System - Cache de indicadores técnicos

Evita recalcular indicadores en backtests chunked o repetitivos.
Almacena en disco los indicadores pre-calculados para reutilizar.

USO:
    cache = IndicatorCache()
    sma20 = cache.get_or_compute(ticker, 'sma20', close, window=20)
"""

import pandas as pd
import numpy as np
import os
import pickle
from pathlib import Path
from typing import Optional, Dict, Any, Tuple
import hashlib
import logging

logger = logging.getLogger(__name__)


class IndicatorCache:
    """
    Cache de indicadores técnicos con persistencia en disco.
    """

    def __init__(self, cache_dir: str = "outputs/indicator_cache"):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        # Cache en memoria para acceso rápido
        self._memory_cache: Dict[str, pd.DataFrame] = {}

        logger.info(f"[U+1F4E6] IndicatorCache inicializado en: {self.cache_dir}")

    def _get_cache_key(
        self, ticker: str, indicator_name: str, data_hash: str, **params
    ) -> str:
        """Genera clave única para el indicador."""
        param_str = "_".join([f"{k}={v}" for k, v in sorted(params.items())])
        return f"{ticker}_{indicator_name}_{data_hash}_{param_str}.pkl"

    def _get_data_hash(self, data: pd.DataFrame) -> str:
        """Calcula hash de los datos para detectar cambios."""
        # Usar solo el índice y el tamaño para velocidad
        idx_str = str(data.index.tz_localize(None))[:100]
        size = data.shape
        hash_input = f"{idx_str}_{size}"
        return hashlib.md5(hash_input.encode()).hexdigest()[:12]

    def get_or_compute(
        self, ticker: str, indicator_name: str, data: pd.DataFrame, compute_fn, **params
    ) -> pd.DataFrame:
        """
        Obtiene indicador del cache o lo calcula.

        Args:
            ticker: Símbolo del activo
            indicator_name: Nombre del indicador (sma20, ema10, etc.)
            data: DataFrame con los datos de entrada (close, high, low, etc.)
            compute_fn: Función que calcula el indicador
            **params: Parámetros del indicador (window, span, etc.)

        Returns:
            DataFrame con el indicador calculado
        """
        data_hash = self._get_data_hash(data)
        cache_key = self._get_cache_key(ticker, indicator_name, data_hash, **params)
        cache_path = self.cache_dir / cache_key

        # Verificar cache en memoria primero
        mem_key = f"{ticker}_{indicator_name}"
        if mem_key in self._memory_cache:
            cached_df = self._memory_cache[mem_key]
            if self._validate_cache(cached_df, data.index):
                logger.debug(f"[U+1F4BE] Cache hit (memoria): {ticker} {indicator_name}")
                return cached_df

        # Verificar cache en disco
        if cache_path.exists():
            try:
                with open(cache_path, "rb") as f:
                    cached_df = pickle.load(f)

                # Validar que el cache sea compatible
                if self._validate_cache(cached_df, data.index):
                    logger.info(f"[U+1F4BE] Cache hit (disco): {ticker} {indicator_name}")

                    # Guardar en memoria
                    self._memory_cache[mem_key] = cached_df
                    return cached_df
                else:
                    logger.debug(
                        f"[U+1F5D1] Cache inválido, recalcular: {ticker} {indicator_name}"
                    )
                    cache_path.unlink()
            except Exception as e:
                logger.warning(f"[WARN] Error leyendo cache: {e}")

        # Calcular indicador
        logger.debug(f"[U+1F9EE] Calculando: {ticker} {indicator_name}")
        result = compute_fn(data, **params)

        # Guardar en cache
        try:
            with open(cache_path, "wb") as f:
                pickle.dump(result, f)

            # Guardar en memoria
            self._memory_cache[mem_key] = result
            logger.debug(f"[U+1F4BE] Guardado en cache: {ticker} {indicator_name}")
        except Exception as e:
            logger.warning(f"[WARN] Error guardando cache: {e}")

        return result

    def _validate_cache(self, cached_df: pd.DataFrame, target_index: pd.Index) -> bool:
        """
        Valida que el cache sea compatible con los datos actuales.

        Returns:
            True si el cache es válido, False si hay que recalcular
        """
        # Verificar que el cache tiene el mismo o más índice que los datos
        if cached_df.index[0] > target_index[0]:
            return False

        # Verificar que el cache cubre el rango necesario
        if cached_df.index[-1] < target_index[-1]:
            return False

        return True

    def get_cached_range(
        self,
        ticker: str,
        indicator_name: str,
        start_date: pd.Timestamp,
        end_date: pd.Timestamp,
        **params,
    ) -> Optional[pd.DataFrame]:
        """
        Obtiene datos del cache dentro de un rango específico.

        Returns:
            DataFrame filtrado o None si no existe
        """
        # Buscar cache que cubra el rango
        for key, cached_df in self._memory_cache.items():
            if f"{ticker}_{indicator_name}" in key:
                mask = (cached_df.index >= start_date) & (cached_df.index <= end_date)
                if mask.any():
                    return cached_df[mask]

        return None

    def clear_ticker(self, ticker: str):
        """Limpia cache para un ticker específico."""
        # Limpiar memoria
        keys_to_delete = [k for k in self._memory_cache if k.startswith(ticker)]
        for key in keys_to_delete:
            del self._memory_cache[key]

        # Limpiar disco
        for file_path in self.cache_dir.glob(f"{ticker}_*.pkl"):
            try:
                file_path.unlink()
                logger.info(f"[U+1F5D1] Cache limpiado: {file_path.name}")
            except Exception as e:
                logger.warning(f"[WARN] Error borrando cache: {e}")

    def clear_all(self):
        """Limpia todo el cache."""
        self._memory_cache.clear()

        for file_path in self.cache_dir.glob("*.pkl"):
            try:
                file_path.unlink()
            except Exception as e:
                logger.warning(f"[WARN] Error borrando cache: {e}")

        logger.info("[U+1F5D1] Todo el cache ha sido limpiado")

    def get_cache_stats(self) -> Dict[str, Any]:
        """Devuelve estadísticas del cache."""
        cache_files = list(self.cache_dir.glob("*.pkl"))
        total_size = sum(f.stat().st_size for f in cache_files) / (1024**2)  # MB

        return {
            "memory_entries": len(self._memory_cache),
            "disk_files": len(cache_files),
            "disk_size_mb": total_size,
            "cache_dir": str(self.cache_dir),
        }


class PrecomputedIndicators:
    """
    Indicadores pre-calculados para backtests chunked.
    """

    @staticmethod
    def sma(data: pd.DataFrame, window: int = 20) -> pd.Series:
        """Simple Moving Average."""
        return data["close"].rolling(window=window, min_periods=1).mean()

    @staticmethod
    def ema(data: pd.DataFrame, span: int = 10) -> pd.Series:
        """Exponential Moving Average."""
        return data["close"].ewm(span=span, adjust=False).mean()

    @staticmethod
    def atr(data: pd.DataFrame, period: int = 14) -> pd.Series:
        """Average True Range."""
        high = data["high"]
        low = data["low"]
        close = data["close"]

        tr1 = high - low
        tr2 = (high - close.shift()).abs()
        tr3 = (low - close.shift()).abs()

        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        return tr.rolling(period, min_periods=1).mean()

    @staticmethod
    def adr(data: pd.DataFrame, period: int = 20) -> pd.Series:
        """Average Daily Range (porcentaje)."""
        high = data["high"]
        low = data["low"]
        close = data["close"]

        hl = (high - low) / close * 100
        return hl.rolling(period, min_periods=1).mean()

    @staticmethod
    def rvol(data: pd.DataFrame, window: int = 20) -> pd.Series:
        """Relative Volume."""
        volume = data["volume"]
        avg_vol = volume.rolling(window=window, min_periods=1).mean()
        return volume / avg_vol

    @staticmethod
    def consolidation_days(
        data: pd.DataFrame, bb_period: int = 20, bb_std: float = 1.0
    ) -> pd.Series:
        """Días en consolidación (dentro de Bollinger Bands)."""
        close = data["close"]
        sma = close.rolling(bb_period, min_periods=1).mean()
        std = close.rolling(bb_period, min_periods=1).std()

        upper = sma + (bb_std * std)
        lower = sma - (bb_std * std)

        inside_bb = (close >= lower) & (close <= upper)
        return inside_bb.rolling(20, min_periods=1).sum()

    @staticmethod
    def dist_sma20(data: pd.DataFrame) -> pd.Series:
        """Distancia porcentual desde SMA20."""
        sma20 = data["close"].rolling(20, min_periods=1).mean()
        return (data["close"] - sma20) / sma20 * 100


if __name__ == "__main__":
    # Test del cache
    logging.basicConfig(level=logging.INFO)

    # Datos de prueba
    dates = pd.date_range("2020-01-01", "2024-12-31", freq="D")
    data = pd.DataFrame(
        {
            "close": np.random.randn(len(dates)).cumsum() + 100,
            "high": np.random.randn(len(dates)).cumsum() + 105,
            "low": np.random.randn(len(dates)).cumsum() + 95,
            "volume": np.random.randint(1000000, 10000000, len(dates)),
        },
        index=dates,
    )

    # Crear cache
    cache = IndicatorCache()

    # Calcular SMA20 (primera vez)
    print("Primer cálculo de SMA20...")
    sma20 = cache.get_or_compute(
        "TEST", "sma20", data, PrecomputedIndicators.sma, window=20
    )
    print(f"[OK] SMA20 shape: {sma20.shape}")

    # Calcular SMA20 (debería venir del cache)
    print("\nSegundo cálculo de SMA20 (del cache)...")
    sma20_cached = cache.get_or_compute(
        "TEST", "sma20", data, PrecomputedIndicators.sma, window=20
    )
    print(f"[OK] SMA20 (cached) shape: {sma20_cached.shape}")

    # Estadísticas del cache
    print(f"\n[U+1F4CA] Cache stats: {cache.get_cache_stats()}")
