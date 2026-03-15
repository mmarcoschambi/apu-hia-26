# 🏎️ WORKFLOW: Agregar Nuevos Tickers al Sistema

## 📋 Resumen Ejecutivo

**Tienes un JSON con tickers en:** `scripts/universe/tickers_universo.json`

**Pipeline completo automatizado:**
```bash
./expand_universe_complete.sh --source json
```

Este script ejecuta las 5 fases del workflow en orden.

---

## 🎯 Fases del Workflow

### **FASE 1: Validación y Deduplicación** ✅
**Script:** `add_tickers_from_json.py`

**Qué hace:**
- Lee `scripts/universe/tickers_universo.json` (tu archivo con ~32,000 tickers)
- Consulta la base de datos SQLite (`data/ticker_cache.db`)
- Filtra **duplicados** (tickers ya existentes)
- Genera `new_tickers_to_add.txt` con solo los nuevos

**Output:**
```
📂 Loading tickers from JSON... ✅ 32000 tickers found
🔍 Checking for duplicates in database... ✅ 500 tickers already in DB
📊 VALIDATION RESULTS
   New to add: 31500
💾 New tickers list saved to: new_tickers_to_add.txt
```

---

### **FASE 2: Descarga de Datos Históricos** 📥
**Script:** `expand_universe.py`

**Qué hace:**
- Descarga OHLCV (Open, High, Low, Close, Volume) desde Yahoo Finance
- Calcula `dollar_volume = close * volume`
- Guarda en SQLite: `data/ticker_cache.db` tabla `ohlcv_cache`
- **Thread-safe**: Usa múltiples workers en paralelo
- **Retry con backoff**: Maneja rate limits de Yahoo (429, 401, 503)
- **Validaciones**: Mínimo 50 días de datos, sin NaN críticos

**Parámetros clave:**
- `--workers 5`: Descargas paralelas (máx 5 para evitar rate limits)
- `--start-date 2020-01-01`: Fecha inicio
- `--end-date 2026-03-09`: Fecha fin

**Output:**
```
RESULTS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Downloaded: 28450
Already cached: 2800
Failed: 250
Total tickers in cache: 31250
```

**Archivos generados:**
- `failed_tickers_expansion.txt` (si hay errores)

---

### **FASE 3: Pre-cálculo de Indicadores** 📊
**Script:** `precompute_all_indicators.py`

**Qué hace:**
- Calcula indicadores técnicos para cada ticker:
  - **Momentum**: RSI, ADX, MACD, ROC
  - **Volatilidad**: ATR, Bollinger Bands
  - **Liquidez**: Dollar Volume promedio 20 días
  - **Precio**: SMA20, SMA50, SMA200

- Guarda en: `data/precomputed_metrics.pkl`
- **Speedup**: 40-57x más rápido que calcular on-the-fly

**Output:**
```
🚀 PRECOMPUTE INDICATORS FOR ALL TICKERS
📊 Found 31250 pickle files
✅ Success: 30950
⏭️  Skipped: 250 (already done)
❌ Failed: 50
Expected speedup: 40-57x for indicator calculations
```

---

### **FASE 4: Pre-cálculo de Patrones** 🎯
**Script:** `precompute_patterns.py`

**Qué hace:**
- Detecta patrones técnicos chartistas:
  - **VCP** (Volatility Contraction Pattern)
  - **Cup & Handle**
  - **Flat Base**
  - **High Tight Flag**

- Para cada ticker, escanea fechas con `step=5` días (optimización)
- Genera confidence scores (0.0 - 1.0)
- **Modo merge**: No sobrescribe cache existente, solo agrega nuevos

**Archivos generados:**
- `data/pattern_cache.pkl`: Dict `{ticker: {date: pattern_info}}`
- `data/pattern_matrix.pkl`: DataFrame con confidence scores
- `data/.pattern_progress.pkl`: Checkpoint cada 10 tickers (auto-resume)

**Output:**
```
═══════════════════════════════════════════════════════════
  PRECOMPUTE PATTERN CACHE
  Tickers : 31250 | Periodo: 2020-01-01 -> 2026-03-09
  Step    : cada 5 dias | Merge: True
═══════════════════════════════════════════════════════════

[MERGE] Cache existente: 500 tickers
[INFO] Por procesar: 30750 tickers

[OK] Cache guardado: data/pattern_cache.pkl (31250 tickers total)
[OK] Matrix: (1500, 31250) | Conf media: 0.42 | Cobertura: 15.3%
```

