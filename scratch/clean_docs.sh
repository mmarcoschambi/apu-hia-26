#!/bin/bash
set -e

# Asegurar que los directorios destino existen
mkdir -p docs/archive/session-artifacts
mkdir -p docs/archive/decisions
mkdir -p docs/archive/analysis
mkdir -p docs/archive/old-readmes

# --- Capa 2: Clasificar y mover archivos de docs/analysis/ ---

# Mover resúmenes de validación de Russell a archive/analysis
if ls docs/analysis/russell_baseline_* 1>/dev/null 2>&1; then
    mv docs/analysis/russell_baseline_* docs/archive/analysis/
fi

# Mover decisions/ADRs históricos de docs/analysis/
DECISION_FILES=(
    "docs/analysis/CYCLE_E12_E15_RETROSPECTIVE.md"
    "docs/analysis/S4_OPTIMIZATION_CLOSURE_20260410.md"
    "docs/analysis/S5_RUSSELL_OPTUNA_DESIGN_SPEC.md"
)
for f in "${DECISION_FILES[@]}"; do
    [ -f "$f" ] && mv "$f" docs/archive/decisions/
done

# Mover análisis específicos de docs/analysis/
ANALYSIS_FILES=(
    "docs/analysis/REGIME_BASELINE_FASE0_COMPLETE.md"
    "docs/analysis/REGIME_ML_FASE1_COMPLETE.md"
    "docs/analysis/ML_SIGNAL_FASE2_COMPLETE.md"
    "docs/analysis/THEMATIC_DIVERGENCE_VERIFICATION_E11.md"
    "docs/analysis/S5_BASELINE_VAL_REPORT.md"
    "docs/analysis/BREADTH_EXECUTIVE_SUMMARY.md"
    "docs/analysis/BREADTH_EXPERIMENT_PROTOCOL.md"
    "docs/analysis/FINAL_ANALYSIS.md"
    "docs/analysis/ANALISIS_MEJORA_PERFORMANCE.md"
    "docs/analysis/KEY_INSIGHTS.md"
)
for f in "${ANALYSIS_FILES[@]}"; do
    [ -f "$f" ] && mv "$f" docs/archive/analysis/
done

# Mover artefactos de sesión / fixes de docs/analysis/
SESSION_FILES=(
    "docs/analysis/BUG_FIX_COMPLETE.md"
    "docs/analysis/FIX_COMPLETED.md"
    "docs/analysis/FIXES_APPLIED_FINAL.md"
    "docs/analysis/FIXES_APPLIED_SUMMARY.md"
    "docs/analysis/FIX_SUMMARY.md"
    "docs/analysis/EXIT_LOGIC_FIX_SUMMARY.md"
    "docs/analysis/BUG_TP_PRESETS_IDENTICAL.md"
    "docs/analysis/BUG_SAME_DAY_EXITS.md"
    "docs/analysis/BUG_ANALYSIS_NON_DETERMINISTIC.md"
    "docs/analysis/DATA_CLEANUP_REPORT.md"
    "docs/analysis/BREADTH_CLOSURE_FINAL.md"
    "docs/analysis/IMPLEMENTATION_SUMMARY.md"
    "docs/analysis/IMPLEMENTATION_SUMMARY_TP_OPTIMIZATION.md"
    "docs/analysis/IMPLEMENTATION_STATUS.md"
    "docs/analysis/CHANGELOG_TP_OPTIMIZATION.md"
)
for f in "${SESSION_FILES[@]}"; do
    [ -f "$f" ] && mv "$f" docs/archive/session-artifacts/
done

# --- Capa 2.1: Clasificar y mover archivos de docs/ raíz ---

# Mover artefactos de sesión de docs/ raíz
DOCS_ROOT_SESSION=(
    "docs/RESUMEN_CAMBIOS_SESION.md"
    "docs/FILTROS_IMPLEMENTADOS.txt"
    "docs/IMPLEMENTACIONES_FINALES.txt"
    "docs/IMPLEMENTACION_SALIDAS_PARCIALES.txt"
    "docs/CAMBIO_IMPLEMENTADO_VELA_VERDE.md"
    "docs/CAMBIOS_FILTRO_MCAP.md"
    "docs/FIX_BACKTEST_NO_TRADES.md"
    "docs/IC_PHASE1_FREEZE_2026-04-15.md"
    "docs/SESSION_2026-05-02.md"
    "docs/temp_custom_symbols.txt"
    "docs/pattern_analysis_SMCI.txt"
)
for f in "${DOCS_ROOT_SESSION[@]}"; do
    [ -f "$f" ] && mv "$f" docs/archive/session-artifacts/
done

# Mover decisions de docs/ raíz
DOCS_ROOT_DECISIONS=(
    "docs/ADR_POSITION_SIZING.md"
    "docs/VECTORBT_MIGRATION.md"
    "docs/VECTORBT_TECHNICAL.md"
    "docs/VECTORBT_LONG_RANGES.md"
    "docs/EXPLICACION_FILTRO_LIQUIDEZ.md"
    "docs/DYNAMIC_DATE_FILTERS.md"
    "docs/risk_profiles_guide.md"
)
for f in "${DOCS_ROOT_DECISIONS[@]}"; do
    [ -f "$f" ] && mv "$f" docs/archive/decisions/
done

# Mover análisis de docs/ raíz
DOCS_ROOT_ANALYSIS=(
    "docs/REGIME_FASE1_RF_REPORT.md"
    "docs/REGIME_FASE2_SIGNAL_QUALITY_PLAN.md"
    "docs/quantconnect_coverage.md"
    "docs/3tier_streamlit_integration.md"
    "docs/STREAMLIT_DYNAMIC_DATES_SUMMARY.md"
    "docs/exit_config_audit.md"
    "docs/shadow_data_inventory.md"
    "docs/CURRENT_STATE_SUMMARY.md"
    "docs/RELEASE_SECTOR_ETF_FILTER.md"
    "docs/RVOL_FILTER_IMPLEMENTATION.md"
)
for f in "${DOCS_ROOT_ANALYSIS[@]}"; do
    [ -f "$f" ] && mv "$f" docs/archive/analysis/
done

# --- Capa 3: Duplicados de README y START_HERE ---

# Si ya existía un GETTING_STARTED.md viejo, lo archivamos antes de mover START_HERE_NOW.md
if [ -f "docs/GETTING_STARTED.md" ] && [ -f "docs/START_HERE_NOW.md" ]; then
    mv docs/GETTING_STARTED.md docs/archive/old-readmes/GETTING_STARTED_OLD.md
fi

# Renombrar nuestro START_HERE_NOW.md unificado a GETTING_STARTED.md
if [ -f "docs/START_HERE_NOW.md" ]; then
    mv docs/START_HERE_NOW.md docs/GETTING_STARTED.md
fi

# Mover antiguos readmes y start-heres a docs/archive/old-readmes/
OLD_READMES=(
    "docs/START_HERE_LIVE.md"
    "docs/START_HERE.txt"
    "docs/LEE_ESTO_PRIMERO.txt"
    "docs/EMPIEZA_AQUI_LIVE_TRADING.txt"
    "docs/README_SISTEMA.md"
    "docs/README_LIVE_TRADING.md"
    "docs/INDEX_LIVE_TRADING.md"
    "docs/README.md"
)

for f in "${OLD_READMES[@]}"; do
    [ -f "$f" ] && mv "$f" docs/archive/old-readmes/
done

echo "Reorganización de docs completada con éxito."
