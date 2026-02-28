#!/usr/bin/env python3
"""
Multi-Backtest Optimizer
========================
Ejecuta múltiples backtests con diferentes combinaciones de parámetros
y encuentra la configuración óptima basada en métricas reales.

VENTAJAS sobre Post-Mortem:
- ✅ Prueba rangos completos (no solo más restrictivo)
- ✅ Métricas REALES de cada configuración
- ✅ Puede optimizar cualquier parámetro
- ✅ Resultados más confiables

PRECAUCIÓN:
- ⚠️  Puede tomar tiempo (N configs × 30 seg cada una)
- ⚠️  Riesgo de overfitting con demasiadas combinaciones
- 💡 Usa grid pequeño (3-4 valores por parámetro)

Uso:
    # Optimización rápida (grid pequeño)
    python3 run_multi_backtest_optimization.py --mode quick
    
    # Optimización completa (grid grande)
    python3 run_multi_backtest_optimization.py --mode full
    
    # Optimización custom
    python3 run_multi_backtest_optimization.py --params params.json
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import pandas as pd
import numpy as np
from datetime import datetime
import itertools
import argparse
import json
import time
from typing import Dict, List, Tuple

from src.backtest.vectorbt_engine_advanced import AdvancedVectorBTEngine
from src.analytics.quantstats_analyzer import TradeGrouper


class MultiBacktestOptimizer:
    """
    Ejecuta múltiples backtests con diferentes parámetros
    y compara resultados para encontrar configuración óptima.
    """
    
    def __init__(self, 
                 universe: List[str],
                 start_date: str,
                 end_date: str,
                 output_dir: str = 'outputs/optimization'):
        
        self.universe = universe
        self.start_date = start_date
        self.end_date = end_date
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True, parents=True)
        
        self.results = []
    
    def define_parameter_grid(self, mode='quick'):
        """
        Define grid de parámetros a optimizar.
        
        mode='quick': Grid pequeño (~10-20 combinaciones, ~5-10 min)
        mode='full': Grid completo (~50-100 combinaciones, ~30-60 min)
        """
        
        if mode == 'quick':
            # Grid pequeño para optimización rápida
            param_grid = {
                'min_rvol': [1.0, 1.5, 2.0],
                'max_dist_sma20': [7.0, 10.0],
                'min_adr': [1.0, 1.5],
                'min_consolidation': [5, 10, 15],
            }
            # 3 × 2 × 2 × 3 = 36 combinaciones
            
        elif mode == 'full':
            # Grid completo para optimización exhaustiva
            param_grid = {
                'min_rvol': [1.0, 1.3, 1.5, 1.8, 2.0],
                'max_dist_sma20': [5.0, 7.0, 10.0, 12.0],
                'min_adr': [1.0, 1.5, 2.0],
                'min_consolidation': [5, 10, 15, 20],
                'max_stop_pct': [6.0, 8.0, 10.0],
            }
            # 5 × 4 × 3 × 4 × 3 = 720 combinaciones (muy lento!)
            
        else:
            raise ValueError(f"Mode '{mode}' no reconocido. Usa 'quick' o 'full'")
        
        return param_grid
    
    def generate_combinations(self, param_grid: Dict) -> List[Dict]:
        """Genera todas las combinaciones de parámetros."""
        
        keys = list(param_grid.keys())
        values = list(param_grid.values())
        
        combinations = []
        for combo in itertools.product(*values):
            config = dict(zip(keys, combo))
            combinations.append(config)
        
        return combinations
    
    def run_single_backtest(self, config: Dict) -> Dict:
        """
        Ejecuta un backtest con una configuración específica.
        Retorna métricas del resultado.
        """
        
        print(f"\n{'='*80}")
        print(f"🔄 Running backtest con configuración:")
        for k, v in config.items():
            print(f"   {k}: {v}")
        print(f"{'='*80}")
        
        start_time = time.time()
        
        try:
            # Crear engine con estos parámetros
            engine = AdvancedVectorBTEngine(
                universe=self.universe,
                start_date=self.start_date,
                end_date=self.end_date,
                
                # Parámetros del grid
                min_rvol=config.get('min_rvol', 1.5),
                max_dist_sma20=config.get('max_dist_sma20', 10.0),
                min_adr=config.get('min_adr', 1.5),
                max_stop_pct=config.get('max_stop_pct', 8.0),
                
                # Parámetros fijos (no optimizar por ahora)
                risk_dollars=150.0,
                initial_capital=100000,
                use_earnings_calendar=True,
                offline_mode=True,
            )
            
            # Ejecutar backtest
            results = engine.run()
            
            # Agrupar trades parciales en trades completos
            if 'trade_log' in results and len(results['trade_log']) > 0:
                complete_trades = TradeGrouper.group_partial_trades(results['trade_log'])
                
                # Calcular métricas
                winners = complete_trades[complete_trades['r_multiple'] > 0]
                losers = complete_trades[complete_trades['r_multiple'] <= 0]
                
                win_rate = len(winners) / len(complete_trades) if len(complete_trades) > 0 else 0
                avg_r = complete_trades['r_multiple'].mean()
                
                gross_win = winners['total_pnl'].sum() if len(winners) > 0 else 0
                gross_loss = abs(losers['total_pnl'].sum()) if len(losers) > 0 else 0
                profit_factor = gross_win / gross_loss if gross_loss > 0 else 0
                
                total_pnl = complete_trades['total_pnl'].sum()
                
                # Calcular Sharpe (aproximado)
                daily_returns = complete_trades.set_index('entry_date')['total_pnl'].resample('D').sum()
                sharpe = (daily_returns.mean() / daily_returns.std() * np.sqrt(252)) if daily_returns.std() > 0 else 0
                
                metrics = {
                    'config': config,
                    'total_trades': len(complete_trades),
                    'win_rate': win_rate,
                    'avg_r': avg_r,
                    'profit_factor': profit_factor,
                    'total_pnl': total_pnl,
                    'sharpe': sharpe,
                    'gross_win': gross_win,
                    'gross_loss': gross_loss,
                    'avg_win': winners['total_pnl'].mean() if len(winners) > 0 else 0,
                    'avg_loss': losers['total_pnl'].mean() if len(losers) > 0 else 0,
                    'max_win': complete_trades['total_pnl'].max() if len(complete_trades) > 0 else 0,
                    'max_loss': complete_trades['total_pnl'].min() if len(complete_trades) > 0 else 0,
                    'success': True,
                    'error': None,
                }
                
            else:
                # No trades
                metrics = {
                    'config': config,
                    'total_trades': 0,
                    'win_rate': 0,
                    'avg_r': 0,
                    'profit_factor': 0,
                    'total_pnl': 0,
                    'sharpe': 0,
                    'success': False,
                    'error': 'No trades generated',
                }
            
        except Exception as e:
            print(f"❌ Error en backtest: {e}")
            metrics = {
                'config': config,
                'success': False,
                'error': str(e),
            }
        
        elapsed = time.time() - start_time
        metrics['elapsed_seconds'] = elapsed
        
        print(f"\n✅ Backtest completado en {elapsed:.1f}s")
        if metrics['success']:
            print(f"   Trades: {metrics['total_trades']}")
            print(f"   Win Rate: {metrics['win_rate']*100:.1f}%")
            print(f"   Profit Factor: {metrics['profit_factor']:.2f}")
            print(f"   Avg R: {metrics['avg_r']:.2f}R")
        else:
            print(f"   ❌ {metrics.get('error', 'Unknown error')}")
        
        return metrics
    
    def run_optimization(self, param_grid: Dict) -> pd.DataFrame:
        """
        Ejecuta optimización completa con todas las combinaciones.
        """
        
        combinations = self.generate_combinations(param_grid)
        
        print("="*80)
        print("🚀 MULTI-BACKTEST OPTIMIZATION")
        print("="*80)
        print(f"Parameter Grid:")
        for k, v in param_grid.items():
            print(f"  {k}: {v}")
        print(f"\nTotal Combinaciones: {len(combinations)}")
        print(f"Tiempo Estimado: ~{len(combinations) * 30 / 60:.1f} minutos")
        print("="*80)
        
        # Ejecutar todos los backtests
        for i, config in enumerate(combinations, 1):
            print(f"\n[{i}/{len(combinations)}] Ejecutando configuración {i}...")
            
            metrics = self.run_single_backtest(config)
            self.results.append(metrics)
            
            # Save intermediate results (por si falla)
            self.save_results(intermediate=True)
        
        # Convertir a DataFrame
        results_df = self.create_results_dataframe()
        
        # Guardar resultados finales
        self.save_results(intermediate=False)
        
        return results_df
    
    def create_results_dataframe(self) -> pd.DataFrame:
        """Convierte resultados a DataFrame para análisis."""
        
        # Expand config dict into columns
        rows = []
        for result in self.results:
            row = result.copy()
            config = row.pop('config', {})
            row.update(config)
            rows.append(row)
        
        df = pd.DataFrame(rows)
        
        # Ordenar por profit factor (descendente)
        if 'profit_factor' in df.columns:
            df = df.sort_values('profit_factor', ascending=False)
        
        return df
    
    def save_results(self, intermediate=False):
        """Guarda resultados en CSV."""
        
        df = self.create_results_dataframe()
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        if intermediate:
            filename = f"optimization_intermediate_{timestamp}.csv"
        else:
            filename = f"optimization_results_{timestamp}.csv"
        
        output_path = self.output_dir / filename
        df.to_csv(output_path, index=False)
        
        if not intermediate:
            print(f"\n✅ Resultados guardados en: {output_path}")
    
    def print_top_results(self, df: pd.DataFrame, n=5):
        """Imprime top N configuraciones."""
        
        print("\n" + "="*80)
        print(f"🏆 TOP {n} CONFIGURACIONES")
        print("="*80)
        
        # Filtrar solo backtests exitosos
        successful = df[df['success'] == True].copy()
        
        if len(successful) == 0:
            print("❌ No se encontraron backtests exitosos")
            return
        
        # Mostrar top N
        for i, (idx, row) in enumerate(successful.head(n).iterrows(), 1):
            print(f"\n#{i} - Profit Factor: {row['profit_factor']:.2f}")
            print(f"   Trades: {row['total_trades']:.0f}")
            print(f"   Win Rate: {row['win_rate']*100:.1f}%")
            print(f"   Avg R: {row['avg_r']:.2f}R")
            print(f"   Total PnL: ${row['total_pnl']:.2f}")
            print(f"   Sharpe: {row['sharpe']:.2f}")
            
            print(f"   Parámetros:")
            param_cols = ['min_rvol', 'max_dist_sma20', 'min_adr', 'min_consolidation', 'max_stop_pct']
            for col in param_cols:
                if col in row:
                    print(f"     {col}: {row[col]}")


def load_universe(file_path='data/universe.csv'):
    """Carga universo de tickers."""
    try:
        df = pd.read_csv(file_path)
        return df['ticker'].tolist()
    except:
        # Universo por defecto pequeño para pruebas
        return ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'META', 'TSLA', 'NVDA', 'JPM']


def main():
    parser = argparse.ArgumentParser(description='Multi-Backtest Optimizer')
    parser.add_argument('--mode', type=str, default='quick', 
                       choices=['quick', 'full'],
                       help='Optimization mode (quick=fast, full=exhaustive)')
    parser.add_argument('--universe-file', type=str, default='data/universe.csv',
                       help='Path to universe CSV')
    parser.add_argument('--start-date', type=str, default='2020-01-01',
                       help='Backtest start date (YYYY-MM-DD)')
    parser.add_argument('--end-date', type=str, default='2023-12-31',
                       help='Backtest end date (YYYY-MM-DD)')
    
    args = parser.parse_args()
    
    # Load universe
    universe = load_universe(args.universe_file)
    print(f"📊 Universo cargado: {len(universe)} tickers")
    
    # Create optimizer
    optimizer = MultiBacktestOptimizer(
        universe=universe,
        start_date=args.start_date,
        end_date=args.end_date,
    )
    
    # Define parameter grid
    param_grid = optimizer.define_parameter_grid(mode=args.mode)
    
    # Run optimization
    results_df = optimizer.run_optimization(param_grid)
    
    # Print top results
    optimizer.print_top_results(results_df, n=5)
    
    print("\n" + "="*80)
    print("✅ OPTIMIZACIÓN COMPLETADA")
    print("="*80)
    print(f"\nResultados guardados en: outputs/optimization/")
    print(f"Total configuraciones probadas: {len(results_df)}")
    print(f"Configuraciones exitosas: {len(results_df[results_df['success']==True])}")
    
    # Best config
    best = results_df[results_df['success']==True].iloc[0] if len(results_df[results_df['success']==True]) > 0 else None
    if best is not None:
        print(f"\n🏆 MEJOR CONFIGURACIÓN:")
        print(f"   Profit Factor: {best['profit_factor']:.2f}")
        print(f"   Win Rate: {best['win_rate']*100:.1f}%")
        print(f"   Avg R: {best['avg_r']:.2f}R")
        
        param_cols = ['min_rvol', 'max_dist_sma20', 'min_adr', 'min_consolidation', 'max_stop_pct']
        print(f"\n   Parámetros óptimos:")
        for col in param_cols:
            if col in best:
                print(f"     {col}: {best[col]}")


if __name__ == '__main__':
    main()
