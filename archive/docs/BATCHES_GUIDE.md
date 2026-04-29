# 🔄 Guía: Procesamiento en Batches

## 🎯 Problema

Cuando tienes muchos tickers (5K+), procesarlos todos de una vez:
- Tarda 24-60 horas
- Riesgo de errores/interrupciones
- Difícil de monitorear progreso
- Rate limits de Yahoo Finance

## ✅ Solución: Script de Batches

**Script:** `expand_universe_batches.sh`

Divide automáticamente tu lista en lotes y procesa uno por uno con:
- ✅ Delays automáticos entre batches (cooldown)
- ✅ Progress tracking por batch
- ✅ Continúa aunque falle un batch
- ✅ Auditoría final consolidada

---

## 🚀 Uso Rápido

### Desde tu JSON (22K tickers)

```bash
./expand_universe_batches.sh --source json --batch-size 500
```

### Desde un archivo custom

```bash
./expand_universe_batches.sh --tickers-file my_large_list.txt --batch-size 1000
```

---

## ⚙️ Parámetros

```bash
./expand_universe_batches.sh \
    --source json              # Usar tickers_universo.json
    --tickers-file FILE        # O archivo custom
    --batch-size 500           # Tickers por batch (default: 500)
    --delay 600                # Segundos entre batches (default: 600 = 10 min)
    --workers 5                # Workers paralelos por batch (default: 5)
    --start-date 2020-01-01    # Fecha inicio
    --end-date 2026-03-09      # Fecha fin
```

---

## 🔄 Flujo del Script

```
1. Validación (add_tickers_from_json.py)
   ↓
   new_tickers_to_add.txt (ej: 21,500 tickers)
   
2. División automática
   ↓
   batches_20260309_165900/
   ├── batch_000 (500 tickers)
   ├── batch_001 (500 tickers)
   ├── batch_002 (500 tickers)
   ├── ...
   └── batch_042 (500 tickers)
   
3. Procesar cada batch (loop)
   ┌─────────────────────────────────────┐
   │  Batch 1/43                         │
   │  ├─ Descarga (expand_universe.py)   │
   │  ├─ Indicadores (precompute_all...) │
   │  └─ Patrones (precompute_patterns)  │
   └─────────────────────────────────────┘
         ↓
   ⏸️ Delay 10 min (rate limit cooldown)
         ↓
   ┌─────────────────────────────────────┐
   │  Batch 2/43                         │
   │  ├─ Descarga                        │
   │  ├─ Indicadores                     │
   │  └─ Patrones                        │
   └─────────────────────────────────────┘
         ↓
   ... (repite para todos los batches)
   
4. Auditoría final (audit_data_gaps.py)
   ↓
   gaps_report.csv
   
5. ✅ COMPLETADO
```

---

## 📊 Ejemplo de Ejecución