**Parámetros importantes:**
- `--merge`: Preserva cache existente (IMPORTANTE para no perder data)
- `--resume`: Continúa desde última interrupción
- `--step 5`: Calcula cada 5 días (balance velocidad/precisión)
- `--no-matrix`: Skip matriz de confidence (más rápido)

---

### **FASE 5: Auditoría de Calidad** 🔍
**Script:** `audit_data_gaps.py`

**Qué hace:**
- Detecta gaps en series temporales
- Identifica tickers con datos insuficientes (<100 días)
- Valida consistencia de precios (sin outliers extremos)

**Output:**
- `gaps_report.csv`: Reporte de gaps por ticker/año

---

## 🚀 Uso Rápido

### Opción 1: Pipeline completo automatizado (RECOMENDADO)

```bash
# Desde tu JSON con 32K tickers
./expand_universe_complete.sh --source json

# O desde un archivo custom
./expand_universe_complete.sh --tickers-file my_new_tickers.txt
```

### Opción 2: Ejecución manual paso a paso

```bash
# 1. Validar y deduplicar
python3 add_tickers_from_json.py --source scripts/universe/tickers_universo.json

# 2. Descargar datos
python3 expand_universe.py --ticker-file new_tickers_to_add.txt --workers 5

# 3. Pre-calcular indicadores
python3 precompute_all_indicators.py --tickers-file new_tickers_to_add.txt

# 4. Pre-calcular patrones (CON --merge para preservar cache existente)
python3 precompute_patterns.py --tickers-file new_tickers_to_add.txt --merge

# 5. Auditar calidad
python3 audit_data_gaps.py
```

### Opción 3: Solo actualizar patrones para universo completo

```bash
# Recalcular patrones para todos los tickers en cache
python3 precompute_patterns.py --full --merge
```

---

## 📦 Estructura de Archivos

```
momentum-v2/
├── scripts/universe/
│   └── tickers_universo.json        # ← TU JSON (input)
│
├── data/
│   ├── ticker_cache.db              # SQLite: OHLCV histórico
│   ├── precomputed_metrics.pkl      # Indicadores técnicos
│   ├── pattern_cache.pkl            # Patrones por ticker/fecha
│   ├── pattern_matrix.pkl           # Matriz de confidence scores
│   └── .pattern_progress.pkl        # Checkpoint automático
│
├── new_tickers_to_add.txt           # Output FASE 1 (tickers filtrados)
├── failed_tickers_expansion.txt     # Output FASE 2 (errores)
└── gaps_report.csv                  # Output FASE 5 (auditoría)
```

---

## ⚙️ Opciones del Script Completo

```bash
./expand_universe_complete.sh \
    --source json                    # Usar tickers_universo.json
    --tickers-file custom.txt        # O usar archivo custom
    --start-date 2020-01-01          # Fecha inicio
    --end-date 2026-03-09            # Fecha fin
    --workers 5                      # Threads paralelos (2-5)
    --skip-validation                # Saltar validación
    --skip-download                  # Saltar descarga
    --skip-indicators                # Saltar indicadores
    --skip-patterns                  # Saltar patrones
    --skip-audit                     # Saltar auditoría
```

**Ejemplos:**

```bash
# Solo descargar datos (sin pre-cálculos)
./expand_universe_complete.sh --source json --skip-indicators --skip-patterns --skip-audit

# Solo pre-calcular patrones (ya tienes los datos)
./expand_universe_complete.sh --tickers-file new.txt --skip-validation --skip-download --skip-indicators --skip-audit

# Pipeline rápido (sin auditoría)
./expand_universe_complete.sh --source json --skip-audit
```

---

## 🔧 Scripts Individuales

| Script | Propósito | Input | Output |
|--------|-----------|-------|--------|
| `add_tickers_from_json.py` | Validar y deduplicar | JSON | `new_tickers_to_add.txt` |
| `expand_universe.py` | Descargar OHLCV (paralelo) | Archivo tickers | SQLite cache |
| `add_tickers_quick.py` | Descargar OHLCV (secuencial) | Args CLI | SQLite cache |
| `precompute_all_indicators.py` | Indicadores técnicos | Archivo tickers | `precomputed_metrics.pkl` |
| `precompute_patterns.py` | Patrones técnicos | Archivo tickers | `pattern_cache.pkl` + `pattern_matrix.pkl` |
| `audit_data_gaps.py` | Validar calidad | Universo completo | `gaps_report.csv` |
| `manage_universe.py` | Info del universo | - | Stats |

