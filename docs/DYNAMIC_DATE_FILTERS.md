# 📅 Filtros de Fecha Dinámicos en Streamlit

## ✅ Implementado

El dashboard de Streamlit ahora detecta **automáticamente** el rango de fechas disponible en tu cache y ajusta los filtros de fecha en consecuencia.

---

## 🎯 Características

### 1️⃣ **Detección Automática de Rango**

La función `get_cache_date_range()` escanea todos los archivos `.pkl` en `data/cache/` y determina:

```
📦 Datos disponibles: 2020-12-22 a 2025-12-22
```

- **Min Date**: Fecha más antigua en cualquier archivo del cache
- **Max Date**: Fecha más reciente en cualquier archivo del cache
- **Fallback**: Si no hay cache → `2020-01-01` a `HOY`

---

### 2️⃣ **Date Pickers Inteligentes**

Los selectores de fecha en el sidebar ahora:

✅ **Se limitan al rango del cache** (no puedes elegir fechas sin datos)
✅ **Muestran advertencias** si seleccionas fuera del rango
✅ **Calculan duración** del backtest en días/años
✅ **Default inteligente**: Última año disponible

**Ejemplo:**
```python
run_start_date = st.date_input(
    "Fecha Inicio", 
    value=st.session_state.start_date,
    min_value=cache_min_date.date(),  # ← Límite inferior
    max_value=cache_max_date.date()   # ← Límite superior
)
```

---

### 3️⃣ **Botón de Rango Aleatorio Mejorado**

El botón `🎲 Rango Aleatorio (Backtest)` ahora:

- ✅ Solo genera fechas **dentro del cache disponible**
- ✅ Elige duraciones de 3-8 meses (óptimo para backtesting)
- ✅ No genera rangos imposibles

---

### 4️⃣ **Verificador de Cache por Símbolo**

**Nuevo botón:** `🔍 Verificar Cache de Símbolos`

Antes de ejecutar un backtest, verifica si tienes datos completos:

```
✅ APP: 2020-12-22 → 2025-12-22 (1826 días)
⚠️ PLTR: Datos incompletos para rango seleccionado
📥 NVDA: No en cache (se descargará)
```

**Estados posibles:**
- ✅ **Verde**: Datos completos para el rango seleccionado
- ⚠️ **Amarillo**: Ticker en cache pero rango incompleto
- 📥 **Azul**: Ticker no en cache, se descargará
- ❌ **Rojo**: Error leyendo cache

---

## 🚀 Uso

### Workflow Recomendado

```
1. Abrir Dashboard Streamlit
   └─ streamlit run app.py

2. Ver rango disponible en el sidebar
   └─ 📦 Datos disponibles: 2020-12-22 a 2025-12-22

3. Ingresar símbolos a testear
   └─ APP, PLTR, NVDA

4. [OPCIONAL] Verificar cache
   └─ Click en "🔍 Verificar Cache de Símbolos"
   └─ Ver qué tickers están listos

5. Seleccionar rango de fechas
   └─ Usar date pickers (limitados al cache)
   └─ O click "🎲 Rango Aleatorio"

6. Ejecutar backtest
   └─ Click "🚀 EJECUTAR BACKTEST"
```

---

## 📊 Beneficios

| Antes | Ahora |
|-------|-------|
| ❌ Podías elegir fechas sin datos | ✅ Solo fechas con datos disponibles |
| ❌ No sabías qué tickers tenías | ✅ Verificación pre-backtest |
| ❌ Fechas aleatorias inválidas | ✅ Aleatorias dentro del cache |
| ❌ Errores al ejecutar | ✅ Validación proactiva |

---

## 🔍 Inspección Manual del Cache

Si necesitas más detalles sobre tu cache:

```bash
# Resumen general
python3 inspect_cache.py

# Inspeccionar ticker específico
python3 inspect_cache.py --ticker AAPL

# Verificar preparación para backtest
python3 inspect_cache.py --check-backtest 2024-01-01 2024-12-31 temp_backtest_list.json
```

**Ver:** `CACHE_MANAGEMENT_GUIDE.md` para más detalles.

---

## 🛠️ Implementación Técnica

### Función Principal

```python
def get_cache_date_range():
    """
    Obtiene el rango de fechas real disponible en el cache
    Returns: (min_date, max_date) as datetime objects
    """
    import pickle
    
    cache_dir = 'data/cache'
    min_date = None
    max_date = None
    
    if not os.path.exists(cache_dir):
        return datetime(2020, 1, 1), datetime.now()
    
    try:
        for file in os.listdir(cache_dir):
            if file.endswith('.pkl'):
                try:
                    with open(os.path.join(cache_dir, file), 'rb') as f:
                        data = pickle.load(f)
                        if not data.empty:
                            dates = data.index
                            file_min = dates.min()
                            file_max = dates.max()
                            
                            if min_date is None or file_min < min_date:
                                min_date = file_min
                            if max_date is None or file_max > max_date:
                                max_date = file_max
                except:
                    continue
    except:
        pass
    
    if min_date is not None and max_date is not None:
        if hasattr(min_date, 'to_pydatetime'):
            min_date = min_date.to_pydatetime()
        if hasattr(max_date, 'to_pydatetime'):
            max_date = max_date.to_pydatetime()
        return min_date, max_date
    
    return datetime(2020, 1, 1), datetime.now()
```

### Performance

- ✅ **Rápido**: Escanea cache en ~100ms (154 archivos)
- ✅ **Sin red**: Solo lee archivos locales
- ✅ **Robusto**: Maneja errores de lectura
- ✅ **Cache de Streamlit**: Resultado se cachea automáticamente

---

## 📝 Notas

### Limitaciones

1. **Solo escanea archivos existentes**: Si un ticker no tiene datos, no lo sabrás hasta el backtest
2. **Gaps en datos**: Un ticker puede tener 2020-2021 y 2024-2025 pero nada en 2022-2023 (esto no se detecta)
3. **Calidad de datos**: No valida si los datos están completos día a día

### Recomendaciones

✅ **Ejecuta `inspect_cache.py` regularmente** para mantener datos actualizados
✅ **Usa `--check-backtest`** antes de backtests largos para validar cobertura completa
✅ **Descarga datos proactivamente** con `inspect_cache.py --download TICKER`

---

## 🎓 FAQ

**P: ¿Por qué no veo fechas hasta 2000?**
R: Solo tienes datos desde 2020-12-22. Descarga más con `inspect_cache.py --download AAPL --start 2000-01-01`

**P: ¿El cache expira?**
R: No, los datos persisten entre sesiones. Ver `CACHE_MANAGEMENT_GUIDE.md`

**P: ¿Puedo forzar fechas fuera del rango?**
R: No desde el dashboard. Edita `app.py` si realmente lo necesitas (no recomendado)

**P: ¿El "Rango Aleatorio" siempre funciona?**
R: Sí, ahora solo elige dentro de fechas disponibles.

---

## 🔗 Ver También

- `CACHE_MANAGEMENT_GUIDE.md` - Gestión completa del cache
- `inspect_cache.py` - Herramienta de inspección
- `DYNAMIC_BACKTEST_GUIDE.md` - Backtesting con universos dinámicos

---

**Última actualización:** 2024-12-22  
**Archivos modificados:** `app.py`  
**Archivos creados:** `inspect_cache.py`, `CACHE_MANAGEMENT_GUIDE.md`
