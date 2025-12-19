"""
System Configuration - Triad Momentum Protocol
"""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

# Risk Management
RISK_PER_TRADE = 0.005  # 0.5% standard
RISK_PER_TRADE_REDUCED = 0.0025  # 0.25% for Camino 2

# Entry Logic Thresholds
BLUE_SKY_OFFSET = 0.05  # Buy Stop offset for Camino 1
AVWAP_TOLERANCE = 0.02  # 2% tolerance for AVWAP convergence
GAP_DOWN_THRESHOLD = -0.01  # -1% for market weakness detection

# Timeframes
INTRADAY_TIMEFRAME = "5m"  # M5 for VWAP reclaim detection
POSITION_TIMEFRAME = "1d"  # Daily for base analysis

# Data Source Configuration
DATA_SOURCE = "openbb"  # Options: "yfinance", "openbb"
OPENBB_PROVIDER = "yfinance"  # Provider to use with OpenBB (yfinance, intrinio, etc.)

# Data
CACHE_DIR = BASE_DIR / "data" / "cache"
LOG_DIR = BASE_DIR / "logs"

# Market Indices
MARKET_INDICES = ["SPY", "QQQ"]
