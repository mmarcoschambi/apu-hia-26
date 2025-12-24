#!/bin/bash
# QUICK START - Live Trading Setup

echo "🚀 MOMENTUM TRIAD - LIVE TRADING SETUP"
echo "========================================"
echo ""

# Check if watchlist exists
if [ ! -f "acciones_activas.csv" ]; then
    echo "📋 Creating sample watchlist..."
    cat > acciones_activas.csv << 'EOF'
Ticker
AAPL
NVDA
TSLA
META
GOOGL
MSFT
AMD
AVGO
SMCI
PLTR
EOF
    echo "✅ Created acciones_activas.csv with 10 sample tickers"
else
    echo "✅ Watchlist already exists: acciones_activas.csv"
fi

# Create empty tracking files if they don't exist
if [ ! -f "active_positions.json" ]; then
    echo "{}" > active_positions.json
    echo "✅ Created active_positions.json"
fi

if [ ! -f "closed_trades.csv" ]; then
    echo "symbol,entry_date,exit_date,camino,entry_price,exit_price,shares,stop_loss,pnl,pnl_pct,r_multiple,notes" > closed_trades.csv
    echo "✅ Created closed_trades.csv"
fi

echo ""
echo "📚 AVAILABLE COMMANDS:"
echo "===================="
echo ""
echo "🌅 MORNING ROUTINE (Run at 8:00 AM):"
echo "   python morning_workflow.py"
echo ""
echo "🛡️  HEALTH CHECK ONLY:"
echo "   python market_health_check.py"
echo ""
echo "🔍 SCAN WATCHLIST:"
echo "   python live_trading_scanner.py"
echo ""
echo "💼 MANAGE POSITIONS:"
echo "   python position_tracker.py                          # View all"
echo "   python position_tracker.py --update                 # Update prices"
echo "   python position_tracker.py --add AAPL 150 145 100 Camino1  # Add position"
echo "   python position_tracker.py --close AAPL 155         # Close position"
echo "   python position_tracker.py --history                # View closed trades"
echo ""
echo "📋 FULL DAILY WORKFLOW:"
echo "   python daily_workflow.py pre-market     # 8:00 AM"
echo "   python daily_workflow.py market-open    # 9:30 AM"
echo "   python daily_workflow.py mid-day        # 12:00 PM"
echo "   python daily_workflow.py market-close   # 4:00 PM"
echo ""
echo "📖 DOCUMENTATION:"
echo "   LIVE_TRADING_GUIDE.md - Complete guide from backtest to live"
echo "   MARKET_FILTERS.md - Understanding market health checks"
echo "   QUICKREF.md - Quick reference for all features"
echo ""
echo "✅ Setup complete! Ready for live trading."
echo ""
echo "⚠️  IMPORTANT: Start with paper trading for 2 weeks before going live!"
echo ""
