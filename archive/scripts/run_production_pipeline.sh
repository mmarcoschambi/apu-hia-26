#!/bin/bash
#
# BUGATTI PRODUCTION PIPELINE
# ============================
# Implements the Dual Mode Architecture:
# 1. CONVERGENCE CHECK (THOR vs Advanced Fixed Risk)
#    - Validates that signal logic is sound and matches legacy engine.
# 2. PRODUCTION RUN (Advanced Percentage Risk)
#    - Simulates real performance with Compounding.
#
# Usage:
#   ./run_production_pipeline.sh [--tickers T,I,C,K...] [--start 2023-01-01]

set -e

TICKERS="AAPL,MSFT,NVDA,TSLA,AMD,META,GOOGL,AMZN"
START_DATE="2023-01-01"
END_DATE="2023-12-31"

while [[ $# -gt 0 ]]; do
    case $1 in
        --tickers)
            TICKERS="$2"
            shift 2
            ;; 
        --start)
            START_DATE="$2"
            shift 2
            ;; 
        --end)
            END_DATE="$2"
            shift 2
            ;; 
        *)
            echo "Unknown option: $1"
            exit 1
            ;; 
    esac
done

echo "================================================================================"
echo "🚀 BUGATTI DUAL MODE PIPELINE"
echo "================================================================================"
echo ""

# ----------------------------------------------------------------------------
# PHASE 1: CONVERGENCE VALIDATION
# ----------------------------------------------------------------------------
echo "🔬 PHASE 1: CONVERGENCE CHECK (THOR vs Advanced Fixed Risk)"
echo "   Goal: Validate signal logic consistency."
echo "--------------------------------------------------------------------------------"

python3 debug_convergence.py \
    --tickers "$TICKERS" \
    --start "$START_DATE" \
    --end "$END_DATE"

if [ $? -ne 0 ]; then
    echo "❌ CONVERGENCE CHECK FAILED!"
    exit 1
fi

echo ""
echo "✅ Convergence check passed. Proceeding to Production simulation."
echo ""

# ----------------------------------------------------------------------------
# PHASE 2: PRODUCTION SIMULATION
# ----------------------------------------------------------------------------
echo "💰 PHASE 2: PRODUCTION RUN (Percentage Risk + Compounding)"
echo "   Goal: Simulate real-world performance."
echo "--------------------------------------------------------------------------------"

# Run Advanced Engine in Production Mode
python3 backtest_vectorbt_advanced.py \
    --tickers "$TICKERS" \
    --start "$START_DATE" \
    --end "$END_DATE" \
    --mode production \
    --equity 100000 \
    --risk 1.5

echo ""
echo "✅ Production run complete."
echo "================================================================================"
echo "🏁 PIPELINE FINISHED"
echo "================================================================================"
