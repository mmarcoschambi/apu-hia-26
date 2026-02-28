"""
Sector Rotation Filter - Top-Down Market Analysis
--------------------------------------------------
Implements institutional-grade sector strength filtering.

Trading Rule: Only trade stocks in sectors showing relative strength vs SPY.

Sector ETFs (SPDR Select Sector):
- XLK: Technology
- XLF: Financials  
- XLV: Healthcare
- XLE: Energy
- XLY: Consumer Discretionary
- XLP: Consumer Staples
- XLI: Industrials
- XLB: Materials
- XLRE: Real Estate
- XLU: Utilities
- XLC: Communication Services
"""

import pandas as pd
import numpy as np
import yfinance as yf
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

# Sector mapping (ticker → sector ETF)
SECTOR_MAP = {
    # Technology
    'AAPL': 'XLK', 'MSFT': 'XLK', 'NVDA': 'XLK', 'GOOGL': 'XLK', 'META': 'XLK',
    'TSLA': 'XLK', 'AMD': 'XLK', 'INTC': 'XLK', 'CRM': 'XLK', 'AVGO': 'XLK',
    'ORCL': 'XLK', 'ADBE': 'XLK', 'CSCO': 'XLK', 'ACN': 'XLK', 'QCOM': 'XLK',
    
    # Financials
    'JPM': 'XLF', 'BAC': 'XLF', 'WFC': 'XLF', 'GS': 'XLF', 'MS': 'XLF',
    'C': 'XLF', 'SCHW': 'XLF', 'BLK': 'XLF', 'AXP': 'XLF', 'USB': 'XLF',
    
    # Healthcare
    'UNH': 'XLV', 'JNJ': 'XLV', 'PFE': 'XLV', 'ABBV': 'XLV', 'LLY': 'XLV',
    'MRK': 'XLV', 'TMO': 'XLV', 'ABT': 'XLV', 'DHR': 'XLV', 'CVS': 'XLV',
    
    # Consumer Discretionary
    'AMZN': 'XLY', 'HD': 'XLY', 'NKE': 'XLY', 'MCD': 'XLY', 'SBUX': 'XLY',
    'TGT': 'XLY', 'LOW': 'XLY', 'DIS': 'XLY', 'BKNG': 'XLY', 'CMG': 'XLY',
    
    # Energy
    'XOM': 'XLE', 'CVX': 'XLE', 'COP': 'XLE', 'SLB': 'XLE', 'EOG': 'XLE',
    
    # Communication Services
    'NFLX': 'XLC', 'GOOG': 'XLC', 'T': 'XLC', 'VZ': 'XLC', 'CMCSA': 'XLC',
    
    # Industrials
    'BA': 'XLI', 'CAT': 'XLI', 'GE': 'XLI', 'HON': 'XLI', 'UPS': 'XLI',
    
    # Consumer Staples
    'PG': 'XLP', 'KO': 'XLP', 'PEP': 'XLP', 'WMT': 'XLP', 'COST': 'XLP',
    
    # Materials
    'LIN': 'XLB', 'APD': 'XLB', 'ECL': 'XLB', 'DD': 'XLB', 'NEM': 'XLB',
    
    # Utilities
    'NEE': 'XLU', 'DUK': 'XLU', 'SO': 'XLU', 'D': 'XLU', 'AEP': 'XLU',
    
    # Real Estate
    'PLD': 'XLRE', 'AMT': 'XLRE', 'CCI': 'XLRE', 'EQIX': 'XLRE', 'PSA': 'XLRE'
}

SECTOR_ETFS = ['XLK', 'XLF', 'XLV', 'XLE', 'XLY', 'XLP', 'XLI', 'XLB', 'XLRE', 'XLU', 'XLC']


