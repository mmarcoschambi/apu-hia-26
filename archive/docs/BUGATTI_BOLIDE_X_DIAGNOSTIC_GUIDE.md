# 🔍 BUGATTI BOLIDE X - AUDITORÍA Y DIAGNÓSTICO

## 🎯 ¿QUÉ ES BOLIDE X?

Versión del BOLIDE Walk-Forward con:
- ✅ Filtros RELAJADOS (más permisivo → genera más trades)
- ✅ Diagnóstico EXHAUSTIVO (verbose logging en failures)
- ✅ Exception handling completo
- ✅ Auditoría automática de data loading

**Usar cuando:** Tus filtros normales dan 0 trades y quieres diagnosticar POR QUÉ.

---

## 📊 DIFERENCIAS vs BOLIDE WALKFORWARD NORMAL:

| Feature | BOLIDE WF (normal) | BOLIDE X (diagnostic) |
|---------|-------------------|----------------------|
| min_rvol | 1.5 mínimo | 1.0 mínimo |
| min_adr | 1.5 mínimo | 1.0 mínimo |
| min_volume | 200k | 100k |
| min_dollar_volume | 10M | 5M |
| signal_type | any/breakout/vcp | any/breakout (sin VCP) |
| min_trades | 10 | 5 |
| Verbose logging | ❌ | ✅ Primeros 5 + failures |
| Exception trace | Básico | Full traceback |
| Data checks | ❌ | ✅ Automático |

---

## 🔍 DIAGNÓSTICO AUTOMÁTICO

### **Qué verifica en cada trial fallido:**

```python
⚠️  TRIAL 3 FALLIDO - 0 Trades
   Params: signal=any, rvol>=1.0, adr>=1.0
   ✅ Engine tiene 2516 días × 100 tickers
   ⚠️  SPY no cargado (lazy) pero require_bullish_spy=True
```

**Checks que hace:**
1. ✅ `engine.close` existe y tiene datos
2. ✅ Shape correcto (días × tickers)
3. ✅ SPY data si `require_bullish_spy=True`
4. ✅ Full traceback en excepciones

---

## 🚀 USO RECOMENDADO

### **Paso 1: Test con diagnóstico (primero usar BOLIDE X)**

```bash
python3 bugatti_bolide_X.py \
    --in-start 2010-01-01 --in-end 2019-12-31 \
    --val-start 2020-01-01 --val-end 2021-12-31 \
    --oos-start 2022-01-01 --oos-end 2024-12-31 \
    --layer1-trials 50 --layer1-tickers 100 \
    --layer2-trials 25 --layer2-tickers 50
```

**Observa el output:**
- Si genera trades → Filtros funcionan, puedes hacer stricter
- Si 0 trades → Diagnóstico te dice POR QUÉ

### **Paso 2: Si funciona, endurece filtros**

Una vez que veas que genera trades con BOLIDE X, puedes:

**Opción A:** Editar BOLIDE X y aumentar filtros gradualmente:
```python
# En bugatti_bolide_X.py línea ~56:
'min_rvol': [1.5, 2.0],      # Sube desde 1.0
'min_adr': [1.5, 2.0],       # Sube desde 1.0
'min_volume': [200000],       # Sube desde 100k
```

**Opción B:** Usa BOLIDE WF normal (filtros más estrictos):
```bash
python3 bugatti_bolide_walkforward.py \
    --in-start 2010-01-01 --in-end 2019-12-31 \
    --layer1-trials 100 --layer1-tickers 150
```

---

## 🐛 INTERPRETACIÓN DE ERRORES

### ✅ **"Engine tiene X días × Y tickers"**
```
⚠️  TRIAL 1 FALLIDO - 0 Trades
   ✅ Engine tiene 2516 días × 100 tickers
```

**Significado:** Data cargó OK, problema es que filtros son muy estrictos aún.

**Solución:** Relaja más los filtros o usa período más largo.

---

### ❌ **"engine.close es None"**
```
⚠️  TRIAL 1 FALLIDO - 0 Trades
   ❌ ERROR CRÍTICO: engine.close es None
```

**Significado:** Data NO cargó, hay problema en TickerCache o base de datos.

**Solución:**
1. Verifica que tienes datos: `python3 show_universe.py`
2. Check logs de DIVO initialization
3. Verifica período tiene datos suficientes

---

### ⚠️ **"SPY no cargado pero require_bullish_spy=True"**
```
⚠️  TRIAL 5 FALLIDO - 0 Trades
   ⚠️  SPY no cargado (lazy) pero require_bullish_spy=True
```

**Significado:** Activaste filtro SPY pero SPY no está en cache.

**Solución:**
1. Pobla SPY: `python3 add_major_indices.py`
2. O desactiva: `'require_bullish_spy': [False]`

---

