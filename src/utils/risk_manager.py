"""
Institutional Risk Manager Module
Implements Volatility-Normalized, Fixed-Fractional Position Sizing.
"""
import logging
from typing import Dict, Optional

logger = logging.getLogger(__name__)

class RiskManager:
    """
    Professional institutional risk manager for systematic trading.
    Enforces constant monetary risk per trade while varying nominal exposure based on volatility.
    """

    def __init__(self, 
                 account_equity: float, 
                 risk_fraction: float = 0.005, 
                 max_exposure_fraction: float = 0.25,
                 buying_power: Optional[float] = None):
        """
        Initialize the Risk Manager.

        Args:
            account_equity: Total account equity (NAV).
            risk_fraction: Fraction of equity to risk per trade (e.g., 0.005 for 0.5%).
            max_exposure_fraction: Hard cap on nominal exposure per single asset (e.g., 0.25 for 25%).
            buying_power: Available buying power. Defaults to account_equity if None (Cash account).
        """
        self.account_equity = account_equity
        self.risk_fraction = risk_fraction
        self.max_exposure_fraction = max_exposure_fraction
        self.buying_power = buying_power if buying_power is not None else account_equity

    def calculate_position_size(self, 
                                entry_price: float, 
                                stop_price: float, 
                                market_regime_factor: float = 1.0,
                                adr_pct: float = 0.0) -> Dict:
        """
        Calculate the optimal position size based on risk parameters.

        Args:
            entry_price: Planned entry price.
            stop_price: Technical invalidation point (structural stop).
            market_regime_factor: Risk scaler {1.0, 0.5, 0.0}.
            adr_pct: Average Daily Range percentage (used for small account constraints).

        Returns:
            Dictionary containing sizing details: shares, position_value, risk_monetary, constraints_hit.
        """
        
        # 1. Market Regime Scaling (Institutional Standard)
        # risk_on -> 1.0, risk_off -> 0.5, no_trade -> 0.0
        if market_regime_factor <= 0:
             return self._zero_allocation("Market Regime / Factor 0")

        # 2. Small Account Constraint (<25k)
        # Low-ADR assets become capital-inefficient. Enforce ADR >= 4% rule.
        if self.account_equity < 25000 and adr_pct < 4.0:
            return self._zero_allocation("Small Account / Low ADR")

        # 3. Monetary Risk Calculation (R)
        # R = account_equity * risk_fraction * market_regime_factor
        risk_monetary = self.account_equity * self.risk_fraction * market_regime_factor

        # 4. Per-Share Risk (D)
        # D = abs(entry_price - stop_price)
        per_share_risk = abs(entry_price - stop_price)
        
        if per_share_risk <= 0:
            logger.error(f"Invalid stop price {stop_price} for entry {entry_price}")
            return self._zero_allocation("Invalid Stop")

        # 5. Theoretical Position Size
        # shares = R / D
        raw_shares = risk_monetary / per_share_risk
        shares = int(raw_shares) # Integer shares usually required

        if shares <= 0:
            return self._zero_allocation("Risk too small for 1 share")

        # 6. Nominal Capital Required
        # position_value = shares * entry_price
        position_value = shares * entry_price
        
        constraint_hit = None

        # 7. Hard Risk Constraints
        
        # Constraint A: Buying Power
        if position_value > self.buying_power:
            shares = int(self.buying_power / entry_price)
            position_value = shares * entry_price
            constraint_hit = "Buying Power"

        # Constraint B: Max Exposure Fraction
        max_nominal_exposure = self.account_equity * self.max_exposure_fraction
        if position_value > max_nominal_exposure:
            shares = int(max_nominal_exposure / entry_price)
            position_value = shares * entry_price
            constraint_hit = "Max Exposure Cap"

        # Recalculate actual risk after constraints (Risk may decrease, never increase)
        actual_risk = shares * per_share_risk
        
        return {
            "shares": shares,
            "position_value": position_value,
            "risk_monetary": actual_risk,
            "entry_price": entry_price,
            "stop_price": stop_price,
            "r_fraction_realized": actual_risk / self.account_equity,
            "constraint_hit": constraint_hit,
            "regime_factor": market_regime_factor
        }

    def _zero_allocation(self, reason: str) -> Dict:
        return {
            "shares": 0,
            "position_value": 0.0,
            "risk_monetary": 0.0,
            "constraint_hit": reason,
            "r_fraction_realized": 0.0
        }

    def get_execution_plan(self, shares: int) -> Dict:
        """
        Execution Layer (Tiered Entry)
        Phase 1: 50% feeler
        Phase 2: Add remaining 50% only after confirmation
        """
        feeler = int(shares * 0.5)
        adds = shares - feeler
        return {
            "phase_1_feeler": feeler,
            "phase_2_confirmation": adds
        }
