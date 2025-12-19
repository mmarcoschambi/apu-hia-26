"""
Market Data Provider - Yahoo Finance
Handles intraday and daily data retrieval with caching
"""
import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta
from pathlib import Path
import pickle
import logging

logger = logging.getLogger(__name__)


class MarketDataProvider:
    def __init__(self, cache_dir: Path = None):
        self.cache_dir = cache_dir or Path("./data/cache")
        self.cache_dir.mkdir(parents=True, exist_ok=True)
    
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
        
        logger.info(f"Fetching {symbol} intraday data from Yahoo Finance")
        ticker = yf.Ticker(symbol)
        
        # Yahoo Finance allows up to 60 days for intraday data
        period = f"{days}d"
        df = ticker.history(period=period, interval=interval)
        
        if df.empty:
            logger.warning(f"No intraday data found for {symbol}")
            return pd.DataFrame()
        
        # Calculate VWAP
        df['VWAP'] = (df['Volume'] * (df['High'] + df['Low'] + df['Close']) / 3).cumsum() / df['Volume'].cumsum()
        
        # Cache the data
        pickle.dump(df, open(cache_file, "wb"))
        
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
        
        logger.info(f"Fetching {symbol} daily data from Yahoo Finance")
        ticker = yf.Ticker(symbol)
        df = ticker.history(period=period)
        
        if df.empty:
            logger.warning(f"No daily data found for {symbol}")
            return pd.DataFrame()
        
        # Cache the data
        pickle.dump(df, open(cache_file, "wb"))
        
        return df
    
    def get_current_price(self, symbol: str) -> dict:
        """Get current price and session info"""
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
