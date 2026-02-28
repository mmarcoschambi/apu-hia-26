#!/usr/bin/env python3
"""
EXAMPLE: Using Custom TP Distribution in Production
====================================================

Muestra cómo usar distribuciones custom de TP en backtests de producción.
"""

import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from src.backtest.vectorbt_engine_advanced import AdvancedVectorBTEngine


def example_1_balanced():
    """Ejemplo 1: Distribución balanceada (33/33/33)"""
    print("\n" + "="*70)
    print("📊 EXAMPLE 1: Balanced Distribution (33/33/33)")
    print("="*70)
    print("Use case: Cuando NO sabes qué distribución es mejor\n")
    
    engine = AdvancedVectorBTEngine(
        universe=['AAPL', 'MSFT', 'GOOGL', 'NVDA'],
        start_date='2023-01-01',
        end_date='2024-12-31',
        tp1_pct=0.33,
        tp2_pct=0.33,
        runner_pct=0.34
    )
    
    result = engine.run_backtest()
    
    print(f"Sharpe: {result['sharpe_ratio']:.3f}")
    print(f"Return: {result['total_return']*100:.2f}%")
    print(f"Trades: {result['total_trades']}")
    print(f"Win Rate: {result['win_rate']*100:.1f}%")


def example_2_aggressive():
    """Ejemplo 2: Distribución agresiva para momentum"""
    print("\n" + "="*70)
    print("🚀 EXAMPLE 2: Aggressive Runner (25/30/45)")
    print("="*70)
    print("Use case: Sistema de breakouts momentum - busca home runs\n")
    
    engine = AdvancedVectorBTEngine(
        universe=['AAPL', 'MSFT', 'GOOGL', 'NVDA'],
        start_date='2023-01-01',
        end_date='2024-12-31',
        tp1_pct=0.25,  # Solo asegura 25% rápido
        tp2_pct=0.30,  # 30% en objetivo medio
        runner_pct=0.45  # 45% busca home runs!
    )
    
    result = engine.run_backtest()
    
    print(f"Sharpe: {result['sharpe_ratio']:.3f}")
    print(f"Return: {result['total_return']*100:.2f}%")
    print(f"Trades: {result['total_trades']}")
    print(f"Win Rate: {result['win_rate']*100:.1f}%")


def example_3_load_optimized():
    """Ejemplo 3: Cargar parámetros optimizados de dual validation"""
    print("\n" + "="*70)
    print("🔬 EXAMPLE 3: Loading Optimized TP Distribution")
    print("="*70)
    print("Use case: Usar parámetros encontrados por walk_forward\n")
    
    # Cargar parámetros validados
    config_file = Path('config/validated_production_params.json')
    
    if not config_file.exists():
        print("⚠️  No optimized params found. Run dual_validation first:")
        print("   bash run_dual_validation.sh --tp-preset optimize")
        return
    
    with open(config_file, 'r') as f:
        config = json.load(f)
    
    params = config['recommended_params']
    
    # Mostrar distribución optimizada
    tp1 = params.get('tp1_pct', 0.5)
    tp2 = params.get('tp2_pct', 0.3)
    runner = params.get('runner_pct', 0.2)
    
    print(f"Optimized Distribution: {tp1*100:.0f}% / {tp2*100:.0f}% / {runner*100:.0f}%")
    
    # Usar en backtest
    engine = AdvancedVectorBTEngine(
        universe=['AAPL', 'MSFT', 'GOOGL', 'NVDA'],
        start_date='2023-01-01',
        end_date='2024-12-31',
        **params  # Incluye tp1_pct, tp2_pct, runner_pct
    )
    
    result = engine.run_backtest()
    
    print(f"\nSharpe: {result['sharpe_ratio']:.3f}")
    print(f"Return: {result['total_return']*100:.2f}%")
    print(f"Trades: {result['total_trades']}")


if __name__ == '__main__':
    print("\n" + "="*70)
    print("🎯 TP DISTRIBUTION EXAMPLES")
    print("="*70)
    print("\nShowing how to use custom TP distributions in production...")
    
    example_1_balanced()
    example_2_aggressive()
    example_3_load_optimized()
    
    print("\n" + "="*70)
    print("💡 RECOMMENDATION")
    print("="*70)
    print("""
Para sistemas de MOMENTUM/BREAKOUT:
  1. Usa aggressive_runner (25/30/45) como baseline
  2. O ejecuta optimize para encontrar la distribución óptima
  3. NO uses classic (50/30/20) - mata el Alpha!

Para encontrar distribución óptima:
  bash run_dual_validation.sh --tp-preset optimize
""")
    print("="*70 + "\n")
