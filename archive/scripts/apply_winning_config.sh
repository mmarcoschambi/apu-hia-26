#!/bin/bash
set -e

echo "════════════════════════════════════════════════════════════════════════"
echo "🏆 APPLYING WINNING CONFIGURATION TO PRODUCTION"
echo "════════════════════════════════════════════════════════════════════════"
echo ""

# Find the best balanced config
BEST_CONFIG="outputs/tp_comparison_20260202_205301/validated_params_balanced.json"
TARGET="config/validated_production_params.json"

if [ ! -f "$BEST_CONFIG" ]; then
    echo "❌ ERROR: Best config not found at: $BEST_CONFIG"
    echo ""
    echo "Run this first:"
    echo "  bash run_dual_validation.sh --tp-preset balanced"
    exit 1
fi

echo "📁 Source: $BEST_CONFIG"
echo "📁 Target: $TARGET"
echo ""

# Backup current config
if [ -f "$TARGET" ]; then
    BACKUP="${TARGET}.backup.$(date +%Y%m%d_%H%M%S)"
    echo "💾 Backing up current config to: $BACKUP"
    cp "$TARGET" "$BACKUP"
fi

# Copy winning config
echo "📋 Copying winning config..."
cp "$BEST_CONFIG" "$TARGET"

# Verify
echo ""
echo "════════════════════════════════════════════════════════════════════════"
echo "✅ CONFIGURATION APPLIED"
echo "════════════════════════════════════════════════════════════════════════"
echo ""

# Show config details
python3 << 'PYCODE'
import json

with open("config/validated_production_params.json") as f:
    config = json.load(f)

perf = config.get("performance", {})
params = config.get("parameters", {})

print(f"📊 Config: {config.get('config_name', 'N/A')}")
print(f"📅 Validated: {config.get('validated_date', 'N/A')[:10]}")
print(f"⭐ Sharpe: {perf.get('sharpe_ratio', 0):.3f}")
print(f"💰 Return: {perf.get('total_return_pct', 0):.2f}%")
print(f"📈 Trades: {perf.get('total_trades', 0)}")
print(f"🎯 Win Rate: {perf.get('win_rate_pct', 0):.1f}%")
print(f"📉 Max DD: {perf.get('max_drawdown_pct', 0):.2f}%")
print("")
print(f"🎲 TP Distribution: {params.get('tp1_pct', 0)*100:.0f}% / {params.get('tp2_pct', 0)*100:.0f}% / {params.get('runner_pct', 0)*100:.0f}%")
PYCODE

echo ""
echo "════════════════════════════════════════════════════════════════════════"
echo "🚀 NEXT STEPS"
echo "════════════════════════════════════════════════════════════════════════"
echo ""
echo "1. Start Streamlit:"
echo "   streamlit run app.py"
echo ""
echo "2. In sidebar, click:"
echo "   📥 Load Validated Params"
echo ""
echo "3. Verify status shows:"
echo "   ✅ ACTIVE - Using these params"
echo ""
echo "4. Run a backtest to confirm!"
echo ""
echo "════════════════════════════════════════════════════════════════════════"
