#!/bin/bash
cd /home/marcos/trade/momentum-v2
for val in 2.0 2.5 3.0; do
  sed -i "s/^ATR_RISK_FILTER = .*/ATR_RISK_FILTER = $val/" scripts/backtest_via_signal_engine.py
  echo "=== ATR=$val ==="
  python3 scripts/backtest_via_signal_engine.py --start 2024-01-01 --end 2024-03-31 --capital 100000 --universe-size 200 --tag e14_cal_q1 2>&1 | tail -15
  echo "---"
done
sed -i "s/^ATR_RISK_FILTER = .*/ATR_RISK_FILTER = 2.5/" scripts/backtest_via_signal_engine.py
echo "Restaurado a 2.5"