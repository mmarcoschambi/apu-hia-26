# 🔍 Análisis Crítico del Workflow - Perspectiva de Trader

## Tu Observación: "One-Shot con Debugging Manual"

**Problema actual:**
```
Run workflow → Resultados malos → ¿Qué falló?
├─ ¿Parámetros?
├─ ¿Data?
├─ ¿Código?
└─ ¿Market conditions?

→ Apagar todo, volver mañana, empezar de cero
→ No hay diagnóstico automático
```

---

## 🚨 Problemas Identificados en Tu Workflow

### 1. **Sin Validación Pre-Flight**
❌ No verificas data quality antes de empezar
❌ No verificas que motores estén OK
❌ Empiezas optimización sin saber si el setup es válido

**Resultado:** Pierdes 2.5 horas descubriendo que data estaba mal

### 2. **Sin Diagnóstico Automático**
❌ Resultados malos → manual debugging
❌ No sabes si es data, código o parámetros
❌ No hay logs estructurados

**Resultado:** Debugging reactivo, no proactivo

### 3. **Sin Checkpoints**
❌ Si falla paso 3, pierdes trabajo de pasos 1-2
❌ No puedes reanudar desde punto de falla
❌ Todo es secuencial sin validación entre pasos

**Resultado:** Re-correr todo desde cero

### 4. **Sin Métricas de Salud del Sistema**
❌ No sabes si cache está corrupto
❌ No sabes si indicadores están calculados
❌ No sabes si TP config es reciente

**Resultado:** "Garbage in, garbage out" descubierto tarde

---

## ✅ Solución: Workflow Automatizado con Validación

### Script Principal: `run_complete_optimization.sh`

