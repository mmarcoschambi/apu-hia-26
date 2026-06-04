"""
The Triad Protocol - Entry Logic Engine
Implements the 3 Caminos (Paths)
"""
import pandas as pd
from enum import Enum
from dataclasses import dataclass
from typing import Optional
import logging

logger = logging.getLogger(__name__)


class Camino(Enum):
    """The 3 Royal Paths"""
    BLUE_SKY = 1  # Combo Perfecto - Base + AVWAP converge
    VWAP_RECLAIM = 2  # Segunda Oportunidad - Gap down recovery
    SAFETY_CHECK = 3  # Filtro de Seguridad - Wait for AVWAP


@dataclass
class Signal:
    """Trading Signal Output"""
    camino: Optional[Camino]
    action: str  # 'BUY_STOP', 'WAIT', 'MANUAL_WATCH', 'NO_SETUP'
    entry_price: Optional[float]
    stop_loss: Optional[float]
    position_size_multiplier: float  # 1.0 = standard, 0.5 = reduced
    reasoning: str
    context: dict


class TriadStrategy:
    
    def __init__(self, 
                 avwap_convergence_tolerance: float = 0.02,
                 blue_sky_offset: float = 0.05,
                 gap_down_threshold: float = -0.01,
                 max_extension_pct: float = 0.0677):
        """
        avwap_convergence_tolerance: AVWAP within X% of base high = convergence
        blue_sky_offset: Buy stop offset above base high
        gap_down_threshold: Market gap % to trigger Camino 2 logic
        max_extension_pct: Maximum allowed extension from base/SMA for Monster Stocks
        """
        self.avwap_tolerance = avwap_convergence_tolerance
        self.blue_sky_offset = blue_sky_offset
        self.gap_threshold = gap_down_threshold
        self.max_extension = max_extension_pct
    
    def analyze(self, 
                base_data: dict,
                avwap_data: dict,
                vwap_data: dict,
                gap_data: dict,
                market_context: dict,
                adr: float) -> Signal:
        """
        Main decision engine - routes to appropriate Camino
        
        Decision Tree:
        1. Check if AVWAP is far above (>5-10%) → Camino 3 (WAIT)
        2. Check if Base + AVWAP converge → Camino 1 (BLUE SKY)
        3. Check if gap down + weak market → Camino 2 (VWAP RECLAIM)
        4. Otherwise → NO SETUP
        """
        
        # Validate data
        if not base_data['detected'] or not avwap_data['calculated']:
            return Signal(
                camino=None,
                action='NO_SETUP',
                entry_price=None,
                stop_loss=None,
                position_size_multiplier=1.0,
                reasoning="Base not detected or AVWAP not calculated",
                context={}
            )
        
        base_high = base_data['base_high']
        current_price = base_data['current_price']
        avwap_price = avwap_data['current_avwap']
        distance_to_avwap_pct = abs(avwap_data['distance_to_avwap_pct'])
        
        # ============================================
        # 🛡️ ALPHA SECTOR FILTER (Main)
        # ============================================
        # Solo permitir trades en los Top 3 Sectores del día.
        # Si no es líder, degradar a MANUAL_WATCH o NO_SETUP.
        sector_leaders = market_context.get('sector_leaders', {})
        stock_symbol = base_data.get('symbol', 'UNKNOWN')
        
        # Note: TriadScanner needs to pass 'symbol' in base_data or we need another way.
        # For now, let's assume we want to check leadership.
        if sector_leaders:
            from src.core.market_context import MarketContext
            # We need an instance to use get_stock_sector, or make it static/helper
            # Actually, MarketContext.is_sector_leading does exactly this.
            # But we don't have the instance here. 
            # We'll use a simplified version or assume market_context has 'is_leading'
            is_leading = market_context.get('is_leading_sector', True) # Default to True if not provided
            
            if not is_leading:
                logger.info(f"⚠️ REJECTED Alpha Sector: {stock_symbol} is not in a Top 3 Sector today.")
                return Signal(
                    camino=None,
                    action='NO_SETUP',
                    entry_price=None,
                    stop_loss=None,
                    position_size_multiplier=0.0,
                    reasoning=f"REJECTED: Alpha Sector Filter. Ticker is not in one of the Top 3 leading sectors. "
                              f"Alpha is found in sector momentum. Wait for sector rotation or pick a leader.",
                    context={
                        'sector_leaders': list(sector_leaders.keys())[:3],
                        'rejection_reason': 'Sector_Not_Leading'
                    }
                )

        # ============================================
        # EXPERIMENTAL: STAGE EXTENSION GATE (exptt)
        # ============================================
        # Monster Stocks must be caught before they are > 6.77% extended from pivot
        extension_from_base = (current_price / base_high) - 1
        if extension_from_base > self.max_extension:
            logger.info(f"🚫 REJECTED: Extension Gate. Price ${current_price:.2f} is {extension_from_base*100:.2f}% "
                       f"extended from Base High ${base_high:.2f} (Limit: {self.max_extension*100:.2f}%)")
            return Signal(
                camino=None,
                action='NO_SETUP',
                entry_price=None,
                stop_loss=None,
                position_size_multiplier=0.0,
                reasoning=f"REJECTED: Extension Gate. Price is {extension_from_base*100:.2f}% extended "
                          f"from base high. Risk of buying the top of a 'Monster Stock' stage. "
                          f"Wait for a pullback or tight consolidation (Limit: {self.max_extension*100:.2f}%).",
                context={
                    'extension_pct': extension_from_base,
                    'limit': self.max_extension,
                    'rejection_reason': 'Extension_Gate'
                }
            )

        # ============================================
        # CAMINO 3: SAFETY CHECK - AVWAP TOO FAR ABOVE
        # ============================================
        if avwap_price > current_price and distance_to_avwap_pct > 0.05:
            # AVWAP is more than 5% above current price
            # This is "Anticipation Breakout" risk
            return Signal(
                camino=Camino.SAFETY_CHECK,
                action='WAIT',
                entry_price=avwap_price + 0.05,  # Entry only above AVWAP
                stop_loss=None,
                position_size_multiplier=1.0,
                reasoning=f"AVWAP ({avwap_price:.2f}) is {distance_to_avwap_pct*100:.1f}% above price. "
                          f"Waiting for AVWAP breakout to avoid Anticipation Breakout trap.",
                context={
                    'base_high': base_high,
                    'avwap_price': avwap_price,
                    'current_price': current_price,
                    'wait_for_price': avwap_price
                }
            )
        
        # ============================================
        # CAMINO 1: BLUE SKY BREAKOUT - CONVERGENCE
        # ============================================
        # Base high and AVWAP are converging (within tolerance)
        avwap_base_convergence = abs(avwap_price - base_high) / base_high
        
        if avwap_base_convergence <= self.avwap_tolerance:
            # CRITICAL: Check trend strength for Blue Sky Breakouts
            # Rule: "Never buy a Breakout if price is not being respected by SMA20"
            trend = market_context.get('trend_sma', 'Unknown')
            rvol = market_context.get('rvol', 0)
            
            # FILTER 1: Reject if Weak Trend
            if trend == 'Weak':
                # REJECT: Blue Sky with Weak trend is a trap
                logger.info(f"🚫 REJECTED Blue Sky Breakout: Trend 'Weak' - Price below SMA20. "
                           f"Base: {base_high:.2f}, AVWAP: {avwap_price:.2f}, "
                           f"Current: {current_price:.2f}, SMA20: {market_context.get('sma_20', 'N/A')}")
                return Signal(
                    camino=None,
                    action='NO_SETUP',
                    entry_price=None,
                    stop_loss=None,
                    position_size_multiplier=0.0,
                    reasoning=f"REJECTED Blue Sky: Trend is 'Weak' (price below SMA20). "
                              f"Base ({base_high:.2f}) and AVWAP ({avwap_price:.2f}) converge, "
                              f"but breakout is unreliable without SMA20 support. "
                              f"Wait for price to recover above SMA20 and form new base.",
                    context={
                        'base_high': base_high,
                        'base_low': base_data['base_low'],
                        'avwap_price': avwap_price,
                        'convergence_pct': avwap_base_convergence,
                        'trend': trend,
                        'rvol': rvol,
                        'rejection_reason': 'Weak_Trend'
                    }
                )
            
            # FILTER 2: Reject if RVOL < 1.5x
            # Rule: "¿El RVOL es mayor a 1.5x y la Tendencia es Fuerte? Si NO -> NO HAY TRADE"
            if rvol < 1.5:
                # REJECT: Blue Sky without institutional volume confirmation
                logger.info(f"🚫 REJECTED Blue Sky Breakout: RVOL too low ({rvol:.2f}x < 1.5x). "
                           f"Base: {base_high:.2f}, AVWAP: {avwap_price:.2f}, "
                           f"Trend: {trend}. Need >1.5x volume for institutional confirmation.")
                return Signal(
                    camino=None,
                    action='NO_SETUP',
                    entry_price=None,
                    stop_loss=None,
                    position_size_multiplier=0.0,
                    reasoning=f"REJECTED Blue Sky: RVOL ({rvol:.2f}x) is below 1.5x threshold. "
                              f"Base ({base_high:.2f}) and AVWAP ({avwap_price:.2f}) converge, "
                              f"Trend is '{trend}', but lack of volume indicates weak institutional interest. "
                              f"Need RVOL > 1.5x (ideally > 2.0x) for confirmation.",
                    context={
                        'base_high': base_high,
                        'base_low': base_data['base_low'],
                        'avwap_price': avwap_price,
                        'convergence_pct': avwap_base_convergence,
                        'trend': trend,
                        'rvol': rvol,
                        'rejection_reason': 'Low_RVOL'
                    }
                )
            
            # Perfect setup: Base and AVWAP eliminate resistance together
            # AND price is respecting SMA20 (Uptrend)
            # AND volume confirms institutional interest (RVOL > 1.5x)
            entry = base_high + self.blue_sky_offset
            stop = base_data['base_low']
            
            # Alternative stop: entry - 1 ADR
            stop_adr = entry - adr
            stop_loss = max(stop, stop_adr)  # Use the higher stop
            
            logger.info(f"✅ APPROVED Blue Sky Breakout: Trend '{trend}', RVOL {rvol:.2f}x. "
                       f"Entry: {entry:.2f}, Stop: {stop_loss:.2f}, "
                       f"Base: {base_high:.2f}, AVWAP: {avwap_price:.2f}")
            
            return Signal(
                camino=Camino.BLUE_SKY,
                action='BUY_STOP',
                entry_price=entry,
                stop_loss=stop_loss,
                position_size_multiplier=1.0,
                reasoning=f"Blue Sky Breakout: Base ({base_high:.2f}) and AVWAP ({avwap_price:.2f}) "
                          f"converge within {avwap_base_convergence*100:.1f}%. "
                          f"Trend: {trend}. RVOL: {rvol:.2f}x. Clear path above with SMA20 support and volume confirmation.",
                context={
                    'base_high': base_high,
                    'base_low': base_data['base_low'],
                    'avwap_price': avwap_price,
                    'convergence_pct': avwap_base_convergence,
                    'trend': trend,
                    'rvol': rvol,
                    'adr': adr
                }
            )
        
        # ============================================
        # CAMINO 2: VWAP RECLAIM - WEAK OPEN RECOVERY
        # ============================================
        # Check if we have gap down OR weak market context
        is_weak_market = (
            gap_data.get('detected', False) or
            market_context.get('spy_gap_down', False) or
            market_context.get('qqq_gap_down', False)
        )
        
        if is_weak_market and vwap_data.get('calculated', False):
            # We're in Camino 2 territory
            # Wait for VWAP reclaim (cross up)
            
            # RVOL filter: VWAP Reclaim requires institutional volume
            rvol = market_context.get('rvol', 0)
            if rvol < 1.0:
                return Signal(
                    camino=None,
                    action='NO_SETUP',
                    entry_price=None,
                    stop_loss=None,
                    position_size_multiplier=1.0,
                    reasoning=f"REJECTED VWAP Reclaim: RVOL ({rvol:.2f}x) below 1.0x. "
                              f"Need institutional volume to confirm recovery.",
                    context={
                        'rvol': rvol,
                        'vwap': vwap_data['current_vwap']
                    }
                )
            
            if vwap_data.get('crossed_up', False):
                # Price just crossed above VWAP - entry signal
                entry = current_price
                stop = vwap_data['session_low']  # LOD is critical
                
                return Signal(
                    camino=Camino.VWAP_RECLAIM,
                    action='BUY_STOP',
                    entry_price=entry,
                    stop_loss=stop,
                    position_size_multiplier=0.5,  # Reduced size (0.25-0.40% risk)
                    reasoning=f"VWAP Reclaim: Weak open, price reclaimed VWAP at {entry:.2f}. "
                              f"Institutions defending position. RVOL: {rvol:.2f}x",
                    context={
                        'vwap': vwap_data['current_vwap'],
                        'session_low': vwap_data['session_low'],
                        'session_open': vwap_data['session_open'],
                        'gap_pct': gap_data.get('gap_pct', 0),
                        'rvol': rvol
                    }
                )
            else:
                # Weak market but VWAP not reclaimed yet - watch
                return Signal(
                    camino=Camino.VWAP_RECLAIM,
                    action='MANUAL_WATCH',
                    entry_price=vwap_data['current_vwap'],
                    stop_loss=vwap_data['session_low'],
                    position_size_multiplier=0.5,
                    reasoning=f"Weak market detected. Waiting for VWAP reclaim at {vwap_data['current_vwap']:.2f}. "
                              f"Current price: {current_price:.2f}",
                    context={
                        'vwap': vwap_data['current_vwap'],
                        'current_price': current_price,
                        'below_vwap': not vwap_data['above_vwap']
                    }
                )
        
        # ============================================
        # NO CLEAR SETUP
        # ============================================
        return Signal(
            camino=None,
            action='NO_SETUP',
            entry_price=None,
            stop_loss=None,
            position_size_multiplier=1.0,
            reasoning="No clear Camino detected. Base exists but no convergence or weak market setup.",
            context={
                'base_high': base_high,
                'avwap_price': avwap_price,
                'convergence_pct': avwap_base_convergence
            }
        )