class SectorRotationAnalyzer:
    """
    Analyzes sector strength relative to SPY for rotation detection.
    """
    
    def __init__(self, start_date: str, end_date: str, cache_dir: str = '.cache/sectors'):
        self.start_date = pd.to_datetime(start_date)
        self.end_date = pd.to_datetime(end_date)
        self.cache_dir = cache_dir
        
        self.sector_data: Dict[str, pd.DataFrame] = {}
        self.spy_data: pd.DataFrame = None
        self.sector_strength: pd.DataFrame = None  # Daily sector rankings (simple method)
        self.composite_scores: pd.DataFrame = None  # Pre-calculated composite scores (advanced method)
        
    def load_sector_data(self) -> bool:
        """
        Load price data for all sector ETFs and SPY.
        Returns True if successful.
        """
        logger.info("📊 Loading sector ETF data...")
        
        try:
            # Load SPY
            spy = yf.download('SPY', start=self.start_date, end=self.end_date, progress=False)
            if spy.empty:
                logger.error("Failed to load SPY data")
                return False
            
            # Handle MultiIndex columns from yfinance
            if isinstance(spy.columns, pd.MultiIndex):
                spy.columns = spy.columns.get_level_values(0)
            
            self.spy_data = spy
            
            # Load sector ETFs
            for sector_etf in SECTOR_ETFS:
                try:
                    data = yf.download(sector_etf, start=self.start_date, end=self.end_date, progress=False)
                    
                    if not data.empty:
                        if isinstance(data.columns, pd.MultiIndex):
                            data.columns = data.columns.get_level_values(0)
                        self.sector_data[sector_etf] = data
                    else:
                        logger.warning(f"No data for {sector_etf}")
                        
                except Exception as e:
                    logger.warning(f"Failed to load {sector_etf}: {e}")
            
            logger.info(f"✅ Loaded {len(self.sector_data)} sector ETFs")
            return len(self.sector_data) > 0
            
        except Exception as e:
            logger.error(f"Failed to load sector data: {e}")
            return False
    
    def calculate_relative_strength(self, lookback_days: int = 20) -> pd.DataFrame:
        """
        Calculate relative strength of each sector vs SPY.
        
        RS = (Sector Performance / SPY Performance) - 1
        RS > 0: Sector outperforming
        RS < 0: Sector underperforming
        
        Returns DataFrame with RS for each sector per day.
        """
        logger.info(f"📈 Calculating sector relative strength ({lookback_days}d lookback)...")
        
        rs_data = {}
        
        # Calculate SPY returns
        spy_returns = self.spy_data['Close'].pct_change(lookback_days)
        
        for sector_etf, data in self.sector_data.items():
            # Calculate sector returns
            sector_returns = data['Close'].pct_change(lookback_days)
            
            # Relative Strength = Sector / SPY - 1
            # Align indices
            aligned_sector = sector_returns.reindex(spy_returns.index)
            rs = (aligned_sector / spy_returns) - 1
            
            rs_data[sector_etf] = rs
        
        self.sector_strength = pd.DataFrame(rs_data)
        
        logger.info("✅ Relative strength calculated")
        return self.sector_strength
    
    def rank_sectors_by_strength(self, date: pd.Timestamp) -> Dict[str, Dict]:
        """
        Rank sectors by relative strength on a given date.
        
        Returns dict: {sector_etf: {'rank': int, 'rs': float, 'strength': str}}
        """
        if self.sector_strength is None:
            logger.error("Sector strength not calculated. Run calculate_relative_strength() first.")
            return {}
        
        try:
            # Get RS values for this date
            rs_values = self.sector_strength.loc[date]
            
            # Sort by RS (descending)
            ranked = rs_values.sort_values(ascending=False)
            
            # Create ranking dict
            rankings = {}
            for rank, (sector, rs_value) in enumerate(ranked.items(), 1):
                if pd.notna(rs_value):
                    # Classify strength
                    if rs_value > 0.05:  # >5% outperformance
                        strength = "STRONG"
                    elif rs_value > 0:
                        strength = "MODERATE"
                    elif rs_value > -0.05:
                        strength = "WEAK"
                    else:
                        strength = "VERY_WEAK"
                    
                    rankings[sector] = {
                        'rank': rank,
                        'rs': rs_value,
                        'strength': strength
                    }
            
            return rankings
            
        except KeyError:
            logger.warning(f"Date {date} not in sector strength data")
            return {}
    
    def is_sector_strong(self, sector_etf: str, date: pd.Timestamp, 
                         min_rank: int = 6, min_rs: float = 0.0) -> bool:
        """
        Check if a sector is strong enough to trade.
        
        Args:
            sector_etf: Sector ETF symbol (e.g., 'XLK')
            date: Date to check
            min_rank: Minimum rank (1 = strongest, 11 = weakest)
            min_rs: Minimum RS threshold (0.0 = at least match SPY)
        
        Returns:
            True if sector meets strength criteria
        """
        rankings = self.rank_sectors_by_strength(date)
        
        if sector_etf not in rankings:
            return False
        
        sector_info = rankings[sector_etf]
        
        # Check criteria
        rank_ok = sector_info['rank'] <= min_rank
        rs_ok = sector_info['rs'] >= min_rs
        
        return rank_ok and rs_ok
    
    def get_ticker_sector_strength(self, ticker: str, date: pd.Timestamp) -> Optional[Dict]:
        """
        Get sector strength info for a specific ticker.
        
        Returns:
            {
                'sector_etf': str,
                'rank': int,
                'rs': float,
                'strength': str,
                'is_tradeable': bool
            }
        """
        # Get sector for ticker
        sector_etf = SECTOR_MAP.get(ticker)
        
        if sector_etf is None:
            logger.debug(f"Sector unknown for {ticker}")
            return None
        
        # Get rankings
        rankings = self.rank_sectors_by_strength(date)
        
        if sector_etf not in rankings:
            return None
        
        sector_info = rankings[sector_etf]
        
        # Determine if tradeable (top 6 sectors, RS > 0)
        is_tradeable = (sector_info['rank'] <= 6 and sector_info['rs'] > 0)
        
        return {
            'sector_etf': sector_etf,
            'rank': sector_info['rank'],
            'rs': sector_info['rs'],
            'strength': sector_info['strength'],
            'is_tradeable': is_tradeable
        }
    
    def calculate_composite_score_vectorized(self, 
                                             lookback_weekly: int = 5,
                                             lookback_monthly: int = 20) -> pd.DataFrame:
        """
        Pre-calculate composite scores for ALL dates (vectorized).
        
        This is MUCH faster than calculating per-date.
        Call once at initialization, then lookup by date.
        
        Returns:
            DataFrame with columns = sectors, index = dates, values = composite scores
        """
        if self.sector_data is None or self.spy_data is None:
            logger.error("Sector data not loaded")
            return pd.DataFrame()
        
        try:
            # Pre-calculate SPY returns (vectorized)
            spy_weekly_returns = self.spy_data['Close'].pct_change(lookback_weekly)
            spy_monthly_returns = self.spy_data['Close'].pct_change(lookback_monthly)
            
            all_scores = {}
            
            for sector_etf, data in self.sector_data.items():
                if data.empty:
                    continue
                
                try:
                    # 1. Weekly RS (40% weight) - vectorized
                    sector_weekly = data['Close'].pct_change(lookback_weekly)
                    rs_weekly = ((sector_weekly / spy_weekly_returns) - 1) * 100
                    rs_weekly = rs_weekly.fillna(0)
                    
                    # 2. Monthly RS (30% weight) - vectorized
                    sector_monthly = data['Close'].pct_change(lookback_monthly)
                    rs_monthly = ((sector_monthly / spy_monthly_returns) - 1) * 100
                    rs_monthly = rs_monthly.fillna(0)
                    
                    # 3. Momentum (20% weight) - vectorized
                    current_price = data['Close']
                    price_20d_ago = data['Close'].shift(20)
                    momentum = ((current_price / price_20d_ago) - 1) * 100
                    momentum = momentum.fillna(0)
                    
                    # 4. Relative Volume (10% weight) - vectorized
                    if 'Volume' in data.columns:
                        current_vol = data['Volume']
                        avg_vol = data['Volume'].rolling(20).mean()
                        rvol = ((current_vol / avg_vol) - 1) * 100
                        rvol = rvol.fillna(0)
                    else:
                        rvol = pd.Series(0, index=data.index)
                    
                    # Composite score - vectorized
                    composite = (
                        rs_weekly * 0.40 +
                        rs_monthly * 0.30 +
                        momentum * 0.20 +
                        rvol * 0.10
                    )
                    
                    all_scores[sector_etf] = composite
                    
                except Exception as e:
                    logger.debug(f"Error calculating scores for {sector_etf}: {e}")
                    continue
            
            # Create DataFrame with all scores
            scores_df = pd.DataFrame(all_scores)
            
            logger.info(f"✅ Pre-calculated composite scores for {len(scores_df)} dates, {len(all_scores)} sectors")
            return scores_df
            
        except Exception as e:
            logger.error(f"Error in vectorized calculation: {e}")
            return pd.DataFrame()
    
    def calculate_composite_score(self, date: pd.Timestamp, 
                                   lookback_weekly: int = 5,
                                   lookback_monthly: int = 20) -> Dict[str, float]:
        """
        Calculate composite sector strength score using multiple timeframes.
        
        DEPRECATED: Use calculate_composite_score_vectorized() for better performance.
        This method kept for backward compatibility.
        
        Professional scoring system:
        - 40% RS Weekly (vs SPY)
        - 30% RS Monthly (vs SPY)
        - 20% Price momentum (rate of change)
        - 10% Relative volume
        
        Args:
            date: Date to calculate scores
            lookback_weekly: Days for weekly calculation (default 5)
            lookback_monthly: Days for monthly calculation (default 20)
        
        Returns:
            Dict of {sector_etf: composite_score}
        """
        scores = {}
        
        if self.sector_data is None or self.spy_data is None:
            logger.error("Sector data not loaded")
            return scores
        
        try:
            # Get SPY performance for both timeframes
            spy_weekly = self.spy_data['Close'].pct_change(lookback_weekly).loc[date]
            spy_monthly = self.spy_data['Close'].pct_change(lookback_monthly).loc[date]
            
            for sector_etf, data in self.sector_data.items():
                if data.empty:
                    continue
                
                try:
                    # 1. Weekly RS (40% weight)
                    sector_weekly = data['Close'].pct_change(lookback_weekly).loc[date]
                    rs_weekly = (sector_weekly / spy_weekly - 1) * 100 if spy_weekly != 0 else 0
                    
                    # 2. Monthly RS (30% weight)
                    sector_monthly = data['Close'].pct_change(lookback_monthly).loc[date]
                    rs_monthly = (sector_monthly / spy_monthly - 1) * 100 if spy_monthly != 0 else 0
                    
                    # 3. Price momentum - Rate of Change (20% weight)
                    current_price = data['Close'].loc[date]
                    price_20d_ago = data['Close'].shift(20).loc[date]
                    momentum = ((current_price / price_20d_ago - 1) * 100) if price_20d_ago != 0 else 0
                    
                    # 4. Relative volume (10% weight)
                    current_vol = data['Volume'].loc[date] if 'Volume' in data.columns else 0
                    avg_vol = data['Volume'].rolling(20).mean().loc[date] if 'Volume' in data.columns else 1
                    rvol = (current_vol / avg_vol - 1) * 100 if avg_vol != 0 else 0
                    
                    # Composite score (0-100 scale)
                    composite = (
                        rs_weekly * 0.40 +
                        rs_monthly * 0.30 +
                        momentum * 0.20 +
                        rvol * 0.10
                    )
                    
                    scores[sector_etf] = composite
                    
                except (KeyError, IndexError) as e:
                    logger.debug(f"Could not calculate score for {sector_etf}: {e}")
                    continue
            
            return scores
            
        except Exception as e:
            logger.error(f"Error calculating composite scores: {e}")
            return scores
    
    def rank_sectors_by_composite(self, date: pd.Timestamp, 
                                   top_percentile: float = 0.40,
                                   use_cache: bool = True) -> Dict[str, Dict]:
        """
        Rank sectors by composite score and identify top performers.
        
        Args:
            date: Date to rank
            top_percentile: Top percentage to consider "strong" (0.40 = top 40%)
            use_cache: Use pre-calculated scores (MUCH faster)
        
        Returns:
            Dict of {sector_etf: {'rank': int, 'score': float, 'percentile': float, 
                                   'is_top_tier': bool, 'classification': str}}
        """
        # Use cached pre-calculated scores if available
        if use_cache and self.composite_scores is not None:
            try:
                scores = self.composite_scores.loc[date].to_dict()
            except KeyError:
                logger.warning(f"Date {date} not in composite scores, falling back to on-demand calculation")
                scores = self.calculate_composite_score(date)
        else:
            # Fallback: calculate on-demand (slower)
            scores = self.calculate_composite_score(date)
        
        if not scores:
            return {}
        
        # Sort by score (descending)
        sorted_sectors = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        
        total_sectors = len(sorted_sectors)
        top_n = max(1, int(total_sectors * top_percentile))
        
        rankings = {}
        for rank, (sector_etf, score) in enumerate(sorted_sectors, 1):
            percentile = (total_sectors - rank + 1) / total_sectors
            is_top_tier = rank <= top_n
            
            # Classification
            if rank <= top_n:
                classification = "LEADER"  # Top 40%
            elif percentile >= 0.3:
                classification = "STRONG"  # 40-70%
            elif percentile >= 0.15:
                classification = "NEUTRAL"  # 70-85%
            else:
                classification = "WEAK"  # Bottom 15%
            
            rankings[sector_etf] = {
                'rank': rank,
                'score': score,
                'percentile': percentile,
                'is_top_tier': is_top_tier,
                'classification': classification
            }
        
        return rankings
    
    def get_ticker_composite_strength(self, ticker: str, date: pd.Timestamp,
                                      top_percentile: float = 0.40) -> Optional[Dict]:
        """
        Get composite sector strength for a ticker using Top 40% methodology.
        
        Returns:
            {
                'sector_etf': str,
                'rank': int,
                'score': float,
                'percentile': float,
                'is_top_tier': bool,
                'classification': str,
                'is_tradeable': bool
            }
        """
        sector_etf = SECTOR_MAP.get(ticker)
        
        if sector_etf is None:
            return None
        
        rankings = self.rank_sectors_by_composite(date, top_percentile)
        
        if sector_etf not in rankings:
            return None
        
        sector_info = rankings[sector_etf]
        
        # Tradeable = Top tier (Top 40%)
        sector_info['sector_etf'] = sector_etf
        sector_info['is_tradeable'] = sector_info['is_top_tier']
        
        return sector_info


