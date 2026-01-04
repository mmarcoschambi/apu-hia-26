# 📊 GUÍA: Comparación de Estrategias de Entrada

## 🎯 Objetivo
Comparar estadísticamente dos estrategias de entrada:
1. **Entrada Inmediata**: Ejecuta cuando high >= trigger (actual)
2. **Entrada Vela Verde**: Solo ejecuta si close > open (confirmación alcista)

---

## 🚀 USO DEL SCRIPT

### Opción 1: Con tickers específicos
```bash
python3 compare_entry_strategies.py \
  --tickers "TSLA,NVDA,AAPL,META,MSFT,AMZN,AMD" \
  --start 2024-01-01 \
  --end 2024-12-31
```

### Opción 2: Con tickers por defecto (14 top líquidos)
```bash
python3 compare_entry_strategies.py --start 2024-01-01 --end 2024-12-31
```

### Opción 3: Capital personalizado
```bash
python3 compare_entry_strategies.py \
  --tickers "TSLA,NVDA,AAPL" \
  --start 2024-01-01 \
  --end 2024-12-31 \
  --capital 250000
```

---

## 📈 QUÉ HACE EL SCRIPT

1. **Ejecuta 2 backtests completos:**
   - Backtest A: Entrada inmediata (código actual)
   - Backtest B: Entrada solo en vela verde (código modificado)

2. **Compara métricas:**
   - Total de trades
   - Win rate %
   - Total PnL
   - Return %
   - Avg Win / Avg Loss
   - Entradas perdidas por filtro de vela

3. **Genera archivos:**
   - `entry_strategy_comparison.json` - Resumen de resultados
   - `trades_immediate_entry.csv` - Trades de estrategia inmediata
   - `trades_green_candle_entry.csv` - Trades de estrategia vela verde

---

## 📊 EJEMPLO DE SALIDA

```
================================================================================
  📊 COMPARACIÓN DE ESTRATEGIAS DE ENTRADA
================================================================================

Periodo: 2024-01-01 a 2024-12-31
Tickers: 7
Capital: $100,000

────────────────────────────────────────────────────────────────────────────────
🔵 ESTRATEGIA 1: ENTRADA INMEDIATA
   • Ejecuta cuando high >= trigger (sin importar color de vela)
────────────────────────────────────────────────────────────────────────────────

✅ Resultados:
   Total Trades: 35
   Win Rate: 48.6%
   Total PnL: $8,420.00
   Return: 8.42%

────────────────────────────────────────────────────────────────────────────────
🟢 ESTRATEGIA 2: ENTRADA SOLO EN VELA VERDE
   • Ejecuta SOLO si high >= trigger Y close > open
────────────────────────────────────────────────────────────────────────────────

✅ Resultados:
   Total Trades: 28
   Win Rate: 57.1%
   Total PnL: $9,850.00
   Return: 9.85%
   Entradas Perdidas (vela roja): 12

================================================================================
  📊 COMPARACIÓN LADO A LADO
================================================================================

Métrica                        Inmediata            Vela Verde           Diferencia     
─────────────────────────────────────────────────────────────────────────────────────
Total Trades                   35                   28                   -7
Win Rate (%)                   48.6                 57.1                 +8.5%
Total PnL ($)                  8,420                9,850                +1,430
Return (%)                     8.42                 9.85                 +1.43%
Avg Win ($)                    650                  780                  +130
Avg Loss ($)                   -320                 -280                 +40

================================================================================
  🎯 CONCLUSIÓN
================================================================================

✅ VELA VERDE ES MEJOR (+1.43% return)
   • Mejor selectividad en entradas
   • Evita 12 entradas en velas rojas
```

---

## 🔍 INTERPRETACIÓN DE RESULTADOS

### Si VELA VERDE gana:
- ✅ Mayor win rate (mejor calidad de entradas)
- ✅ Menos trades pero más selectivos
- ✅ Evita entradas en falsos breakouts (velas rojas)
- 💡 **Recomendación:** Implementar filtro de vela verde

### Si ENTRADA INMEDIATA gana:
- ✅ Más oportunidades capturadas
- ✅ No pierde momentum inicial
- ✅ Mejor para momentum fuerte intradiario
- 💡 **Recomendación:** Mantener entrada inmediata

### Si es EMPATE:
- 🤝 No hay diferencia estadística significativa
- 💡 **Recomendación:** Usar criterio de preferencia personal o testear más periodos

---

## 📝 PRÓXIMOS PASOS

1. **Ejecutar para diferentes periodos:**
   ```bash
   # Año 2024
   python3 compare_entry_strategies.py --start 2024-01-01 --end 2024-12-31
   
   # 2023
   python3 compare_entry_strategies.py --start 2023-01-01 --end 2023-12-31
   
   # 2022 (año bajista)
   python3 compare_entry_strategies.py --start 2022-01-01 --end 2022-12-31
   ```

2. **Analizar por tipo de mercado:**
   - Bull market vs Bear market
   - Alta vs baja volatilidad
   - Diferentes sectores

3. **Refinar si vela verde gana:**
   - Implementar en `daily_engine.py` línea 273
   - Agregar toggle en Streamlit
   - Testear en tiempo real

---

## ⚙️ IMPLEMENTACIÓN (Si decides usar vela verde)

Si los resultados muestran que vela verde es mejor, modificar en `daily_engine.py`:

```python
# ANTES (línea 272-273):
if daily_bar['high'] >= order.limit_price:
    execution_price = max(daily_bar['open'], order.limit_price)

# DESPUÉS:
is_green_candle = daily_bar['close'] > daily_bar['open']
if daily_bar['high'] >= order.limit_price and is_green_candle:
    execution_price = max(daily_bar['open'], order.limit_price)
```

---

## 🎓 NOTAS TÉCNICAS

**Diferencias clave:**
- **Inmediata:** Ejecuta intradiario si toca trigger (simula buy stop)
- **Vela Verde:** Espera confirmación de cierre alcista

**Limitaciones:**
- Backtest usa datos diarios (no intraday)
- Ejecución real en `daily_bar['open']` o `trigger` (el mayor)
- Vela verde requiere esperar al cierre del día

**Consideraciones:**
- Vela verde sacrifica velocidad por calidad
- Inmediata captura momentum pero acepta falsos breakouts
- Resultado depende del tipo de mercado y tickers

