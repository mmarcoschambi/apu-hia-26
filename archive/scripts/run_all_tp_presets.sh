#!/bin/bash
#
# SAFE PARALLEL TP PRESET COMPARISON
# ===================================
# Corre múltiples presets EN SECUENCIA (no paralelo)
# y guarda cada resultado en archivos separados
#

set -e

echo "================================================================================"
echo "🔬 TP PRESET COMPARISON SUITE"
echo "================================================================================"
echo ""

PRESETS=("balanced" "classic" "conservative" "aggressive_runner")
RESULTS_DIR="outputs/tp_comparison_$(date +%Y%m%d_%H%M%S)"

mkdir -p "$RESULTS_DIR"

echo "📁 Results will be saved to: $RESULTS_DIR"
echo ""

# Run each preset sequentially
for preset in "${PRESETS[@]}"; do
    echo ""
    echo "================================================================================"
    echo "🎯 Running: $preset"
    echo "================================================================================"
    echo ""
    
    # Run validation
    bash run_dual_validation.sh --tp-preset "$preset"
    
    # Copy results to unique files
    if [ -f "outputs/walk_forward_results.json" ]; then
        cp outputs/walk_forward_results.json "$RESULTS_DIR/walk_forward_${preset}.json"
    fi
    
    if [ -f "config/validated_production_params.json" ]; then
        cp config/validated_production_params.json "$RESULTS_DIR/validated_params_${preset}.json"
    fi
    
    echo "✅ $preset complete"
    echo ""
done

# Generate comparison report
echo ""
echo "================================================================================"
echo "📊 GENERATING COMPARISON REPORT"
echo "================================================================================"
echo ""

python3 << PYCODE
import json
import os
from pathlib import Path

results_dir = "$RESULTS_DIR"
presets = ["balanced", "classic", "conservative", "aggressive_runner"]

print("=" * 80)
print("📊 TP PRESET COMPARISON RESULTS")
print("=" * 80)
print()

comparison = []

for preset in presets:
    params_file = f"{results_dir}/validated_params_{preset}.json"
    
    if not os.path.exists(params_file):
        print(f"❌ {preset}: No results found")
        continue
    
    with open(params_file) as f:
        data = json.load(f)
    
    params = data.get('parameters', {})
    perf = data.get('performance', {})
    
    result = {
        'preset': preset,
        'tp1': params.get('tp1_pct', 'N/A'),
        'tp2': params.get('tp2_pct', 'N/A'),
        'runner': params.get('runner_pct', 'N/A'),
        'sharpe': perf.get('sharpe_ratio', 0),
        'return': perf.get('total_return_pct', 0) / 100.0,  # Convert % to decimal
        'trades': perf.get('total_trades', 0),
        'win_rate': perf.get('win_rate_pct', 0) / 100.0,  # Convert % to decimal
        'max_dd': perf.get('max_drawdown_pct', 0) / 100.0  # Convert % to decimal
    }
    
    comparison.append(result)
    
    print(f"📈 {preset.upper()}")
    print(f"   TP Distribution: {result['tp1']:.0%} / {result['tp2']:.0%} / {result['runner']:.0%}")
    print(f"   Sharpe: {result['sharpe']:.3f}")
    print(f"   Return: {result['return']:.2%}")
    print(f"   Trades: {result['trades']}")
    print(f"   Win Rate: {result['win_rate']:.1%}")
    print(f"   Max DD: {result['max_dd']:.2%}")
    print()

# Find winner
if comparison:
    winner = max(comparison, key=lambda x: x['sharpe'])
    
    print("=" * 80)
    print("🏆 WINNER")
    print("=" * 80)
    print()
    print(f"   Preset: {winner['preset'].upper()}")
    print(f"   TP Distribution: {winner['tp1']:.0%} / {winner['tp2']:.0%} / {winner['runner']:.0%}")
    print(f"   Sharpe: {winner['sharpe']:.3f}")
    print(f"   Return: {winner['return']:.2%}")
    print(f"   Trades: {winner['trades']}")
    print()
    
    # Copy winner to production config
    winner_file = f"{results_dir}/validated_params_{winner['preset']}.json"
    import shutil
    shutil.copy(winner_file, "config/validated_production_params.json")
    print(f"✅ Winner copied to: config/validated_production_params.json")

PYCODE

echo ""
echo "================================================================================"
echo "✅ COMPARISON COMPLETE"
echo "================================================================================"
echo ""
echo "📁 All results saved in: $RESULTS_DIR"
echo ""
echo "💡 Next steps:"
echo "   1. Review winning config: cat config/validated_production_params.json"
echo "   2. Test in Streamlit: streamlit run app.py"
echo ""
