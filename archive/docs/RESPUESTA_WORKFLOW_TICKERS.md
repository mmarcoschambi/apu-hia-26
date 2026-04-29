# 🎯 RESPUESTA: Workflow para Agregar Tickers desde JSON

## Tu Situación
- **Tienes:** `scripts/universe/tickers_universo.json` con **22,662 tickers**
- **Quieres:** Agregarlos al sistema con validaciones, cache, y pre-cálculos
- **Incluir:** `precompute_patterns.py` en el workflow

---

## ✅ SOLUCIÓN: Script Completo Creado

He creado **`expand_universe_complete.sh`** que ejecuta todo el pipeline automáticamente.

### Comando único para hacerlo TODO:

```bash
./expand_universe_complete.sh --source json
```

---

## 📋 Las 5 Fases que Ejecuta

### **1. VALIDACIÓN** (`add_tickers_from_json.py`)
- Lee tu JSON: `scripts/universe/tickers_universo.json`
- Compara con la base de datos SQLite
- **Filtra duplicados** (tickers ya existentes)
- Genera: `new_tickers_to_add.txt` con solo los nuevos

### **2. DESCARGA** (`expand_universe.py`)
- Descarga OHLCV desde Yahoo Finance
- **Thread-safe** con 5 workers en paralelo
- **Retry automático** para rate limits (429, 503, etc.)
- Guarda en: `data/ticker_cache.db` (SQLite)

### **3. INDICADORES** (`precompute_all_indicators.py`)
- Pre-calcula: RSI, ATR, MACD, SMA20/50/200
- Guarda en: `data/precomputed_metrics.pkl`
- **Speedup 40-57x** en backtests

### **4. PATRONES** (`precompute_patterns.py`) ⭐ **INTEGRADO**
- Detecta: VCP, Cup & Handle, Flat Base, High Tight Flag
- **Usa `--merge`**: Preserva cache existente, solo agrega nuevos
- **Checkpoint automático** cada 10 tickers
- **Resume** si se interrumpe
- Guarda en:
  - `data/pattern_cache.pkl` (patrones por ticker/fecha)
  - `data/pattern_matrix.pkl` (matriz de confidence)

### **5. AUDITORÍA** (`audit_data_gaps.py`)
- Detecta gaps en datos
- Valida calidad
- Genera: `gaps_report.csv`

---

## 🚀 Ejecución Paso a Paso (Manual)

Si prefieres control manual en vez del script automatizado:

```bash
# Paso 1: Validar y filtrar duplicados
python3 add_tickers_from_json.py --source scripts/universe/tickers_universo.json

# Paso 2: Descargar datos (paralelo, con retry)
python3 expand_universe.py --ticker-file new_tickers_to_add.txt --workers 5

# Paso 3: Pre-calcular indicadores
python3 precompute_all_indicators.py --tickers-file new_tickers_to_add.txt

# Paso 4: Pre-calcular patrones (CON --merge para no perder cache existente)
python3 precompute_patterns.py --tickers-file new_tickers_to_add.txt --merge

# Paso 5: Auditar calidad
python3 audit_data_gaps.py
```

---

## 🔧 Opciones del Script Completo

```bash
./expand_universe_complete.sh \
    --source json                # Usar tickers_universo.json
    --tickers-file FILE          # O archivo custom
    --workers 5                  # Threads paralelos (2-5)
    --start-date 2020-01-01      # Fecha inicio
    --end-date 2026-03-09        # Fecha fin
    --skip-validation            # Saltar FASE 1
    --skip-download              # Saltar FASE 2
    --skip-indicators            # Saltar FASE 3
    --skip-patterns              # Saltar FASE 4
    --skip-audit                 # Saltar FASE 5
```

**Ejemplos:**

```bash
# Solo descargar, sin pre-cálculos
./expand_universe_complete.sh --source json --skip-indicators --skip-patterns --skip-audit

# Solo pre-calcular patrones (ya tenés los datos)
./expand_universe_complete.sh --tickers-file new.txt --skip-validation --skip-download --skip-indicators --skip-audit
```

---

## 📦 Archivos Generados por el Workflow

```
momentum-v2/
│
├── scripts/universe/
│   └── tickers_universo.json        ← TU JSON (input)
│
├── data/
│   ├── ticker_cache.db              ← SQLite: OHLCV histórico
│   ├── precomputed_metrics.pkl      ← Indicadores técnicos
│   ├── pattern_cache.pkl            ← Patrones por ticker/fecha ⭐
│   ├── pattern_matrix.pkl           ← Matriz de confidence ⭐
│   └── .pattern_progress.pkl        ← Checkpoint automático ⭐
│
├── new_tickers_to_add.txt           ← Output validación (tickers filtrados)
├── failed_tickers_expansion.txt     ← Errores de descarga
└── gaps_report.csv                  ← Reporte de auditoría
```

---

## ⏱️ Tiempos Estimados para tu JSON (22K tickers)

| Fase | Tiempo | Notas |
|------|--------|-------|
| Validación | 10 seg | Rápido (solo query SQL) |
| Descarga | 24-36 hrs | Depende de rate limits de Yahoo |
| Indicadores | 2-3 hrs | Cálculo en memoria |
| **Patrones** | **12-18 hrs** | **Con checkpoint cada 10 tickers** |
| Auditoría | 5 min | Análisis de gaps |
| **TOTAL** | **48-60 hrs** | **Recomendación: batches de 500-1000** |

---

## 💡 Características del Sistema de Patrones

