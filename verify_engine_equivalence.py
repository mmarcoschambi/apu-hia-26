#!/usr/bin/env python3
"""
VERIFICACIÓN DE EQUIVALENCIA DE MOTORES
=======================================
Compara resultados entre:
1. AdvancedVectorBTEngine (Producción/Lento)
2. OptimizationEngineV6_PRO (Optimización/Bugatti)

Objetivo: Garantizar que la optimización rápida produce parámetros válidos para producción.
"""

import logging
import pandas as pd
import numpy as np
import sys
from pathlib import Path

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger("EquivalenceTest")

sys.path.insert(0, str(Path(__file__).resolve().parent))

from src.backtest.vectorbt_engine_advanced import AdvancedVectorBTEngine
from src.backtest.optimization_engine_v6_pro import OptimizationEngineV6_PRO

def run_comparison():
    # 1. Configuración Común
    tickers = ['AAPL', 'MSFT', 'NVDA', 'TSLA', 'AMD']
    start_date = '2022-01-01'
    end_date = '2023-01-01'
    
    params = {
        'initial_capital': 100000,
        'risk_dollars': 100,
        'min_volume': 100000,
        'min_dollar_volume': 1000000,
        'min_rvol': 1.0,
        'min_adr': 1.5,
        'max_dist_sma20': 50.0, # Permisivo para asegurar trades
        'max_stop_pct': 10.0,
        'use_phases': True,      # CRÍTICO: Advanced siempre usa fases
        'min_consolidation_days': 0,
        
        # PARAMETROS DE CONVERGENCIA
        'use_dynamic_thresholds': False, # Desactivar VIX overrides en Advanced
        'use_dynamic_stop': False,       # Desactivar Stop Dinámico en V6_PRO (usar fijo)
        
        # Desactivar filtros extraños para comparación pura
        'require_sector_strength': False,
        'use_composite_sector_scoring': False,
        'require_positive_rs': False,
        'require_spy_above_sma50': False, 
        'use_market_regime_filter': False,
        'use_adaptive_filtering': False
    }
    
    logger.info("="*60)
    logger.info("⚖️  INICIANDO TEST DE CONVERGENCIA")
    logger.info("="*60)
    logger.info(f"Tickers: {tickers}")
    logger.info(f"Periodo: {start_date} a {end_date}")
    
    # 2. Correr Motor ADVANCED (La referencia)
    logger.info("\n🐢 Ejecutando ADVANCED Engine (Referencia)...")
    adv_engine = AdvancedVectorBTEngine(
        universe=tickers,
        start_date=start_date,
        end_date=end_date,
        offline_mode=True, # Usar datos cacheados
        **params
    )
    # Force load data explicitamente para asegurar cache
    adv_engine.load_data()
    adv_results = adv_engine.run_backtest()
    
    # 3. Correr Motor V6_PRO (El Bugatti)
    logger.info("\n🐇 Ejecutando V6_PRO Engine (Bugatti)...")
    pro_engine = OptimizationEngineV6_PRO(
        tickers=tickers,
        start_date=start_date,
        end_date=end_date,
        initial_capital=100000,
        offline_mode=True
    )
    # V6 Pro carga datos en init, corremos backtest directo
    pro_results = pro_engine.backtest(params)
    
    # 4. Comparar Métricas
    logger.info("\n" + "="*60)
    logger.info("📊 COMPARACIÓN DE RESULTADOS")
    logger.info("="*60)
    
    metrics = ['total_trades', 'total_return', 'sharpe_ratio', 'win_rate', 'max_drawdown']
    
    match = True
    
    print(f"{'Métrica':<20} | {'Advanced':<15} | {'V6_PRO':<15} | {'Dif %':<10}")
    print("-" * 65)
    
    for m in metrics:
        val_adv = adv_results.get(m, 0)
        val_pro = pro_results.get(m, 0)
        
        # Manejar None o NaN
        if pd.isna(val_adv): val_adv = 0.0
        if pd.isna(val_pro): val_pro = 0.0
        
        # Calcular diferencia
        if val_adv == 0 and val_pro == 0:
            diff = 0.0
        elif val_adv == 0:
            diff = 100.0
        else:
            diff = abs((val_pro - val_adv) / val_adv) * 100
            
        status = "✅" if diff < 1.0 else "❌"
        if diff >= 1.0: match = False
        
        # Formato visual
        fmt = "{:.4f}"
        if m in ['total_trades']: fmt = "{:.0f}"
        
        print(f"{m:<20} | {fmt.format(val_adv):<15} | {fmt.format(val_pro):<15} | {diff:>6.2f}% {status}")

    print("-" * 65)
    
    if match:
        logger.info("\n✅ ÉXITO: Los motores convergen correctamente.")
    else:
        logger.error("\n❌ ERROR: Hay divergencia significativa entre motores.")

if __name__ == "__main__":
    try:
        run_comparison()
    except Exception as e:
        logger.error(f"Fallo en ejecución: {e}")
        import traceback
        traceback.print_exc()
