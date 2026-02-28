#!/bin/bash
#
# COMPARE TP DISTRIBUTIONS
# =========================
# 
# Compara las 4 distribuciones de TP diferentes:
# 1. Classic (50/30/20) - Tradicional que "mata Alpha"
# 2. Balanced (33/33/33) - Distribución equilibrada
# 3. Aggressive Runner (25/30/45) - Maximiza runners
# 4. Optimize - Deja que Optuna encuentre lo óptimo
#
# Usage:
#   bash compare_tp_distributions.sh

set -e

echo "================================================================================"
echo "🔬 COMPARING TP DISTRIBUTIONS"
echo "================================================================================"
echo ""
echo "Este script compara 4 estrategias de distribución de salidas:"
echo ""
echo "1️⃣  CLASSIC (50/30/20)"
echo "   - 50% sale en TP1 → Asegura ganancias rápido"
echo "   - 30% sale en TP2 → Objetivo medio"
echo "   - 20% runner → Poco upside para Alpha"
echo "   ❌ PROBLEMA: Mata el Alpha potencial"
echo ""
echo "2️⃣  BALANCED (33/33/33)"
echo "   - 33% en cada nivel"
echo "   - Distribución equitativa de riesgo/reward"
echo "   - Balance entre asegurar y dejar correr"
echo ""
echo "3️⃣  AGGRESSIVE RUNNER (25/30/45)"
echo "   - Solo 25% en TP1 → Deja correr más"
echo "   - 30% en TP2 → Objetivo medio"
echo "   - 45% runner → Maximiza potencial de home runs"
echo "   ✅ RECOMENDADO para capturar Alpha"
echo ""
echo "4️⃣  OPTIMIZE"
echo "   - Deja que Optuna encuentre la distribución óptima"
echo "   - Rangos: TP1 25-50%, TP2 25-40%, Runner 15-40%"
echo ""
echo "================================================================================"
read -p "Presiona ENTER para continuar o Ctrl+C para cancelar..."
echo ""

# Quick test period for comparison
START_DATE="2023-01-01"
END_DATE="2024-12-31"
TICKERS="AAPL MSFT GOOGL NVDA TSLA META AMZN"

# Output directory
mkdir -p outputs/tp_comparison

echo ""
echo "================================================================================"
echo "🧪 TEST 1/4: CLASSIC (50/30/20)"
echo "================================================================================"
echo ""

python3 walk_forward_validation.py \
    --train-months 12 \
    --test-months 3 \
    --walk-months 6 \
    --trials 30 \
    --start "$START_DATE" \
    --end "$END_DATE" \
    --tickers $TICKERS \
    --tp-preset classic

cp outputs/walk_forward_results.json outputs/tp_comparison/classic_results.json

echo ""
echo "================================================================================"
echo "🧪 TEST 2/4: BALANCED (33/33/33)"
echo "================================================================================"
echo ""

python3 walk_forward_validation.py \
    --train-months 12 \
    --test-months 3 \
    --walk-months 6 \
    --trials 30 \
    --start "$START_DATE" \
    --end "$END_DATE" \
    --tickers $TICKERS \
    --tp-preset balanced

cp outputs/walk_forward_results.json outputs/tp_comparison/balanced_results.json

echo ""
echo "================================================================================"
echo "🧪 TEST 3/4: AGGRESSIVE RUNNER (25/30/45)"
echo "================================================================================"
echo ""

python3 walk_forward_validation.py \
    --train-months 12 \
    --test-months 3 \
    --walk-months 6 \
    --trials 30 \
    --start "$START_DATE" \
    --end "$END_DATE" \
    --tickers $TICKERS \
    --tp-preset aggressive_runner

cp outputs/walk_forward_results.json outputs/tp_comparison/aggressive_results.json

echo ""
echo "================================================================================"
echo "🧪 TEST 4/4: OPTIMIZE (Búsqueda óptima)"
echo "================================================================================"
echo ""

python3 walk_forward_validation.py \
    --train-months 12 \
    --test-months 3 \
    --walk-months 6 \
    --trials 50 \
    --start "$START_DATE" \
    --end "$END_DATE" \
    --tickers $TICKERS \
    --tp-preset optimize

cp outputs/walk_forward_results.json outputs/tp_comparison/optimized_results.json

# Generate comparison report
echo ""
echo "================================================================================"
echo "📊 GENERATING COMPARISON REPORT"
echo "================================================================================"
echo ""

python3 - <<'EOF'
import json
import pandas as pd

presets = ['classic', 'balanced', 'aggressive', 'optimized']
files = [
    'outputs/tp_comparison/classic_results.json',
    'outputs/tp_comparison/balanced_results.json',
    'outputs/tp_comparison/aggressive_results.json',
    'outputs/tp_comparison/optimized_results.json'
]

results = []

for preset, filepath in zip(presets, files):
    try:
        with open(filepath, 'r') as f:
            data = json.load(f)
        
        windows = data['windows']
        sharpes = [w['oos_sharpe'] for w in windows]
        returns = [w['oos_return'] for w in windows]
        trades = [w['oos_trades'] for w in windows]
        win_rates = [w['oos_win_rate'] for w in windows]
        
        # Get TP distribution from first window
        if preset == 'optimized':
            tp1 = windows[0]['params'].get('tp1_pct', '?') * 100
            tp2 = windows[0]['params'].get('tp2_pct', '?') * 100
            runner = windows[0]['params'].get('runner_pct', '?') * 100
            dist = f"{tp1:.0f}/{tp2:.0f}/{runner:.0f}"
        else:
            dist = {'classic': '50/30/20', 'balanced': '33/33/33', 'aggressive': '25/30/45'}[preset]
        
        results.append({
            'Preset': preset.upper(),
            'Distribution': dist,
            'Avg Sharpe': f"{pd.Series(sharpes).mean():.3f}",
            'Avg Return': f"{pd.Series(returns).mean()*100:.2f}%",
            'Avg Trades': f"{pd.Series(trades).mean():.1f}",
            'Avg Win Rate': f"{pd.Series(win_rates).mean()*100:.1f}%"
        })
    except Exception as e:
        print(f"⚠️  Could not load {preset}: {e}")

df = pd.DataFrame(results)
print("\n" + "="*90)
print("📊 TP DISTRIBUTION COMPARISON")
print("="*90)
print(df.to_string(index=False))
print("="*90)
print("\n💡 RECOMENDACIÓN:")
print("   Si AGGRESSIVE_RUNNER o OPTIMIZED tienen mejor Sharpe → Usar esa distribución")
print("   El preset CLASSIC (50/30/20) probablemente sea el PEOR porque mata el Alpha\n")

EOF

echo ""
echo "✅ Comparación completa!"
echo ""
echo "📁 Resultados guardados en: outputs/tp_comparison/"
echo ""
