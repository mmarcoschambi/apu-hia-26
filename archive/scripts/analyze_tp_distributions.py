#!/usr/bin/env python3
"""
TP DISTRIBUTION ANALYZER
========================

Analiza el impacto de diferentes distribuciones de TP en el Alpha capturado.

Simula escenarios de trades ganadores con diferentes distribuciones.
"""

import pandas as pd
import numpy as np


def calculate_realized_r(distribution: dict, exit_prices_r: list) -> float:
    """
    Calcula el R realizado dado una distribución y precios de salida.
    
    Args:
        distribution: Dict con 'tp1_pct', 'tp2_pct', 'runner_pct'
        exit_prices_r: Lista de [tp1_r, tp2_r, runner_r]
    
    Returns:
        Total R realizado
    """
    tp1_r, tp2_r, runner_r = exit_prices_r
    
    realized_r = (
        distribution['tp1_pct'] * tp1_r +
        distribution['tp2_pct'] * tp2_r +
        distribution['runner_pct'] * runner_r
    )
    
    return realized_r


def analyze_distributions():
    """Compara distribuciones en diferentes escenarios."""
    
    print("\n" + "="*80)
    print("📊 TP DISTRIBUTION IMPACT ANALYSIS")
    print("="*80)
    print("\nComparing how different distributions capture Alpha in various scenarios\n")
    
    # Distribuciones a comparar
    distributions = {
        'Classic (50/30/20)': {'tp1_pct': 0.50, 'tp2_pct': 0.30, 'runner_pct': 0.20},
        'Balanced (33/33/34)': {'tp1_pct': 0.33, 'tp2_pct': 0.33, 'runner_pct': 0.34},
        'Aggressive (25/30/45)': {'tp1_pct': 0.25, 'tp2_pct': 0.30, 'runner_pct': 0.45},
        'Conservative (40/35/25)': {'tp1_pct': 0.40, 'tp2_pct': 0.35, 'runner_pct': 0.25},
    }
    
    # Escenarios de trade
    scenarios = [
        {
            'name': 'Small Winner',
            'description': 'TP1 hit only (1.5R)',
            'exits': [1.5, 0, 0]  # Solo TP1
        },
        {
            'name': 'Medium Winner',
            'description': 'TP2 hit (3R)',
            'exits': [1.5, 3.0, 0]  # TP1 + TP2
        },
        {
            'name': 'Big Winner',
            'description': 'Runner hits 6R',
            'exits': [1.5, 3.0, 6.0]  # TP1 + TP2 + 6R runner
        },
        {
            'name': 'Home Run',
            'description': 'Runner hits 10R',
            'exits': [1.5, 3.0, 10.0]  # TP1 + TP2 + 10R runner
        },
        {
            'name': 'Moonshot',
            'description': 'Runner hits 20R (TSLA/GME style)',
            'exits': [1.5, 3.0, 20.0]  # TP1 + TP2 + 20R runner
        }
    ]
    
    # Tabla de resultados
    results = []
    
    for scenario in scenarios:
        print(f"\n{'─'*80}")
        print(f"📈 Scenario: {scenario['name']} - {scenario['description']}")
        print(f"{'─'*80}")
        
        scenario_results = {'Scenario': scenario['name']}
        
        for dist_name, dist in distributions.items():
            realized_r = calculate_realized_r(dist, scenario['exits'])
            scenario_results[dist_name] = f"{realized_r:.2f}R"
            print(f"  {dist_name:<25} → {realized_r:6.2f}R")
        
        results.append(scenario_results)
    
    # Summary table
    print("\n" + "="*80)
    print("📊 SUMMARY: R Captured by Distribution")
    print("="*80)
    
    df = pd.DataFrame(results)
    print(df.to_string(index=False))
    
    # Calculate differences
    print("\n" + "="*80)
    print("💡 ALPHA DIFFERENCE vs Classic (50/30/20)")
    print("="*80)
    print("\nCuánto Alpha EXTRA capturas con cada distribución:\n")
    
    for scenario in scenarios:
        classic_r = calculate_realized_r(distributions['Classic (50/30/20)'], scenario['exits'])
        
        print(f"{scenario['name']:<20}:", end=" ")
        
        for dist_name, dist in distributions.items():
            if dist_name == 'Classic (50/30/20)':
                continue
            
            realized_r = calculate_realized_r(dist, scenario['exits'])
            diff = realized_r - classic_r
            pct_diff = (diff / classic_r * 100) if classic_r > 0 else 0
            
            print(f"{dist_name.split()[0]:<15} +{diff:4.2f}R ({pct_diff:+5.1f}%)", end="  ")
        
        print()
    
    # Recommendations
    print("\n" + "="*80)
    print("🎯 RECOMMENDATIONS")
    print("="*80)
    print("""
1. Para sistemas MOMENTUM (breakouts):
   ✅ Use AGGRESSIVE (25/30/45)
   - Los grandes ganadores generan TODO el Alpha
   - Necesitas dejar correr más % para capturarlos
   - Ejemplo: Si tienes 1 trade de 20R, capturas 9.0R vs 5.65R (59% más!)

2. Para sistemas MEAN REVERSION:
   ✅ Use CONSERVATIVE (40/35/25)
   - Los movimientos son más acotados
   - Es mejor asegurar ganancias rápido

3. Para OPTIMIZAR científicamente:
   ✅ Use '--tp-preset optimize' en dual_validation
   - Deja que Optuna encuentre lo óptimo para TU universo
   - Cada mercado/timeframe puede tener distribución óptima diferente

4. Si NO sabes cuál usar:
   ✅ Empieza con BALANCED (33/33/33)
   - Es un buen punto medio
   - Luego experimenta con aggressive_runner si ves muchos big winners
""")
    
    print("="*80)


if __name__ == '__main__':
    analyze_distributions()
