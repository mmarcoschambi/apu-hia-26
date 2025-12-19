#!/bin/bash
# Quick script to open the dashboard

if [ -f "backtest_dashboard.html" ]; then
    echo "🌐 Opening dashboard in browser..."
    xdg-open backtest_dashboard.html 2>/dev/null || open backtest_dashboard.html 2>/dev/null || start backtest_dashboard.html 2>/dev/null
    echo "✅ Dashboard opened!"
else
    echo "❌ Dashboard not found. Generate it first:"
    echo "   python3 src/backtest/dashboard.py backtest_results.csv"
fi
