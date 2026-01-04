# Sistema de Salidas Escalonadas - Implementación Completa

## 🎯 Objetivo
Convertir operaciones ganadoras en "risk-free" tempranamente mientras se mantiene exposición para capturar movimientos extendidos.

## 📐 Estructura del Sistema (3 Fases)

### FASE 1: CONVERSIÓN A RISK-FREE (+1R a +1.5R)

**Trigger:**
```
IF precio_high >= (entrada + 1.0R) 
   AND precio_close <= (entrada + 1.5R)
THEN ejecutar_fase_1()
```

**Acciones:**
- ✅ Vender 50% de la posición original
- ✅ Mover stop loss a precio de entrada (Breakeven)
- ✅ Marcar posición como "RISK-FREE"

**Ejemplo:**
```
Entrada: $100
Stop inicial: $95
R = $5

TP1 trigger: $105 (entrada + 1R)
Vende: 50% de las acciones
Nuevo stop: $100 (breakeven)
```

---

### FASE 2: TOMA DE BENEFICIOS EN RESISTENCIA/ADR (+2.5R o ADR)

**Trigger (OR lógico):**
```
IF precio_high >= (entrada + 2.5R)
   OR movimiento_del_dia >= (80% del ADR promedio)
THEN ejecutar_fase_2()
```

**Acciones:**
- ✅ Vender 30% de la posición ORIGINAL
- ✅ Asegurar beneficio principal
- ✅ Dejar 20% para runner

**Ejemplo:**
```
Continuando ejemplo anterior:
Posición restante: 50%
TP2 trigger: $112.50 (entrada + 2.5R) O ADR alcanzado
Vende: 30% de posición original
Quedan: 20% para fase 3
```

---

### FASE 3: RUNNER CON TRAILING STOP DINÁMICO

**Trigger:**
```
IF ema_8 < ema_21  // Cambio de tendencia
   OR precio_close < sma_20  // Ruptura de soporte
THEN cerrar_posicion_completa()
```

**Acciones:**
- ✅ Cerrar 20% restante al detectar cambio de tendencia
- ✅ Maximizar beneficio en movimientos extendidos
- ✅ Salida limpia sin dejar "dead money"

**Ejemplo:**
```
Runner: 20% de posición original
Mantiene mientras EMA8 > EMA21
Sale cuando tendencia se rompe
```

---

## 🔧 Configuración Actual

| Parámetro | Valor | Ajustable |
|-----------|-------|-----------|
| **Fase 1: Trigger** | +1R a +1.5R | Sí |
| **Fase 1: % Venta** | 50% | Sí |
| **Fase 2: Trigger** | +2.5R o ADR | Sí |
| **Fase 2: % Venta** | 30% | Sí |
| **Fase 3: Trailing** | EMA 8/21 | Sí |
| **Fase 3: % Runner** | 20% | Automático |

---

## 📊 Flujo de Ejecución

```
ENTRADA: 100% posición
    │
    ├─► Precio alcanza +1R
    │   ├─► FASE 1: Vende 50%
    │   └─► Stop → Breakeven
    │       Posición: 50% (RISK-FREE)
    │
    ├─► Precio alcanza +2.5R o ADR
    │   ├─► FASE 2: Vende 30%
    │   └─► Posición: 20% (RUNNER)
    │
    └─► EMA 8 cruza bajo EMA 21
        └─► FASE 3: Cierra 20%
            POSICIÓN CERRADA 100%
```

---

## 💡 Ventajas del Sistema

1. **Protección de Capital**
   - Posición risk-free en +1R
   - No puede perder dinero después de TP1

2. **Optimización de Beneficios**
   - Asegura ganancias tempranas (50% en +1R)
   - Captura movimientos extendidos (20% runner)

3. **Gestión Psicológica**
   - Elimina ansiedad (breakeven garantizado)
   - Permite "dejar correr" el runner sin estrés

4. **Flexibilidad**
   - Se adapta a diferentes volatilidades (ADR)
   - Ajustable según estilo de trading

---

## 📝 Registro de Salidas

Cada salida parcial se registra con:
- Fecha y hora de ejecución
- Precio de salida
- % vendido
- Fase ejecutada (1, 2, o 3)
- Razón de salida

**Ejemplo de Log:**
```
✅ FASE 1: AAPL - 50% vendido en +1R ($105.23), Stop → BE
✅ FASE 2: AAPL - 30% vendido en resistencia/ADR ($112.87)
🏁 FASE 3: AAPL - 20% cerrado por EMA_CROSS ($118.45)
```

---

## 🧪 Testing Recomendado

Después de implementar:

1. Ejecutar backtest completo
2. Verificar logs de salidas parciales
3. Comparar métricas vs. sistema anterior:
   - Win rate
   - Profit factor
   - Maximum drawdown
   - Average hold time

4. Validar que posiciones risk-free no generan pérdidas

---

## 🔄 Próximas Mejoras Opcionales

- [ ] Fase 2 configurable por volatilidad del símbolo
- [ ] Trailing stop alternativo por porcentaje
- [ ] Alertas visuales en dashboard para cada fase
- [ ] Estadísticas por fase (% de trades que llegan a cada nivel)
- [ ] Optimización de % de salida por fase según backtest

---

## 📚 Referencias

- **Archivo:** `src/backtest/daily_engine.py` (líneas 323-378)
- **Clase:** `DailyBacktestEngine._manage_positions()`
- **Estructura:** `Position` dataclass (incluye tp1_hit, tp2_hit, R_inicial, adr_valor)

---

✨ **Sistema completamente implementado y listo para testing.**
