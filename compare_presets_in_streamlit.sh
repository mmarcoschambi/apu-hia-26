#!/bin/bash
#
# COMPARE PRESETS IN STREAMLIT (FIXED)
# =====================================
#
# Compara 5 distribuciones de TP de forma independiente:
#   - classic: 50/30/20
#   - conservative: 40/35/25
#   - balanced: 33/33/34
#   - aggressive: 25/30/45
#   - extreme: 20/30/50
#
# Usa optimize_tp_distributions.py que guarda resultados independientes
#

set -e

echo "================================================================================"
echo "🔬 STREAMLIT TP PRESET COMPARISON (FIXED)"
echo "================================================================================"
echo ""
echo "Comparando 5 distribuciones hardcoded de TP:"
echo "  1. classic - 50/30/20 (tradicional)"
echo "  2. conservative - 40/35/25 (seguro)"
echo "  3. balanced - 33/33/34 (equilibrado)"
echo "  4. aggressive - 25/30/45 (busca home runs)"
echo "  5. extreme - 20/30/50 (máximo runner)"
echo ""
echo "Tarda ~20-30 min. Luego puedes comparar en Streamlit."
echo ""
read -p "Presiona ENTER para continuar o Ctrl+C para cancelar..."

mkdir -p config/tp_comparisons
mkdir -p outputs/tp_optimization

# Ejecutar comparación de distribuciones con nuevo script
echo ""
echo "═══ COMPARING 5 TP DISTRIBUTIONS ═══"
echo ""

python3 optimize_tp_distributions.py \
    --mode compare \
    --start 2023-01-01 \
    --end 2024-12-31 \
    --tickers AAPL MSFT GOOGL NVDA TSLA META AMZN \
    --output-dir outputs/tp_optimization

# Copiar resultados individuales para comparación
cp outputs/tp_optimization/hardcoded_comparison.json config/tp_comparisons/all_distributions.json

# Show comparison
echo ""
echo "================================================================================"
echo "📊 COMPARISON RESULTS"
echo "================================================================================"

python3 - <<'PY'
import json

with open('outputs/tp_optimization/hardcoded_comparison.json') as f:
    data = json.load(f)

print("\n📊 TP DISTRIBUTION COMPARISON:")
print("=" * 80)
print(f"{'Distribution':<15} | {'TP1':<6} | {'TP2':<6} | {'Runner':<6} | {'Sharpe':<8} | {'Return':<8} | {'Trades':<7}")
print("-" * 80)

for r in data['results']:
    if r['status'] == 'success':
        print(f"{r['distribution_name']:<15} | {r['tp1_pct']*100:<5.0f}% | {r['tp2_pct']*100:<5.0f}% | {r['runner_pct']*100:<5.0f}% | {r['sharpe']:<8.3f} | {r['return']*100:<7.2f}% | {r['trades']:<7}")

print("-" * 80)

# Mejor
distributions = [r for r in data['results'] if r['status'] == 'success']
if distributions:
    best = max(distributions, key=lambda x: x['sharpe'])
    print(f"\n🥇 BEST: {best['distribution_name'].upper()}")
    print(f"   TP: {best['tp1_pct']*100:.0f}% / {best['tp2_pct']*100:.0f}% / {best['runner_pct']*100:.0f}%")
    print(f"   Sharpe: {best['sharpe']:.3f}")
    print(f"   Return: {best['return']*100:.2f}%")
    print(f"   Trades: {best['trades']}")
PY

echo ""
echo "================================================================================"
echo "🎯 OPTIMIZACIÓN CON OPTUNA (OPCIONAL)"
echo "================================================================================"
echo ""
echo "Para buscar la distribución óptima con Optuna (63 combinaciones):"
echo ""
echo "  python3 optimize_tp_distributions.py \\"
echo "      --mode optimize \\"
echo "      --trials 63 \\"
echo "      --start 2023-01-01 \\"
echo "      --end 2024-12-31"
echo ""
echo "Rangos de optimización:"
echo "  TP1: 20% - 60% (step=5%)"
echo "  TP2: 20% - 50% (step=5%)"
echo "  Runner: 10% - 60% (calculado automáticamente)"
echo ""
echo "================================================================================"
echo "📱 CÓMO USAR EN STREAMLIT:"
echo "================================================================================"
echo ""
echo "La mejor distribución ya está guardada en:"
echo "  config/validated_production_params.json"
echo ""
echo "Para cargar en Streamlit:"
echo "  streamlit run app.py"
echo "  → Click 'Load Validated Params'"
echo "  → La distribución TP se cargará automáticamente"
echo ""
echo "✅ Resultados guardados en:"
echo "  - outputs/tp_optimization/hardcoded_comparison.json"
echo "  - config/tp_comparisons/all_distributions.json"
echo "  - config/validated_production_params.json (mejor distribución)"
echo ""
