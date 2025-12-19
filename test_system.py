"""
Quick Test Script - Verify Triad System
"""
import sys
from pathlib import Path

project_root = Path(__file__).resolve().parent
sys.path.insert(0, str(project_root))

from src.core.scanner import TriadScanner


def quick_test():
    """Quick test with example symbols"""
    print("Initializing Triad Scanner...")
    scanner = TriadScanner()
    
    # Test with a single symbol first
    test_symbol = "AAPL"
    print(f"\nTesting with {test_symbol}...")
    
    result = scanner.scan_symbol(test_symbol)
    
    if result.get('signal'):
        print(f"\n✓ System working! Signal generated for {test_symbol}")
    else:
        print(f"\n✓ System working! No setup detected for {test_symbol}")
    
    print("\nTest complete. Check logs/ directory for details.")


if __name__ == "__main__":
    quick_test()
