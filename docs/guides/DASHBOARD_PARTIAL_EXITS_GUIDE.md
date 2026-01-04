# 📊 Guía: Salidas Parciales en el Dashboard

## 🎯 Objetivo
Mostrar las salidas parciales (Fase 1 y Fase 2) **directamente en el dashboard de Streamlit** para análisis visual e interactivo.

---

## 📋 VISTA GENERAL DEL DASHBOARD

Después de ejecutar el backtest, el dashboard muestra:

### 1. **Trade Log Principal** (tabla existente)
```
📋 Trade Log (Institutional)
┌────────┬──────────┬──────┬────────┬────────┬──────────┬─────┬──────────┐
│ Symbol │ Entry    │ Days │ Signal │ RVOL   │ Trend    │ ... │ P&L      │
├────────┼──────────┼──────┼────────┼────────┼──────────┼─────┼──────────┤
│ AAPL   │ 01-15-24 │  10  │ BLUE   │ 2.15x  │ Uptrend  │ ... │ +$1,029  │
│ TSLA   │ 01-20-24 │   5  │ VWAP   │ 1.85x  │ Uptrend  │ ... │ +$523    │
└────────┴──────────┴──────┴────────┴────────┴──────────┴─────┴──────────┘
```

### 2. **📤 Salidas Parciales (Nueva Tabla)** ⭐
```
📤 Salidas Parciales (Fases 1 y 2)
┌────────┬────────┬──────────┬──────┬──────┬────────┬───────┬──────┬────────┬────────────┐
│ Symbol │ Fase   │ Exit     │ Days │ Exit │ Shares │ % Sold│ P&L  │ Return │ Reason     │
│        │        │ Date     │      │ Price│ Sold   │       │      │ %      │            │
├────────┼────────┼──────────┼──────┼──────┼────────┼───────┼──────┼────────┼────────────┤
│ AAPL   │FASE_1  │ 01-16-24 │  1   │185.23│   50   │  50%  │+261  │ +2.9%  │TP1: +1R... │
│ AAPL   │FASE_2  │ 01-18-24 │  3   │193.45│   30   │  30%  │+403  │ +7.5%  │TP2: +2.5R..│
│ TSLA   │FASE_1  │ 01-21-24 │  1   │ 245.8│   25   │  50%  │+180  │ +3.1%  │TP1: +1R... │
└────────┴────────┴──────────┴──────┴──────┴────────┴───────┴──────┴────────┴────────────┘

Métricas Rápidas:
┌──────────────────┬────────────────┬────────────────┬─────────────────┐
│ Total P&L        │ Fase 1         │ Fase 2         │ Días Promedio   │
│ Parciales        │ Ejecutadas     │ Ejecutadas     │                 │
├──────────────────┼────────────────┼────────────────┼─────────────────┤
│ $844             │ 2              │ 1              │ 1.7 días        │
└──────────────────┴────────────────┴────────────────┴─────────────────┘
```

---

## 🔍 ANÁLISIS DETALLADO POR TRADE

Cuando seleccionas un trade específico para analizar:

### **Progresión de Salidas Parciales** (Nueva Sección)

```
📤 Progresión de Salidas Parciales

�� ENTRADA          🔵 FASE_1          🟡 FASE_2         🔴 FASE_3 (Final)
──────────────────  ──────────────────  ─────────────────  ──────────────────
Fecha: 2024-01-15   Fecha: 2024-01-16  Fecha: 2024-01-18  Fecha: 2024-01-25
Precio: $180.00     Precio: $185.23    Precio: $193.45    Precio: $198.20
Shares: 100         Vendido: 50 (50%)  Vendido: 30 (30%)  Vendido: 20 (20%)
R inicial: $5.00    P&L: +$261.50      P&L: +$403.50      P&L: +$364.00
                    Return: +2.9%      Return: +7.5%      Return: +10.1%
```

### **Resumen de Ejecución (Tabla)**

```
┌────────────────┬───────────────┬────────────┬────────┬─────────┬────────┬────────┐
│ Fase           │ Trigger       │ Exit Price │ Shares │ % Sold  │ P&L    │ Return │
├────────────────┼───────────────┼────────────┼────────┼─────────┼────────┼────────┤
│ FASE_1         │ +1R Risk-Free │ $185.23    │   50   │   50%   │ +$261  │ +2.9%  │
│ FASE_2         │ +2.5R         │ $193.45    │   30   │   30%   │ +$403  │ +7.5%  │
│ FASE_3 (Final) │ EMA_CROSS     │ $198.20    │   20   │   20%   │ +$364  │ +10.1% │
└────────────────┴───────────────┴────────────┴────────┴─────────┴────────┴────────┘
```

### **Métricas Totales**

```
┌─────────────┬─────────────────┬──────────────┬────────────────┐
│ Total P&L   │ Parciales P&L   │ Final P&L    │ Fases          │
│             │ (Fase 1+2)      │ (Fase 3)     │ Ejecutadas     │
├─────────────┼─────────────────┼──────────────┼────────────────┤
│ +$1,029     │ +$665           │ +$364        │ 2/2            │
└─────────────┴─────────────────┴──────────────┴────────────────┘
```

---

## 📊 CÓMO USAR EL DASHBOARD

