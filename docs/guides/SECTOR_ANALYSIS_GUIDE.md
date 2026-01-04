# 📊 BACKTEST SECTOR & MARKET HEALTH ANALYTICS

## 🎯 **Objetivo**

Analizar la correlación entre tus trades ganadores y:
1. **Sector del ticker** (Tech, Energy, Consumer Cyclical, etc.)
2. **Market Health** en momento de entrada (GREEN/YELLOW/RED)
3. **Sector Momentum** (¿El sector estaba fuerte cuando entraste?)

**¿Por qué?** Para identificar si tus ganancias vienen de:
- ✅ **Tu sistema** (funciona en cualquier condición)
- ⚠️ **Suerte** (solo funcionó porque Tech explotó en 2024)

---

## 🚀 **USO RÁPIDO**

### **1. Análisis Básico**
```bash
python3 analyze_backtest_sectors.py --results backtest_results.csv
```

**Output:**
```
📈 CORRELATION ANALYSIS
════════════════════════════════════════════════════════════

1️⃣  PERFORMANCE BY SECTOR
────────────────────────────────────────────────────────────
Sector                    Trades  Avg_Return%  Median%  Std%   Win_Rate
────────────────────────────────────────────────────────────
Consumer Cyclical         15      4.8          3.2      8.1    0.73
Technology                23      2.1          1.5      6.5    0.61
Energy                    8       1.2          0.8      5.2    0.50
Financial                 12      -0.5         -0.2     4.8    0.42

2️⃣  PERFORMANCE BY MARKET HEALTH
────────────────────────────────────────────────────────────
Health      Trades  Avg_Return%  Median%  Win_Rate
────────────────────────────────────────────────────────────
GREEN       35      3.5          2.1      0.71
YELLOW      18      1.2          0.8      0.56
RED         5       -1.8         -2.1     0.20

3️⃣  PERFORMANCE BY SECTOR MOMENTUM
────────────────────────────────────────────────────────────
Momentum Class    Trades  Avg_Return%  Median%  Win_Rate
────────────────────────────────────────────────────────────
Strong (>10%)     12      5.2          3.8      0.83
Moderate (5-10%)  28      2.1          1.5      0.64
Weak (0-5%)       15      0.5          0.2      0.47
Negative          3       -2.1         -1.8     0.33

4️⃣  BEST COMBINATIONS (Sector + Market Health)
────────────────────────────────────────────────────────────
Sector             Health   Trades  Avg_Return%  Win_Rate
────────────────────────────────────────────────────────────
Consumer Cyclical  GREEN    8       8.2          0.88
Technology         GREEN    15      4.1          0.73
Energy             YELLOW   5       3.2          0.60

💡 INSIGHTS & OVERFITTING CHECK
════════════════════════════════════════════════════════════
⚠️  OVERFITTING RISK: 62.3% of PnL from Consumer Cyclical
   → Your system may be overfit to Consumer Cyclical characteristics

⚠️  MARKET DEPENDENCY: Win rate drops 51% in RED markets
   → System performs best in bull markets only

✅ Sector agnostic: Works across sector momentum levels
════════════════════════════════════════════════════════════
```

---

## 📊 **COMANDOS ÚTILES**

### **2. Análisis de Año Específico**
```bash
# Solo 2024
python3 analyze_backtest_sectors.py --results backtest_results.csv --year 2024

# Solo 2021
python3 analyze_backtest_sectors.py --results backtest_results.csv --year 2021
```

### **3. Report Completo con Gráficos**
```bash
python3 analyze_backtest_sectors.py \
    --results backtest_results.csv \
    --full-report \
    --output backtest_results_enriched.csv
```

**Genera:**
- ✅ `backtest_results_enriched.csv` - Con columnas de sector y market health
- ✅ `sector_performance.png` - Gráfico de barras por sector

---

## 📁 **ARCHIVOS GENERADOS**

### **backtest_results_enriched.csv**

Columnas originales + nuevas:

| Nueva Columna | Descripción |
|---------------|-------------|
| `sector` | Technology, Energy, Consumer Cyclical, etc. |
| `market_health_score` | 0-7 puntos (SPY trend + VIX) |
| `market_health_status` | GREEN, YELLOW, RED |
| `market_health_reasons` | SPY>EMA21, VIX<20, etc. |
| `sector_momentum_20d` | % momentum del sector en entrada |
| `sector_ranking` | 1-11 (ranking vs otros sectores) |
| `sector_momentum_class` | Strong, Moderate, Weak, Negative |

---

## 🧠 **INTERPRETACIÓN DE RESULTADOS**

### **Ejemplo: Tu caso TSLA 2024**

```
Ticker: TSLA
Entry Date: 2024-11-06
Sector: Consumer Cyclical
Market Health: GREEN (6/7 points - SPY>EMA21, VIX<20, VIX↓)
Sector Momentum: +15.2% (Ranking: #1 - Top sector)
Trade Return: +18.5%
```

