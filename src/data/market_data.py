"""
Market Data Provider - Supports both Yahoo Finance and OpenBB
Handles intraday and daily data retrieval with caching
"""
import yfinance as yf
from openbb import obb
import pandas as pd
from datetime import datetime, timedelta
from pathlib import Path
import pickle
import logging
from config.settings import DATA_SOURCE, OPENBB_PROVIDER

logger = logging.getLogger(__name__)


class MarketDataProvider:
    def __init__(self, cache_dir: Path = None):
        self.cache_dir = cache_dir or Path("./data/cache")
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.data_source = DATA_SOURCE

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

    def get_daily_data(self, symbol: str, period: str = "1y") -> pd.DataFrame:
        """
        Get daily data for base analysis and ATH detection
        period: 1d, 5d, 1mo, 3mo, 6mo, 1y, 2y, 5y, 10y, ytd, max
        """
        cache_file = self.cache_dir / f"{symbol}_daily.pkl"

        # Check cache (valid for 1 day)
        if cache_file.exists():
            cache_time = datetime.fromtimestamp(cache_file.stat().st_mtime)
            if datetime.now() - cache_time < timedelta(hours=24):
                logger.info(f"Loading {symbol} daily data from cache")
                return pickle.load(open(cache_file, "rb"))

        if self.data_source == "openbb":
            logger.info(f"Fetching {symbol} daily data from OpenBB")
            df = self._get_daily_data_openbb(symbol, period)
        else:
            logger.info(f"Fetching {symbol} daily data from Yahoo Finance")
            df = self._get_daily_data_yfinance(symbol, period)

        if df.empty:
            logger.warning(f"No daily data found for {symbol}")
            return pd.DataFrame()

        # Cache the data
        pickle.dump(df, open(cache_file, "wb"))

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
