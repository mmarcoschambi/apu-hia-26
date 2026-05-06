"""
Verification script for the Extension Gate (Monster Stock Stage limit)
"""
import sys
from pathlib import Path

project_root = Path(__file__).resolve().parent
sys.path.insert(0, str(project_root))

from src.strategies.triad_protocol import TriadStrategy, Camino

def test_extension_gate():
    strategy = TriadStrategy(max_extension_pct=0.0677)
    
    # CASE 1: Within limit (6%)
    base_data = {'detected': True, 'base_high': 100.0, 'base_low': 95.0, 'current_price': 106.0}
    avwap_data = {'calculated': True, 'current_avwap': 101.0, 'distance_to_avwap_pct': -0.01}
    market_context = {'trend_sma': 'Strong', 'rvol': 2.0}
    
    signal = strategy.analyze(base_data, avwap_data, {}, {}, market_context, 5.0)
    print(f"CASE 1 (6% Extension): {signal.action} - Reasoning: {signal.reasoning}")
    assert signal.action == 'BUY_STOP' or signal.action == 'MANUAL_WATCH' or signal.action == 'NO_SETUP' # Depends on other factors but NOT Extension Gate
    if signal.context.get('rejection_reason') == 'Extension_Gate':
        print("FAIL: Should not be rejected by Extension Gate at 6%")
    else:
        print("PASS: Not rejected by Extension Gate at 6%")

    # CASE 2: Over limit (8%)
    base_data = {'detected': True, 'base_high': 100.0, 'base_low': 95.0, 'current_price': 108.0}
    signal = strategy.analyze(base_data, avwap_data, {}, {}, market_context, 5.0)
    print(f"CASE 2 (8% Extension): {signal.action} - Reasoning: {signal.reasoning}")
    if signal.context.get('rejection_reason') == 'Extension_Gate':
        print("PASS: Correctly rejected by Extension Gate at 8%")
    else:
        print("FAIL: Should be rejected by Extension Gate at 8%")

if __name__ == "__main__":
    test_extension_gate()
