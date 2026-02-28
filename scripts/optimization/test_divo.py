# test_engine.py
import sys
import os

# Add the project root directory to the Python path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path.insert(0, project_root)

from src.backtest.optimization_engine_divo import OptimizationEngineDIVO

print("🔥 Probando Motor DIVO...")
engine = OptimizationEngineDIVO(
    tickers=['AAPL', 'MSFT', 'TLSA','META'], # Solo 2 tickers seguros
    start_date='2020-01-01',
    end_date='2021-01-01'
)

# Prueba con parámetros ultra-laxos
params = {
    'signal_type': 'any',
    'min_rvol': 1.0,           # Volumen normal
    'min_adr': 0.5,            # Movimiento mínimo
    'risk_dollars': 100,
    'max_stop_pct': 0.1,
    'tp1_r': 1.0,
    'tp2_r': 2.0,
    'use_phases': False        # Simplificado
}

try:
    stats = engine.backtest(params)
    print("✅ Resultado:", stats)
except Exception as e:
    print("❌ Error:", e)
