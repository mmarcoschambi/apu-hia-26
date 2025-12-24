#!/usr/bin/env python3
"""
Encuentra el MEJOR punto de equilibrio entre ADR y Max Exposure
Combina optimize_filters.py + validate_optimization.py

FLUJO:
1. Optimiza en período completo → Genera heatmap
2. Toma los TOP 10 mejores parámetros
3. Valida cada uno con Walk-Forward Analysis
4. Encuentra el que tiene MENOR DEGRADACIÓN (más robusto)
"""

import pandas as pd
import numpy as np
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from optimize_filters import FilterOptimizer
from validate_optimization import RobustValidator


def find_sweet_spot(symbols, start_date, end_date, 
                   adr_range, max_exp_range,
                   equity=100000, risk_pct=0.5):
    """
    Encuentra el punto óptimo considerando:
    - Performance (Score alto)
    - Robustez (Baja degradación en walk-forward)
    - Consistencia (Funciona en diferentes períodos)
    """
    
    print("\n" + "="*80)
    print("🎯 BÚSQUEDA DEL PUNTO ÓPTIMO DE EQUILIBRIO")
    print("="*80)
    print(f"Período: {start_date} a {end_date}")
    print(f"Símbolos: {len(symbols)}")
    print(f"ADR Range: {adr_range}")
    print(f"Max Exp Range: {max_exp_range}")
    print("="*80 + "\n")
    
    # =========================================================================
    # PASO 1: OPTIMIZACIÓN INICIAL (Encontrar mejores parámetros)
    # =========================================================================
    print("📊 PASO 1: Optimización Inicial (Grid Search)")
    print("-" * 80)
    
    optimizer = FilterOptimizer(
        symbols=symbols,
        start_date=start_date,
        end_date=end_date,
        equity=equity,
        risk_pct=risk_pct
    )
    
    initial_results = optimizer.optimize_grid_search(adr_range, max_exp_range, verbose=True)
    
    if initial_results.empty:
        print("❌ No se encontraron resultados en optimización inicial")
        return None
    
    # Guardar y mostrar
    initial_results.to_csv('step1_initial_optimization.csv', index=False)
    optimizer.plot_heatmap()
    
    print("\n✅ Heatmap generado: optimization_heatmap.html")
    print("✅ Resultados guardados: step1_initial_optimization.csv\n")
    
    # Filtrar solo combinaciones con score positivo y suficientes trades
    profitable = initial_results[
        (initial_results['score'] > 0) & 
        (initial_results['total_trades'] >= 20)
    ].copy()
    
    if profitable.empty:
        print("⚠️  No hay combinaciones rentables. Usando todas para validación...")
        candidates = initial_results.head(10)
    else:
        # TOP 10 mejores
        candidates = profitable.head(10)
    
    print(f"🎯 Candidatos seleccionados para validación: {len(candidates)}")
    print("-" * 80)
    for idx, row in candidates.iterrows():
        print(f"  ADR={row['adr']:.1f}%, Exp={row['max_exposure']:.0f}% | "
              f"Score={row['score']:.2f}, WR={row['win_rate']:.1f}%, "
              f"Trades={row['total_trades']}")
    print()
    
    # =========================================================================
    # PASO 2: VALIDACIÓN WALK-FORWARD (Robustez en el tiempo)
    # =========================================================================
    print("\n📈 PASO 2: Validación Walk-Forward (Robustez temporal)")
    print("-" * 80)
    print("Probando cada candidato en múltiples ventanas de tiempo...\n")
    
    validator = RobustValidator(symbols, equity=equity, risk_pct=risk_pct)
    
    validation_results = []
    
    for idx, candidate in candidates.iterrows():
        adr = candidate['adr']
        max_exp = candidate['max_exposure']
        
        print(f"\n🔍 Validando: ADR={adr:.1f}%, Exp={max_exp:.0f}%")
        print("-" * 60)
        
        # Validar con out-of-sample split (70% train / 30% test)
        train_end_date = pd.to_datetime(start_date) + pd.Timedelta(days=int((pd.to_datetime(end_date) - pd.to_datetime(start_date)).days * 0.7))
        
        result = validator.out_of_sample_validation(
            adr=adr,
            max_exp=max_exp,
            train_start=start_date,
            train_end=str(train_end_date.date()),
            test_start=str(train_end_date.date()),
            test_end=end_date
        )
        
        if result:
            train_metrics = result['train']
            test_metrics = result['test']
            
            # Calcular degradación
            degradation_pct = ((train_metrics['score'] - test_metrics['score']) / train_metrics['score'] * 100) if train_metrics['score'] != 0 else 0
            
            validation_results.append({
                'adr': adr,
                'max_exposure': max_exp,
                'train_score': train_metrics['score'],
                'test_score': test_metrics['score'],
                'degradation_pct': degradation_pct,
                'train_win_rate': train_metrics['win_rate'],
                'test_win_rate': test_metrics['win_rate'],
                'train_trades': train_metrics['total_trades'],
                'test_trades': test_metrics['total_trades'],
                # Métricas combinadas
                'avg_score': (train_metrics['score'] + test_metrics['score']) / 2,
                'robustness_score': 100 - abs(degradation_pct)  # Menor degradación = más robusto
            })
            
            print(f"  Train: Score={train_metrics['score']:.2f}, WR={train_metrics['win_rate']:.1f}%")
            print(f"  Test:  Score={test_metrics['score']:.2f}, WR={test_metrics['win_rate']:.1f}%")
            print(f"  Degradación: {degradation_pct:.1f}%")
    
    if not validation_results:
        print("\n❌ No se pudo validar ningún candidato")
        return None
    
    validation_df = pd.DataFrame(validation_results)
    validation_df.to_csv('step2_validation_results.csv', index=False)
    
    print("\n✅ Validación completada: step2_validation_results.csv\n")
    
    # =========================================================================
    # PASO 3: ANÁLISIS FINAL (Encontrar el mejor balance)
    # =========================================================================
    print("\n🏆 PASO 3: Análisis Final - Mejor Balance")
    print("=" * 80)
    
    # Calcular score final considerando:
    # 1. Performance promedio (avg_score)
    # 2. Robustez (robustness_score)
    # 3. Consistencia (menor diferencia entre train y test)
    
    validation_df['final_score'] = (
        validation_df['avg_score'] * 0.5 +  # 50% peso a performance
        validation_df['robustness_score'] * 0.5  # 50% peso a robustez
    )
    
    # Ordenar por score final
    validation_df = validation_df.sort_values('final_score', ascending=False)
    
    print("\n🎖️  TOP 5 MEJORES BALANCES:")
    print("-" * 80)
    for i, row in validation_df.head(5).iterrows():
        print(f"\n#{i+1}. ADR={row['adr']:.1f}%, Max Exp={row['max_exposure']:.0f}%")
        print(f"    Final Score: {row['final_score']:.2f}")
        print(f"    Avg Score: {row['avg_score']:.2f} | Robustness: {row['robustness_score']:.1f}")
        print(f"    Degradación: {row['degradation_pct']:.1f}%")
        print(f"    Train: Score={row['train_score']:.2f}, WR={row['train_win_rate']:.1f}%, Trades={row['train_trades']}")
        print(f"    Test:  Score={row['test_score']:.2f}, WR={row['test_win_rate']:.1f}%, Trades={row['test_trades']}")
    
    # GANADOR
    winner = validation_df.iloc[0]
    
    print("\n" + "="*80)
    print("🥇 CONFIGURACIÓN ÓPTIMA RECOMENDADA")
    print("="*80)
    print(f"\n✨ ADR: {winner['adr']:.1f}%")
    print(f"✨ Max Exposure: {winner['max_exposure']:.0f}%")
    print(f"\n📊 Por qué es la mejor:")
    print(f"   • Score promedio: {winner['avg_score']:.2f}")
    print(f"   • Robustez: {winner['robustness_score']:.1f}/100")
    print(f"   • Degradación: {winner['degradation_pct']:.1f}% (cuanto menor, mejor)")
    print(f"   • Win Rate promedio: {(winner['train_win_rate'] + winner['test_win_rate'])/2:.1f}%")
    
    if abs(winner['degradation_pct']) < 20:
        print(f"\n✅ EXCELENTE: Degradación < 20% - Parámetros muy robustos")
    elif abs(winner['degradation_pct']) < 40:
        print(f"\n⚠️  ACEPTABLE: Degradación < 40% - Parámetros moderadamente robustos")
    else:
        print(f"\n⚠️  CUIDADO: Degradación > 40% - Posible overfitting")
    
    print("\n" + "="*80)
    
    # Guardar resultado final
    validation_df.to_csv('step3_final_ranking.csv', index=False)
    print("\n✅ Ranking final guardado: step3_final_ranking.csv")
    
    return winner


