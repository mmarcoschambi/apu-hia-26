"""
Adaptive Filter Engine - Tiered Progressive Filtering System
============================================================
Implements 3-tier filtering based on market regime (VIX/SPY).

TIER 1: Hard Floors (Always Active)
- Price >= SMA20 (Trend Alignment)
- Minimum Liquidity ($Volume, Shares)
- Market Safety (SPY > SMA50, VIX < 35)

TIER 2: Dynamic Quality (Regime-Based)
- RVOL, ADR, Distance SMA20, Dollar Volume
- Thresholds adjust based on VIX regime

TIER 3: Optional (Configurable)
- Consolidation Days
- Sector Strength
"""

import pandas as pd
import numpy as np
from typing import Dict, Any
import logging

logger = logging.getLogger(__name__)


class AdaptiveFilterEngine:
    """
    Tiered progressive filtering system with market regime adaptation.
    
    Provides detailed rejection logging for diagnostics and 
    dynamic thresholds based on VIX/SPY market conditions.
    """
    
    def __init__(self, use_dynamic: bool = True, logger_obj=None):
        """
        Initialize adaptive filter engine.
        
        Args:
            use_dynamic: If True, use VIX-based dynamic thresholds
            logger_obj: Optional custom logger instance
        """
        self.use_dynamic = use_dynamic
        self.rejection_stats = {}
        self.logger = logger_obj or logger
        self.logger.info("🔧 AdaptiveFilterEngine initialized")
        
    def get_market_regime_thresholds(self, 
                                     vix_value: float, 
                                     spy_trend_strength: float,
                                     base_min_rvol: float = 1.5,
                                     base_min_adr: float = 2.5,
                                     base_max_dist_sma20: float = 7.0,
                                     base_min_dollar_volume: float = 3_000_000,
                                     base_min_consolidation: int = 8) -> Dict[str, Any]:
        """
        Define thresholds based on market context.
        DYNAMIC: Uses validated params as base and applies regime multipliers.
        
        Args:
            vix_value: Current VIX value
            spy_trend_strength: % SPY above/below SMA50
            base_*: Base parameters from validated config (NEUTRAL regime baseline)
            
        Returns:
            Dictionary with regime-specific thresholds
        """
        if vix_value < 20:  # BULL regime - relax filters
            return {
                'regime_name': 'BULL',
                'min_rvol': base_min_rvol * 1.0,
                'min_adr': base_min_adr * 1.0,
                'max_dist_sma20': base_max_dist_sma20 * 1.15,
                'min_dollar_volume': base_min_dollar_volume * 0.67,
                'min_consolidation': max(5, int(base_min_consolidation * 0.6)),
                'strict_sector': False
            }
        elif vix_value < 30:  # NEUTRAL regime - use base params
            return {
                'regime_name': 'NEUTRAL',
                'min_rvol': base_min_rvol,
                'min_adr': base_min_adr,
                'max_dist_sma20': base_max_dist_sma20,
                'min_dollar_volume': base_min_dollar_volume,
                'min_consolidation': base_min_consolidation,
                'strict_sector': False
            }
        else:  # BEAR regime - tighten filters
            return {
                'regime_name': 'BEAR',
                'min_rvol': base_min_rvol * 1.2,
                'min_adr': base_min_adr * 1.6,
                'max_dist_sma20': base_max_dist_sma20 * 0.71,
                'min_dollar_volume': base_min_dollar_volume * 1.67,
                'min_consolidation': int(base_min_consolidation * 1.2),
                'strict_sector': True
            }
    
    def check_filters(self, 
                      ticker: str,
                      date: pd.Timestamp,
                      price: float,
                      sma20: float,
                      volume: float,
                      avg_vol: float,
                      adr: float,
                      sector_rs: float,
                      consolidation_days: int,
                      vix_value: float,
                      spy_trend_strength: float,
                      dollar_volume: float = None,
                      base_min_rvol: float = 1.5,
                      base_min_adr: float = 2.5,
                      base_max_dist_sma20: float = 7.0,
                      base_min_dollar_volume: float = 3_000_000,
                      base_min_consolidation: int = 8) -> bool:
        """
        Apply tiered progressive filtering (TIER 1, 2, 3).
        DYNAMIC: Uses validated params as base for regime adjustments.
        
        Args:
            ticker: Stock ticker symbol
            date: Current date
            price: Current price
            sma20: SMA20 value
            volume: Current volume
            avg_vol: Average volume (20-day)
            adr: Average daily range percentage
            sector_rs: Relative strength of sector
            consolidation_days: Days in consolidation
            vix_value: Current VIX
            spy_trend_strength: SPY trend strength
            dollar_volume: Dollar volume (optional, calculated if not provided)
            base_*: Base parameters from validated config
            
        Returns:
            True if passes all filters, False otherwise
        """
        if self.use_dynamic:
            thresholds = self.get_market_regime_thresholds(
                vix_value, 
                spy_trend_strength,
                base_min_rvol=base_min_rvol,
                base_min_adr=base_min_adr,
                base_max_dist_sma20=base_max_dist_sma20,
                base_min_dollar_volume=base_min_dollar_volume,
                base_min_consolidation=base_min_consolidation
            )
        else:
            # Use base params directly when not dynamic
            thresholds = {
                'regime_name': 'FIXED',
                'min_rvol': base_min_rvol,
                'min_adr': base_min_adr,
                'max_dist_sma20': base_max_dist_sma20,
                'min_dollar_volume': base_min_dollar_volume,
                'min_consolidation': base_min_consolidation,
                'strict_sector': True
            }
        
        dollar_volume = dollar_volume or (price * volume)
        
        current_rvol = volume / avg_vol if avg_vol > 0 else 0
        dist_sma20 = (price - sma20) / sma20 * 100 if sma20 > 0 else 0
        
        # TIER 1: HARD FLOORS (Non-negotiable)
        if price < sma20:
            self._log_rejection("TIER1_PriceBelowSMA20")
            return False
        
        if volume < 200000:
            self._log_rejection("TIER1_LowLiquidity_Volume")
            return False
        
        if dollar_volume < thresholds['min_dollar_volume']:
            self._log_rejection(f"TIER1_LowLiquidity_DollarVol_{thresholds['min_dollar_volume']/1e6:.0f}M")
            return False
        
        # TIER 2: DYNAMIC QUALITY (Regime-based)
        if current_rvol < thresholds['min_rvol']:
            self._log_rejection(f"TIER2_LowRVOL_Regime{thresholds['regime_name']}_{current_rvol:.2f}x")
            return False
        
        if adr < thresholds['min_adr']:
            self._log_rejection(f"TIER2_LowADR_Regime{thresholds['regime_name']}_{adr:.2f}%")
            return False
        
        if dist_sma20 > thresholds['max_dist_sma20']:
            self._log_rejection(f"TIER2_Overextended_Regime{thresholds['regime_name']}_{dist_sma20:.1f}%")
            return False
        
        # TIER 3: OPTIONAL (Configurable)
        if consolidation_days < thresholds['min_consolidation']:
            self._log_rejection(f"TIER3_ShortConsolidation_{consolidation_days}d_Req{thresholds['min_consolidation']}d")
            return False
        
        if thresholds['strict_sector'] and sector_rs <= 0:
            self._log_rejection("TIER3_WeakSector")
            return False
        
        return True
    
    def _log_rejection(self, reason: str):
        """Log rejection for diagnostics."""
        self.rejection_stats[reason] = self.rejection_stats.get(reason, 0) + 1
    
    def print_report(self):
        """Print rejection statistics."""
        print("\n" + "="*60)
        print("📊 ADAPTIVE FILTER ENGINE - REJECTION DIAGNOSTICS")
        print("="*60)
        
        if not self.rejection_stats:
            print("✅ No rejections logged")
            return
        
        # Group by tier
        tier1 = {k: v for k, v in self.rejection_stats.items() if k.startswith('TIER1')}
        tier2 = {k: v for k, v in self.rejection_stats.items() if k.startswith('TIER2')}
        tier3 = {k: v for k, v in self.rejection_stats.items() if k.startswith('TIER3')}
        
        total_rejections = sum(self.rejection_stats.values())
        
        print(f"\n📊 Total Rejections: {total_rejections}")
        
        if tier1:
            print(f"\n🛡️ TIER 1 (Hard Floors): {sum(tier1.values())}")
            for reason, count in sorted(tier1.items(), key=lambda x: x[1], reverse=True):
                print(f"   ❌ {reason}: {count}")
        
        if tier2:
            print(f"\n📈 TIER 2 (Dynamic Quality): {sum(tier2.values())}")
            for reason, count in sorted(tier2.items(), key=lambda x: x[1], reverse=True):
                print(f"   ❌ {reason}: {count}")
        
        if tier3:
            print(f"\n⚙️ TIER 3 (Optional): {sum(tier3.values())}")
            for reason, count in sorted(tier3.items(), key=lambda x: x[1], reverse=True):
                print(f"   ❌ {reason}: {count}")
        
        print("\n" + "="*60)
    
    def get_rejection_stats(self) -> Dict[str, int]:
        """Return rejection statistics dictionary."""
        return self.rejection_stats.copy()
    
    def reset_stats(self):
        """Clear rejection statistics."""
        self.rejection_stats = {}
    
    def print_threshold_summary(self, 
                                base_min_rvol: float,
                                base_min_adr: float, 
                                base_max_dist_sma20: float,
                                base_min_dollar_volume: float,
                                base_min_consolidation: int):
        """
        Print how validated params are adjusted by regime.
        
        Shows base params and regime multipliers for transparency.
        """
        print("\n" + "="*70)
        print("📊 ADAPTIVE FILTER THRESHOLDS (Based on Validated Params)")
        print("="*70)
        print(f"\n✅ BASE PARAMS (NEUTRAL VIX 20-30):")
        print(f"   min_rvol:             {base_min_rvol:.1f}x")
        print(f"   min_adr:              {base_min_adr:.1f}%")
        print(f"   max_dist_sma20:       {base_max_dist_sma20:.1f}%")
        print(f"   min_dollar_volume:    ${base_min_dollar_volume/1e6:.1f}M")
        print(f"   min_consolidation:    {base_min_consolidation} days")
        
        # Calculate and show regime adjustments
        bull = self.get_market_regime_thresholds(15, 0, base_min_rvol, base_min_adr, 
                                                 base_max_dist_sma20, base_min_dollar_volume, 
                                                 base_min_consolidation)
        neutral = self.get_market_regime_thresholds(25, 0, base_min_rvol, base_min_adr,
                                                    base_max_dist_sma20, base_min_dollar_volume,
                                                    base_min_consolidation)
        bear = self.get_market_regime_thresholds(35, 0, base_min_rvol, base_min_adr,
                                                 base_max_dist_sma20, base_min_dollar_volume,
                                                 base_min_consolidation)
        
        print(f"\n📈 BULL REGIME (VIX < 20) - Relaxed:")
        print(f"   min_rvol:    {bull['min_rvol']:.1f}x  (base × 1.0)")
        print(f"   min_adr:     {bull['min_adr']:.1f}%  (base × 1.0)")
        print(f"   max_dist:    {bull['max_dist_sma20']:.1f}%  (base × 1.15)")
        print(f"   min_$vol:    ${bull['min_dollar_volume']/1e6:.1f}M  (base × 0.67)")
        print(f"   min_consol:  {bull['min_consolidation']}d  (base × 0.6)")
        
        print(f"\n📊 NEUTRAL REGIME (VIX 20-30) - Base Params:")
        print(f"   (Uses validated params as-is)")
        
        print(f"\n📉 BEAR REGIME (VIX > 30) - Tightened:")
        print(f"   min_rvol:    {bear['min_rvol']:.1f}x  (base × 1.2)")
        print(f"   min_adr:     {bear['min_adr']:.1f}%  (base × 1.6)")
        print(f"   max_dist:    {bear['max_dist_sma20']:.1f}%  (base × 0.71)")
        print(f"   min_$vol:    ${bear['min_dollar_volume']/1e6:.1f}M  (base × 1.67)")
        print(f"   min_consol:  {bear['min_consolidation']}d  (base × 1.2)")
        
        print("="*70)
