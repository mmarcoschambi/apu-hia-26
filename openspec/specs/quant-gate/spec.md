# Spec: Quantitative Baseline Integrity & Ingestion Resilience

### Requirement: REQ-QUANT-01 - Baseline Performance Preservation
Cualquier refactor en la capa de datos (`ticker_cache.py`) o señales no debe degradar el retorno acumulado ni empeorar la pérdida máxima del sistema cuantitativo en simulación histórica.

#### Scenario: SCEN-01 - Return Percentage Preservation
- **Given** el motor de backtest con configuración Gold Standard Variant E (`production_config.json`, Russell 1000 + E25 Sizing + ex-XLV, 2023-2024)
- **When** se ejecuta la simulación completa sobre el universo histórico PIT
- **Then** el retorno total del sistema debe ser `>= 2.55%` (idéntico al baseline verificado de control `main` `b13fcbf` + fix `setdefault`)

#### Scenario: SCEN-02 - Maximum Drawdown Protection
- **Given** la simulación Gold Standard Variant E sobre el histórico PIT
- **When** se evalúan las caídas de capital y riesgo en el backtest (2023-2024)
- **Then** el Maximum Drawdown debe mantenerse controlado en `>= -41.95%` y preservar exactamente `158` trades (coincidiendo 100% con el baseline `main` `b13fcbf` + `setdefault`)

