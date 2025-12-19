"""
Market Context Analyzer
Determines if market conditions are favorable for momentum trades

NEW FILTERS:
- SPY > EMA 20 (trend confirmation)
- Breadth improving (% stocks above SMA20 ascending)
- GEX > 0 (Gamma Exposure positive - optional advanced)
"""
import pandas as pd
import numpy as np
from typing import List, Dict
import logging

logger = logging.getLogger(__name__)


class MarketContext:
    
    def __init__(self, market_data_provider):
        self.data_provider = market_data_provider
    
    def analyze_indices(self, symbols: List[str] = ['SPY', 'QQQ']) -> dict:
        """
        Analyze market indices with NEW regime filters
        
        Returns context including:
        - Gap down detection
        - SPY trend (> EMA20)
        - Breadth direction
        - GEX regime estimation
        """
        context = {}
        
        # Get historical data for SPY (need for EMA/SMA calculations)
        try:
            spy_daily = self.data_provider.get_daily_data('SPY', period='3mo')
            qqq_daily = self.data_provider.get_daily_data('QQQ', period='3mo')
            
            if not spy_daily.empty:
                # Calculate SPY EMA 20
                spy_ema20 = spy_daily['Close'].ewm(span=20, adjust=False).mean().iloc[-1]
                spy_current = spy_daily['Close'].iloc[-1]
                context['spy_above_ema20'] = spy_current > spy_ema20
                context['spy_ema20'] = spy_ema20
                context['spy_price'] = spy_current
                
                # Estimate breadth trend
                context['breadth_improving'] = self._estimate_breadth_trend(spy_daily, qqq_daily)
                
                # Estimate GEX regime
                context['positive_gex'] = self._estimate_positive_gex(spy_daily)
                
                logger.info(f"SPY: ${spy_current:.2f} | EMA20: ${spy_ema20:.2f} | Above: {context['spy_above_ema20']}")
                logger.info(f"Breadth improving: {context['breadth_improving']} | Positive GEX: {context['positive_gex']}")
        
        except Exception as e:
            logger.error(f"Error calculating SPY trend: {e}")
            context['spy_above_ema20'] = True  # Default to allow if data fails
            context['breadth_improving'] = False
            context['positive_gex'] = False
        
        # Original gap down detection
        for symbol in symbols:
            try:
                info = self.data_provider.get_current_price(symbol)
                
                gap_pct = (info['open'] - info['previous_close']) / info['previous_close']
                is_gap_down = gap_pct < -0.005
                
                context[f'{symbol.lower()}_gap_down'] = is_gap_down
                context[f'{symbol.lower()}_gap_pct'] = gap_pct
                context[f'{symbol.lower()}_current'] = info['current_price']
                context[f'{symbol.lower()}_change_pct'] = (
                    (info['current_price'] - info['previous_close']) / info['previous_close']
                )
                
                logger.info(f"{symbol}: Gap {gap_pct*100:.2f}%, Current Change {context[f'{symbol.lower()}_change_pct']*100:.2f}%")
            
            except Exception as e:
                logger.error(f"Error analyzing {symbol}: {e}")
                context[f'{symbol.lower()}_gap_down'] = False
                context[f'{symbol.lower()}_gap_pct'] = 0
        
        # Market weakness flag
        context['market_weak'] = any([
            context.get('spy_gap_down', False),
            context.get('qqq_gap_down', False),
            context.get('spy_change_pct', 0) < -0.01,
            context.get('qqq_change_pct', 0) < -0.01
        ])
        
        # NEW: Market favorable for longs
        # SPY > EMA20 OR Breadth improving
        context['market_favorable_for_longs'] = (
            context.get('spy_above_ema20', True) or 
            context.get('breadth_improving', False)
        )
        
        # NEW: Allow aggressive entries
        # Market favorable AND positive GEX
        context['allow_aggressive_entries'] = (
            context.get('market_favorable_for_longs', False) and
            context.get('positive_gex', False)
        )
        
        return context
    
    def _estimate_breadth_trend(self, spy_data: pd.DataFrame, qqq_data: pd.DataFrame) -> bool:
        """
        Estimate if breadth (% stocks above SMA20) is improving
        
        Proxy method:
        - Calculate SMA20 for SPY and QQQ
        - Check if both are above their SMA20
        - Check if recent 5 days avg > previous 5 days avg (ascending)
        """
        try:
            if len(spy_data) < 20 or len(qqq_data) < 20:
                return False
            
            # SMA20 for both
            spy_sma20 = spy_data['Close'].rolling(20).mean().iloc[-1]
            qqq_sma20 = qqq_data['Close'].rolling(20).mean().iloc[-1]
            
            spy_above = spy_data['Close'].iloc[-1] > spy_sma20
            qqq_above = qqq_data['Close'].iloc[-1] > qqq_sma20
            
            # Check ascending trend (recent vs previous)
            recent_5 = spy_data['Close'].iloc[-5:].mean()
            previous_5 = spy_data['Close'].iloc[-10:-5].mean()
            ascending = recent_5 > previous_5
            
            # Breadth improving if both above SMA20 OR ascending
            return (spy_above and qqq_above) or ascending
        
        except Exception as e:
            logger.error(f"Error estimating breadth: {e}")
            return False
    
    def _estimate_positive_gex(self, spy_data: pd.DataFrame) -> bool:
        """
        Estimate positive GEX (Gamma Exposure) regime
        
        Positive GEX characteristics:
        - Low volatility (declining ATR)
        - Grinding uptrend
        - Price above short-term EMA
        
        Proxy:
        - ATR(5) declining
        - SPY > EMA10
        """
        try:
            if len(spy_data) < 20:
                return False
            
            # Calculate ATR(5)
            high_low = spy_data['High'] - spy_data['Low']
            atr5 = high_low.rolling(5).mean()
            
            atr_declining = atr5.iloc[-1] < atr5.iloc[-5]
            
            # EMA10
            ema10 = spy_data['Close'].ewm(span=10, adjust=False).mean().iloc[-1]
            price_above_ema10 = spy_data['Close'].iloc[-1] > ema10
            
            # Positive GEX = declining vol + uptrend
            return atr_declining and price_above_ema10
        
        except Exception as e:
            logger.error(f"Error estimating GEX: {e}")
            return False
