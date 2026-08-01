"""
Market Data Provider - Supports both Yahoo Finance and OpenBB
Handles intraday and daily data retrieval with caching
"""
import logging
import pickle
import time
import warnings
from collections import OrderedDict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import pandas as pd
import requests
import yfinance as yf
from openbb import obb

from config.settings import DATA_SOURCE, OPENBB_PROVIDER
from src.data.ticker_cache import TickerCache

logger = logging.getLogger(__name__)

# Intentos máximos de descarga de earnings antes de rendirse (retorno vacío).
_EARNINGS_MAX_ATTEMPTS = 3
# Backoff en segundos entre reintentos de descarga de earnings.
_EARNINGS_RETRY_BACKOFF = 1.0
# Máximo de símbolos cacheados en memoria (éxitos y negativos) por proceso.
_EARNINGS_CACHE_MAX = 1024
# User-Agent realista para el backend requests (sin impersonación TLS).
_EARNINGS_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)


class MarketDataProvider:
    def __init__(self, cache_dir: Path = None):
        self.cache_dir = cache_dir or Path("./data/cache")
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.data_source = DATA_SOURCE
        self.sqlite_cache = TickerCache()
        # Sesión HTTP compartida del backend requests para earnings (evita curl_cffi).
        self._earnings_session: Optional[requests.Session] = None
        # Cache en memoria acotado (éxitos y negativos) para evitar re-descargas.
        self._earnings_cache: "OrderedDict[str, pd.DatetimeIndex]" = OrderedDict()

    def get_intraday_data(self, symbol: str, interval: str = "5m", days: int = 5) -> pd.DataFrame:
        """
        Get intraday data for VWAP calculations
        interval: 1m, 2m, 5m, 15m, 30m, 60m, 90m
        """
        cache_file = self.cache_dir / f"{symbol}_{interval}_intraday.pkl"

        # Check cache (valid for 5 minutes)
        if cache_file.exists():
            cache_time = datetime.fromtimestamp(cache_file.stat().st_mtime)
            if datetime.now() - cache_time < timedelta(minutes=5):
                logger.info(f"Loading {symbol} intraday data from cache")
                return pickle.load(open(cache_file, "rb"))

        if self.data_source == "openbb":
            logger.info(f"Fetching {symbol} intraday data from OpenBB")
            df = self._get_intraday_data_openbb(symbol, interval, days)
            
            # Fallback to YFinance if OpenBB fails or returns empty data
            if df.empty:
                logger.warning(f"OpenBB returned no data for {symbol}, falling back to Yahoo Finance")
                df = self._get_intraday_data_yfinance(symbol, interval, days)
        else:
            logger.info(f"Fetching {symbol} intraday data from Yahoo Finance")
            df = self._get_intraday_data_yfinance(symbol, interval, days)

        if df.empty:
            logger.warning(f"No intraday data found for {symbol}")
            return pd.DataFrame()

        # Calculate VWAP if not already present
        if 'VWAP' not in df.columns:
            if df['Volume'].sum() > 0:  # Solo calcular VWAP si hay volumen
                df['VWAP'] = (df['Volume'] * (df['High'] + df['Low'] + df['Close']) / 3).cumsum() / df['Volume'].cumsum()
            else:  # Si no hay volumen, usar precio promedio simple
                df['VWAP'] = (df['High'] + df['Low'] + df['Close']) / 3

        # Cache the data
        pickle.dump(df, open(cache_file, "wb"))

        return df

    def _get_intraday_data_openbb(self, symbol: str, interval: str, days: int) -> pd.DataFrame:
        """Get intraday data using OpenBB"""
        try:
            from datetime import datetime, timedelta
            end_date = datetime.now().strftime('%Y-%m-%d')
            start_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')

            result = obb.equity.price.historical(
                symbol=symbol,
                start_date=start_date,
                end_date=end_date,
                interval=interval,
                provider=OPENBB_PROVIDER
            )

            if result and hasattr(result, 'to_df'):
                df = result.to_df()
                if not df.empty:
                    # Ensure datetime index
                    df.index = pd.to_datetime(df.index)

                    # OpenBB puede usar diferentes nombres de columnas
                    # Aseguramos que las columnas tengan los nombres correctos
                    column_mapping = {
                        'open': 'Open',
                        'high': 'High',
                        'low': 'Low',
                        'close': 'Close',
                        'volume': 'Volume',
                        'adj_close': 'Adj Close'
                    }

                    # Renombrar columnas si es necesario
                    df_renamed = df.copy()
                    for old_col, new_col in column_mapping.items():
                        if old_col in df.columns:
                            df_renamed = df_renamed.rename(columns={old_col: new_col})

                    # Si no hay volumen, crear una columna de volumen con valores por defecto
                    if 'Volume' not in df_renamed.columns:
                        df_renamed['Volume'] = 0  # Valor por defecto si no hay volumen

                    return df_renamed
        except Exception as e:
            logger.error(f"Error getting intraday data from OpenBB for {symbol}: {str(e)}")

        return pd.DataFrame()

    def _get_intraday_data_yfinance(self, symbol: str, interval: str, days: int) -> pd.DataFrame:
        """Get intraday data using Yahoo Finance"""
        ticker = yf.Ticker(symbol)

        # Yahoo Finance allows up to 60 days for intraday data
        period = f"{days}d"
        df = ticker.history(period=period, interval=interval)

        return df

    def get_daily_data(self, symbol: str, period: str = "1y", start_date: str = None, end_date: str = None, offline: bool = False) -> pd.DataFrame:
        """
        Get daily data for base analysis and ATH detection
        period: 1d, 5d, 1mo, 3mo, 6mo, 1y, 2y, 5y, 10y, ytd, max
        """
        # If dates are provided, use SQLite cache directly
        if start_date and end_date:
            df = self.sqlite_cache.get_ohlcv(symbol, start_date, end_date, offline=offline)
            if df is not None and not df.empty:
                return df
            if offline:
                return pd.DataFrame()

        # Otherwise use period-based logic
        cache_file = self.cache_dir / f"{symbol}_daily.pkl"

        # Check legacy cache (valid for 1 day)
        if cache_file.exists():
            cache_time = datetime.fromtimestamp(cache_file.stat().st_mtime)
            # If offline, ignore expiration time
            if offline or (datetime.now() - cache_time < timedelta(hours=24)):
                if not offline:
                    logger.info(f"Loading {symbol} daily data from legacy cache")
                df = pickle.load(open(cache_file, "rb"))
                # Also save to SQLite if it's there
                if not df.empty:
                    # Update SQLite in background (simplified)
                    # For now just return
                    return df
        
        if offline:
            return pd.DataFrame()

        if self.data_source == "openbb":
            logger.info(f"Fetching {symbol} daily data from OpenBB")
            df = self._get_daily_data_openbb(symbol, period)
        else:
            logger.info(f"Fetching {symbol} daily data from Yahoo Finance")
            df = self._get_daily_data_yfinance(symbol, period)

        if df.empty:
            logger.warning(f"No daily data found for {symbol}")
            return pd.DataFrame()

        # Cache the data in legacy format
        pickle.dump(df, open(cache_file, "wb"))
        
        # ALSO Cache in SQLite
        try:
            # Calcular métricas faltantes para la DB
            if 'dollar_volume' not in df.columns:
                df['dollar_volume'] = df['Close'] * df['Volume']
            if 'rolling_dollar_vol_20' not in df.columns:
                df['rolling_dollar_vol_20'] = df['dollar_volume'].rolling(window=20, min_periods=1).mean()

            # Limpiar filas inválidas (fix para Open=0)
            df = df.dropna(subset=["Open", "Close"])
            if not df.empty:
                df = df[(df["Open"] > 0) & (df["Close"] > 0)]

            for date, row in df.iterrows():
                # Safe extraction
                d_vol = row['dollar_volume'] if pd.notna(row['dollar_volume']) else 0.0
                rd_vol = row['rolling_dollar_vol_20'] if pd.notna(row['rolling_dollar_vol_20']) else 0.0
                
                self.sqlite_cache.conn.execute('''
                    INSERT OR REPLACE INTO ohlcv_cache 
                    (ticker, date, open, high, low, close, volume, dollar_volume, rolling_dollar_vol_20)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    symbol,
                    date.strftime('%Y-%m-%d'),
                    float(row['Open']),
                    float(row['High']),
                    float(row['Low']),
                    float(row['Close']),
                    int(row['Volume']),
                    float(d_vol),
                    float(rd_vol)
                ))
            self.sqlite_cache.conn.commit()
        except Exception as e:
            logger.error(f"Error saving {symbol} to SQLite cache: {e}")

        return df

    def _get_daily_data_openbb(self, symbol: str, period: str) -> pd.DataFrame:
        """Get daily data using OpenBB"""
        try:
            from datetime import datetime
            end_date = datetime.now().strftime('%Y-%m-%d')

            # Convert period to start date
            if period == "1y":
                start_date = (datetime.now() - timedelta(days=365)).strftime('%Y-%m-%d')
            elif period == "6mo":
                start_date = (datetime.now() - timedelta(days=180)).strftime('%Y-%m-%d')
            elif period == "3mo":
                start_date = (datetime.now() - timedelta(days=90)).strftime('%Y-%m-%d')
            elif period == "1mo":
                start_date = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
            elif period == "max":
                start_date = (datetime.now() - timedelta(days=365*20)).strftime('%Y-%m-%d') # 20 years
            else:
                start_date = (datetime.now() - timedelta(days=365)).strftime('%Y-%m-%d')  # default to 1 year

            result = obb.equity.price.historical(
                symbol=symbol,
                start_date=start_date,
                end_date=end_date,
                interval="1d",
                provider=OPENBB_PROVIDER
            )

            if result and hasattr(result, 'to_df'):
                df = result.to_df()
                if not df.empty:
                    # Ensure datetime index
                    df.index = pd.to_datetime(df.index)

                    # OpenBB puede usar diferentes nombres de columnas
                    # Aseguramos que las columnas tengan los nombres correctos
                    column_mapping = {
                        'open': 'Open',
                        'high': 'High',
                        'low': 'Low',
                        'close': 'Close',
                        'volume': 'Volume',
                        'adj_close': 'Adj Close'
                    }

                    # Renombrar columnas si es necesario
                    df_renamed = df.copy()
                    for old_col, new_col in column_mapping.items():
                        if old_col in df.columns:
                            df_renamed = df_renamed.rename(columns={old_col: new_col})

                    # Si no hay volumen, crear una columna de volumen con valores por defecto
                    if 'Volume' not in df_renamed.columns:
                        df_renamed['Volume'] = 0  # Valor por defecto si no hay volumen

                    return df_renamed
        except Exception as e:
            logger.error(f"Error getting daily data from OpenBB for {symbol}: {str(e)}")

        return pd.DataFrame()

    def _get_daily_data_yfinance(self, symbol: str, period: str) -> pd.DataFrame:
        """Get daily data using Yahoo Finance"""
        ticker = yf.Ticker(symbol)
        df = ticker.history(period=period)

        return df

    def get_current_price(self, symbol: str) -> dict:
        """Get current price and session info"""
        if self.data_source == "openbb":
            return self._get_current_price_openbb(symbol)
        else:
            return self._get_current_price_yfinance(symbol)

    def _get_current_price_openbb(self, symbol: str) -> dict:
        """Get current price using OpenBB"""
        try:
            from datetime import datetime
            end_date = datetime.now().strftime('%Y-%m-%d')
            start_date = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')

            result = obb.equity.price.historical(
                symbol=symbol,
                start_date=start_date,
                end_date=end_date,
                interval="1d",
                provider=OPENBB_PROVIDER
            )

            if result and hasattr(result, 'to_df'):
                df = result.to_df()
                if not df.empty:
                    latest = df.iloc[-1]
                    return {
                        'symbol': symbol,
                        'current_price': latest['close'],
                        'open': latest['open'],
                        'high': latest['high'],
                        'low': latest['low'],
                        'volume': latest['volume'],
                        'previous_close': df.iloc[-2]['close'] if len(df) > 1 else latest['close']
                    }
        except Exception as e:
            logger.error(f"Error getting current price from OpenBB for {symbol}: {str(e)}")

        return {
            'symbol': symbol,
            'current_price': 0,
            'open': 0,
            'high': 0,
            'low': 0,
            'volume': 0,
            'previous_close': 0
        }

    def _get_current_price_yfinance(self, symbol: str) -> dict:
        """Get current price using Yahoo Finance"""
        ticker = yf.Ticker(symbol)
        info = ticker.info

        return {
            'symbol': symbol,
            'current_price': info.get('currentPrice', info.get('regularMarketPrice', 0)),
            'open': info.get('regularMarketOpen', 0),
            'high': info.get('dayHigh', 0),
            'low': info.get('dayLow', 0),
            'volume': info.get('volume', 0),
            'previous_close': info.get('previousClose', 0)
        }

    def calculate_adr(self, symbol: str, period: int = 20) -> float:
        """Calculate Average Daily Range for stop placement"""
        df = self.get_daily_data(symbol, period="3mo")

        if df.empty or len(df) < period:
            return 0.0

        df['Range'] = df['High'] - df['Low']
        adr = df['Range'].tail(period).mean()

        return adr

    def get_earnings_dates(self, symbol: str) -> pd.DatetimeIndex:
        """
        Obtiene fechas de earnings (históricas y futuras) para un símbolo.

        Prioridad de fuentes: cache en memoria -> cache SQLite -> descarga
        vía yfinance. Ante cualquier fallo transitorio retorna un
        DatetimeIndex vacío (nunca propaga excepciones) y registra el
        símbolo en un cache negativo acotado para evitar re-descargas
        dentro del mismo proceso.

        Args:
            symbol: Ticker del símbolo a consultar.

        Returns:
            DatetimeIndex ordenado con las fechas de earnings, o vacío si
            no hay datos o si la descarga falla.
        """
        if symbol in self._earnings_cache:
            return self._earnings_cache[symbol]

        # 1. Check SQLite Cache
        try:
            cached_earnings = self.sqlite_cache.get_earnings_history(symbol)
            if cached_earnings is not None and not cached_earnings.empty:
                dates = pd.DatetimeIndex(pd.to_datetime(cached_earnings["report_date"]).sort_values())
                self._cache_earnings_result(symbol, dates)
                return dates
        except Exception as e:
            logger.warning(f"Error reading earnings from SQLite for {symbol}: {e}")

        # 2. Download via YFinance (Fallback) con reintentos acotados
        earnings = self._download_earnings_dates(symbol)

        if earnings is not None and not earnings.empty:
            # Save to SQLite for future use
            df_to_save = pd.DataFrame()
            df_to_save["report_date"] = earnings.index
            df_to_save["eps_estimate"] = (
                earnings["EPS Estimate"].values if "EPS Estimate" in earnings.columns else None
            )
            df_to_save["eps_actual"] = (
                earnings["Reported EPS"].values if "Reported EPS" in earnings.columns else None
            )
            df_to_save["surprise_pct"] = (
                earnings["Surprise(%)"].values if "Surprise(%)" in earnings.columns else None
            )

            try:
                self.sqlite_cache.save_earnings(symbol, df_to_save)
            except Exception as e:
                logger.debug(f"Error saving earnings to SQLite for {symbol}: {e}")

            # Return dates
            dates = pd.to_datetime(earnings.index).tz_localize(None).sort_values()
        else:
            dates = pd.DatetimeIndex([])

        self._cache_earnings_result(symbol, dates)
        return dates

    def _get_earnings_session(self) -> requests.Session:
        """
        Retorna la sesión HTTP compartida para descargas de earnings.

        Usa el backend `requests` (pila pura de Python, sin curl_cffi) para
        eliminar la posibilidad de fallos nativos de TLS que matarían el
        proceso sin traceback. yfinance ya aplica `timeout=30` por request.

        Returns:
            Sesión `requests.Session` con User-Agent realista.
        """
        if self._earnings_session is None:
            session = requests.Session()
            session.headers.update({"User-Agent": _EARNINGS_USER_AGENT})
            self._earnings_session = session
        return self._earnings_session

    def _download_earnings_dates(self, symbol: str) -> Optional[pd.DataFrame]:
        """
        Descarga fechas de earnings vía yfinance con reintentos acotados.

        Todo error (red, timeout, parseo) se captura y se traduce en un
        retorno vacío; jamás se propaga una excepción que pueda matar al
        proceso ni un fallo nativo (el backend requests no usa curl_cffi).

        Args:
            symbol: Ticker del símbolo a consultar.

        Returns:
            DataFrame de yfinance con fechas de earnings, o None si falla.
        """
        last_error: Optional[Exception] = None
        for attempt in range(_EARNINGS_MAX_ATTEMPTS):
            try:
                with warnings.catch_warnings():
                    warnings.filterwarnings("ignore")  # Suprimir warnings de yfinance
                    ticker = yf.Ticker(symbol, session=self._get_earnings_session())
                    return ticker.earnings_dates
            except Exception as e:
                last_error = e
                if attempt < _EARNINGS_MAX_ATTEMPTS - 1:
                    time.sleep(_EARNINGS_RETRY_BACKOFF)
        if last_error is not None:
            logger.debug(f"Earnings download failed for {symbol}: {last_error}")
        return None

    def _cache_earnings_result(self, symbol: str, dates: pd.DatetimeIndex) -> None:
        """
        Cachea el resultado de earnings en un diccionario acotado.

        Limita el crecimiento de memoria a `_EARNINGS_CACHE_MAX` entradas
        desalojando la entrada más antigua (FIFO).

        Args:
            symbol: Ticker del símbolo.
            dates: DatetimeIndex con las fechas (puede ser vacío).
        """
        if len(self._earnings_cache) >= _EARNINGS_CACHE_MAX:
            self._earnings_cache.popitem(last=False)
        self._earnings_cache[symbol] = dates
