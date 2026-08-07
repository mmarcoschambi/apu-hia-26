# 🎯 SYSTEM_CONTEXT.md — Estado Actual y Mapa del Sistema

Este documento es la **única fuente de verdad (Single Source of Truth)** sobre el estado de desarrollo, reglas de negocio activas, arquitectura de software y decisiones estratégicas de **Momentum v2**.

---

## 1. ¿Qué hace el sistema HOY?

**Momentum v2** es un sistema de swing trading cuantitativo de alta convicción (horizonte temporal de holding >= 10 días). El sistema busca capturar setups de momentum en acciones individuales basándose en la **fuerza relativa**, **rotación sectorial**, **regímenes de mercado** y **divergencia temática**.

El sistema es auto-consciente de su entorno (**Auto-Aware**):
*   **Laboratory (Local / WSL2):** Corre en **Modo Híbrido** con `data/ticker_cache.db`. Utiliza el universo local Point-In-Time (PIT) basado en volumen de dólares (ADV Top 200) para decisiones principales y Finviz como observación.
*   **Torre de Control (VPS):** No posee base de datos local pesada. Promueve de forma autónoma la watchlist de **Finviz Live** como fuente primaria para monitoreo y alertas 24/7.

---

## 2. Módulos y Estado Operativo

| Módulo | Componente en Producción | Estado Actual / Reglas de Negocio |
| :--- | :--- | :--- |
| **Señales** | [signal_engine.py](file:///home/marcos/trade/momentum-v2/src/signals/signal_engine.py) | **Verdad Canónica.** Indicadores técnicos, Trend Intensity, Relative Strength y condiciones técnicas de entrada. |
| **Filtros Tier 2** | [thematic_logic.py](file:///home/marcos/trade/momentum-v2/src/signals/thematic_logic.py) | Filtros de Fuerza Relativa, ADR (volatilidad) y Sector ETF. |
| **Divergencia Temática** | [thematic_logic.py](file:///home/marcos/trade/momentum-v2/src/signals/thematic_logic.py) | **Variante E (Shadow Mode):** Setup válido si el Tema es alcista pero el Sector es neutral/bajista. Acumulando señales en `rejection_audit.csv`. |
| **Sizing y Riesgo** | [risk_manager.py](file:///home/marcos/trade/momentum-v2/src/utils/risk_manager.py) / [position_sizing.py](file:///home/marcos/trade/momentum-v2/src/risk/position_sizing.py) | **Doble rol:** `risk_manager.py` gestiona sizing y límites de exposición en live/scanner. `position_sizing.py` provee las funciones vectorizadas equivalentes para simulaciones de backtesting. |
| **Simulador** | [backtest_via_signal_engine.py](file:///home/marcos/trade/momentum-v2/scripts/backtest_via_signal_engine.py) / [vectorbt_engine_advanced.py](file:///home/marcos/trade/momentum-v2/src/backtest/vectorbt_engine_advanced.py) | **Verdad Canónica de simulación.** `backtest_via_signal_engine.py` es el script de entrada que orquesta el backtest. `vectorbt_engine_advanced.py` es el motor core basado en vectorbt. |
| **Live Scanner** | [live_trading_scanner.py](file:///home/marcos/trade/momentum-v2/scripts/live_trading_scanner.py) | Escaneo en vivo. Generación diaria de alertas en `outputs/live_signals/`. |
| **Machine Learning** | [entry_scorer_gate.py](file:///home/marcos/trade/momentum-v2/src/ml/entry_scorer_gate.py) / [trainer.py](file:///home/marcos/trade/momentum-v2/src/ml_signal/trainer.py) | **Clasificación y Filtro.** `src/ml/` se encarga del scoring e inyección de filtros en vivo y simulación (`entry_scorer_gate.py`). `src/ml_signal/` contiene el pipeline de desarrollo: features (`features.py`), entrenamiento walk-forward (`trainer.py`) y auditoría (`audit.py`). |

---

## 3. Decisiones de Arquitectura e Historial de Trading (ADRs)

### Las 5 decisiones estratégicas más importantes:

1.  **Motor Vectorizado vectorbt sobre Backtrader (2026-06):** Para eliminar loops de Python y permitir búsquedas de hiperparámetros con Optuna en segundos.
2.  **Gold Standard ex-XLV (2026-05):** Exclusión estricta del sector salud (XLV) tras verificar degradación sistémica en backtests. (Baseline: Russell 1000 + E25 Sizing + ex-XLV -> +96.12% Return, -35.09% MDD).
3.  **Separación de Entornos (Local vs. VPS):** Local corre híbrido con PIT DB, VPS corre en tiempo real con Finviz sin DB para evitar snapshotting costoso y mantener la agilidad del deploy.
4.  **Verdad Canónica Compartida:** Backtest y Live Scanner consumen exactamente el mismo archivo de lógica de señales ([signal_engine.py](file:///home/marcos/trade/momentum-v2/src/signals/signal_engine.py)).
5.  **Strict TDD Mode:** Lógica de entrada/salida protegida por pruebas unitarias obligatorias en [tests/](file:///home/marcos/trade/momentum-v2/tests/) (Fase Red -> Green).

### Baselines de referencia (dos distintos)

El sistema distingue **DOS baselines independientes** que no deben confundirse ni usarse como intercambiables:

| Baseline | Métricas | Rol |
| :--- | :--- | :--- |
| **Histórico Gold Standard** (Russell 1000 + E25 Sizing + ex-XLV) | **96.12% Return / -35.09% MDD** | Baseline oficial de referencia de producción. Toda estrategia promovida debe no degradar estas métricas (Return >= 96%, MDD <= -36%). |
| **Variante E (Divergencia Temática — Shadow Mode)** | **2.55% Return** | Baseline de experimento en shadow trading. Acumulando señales reales antes de su promoción; NO es referencia de producción. |

---

## 4. Estado de Desarrollo y Roadmap
 
### 🟢 Activo en Producción / Live
*   Exclusión activa de XLV en el scanner y backtests diarios.
*   Auditoría diaria automatizada de señales aprobadas y rechazadas (`rejection_audit.csv`).
*   Configuraciones leídas directamente de [production_config.json](file:///home/marcos/trade/momentum-v2/config/production_config.json).
*   **Breadth Gate (Filtro de participación de mercado):** Optimizado y validado en Walk-Forward de 15 pliegues (Modos A y B). Determinado NO-GO para su uso estático (degrada Sharpe de 0.39 a 0.23). Se promueve a Gate Dinámico Condicional acoplado al Regime Detection (umbral 0.40 en Modo B activado únicamente en mercados correctivos/bajistas).
*   **Dynamic Switch (Ataque/Defensa):** **PROMOVIDO a producción.** Precarga histórica completada (8,195 registros, 1993-2026). `health_score` (0-7) vía `src/utils/market_health.py`. Evidencia empírica validada con script three-way `scripts/run_dynamic_switch_backtest.py`.
*   **Shadow Convergence Audit:** `scripts/convergence_check.py` con Jaccard scoring, price discrepancy gate (<2%), y fallback VPS_UNAVAILABLE. `daily_scan.py` emite `scan_metadata.json`. Fixes #49.
 
### 🟡 En Desarrollo / Shadow Mode
*   **Variante E (Divergencia Temática):** Monitoreo pasivo en shadow trading para acumular ~30-40 señales reales antes de su promoción.
*   **Purged Walk-Forward Cross-Validation:** Implementado en `src/validation/purged_walk_forward.py` con purge (10d) y embargo (5d). Degradation gate: 25%. Integrado como Phase 2b opcional en `ResearchGate.validate_strategy()`. **Estado: NO VERIFICABLE** — `purged_walk_forward.py` es biblioteca pura sin persistencia en disco. Para auditar, se necesita ejecutar `scripts/run_purged_cv_freeze_evidence.py` y analizar el JSON resultante.
*   **VPS Deploy & Control Tower:** `scripts/sv/` con systemd units, health check, PID lifecycle. `deploy_vps.sh` validado con 5-step pipeline. `start_live_session.sh` migrado a systemd-first con fallback nohup+PID.
 
### 🔴 Bloqueado / Pendiente
*   **Unificación de Pipelines ML:** `src/ml_signal/` (walk-forward con features de mercado) y `src/ml/` (entry scoring con features de setup) son pipelines independientes, sin features compartidos ni `models/entry_scorer.pkl` en disco. Documentado en DECISIONS.md — pendiente de estrategia de consolidación cross-sesión.
*   **Shadow watchlist_detail gap:** `experiments/shadow_watchlist_sim.py` reporta ~44% de omisión en watchlist_detail (331/591 tickers únicos).
 
### ❌ Descartado Definitivamente
*   **Modelos Random Forest tradicionales de sklearn:** Reemplazados por LightGBM debido a su velocidad de entrenamiento y feature importance nativa óptima para series de tiempo.
*   **GridSearch:** Reemplazado por Optuna con algoritmos de poda (pruning) eficientes.
*   **Salidas por salud de mercado (Fase-Aware y Binarias):** Se descartaron definitivamente tras simulación a 6 años (2019-2025). Multiplican la fricción transaccional por 4 (1,091 trades) y cortan las ganancias de líderes, degradando severamente el retorno (37.5% vs 222.3% baseline). El control macro debe limitarse al Sizing Gate de entrada.

---

## 5. Mapa de Archivos Clave para la IA

*   **Punto de partida del sistema:** [docs/GETTING_STARTED.md](file:///home/marcos/trade/momentum-v2/docs/GETTING_STARTED.md)
*   **Playbook de desarrollo:** [docs/playbook_sdd_scrumban.md](file:///home/marcos/trade/momentum-v2/docs/playbook_sdd_scrumban.md)
*   **Reglas de comportamiento y ScrumBan del Agente (Control de IA):** [AGENTS.md](file:///home/marcos/trade/momentum-v2/AGENTS.md)
*   **Instrucciones del proyecto para Gemini (Control de IA):** [GEMINI.md](file:///home/marcos/trade/momentum-v2/GEMINI.md)
*   **Lógica de Sizing histórica:** [docs/archive/decisions/ADR_POSITION_SIZING.md](file:///home/marcos/trade/momentum-v2/docs/archive/decisions/ADR_POSITION_SIZING.md)
*   **Análisis detallados de baselines:** [docs/archive/analysis/](file:///home/marcos/trade/momentum-v2/docs/archive/analysis/)