```bash
$ ./expand_universe_batches.sh --source json --batch-size 500

════════════════════════════════════════════════════════════════
  🏎️  EXPAND UNIVERSE EN BATCHES
════════════════════════════════════════════════════════════════

  Batch size:  500 tickers
  Delay:       600 segundos entre batches
  Workers:     5
  Período:     2020-01-01 → 2026-03-09

════════════════════════════════════════════════════════════════
  📋 PASO 1: Validación y generación de lista limpia
════════════════════════════════════════════════════════════════

📂 Validando desde JSON: scripts/universe/tickers_universo.json
📂 Loading tickers from JSON... ✅ 22662 tickers found
🔍 Checking for duplicates... ✅ 1162 already in DB

✅ Total tickers a procesar: 21500
📦 Se crearán 43 batches de máximo 500 tickers

════════════════════════════════════════════════════════════════
  ✂️  PASO 2: Dividiendo en batches
════════════════════════════════════════════════════════════════

✅ Creados 43 batches en: batches_20260309_165900/

  Batch 1/43: batch_000 → 500 tickers
  Batch 2/43: batch_001 → 500 tickers
  ...
  Batch 43/43: batch_042 → 500 tickers

🤔 ¿Continuar con el procesamiento? (yes/no): yes

════════════════════════════════════════════════════════════════
  🚀 PASO 3: Procesando batches
════════════════════════════════════════════════════════════════

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  📦 BATCH 1/43 (batch_000)
  Tickers: 500 | Hora: 16:59:23
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  📥 FASE 2: Descarga de Datos Históricos
  ... (progress)
  ✅ Descarga completada
  
  📊 FASE 3: Pre-cálculo de Indicadores
  ... (progress)
  ✅ Indicadores pre-calculados
  
  🎯 FASE 4: Pre-cálculo de Patrones
  ... (progress)
  ✅ Patrones pre-calculados

  ✅ Batch 1 completado exitosamente
  
  ⏸️  Esperando 600 segundos antes del siguiente batch...
     (Rate limit cooldown + sistema estable)
     ⏳ 570 segundos restantes...

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  📦 BATCH 2/43 (batch_001)
  Tickers: 500 | Hora: 19:09:23
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

... (continúa)

════════════════════════════════════════════════════════════════
  🔍 PASO 4: Auditoría Final del Universo Completo
════════════════════════════════════════════════════════════════

Analyzing gaps... 100%|██████████| 21500/21500 [00:04:32<00:00]

✅ Auditoría completa. Ver: gaps_report.csv

════════════════════════════════════════════════════════════════
  ✅ PROCESAMIENTO EN BATCHES COMPLETADO
════════════════════════════════════════════════════════════════

  📊 Estadísticas:
     Total tickers:      21500
     Total batches:      43
     Batches exitosos:   42
     Batches fallidos:   1
     Tiempo total:       18.5 horas (1110 minutos)

  📦 Archivos generados:
     - data/ticker_cache.db
     - data/precomputed_metrics.pkl
     - data/pattern_cache.pkl ⭐
     - data/pattern_matrix.pkl ⭐
     - gaps_report.csv

  📂 Batches guardados en: batches_20260309_165900/

🗑️  ¿Eliminar directorio de batches? (yes/no): yes
✅ Directorio eliminado

🏁 PROCESO COMPLETADO
```

---

## 📊 Comparación: Script Normal vs Batches

| Característica | `expand_universe_complete.sh` | `expand_universe_batches.sh` |
|----------------|-------------------------------|------------------------------|
| **Tickers recomendados** | <1000 | >1000 |
| **Tiempo por 500 tickers** | 2-3 hrs | 2-3 hrs × N batches |
| **Interruptible** | ❌ Pierde todo | ✅ Por batch |
| **Monitoreo** | ⚠️ Difícil | ✅ Progress claro |
| **Rate limits** | ⚠️ Puede fallar | ✅ Delays automáticos |
| **Auditoría** | En cada ejecución | Solo al final |
| **Checkpoint patrones** | ✅ Cada 10 tickers | ✅ Cada 10 tickers |

---

## ⏱️ Estimación de Tiempos

### Para tu JSON (22K tickers) con batch-size 500:

| Concepto | Valor |
|----------|-------|
| **Total batches** | 43-44 batches |
| **Tiempo por batch** | ~25-30 min |
| **Delay entre batches** | 10 min |
| **Tiempo batch + delay** | ~35-40 min |
| **TOTAL** | ~25-30 horas |

**Fórmula:**
```
Total = (N_batches × tiempo_batch) + ((N_batches - 1) × delay)
      = (43 × 25 min) + (42 × 10 min)
      = 1075 min + 420 min
      = 1495 min ≈ 25 horas
```

### Optimización de batch-size:

| Batch Size | N° Batches | Tiempo Estimado | Recomendación |
|------------|------------|-----------------|---------------|
| 250 | 86 | ~35 hrs | Muy lento |
| **500** | **43** | **~25 hrs** | ⭐ **Óptimo** |
| 1000 | 22 | ~20 hrs | Riesgo rate limit |
| 2000 | 11 | ~18 hrs | Alto riesgo |

---

## 🔧 Opciones Avanzadas

### Procesar solo una fase en batches

```bash
# Solo descargar (sin indicadores ni patrones)
./expand_universe_batches.sh --source json --batch-size 500 --skip-indicators --skip-patterns

# Luego, pre-calcular indicadores y patrones para TODO de una vez
python3 precompute_all_indicators.py --full
python3 precompute_patterns.py --full --merge
```

### Ajustar delays según tu conexión

```bash
# Delay corto (5 min) si tienes buena conexión
./expand_universe_batches.sh --source json --delay 300

# Delay largo (20 min) si tienes rate limits frecuentes
./expand_universe_batches.sh --source json --delay 1200
```