### Validaciones incluidas:
✅ **Checkpoint automático** cada 10 tickers → No pierde progreso  
✅ **Resume capability** → Continúa desde donde quedó  
✅ **Merge mode** → No sobrescribe cache existente  
✅ **Step optimization** → Calcula cada 5 días (no todos los días)  
✅ **Error handling** → Continúa aunque falle algún ticker  

### Uso de `--merge` (CRÍTICO):
```python
# ❌ SIN --merge: Reemplaza TODO el cache
python3 precompute_patterns.py --tickers-file new.txt

# ✅ CON --merge: Solo agrega nuevos, preserva existentes
python3 precompute_patterns.py --tickers-file new.txt --merge
```

### Uso de `--resume`:
```bash
# Si se interrumpe el proceso
python3 precompute_patterns.py --tickers-file new.txt --merge --resume
# ↑ Lee desde data/.pattern_progress.pkl y continúa
```

---

## 🔍 Verificación Post-Agregado

```bash
# 1. Ver cuántos tickers hay en el sistema
python3 manage_universe.py --info

# 2. Ver stats del cache
python3 manage_universe.py --cache-info

# 3. Verificar que los patrones se calcularon
python3 -c "
import pickle
cache = pickle.load(open('data/pattern_cache.pkl', 'rb'))
print(f'✅ Tickers con patrones: {len(cache)}')

# Ver ejemplo de un ticker
if 'AAPL' in cache:
    aapl_patterns = cache['AAPL']
    print(f'✅ AAPL: {len(aapl_patterns)} fechas analizadas')
    
    # Ver patrones detectados
    detected = [v for v in aapl_patterns.values() if v['pattern_type'] != 'NONE']
    print(f'✅ AAPL: {len(detected)} fechas con patrones detectados')
"

# 4. Ver matriz de confidence
python3 -c "
import pickle
matrix = pickle.load(open('data/pattern_matrix.pkl', 'rb'))
conf = matrix['confidence']
print(f'✅ Matrix shape: {conf.shape}')
print(f'✅ Mean confidence: {conf[conf > 0].mean().mean():.3f}')
print(f'✅ Coverage: {(conf > 0).mean().mean() * 100:.1f}%')
"

# 5. Verificar un ticker específico
python3 check_ticker_data.py AAPL
```

---

## 🚨 Problemas Comunes y Soluciones

### "429 Too Many Requests" durante descarga
**Causa:** Rate limit de Yahoo Finance  
**Solución:**
```bash
# Reducir workers
./expand_universe_complete.sh --source json --workers 2

# O agregar más delay (editar expand_universe.py línea ~136)
time.sleep(1.0)  # Cambiar a 2.0 o 3.0
```

### "No data available" para muchos tickers
**Causa:** Tickers delisted, fusionados, o inválidos  
**Solución:** Normal. Revisar `failed_tickers_expansion.txt` y descartarlos.

### Proceso de patrones interrumpido
**Causa:** Sistema apagado, error de memoria, etc.  
**Solución:**
```bash
# Continuar desde checkpoint
python3 precompute_patterns.py --tickers-file new_tickers_to_add.txt --merge --resume
```

### Ya tengo algunos tickers en DB, quiero solo agregar nuevos
**Solución:** El sistema hace esto automáticamente en FASE 1 (validación).

---

## 📚 Archivos de Documentación

1. **`RESUMEN_WORKFLOW_TICKERS.md`** (este archivo) → Quick reference
2. **`WORKFLOW_AGREGAR_TICKERS.md`** → Guía completa detallada
3. **`WORKFLOW_UNIVERSE_EXPANSION.md`** → Documentación técnica original

---

## 🎓 Para tu Caso Específico (22K tickers)

### Opción A: Ejecutar en batches (RECOMENDADO)
```bash
# 1. Validar primero para ver cuántos son nuevos
python3 add_tickers_from_json.py --source scripts/universe/tickers_universo.json

# 2. Si son muchos (>5K), dividir en batches
split -l 500 new_tickers_to_add.txt batch_

# 3. Procesar cada batch
for batch in batch_*; do
    echo "Procesando $batch..."
    ./expand_universe_complete.sh --tickers-file "$batch" --skip-audit
    sleep 600  # 10 min entre batches para rate limits
done

# 4. Al final, auditar todo
python3 audit_data_gaps.py
```

### Opción B: Dejarlo correr 48-60 horas directo
```bash
# Ejecutar todo de una (overnight en servidor)
nohup ./expand_universe_complete.sh --source json > expansion.log 2>&1 &

# Ver progreso
tail -f expansion.log

# Checkpoint automático cada 10 tickers en patrones
# Si se interrumpe, usar --resume
```

---

## ✨ Resumen de Comandos Clave

```bash
# 🥇 UN COMANDO para hacerlo todo
./expand_universe_complete.sh --source json

# 🔍 Verificar después
python3 manage_universe.py --info
python3 -c "import pickle; print(f'Patrones: {len(pickle.load(open(\"data/pattern_cache.pkl\", \"rb\")))}')"

# 🏎️ Usar el sistema
streamlit run app.py
```

---

**Creado:** 2026-03-09  
**Scripts nuevos:**
- ✅ `expand_universe_complete.sh` (pipeline automatizado)
- ✅ `WORKFLOW_AGREGAR_TICKERS.md` (guía detallada)
- ✅ `RESUMEN_WORKFLOW_TICKERS.md` (quick reference)
- ✅ `test_workflow.sh` (test rápido)

**Integración con `precompute_patterns.py`:** ✅ COMPLETA
