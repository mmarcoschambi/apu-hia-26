#!/bin/bash
# Setup Historical Metrics Cache - One-time setup
# This will make your backtests 100x faster!

echo "🚀 Historical Metrics Cache Setup"
echo "=================================="
echo ""
echo "This will:"
echo "  1. Add new columns to ohlcv_cache"
echo "  2. Calculate and populate ADR, SMAs, and trend flags"
echo "  3. Test the performance improvement"
echo ""
echo "⏱️  Expected time: 1-3 hours (depending on data size)"
echo "💾  Disk space needed: ~100-500 MB extra"
echo ""

read -p "Continue? (y/n) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]
then
    echo "❌ Cancelled"
    exit 1
fi

echo ""
echo "📝 Step 1/3: Adding columns to database..."
python3 add_historical_metrics.py

if [ $? -ne 0 ]; then
    echo "❌ Error adding columns"
    exit 1
fi

echo ""
echo "🧮 Step 2/3: Calculating historical metrics..."
echo "   (This is the slow part - grab a coffee ☕)"
python3 populate_historical_metrics.py

if [ $? -ne 0 ]; then
    echo "❌ Error calculating metrics"
    exit 1
fi

echo ""
echo "🧪 Step 3/3: Testing performance..."
python3 test_fast_filters.py

echo ""
echo "✅ Setup Complete!"
echo ""
echo "📚 Next steps:"
echo "   - Your backtests will now be MUCH faster"
echo "   - Run backtests as usual - they'll automatically use fast lookups"
echo "   - Read docs/HISTORICAL_METRICS_CACHE.md for details"
echo ""
echo "🔄 Maintenance:"
echo "   - Re-run 'python3 populate_historical_metrics.py' when adding new data"
echo ""
