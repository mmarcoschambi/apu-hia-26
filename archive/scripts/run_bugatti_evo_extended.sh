#!/bin/bash
# Bugatti EVO - Extended Testing con múltiples periodos

echo "🏎️💨 BUGATTI EVO - Extended Multi-Period Testing"
echo "================================================="

# Window 1: Pre-COVID
echo ""
echo "🔹 Window 1: Pre-COVID Era (2018-2020)"
python bugatti_evo.py \
    --k-folds 3 \
    --fold-size 300 \
    --l1-trials 100 \
    --l2-trials 50 \
    --in-start 2018-01-01 --in-end 2020-06-30 \
    --val-start 2020-07-01 --val-end 2021-06-30 \
    --oos-start 2021-07-01 --oos-end 2022-12-31 \
    --equity 100000 \
    --run-oos

# Window 2: Post-COVID
echo ""
echo "🔹 Window 2: Post-COVID Era (2021-2023)"
python bugatti_evo.py \
    --k-folds 3 \
    --fold-size 300 \
    --l1-trials 100 \
    --l2-trials 50 \
    --in-start 2021-01-01 --in-end 2023-06-30 \
    --val-start 2023-07-01 --val-end 2024-03-31 \
    --oos-start 2024-04-01 --oos-end 2024-12-31 \
    --equity 100000 \
    --run-oos

# Window 3: Recent Market (Recomendado)
echo ""
echo "🔹 Window 3: Recent Market (2020-2024)"
python bugatti_evo.py \
    --k-folds 3 \
    --fold-size 300 \
    --l1-trials 100 \
    --l2-trials 50 \
    --in-start 2020-01-01 --in-end 2022-12-31 \
    --val-start 2023-01-01 --val-end 2023-12-31 \
    --oos-start 2024-01-01 --oos-end 2024-12-31 \
    --equity 100000 \
    --run-oos

echo ""
echo "✅ All windows completed!"
echo "📊 Check outputs/bugatti_evo/ for results"