```bash
#!/bin/bash
# 🎯 Complete Optimization Workflow with Validation
#
# Features:
# - Pre-flight checks (data, cache, convergence)
# - Automated 5-step workflow
# - Health monitoring
# - Checkpoint-based resume
# - Automatic diagnostics on failure
# - Results comparison
# - Final report

set -e

CHECKPOINT_FILE=".workflow_checkpoint"
RESULTS_DIR="outputs/optimization_runs/$(date +%Y%m%d_%H%M%S)"
mkdir -p "$RESULTS_DIR"

echo "======================================================================="
echo "🚀 COMPLETE OPTIMIZATION WORKFLOW"
echo "======================================================================="
echo "Results will be saved to: $RESULTS_DIR"
echo ""

# ============================================================================
# PRE-FLIGHT CHECKS
# ============================================================================

echo "🔍 STEP 0: PRE-FLIGHT CHECKS"
echo "-----------------------------------------------------------------------"

# Check 1: Cache health
echo "  [1/5] Checking cache health..."
python3 << 'PYTHON'
import pandas as pd
from pathlib import Path

cache_files = list(Path('data/cache').glob('*.pkl'))
total = len(cache_files)

# Sample 10 random tickers
import random
sample = random.sample(cache_files, min(10, total))

issues = []
for pkl in sample:
    try:
        df = pd.read_pickle(pkl)
        # Check for indicators
        if 'sma_20' not in df.columns:
            issues.append(f"{pkl.stem}: missing indicators")
        # Check for data
        if len(df) < 100:
            issues.append(f"{pkl.stem}: insufficient data ({len(df)} bars)")
    except Exception as e:
        issues.append(f"{pkl.stem}: {e}")

if issues:
    print(f"  ❌ FAIL: Cache issues found")
    for issue in issues[:5]:
        print(f"     - {issue}")
    exit(1)
else:
    print(f"  ✅ PASS: Cache healthy ({total} tickers)")
PYTHON

# Check 2: Engine convergence
echo "  [2/5] Checking engine convergence..."
if timeout 300 python3 scripts/debug_convergence.py > "$RESULTS_DIR/convergence.log" 2>&1; then
    # Extract divergence %
    DIVERGENCE=$(grep "Trades Difference:" "$RESULTS_DIR/convergence.log" | awk '{print $3}' | tr -d '%')
    if (( $(echo "$DIVERGENCE < 60" | bc -l) )); then
        echo "  ✅ PASS: Engines converged (divergence: $DIVERGENCE%)"
    else
        echo "  ⚠️  WARN: High divergence ($DIVERGENCE%), but continuing..."
    fi
else
    echo "  ❌ FAIL: Engine convergence check failed"
    echo "  See: $RESULTS_DIR/convergence.log"
    exit 1
fi

# Check 3: TP config freshness
echo "  [3/5] Checking TP config freshness..."
python3 << 'PYTHON'
from pathlib import Path
import json
from datetime import datetime

tp_file = Path('config/tp_optimal.json')
if tp_file.exists():
    with open(tp_file) as f:
        config = json.load(f)
    saved_date = datetime.fromisoformat(config['timestamp'])
    age_days = (datetime.now() - saved_date).days
    
    if age_days <= 7:
        print(f"  ✅ PASS: TP config is fresh ({age_days} days old)")
    else:
        print(f"  ⚠️  WARN: TP config is old ({age_days} days), will re-optimize")
        tp_file.unlink()  # Force re-optimization
else:
    print(f"  ℹ️  INFO: No TP config found, will optimize")
PYTHON

# Check 4: Disk space
echo "  [4/5] Checking disk space..."
SPACE_GB=$(df -BG . | tail -1 | awk '{print $4}' | tr -d 'G')
if [ "$SPACE_GB" -lt 5 ]; then
    echo "  ❌ FAIL: Low disk space ($SPACE_GB GB free)"
    exit 1
else
    echo "  ✅ PASS: Sufficient disk space ($SPACE_GB GB free)"
fi

# Check 5: Dependencies
echo "  [5/5] Checking dependencies..."
python3 << 'PYTHON'
import sys
required = ['pandas', 'numpy', 'optuna', 'vectorbt', 'numba']
missing = []
for pkg in required:
    try:
        __import__(pkg)
    except ImportError:
        missing.append(pkg)

if missing:
    print(f"  ❌ FAIL: Missing packages: {', '.join(missing)}")
    sys.exit(1)
else:
    print(f"  ✅ PASS: All dependencies installed")
PYTHON

echo ""
echo "✅ All pre-flight checks passed!"
echo ""

# ============================================================================
# CHECKPOINT RESUME LOGIC
# ============================================================================

if [ -f "$CHECKPOINT_FILE" ]; then
    LAST_STEP=$(cat "$CHECKPOINT_FILE")
    echo "🔄 Found checkpoint at step $LAST_STEP"
    read -p "Resume from there? (y/n): " RESUME
    if [ "$RESUME" != "y" ]; then
        LAST_STEP=0
        rm "$CHECKPOINT_FILE"
    fi
else
    LAST_STEP=0
fi

# ============================================================================
# STEP 1: BASELINE (BALANCED)
# ============================================================================

if [ $LAST_STEP -lt 1 ]; then
    echo ""
    echo "======================================================================="
    echo "📊 STEP 1: BASELINE WITH BALANCED TP"
    echo "======================================================================="
    
    if bash run_dual_validation.sh --tp-preset balanced > "$RESULTS_DIR/step1_balanced.log" 2>&1; then
        echo "✅ Step 1 complete"
        echo "1" > "$CHECKPOINT_FILE"
        
        # Extract key metrics
        python3 << 'PYTHON'
import json
from pathlib import Path
results = json.load(open('outputs/walk_forward_results.json'))
print(f"   Sharpe: {results.get('sharpe', 'N/A'):.3f}")
print(f"   Trades: {results.get('trades', 'N/A')}")
print(f"   Win Rate: {results.get('win_rate', 'N/A')*100:.1f}%")
PYTHON
    else
        echo "❌ Step 1 failed! Check: $RESULTS_DIR/step1_balanced.log"
        exit 1
    fi
fi

# ============================================================================
# STEP 2: OPTIMIZE TP
# ============================================================================

if [ $LAST_STEP -lt 2 ]; then
    echo ""
    echo "======================================================================="
    echo "🎯 STEP 2: OPTIMIZE TP DISTRIBUTION"
    echo "======================================================================="
    
    if bash run_dual_validation.sh --tp-preset optimize > "$RESULTS_DIR/step2_optimize.log" 2>&1; then
        echo "✅ Step 2 complete"
        echo "2" > "$CHECKPOINT_FILE"
        
        # Show optimized TP
        python3 << 'PYTHON'
import json
config = json.load(open('config/tp_optimal.json'))
print(f"   Optimal TP: {config['tp1_pct']*100:.0f}% / {config['tp2_pct']*100:.0f}% / {config['runner_pct']*100:.0f}%")
print(f"   Sharpe: {config.get('sharpe', 'N/A'):.3f}")
PYTHON
    else
        echo "❌ Step 2 failed! Check: $RESULTS_DIR/step2_optimize.log"
        exit 1
    fi
fi

# ============================================================================
# STEP 3: COMPARE PRESETS
# ============================================================================

if [ $LAST_STEP -lt 3 ]; then
    echo ""
    echo "======================================================================="
    echo "⚖️  STEP 3: COMPARE TP PRESETS"
    echo "======================================================================="
    
    # Run with different presets and compare
    PRESETS=("classic" "balanced" "aggressive_runner" "conservative")
    
    for preset in "${PRESETS[@]}"; do
        echo "  Testing preset: $preset..."
        bash run_dual_validation.sh --tp-preset "$preset" > "$RESULTS_DIR/step3_${preset}.log" 2>&1 || true
    done
    
    echo "✅ Step 3 complete"
    echo "3" > "$CHECKPOINT_FILE"
    
    # Compare results
    python3 << 'PYTHON'
import json
from pathlib import Path

results = {}
for log_file in Path('outputs/optimization_runs').rglob('walk_forward_results.json'):
    with open(log_file) as f:
        data = json.load(f)
    preset_name = log_file.parent.name
    results[preset_name] = data.get('sharpe', 0)

print("\n  Results comparison:")
for preset, sharpe in sorted(results.items(), key=lambda x: x[1], reverse=True):
    print(f"    {preset:20s}: Sharpe {sharpe:.3f}")
PYTHON
fi

# ============================================================================
# STEP 4: VALIDATE WINNER
# ============================================================================

if [ $LAST_STEP -lt 4 ]; then
    echo ""
    echo "======================================================================="
    echo "🏆 STEP 4: VALIDATE WINNER"
    echo "======================================================================="
    
    # Auto-select best preset
    WINNER=$(python3 << 'PYTHON'
import json
from pathlib import Path

results = {}
for log_file in Path('outputs/optimization_runs').rglob('walk_forward_results.json'):
    with open(log_file) as f:
        data = json.load(f)
    preset_name = log_file.parent.name
    results[preset_name] = data.get('sharpe', 0)

winner = max(results, key=results.get)
print(winner)
PYTHON
)
    
    echo "  Winner: $WINNER"
    
    if bash run_dual_validation.sh --tp-preset "$WINNER" > "$RESULTS_DIR/step4_validation.log" 2>&1; then
        echo "✅ Step 4 complete"
        echo "4" > "$CHECKPOINT_FILE"
    else
        echo "❌ Step 4 failed! Check: $RESULTS_DIR/step4_validation.log"
        exit 1
    fi
fi

# ============================================================================
# STEP 5: GENERATE FINAL REPORT
# ============================================================================

echo ""
echo "======================================================================="
echo "📋 FINAL REPORT"
echo "======================================================================="

python3 << 'PYTHON'
import json
from pathlib import Path
from datetime import datetime

print("\n🎯 OPTIMIZATION SUMMARY")
print("="*70)

# Load final validated params
params = json.load(open('config/validated_production_params.json'))
print(f"\n📊 Production Parameters:")
print(f"   min_rvol: {params.get('min_rvol')}")
print(f"   min_adr: {params.get('min_adr')}")
print(f"   risk_dollars: ${params.get('risk_dollars')}")
print(f"   max_stop_pct: {params.get('max_stop_pct')*100:.1f}%")

# Load TP config
tp = json.load(open('config/tp_optimal.json'))
print(f"\n🎯 TP Distribution:")
print(f"   TP1: {tp['tp1_pct']*100:.0f}%")
print(f"   TP2: {tp['tp2_pct']*100:.0f}%")
print(f"   Runner: {tp['runner_pct']*100:.0f}%")

# Load final results
results = json.load(open('outputs/walk_forward_results.json'))
print(f"\n📈 Performance:")
print(f"   Sharpe: {results.get('sharpe', 'N/A'):.3f}")
print(f"   Return: {results.get('return', 'N/A')*100:.2f}%")
print(f"   Max DD: {results.get('max_dd', 'N/A')*100:.2f}%")
print(f"   Win Rate: {results.get('win_rate', 'N/A')*100:.1f}%")
print(f"   Trades: {results.get('trades', 'N/A')}")

# Production readiness checklist
print(f"\n✅ PRODUCTION READINESS:")
checks = [
    ("Sharpe > 1.0", results.get('sharpe', 0) > 1.0),
    ("Max DD < 20%", abs(results.get('max_dd', 100)) < 0.20),
    ("Trades > 50", results.get('trades', 0) > 50),
    ("Win Rate > 40%", results.get('win_rate', 0) > 0.40),
]

all_passed = all(passed for _, passed in checks)
for check, passed in checks:
    status = "✅" if passed else "❌"
    print(f"   {status} {check}")

if all_passed:
    print(f"\n🎉 READY FOR PRODUCTION!")
else:
    print(f"\n⚠️  NOT READY - Review failed checks")
PYTHON

# Cleanup
rm "$CHECKPOINT_FILE"

echo ""
echo "======================================================================="
echo "✅ WORKFLOW COMPLETE"
echo "======================================================================="
echo "Results saved to: $RESULTS_DIR"
echo ""
echo "Next steps:"
echo "  1. Review results: ls -lh $RESULTS_DIR"
echo "  2. Test in Streamlit: streamlit run app.py"
echo "  3. Monitor live: python3 live_scanner.py"
echo ""
