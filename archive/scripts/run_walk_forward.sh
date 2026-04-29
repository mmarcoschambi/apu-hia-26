#!/bin/bash
# Walk Forward Validation Runner
# ===============================

echo "🚀 WALK FORWARD ANALYSIS"
echo "========================================"

# Default parameters
TRAIN_MONTHS=12
TEST_MONTHS=3
WALK_MONTHS=3
TRIALS=20
START="2019-01-01"
END="2025-12-31"

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --train) TRAIN_MONTHS=$2; shift 2;;
        --test) TEST_MONTHS=$2; shift 2;;
        --walk) WALK_MONTHS=$2; shift 2;;
        --trials) TRIALS=$2; shift 2;;
        --start) START=$2; shift 2;;
        --end) END=$2; shift 2;;
        --quick) TRAIN_MONTHS=6; TEST_MONTHS=2; WALK_MONTHS=2; TRIALS=20; shift;;
        *) echo "Unknown option: $1"; exit 1;;
    esac
done

echo "📅 Period: $START → $END"
echo "⚙️  Train: ${TRAIN_MONTHS}m | Test: ${TEST_MONTHS}m | Walk: ${WALK_MONTHS}m"
echo "🔬 Trials per window: $TRIALS"
echo ""

# Check for universe file
UNIVERSE_ARG=""
if [ -f "sp500_tickers_since_2014.txt" ]; then
    echo "📂 Using S&P 500 Universe (sp500_tickers_since_2014.txt)"
    UNIVERSE_ARG="--universe-file sp500_tickers_since_2014.txt"
elif [ -f "top_global_tickers.txt" ]; then
    echo "📂 Using Top Global Universe (top_global_tickers.txt)"
    UNIVERSE_ARG="--universe-file top_global_tickers.txt"
else
    echo "⚠️  No universe file found. Using default Mega-Cap list."
fi

python3 walk_forward_validation.py \
    --train-months $TRAIN_MONTHS \
    --test-months $TEST_MONTHS \
    --walk-months $WALK_MONTHS \
    --trials $TRIALS \
    --start $START \
    --end $END \
    $UNIVERSE_ARG

echo ""
echo "✅ Walk Forward Complete!"
echo "📊 Results saved to: outputs/walk_forward_results.json"