### Workers según tu máquina

```bash
# Máquina lenta o conexión limitada
./expand_universe_batches.sh --source json --workers 2

# Máquina rápida y buena conexión
./expand_universe_batches.sh --source json --workers 5
```

---

## 🚨 Troubleshooting

### Un batch falló, ¿cómo continuar?

El script continúa automáticamente con el siguiente batch. 
Los batches fallidos quedan registrados en el summary final.

**Para reprocesar un batch fallido:**
```bash
# Identificar el batch que falló (ej: batch_015)
./expand_universe_complete.sh --tickers-file batches_20260309_165900/batch_015
```

### Rate limits durante ejecución

**Síntomas:**
- Muchos "429 Too Many Requests"
- Batch tarda más de 1 hora

**Solución:**
```bash
# Aumentar delay entre batches
./expand_universe_batches.sh --source json --delay 1200  # 20 min

# Reducir workers
./expand_universe_batches.sh --source json --workers 2

# O ambos
./expand_universe_batches.sh --source json --delay 1200 --workers 2
```

### Quedó a medio procesar, ¿cómo continuar?

El sistema usa `--merge` en patrones, así que puedes:

```bash
# Opción A: Continuar desde el batch que quedó
# (El script muestra qué batch está procesando)
# Esperar a que termine el batch actual y continuar

# Opción B: Procesar solo los batches que faltan manualmente
cd batches_20260309_165900/
for batch in batch_025 batch_026 batch_027; do  # Ajustar según necesites
    ../expand_universe_complete.sh --tickers-file "$batch" --skip-validation --skip-audit
    sleep 600
done
```

### ¿Cómo saber si un batch se procesó correctamente?

```bash
# Ver tickers en DB
python3 -c "
from src.data.ticker_cache import TickerCache
cache = TickerCache()
count = cache.conn.execute('SELECT COUNT(DISTINCT ticker) FROM ohlcv_cache').fetchone()[0]
print(f'Tickers en DB: {count}')
cache.close()
"

# Ver tickers en cache de patrones
python3 -c "
import pickle
cache = pickle.load(open('data/pattern_cache.pkl', 'rb'))
print(f'Tickers con patrones: {len(cache)}')
"
```

---

## 📊 Monitoreo Durante Ejecución

### Ver progreso en tiempo real

```bash
# Si ejecutaste en background
nohup ./expand_universe_batches.sh --source json > batch_processing.log 2>&1 &

# Monitorear en otra terminal
tail -f batch_processing.log

# Ver batches procesados
ls -1 batches_*/batch_* | wc -l  # Total batches creados
grep "Batch .* completado" batch_processing.log | wc -l  # Batches procesados
```

### Ver cuántos tickers se han agregado

```bash
# Durante la ejecución
watch -n 60 'python3 -c "from src.data.ticker_cache import TickerCache; c = TickerCache(); print(f\"Tickers: {c.conn.execute(\"SELECT COUNT(DISTINCT ticker) FROM ohlcv_cache\").fetchone()[0]}\"); c.close()"'
```

---

## 🎓 Mejores Prácticas

### ✅ DO:

1. **Batch size óptimo:** 500 tickers
   - Balance entre velocidad y robustez
   - Reduce riesgo de rate limits

2. **Delay adecuado:** 10 minutos (600 seg)
   - Cooldown para Yahoo API
   - Permite que el sistema se estabilice

3. **Ejecutar en horario de baja actividad:**
   - Overnight o fines de semana
   - Menos competencia por API

4. **Monitorear primeros batches:**
   - Ver que no haya rate limits
   - Ajustar workers/delay si es necesario

5. **Hacer backup antes:**
   ```bash
   cp data/ticker_cache.db data/ticker_cache.db.backup
   cp data/pattern_cache.pkl data/pattern_cache.pkl.backup
   ```

### ❌ DON'T:

1. No usar batch-size >1000 (rate limits garantizados)
2. No usar delay <300 segundos (5 min mínimo)
3. No usar workers >5 (Yahoo bloqueará tu IP)
4. No eliminar carpeta de batches hasta confirmar éxito
5. No interrumpir manualmente (deja que termine el batch actual)

---

## 🧮 Calculadora de Tiempos

