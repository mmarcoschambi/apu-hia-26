# WORKFLOW: Expansión del Universo de Tickers

## 📋 Overview

Proceso completo para agregar nuevos tickers al sistema:
1. **Validación y deduplicación** de tickers
2. **Descarga de datos históricos** (OHLCV + dollar_volume)
3. **Pre-cálculo de indicadores** (momentum, volatilidad, etc.)
4. **Pre-cálculo de patrones** (VCP, Cup&Handle, etc.)
5. **Verificación de calidad** de datos

---

## 🚀 Quick Start

### Opción 1: JSON desde `scripts/universe/tickers_universo.json`

```bash
# Paso completo automatizado (recomendado)
./expand_universe_complete.sh --source json

# O manualmente:
python3 add_tickers_from_json.py --source scripts/universe/tickers_universo.json
python3 precompute_all_indicators.py --tickers-file new_tickers.txt
python3 precompute_patterns.py --tickers-file new_tickers.txt --merge
```

### Opción 2: Lista manual de tickers

```bash
# Agregar tickers específicos
python3 manage_universe.py --add "ASMB, CYTK, BBNX, ISSC, GOLD"

# Descargar datos para esos tickers
python3 add_tickers_quick.py ASMB CYTK BBNX ISSC GOLD

# Pre-calcular todo
python3 precompute_all_indicators.py --tickers ASMB CYTK BBNX ISSC GOLD
python3 precompute_patterns.py --tickers ASMB CYTK BBNX ISSC GOLD --merge
```

### Opción 3: Pipeline completo desde archivo

```bash
# Preparar archivo (un ticker por línea)
echo "AAPL" > new_tickers.txt
echo "TSLA" >> new_tickers.txt

# Ejecutar pipeline completo
./expand_universe_complete.sh --tickers-file new_tickers.txt
```

---

## 📖 Workflow Detallado

### FASE 1: Validación y Deduplicación
**Script:** `add_tickers_from_json.py` (nuevo)

- Lee `scripts/universe/tickers_universo.json`
- Compara con tickers existentes en DB (`ohlcv_cache`)
- Filtra duplicados
- Genera `new_tickers_to_add.txt` con la lista limpia

### FASE 2: Descarga de Datos Históricos
**Scripts:** `expand_universe.py` o `add_tickers_quick.py`

- Descarga OHLCV desde Yahoo Finance
- Calcula `dollar_volume = close * volume`
- Guarda en SQLite (`data/ticker_cache.db` tabla `ohlcv_cache`)
- Maneja rate limits (sleep entre requests)
- Retry con backoff exponencial para errores transitorios
- Thread-safe con múltiples workers

**Parámetros:**
- `--start-date`: Default `2020-01-01`
- `--end-date`: Default `2025-12-31`
- `--workers`: Threads paralelos (default: 3, máx: 5)
- `--skip-existing`: Saltar tickers ya en DB

### FASE 3: Pre-cálculo de Indicadores
**Script:** `precompute_all_indicators.py`

Calcula y guarda en `data/precomputed_metrics.pkl`:
- **Momentum**: RSI, ADX, MACD, ROC
- **Volatilidad**: ATR, Bollinger Bands
- **Liquidez**: Dollar Volume promedio
- **Precio**: SMA20, SMA50, SMA200

**Opciones:**
- `--tickers AAPL MSFT`: Lista específica
- `--tickers-file`: Desde archivo
- `--full`: Procesar todo el universo

### FASE 4: Pre-cálculo de Patrones
**Script:** `precompute_patterns.py`

Detecta patrones técnicos:
- **VCP** (Volatility Contraction Pattern)
- **Cup & Handle**
- **Flat Base**
- **High Tight Flag**

Genera:
- `data/pattern_cache.pkl`: Diccionario `{ticker: {date: pattern_info}}`
- `data/pattern_matrix.pkl`: DataFrame con confidence scores

**Opciones clave:**
- `--merge`: Mergear con cache existente (no sobreescribir)
- `--resume`: Continuar desde última interrupción
- `--step N`: Calcular cada N días (default: 5)
- `--tickers-file`: Archivo con lista de tickers
- `--no-matrix`: No construir matriz de confidence

### FASE 5: Verificación de Calidad
**Script:** `audit_data_gaps.py`

- Detecta gaps en series temporales
- Identifica tickers con datos insuficientes (<100 días)
- Genera reporte CSV: `gaps_report.csv`

---

## 🛠️ Scripts Involucrados

| Script | Función | Input | Output |
|--------|---------|-------|--------|
| `manage_universe.py` | Gestión de universo | Tickers custom | `data/universe/*.json` |
| `expand_universe.py` | Descarga paralela | Archivo tickers | SQLite cache |
| `add_tickers_quick.py` | Descarga secuencial | Args CLI | SQLite cache |
| `precompute_all_indicators.py` | Indicadores técnicos | Tickers | `precomputed_metrics.pkl` |
| `precompute_patterns.py` | Patrones técnicos | Tickers | `pattern_cache.pkl` + `pattern_matrix.pkl` |
| `audit_data_gaps.py` | Validación calidad | Universo | `gaps_report.csv` |

---

## 🔄 Workflow Típico (Paso a Paso)

### Si tienes `scripts/universe/tickers_universo.json`:

