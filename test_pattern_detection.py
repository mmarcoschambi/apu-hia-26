#!/usr/bin/env python3
"""
Test Script para Pattern Detection Engine
==========================================
Prueba la detección de patrones en símbolos específicos
"""

import sys
from pathlib import Path
project_root = Path(__file__).resolve().parent
sys.path.insert(0, str(project_root))

from openbb import obb
import pandas as pd
from src.indicators.pattern_detection import PatternDetectionEngine, PatternType
from src.core.pattern_screener import export_pattern_analysis

def test_symbol(symbol: str, start_date: str = '2023-01-01'):
    """Prueba detección de patrones en un símbolo"""
    
    print(f"\n{'='*70}")
    print(f"TESTING PATTERN DETECTION: {symbol}")
    print(f"{'='*70}\n")
    
    try:
        # Cargar datos
        print(f"📊 Loading data for {symbol}...")
        data = obb.equity.price.historical(
            symbol=symbol,
            start_date=start_date,
            provider='yfinance'
        ).to_df()
        
        if data.empty:
            print(f"❌ No data available for {symbol}")
            return
        
        print(f"✅ Loaded {len(data)} bars")
        first_date = data.index[0] if hasattr(data.index[0], 'date') else data.index[0]
        last_date = data.index[-1] if hasattr(data.index[-1], 'date') else data.index[-1]
        print(f"   Date range: {first_date} to {last_date}")
        print(f"   Current price: ${data['close'].iloc[-1]:.2f}")
        print()
        
        # Crear engine
        engine = PatternDetectionEngine(symbol, data)
        
        # Escanear patrones
        print(f"🔍 Scanning for patterns...")
        patterns = engine.scan_all_patterns()
        
        if not patterns:
            print(f"❌ No institutional patterns detected")
            return
        
        print(f"✅ Found {len(patterns)} pattern(s)\n")
        
        # Mostrar cada patrón
        for i, pattern in enumerate(patterns, 1):
            print(f"{'-'*70}")
            print(f"PATTERN #{i}: {pattern.pattern_type.value}")
            print(f"{'-'*70}")
            print(f"✓ Detected: {'YES' if pattern.detected else 'NO'}")
            print(f"✓ Confidence: {pattern.confidence:.1%}")
            print(f"✓ Reasoning: {pattern.reasoning}")
            print()
            
            if pattern.entry_price:
                print(f"📍 Entry: ${pattern.entry_price:.2f}")
            if pattern.stop_loss:
                print(f"🛑 Stop: ${pattern.stop_loss:.2f}")
                if pattern.entry_price:
                    risk_pct = ((pattern.entry_price - pattern.stop_loss) / pattern.entry_price) * 100
                    r_value = (pattern.entry_price - pattern.stop_loss)
                    print(f"⚖️  Risk: {risk_pct:.1f}% (${r_value:.2f})")
            
            if pattern.pivot_price:
                print(f"🎯 Pivot: ${pattern.pivot_price:.2f}")
            
            if pattern.base_depth:
                print(f"📏 Base Depth: {pattern.base_depth:.1f}%")
            
            if pattern.base_length > 0:
                weeks = pattern.base_length / 5
                print(f"📅 Base Length: {pattern.base_length} days ({weeks:.1f} weeks)")
            
            print()
            
            # Características específicas
            if pattern.characteristics:
                print(f"📊 Pattern Characteristics:")
                for key, value in pattern.characteristics.items():
                    if key in ['contractions', 'depths', 'volume_ratios']:
                        continue  # Skip complex structures in console
                    
                    if isinstance(value, float):
                        if 'pct' in key or 'ratio' in key:
                            print(f"   • {key}: {value:.2f}")
                        else:
                            print(f"   • {key}: ${value:.2f}")
                    elif isinstance(value, bool):
                        print(f"   • {key}: {'YES' if value else 'NO'}")
                    elif isinstance(value, (int, str)):
                        print(f"   • {key}: {value}")
            
            print()
        
        # Exportar análisis completo
        output_file = f"pattern_analysis_{symbol}.txt"
        export_pattern_analysis(symbol, data, output_file)
        print(f"📄 Full analysis exported to: {output_file}")
        
    except Exception as e:
        print(f"❌ Error testing {symbol}: {e}")
        import traceback
        traceback.print_exc()


def test_multiple_symbols():
    """Prueba múltiples símbolos conocidos por tener patrones"""
    
    # Símbolos con patrones históricos conocidos
    test_cases = [
        ("NVDA", "2023-01-01"),  # High Tight Flag histórico
        ("SMCI", "2023-06-01"),  # Multiple patterns
        ("TSLA", "2023-01-01"),  # VCP patterns
        ("SHOP", "2023-01-01"),  # Cup & Handle
        ("ROKU", "2023-01-01"),  # Various bases
    ]
    
    for symbol, start_date in test_cases:
        test_symbol(symbol, start_date)
        print("\n" * 2)


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Test Pattern Detection Engine')
    parser.add_argument('--symbol', type=str, help='Symbol to test (e.g., NVDA)')
    parser.add_argument('--start', type=str, default='2023-01-01', help='Start date')
    parser.add_argument('--all', action='store_true', help='Test multiple symbols')
    
    args = parser.parse_args()
    
    if args.all:
        test_multiple_symbols()
    elif args.symbol:
        test_symbol(args.symbol, args.start)
    else:
        # Default: test single symbol
        test_symbol("NVDA", "2023-01-01")
