#!/bin/bash
# Script para MATAR completamente Streamlit y reiniciarlo limpio

echo "╔═══════════════════════════════════════════════════════════════════════╗"
echo "║              🔴 REINICIO FORZADO DE STREAMLIT                         ║"
echo "╚═══════════════════════════════════════════════════════════════════════╝"
echo ""

# 1. Matar todos los procesos de Streamlit
echo "1️⃣  Matando procesos de Streamlit..."
pkill -9 -f "streamlit run"
sleep 2

# Verificar que no quede ninguno
if ps aux | grep -v grep | grep streamlit > /dev/null; then
    echo "   ⚠️  Aún hay procesos de Streamlit, intentando de nuevo..."
    killall -9 streamlit 2>/dev/null
    killall -9 python3 2>/dev/null
    sleep 1
fi

if ps aux | grep -v grep | grep "streamlit run" > /dev/null; then
    echo "   ❌ No se pudieron matar los procesos"
    echo "   Por favor cierra manualmente (Ctrl+C en la terminal)"
    exit 1
else
    echo "   ✅ Procesos de Streamlit terminados"
fi

# 2. Limpiar cache de Python
echo ""
echo "2️⃣  Limpiando cache de Python..."
cd /home/marcos/trade/momentum-v2
find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null
find . -type f -name "*.pyc" -delete 2>/dev/null
echo "   ✅ Cache limpiado"

# 3. Verificar que los fixes estén aplicados
echo ""
echo "3️⃣  Verificando fixes..."
if grep -q "df\['Volume'\]" src/core/triad_openbb.py && \
   grep -q "info\['open'\]" src/core/market_context.py && \
   grep -q "\['Close'\]" src/backtest/daily_engine.py; then
    echo "   ✅ Todos los fixes están aplicados"
else
    echo "   ❌ Algunos fixes faltan - ejecuta ./fix_and_restart.sh primero"
    exit 1
fi

# 4. Test standalone
echo ""
echo "4️⃣  Ejecutando test standalone..."
python3 test_streamlit_load.py > /tmp/test_output.txt 2>&1
if [ $? -eq 0 ]; then
    echo "   ✅ Tests pasaron - código funciona correctamente"
else
    echo "   ❌ Tests fallaron"
    cat /tmp/test_output.txt
    exit 1
fi

echo ""
echo "╔═══════════════════════════════════════════════════════════════════════╗"
echo "║                  ✅ LISTO PARA REINICIAR                              ║"
echo "╚═══════════════════════════════════════════════════════════════════════╝"
echo ""
echo "🚀 Ahora ejecuta EN UNA TERMINAL NUEVA:"
echo ""
echo "   cd /home/marcos/trade/momentum-v2"
echo "   streamlit run app.py"
echo ""
echo "⚠️  IMPORTANTE:"
echo "   - Usa una terminal NUEVA (no la misma donde corrió antes)"
echo "   - NO presiones solo 'Rerun' en el navegador"
echo "   - Cierra el navegador y ábrelo de nuevo después de iniciar"
echo ""