def integrate_sector_filter_in_backtest(
    ticker: str,
    date: pd.Timestamp,
    analyzer: SectorRotationAnalyzer,
    require_sector_strength: bool = True,
    use_composite_scoring: bool = False,
    top_percentile: float = 0.40
) -> tuple[bool, str]:
    """
    Integration function for backtest entry logic.
    
    Args:
        ticker: Stock ticker
        date: Trading date
        analyzer: SectorRotationAnalyzer instance
        require_sector_strength: Apply sector filter
        use_composite_scoring: Use advanced Top 40% methodology
        top_percentile: Top % to consider strong (0.40 = top 40%)
    
    Returns:
        (can_trade, reason)
    """
    
    # Choose method: Composite (advanced) or Simple (current)
    if use_composite_scoring:
        sector_info = analyzer.get_ticker_composite_strength(ticker, date, top_percentile)
    else:
        sector_info = analyzer.get_ticker_sector_strength(ticker, date)
    
    if sector_info is None:
        # Unknown sector - allow trade (but log warning)
        return (True, "SECTOR_UNKNOWN")
    
    if require_sector_strength:
        if not sector_info['is_tradeable']:
            # Sector too weak - reject trade
            if use_composite_scoring:
                return (False, f"WEAK_SECTOR({sector_info['sector_etf']},rank={sector_info['rank']}/{int(1/top_percentile)},class={sector_info['classification']})")
            else:
                return (False, f"WEAK_SECTOR({sector_info['sector_etf']},rank={sector_info['rank']})")
    
    # Sector is strong - allow trade
    if use_composite_scoring:
        return (True, f"TOP_SECTOR({sector_info['sector_etf']},rank={sector_info['rank']},score={sector_info['score']:.1f})")
    else:
        return (True, f"STRONG_SECTOR({sector_info['sector_etf']},rank={sector_info['rank']},rs={sector_info['rs']:.1%})")