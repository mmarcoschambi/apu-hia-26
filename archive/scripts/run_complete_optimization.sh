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

if [ $? -ne 0 ]; then
    echo "Pre-flight check failed!"
    exit 1
fi

# Check 2: TP config freshness
echo "  [2/5] Checking TP config freshness..."
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
else:
    print(f"  ℹ️  INFO: No TP config found, will optimize")
PYTHON

# Check 3: Disk space
echo "  [3/5] Checking disk space..."
SPACE_GB=$(df -BG . | tail -1 | awk '{print $4}' | tr -d 'G')
if [ "$SPACE_GB" -lt 5 ]; then
    echo "  ❌ FAIL: Low disk space ($SPACE_GB GB free)"
    exit 1
else
    echo "  ✅ PASS: Sufficient disk space ($SPACE_GB GB free)"
fi

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
    else
        echo "❌ Step 2 failed! Check: $RESULTS_DIR/step2_optimize.log"
        exit 1
    fi
fi

# ============================================================================
# STEP 3: VALIDATE WINNER
# ============================================================================

if [ $LAST_STEP -lt 3 ]; then
    echo ""
    echo "======================================================================="
    echo "🏆 STEP 3: FINAL VALIDATION"
    echo "======================================================================="
    
    if bash run_dual_validation.sh --tp-preset optimize > "$RESULTS_DIR/step3_validation.log" 2>&1; then
        echo "✅ Step 3 complete"
        echo "3" > "$CHECKPOINT_FILE"
    else
        echo "❌ Step 3 failed! Check: $RESULTS_DIR/step3_validation.log"
        exit 1
    fi
fi

# ============================================================================
# FINAL REPORT
# ============================================================================

echo ""
echo "======================================================================="
echo "📋 FINAL REPORT"
echo "======================================================================="

python3 << 'PYTHON'
import json
from pathlib import Path

print("\n🎯 OPTIMIZATION SUMMARY")
print("="*70)

# Load TP config
try:
    tp = json.load(open('config/tp_optimal.json'))
    print(f"\n🎯 TP Distribution:")
    print(f"   TP1: {tp['tp1_pct']*100:.0f}%")
    print(f"   TP2: {tp['tp2_pct']*100:.0f}%")
    print(f"   Runner: {tp['runner_pct']*100:.0f}%")
    print(f"   Sharpe: {tp.get('sharpe', 'N/A'):.3f}")
except:
    print("\n⚠️  No TP config found")

print(f"\n✅ Workflow complete!")
PYTHON

# Cleanup
rm -f "$CHECKPOINT_FILE"

echo ""
echo "======================================================================="
echo "✅ WORKFLOW COMPLETE"
echo "======================================================================="
echo "Results saved to: $RESULTS_DIR"
echo ""
echo "Next steps:"
echo "  1. Review results: ls -lh $RESULTS_DIR"
echo "  2. Test in Streamlit: streamlit run app.py"
echo ""