### Fórmula:

```
Tiempo total = (N_batches × tiempo_por_batch) + (N_batches × delay)

Donde:
  N_batches = ceil(total_tickers / batch_size)
  tiempo_por_batch ≈ 25-30 min (depende de workers y conexión)
  delay = 10 min (recomendado)
```

### Ejemplos:

```bash
# 500 tickers, batch-size 500
N_batches = 1
Tiempo = (1 × 25 min) + (0 × 10 min) = 25 min

# 5000 tickers, batch-size 500
N_batches = 10
Tiempo = (10 × 25 min) + (9 × 10 min) = 340 min ≈ 5.7 hrs

# 22000 tickers, batch-size 500
N_batches = 44
Tiempo = (44 × 25 min) + (43 × 10 min) = 1530 min ≈ 25.5 hrs

# 22000 tickers, batch-size 1000
N_batches = 22
Tiempo = (22 × 50 min) + (21 × 10 min) = 1310 min ≈ 21.8 hrs
```

---

## 💡 Casos de Uso

### Caso 1: Primera vez con 22K tickers

```bash
# Ejecutar en batches overnight
nohup ./expand_universe_batches.sh --source json > expansion.log 2>&1 &

# Monitorear
tail -f expansion.log
```

### Caso 2: Ya tienes 10K, agregar 12K más

```bash
# El script automáticamente filtra los 10K existentes
./expand_universe_batches.sh --source json --batch-size 500

# Solo procesará los 12K nuevos en ~15 horas
```

### Caso 3: Reprocesar batches específicos que fallaron

```bash
# Ver qué batches fallaron en el log
grep "falló" expansion.log

# Reprocesar manualmente
./expand_universe_complete.sh --tickers-file batches_20260309_165900/batch_015 --skip-validation --skip-audit
```

### Caso 4: Agregar solo algunos sectores

```bash
# Filtrar JSON por sector (ej: tech)
python3 -c "
import json
tickers = json.load(open('scripts/universe/tickers_universo.json'))
# Filtrar manualmente o con lógica específica
tech_tickers = ['AAPL', 'MSFT', 'GOOGL', ...]  # Tu lista
with open('tech_tickers.txt', 'w') as f:
    f.write('\n'.join(tech_tickers))
"

# Procesar solo esos
./expand_universe_batches.sh --tickers-file tech_tickers.txt --batch-size 100
```

---

## 🔍 Verificación Post-Batches

```bash
# 1. Ver cuántos tickers se agregaron
python3 manage_universe.py --info

# 2. Ver cache de patrones
python3 -c "
import pickle
cache = pickle.load(open('data/pattern_cache.pkl', 'rb'))
print(f'✅ Tickers con patrones: {len(cache)}')

# Mostrar sample
for ticker in list(cache.keys())[:5]:
    n_patterns = sum(1 for v in cache[ticker].values() if v['pattern_type'] != 'NONE')
    print(f'   {ticker}: {len(cache[ticker])} fechas, {n_patterns} patrones detectados')
"

# 3. Ver matriz de confidence
python3 -c "
import pickle
matrix = pickle.load(open('data/pattern_matrix.pkl', 'rb'))
conf = matrix['confidence']
print(f'✅ Matrix shape: {conf.shape}')
print(f'✅ Tickers activos: {(conf.sum(axis=0) > 0).sum()}')
print(f'✅ Mean confidence: {conf[conf > 0].mean().mean():.3f}')
"

# 4. Verificar errores
if [ -f failed_tickers_expansion.txt ]; then
    echo "⚠️  Algunos tickers fallaron:"
    head -20 failed_tickers_expansion.txt
fi
```

---

## 🎯 Resumen de Comandos

```bash
# Batches automáticos (recomendado para 5K+ tickers)
./expand_universe_batches.sh --source json --batch-size 500

# Con parámetros custom
./expand_universe_batches.sh \
    --source json \
    --batch-size 500 \
    --delay 600 \
    --workers 5

# Test con archivo pequeño
./expand_universe_batches.sh --tickers-file test.txt --batch-size 10

# Background con log
nohup ./expand_universe_batches.sh --source json > batches.log 2>&1 &
```

---

**Creado:** 2026-03-09  
**Complementa:** `expand_universe_complete.sh` para listas grandes
