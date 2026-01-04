# 🚀 Guía: Re-ejecutar Backtest con Fixes Aplicados

## ✅ Estado Actual

**Fixes aplicados en código:**
- ✅ RVOL filter en screener
- ✅ P&L total con salidas parciales
- ✅ FASE_3 solo si hubo FASE_1
- ✅ FASE_2 puede ejecutarse mismo día que FASE_1
- ✅ Trend context coherente (SMA20 AND SMA50)

**Archivos desactualizados:**
- ❌ `backtest_results.csv` - Fecha: 06:30 (antes de fixes)
- ❌ `partial_exits.csv` - Fecha: 06:30 (antes de fixes)

---

## 🔄 Cómo Re-ejecutar el Backtest

### Opción 1: Script Existente

```bash
cd /home/marcos/trade/momentum-v2
python3 daily_backtest_runner.py
```

### Opción 2: Ver opciones disponibles

```bash
# Ver qué backtests puedes ejecutar
ls -lh *backtest*.py
```

**Archivos disponibles:**
- `daily_backtest_runner.py` - Runner principal
- `backtest_runner.py` - Runner alternativo
- `ejecutar_backtest_nuevo.py` - Script personalizado

---

## 📊 Qué Esperar Después del Backtest

### 1. FASE_2 aparecerá

**Antes (bug):**
```
CVNA | FASE_1 | 40% | $220
CVNA | FASE_3 | 60% | -$309  ← Falta FASE_2
```

**Después (corregido):**
```
CVNA | FASE_1 | 40% | $220
CVNA | FASE_2 | 30% | $XXX  ✅ Aparece
CVNA | FASE_3 | 30% | $XXX  ✅ Correcto
```

### 2. Trend "Weak" desaparecerá

**Antes:**
```
📈 Tendencia: Weak  ← Contradictorio
```

**Después:**
```
📈 Tendencia: Uptrend  ✅ Coherente
```

### 3. RVOL filter funcionará

**Antes:**
```
AGI | RVOL: 0.76x  ← Entrada inválida
```

**Después:**
```
AGI | NO APARECE  ✅ Filtrado correctamente
```

---

## 🔬 Verificación Post-Backtest

### 1. Verificar archivos actualizados

```bash
ls -lh backtest_results.csv partial_exits.csv
# Debe mostrar fecha/hora reciente
```

### 2. Verificar FASE_2 en CSV

```bash
grep "FASE_2" partial_exits.csv | wc -l
# Debe mostrar > 0 (antes era 0)
```

### 3. Verificar Trend context

```bash
grep "Weak" backtest_results.csv | wc -l
# Debe ser mucho menor que antes
```

### 4. Abrir Dashboard

```bash
streamlit run app.py
```

**Verificar en dashboard:**
- [ ] Trades con FASE_1 muestran FASE_2 (si aplicable)
- [ ] Distribución 40% / 30% / 30%
- [ ] Contexto "Uptrend" coherente
- [ ] No hay entradas con RVOL < 1.5x

---

## ⚠️ Problemas Comunes

### Problema: "ModuleNotFoundError"

**Solución:**
```bash
pip install -r requirements.txt
```

### Problema: "No data loaded"

**Solución:** Verificar que tienes datos históricos:
```bash
ls -lh data/
```

### Problema: Backtest muy lento

**Solución:** Reduce el universo o periodo:
- Edita `daily_backtest_runner.py`
- Reduce fechas o número de símbolos

---

## 📝 Notas Importantes

### ¿Cuánto tiempo toma?

Depende del universo y periodo:
- **10 símbolos, 1 año:** ~5-10 minutos
- **100 símbolos, 2 años:** ~30-60 minutos
- **500 símbolos, 5 años:** ~2-4 horas

### ¿Puedo ver progreso?

Sí, el backtest muestra:
```
__PROGRESS__15/250__2024-06-15
```

### ¿Qué pasa si interrumpo?

- Los resultados parciales NO se guardan
- Debes re-ejecutar desde el inicio
- Usa `screen` o `tmux` para sesiones largas

---

## 🎯 Checklist Final

Antes de considerar que funciona:

- [ ] Re-ejecuté el backtest completo
- [ ] `backtest_results.csv` tiene fecha reciente
- [ ] `partial_exits.csv` tiene entradas FASE_2
- [ ] Dashboard muestra distribución 40%/30%/30%
- [ ] No hay trades "Weak" que entraron
- [ ] No hay entradas con RVOL < 1.5x

---

**Fecha guía:** 2025-12-22  
**Tiempo estimado:** 10-60 minutos (según configuración)  
**Acción requerida:** RE-EJECUTAR BACKTEST

```bash
# Comando principal:
cd /home/marcos/trade/momentum-v2
python3 daily_backtest_runner.py
```