def main():
    print("\n🎯 FIND OPTIMAL BALANCE - ADR vs MAX EXPOSURE")
    print("Encuentra el mejor punto de equilibrio validando robustez\n")
    
    # Configuración
    symbols = [
        'AAPL', 'NVDA', 'TSLA', 'META', 'PLTR', 'AMD', 'AVGO', 'COIN',
        'GOOGL', 'MSFT', 'AMZN', 'NFLX', 'CRM', 'ORCL', 'ADBE', 'QCOM'
    ]
    
    # Rangos a probar (más granular para mejor precisión)
    adr_range = [1.5, 2.0, 2.5, 3.0, 3.5, 4.0]
    max_exp_range = [20, 25, 30, 35, 40]
    
    # Período de análisis
    start_date = '2024-01-01'
    end_date = '2024-12-20'
    
    print("⚙️  CONFIGURACIÓN:")
    print(f"   Símbolos: {len(symbols)}")
    print(f"   ADR range: {adr_range}")
    print(f"   Max Exp range: {max_exp_range}")
    print(f"   Combinaciones: {len(adr_range) * len(max_exp_range)}")
    print(f"   Período: {start_date} a {end_date}\n")
    
    response = input("¿Continuar? (y/n): ").strip()
    if response.lower() != 'y':
        print("❌ Cancelado")
        return
    
    # Ejecutar búsqueda
    winner = find_sweet_spot(
        symbols=symbols,
        start_date=start_date,
        end_date=end_date,
        adr_range=adr_range,
        max_exp_range=max_exp_range,
        equity=100000,
        risk_pct=0.5
    )
    
    if winner is not None:
        print("\n✅ Proceso completado!")
        print("\n📁 Archivos generados:")
        print("   1. step1_initial_optimization.csv - Resultados de grid search")
        print("   2. optimization_heatmap.html - Visualización interactiva")
        print("   3. step2_validation_results.csv - Validación de candidatos")
        print("   4. step3_final_ranking.csv - Ranking final con scores")
        print("\n💡 Usa los parámetros ganadores en tu config/filters.json")
    else:
        print("\n❌ No se pudo completar el proceso")


if __name__ == "__main__":
    main()