---

## 🎓 Mejores Prácticas

### ✅ DO:
1. **Usa `--merge`** en `precompute_patterns.py` para no perder data existente
2. **Valida primero** con `add_tickers_from_json.py` para evitar duplicados
3. **Workers conservadores** (3-5) para evitar rate limits de Yahoo
4. **Batches pequeños** (<500 tickers) si tienes conexión lenta
5. **Verifica calidad** con `audit_data_gaps.py` después de agregar muchos tickers

### ❌ DON'T:
1. No correr `precompute_patterns.py` sin `--merge` si ya tienes cache
2. No usar más de 5 workers (Yahoo bloqueará tu IP)
3. No agregar >1000 tickers de una vez (tarda horas)
4. No saltar validación si no estás seguro de que no hay duplicados

---

## 🔍 Verificación Post-Agregado

```bash
# Ver stats del universo
python3 manage_universe.py --info

# Ver stats del cache
python3 manage_universe.py --cache-info

# Verificar un ticker específico
python3 check_ticker_data.py AAPL

# Ver patrones detectados
python3 -c "
import pickle
with open('data/pattern_cache.pkl', 'rb') as f:
    cache = pickle.load(f)
    print(f'Tickers con patrones: {len(cache)}')
"

# Ver matriz de confidence
python3 -c "
import pickle
with open('data/pattern_matrix.pkl', 'rb') as f:
    matrix = pickle.load(f)
    conf = matrix['confidence']
    print(f'Shape: {conf.shape}')
    print(f'Mean confidence: {conf[conf > 0].mean().mean():.3f}')
"
```

---

## 🚨 Troubleshooting

### Error: "429 Too Many Requests"
**Solución:**
- Reducir `--workers` a 2-3
- Agregar sleep más largo en `expand_universe.py`
- Esperar 1 hora y reintentar

### Error: "No data available" para algunos tickers
**Causa:** Ticker delisted, fusionado, o inválido
**Solución:** Normal. Revisar `failed_tickers_expansion.txt` y descartar esos tickers.

### Pre-compute interrumpido
**Solución:**
```bash
# Usar --resume (lee desde checkpoint automático)
python3 precompute_patterns.py --tickers-file new_tickers.txt --merge --resume
```

### "insufficient_data" para muchos tickers
**Causa:** Tickers con menos de 50 días de historia (IPOs recientes)
**Solución:** Normal. Sistema los saltará automáticamente.

### Cache de patrones corrupto
**Solución:**
```bash
# Backup del cache actual
cp data/pattern_cache.pkl data/pattern_cache.pkl.backup

# Regenerar desde cero
python3 precompute_patterns.py --full
```

---

## 📊 Performance Tips

| Escenario | Tiempo estimado | Comando |
|-----------|-----------------|---------|
| 50 tickers nuevos | 5-10 min | `./expand_universe_complete.sh --tickers-file short.txt` |
| 500 tickers nuevos | 45-60 min | `./expand_universe_complete.sh --source json` |
| 5000 tickers nuevos | 6-8 horas | `./expand_universe_complete.sh --source json` |
| 30000+ tickers | 24-48 horas | Ejecutar en batches de 500 |

**Optimización para listas grandes:**
```bash
# Dividir en batches de 500 tickers cada uno
split -l 500 new_tickers_to_add.txt batch_

# Procesar cada batch
for batch in batch_*; do
    ./expand_universe_complete.sh --tickers-file "$batch"
    sleep 600  # 10 min entre batches
done
```

---

## 🔄 Flujo Visual

