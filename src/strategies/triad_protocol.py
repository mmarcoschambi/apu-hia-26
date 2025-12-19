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
                 gap_down_threshold: float = -0.01):
        """
        avwap_convergence_tolerance: AVWAP within X% of base high = convergence
        blue_sky_offset: Buy stop offset above base high
        gap_down_threshold: Market gap % to trigger Camino 2 logic
        """
        self.avwap_tolerance = avwap_convergence_tolerance
        self.blue_sky_offset = blue_sky_offset
        self.gap_threshold = gap_down_threshold
    
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
            # Perfect setup: Base and AVWAP eliminate resistance together
            entry = base_high + self.blue_sky_offset
            stop = base_data['base_low']
            
            # Alternative stop: entry - 1 ADR
            stop_adr = entry - adr
            stop_loss = max(stop, stop_adr)  # Use the higher stop
            
            return Signal(
                camino=Camino.BLUE_SKY,
                action='BUY_STOP',
                entry_price=entry,
                stop_loss=stop_loss,
                position_size_multiplier=1.0,
                reasoning=f"Blue Sky Breakout: Base ({base_high:.2f}) and AVWAP ({avwap_price:.2f}) "
                          f"converge within {avwap_base_convergence*100:.1f}%. Clear path above.",
                context={
                    'base_high': base_high,
                    'base_low': base_data['base_low'],
                    'avwap_price': avwap_price,
                    'convergence_pct': avwap_base_convergence,
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
                              f"Institutions defending position.",
                    context={
                        'vwap': vwap_data['current_vwap'],
                        'session_low': vwap_data['session_low'],
                        'session_open': vwap_data['session_open'],
                        'gap_pct': gap_data.get('gap_pct', 0)
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
