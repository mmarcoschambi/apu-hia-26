# Spec: Quantitative Baseline Integrity & Ingestion Resilience

### Requirement: REQ-QUANT-01 - Baseline Performance Preservation
Cualquier refactor en la capa de datos (`ticker_cache.py`) o señales no debe degradar el retorno acumulado ni empeorar la pérdida máxima del sistema cuantitativo en la ventana canónica oficial de simulación.

#### Scenario: SCEN-01 - Return Percentage Preservation
- **Given** el motor de backtest con configuración Gold Standard Variant E (`docs/GETTING_STARTED.md` §1, Russell 1000 + E25 Sizing + ex-XLV)
- **When** se ejecuta la simulación canónica sobre la ventana oficial de 2 años (2023-2024)
- **Then** el retorno total del sistema debe ser `>= 2.55%` (resultado verificado e idéntico al control de `main` `b13fcbf` + `setdefault`)

#### Scenario: SCEN-02 - Maximum Drawdown Protection
- **Given** la simulación canónica sobre el histórico PIT
- **When** se evalúan las caídas de capital y riesgo en el backtest canónico (2023-2024)
- **Then** el Maximum Drawdown debe mantenerse controlado en `>= -41.95%` y preservar exactamente `158` trades (`gold_standard_variant_e_trades.csv` con SHA-256 idéntico al control de `main`).


#### Scenario: SCEN-03 - Bit-for-Bit Parity Verification (Gold Standard Variant E)
- **Given** una ejecución control en el worktree aislado de `main` (`b13fcbf`) con el parche quirúrgico de crash `setdefault` vs. la rama completa `feature/ticker-cache-harness`
- **When** se comparan los archivos resultantes de operaciones (`outputs/backtests/gold_standard_variant_e_trades.csv`)
- **Then** ambos archivos deben tener paridad byte a byte y coincidir en hash SHA-256 exactamente (`4D646DB6...1CA45E5F`, `35009 bytes`, 158 trades), demostrando que las mejoras de resiliencia en `ticker_cache.py` (`tenacity`, `WAL`, `DLQ`) tienen un desvío numérico exacto de `0.000000%`.

#### Scenario: SCEN-04 - Dynamic Sizing Crash Prevention (`setdefault` Scope Declaration)
- **Given** el motor de simulación `scripts/backtest_via_signal_engine.py`
- **When** el archivo `combo_stage2_breakout_config.json` no existe en `outputs/best_combos_run/` y se carga en modo `base only`
- **Then** el uso de `cfg_b.setdefault("tier1_strategy", {})["risk_dollars"] = dynamic_risk_dollars` previene el `KeyError: 'tier1_strategy'` en el día 6 y activa el sizing dinámico (`total_equity * risk_pct`) para el Sistema B durante toda la simulación. *Declarado como hallazgo arquitectónico y scope creep justificado por pragmatismo en el mismo commit de resiliencia de datos.*

