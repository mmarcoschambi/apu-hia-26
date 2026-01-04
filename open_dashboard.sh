#!/bin/bash
# Quick script to open the dashboard

if [ -f "outputs/backtests/backtest_dashboard.html" ]; then
    echo "🌐 Opening dashboard in browser..."
    xdg-open outputs/backtests/backtest_dashboard.html 2>/dev/null || open outputs/backtests/backtest_dashboard.html 2>/dev/null || start outputs/backtests/backtest_dashboard.html 2>/dev/null
    echo "✅ Dashboard opened!"
else
    echo "❌ Dashboard not found. Generate it first:"
    echo "   python3 src/backtest/dashboard.py outputs/backtests/backtest_results.csv"
fi
