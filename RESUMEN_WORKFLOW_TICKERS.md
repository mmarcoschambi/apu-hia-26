# 🚀 RESUMEN: Workflow para Agregar Tickers Nuevos

## Tu JSON: `scripts/universe/tickers_universo.json`
**Contiene: ~22,662 tickers**

---

## ⚡ UN COMANDO para hacerlo TODO

```bash
./expand_universe_complete.sh --source json
```

Esto ejecuta automáticamente:
1. ✅ **Validación** → Filtra duplicados contra tu DB
2. 📥 **Descarga** → OHLCV desde Yahoo (con retry, thread-safe)
3. 📊 **Indicadores** → RSI, ATR, MACD, SMAs pre-calculados
4. 🎯 **Patrones** → VCP, Cup&Handle detectados (con --merge)
5. 🔍 **Auditoría** → Reporte de gaps y calidad

---

## 📖 Scripts Clave del Workflow

### 1. `add_tickers_from_json.py` - Validación
```bash
python3 add_tickers_from_json.py --source scripts/universe/tickers_universo.json
```
- Lee tu JSON (22K tickers)
- Compara con DB SQLite
- Filtra duplicados
- Output: `new_tickers_to_add.txt` (solo nuevos)

### 2. `expand_universe.py` - Descarga
```bash
python3 expand_universe.py --ticker-file new_tickers_to_add.txt --workers 5
```
- Descarga OHLCV paralelo (5 workers)
- Retry automático en rate limits
- Guarda en: `data/ticker_cache.db`

### 3. `precompute_all_indicators.py` - Indicadores
```bash
python3 precompute_all_indicators.py --tickers-file new_tickers_to_add.txt
```
- Pre-calcula RSI, ATR, MACD, SMAs
- Output: `data/precomputed_metrics.pkl`
- Speedup: 40-57x vs cálculo on-the-fly

### 4. `precompute_patterns.py` - Patrones ⭐ NUEVO
```bash
python3 precompute_patterns.py --tickers-file new_tickers_to_add.txt --merge
```
- Detecta VCP, Cup&Handle, Flat Base, HTF
- **--merge**: Preserva cache existente (CRÍTICO)
- Output: `data/pattern_cache.pkl` + `pattern_matrix.pkl`
- Checkpoint automático cada 10 tickers

### 5. `audit_data_gaps.py` - Validación
```bash
python3 audit_data_gaps.py
```
- Detecta gaps en datos
- Output: `gaps_report.csv`

---

## 🎯 Flujo Recomendado

```bash
# Opción A: TODO automatizado (recomendado)
./expand_universe_complete.sh --source json

# Opción B: Paso a paso (más control)
python3 add_tickers_from_json.py --source scripts/universe/tickers_universo.json
python3 expand_universe.py --ticker-file new_tickers_to_add.txt --workers 5
python3 precompute_all_indicators.py --tickers-file new_tickers_to_add.txt
python3 precompute_patterns.py --tickers-file new_tickers_to_add.txt --merge
python3 audit_data_gaps.py
```

---

## 🔥 Integración de `precompute_patterns.py`

**Opciones importantes:**

| Flag | Propósito |
|------|-----------|
| `--merge` | ⭐ Preserva cache existente, solo agrega nuevos |
| `--resume` | Continúa desde checkpoint si se interrumpió |
| `--step 5` | Calcula cada 5 días (balance velocidad/precisión) |
| `--full` | Procesa TODO el universo |
| `--tickers-file` | Archivo con lista de tickers |
| `--no-matrix` | Skip matriz de confidence (más rápido) |

**Ejemplo para tu caso:**
```bash
# Primera vez con tu JSON (22K tickers)
python3 precompute_patterns.py --tickers-file new_tickers_to_add.txt --merge --step 5

# Si se interrumpe, resume automáticamente
python3 precompute_patterns.py --tickers-file new_tickers_to_add.txt --merge --resume

# Recalcular TODO el universo
python3 precompute_patterns.py --full --merge
```

---

## 📦 Outputs del Workflow

```
data/
├── ticker_cache.db                # SQLite con OHLCV (22K+ tickers)
├── precomputed_metrics.pkl        # Indicadores pre-calculados
├── pattern_cache.pkl              # {ticker: {date: pattern_info}}
├── pattern_matrix.pkl             # DataFrame (dates × tickers)
└── .pattern_progress.pkl          # Checkpoint automático

new_tickers_to_add.txt             # Lista filtrada (solo nuevos)
failed_tickers_expansion.txt       # Tickers con errores
gaps_report.csv                    # Reporte de calidad
```

---

## ⏱️ Tiempos Estimados

| Fase | ~22K tickers | ~500 tickers | ~50 tickers |
|------|--------------|--------------|-------------|
| Validación | 10 seg | 5 seg | 2 seg |
| Descarga | 24-36 hrs | 45 min | 5 min |
| Indicadores | 2-3 hrs | 10 min | 1 min |
| Patrones | 12-18 hrs | 1-2 hrs | 10 min |
| **TOTAL** | **48-60 hrs** | **2-3 hrs** | **15-20 min** |

**Tip:** Para 22K tickers, ejecutar en batches de 500-1000 o dejarlo correr overnight.

---

## 🛡️ Validaciones Incluidas

✅ **Deduplicación** - No descarga tickers ya en DB  
✅ **Retry logic** - Maneja rate limits (429) con backoff exponencial  
✅ **Thread-safe** - Cada worker usa su propia conexión SQLite  
✅ **Checkpoint** - Patterns guarda progreso cada 10 tickers  
✅ **Data quality** - Rechaza tickers con <50 días de data  
✅ **Cache merge** - Preserva patrones existentes al agregar nuevos  

---

## 🚨 Si Algo Falla

```bash
# Ver logs de descarga
cat failed_tickers_expansion.txt

# Ver progreso de patrones (checkpoint)
python3 -c "
import pickle
from pathlib import Path
if Path('data/.pattern_progress.pkl').exists():
    prog = pickle.load(open('data/.pattern_progress.pkl', 'rb'))
    print(f'Checkpoint: {len(prog)} tickers procesados')
"

# Resume desde checkpoint
python3 precompute_patterns.py --tickers-file new_tickers_to_add.txt --merge --resume

# Verificar integridad del cache
python3 cache_inspector.py
```

---

## 🎓 Documentación Completa

Ver: **`WORKFLOW_AGREGAR_TICKERS.md`** para guía detallada con:
- Troubleshooting avanzado
- Optimizaciones de performance
- Verificación post-agregado
- Casos de uso específicos
