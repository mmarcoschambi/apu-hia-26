#!/bin/bash
echo "================================================================================"
echo "🧪 TEST DE INTEGRACIÓN VECTORBT + STREAMLIT"
echo "================================================================================"
echo ""

echo "1️⃣ Verificando archivos necesarios..."
echo ""

files=(
    "app.py"
    "src/backtest/vectorbt_engine.py"
    "src/backtest/vectorbt_engine_advanced.py"
    "backtest_vectorbt_advanced.py"
)

all_ok=true
for file in "${files[@]}"; do
    if [ -f "$file" ]; then
        echo "✅ $file"
    else
        echo "❌ $file - NOT FOUND"
        all_ok=false
    fi
done

echo ""
if [ "$all_ok" = false ]; then
    echo "❌ Faltan archivos necesarios. Abortando."
    exit 1
fi

echo "2️⃣ Verificando función run_vectorbt_backtest_ui en app.py..."
if grep -q "def run_vectorbt_backtest_ui" app.py; then
    echo "✅ Función encontrada"
else
    echo "❌ Función no encontrada en app.py"
    exit 1
fi

echo ""
echo "3️⃣ Verificando selector de motor en app.py..."
if grep -q "use_vectorbt" app.py; then
    echo "✅ Selector encontrado"
else
    echo "❌ Selector no encontrado"
    exit 1
fi

echo ""
echo "4️⃣ Test rápido de VectorBT engine standalone..."
python3 << 'PYEOF'
try:
    from src.backtest.vectorbt_engine_advanced import AdvancedVectorBTEngine
    print("✅ AdvancedVectorBTEngine importa correctamente")
    
    # Test rápido con 2 tickers
    engine = AdvancedVectorBTEngine(
        universe=['AAPL', 'MSFT'],
        start_date='2021-01-01',
        end_date='2021-01-31',
        initial_capital=100000
    )
    print("✅ Engine instancia correctamente")
    engine.cleanup()
    print("✅ Cleanup funciona")
    
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
    exit(1)
PYEOF

if [ $? -ne 0 ]; then
    echo ""
    echo "❌ Test de engine falló"
    exit 1
fi

echo ""
echo "================================================================================"
echo "✅ TODOS LOS TESTS PASARON"
echo "================================================================================"
echo ""
echo "🚀 Para iniciar Streamlit:"
echo "   streamlit run app.py"
echo ""
echo "📝 Test sugerido en UI:"
echo "   1. Modo: Lista Manual"
echo "   2. Tickers: AAPL,MSFT,NVDA"
echo "   3. Fechas: 2021-01-01 a 2021-12-31"
echo "   4. Motor: VectorBT (default)"
echo "   5. Click: EJECUTAR BACKTEST"
echo ""
echo "⏱️  Tiempo esperado: 2-3 segundos"
echo "📊 Resultado esperado: Trades + desglose TP1/TP2"
echo ""
