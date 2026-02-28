#!/bin/bash
# Quick test to reproduce the bug

echo "Testing TP preset application..."

for preset in balanced classic conservative aggressive_runner; do
    echo ""
    echo "==============================================="
    echo "Testing: $preset"
    echo "==============================================="
    
    python3 walk_forward_validation.py \
      --train-months 12 \
      --test-months 3 \
      --walk-months 12 \
      --trials 3 \
      --start 2023-01-01 \
      --end 2024-01-01 \
      --tickers AAPL \
      --tp-preset "$preset" 2>&1 | grep -E "DEBUG TP CONFIG|tp1_pct|tp2_pct|runner_pct|After update" | head -20
    
    echo "Checking validated_production_params.json..."
    python3 -c "
import json
with open('config/validated_production_params.json') as f:
    config = json.load(f)
params = config.get('parameters', {})
print(f'  Saved TP: {params.get(\"tp1_pct\")}/{params.get(\"tp2_pct\")}/{params.get(\"runner_pct\")}')
"
done
