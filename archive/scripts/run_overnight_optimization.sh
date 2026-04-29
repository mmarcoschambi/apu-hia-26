#!/bin/bash
# 🌙 Optimización Nocturna - Configuración Profesional

echo "🚀 Starting overnight optimization..."
echo "📅 $(date)"
echo ""

# Verificar universo
TICKER_COUNT=$(sqlite3 data/momentum_scanner.db "SELECT COUNT(DISTINCT symbol) FROM daily_bars;" 2>/dev/null || echo "0")
echo "📊 Universe size: $TICKER_COUNT tickers"

if [ "$TICKER_COUNT" -lt "100" ]; then
    echo "❌ Need at least 100 tickers. Populating universe..."
    python3 manage_universe.py --add-sp500
fi

# Run optimización
nohup python3 run_custom_optimization.py \
    --in-start 2012-01-01 --in-end 2018-12-31 \
    --val-start 2019-01-01 --val-end 2021-12-31 \
    --oos-start 2022-01-01 --oos-end 2025-12-31 \
    --trials 800 \
    --limit 600 \
    > bugatti_overnight_$(date +%Y%m%d).log 2>&1 &

PID=$!
echo "✅ Optimization started (PID: $PID)"
echo "📝 Log: bugatti_overnight_$(date +%Y%m%d).log"
echo ""
echo "🔍 Monitor progress:"
echo "   tail -f bugatti_overnight_$(date +%Y%m%d).log"
echo ""
echo "⏱️  Estimated completion: $(date -d '+8 hours' '+%Y-%m-%d %H:%M')"
