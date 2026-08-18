# Proposal: feat(indicators): Add rolling percentile ATR volatility helper with unit tests

## Intent
### Propósito
Implementar un helper funcional calculate_atr_percentile(high, low, close, period=14, window=100) en src/indicators/atr.py para normalizar la volatilidad del True Range en percentiles móviles (0-100%).

### Acceptance Criteria
- [ ] Función calculate_atr_percentile en src/indicators/atr.py con type hints y docstring en español.
- [ ] Retorna pandas.Series con valores normalizados en rango [0, 100].
- [ ] Manejo correcto de NaNs iniciales sin excepciones.
- [ ] Suite de tests formal pytest en tests/test_atr_percentile.py bajo ciclo TDD (RED -> GREEN).
- [ ] pytest tests/test_atr_percentile.py pasa al 100% sin warnings.
- [ ] Commit con formato: [Indicators] Add rolling percentile ATR helper. Fixes #65

### Baseline a no degradar
N/A (feature aditiva, no toca backtest core).

### Módulos sensibles
N/A (no modifica src/backtest/ ni src/data/).

### Módulo objetivo de la inspección
src/indicators/atr.py y tests/test_atr_percentile.py

## Context
URL: https://github.com/mmarcoschambi/swing-momentum-v1/issues/65
Labels: feat