```bash
# 1. Validar tickers nuevos (filtra duplicados)
python3 add_tickers_from_json.py --source scripts/universe/tickers_universo.json

# 2. Descargar datos (paralelo, con retry)
python3 expand_universe.py --ticker-file new_tickers_to_add.txt --workers 5

# 3. Pre-calcular indicadores
python3 precompute_all_indicators.py --tickers-file new_tickers_to_add.txt

# 4. Pre-calcular patrones (con merge para no perder data existente)
python3 precompute_patterns.py --tickers-file new_tickers_to_add.txt --merge

# 5. Verificar calidad
python3 audit_data_gaps.py

# 6. Reconstruir universo completo (opcional)
python3 manage_universe.py --refresh
```

### Si tienes una lista manual:

```bash
# 1. Descargar datos
python3 add_tickers_quick.py AAPL MSFT GOOGL --skip-existing

# 2. Pre-calcular todo
python3 precompute_all_indicators.py --tickers AAPL MSFT GOOGL
python3 precompute_patterns.py --tickers AAPL MSFT GOOGL --merge

# 3. Verificar
python3 check_ticker_data.py AAPL
```

---

## 📦 Archivos Generados

```
data/
├── ticker_cache.db              # SQLite: OHLCV histórico
├── precomputed_metrics.pkl      # Indicadores pre-calculados
├── pattern_cache.pkl            # Patrones por ticker/fecha
├── pattern_matrix.pkl           # Matriz de confidence scores
├── cache/                       # Pickles individuales (legacy)
│   ├── AAPL.pkl
│   └── MSFT.pkl
└── universe/
    ├── universe.json            # Universo completo (S&P500 + NASDAQ100 + custom)
    ├── custom_tickers.json      # Tickers agregados manualmente
    └── metadata.json            # Metadata de última actualización
```

---

## 🎯 Integración con `precompute_patterns.py`

### Cambios clave:

1. **Acepta múltiples fuentes de input:**
   - `--tickers AAPL MSFT`: Lista explícita
   - `--tickers-file`: Archivo con un ticker por línea
   - `--full`: Todo el universo (`top_500_momentum_tickers.txt`)

2. **Modo merge:**
   - `--merge`: Preserva cache existente, solo agrega nuevos
   - Sin `--merge`: Reemplaza todo el cache

3. **Output:**
   - `data/pattern_cache.pkl`: Datos crudos
   - `data/pattern_matrix.pkl`: DataFrame para backtesting rápido

### Ejemplo de uso después de agregar tickers:

```bash
# Después de agregar 50 tickers nuevos:
python3 expand_universe.py --ticker-file new_tickers.txt --workers 5

# Pre-calcular patrones SOLO para los nuevos (eficiente)
python3 precompute_patterns.py --tickers-file new_tickers.txt --merge

# O recalcular TODO el universo (más lento pero garantiza consistencia)
python3 precompute_patterns.py --full --merge
```

---

## ⚡ Script Automatizado

Usa `expand_universe_complete.sh` (nuevo) que ejecuta todo el pipeline:

```bash
# Desde JSON
./expand_universe_complete.sh --source json

# Desde archivo
./expand_universe_complete.sh --tickers-file my_tickers.txt

# Con parámetros personalizados
./expand_universe_complete.sh \
    --tickers-file new_tickers.txt \
    --start-date 2022-01-01 \
    --workers 5 \
    --skip-precompute  # Solo descargar datos
```

---

## 🔍 Verificación Post-Agregado

```bash
# Ver info del universo
python3 manage_universe.py --info

# Ver info del cache
python3 manage_universe.py --cache-info

# Verificar datos de un ticker específico
python3 check_ticker_data.py AAPL

# Buscar gaps en los datos
python3 audit_data_gaps.py --year 2024

# Ver patrones detectados
python3 -c "
import pickle
with open('data/pattern_cache.pkl', 'rb') as f:
    cache = pickle.load(f)
    print(f'Tickers con patrones: {len(cache)}')
    print(f'Ejemplo AAPL: {len(cache.get(\"AAPL\", {}))} fechas')
"
```

---

## 🚨 Troubleshooting

### Error: "429 Rate Limit"
- Reducir `--workers` (usar 2-3)
- Aumentar sleep entre requests en `expand_universe.py`

### Error: "No data available"
- Ticker delisted o inválido
- Revisar `failed_tickers_expansion.txt`

### Error: "insufficient_data"
- Ticker con menos de 50 días de historia
- Normal para IPOs recientes

### Pre-compute falla para algunos tickers
- Revisar `data/.pattern_progress.pkl` (checkpoint automático)
- Usar `--resume` para continuar desde donde quedó

---

## 📊 Performance Tips

1. **Descarga:** Usa `expand_universe.py` con workers=5 para listas grandes (>100 tickers)
2. **Pre-compute:** Usa `--step 5` (calcula cada 5 días) para balance speed/precisión
3. **Merge mode:** Usa `--merge` en `precompute_patterns.py` cuando agregues pocos tickers
4. **Checkpoint:** `precompute_patterns.py` guarda progreso cada 10 tickers
5. **Resume:** Si se interrumpe, usa `--resume` para no empezar de cero

---

## 🎓 Best Practices

1. **Agregar en batches:** No más de 200 tickers a la vez (rate limits)
2. **Validar primero:** Usa `manage_universe.py --list <TICKER>` para verificar si ya existe
3. **Skip existing:** Usa `--skip-existing` en descargas para eficiencia
4. **Merge patterns:** Usa `--merge` en patterns para preservar cache existente
5. **Audit después:** Ejecuta `audit_data_gaps.py` después de agregar muchos tickers

---

## 🔗 Referencias

- `TICKER_MANAGEMENT.md`: Gestión avanzada de tickers
- `PRECOMPUTE_GUIDE.md`: Guía detallada de pre-cálculo
- `COMO_POBLAR_DATOS.md`: Documentación legacy de población