```
┌─────────────────────────────────────┐
│  scripts/universe/                  │
│  tickers_universo.json (32K)       │
└────────────┬────────────────────────┘
             │
             ▼
    ┌────────────────────────┐
    │  FASE 1: Validación    │  ← add_tickers_from_json.py
    │  Filtrar duplicados    │
    └────────┬───────────────┘
             │ new_tickers_to_add.txt (31.5K)
             ▼
    ┌────────────────────────┐
    │  FASE 2: Descarga      │  ← expand_universe.py
    │  Yahoo Finance OHLCV   │     (5 workers, retry logic)
    └────────┬───────────────┘
             │ data/ticker_cache.db (SQLite)
             ▼
    ┌────────────────────────┐
    │  FASE 3: Indicadores   │  ← precompute_all_indicators.py
    │  RSI, ATR, MACD, etc.  │
    └────────┬───────────────┘
             │ data/precomputed_metrics.pkl
             ▼
    ┌────────────────────────┐
    │  FASE 4: Patrones      │  ← precompute_patterns.py --merge
    │  VCP, C&H, Flat Base   │     (checkpoint cada 10 tickers)
    └────────┬───────────────┘
             │ data/pattern_cache.pkl
             │ data/pattern_matrix.pkl
             ▼
    ┌────────────────────────┐
    │  FASE 5: Auditoría     │  ← audit_data_gaps.py
    │  Calidad de datos      │
    └────────┬───────────────┘
             │ gaps_report.csv
             ▼
    ┌────────────────────────┐
    │  ✅ UNIVERSO LISTO     │
    │  Para backtest/optim   │
    └────────────────────────┘
```

---

## 🧪 Testing del Workflow

```bash
# Test rápido con 5 tickers
cat > test_tickers.txt << EOF
AAPL
MSFT
GOOGL
NVDA
TSLA
EOF

# Ejecutar pipeline completo
./expand_universe_complete.sh --tickers-file test_tickers.txt

# Verificar resultados
python3 check_ticker_data.py AAPL
python3 -c "
import pickle
with open('data/pattern_cache.pkl', 'rb') as f:
    cache = pickle.load(f)
    print('Tickers en cache:', len(cache))
    if 'AAPL' in cache:
        print('AAPL fechas:', len(cache['AAPL']))
"
```

---

## 💡 Casos de Uso Comunes

### Caso 1: Primer poblado completo desde JSON
```bash
./expand_universe_complete.sh --source json
```

### Caso 2: Agregar 20 tickers específicos
```bash
# Crear archivo
echo -e "ASMB\nCYTK\nBBNX\nISSC\nGOLD" > new.txt

# Pipeline completo
./expand_universe_complete.sh --tickers-file new.txt
```

### Caso 3: Solo actualizar patrones (ya tienes los datos)
```bash
./expand_universe_complete.sh \
    --tickers-file new.txt \
    --skip-validation \
    --skip-download \
    --skip-indicators \
    --skip-audit
```

### Caso 4: Reconstruir cache de patrones desde cero
```bash
# Backup del cache actual
mv data/pattern_cache.pkl data/pattern_cache.pkl.old

# Regenerar todo
python3 precompute_patterns.py --full
```

---

## 📚 Referencias Adicionales

- **`WORKFLOW_UNIVERSE_EXPANSION.md`**: Guía original detallada
- **`TICKER_MANAGEMENT.md`**: Gestión avanzada de universo
- **`PRECOMPUTE_GUIDE.md`**: Guía de pre-cálculo de métricas
- **`COMO_POBLAR_DATOS.md`**: Documentación legacy

---

## 🎯 Resumen de Comandos Clave

```bash
# 1️⃣ UN COMANDO para hacerlo todo (desde tu JSON)
./expand_universe_complete.sh --source json

# 2️⃣ Ver info del sistema después
python3 manage_universe.py --info
python3 manage_universe.py --cache-info

# 3️⃣ Verificar que los patrones se calcularon
python3 -c "import pickle; cache = pickle.load(open('data/pattern_cache.pkl', 'rb')); print(f'✅ {len(cache)} tickers con patrones')"

# 4️⃣ Abrir dashboard para usar los nuevos tickers
streamlit run app.py
```

---

## ✨ Nuevo: Integración Completa de Patrones

El workflow ahora incluye **automáticamente** el pre-cálculo de patrones con:

- ✅ **Validación de duplicados** antes de descargar
- ✅ **Descarga con retry** y manejo de rate limits
- ✅ **Caché incremental** (solo agrega nuevos, preserva existentes)
- ✅ **Checkpoint automático** cada 10 tickers
- ✅ **Resume** desde interrupción
- ✅ **Matriz de confidence** para backtesting rápido

**Antes:** 4 comandos manuales → **Ahora:** 1 comando automatizado 🚀

---

**Última actualización:** 2026-03-09  
**Compatibilidad:** momentum-v2 (Triad Protocol)