### **Paso 1: Ejecutar Backtest**
```bash
python3 daily_backtest_runner.py
```

Esto genera:
- `backtest_results.csv` (trades completos)
- `partial_exits.csv` (salidas parciales) ⭐

### **Paso 2: Abrir Dashboard**
```bash
streamlit run app.py
```

### **Paso 3: Navegar por las Vistas**

#### **Vista 1: Tabla General**
- Scroll hacia abajo después del equity curve
- Verás la tabla principal de trades
- **NUEVA:** Debajo aparece la tabla "📤 Salidas Parciales"

#### **Vista 2: Análisis Detallado**
- En la sección "🔬 Análisis Detallado de Operaciones"
- Selecciona un trade del dropdown
- Verás el gráfico + **nueva sección de progresión de salidas**

---

## 🎨 ELEMENTOS VISUALES

### **Colores de Fases:**
- 🟢 **ENTRADA** - Verde (inicio)
- 🔵 **FASE_1** - Azul (+1R, risk-free)
- 🟡 **FASE_2** - Amarillo (+2.5R/ADR, profit secured)
- 🔴 **FASE_3** - Rojo (runner final)

### **Información en Cada Card:**
- **Fecha** de la salida
- **Días** desde entrada
- **Precio** de exit
- **Shares** vendidas
- **% Sold** (50%, 30%, 20%)
- **P&L** individual de esa fase
- **Return %** desde entrada

---

## 📈 ANÁLISIS POSIBLES

### **1. Rentabilidad por Fase**
En la tabla de salidas parciales puedes ver:
```python
# P&L total de Fase 1
Suma de todas las filas donde phase = 'FASE_1'

# P&L total de Fase 2
Suma de todas las filas donde phase = 'FASE_2'
```

### **2. Velocidad de las Salidas**
```python
# Días promedio hasta Fase 1
Promedio de 'days_to_exit' donde phase = 'FASE_1'
# Típicamente: 1-2 días

# Días promedio hasta Fase 2
Promedio de 'days_to_exit' donde phase = 'FASE_2'
# Típicamente: 3-5 días
```

### **3. Tasa de Ejecución**
```python
# ¿Qué % de trades llega a Fase 1?
Contar filas FASE_1 / Total trades × 100

# ¿Qué % de trades llega a Fase 2?
Contar filas FASE_2 / Total trades × 100
```

---

## 🔍 FILTROS APLICABLES

Los filtros en el sidebar **SE APLICAN** a ambas tablas:

```python
Filtro por Symbol: 'AAPL'
→ Muestra solo trades de AAPL
→ Muestra solo partial exits de AAPL

Filtro por Signal Type: 'BLUE_SKY'
→ Muestra solo trades Blue Sky
→ Muestra solo partial exits de Blue Sky
```

---

## 💡 EJEMPLO COMPLETO EN DASHBOARD

### **Escenario: Analizar trade AAPL**

1. **Abro dashboard** → Veo tabla principal
   ```
   AAPL | 01-15-24 | 10 días | BLUE_SKY | +$1,029
   ```

2. **Scroll down** → Veo tabla de salidas parciales
   ```
   AAPL | FASE_1 | 01-16-24 | +$261 (50%)
   AAPL | FASE_2 | 01-18-24 | +$403 (30%)
   ```

3. **Selecciono AAPL** en análisis detallado
   → Veo gráfico con entry/exits
   → **NUEVA SECCIÓN:** Timeline visual
   ```
   🟢 ENTRADA → 🔵 FASE_1 → 🟡 FASE_2 → 🔴 FASE_3
   $180       $185.23     $193.45     $198.20
   ```

4. **Veo tabla resumen:**
   ```
   Fase 1: +$261 (2.9%)
   Fase 2: +$403 (7.5%)
   Fase 3: +$364 (10.1%)
   Total:  +$1,029
   ```

5. **Insight:** 
   - Fase 2 aportó el 39% del P&L total
   - Fase 1 se ejecutó en 1 día (rápido ✅)
   - Runner (Fase 3) capturó +10% adicional

---

## 🎯 BENEFICIOS

### **Antes:**
- ❌ Solo veías el resultado final
- ❌ No sabías cuándo/cómo saliste
- ❌ Imposible optimizar por fase

### **Ahora:**
- ✅ Ves cada salida parcial individualmente
- ✅ Timeline visual de progresión
- ✅ P&L desglosado por fase
- ✅ Métricas de velocidad (días hasta cada fase)
- ✅ Análisis de contribución por fase
- ✅ Optimización basada en datos reales

---

## 🚀 PRÓXIMOS PASOS

1. **Ejecutar backtest** → Genera partial_exits.csv
2. **Abrir dashboard** → Ver nuevas tablas
3. **Analizar un trade** → Ver progresión detallada
4. **Identificar patrones:**
   - ¿Qué fase aporta más P&L?
   - ¿Vale la pena esperar Fase 2?
   - ¿Runners agregan valor significativo?

5. **Optimizar:**
   - Ajustar % de cada fase
   - Tunear triggers (¿2.5R óptimo?)
   - Considerar skip Fase 2 si no aporta

---

✨ **Dashboard ahora muestra el ciclo de vida completo de cada trade con todas sus salidas parciales**
