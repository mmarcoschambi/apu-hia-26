#!/bin/bash
echo "🏎️ Populating S&P 500 tickers from sp500_tickers_since_2014.txt"
echo "Time: ~30 minutes"
echo ""
python3 add_tickers_quick.py --file sp500_tickers_since_2014.txt --skip-existing
