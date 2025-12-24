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
                 buying_power: Optional[float] = None,
                 allow_fractional_shares: bool = True):
        """
        Initialize the Risk Manager.

        Args:
            account_equity: Total account equity (NAV).
            risk_fraction: Fraction of equity to risk per trade (e.g., 0.005 for 0.5%).
            max_exposure_fraction: Hard cap on nominal exposure per single asset (e.g., 0.25 for 25%).
            buying_power: Available buying power. Defaults to account_equity if None (Cash account).
            allow_fractional_shares: Enable fractional shares for small accounts (default: True).
        """
        self.account_equity = account_equity
        self.risk_fraction = risk_fraction
        self.max_exposure_fraction = max_exposure_fraction
        self.buying_power = buying_power if buying_power is not None else account_equity
        self.allow_fractional_shares = allow_fractional_shares

    def calculate_position_size(self, 
                                entry_price: float, 
                                stop_price: float, 
                                adr_percent: float,
                                avg_daily_volume: int,
                                market_regime_factor: float = 1.0) -> Dict:
        """
        Calculate the optimal position size based on risk parameters.

        Args:
            entry_price: Planned entry price.
            stop_price: Technical invalidation point (structural stop).
            adr_percent: Average Daily Range percentage (REQUIRED for volatility-based exposure).
            avg_daily_volume: Average daily volume in shares (REQUIRED for liquidity check).
            market_regime_factor: Risk scaler {1.0, 0.5, 0.0}.

        Returns:
            Dictionary containing sizing details: shares, position_value, risk_monetary, constraints_hit.
        """
        
        # 1. Market Regime Scaling (Institutional Standard)
        # risk_on -> 1.0, risk_off -> 0.5, no_trade -> 0.0
        if market_regime_factor <= 0:
             return self._zero_allocation("Market Regime / Factor 0")

        # 2. Small Account Constraint (<25k)
        # Low-ADR assets become capital-inefficient. Enforce ADR >= 4% rule.
        if self.account_equity < 25000 and adr_percent < 4.0:
            return self._zero_allocation("Small Account / Low ADR")
        
        # --- MODIFICACIÓN 1: STOP LOSS SANITY CHECK (Anti-Bagholding) ---
        # Rechazar trades con stops demasiado amplios (ineficientes)
        stop_loss_pct = abs(entry_price - stop_price) / entry_price
        MAX_ALLOWED_STOP_PCT = 0.08  # 8% Hard Cap institucional
        
        if stop_loss_pct > MAX_ALLOWED_STOP_PCT:
            logger.warning(f"Trade Rejected: Stop Loss of {stop_loss_pct:.2%} exceeds max allowed {MAX_ALLOWED_STOP_PCT:.2%}")
            return self._zero_allocation(f"Stop Loss too wide ({stop_loss_pct:.2%} > {MAX_ALLOWED_STOP_PCT:.2%})")

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
        
        # Soporte para acciones fraccionadas en cuentas pequeñas
        if self.allow_fractional_shares and self.account_equity < 25000:
            # Para cuentas pequeñas, permitir fracciones con 3 decimales
            shares = round(raw_shares, 3)
            # Mínimo: $25 de capital o 0.001 shares (lo que sea mayor)
            min_position_value = 25.0
            min_shares = max(0.001, min_position_value / entry_price)
            
            if shares < min_shares:
                return self._zero_allocation(f"Position too small (${shares * entry_price:.2f} < ${min_position_value})")
        else:
            # Cuentas grandes: solo acciones enteras
            shares = int(raw_shares)
            
            if shares <= 0:
                return self._zero_allocation("Risk too small for 1 share")

        # 6. Nominal Capital Required
        # position_value = shares * entry_price
        position_value = shares * entry_price
        
        constraint_hit = None

        # 7. Hard Risk Constraints
        
        # --- MODIFICACIÓN 2: EXPOSICIÓN DINÁMICA basada en VOLATILIDAD (ADR Tiering) ---
        # Si la acción es muy volátil (ADR > 5%), reducimos exposición máxima a la mitad
        if adr_percent > 5.0:
            dynamic_max_exposure = self.max_exposure_fraction * 0.5  # Ej: 25% -> 12.5%
            limit_reason = "High Volatility Cap"
        else:
            dynamic_max_exposure = self.max_exposure_fraction
            limit_reason = "Standard Cap"
        
        max_nominal_exposure = self.account_equity * dynamic_max_exposure
        
        # Constraint A: Buying Power
        if position_value > self.buying_power:
            if self.allow_fractional_shares and self.account_equity < 25000:
                shares = round(self.buying_power / entry_price, 3)
            else:
                shares = int(self.buying_power / entry_price)
            position_value = shares * entry_price
            constraint_hit = "Buying Power"

        # Constraint B: Max Exposure Fraction (Dynamic)
        if position_value > max_nominal_exposure:
            if self.allow_fractional_shares and self.account_equity < 25000:
                shares = round(max_nominal_exposure / entry_price, 3)
            else:
                shares = int(max_nominal_exposure / entry_price)
            position_value = shares * entry_price
            constraint_hit = limit_reason
        
        # --- MODIFICACIÓN 3: FILTRO DE LIQUIDEZ (No seas la Ballena) ---
        # Nunca ser más del 1% del volumen diario promedio (ADV)
        # Para cuentas pequeñas con fracciones, permitir fracciones en el límite de liquidez
        if self.allow_fractional_shares and self.account_equity < 25000:
            max_shares_liquidity = round(avg_daily_volume * 0.01, 3)
        else:
            max_shares_liquidity = int(avg_daily_volume * 0.01)
        
        if shares > max_shares_liquidity:
            shares = max_shares_liquidity
            position_value = shares * entry_price
            constraint_hit = f"Liquidity Constrained (Max 1% of ADV: {avg_daily_volume:,})"

        # Recalculate actual risk after constraints (Risk may decrease, never increase)
        actual_risk = shares * per_share_risk
        
        # Determinar si es posición fraccionada
        is_fractional = (shares % 1 != 0) if isinstance(shares, float) else False
        
        return {
            "shares": shares,
            "position_value": position_value,
            "risk_monetary": actual_risk,
            "entry_price": entry_price,
            "stop_price": stop_price,
            "r_fraction_realized": actual_risk / self.account_equity,
            "constraint_hit": constraint_hit,
            "regime_factor": market_regime_factor,
            "is_fractional": is_fractional
        }

    def _zero_allocation(self, reason: str) -> Dict:
        return {
            "shares": 0,
            "position_value": 0.0,
            "risk_monetary": 0.0,
            "constraint_hit": reason,
            "r_fraction_realized": 0.0
        }

    def get_execution_plan(self, shares: float) -> Dict:
        """
        Execution Layer (Tiered Entry)
        Phase 1: 50% feeler
        Phase 2: Add remaining 50% only after confirmation
        
        Soporta acciones fraccionadas para cuentas pequeñas.
        """
        is_fractional = isinstance(shares, float) and shares % 1 != 0
        
        if is_fractional:
            # Para fracciones, mantener precisión de 3 decimales
            feeler = round(shares * 0.5, 3)
            adds = round(shares - feeler, 3)
        else:
            # Para enteros, usar lógica tradicional
            feeler = int(shares * 0.5)
            adds = shares - feeler
            
        return {
            "phase_1_feeler": feeler,
            "phase_2_confirmation": adds,
            "is_fractional": is_fractional
        }
