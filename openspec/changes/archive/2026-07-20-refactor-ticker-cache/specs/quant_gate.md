# Spec: Quantitative Baseline Integrity & Ingestion Resilience

### Requirement: REQ-QUANT-01 - Baseline Performance Preservation
Cualquier refactor en la capa de datos (`ticker_cache.py`) o señales no debe degradar el retorno acumulado ni empeorar la pérdida máxima del sistema cuantitativo en simulación histórica.

#### Scenario: SCEN-01 - Return Percentage Preservation
- **Given** el motor de backtest con configuración canónica de producción (`production_config.json`)
- **When** se ejecuta la simulación completa sobre el universo histórico PIT
- **Then** el retorno total del sistema debe ser `>= 96.12%`

#### Scenario: SCEN-02 - Maximum Drawdown Protection
- **Given** la simulación canónica sobre el histórico PIT
- **When** se evalúan las caídas de capital y riesgo en el backtest
- **Then** el Maximum Drawdown debe mantenerse strictly controlado en `>= -35.09%` (no caer a -36% ni -40%)
