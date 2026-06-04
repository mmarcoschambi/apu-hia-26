"""
Scanner Combo Adapter
=====================
Injects YAML combo parameters into the live scanner.

Usage:
    from config.scanner_combo_adapter import apply_combo_to_scanner
    
    # In live_scanner.py or app.py
    scanner = PatternScanner()
    scanner = apply_combo_to_scanner(scanner, combo_params)
"""

from __future__ import annotations

import logging
from typing import Any, Dict

logger = logging.getLogger(__name__)


def apply_combo_to_scanner(
    scanner: Any,
    combo_params: Dict[str, Any],
) -> Any:
    """
    Applies YAML combo parameters to a scanner instance.
    
    Args:
        scanner: Scanner instance (PatternScanner, LiveTradingScanner, etc.)
        combo_params: Dictionary of parameters from _yaml_combo_params
        
    Returns:
        Modified scanner instance
    """
    if not combo_params:
        logger.warning("No combo params provided, scanner unchanged")
        return scanner
    
    # Apply fee_rate and slippage_rate
    if 'fee_rate' in combo_params:
        if hasattr(scanner, 'fee_rate'):
            scanner.fee_rate = combo_params['fee_rate']
        else:
            setattr(scanner, 'fee_rate', combo_params['fee_rate'])
    
    if 'slippage_rate' in combo_params:
        if hasattr(scanner, 'slippage_rate'):
            scanner.slippage_rate = combo_params['slippage_rate']
        else:
            setattr(scanner, 'slippage_rate', combo_params['slippage_rate'])
    
    # Apply regime_blocked
    if 'regime_blocked' in combo_params:
        if hasattr(scanner, 'regime_blocked'):
            scanner.regime_blocked = combo_params['regime_blocked']
        else:
            setattr(scanner, 'regime_blocked', combo_params['regime_blocked'])
    
    # Apply scanner_filter
    if 'scanner_filter' in combo_params:
        if hasattr(scanner, 'scanner_filter'):
            scanner.scanner_filter = combo_params['scanner_filter']
        else:
            setattr(scanner, 'scanner_filter', combo_params['scanner_filter'])
    
    # Apply pattern_filter
    if 'pattern_filter' in combo_params:
        if hasattr(scanner, 'pattern_filter'):
            scanner.pattern_filter = combo_params['pattern_filter']
        else:
            setattr(scanner, 'pattern_filter', combo_params['pattern_filter'])
    
    # Apply lookback_days
    if 'lookback_days' in combo_params:
        if hasattr(scanner, 'lookback_days'):
            scanner.lookback_days = combo_params['lookback_days']
        else:
            setattr(scanner, 'lookback_days', combo_params['lookback_days'])
    
    # Apply max_setups
    if 'max_setups' in combo_params:
        if hasattr(scanner, 'max_setups'):
            scanner.max_setups = combo_params['max_setups']
        else:
            setattr(scanner, 'max_setups', combo_params['max_setups'])
    
    logger.info(
        f"Applied combo params to scanner: "
        f"fee={combo_params.get('fee_rate', 0)*10000:.0f}bps, "
        f"slippage={combo_params.get('slippage_rate', 0)*10000:.0f}bps, "
        f"filter={combo_params.get('scanner_filter', 'default')}"
    )
    
    return scanner


def calculate_effective_entry_price(
    base_price: float,
    fee_rate: float = 0.001,
    slippage_rate: float = 0.001,
) -> float:
    """
    Calculates effective entry price including fees and slippage.
    
    Args:
        base_price: Raw entry price from signal
        fee_rate: Commission fee rate (e.g., 0.001 = 10bps)
        slippage_rate: Estimated slippage rate
        
    Returns:
        Effective entry price after costs
    """
    total_cost_rate = fee_rate + slippage_rate
    return base_price * (1 + total_cost_rate)


def calculate_adjusted_pnl(
    entry_price: float,
    exit_price: float,
    quantity: int,
    fee_rate: float = 0.001,
    slippage_rate: float = 0.001,
    direction: str = "long",
) -> float:
    """
    Calculates P&L adjusted for fees and slippage on both entry and exit.
    
    Args:
        entry_price: Entry price
        exit_price: Exit price
        quantity: Number of shares
        fee_rate: Commission fee rate per side
        slippage_rate: Slippage rate per side
        direction: "long" or "short"
        
    Returns:
        Net P&L after all costs
    """
    # Entry costs
    entry_cost = entry_price * quantity * (fee_rate + slippage_rate)
    
    # Exit costs
    exit_cost = exit_price * quantity * (fee_rate + slippage_rate)
    
    # Gross P&L
    if direction == "long":
        gross_pnl = (exit_price - entry_price) * quantity
    else:  # short
        gross_pnl = (entry_price - exit_price) * quantity
    
    # Net P&L
    net_pnl = gross_pnl - entry_cost - exit_cost
    
    return net_pnl


def is_regime_blocked(
    regime_status: int,
    regime_blocked: list[int],
) -> bool:
    """
    Determines if trading should be blocked based on market regime.
    
    Args:
        regime_status: Current regime status (e.g., 1=bull, 2=neutral, 3=bear, 4=crash)
        regime_blocked: List of regime statuses that block trading
        
    Returns:
        True if trading is blocked, False otherwise
    """
    return regime_status in regime_blocked


if __name__ == "__main__":
    # Test the adapter
    logging.basicConfig(level=logging.INFO)
    
    # Test effective entry price
    base_price = 150.0
    effective = calculate_effective_entry_price(base_price, 0.001, 0.001)
    print(f"Base: ${base_price:.2f} -> Effective: ${effective:.2f} (cost: ${effective-base_price:.2f})")
    
    # Test adjusted P&L
    pnl = calculate_adjusted_pnl(150.0, 155.0, 100, 0.001, 0.001)
    print(f"P&L: ${pnl:.2f} (gross would be ${(155-150)*100:.2f})")
    
    # Test blocked mask
    blocked = is_regime_blocked(3, [3, 4])
    print(f"Regime 3 blocked by [3,4]: {blocked}")
    
    blocked = is_regime_blocked(1, [3, 4])
    print(f"Regime 1 blocked by [3,4]: {blocked}")
