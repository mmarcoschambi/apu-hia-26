#!/usr/bin/env python3
"""
Quick Analysis - Single Symbol
Usage: python3 quick_analysis.py SYMBOL
"""
import sys
from pathlib import Path

project_root = Path(__file__).resolve().parent
sys.path.insert(0, str(project_root))

from src.core.scanner import TriadScanner
from src.utils.risk_calculator import RiskCalculator


def analyze_symbol(symbol: str, account_size: float = 100000):
    """Analyze a single symbol with full details"""
    
    scanner = TriadScanner()
    calc = RiskCalculator()
    
    print(f"\n{'='*80}")
    print(f"TRIAD ANALYSIS: {symbol.upper()}")
    print(f"{'='*80}\n")
    
    result = scanner.scan_symbol(symbol.upper())
    
    if not result.get('signal'):
        print(f"❌ Error analyzing {symbol}")
        return
    
    signal = result['signal']
    
    print(f"🎯 SIGNAL")
    print(f"  Camino: {signal.camino.name if signal.camino else 'N/A'}")
    print(f"  Action: {signal.action}")
    
    if signal.entry_price and signal.stop_loss:
        print(f"\n💰 PRICES")
        print(f"  Entry: ${signal.entry_price:.2f}")
        print(f"  Stop:  ${signal.stop_loss:.2f}")
        print(f"  Risk:  ${signal.entry_price - signal.stop_loss:.2f} per share")
        
        # Calculate position size
        risk_pct = 0.005 if signal.position_size_multiplier == 1.0 else 0.0025
        
        pos_result = calc.calculate_position_size(
            account_size=account_size,
            risk_pct=risk_pct,
            entry_price=signal.entry_price,
            stop_loss=signal.stop_loss,
            multiplier=signal.position_size_multiplier
        )
        
        if 'error' not in pos_result:
            print(f"\n📊 POSITION SIZING (${account_size:,.0f} account)")
            print(f"  Shares: {pos_result['shares']}")
            print(f"  Capital: ${pos_result['capital_required']:,.2f}")
            print(f"  Risk Amount: ${pos_result['risk_amount']:.2f}")
            print(f"  Risk %: {pos_result['risk_pct']:.2f}%")
            print(f"\n🎯 PROFIT TARGETS")
            print(f"  1R: ${pos_result['risk_reward_1to1']:.2f}")
            print(f"  2R: ${pos_result['risk_reward_2to1']:.2f}")
            print(f"  3R: ${pos_result['risk_reward_3to1']:.2f}")
    
    print(f"\n📝 REASONING")
    print(f"  {signal.reasoning}")
    
    # Additional context
    if result.get('base_data', {}).get('detected'):
        base = result['base_data']
        print(f"\n📦 BASE STRUCTURE")
        print(f"  High: ${base['base_high']:.2f}")
        print(f"  Low:  ${base['base_low']:.2f}")
        print(f"  Compression: {base['compression_pct']*100:.1f}%")
    
    if result.get('avwap_data', {}).get('calculated'):
        avwap = result['avwap_data']
        print(f"\n🚧 AVWAP (Tollbooth)")
        print(f"  ATH: ${avwap['ath_price']:.2f} ({avwap['ath_date'].date()})")
        print(f"  AVWAP: ${avwap['current_avwap']:.2f}")
        print(f"  Distance: {avwap['distance_to_avwap_pct']*100:.1f}%")
    
    if result.get('market_context', {}).get('spy_gap_pct') is not None:
        ctx = result['market_context']
        print(f"\n📈 MARKET CONTEXT")
        print(f"  SPY: {ctx.get('spy_change_pct', 0)*100:.2f}%")
        print(f"  QQQ: {ctx.get('qqq_change_pct', 0)*100:.2f}%")
        print(f"  Weak: {'Yes' if ctx.get('market_weak') else 'No'}")
    
    print(f"\n{'='*80}\n")


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 quick_analysis.py SYMBOL [ACCOUNT_SIZE]")
        print("Example: python3 quick_analysis.py RDDT 100000")
        sys.exit(1)
    
    symbol = sys.argv[1]
    account_size = float(sys.argv[2]) if len(sys.argv) > 2 else 100000
    
    analyze_symbol(symbol, account_size)


if __name__ == "__main__":
    main()