**Análisis:**
✅ **Entry perfecta**: Sector #1, mercado GREEN
✅ **No overfitting**: Si otros trades también ganan en condiciones similares
⚠️ **Posible luck**: Si SOLO Consumer Cyclical en GREEN funciona

---

## 🔍 **CASOS DE OVERFITTING**

### **❌ Red Flag #1: Sector Concentration**
```
⚠️  62% of PnL from Technology
```
**Problema**: Sistema puede estar overfit a características de Tech (alta volatilidad, momentum extremo)

**Solución**:
- Validar en otros sectores (Energy, Healthcare)
- Agregar filtro de diversificación sectorial

---

### **❌ Red Flag #2: Market Dependency**
```
GREEN: 71% WR | RED: 20% WR (-51%)
```
**Problema**: Sistema solo funciona en bull markets

**Solución**:
- Desactivar trading en RED markets
- Reducir tamaño de posición en YELLOW

---

### **❌ Red Flag #3: Momentum Dependency**
```
Strong momentum: 83% WR | Weak: 47% WR (-36%)
```
**Problema**: Necesitas sector fuerte para ganar

**Solución**:
- Agregar filtro: Solo entrar si `sector_ranking <= 5`
- O reducir size si sector débil

---

## ✅ **SEÑALES DE SISTEMA ROBUSTO**

```
✅ Good diversification: Top sector = 35% of PnL
✅ Market resilience: Similar performance across conditions  
✅ Sector agnostic: Works across momentum levels
```

**Interpretación**: Tu sistema tiene **skill**, no solo luck

---

## 🛠️ **INTEGRACIÓN CON BACKTEST ENGINE**

Para que el backtest **guarde** sector y market health automáticamente:

```python
# En daily_engine.py - método _execute_pending_orders()

# Agregar al cerrar trade:
closed_trade['sector'] = get_sector(position.symbol)
closed_trade['market_health_score'] = current_market_health_score
closed_trade['market_health_status'] = current_market_health_status
closed_trade['sector_momentum_20d'] = sector_etf_momentum
```

---

## 📈 **WORKFLOW RECOMENDADO**

### **Después de cada backtest:**

1. **Ejecutar análisis**
   ```bash
   python3 analyze_backtest_sectors.py --results backtest_results.csv --full-report
   ```

2. **Revisar insights**
   - ¿Hay overfitting risk?
   - ¿Funciona en RED markets?
   - ¿Un sector domina?

3. **Ajustar estrategia**
   - Si Tech domina → Testar sin Tech
   - Si RED falla → Agregar market filter
   - Si momentum crítico → Agregar sector strength filter

4. **Validar Out-of-Sample**
   ```bash
   # Backtest 2023 (in-sample)
   python3 backtest_runner.py --start 2023-01-01 --end 2023-12-31
   
   # Analizar
   python3 analyze_backtest_sectors.py --results backtest_results.csv
   
   # Backtest 2024 (out-of-sample)
   python3 backtest_runner.py --start 2024-01-01 --end 2024-12-31
   
   # Comparar resultados
   ```

---

## 🎯 **PREGUNTAS QUE RESPONDE**

1. **¿Mi sistema está overfit a Tech?**
   → Mira % PnL por sector

2. **¿Solo funciona en bull markets?**
   → Compara GREEN vs RED win rate

3. **¿Necesito sector momentum para ganar?**
   → Compara Strong vs Weak momentum

4. **¿Qué combinación es mejor?**
   → Best Combinations table

5. **¿Mi mejor trade de 2024 fue skill o luck?**
   → Chequea sector momentum + market health en esa fecha

---

## 💡 **EJEMPLO REAL: Tu TSLA Trade**

```bash
# Analizar 2024
python3 analyze_backtest_sectors.py --results backtest_results.csv --year 2024

# Buscar en enriched results:
grep "TSLA.*2024-11" backtest_results_enriched.csv
```

**Output:**
```
TSLA,2024-11-06,2024-11-20,...
sector: Consumer Cyclical
market_health: GREEN (6/7)
sector_momentum_20d: 15.2%
sector_ranking: 1
returns_pct: 18.5%
```

**Interpretación:**
- ✅ Entrada en condiciones ÓPTIMAS (GREEN + Sector #1)
- ✅ Si otros trades similares también ganan → SKILL
- ⚠️ Si solo TSLA gana y otros Consumer Cyclical fallan → LUCK

---

## 🚀 **PRÓXIMOS PASOS**

1. Ejecuta análisis en tu backtest de 2021:
   ```bash
   python3 analyze_backtest_sectors.py --results backtest_results.csv --year 2021 --full-report
   ```

2. Identifica overfitting risks

3. Ajusta filtros si es necesario

4. Re-testea out-of-sample

---

**¿Preguntas?** Este sistema te ayuda a separar **SKILL vs LUCK** 🎯
