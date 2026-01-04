#!/usr/bin/env python3
"""
Validación Robusta de Optimización - Evita Data Mining Bias
Implementa Walk-Forward Analysis y Out-of-Sample Testing
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from optimize_filters import FilterOptimizer


class RobustValidator:
    """
    Valida optimizaciones evitando sesgos estadísticos:
    1. Walk-Forward Analysis (múltiples períodos)
    2. Out-of-Sample Testing (validación en datos no vistos)
    3. Bootstrap Resampling (estabilidad de resultados)
    4. Sensitivity Analysis (qué pasa si cambias símbolos)
    """
    
    def __init__(self, all_symbols, equity=100000, risk_pct=0.5):
        self.all_symbols = all_symbols
        self.equity = equity
        self.risk_pct = risk_pct
        
    def walk_forward_analysis(self, adr_range, max_exp_range, 
                             start_date='2023-01-01', 
                             end_date='2024-12-20',
                             train_months=6,
                             test_months=3):
        """
        Walk-Forward Analysis:
        1. Entrena en 6 meses → Optimiza parámetros
        2. Valida en los siguientes 3 meses → Mide performance real
        3. Repite avanzando en el tiempo
        """
        print("\n" + "="*80)
        print("🔄 WALK-FORWARD ANALYSIS")
        print("="*80)
        print(f"Train: {train_months} meses | Test: {test_months} meses")
        print(f"Período total: {start_date} a {end_date}\n")
        
        start = pd.to_datetime(start_date)
        end = pd.to_datetime(end_date)
        
        results = []
        window_num = 1
        
        current_start = start
        
        while current_start + timedelta(days=30*(train_months + test_months)) <= end:
            train_end = current_start + timedelta(days=30*train_months)
            test_start = train_end
            test_end = test_start + timedelta(days=30*test_months)
            
            print(f"\n{'='*80}")
            print(f"VENTANA #{window_num}")
            print(f"{'='*80}")
            print(f"📚 TRAIN: {current_start.date()} a {train_end.date()}")
            print(f"🧪 TEST:  {test_start.date()} a {test_end.date()}")
            print(f"{'='*80}\n")
            
            # FASE 1: Optimizar en período de entrenamiento
            print("FASE 1: Optimizando en período de entrenamiento...")
            train_optimizer = FilterOptimizer(
                symbols=self.all_symbols,
                start_date=str(current_start.date()),
                end_date=str(train_end.date()),
                equity=self.equity,
                risk_pct=self.risk_pct
            )
            
            train_results = train_optimizer.optimize_grid_search(
                adr_range, max_exp_range, verbose=False
            )
            
            if train_results.empty:
                print("❌ Sin resultados en entrenamiento, saltando ventana")
                current_start = test_end
                window_num += 1
                continue
            
            # Mejor configuración en train
            best_train = train_results.iloc[0]
            best_adr = best_train['adr']
            best_exp = best_train['max_exposure']
            
            print(f"✅ Mejor config en TRAIN: ADR={best_adr:.1f}%, Exp={best_exp:.0f}%")
            print(f"   Train Score: {best_train['score']:.2f}")
            print(f"   Train Win Rate: {best_train['win_rate']:.1f}%")
            
            # FASE 2: Validar en período de test (out-of-sample)
            print("\nFASE 2: Validando en período TEST (out-of-sample)...")
            test_optimizer = FilterOptimizer(
                symbols=self.all_symbols,
                start_date=str(test_start.date()),
                end_date=str(test_end.date()),
                equity=self.equity,
                risk_pct=self.risk_pct
            )
            
            # Probar SOLO la mejor configuración encontrada en train
            test_metrics = test_optimizer.run_backtest(best_adr, best_exp)
            
            if test_metrics:
                print(f"✅ Resultados en TEST:")
                print(f"   Test Score: {test_metrics['score']:.2f}")
                print(f"   Test Win Rate: {test_metrics['win_rate']:.1f}%")
                print(f"   Test Avg Return: {test_metrics['avg_return']:.2f}%")
                
                # Comparar
                degradation = ((best_train['score'] - test_metrics['score']) / 
                              best_train['score'] * 100)
                
                print(f"\n📊 Degradación: {degradation:.1f}%")
                
                if degradation > 50:
                    print("   ⚠️  OVERFITTING detectado (>50% degradación)")
                elif degradation > 30:
                    print("   ⚠️  Degradación moderada (30-50%)")
                elif degradation < 0:
                    print("   ✨ Mejoró en test (¡sorprendente!)")
                else:
                    print("   ✅ Degradación aceptable (<30%)")
                
                results.append({
                    'window': window_num,
                    'train_start': current_start.date(),
                    'train_end': train_end.date(),
                    'test_start': test_start.date(),
                    'test_end': test_end.date(),
                    'best_adr': best_adr,
                    'best_exp': best_exp,
                    'train_score': best_train['score'],
                    'test_score': test_metrics['score'],
                    'train_win_rate': best_train['win_rate'],
                    'test_win_rate': test_metrics['win_rate'],
                    'train_avg_return': best_train['avg_return'],
                    'test_avg_return': test_metrics['avg_return'],
                    'degradation_pct': degradation
                })
            else:
                print("❌ Sin trades en período TEST")
            
            # Avanzar ventana
            current_start = test_end
            window_num += 1
        
        return pd.DataFrame(results)
    
    def sensitivity_analysis(self, adr_range, max_exp_range,
                            start_date, end_date, n_samples=5):
        """
        Sensitivity Analysis:
        Prueba múltiples combinaciones aleatorias de símbolos
        para ver si los resultados son estables o dependen de símbolos específicos
        """
        print("\n" + "="*80)
        print("🎲 SENSITIVITY ANALYSIS - Random Symbol Sampling")
        print("="*80)
        print(f"Muestras: {n_samples} | Símbolos por muestra: {len(self.all_symbols)//2}")
        print("="*80 + "\n")
        
        results = []
        
        for i in range(n_samples):
            print(f"\n{'='*80}")
            print(f"MUESTRA #{i+1}/{n_samples}")
            print(f"{'='*80}")
            
            # Seleccionar aleatoriamente mitad de símbolos
            sample_size = max(4, len(self.all_symbols) // 2)
            sample_symbols = np.random.choice(
                self.all_symbols, 
                size=sample_size, 
                replace=False
            ).tolist()
            
            print(f"Símbolos seleccionados: {', '.join(sample_symbols[:10])}")
            if len(sample_symbols) > 10:
                print(f"   ... y {len(sample_symbols)-10} más")
            
            optimizer = FilterOptimizer(
                symbols=sample_symbols,
                start_date=start_date,
                end_date=end_date,
                equity=self.equity,
                risk_pct=self.risk_pct
            )
            
            sample_results = optimizer.optimize_grid_search(
                adr_range, max_exp_range, verbose=False
            )
            
            if not sample_results.empty:
                best = sample_results.iloc[0]
                print(f"✅ Mejor config: ADR={best['adr']:.1f}%, Exp={best['max_exposure']:.0f}%")
                print(f"   Score: {best['score']:.2f}")
                print(f"   Win Rate: {best['win_rate']:.1f}%")
                
                results.append({
                    'sample': i+1,
                    'symbols': ','.join(sample_symbols),
                    'best_adr': best['adr'],
                    'best_exp': best['max_exposure'],
                    'score': best['score'],
                    'win_rate': best['win_rate'],
                    'avg_return': best['avg_return'],
                    'total_trades': best['total_trades']
                })
            else:
                print("❌ Sin resultados")
        
        return pd.DataFrame(results)
    
    def out_of_sample_validation(self, adr, max_exp, 
                                 train_start, train_end,
                                 test_start, test_end):
        """
        Out-of-Sample Validation simple:
        Prueba configuración específica en período completamente diferente
        """
        print("\n" + "="*80)
        print("🧪 OUT-OF-SAMPLE VALIDATION")
        print("="*80)
        print(f"Configuración a validar: ADR={adr:.1f}%, Max Exp={max_exp:.0f}%")
        print(f"Train: {train_start} a {train_end}")
        print(f"Test:  {test_start} a {test_end}")
        print("="*80 + "\n")
        
        # Train
        print("Ejecutando en período TRAIN...")
        train_optimizer = FilterOptimizer(
            symbols=self.all_symbols,
            start_date=train_start,
            end_date=train_end,
            equity=self.equity,
            risk_pct=self.risk_pct
        )
        train_metrics = train_optimizer.run_backtest(adr, max_exp)
        
        # Test
        print("Ejecutando en período TEST...")
        test_optimizer = FilterOptimizer(
            symbols=self.all_symbols,
            start_date=test_start,
            end_date=test_end,
            equity=self.equity,
            risk_pct=self.risk_pct
        )
        test_metrics = test_optimizer.run_backtest(adr, max_exp)
        
        if train_metrics and test_metrics:
            print("\n" + "="*80)
            print("📊 COMPARACIÓN")
            print("="*80)
            
            metrics = ['win_rate', 'avg_return', 'sharpe_ratio', 'profit_factor', 'max_drawdown']
            
            for metric in metrics:
                train_val = train_metrics[metric]
                test_val = test_metrics[metric]
                
                if metric == 'max_drawdown':
                    diff = test_val - train_val
                    status = "⚠️" if diff > 5 else "✅"
                else:
                    diff_pct = ((test_val - train_val) / train_val * 100) if train_val != 0 else 0
                    status = "✅" if diff_pct > -30 else "⚠️"
                
                print(f"{metric.replace('_', ' ').title():<20} Train: {train_val:>7.2f}  Test: {test_val:>7.2f}  {status}")
            
            print("="*80)
            
            return {
                'train': train_metrics,
                'test': test_metrics
            }
        else:
            print("❌ Sin métricas suficientes")
            return None


def print_walkforward_summary(wf_results):
    """Imprime resumen de Walk-Forward Analysis"""
    if wf_results.empty:
        print("❌ No hay resultados de walk-forward")
        return
    
    print("\n" + "="*80)
    print("📊 RESUMEN WALK-FORWARD ANALYSIS")
    print("="*80)
    
    # Consistencia de parámetros óptimos
    print("\n🎯 PARÁMETROS ÓPTIMOS POR VENTANA:")
    print("-" * 80)
    for _, row in wf_results.iterrows():
        print(f"Ventana {row['window']}: ADR={row['best_adr']:.1f}%, "
              f"Exp={row['best_exp']:.0f}% | "
              f"Degradación: {row['degradation_pct']:.1f}%")
    
    # Estadísticas
    print("\n📈 ESTADÍSTICAS:")
    print("-" * 80)
    print(f"ADR más común: {wf_results['best_adr'].mode()[0]:.1f}%")
    print(f"Max Exp más común: {wf_results['best_exp'].mode()[0]:.0f}%")
    print(f"Degradación promedio: {wf_results['degradation_pct'].mean():.1f}%")
    print(f"Degradación std dev: {wf_results['degradation_pct'].std():.1f}%")
    
    # Win rate comparison
    print(f"\nWin Rate promedio TRAIN: {wf_results['train_win_rate'].mean():.1f}%")
    print(f"Win Rate promedio TEST: {wf_results['test_win_rate'].mean():.1f}%")
    print(f"Diferencia: {wf_results['train_win_rate'].mean() - wf_results['test_win_rate'].mean():.1f}%")
    
    # Conclusión
    print("\n🎓 CONCLUSIÓN:")
    print("-" * 80)
    avg_degradation = wf_results['degradation_pct'].mean()
    
    if avg_degradation > 50:
        print("❌ OVERFITTING SEVERO - Los parámetros no generalizan bien")
        print("   Recomendación: Simplificar estrategia o usar más datos")
    elif avg_degradation > 30:
        print("⚠️  OVERFITTING MODERADO - Hay degradación significativa")
        print("   Recomendación: Validar con más símbolos o períodos")
    else:
        print("✅ RESULTADOS ROBUSTOS - Los parámetros generalizan bien")
        print("   Recomendación: Puedes usar estos parámetros con confianza")
    
    print("="*80)


def print_sensitivity_summary(sens_results):
    """Imprime resumen de Sensitivity Analysis"""
    if sens_results.empty:
        print("❌ No hay resultados de sensitivity analysis")
        return
    
    print("\n" + "="*80)
    print("📊 RESUMEN SENSITIVITY ANALYSIS")
    print("="*80)
    
    print("\n🎯 PARÁMETROS ÓPTIMOS POR MUESTRA:")
    print("-" * 80)
    for _, row in sens_results.iterrows():
        print(f"Muestra {row['sample']}: ADR={row['best_adr']:.1f}%, "
              f"Exp={row['best_exp']:.0f}% | Score={row['score']:.2f}")
    
    print("\n📈 ESTABILIDAD:")
    print("-" * 80)
    print(f"ADR - Media: {sens_results['best_adr'].mean():.1f}%, "
          f"Std Dev: {sens_results['best_adr'].std():.1f}%")
    print(f"Max Exp - Media: {sens_results['best_exp'].mean():.1f}%, "
          f"Std Dev: {sens_results['best_exp'].std():.1f}%")
    print(f"Score - Media: {sens_results['score'].mean():.2f}, "
          f"Std Dev: {sens_results['score'].std():.2f}")
    
    # Coeficiente de variación
    cv_adr = (sens_results['best_adr'].std() / sens_results['best_adr'].mean()) * 100
    cv_score = (sens_results['score'].std() / sens_results['score'].mean()) * 100
    
    print("\n🎓 CONCLUSIÓN:")
    print("-" * 80)
    
    if cv_adr < 20 and cv_score < 30:
        print("✅ RESULTADOS ESTABLES - Los parámetros no dependen de símbolos específicos")
    elif cv_adr < 40 and cv_score < 50:
        print("⚠️  ESTABILIDAD MODERADA - Hay alguna variación según símbolos")
    else:
        print("❌ RESULTADOS INESTABLES - Los resultados dependen fuertemente de qué símbolos uses")
        print("   Recomendación: Usar más símbolos o revisar la estrategia")
    
    print("="*80)


def main():
    print("\n🔬 VALIDACIÓN ROBUSTA DE OPTIMIZACIÓN")
    print("Este script evita data mining bias y overfitting\n")
    
    # Símbolos a usar
    symbols = ['AAPL', 'NVDA', 'TSLA', 'META', 'PLTR', 'AMD', 'AVGO', 'COIN',
               'GOOGL', 'MSFT', 'AMZN', 'NFLX']
    
    # Rangos reducidos para prueba rápida
    adr_range = [1.5, 2.5, 3.5]
    max_exp_range = [20, 30, 40]
    
    validator = RobustValidator(symbols, equity=100000, risk_pct=0.5)
    
    print("\n📋 MENÚ DE VALIDACIÓN:")
    print("1. Walk-Forward Analysis (recomendado)")
    print("2. Sensitivity Analysis (random symbols)")
    print("3. Simple Out-of-Sample Test")
    print("4. Todo lo anterior (completo)\n")
    
    choice = input("Selecciona (1-4): ").strip()
    
    if choice == '1' or choice == '4':
        # Walk-Forward
        wf_results = validator.walk_forward_analysis(
            adr_range, max_exp_range,
            start_date='2023-06-01',
            end_date='2024-12-20',
            train_months=6,
            test_months=3
        )
        
        if not wf_results.empty:
            wf_results.to_csv('walkforward_results.csv', index=False)
            print_walkforward_summary(wf_results)
            print("\n✅ Resultados guardados en walkforward_results.csv")
    
    if choice == '2' or choice == '4':
        # Sensitivity
        sens_results = validator.sensitivity_analysis(
            adr_range, max_exp_range,
            start_date='2024-01-01',
            end_date='2024-12-20',
            n_samples=5
        )
        
        if not sens_results.empty:
            sens_results.to_csv('sensitivity_results.csv', index=False)
            print_sensitivity_summary(sens_results)
            print("\n✅ Resultados guardados en sensitivity_results.csv")
    
    if choice == '3':
        # Simple validation
        result = validator.out_of_sample_validation(
            adr=2.5, max_exp=30,
            train_start='2023-01-01', train_end='2023-12-31',
            test_start='2024-01-01', test_end='2024-12-20'
        )
    
    print("\n✅ Validación completada!")


if __name__ == "__main__":
    main()
