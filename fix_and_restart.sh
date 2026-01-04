#!/bin/bash
# Script final para reiniciar Streamlit con TODOS los fixes aplicados

echo "╔═══════════════════════════════════════════════════════════════════════╗"
echo "║          REINICIO COMPLETO DE STREAMLIT - FIX FINAL                   ║"
echo "╚═══════════════════════════════════════════════════════════════════════╝"
echo ""

echo "🔄 Limpiando cache de Python..."
find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null
find . -type f -name "*.pyc" -delete 2>/dev/null
echo "✅ Cache de Python limpiado"
echo ""

echo "📊 Verificando fixes aplicados..."
echo ""

# Verificar que los cambios estén aplicados
echo "1. Verificando triad_openbb.py..."
if grep -q "df\['Volume'\]" src/core/triad_openbb.py; then
    echo "   ✅ triad_openbb.py correcto (usa Volume mayúscula)"
else
    echo "   ❌ triad_openbb.py tiene problema"
fi

echo "2. Verificando market_context.py..."
if grep -q "info\['open'\]" src/core/market_context.py; then
    echo "   ✅ market_context.py correcto (usa open minúscula para dict)"
else
    echo "   ❌ market_context.py tiene problema"
fi

echo "3. Verificando daily_engine.py..."
if grep -q "\['Close'\]" src/backtest/daily_engine.py; then
    echo "   ✅ daily_engine.py correcto (usa Close mayúscula)"
else
    echo "   ❌ daily_engine.py tiene problema"
fi

echo ""
echo "🧪 Ejecutando test standalone..."
python3 test_streamlit_load.py
TEST_EXIT=$?

echo ""
if [ $TEST_EXIT -eq 0 ]; then
    echo "═══════════════════════════════════════════════════════════════════════"
    echo "✅ TODOS LOS TESTS PASARON"
    echo "═══════════════════════════════════════════════════════════════════════"
    echo ""
    echo "🚀 AHORA REINICIA STREAMLIT:"
    echo ""
    echo "   1. Si Streamlit está corriendo, deténlo (Ctrl+C)"
    echo "   2. Ejecuta: streamlit run app.py"
    echo "   3. O usa: ./run_dashboard.sh"
    echo ""
    echo "   ⚠️  NO uses 'Rerun' desde la UI - Necesitas reinicio COMPLETO"
    echo ""
else
    echo "═══════════════════════════════════════════════════════════════════════"
    echo "❌ TESTS FALLARON - Aún hay problemas"
    echo "═══════════════════════════════════════════════════════════════════════"
    echo ""
    echo "Por favor reporta este error"
fi
