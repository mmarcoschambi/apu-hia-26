#!/bin/bash
# Test del workflow con 3 tickers de prueba

echo "🧪 TEST RÁPIDO DEL WORKFLOW"
echo "═══════════════════════════════════════════"
echo ""

# Crear lista de test
cat > test_tickers_workflow.txt << TESTEOF
AAPL
MSFT
NVDA
TESTEOF

echo "✅ Archivo de test creado: test_tickers_workflow.txt (3 tickers)"
echo ""
echo "Ejecutando pipeline completo..."
echo ""

# Ejecutar pipeline
./expand_universe_complete.sh --tickers-file test_tickers_workflow.txt --skip-audit

echo ""
echo "═══════════════════════════════════════════"
echo "✅ TEST COMPLETADO"
echo ""
echo "Verificar:"
echo "  1. cat new_tickers_to_add.txt"
echo "  2. ls -lh data/pattern_cache.pkl"
echo "  3. python3 check_ticker_data.py AAPL"
echo ""

# Cleanup
rm -f test_tickers_workflow.txt
