#!/bin/bash
# MORNING WORKFLOW - Script para ejecutar cada mañana

echo "════════════════════════════════════════════════════════════════════════════════"
echo "🌅 MORNING TRADING WORKFLOW"
echo "════════════════════════════════════════════════════════════════════════════════"
echo ""
echo "Date: $(date '+%Y-%m-%d %H:%M:%S')"
echo ""

# Verificar cache
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📊 STEP 1: Checking cache status"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
python3 cache_inspector.py | head -20
echo ""

# Ejecutar scanner
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🔍 STEP 2: Running live scanner"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
python3 live_scanner.py --static --processes 4
echo ""

# Verificar si se generó focus list
if [ -f "live_trading_focus_list.csv" ]; then
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "✅ FOCUS LIST GENERATED"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""
    echo "Tickers to watch today:"
    tail -n +2 live_trading_focus_list.csv | cut -d',' -f1 | while read ticker; do
        echo "  → $ticker"
    done
    echo ""
    echo "📄 Full details: live_trading_focus_list.csv"
else
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "⚠️  NO FOCUS LIST GENERATED"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""
    echo "Possible reasons:"
    echo "  - Market conditions not favorable (Red/Yellow light)"
    echo "  - No setups found matching criteria"
    echo "  - Check scanner output above"
fi

echo ""
echo "════════════════════════════════════════════════════════════════════════════════"
echo "✅ MORNING WORKFLOW COMPLETE"
echo "════════════════════════════════════════════════════════════════════════════════"
echo ""
echo "Next steps:"
echo "  1. Review focus list (if generated)"
echo "  2. Add tickers to your trading platform"
echo "  3. Set alerts at trigger prices"
echo "  4. Monitor during market hours"
echo ""
