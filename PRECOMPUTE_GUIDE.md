# 📊 Precompute Indicators - Guía Completa

## ✅ Test Completado Exitosamente

**Resultados del Test (AAPL):**
- ✅ Indicadores calculados correctamente
- ✅ Archivo guarda/carga correctamente  
- ✅ Estructura de datos preservada
- ✅ Overhead de carga: solo +16.4% (0.11ms)
- ✅ Indicadores tienen 99%+ cobertura

**Archivo actualizado:** `AAPL.pkl` ahora tiene 11 columnas (antes 5)

---

## 🚀 Listo para Ejecutar Precompute Completo

### Lo Que Va a Pasar
1. Hace backup de TODOS los .pkl en `data/cache_backups/` (seguridad)
2. Agrega 6 columnas nuevas a cada ticker:
   - `sma_20`, `sma_50`, `atr`, `adr_pct`, `dollar_volume`, `avg_dollar_vol_20`
3. Tamaño de archivo aumenta ~99% (143 KB → 286 KB por ticker)
4. Penalidad de velocidad: solo +16% (mínimo)

### Resultados Esperados
- **3,923 tickers** serán procesados (AAPL ya está hecho)
- **Tiempo:** ~30-35 minutos
- **Espacio disco:** ~550 MB indicadores + ~550 MB backups = 1.1 GB total
- **Speedup:** 40-57x más rápido en cálculos de indicadores

---

## 📋 Instrucciones Paso a Paso

### Paso 1: Verificar Espacio en Disco
```bash
df -h data/cache  # Necesitas ~1.1 GB libre
```

### Paso 2: Ejecutar Precompute
```bash
python3 precompute_all_indicators.py
```

**El script va a:**
1. Mostrarte qué va a hacer
2. Pedir confirmación
3. Crear backups automáticamente
4. Procesar todos los tickers con barra de progreso
5. Loggear todo en `precompute_log.txt`

### Paso 3: Verificar Resultados
```bash
# Verifica algunos tickers
python3 << 'VERIFY'
import pandas as pd
for ticker in ['AAPL', 'MSFT', 'NVDA']:
    df = pd.read_pickle(f'data/cache/{ticker}.pkl')
    has_indicators = 'sma_20' in df.columns
    print(f"{ticker}: {'✅' if has_indicators else '❌'} {df.shape}")
VERIFY
```

---

## 🛡️ Características de Seguridad

### Backups
- Todos los archivos originales en `data/cache_backups/`
- Puedes hacer rollback en cualquier momento:
  ```bash
  rm data/cache/*.pkl
  cp data/cache_backups/*.pkl data/cache/
  ```

### Capacidad de Reanudar
- Si se interrumpe (Ctrl+C), solo vuelve a ejecutar
- Tickers ya procesados se saltan
- No hay trabajo duplicado

### Validación
- Cada ticker validado antes de guardar
- Debe tener al menos 10 valores SMA válidos
- Archivos corruptos se loggean y se saltan

---

## 📊 Comparación Antes vs Después

### Antes (actual - AAPL ya precomputado)
```python
# MSFT.pkl (ejemplo sin precompute)
Columns: ['Open', 'High', 'Low', 'Close', 'Volume']
Size: ~140 KB
Load: ~0.7ms
```

### Después (precomputado)
```python
# MSFT.pkl (después de precompute)
Columns: ['Open', 'High', 'Low', 'Close', 'Volume',
          'sma_20', 'sma_50', 'atr', 'adr_pct',
          'dollar_volume', 'avg_dollar_vol_20']
Size: ~280 KB
Load: ~0.8ms (+14%)
```

### Ganancia de Performance
| Tickers | Antes (calc) | Después (precomp) | Speedup |
|---------|--------------|-------------------|---------|
| 100 | 0.16s | 0.004s | **40x** |
| 1000 | 1.64s | 0.029s | **57x** |
| Walk Forward (500 BTs) | 16.7 min | <1 min | **16x** |

---

## ✅ Lista de Verificación

Después de ejecutar, verifica:
- [ ] Revisa `precompute_log.txt` para errores
- [ ] Verifica algunos tickers random tienen indicadores
- [ ] Corre un backtest rápido para confirmar speedup
- [ ] Compara tiempo de backtest antes/después

**Test rápido:**
```bash
# Debería ser mucho más rápido que antes
time python3 walk_forward_validation.py \
    --trials 3 --tickers AAPL MSFT NVDA \
    --start 2023-01-01 --end 2023-06-30
```

---

## 💡 Resumen de Impacto en Performance

**Problema Actual:**
- Cada backtest recalcula SMA/ATR/ADR para todos los tickers
- 1000 tickers = 1.64 segundos desperdiciados por backtest
- Walk Forward = 500 backtests = 13.7 minutos desperdiciados

**Después de Precompute:**
- Indicadores ya en cache
- Overhead de carga: +0.11ms por ticker (despreciable)
- Speedup Walk Forward: 16.7 min → <1 min

**Speedup General Esperado:**
- Backtest simple: 2.4x más rápido
- Walk Forward: 16x más rápido
- Workflows de optimización: 10-20x más rápido

---

## ⚠️ Notas Importantes

1. **Espacio Disco:** Necesitas 1.1 GB libre (550 MB indicadores + 550 MB backups)
2. **Tiempo:** ~30-35 minutos una sola vez
3. **Seguridad:** Backups creados automáticamente
4. **Resumible:** Puedes parar y reiniciar cuando quieras
5. **Validado:** Cada ticker verificado antes de guardar

**Esta es una operación ONE-TIME con GANANCIA MASIVA de performance.**

Ejecuta cuando tengas 35 minutos y 1.1 GB de disco libre.
