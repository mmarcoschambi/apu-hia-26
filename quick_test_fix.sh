#!/bin/bash
# Quick test para verificar que el fix de exit logic funciona

echo "================================================================================"
echo "🧪 QUICK TEST - Exit Logic Fix"
echo "================================================================================"
echo ""
echo "Este test verifica que el código fue modificado correctamente."
echo ""

# 1. Verificar código
echo "1️⃣ Verificando código fuente..."
python3 verify_exit_fix.py

if [ $? -eq 0 ]; then
    echo ""
    echo "✅ Código verificado correctamente"
else
    echo ""
    echo "❌ Error en verificación de código"
    exit 1
fi

echo ""
echo "================================================================================"
echo "📝 SIGUIENTE PASO: Testear con data real"
echo "================================================================================"
echo ""
echo "Para testear el fix con data real, ejecuta un backtest pequeño:"
echo ""
echo "  python3 backtest_dynamic_universe.py \\"
echo "    --start 2024-11-01 \\"
echo "    --end 2024-12-31 \\"
echo "    --tickers AAPL MSFT NVDA"
echo ""
echo "Métricas a verificar:"
echo "  • TP1 Rate debe ser > 50% (antes: 34.7%)"
echo "  • Avg Loss debe ser < -2% (antes: -4.37%)"
echo "  • Win Rate debe mejorar"
echo ""
echo "IMPORTANTE: Asegúrate que use_trailing_stop = True en tu config!"
echo ""

