#!/usr/bin/env python3
"""
Example: Scan watchlist for Triad setups
Customize your symbols and run daily pre-market or during market hours
"""
import sys
from pathlib import Path

project_root = Path(__file__).resolve().parent
sys.path.insert(0, str(project_root))

from src.core.scanner import TriadScanner


def main():
    """
    Main scanner - customize your watchlist here
    """
    # Initialize scanner
    scanner = TriadScanner()
    
    # YOUR WATCHLIST - Edit this list with your symbols
    watchlist = [
        'AAPL',
        'GOOGL',
        'MSFT',
        'NVDA',
        'META',# Example: Blue Sky candidate
    ]
    
    print(f"\n{'='*80}")
    print(f"TRIAD MOMENTUM SCANNER - {len(watchlist)} symbols")
    print(f"{'='*80}\n")
    
    # Scan the watchlist
    results = scanner.scan_watchlist(watchlist)
    
    # Filter for actionable setups
    actionable = [
        r for r in results 
        if r.get('signal') and r['signal'].action in ['BUY_STOP', 'MANUAL_WATCH']
    ]
    
    # Print actionable summary
    if actionable:
        print(f"\n{'='*80}")
        print("ACTIONABLE SETUPS")
        print(f"{'='*80}\n")
        
        for r in actionable:
            signal = r['signal']
            symbol = r['symbol']
            
            print(f"\n{symbol} - {signal.camino.name if signal.camino else 'N/A'}")
            print(f"  Action: {signal.action}")
            
            if signal.entry_price:
                print(f"  Entry: ${signal.entry_price:.2f}")
            
            if signal.stop_loss:
                print(f"  Stop: ${signal.stop_loss:.2f}")
                if signal.entry_price:
                    risk_pct = (signal.entry_price - signal.stop_loss) / signal.entry_price * 100
                    print(f"  Risk: {risk_pct:.2f}%")
            
            print(f"  Size: {signal.position_size_multiplier*100:.0f}%")
            print(f"  Reason: {signal.reasoning[:80]}...")
    else:
        print("\n⚠️  No actionable setups found in current watchlist.")
        print("This is normal - the system is disciplined and waits for high-probability setups.")
    
    print(f"\n{'='*80}")
    print("Check logs/ directory for detailed analysis")
    print(f"{'='*80}\n")


if __name__ == "__main__":
    main()
