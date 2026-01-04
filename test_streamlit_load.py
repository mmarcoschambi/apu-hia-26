#!/usr/bin/env python3
"""
Test completo que simula la carga de datos en Streamlit
"""
import sys
from pathlib import Path

# Asegurar ruta correcta
sys.path.insert(0, str(Path(__file__).resolve().parent))

print("=" * 70)
print("TEST COMPLETO: Simulación de carga de Streamlit")
print("=" * 70)

# Limpiar cache de módulos
for mod in list(sys.modules.keys()):
    if 'src.' in mod:
        del sys.modules[mod]

from src.data.market_data import MarketDataProvider
from src.core.triad_openbb import TriadOpenBB
from datetime import datetime, timedelta

def test_load_symbol(symbol):
    """Simula exactamente lo que hace daily_engine"""
    try:
        provider = MarketDataProvider()
        triad = TriadOpenBB()
        
        # Obtener datos
        end_date = datetime.now()
        start_date = end_date - timedelta(days=60)
        
        df = provider.get_daily_data(
            symbol, 
            start_date=start_date.strftime('%Y-%m-%d'),
            end_date=end_date.strftime('%Y-%m-%d'),
            offline=True
        )
        
        if df.empty:
            print(f"❌ {symbol}: No data")
            return False
        
        print(f"\n📊 {symbol}:")
        print(f"   Filas: {len(df)}")
        print(f"   Columnas OHLCV: {[c for c in df.columns if c in ['Open', 'High', 'Low', 'Close', 'Volume']]}")
        
        # CRÍTICO: Calcular indicadores (esto es donde falla)
        print(f"   Calculando indicadores...")
        df_with_indicators = triad._calculate_indicators(df.copy())
        
        # Verificar nuevas columnas
        new_cols = [c for c in df_with_indicators.columns if c not in df.columns]
        print(f"   ✅ Indicadores agregados: {new_cols}")
        
        return True
        
    except KeyError as e:
        print(f"❌ {symbol}: KeyError - {e}")
        print(f"   Columnas disponibles: {list(df.columns) if 'df' in locals() else 'N/A'}")
        return False
    except Exception as e:
        print(f"❌ {symbol}: {type(e).__name__} - {e}")
        return False

# Test con los símbolos que mencionaste
test_symbols = ['AAPL', 'PLTR', 'APP', 'MSFT']

print("\n🧪 Testing símbolos...")
results = []

for symbol in test_symbols:
    success = test_load_symbol(symbol)
    results.append((symbol, success))

print("\n" + "=" * 70)
print("RESUMEN:")
print("=" * 70)

passed = sum(1 for _, s in results if s)
failed = len(results) - passed

for symbol, success in results:
    status = "✅ PASS" if success else "❌ FAIL"
    print(f"{status}: {symbol}")

print(f"\nTotal: {passed}/{len(results)} pasaron")

if failed == 0:
    print("\n🎉 TODOS LOS TESTS PASARON - App debería funcionar!")
    sys.exit(0)
else:
    print(f"\n⚠️  {failed} tests fallaron - Aún hay problemas")
    sys.exit(1)
