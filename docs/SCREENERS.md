# Sistema Multi-Screener — momentum-v2

## Screeners disponibles

| Nombre | Descripción | Patrones compatibles |
|---|---|---|
| `minervini_trend` | Stage 2 Trend Template (7 criterios) | vcp, cup_and_handle, flat_base, pocket_pivot, breakout |
| `ema21_pullback` | Pullback a 21EMA en zona ATR válida (-0.5R a +1R) | pocket_pivot, breakout |
| `qullamaggie_momentum` | Top 3% RS + MA Stack completo | vcp, pocket_pivot, breakout |
| `vcp_enhanced` | VCP con Volatility Contraction Score (VCS 0-100) | vcp |

---

## Uso básico (live_scanner.py)

```bash
# Un screener
python live_scanner.py --screener minervini_trend

# Combinación AND (todos deben pasar)
python live_scanner.py --screener minervini_trend+vcp_enhanced --screener-mode all

# Combinación OR (al menos uno debe pasar)
python live_scanner.py --screener qullamaggie_momentum+ema21_pullback --screener-mode any

# Con configuración custom
python live_scanner.py --screener minervini_trend --screener-config config/screeners/minervini_trend.json
```

---

## Uso programático

```python
from src.screeners import ScreenerRegistry, ScreenerPipeline

# Screener individual
screener = ScreenerRegistry.get('minervini_trend')
result = screener.scan('NVDA', df)
print(result.passed, result.score, result.reason)

# Pipeline AND
pipeline = ScreenerPipeline([
    ScreenerRegistry.get('minervini_trend'),
    ScreenerRegistry.get('vcp_enhanced'),
], mode='all')
result = pipeline.scan('NVDA', df)

# Pipeline OR
pipeline = ScreenerPipeline([
    ScreenerRegistry.get('qullamaggie_momentum'),
    ScreenerRegistry.get('ema21_pullback'),
], mode='any')

# Listar disponibles
print(ScreenerRegistry.list_available())
# → ['minervini_trend', 'ema21_pullback', 'qullamaggie_momentum', 'vcp_enhanced']

# Ver descripciones
print(ScreenerRegistry.describe())
```

---

## ScreenerResult

```python
@dataclass
class ScreenerResult:
    passed: bool          # True/False
    ticker: str
    screener_name: str
    score: float          # 0-100 para ranking
    metrics: dict         # Métricas detalladas del screener
    reason: str           # Por qué pasó/falló
```

---

## Configuración (JSON)

Los JSONs están en `config/screeners/`. Ejemplo mínimo:

```json
{
  "name": "minervini_trend",
  "min_price": 10.0,
  "params": {
    "max_dist_from_52wk_high_pct": 20.0
  }
}
```

Todos los campos de `ScreenerConfig` son opcionales — los no especificados toman el valor por defecto del screener.

---

## Minervini Trend Template — criterios

1. `price > SMA150` AND `price > SMA200`
2. `SMA150 > SMA200`
3. `SMA200` en uptrend (comparado 22 días atrás)
4. `SMA50 > SMA150 > SMA200`
5. `price > SMA50`
6. `price >= 52wk_high * (1 - 0.25)` — dentro del 25% del máximo anual
7. `price >= 52wk_low * 1.30` — al menos 30% sobre el mínimo anual

Score = criterios_pasados / 7 × 100. Requiere todos (7/7) para `passed=True`.

---

## EMA21 Pullback — criterios

1. **Zona EMA21**: `(price - EMA21) / ATR` entre -0.5R y +1.0R
2. **Zona SMA50**: `(price - SMA50) / ATR` entre 0.0R y +3.0R
3. `price >= EMA21 × 0.995` — no romper el soporte

Score basado en proximidad al centro de la zona ideal.

---

## Qullamaggie Momentum — criterios

1. **RS Percentil ≥ 97** — Top 3% del universo (lee de `daily_rs_rankings`)
2. **MA Stack**: `price ≥ EMA10 ≥ SMA20 ≥ SMA50 ≥ SMA100 ≥ SMA200` (tolerancia 0.2%)
3. **Trend Intensity**: `(SMA13 / SMA65) × 100 ≥ 108`

Si `daily_rs_rankings` no tiene datos para ese ticker/fecha, hace fallback calculando RS vs SPY.

---

## VCP Enhanced — criterios + VCS Score

**Volatility Contraction Score (VCS, 0-100)**:

| Componente | Peso | Cálculo |
|---|---|---|
| Price Compression | 35% | `1 - ATR13/ATR63` |
| Price Stability | 30% | `1 - StdDev13/StdDev63` |
| Volume Contraction | 25% | `1 - Vol13/Vol63 × 0.5` |
| Structure Bonus | 10% | Proporción de higher lows locales |

**Criterios de aprobación**:
1. `VCS Score ≥ 60`
2. `n_contracciones ≥ 2`
3. Higher lows presentes
4. Pasa Minervini Trend Template (5 de 7 criterios)

---

## RS Cross-Sectional (Fase 0)

Para `qullamaggie_momentum` se requiere poblar `daily_rs_rankings`:

```bash
# Poblar día de hoy
python scripts/populate_rs_rankings.py

# Poblar últimos 30 días
python scripts/populate_rs_rankings.py --days-back 30

# Fecha específica
python scripts/populate_rs_rankings.py --date 2025-06-15

# Sobreescribir datos existentes
python scripts/populate_rs_rankings.py --days-back 5 --overwrite
```

Lectura programática:

```python
from src.data.rs_rankings import get_rs_percentile, get_top_rs_tickers

pct = get_rs_percentile('NVDA')           # último día disponible
top = get_top_rs_tickers(percentile=97)   # Top 3% hoy
```

---

## Cómo agregar un nuevo screener

1. Crear `src/screeners/mi_screener.py`:

```python
from .base import BaseScreener, ScreenerConfig, ScreenerResult
from .registry import ScreenerRegistry

@ScreenerRegistry.register
class MiScreener(BaseScreener):

    @property
    def name(self): return "mi_screener"

    @property
    def description(self): return "Descripción breve"

    def get_default_config(self):
        return ScreenerConfig(name=self.name, params={...})

    def scan(self, ticker, df, spy_df=None):
        passed, reason = self.apply_base_filters(df)
        if not passed:
            return ScreenerResult(False, ticker, self.name, reason=reason)
        # ... lógica ...
        return ScreenerResult(passed=True, ticker=ticker, screener_name=self.name,
                              score=75.0, metrics={...}, reason="OK")
```

2. Agregar el import en `src/screeners/__init__.py`:

```python
from . import mi_screener  # noqa: F401
```

3. Crear `config/screeners/mi_screener.json` con los parámetros.

4. Agregar tests en `tests/test_screeners.py`.

---

## Tests

```bash
cd /home/marcos/trade/momentum-v2
python -m pytest tests/test_screeners.py -v
```

---

## Workflow de optimización de combinaciones (futuro)

Ver `optimize_screener_combinations.py` (pendiente implementar):

```python
# Encuentra la mejor combinación screener + patrón por Sharpe
from itertools import combinations
from src.screeners import ScreenerRegistry, ScreenerPipeline

screeners = ['minervini_trend', 'ema21_pullback', 'qullamaggie_momentum']
patterns  = ['vcp', 'flat_base', 'pocket_pivot', 'breakout']

# Testear todas las combinatorias contra resultados históricos
```

---

*Archivos de specs originales en `docs/screener_specs/`.*
*Features futuros (fundamentales, cockpit UI) en `docs/screener_specs/future/`.*