### 🔥 **"EXCEPCIÓN EN TRIAL X"**
```
🔥 EXCEPCIÓN EN TRIAL 3: 'NoneType' object has no attribute 'shape'
Traceback (most recent call last):
  File "bugatti_bolide_X.py", line 182, in objective
    stats = engine.backtest(params)
  File "optimization_engine_divo.py", line 450, in backtest
    base_filters = (self.close > self.sma20)
AttributeError: 'NoneType' object has no attribute 'shape'
```

**Significado:** Exception durante backtest, traceback muestra DÓNDE.

**Solución:** Revisar línea exacta en el traceback (línea 450 en ejemplo).

---

## 📋 CHECKLIST DE TROUBLESHOOTING

### Si TODOS los trials dan -999:

- [ ] Verifica datos existen: `python3 show_universe.py`
- [ ] Verifica período tiene datos: `--in-start 2010-01-01` (no 2022)
- [ ] Usa > 100 tickers (más chances de trades)
- [ ] Relaja filtros aún más en código
- [ ] Mira verbose output de primeros 5 trials
- [ ] Check si alguna excepción aparece

### Si algunos trials SÍ generan trades:

✅ **PERFECTO!** Significa:
- Data loading funciona
- Backtest engine funciona
- Solo necesitas ajustar params

**Siguiente paso:** Observa qué params generan trades y ajusta rangos.

---

## 🔧 MODIFICAR FILTROS MANUALMENTE

Si quieres hacer ULTRA-PERMISIVO para test:

```python
# Edita bugatti_bolide_X.py línea ~56:

LAYER1_PARAMS = {
    'risk_dollars': [200],  # Solo un valor
    'max_exposure_pct': [0.30],  # Solo un valor
    'min_rvol': [0.5],  # MUY bajo
    'min_adr': [0.5],   # MUY bajo
    'signal_type': ['any'],  # Solo 'any'
    'tp1_r': [1.5],
    'tp2_r': [3.0],
    'rvol_danger_size': [0.30],
}

LAYER2_PARAMS = {
    'min_consolidation_days': [3],  # MUY bajo
    'max_consolidation_range': [30.0],  # MUY permisivo
    'min_volume': [50000],  # MUY bajo
    'min_dollar_volume': [1e6],  # MUY bajo
    'max_dist_sma20': [30.0],  # MUY permisivo
    'max_stop_pct': [0.10],  # Stop amplio
    'rvol_danger': [4.0],
    'rvol_warning': [3.0],
    'rvol_warning_size': [0.70],
    'require_bullish_spy': [False],
    'max_vix': [100.0],  # Sin límite
}
```

Con esto, si AÚN da 0 trades → problema es data, no filtros.

---

## 📊 VERIFICAR SPY DATA EN DIVO

### **Cómo DIVO carga SPY:**

```python
# src/backtest/optimization_engine_divo.py línea ~319

@property
def spy_close(self):
    if self._spy_close is None:
        try:
            spy_df = self.cache.get_ohlcv(
                'SPY',
                start_date=(self.start_date - timedelta(days=self.lookback_days)).strftime('%Y-%m-%d'),
                end_date=self.end_date.strftime('%Y-%m-%d'),
                offline=self.offline_mode
            )
            if spy_df is not None and len(spy_df) >= 100:
                # Convert to Float32 y reindex
                self._spy_close = spy_df['close'].reindex(self.close.index).ffill().astype(self.dtype)
            else:
                # Fallback: Series de 0s (no rompe)
                self._spy_close = pd.Series(0, index=self.close.index, dtype=self.dtype)
        except:
            # Exception: Safe fallback
            self._spy_close = pd.Series(0, index=self.close.index, dtype=self.dtype)
    return self._spy_close
```

**Características:**
- ✅ Lazy (solo carga si se accede)
- ✅ Safe fallback (devuelve 0s si falla)
- ✅ No rompe el backtest nunca
- ✅ Float32 automático

**Para verificar SPY manualmente:**

```bash
python3 -c "
from src.data.ticker_cache import TickerCache
cache = TickerCache()
spy = cache.get_ohlcv('SPY', '2010-01-01', '2024-12-31', offline=True)
print(f'SPY data: {len(spy)} días' if spy is not None else 'SPY NO ENCONTRADO')
"
```

---

## 🎓 RESUMEN EJECUTIVO

### **BOLIDE X es para:**
- 🔍 Diagnosticar por qué tus filtros no generan trades
- 🐛 Debug de data loading issues
- 📊 Encontrar rangos de params viables

### **NO es para:**
- ❌ Production (usa BOLIDE WF normal)
- ❌ Final optimization (filtros demasiado flojos)

### **Workflow recomendado:**
```
1. Corre BOLIDE X con verbose
   ↓
2. Observa diagnóstico
   ↓
3. Ajusta filtros gradualmente
   ↓
4. Cuando genera trades consistentes → BOLIDE WF normal
```

---

**Built for debugging. Optimized for insights. Ready to diagnose.** 🔍🏎️

**Fin.**
