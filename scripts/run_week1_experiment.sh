#!/usr/bin/env bash
# run_week1_experiment.sh
# =======================
# Ejecuta experimentos de combo de forma aislada y segura.
#
# Etapa A: corre UN combo individual y valida no-regresion del campeon.
# Etapa B: opcionalmente corre el torneo completo.
#
# Uso:
#   bash scripts/run_week1_experiment.sh --combo combo_ideal_setup
#   bash scripts/run_week1_experiment.sh --combo combo_stage2_breakout --tournament
#   bash scripts/run_week1_experiment.sh --tournament-only
#
# Variables de entorno opcionales:
#   TRIALS=50   START=2019-01-01   END=2024-12-31   TICKERS=200

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOGS_DIR="$ROOT/logs/week1"
mkdir -p "$LOGS_DIR"

TRIALS="${TRIALS:-100}"
START="${START:-2019-01-01}"
END="${END:-2024-12-31}"
TICKERS="${TICKERS:-200}"
COMBO=""
RUN_TOURNAMENT=false
TOURNAMENT_ONLY=false

# Parse args
while [[ $# -gt 0 ]]; do
    case "$1" in
        --combo)        COMBO="$2"; shift 2 ;;
        --tournament)   RUN_TOURNAMENT=true; shift ;;
        --tournament-only) TOURNAMENT_ONLY=true; shift ;;
        --trials)       TRIALS="$2"; shift 2 ;;
        --tickers)      TICKERS="$2"; shift 2 ;;
        *) echo "Unknown arg: $1"; exit 1 ;;
    esac
done

TS=$(date +%Y%m%d_%H%M%S)

echo "======================================================"
echo "  WEEK1 EXPERIMENT"
echo "  Timestamp: $TS"
echo "  Trials: $TRIALS | Tickers: $TICKERS"
echo "======================================================"

# ─── ETAPA A: combo individual ─────────────────────────────
if [[ -n "$COMBO" ]]; then
    LOG_A="$LOGS_DIR/${COMBO}_${TS}.log"
    echo ""
    echo "ETAPA A: Corriendo $COMBO..."
    echo "  Log: $LOG_A"
    echo ""

    cd "$ROOT"
    python3 scripts/optimize_combo.py \
        --combo "$COMBO" \
        --start "$START" \
        --end "$END" \
        --trials "$TRIALS" \
        --tickers "$TICKERS" \
        2>&1 | tee "$LOG_A"

    echo ""
    echo "ETAPA A completa. Validando no-regresion del campeon..."
    echo ""

    # Siempre validar pullback_entry (el campeon) aunque no lo hayamos tocado
    python3 scripts/validate_combo_regression.py \
        --combo combo_pullback_entry \
        --max-sharpe-drop 15 \
        --max-pbo 0.50

    CHAMP_OK=$?

    # Validar el combo que corrimos (si tiene baseline)
    python3 scripts/validate_combo_regression.py \
        --combo "$COMBO" \
        --max-sharpe-drop 30 \
        --max-pbo 0.80 || true   # no falla el script si el combo no tiene baseline

    if [[ $CHAMP_OK -ne 0 ]]; then
        echo ""
        echo "======================================================"
        echo "  ⛔ ETAPA A: BLOQUEADA — pullback_entry regresiono"
        echo "  Rollback necesario antes de continuar."
        echo "======================================================"
        exit 1
    fi

    echo ""
    echo "  ✅ ETAPA A: pullback_entry intacto. Listo para Etapa B si aplica."
fi

# ─── ETAPA B: torneo completo ───────────────────────────────
if [[ "$RUN_TOURNAMENT" == "true" || "$TOURNAMENT_ONLY" == "true" ]]; then
    LOG_B="$LOGS_DIR/torneo_${TS}.log"
    echo ""
    echo "ETAPA B: Corriendo torneo completo..."
    echo "  Log: $LOG_B"
    echo ""

    cd "$ROOT"
    python3 scripts/optimize_combo.py --all \
        --start "$START" \
        --end "$END" \
        --trials "$TRIALS" \
        --tickers "$TICKERS" \
        2>&1 | tee "$LOG_B"

    echo ""
    echo "ETAPA B completa. Validando no-regresion..."
    echo ""

    python3 scripts/validate_combo_regression.py \
        --combo combo_pullback_entry \
        --max-sharpe-drop 15 \
        --max-pbo 0.50

    CHAMP_OK=$?

    # Contar strict passed del torneo
    STRICT=$(grep -c '"passed": true' "$ROOT/config/combos/top5.json" 2>/dev/null || echo 0)
    echo ""
    echo "======================================================"
    echo "  RESULTADO TORNEO"
    echo "  Strict passed en top5: $STRICT"
    if [[ $CHAMP_OK -eq 0 ]]; then
        echo "  pullback_entry: ✅ intacto"
    else
        echo "  pullback_entry: ❌ REGRESION"
    fi

    if [[ $STRICT -ge 2 && $CHAMP_OK -eq 0 ]]; then
        echo "  CRITERIO SEMANAL: ✅ ALCANZADO ($STRICT/6 strict, campeon OK)"
    else
        echo "  CRITERIO SEMANAL: ❌ NO ALCANZADO (necesitas >=2/6 strict y campeon OK)"
    fi
    echo "======================================================"

    [[ $CHAMP_OK -eq 0 ]] || exit 1
fi

echo ""
echo "Experimento completado: $TS"
