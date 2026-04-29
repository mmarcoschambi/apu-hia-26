import pandas as pd
import numpy as np
from typing import Dict
import logging

# Configurar paths
from pathlib import Path
import sys
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from src.backtest.optimization_engine_thor import OptimizationEngineTHOR

logger = logging.getLogger(__name__)

# 2023 Fallback parameters (funcionan en otros años)
params_2023 = {
    # Entradas más permisivas
    'min_rvol': 1.0,
    'min_adr': 1.5,
    'min_volume': 100000,
    'min_dollar_volume': 1_000_000,
    
    # Calidad más permisiva
    'max_dist_sma20': 20.0,
    'max_consolidation_range': 30.0,
    'min_consolidation_days': 3,
    
    # Targets más agresivos
    'tp1_r': 1.25,
    'tp2_r': 2.5,
    'stop_atr_mult': 1.0,
    
    # Exits 3-phase como Chiron
    'use_phases': True,
    'tp1_r': 1.5,
    'tp2_r': 3.0,
    
    # Posicionamiento
    'risk_dollars': 150,
    'max_stop_pct': 0.10,
    'max_exposure_pct': 0.30,
    
    # Filtros de mercado más permisivos
    'use_phases': True,
    'require_bullish_spy': False,
    'require_sma_trend': False,
    'max_vix': 50.0,
}

# Grid search parameters
grid_search = {
    'min_rvol': [0.8, 1.0, 1.2],
    'min_adr': [1.0, 1.5, 2.0],
    'min_consolidation_days': [3, 5, 7],
    'max_dist_sma20': [10.0, 15.0, 20.0],
    'tp1_r': [1.25, 1.5, 1.75],
    'stop_atr_mult': [0.8, 1.0, 1.2],
}

def run_grid_search(year=2023, max_iterations=30):
    """Ejecutar grid search para encontrar parámetros óptimos"""
    
    print(f"\n{'='*80}")
    print(f"🔬 GRID SEARCH 2023 - Encontrando parámetros óptimos")
    print(f"{'='*80}")
    
    results = []
    combinations = 0
    
    for rvol in grid_search['min_rvol']:
        for adr in grid_search['min_adr']:
            for consol in grid_search['min_consolidation_days']:
                for dist in grid_search['max_dist_sma20']:
                    for tp1 in grid_search['tp1_r']:
                        params = params_2023.copy()
                        params['min_rvol'] = rvol
                        params['min_adr'] = adr
                        params['min_consolidation_days'] = consol
                        params['max_dist_sma20'] = dist
                        params['tp1_r'] = tp1
                        
                        try:
                            engine = OptimizationEngineTHOR(
                                tickers=['AAPL', 'MSFT', 'GOOGL', 'NVDA', 'AMD', 'TSLA', 'META', 'AMZN', 'NFLX'],
                                start_date=f'{year}-01-01',
                                end_date=f'{year}-12-31',
                                use_float32=True,
                                chunk_size=50
                            )
                            
                            result = engine.backtest(params)
                            results.append({
                                'params': params,
                                'result': result,
                                'combo': combinations,
                                'rvol': rvol,
                                'adr': adr,
                                'consol': consol,
                                'dist': dist,
                                'tp1': tp1,
                            })
                            combinations += 1
                            
                            # Log cada 10 combinaciones
                            if combinations % 10 == 0:
                                print(f"   Combinations tested: {combinations}")
                            
                        except Exception as e:
                            logger.error(f"Error en combo rvol={rvol}, adr={adr}, consol={consol}: {e}")
                            continue
                        
                        if combinations >= max_iterations:
                            print(f"\n⏹ Max iterations reached: {max_iterations}")
                            break
                    if combinations >= max_iterations:
                        break
                if combinations >= max_iterations:
                    break
            if combinations >= max_iterations:
                break
        if combinations >= max_iterations:
            break
    
    # Analizar resultados
    if results:
        df = pd.DataFrame(results)
        
        # Filtrar solo con trades significativos (> 10)
        df_valid = df[df['result'].apply(lambda x: x.get('total_trades', 0) > 10)].copy()
        
        if len(df_valid) == 0:
            print("\n❌ No valid results found!")
            return None
        
        # Ordenar por MAR Ratio
        df_valid['mar_ratio'] = df_valid['result'].apply(lambda x: x.get('mar_ratio', 0))
        df_sorted = df_valid.sort_values('mar_ratio', ascending=False)
        
        print(f"\n📊 TOP 10 COMBINACIONES POR MAR RATIO:")
        print(f"{'='*100}")
        print(f"{'='*100}")
        
        for i, (_, row) in enumerate(df_sorted.head(10).iterrows()):
            print(f"\n#{i+1} MAR={row['mar_ratio']:.2f}, Trades={row['result']['total_trades']}")
            print(f"   RVOL: {row['rvol']}, ADR: {row['adr']:.1f}%")
            print(f"   Consol: {row['consol']}d, Dist: {row['dist']}%")
            print(f"   TP1: {row['tp1']}R, Return: {row['result']['total_return_pct']:.1f}%")
            print(f"   Sharpe: {row['result']['sharpe_ratio']:.2f}")
            print(f"   Max DD: {row['result']['max_drawdown_pct']:.1f}%")
        
        # Mejor resultado completo
        best = df_sorted.iloc[0]
        print(f"\n🏆 MEJOR PARÁMETRO:")
        print(f"{'='*100}")
        print(f"   RVOL: {best['rvol']}")
        print(f"   ADR: {best['adr']:.1f}%")
        print(f"   Consolidation Days: {best['consol']}")
        print(f"   Max Dist SMA20: {best['dist']}%")
        print(f"   TP1: {best['tp1']}R")
        print(f"   MAR Ratio: {best['mar_ratio']:.2f}")
        print(f"   Sharpe: {best['result']['sharpe_ratio']:.2f}")
        print(f"   Total Return: {best['result']['total_return_pct']:.1f}%")
        print(f"   Total Trades: {best['result']['total_trades']}")
        print(f"   Win Rate: {best['result']['win_rate_pct']:.1f}%")
        print(f"   Max DD: {best['result']['max_drawdown_pct']:.1f}%")
        
        return best['params']
    else:
        print("\n❌ No results found!")
        return None


def main():
    best_params = run_grid_search(year=2023, max_iterations=50)
    
    if best_params:
        print(f"\n💾 Saving best parameters to outputs/2023_best_params.json")
        
        import json
        with open('outputs/2023_best_params.json', 'w') as f:
            json.dump(best_params, f, indent=2)
        
        print(f"\n📋 PRÓXIMO PASO: Aplicar parámetros a universo completo 5375 tickers")
        print(f"   • Si funciona, extender a 2017-2021")
        print(f"   • Si no, ajustar parámetros y volver a buscar")
    else:
        print("\n❌ No parameters found!")


if __name__ == "__main__":
    main()
