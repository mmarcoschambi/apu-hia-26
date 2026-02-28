#!/bin/bash
# Quick check script for Market Regime Filter implementation

echo "=============================================================="
echo "Market Regime Filter - Installation Check"
echo "=============================================================="
echo ""

# Check files
echo "📁 Checking files..."
FILES=(
    "src/utils/market_regime.py"
    "test_market_regime.py"
    "demo_market_regime.py"
    "MARKET_REGIME_FILTER_GUIDE.md"
    "MARKET_REGIME_IMPLEMENTATION.md"
    "RESUMEN_MARKET_REGIME.md"
)

ALL_OK=true
for file in "${FILES[@]}"; do
    if [ -f "$file" ]; then
        echo "  ✅ $file"
    else
        echo "  ❌ $file (MISSING)"
        ALL_OK=false
    fi
done

echo ""
echo "🧪 Running quick test..."
python3 -c "
from src.utils.market_regime import MarketRegimeClassifier, load_spy_vix_data
import pandas as pd

spy, vix = load_spy_vix_data('2024-06-01', '2024-06-30')
classifier = MarketRegimeClassifier(spy, vix)
date = pd.to_datetime('2024-06-15')
context = classifier.get_market_context(date)

print('  ✅ Module loads successfully')
print(f'  ✅ SPY data: {len(spy)} bars')
print(f'  ✅ Classification works: {context[\"market_stage\"]}')
" 2>&1

if [ $? -eq 0 ]; then
    echo ""
    echo "✅ All tests passed!"
    echo ""
    echo "Next steps:"
    echo "  1. Run: python3 test_market_regime.py"
    echo "  2. Read: MARKET_REGIME_FILTER_GUIDE.md"
    echo "  3. Integrate in your backtests with use_market_regime_filter=True"
else
    echo ""
    echo "❌ Tests failed. Check error messages above."
fi

echo ""
echo "=============================================================="
