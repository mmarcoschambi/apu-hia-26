#!/bin/bash
# Quick Bugatti EVO Run - Configuración Óptima

echo "🏎️ BUGATTI EVO - Quick Production Run"
echo "======================================"
echo ""
echo "Configuración:"
echo "  K-Folds: 3"
echo "  Fold Size: 100 tickers"
echo "  L1 Trials: 50"
echo "  L2 Trials: 30"
echo "  Period: 2020-2024"
echo ""
echo "Tiempo estimado: 15-20 minutos"
echo ""
read -p "¿Continuar? (y/n): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    python3 bugatti_evo.py \
      --k-folds 3 \
      --fold-size 100 \
      --l1-trials 50 \
      --l2-trials 30 \
      --equity 100000 \
      --seed 42 \
      --in-start 2020-01-01 \
      --in-end 2022-12-31 \
      --val-start 2023-01-01 \
      --val-end 2023-06-30 \
      --oos-start 2023-07-01 \
      --oos-end 2024-12-31 \
      --run-oos
else
    echo "Cancelado."
fi
