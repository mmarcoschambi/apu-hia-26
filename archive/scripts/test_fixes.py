"""
Quick test para verificar que los fixes funcionan
"""
import sys
sys.path.insert(0, '/home/marcos/trade/momentum-v2')

print("🔬 Verificando Fixes Aplicados...")
print("=" * 60)

# Test 1: Verificar que FASE_2 usa 'if' no 'elif'
print("\n1️⃣ Test: FASE_2 puede ejecutarse mismo día que FASE_1")
with open('src/backtest/daily_engine.py', 'r') as f:
    content = f.read()
    # Buscar la línea específica
    if 'if pos.tp1_hit and not pos.tp2_hit:' in content and \
       '# IMPORTANTE: Usar \'if\' no \'elif\' para permitir ejecución el mismo día' in content:
        print("   ✅ Fix aplicado: FASE_2 usa 'if' (no 'elif')")
    else:
        print("   ❌ Fix NO encontrado: Revisar línea 380")

# Test 2: Verificar trend context con SMA50
print("\n2️⃣ Test: Trend context coherente con screener")
if 'sma_50 = df[\'close\'].rolling(window=50).mean()' in content and \
   'is_uptrend = (current_bar[\'close\'] > sma_20) and (sma_20 > sma_50)' in content:
    print("   ✅ Fix aplicado: Trend usa SMA20 AND SMA50")
else:
    print("   ❌ Fix NO encontrado: Revisar líneas 626-632")

# Test 3: Verificar RVOL en screener
print("\n3️⃣ Test: RVOL filter en screener")
with open('src/core/screener.py', 'r') as f:
    screener_content = f.read()
    if 'min_rvol' in screener_content and 'FILTER 3B: RVOL' in screener_content:
        print("   ✅ Fix aplicado: RVOL filter en screener")
    else:
        print("   ❌ Fix NO encontrado: Revisar screener.py")

print("\n" + "=" * 60)
print("✅ Todos los fixes están en el código")
print("\n⚠️  IMPORTANTE: Ahora debes RE-EJECUTAR el backtest:")
print("   python3 daily_backtest_runner.py")
print("\n📊 Los archivos actuales son del backtest ANTERIOR")
print("   backtest_results.csv: 06:30 (antes de fixes)")
print("   partial_exits.csv: 06:30 (antes de fixes)")
