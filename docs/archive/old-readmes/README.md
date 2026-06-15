# Triad Momentum Protocol v2

Sistema de trading institucional basado en el protocolo "Triad" - tres vectores de fuerza para capturar breakouts de momentum.

## Filosofía

**No perseguimos precios; capturamos la liberación de energía cuando la oferta desaparece.**

## Los 3 Vectores

1. **La Base (El Mapa)** - Dónde se acumula la energía
2. **AVWAP de Máximos (El Peaje)** - Dónde están atrapados los vendedores
3. **VWAP Intradía (El Pedal)** - Confirmación de flujo institucional

## Los 3 Caminos (Entry Logic)

### Camino 1: Blue Sky Breakout
El "Combo Perfecto". Base + AVWAP convergen → resistencia cero arriba.
- **Trigger**: Buy Stop en Base High + $0.05
- **Ejemplo**: RDDT - ruptura explosiva

### Camino 2: VWAP Reclaim
La "Segunda Oportunidad". Gap down → instituciones defienden → recuperación.
- **Trigger**: Manual al cruzar VWAP intradía
- **Ejemplo**: CEG - trampa para osos

### Camino 3: Safety Filter
El "Filtro de Seguridad". Evita Anticipation Breakouts.
- **Trigger**: Espera hasta romper AVWAP (no la base pequeña)
- **Protección**: Evita comprar antes del muro de vendedores

## Instalación

```bash
# Clonar el repositorio
cd momentum-v2

# Crear entorno virtual (recomendado)
python -m venv venv
source venv/bin/activate  # Linux/Mac
# o
venv\Scripts\activate  # Windows

# Instalar dependencias
pip install -r requirements.txt
```

## Uso

### Scanner Principal

```bash
python src/core/scanner.py
```

Edita el watchlist en `scanner.py`:

```python
watchlist = ['RDDT', 'CEG', 'AAPL', 'NVDA', 'TSLA']
```

### Salida Ejemplo

```
============================================================
SIGNAL FOR RDDT
============================================================
Camino: BLUE_SKY
Action: BUY_STOP
Entry Price: $100.05
Stop Loss: $95.20
Risk: 4.85%
Position Size: 100% of standard

Reasoning: Blue Sky Breakout: Base ($100.00) and AVWAP ($100.15) 
converge within 0.2%. Clear path above.
============================================================
```

## Estructura del Proyecto

```
momentum-v2/
├── config/
│   └── settings.py          # Configuración del sistema
├── src/
│   ├── core/
│   │   ├── scanner.py       # Scanner principal
│   │   └── market_context.py # Análisis SPY/QQQ
│   ├── data/
│   │   └── market_data.py   # Provider de datos (Yahoo Finance)
│   ├── indicators/
│   │   └── triad.py         # Los 3 indicadores
│   └── strategies/
│       └── triad_protocol.py # Lógica de los 3 Caminos
├── data/
│   └── cache/               # Cache de datos
├── logs/                    # Logs del sistema
└── requirements.txt
```

## Configuración

Ajusta parámetros en `config/settings.py`:

```python
RISK_PER_TRADE = 0.005  # 0.5% riesgo estándar
RISK_PER_TRADE_REDUCED = 0.0025  # 0.25% para Camino 2
BLUE_SKY_OFFSET = 0.05  # Offset del Buy Stop
AVWAP_TOLERANCE = 0.02  # Tolerancia de convergencia
```

## Gestión de Riesgo

| Camino | Stop Loss | Tamaño Posición |
|--------|-----------|-----------------|
| Blue Sky | Base Low o Entry - 1 ADR | 100% (0.5% riesgo) |
| VWAP Reclaim | Low of Day (LOD) | 50% (0.25% riesgo) |
| Safety | Entry - 1 ADR | 100% (0.5% riesgo) |

## Checklist Pre-Trade

Antes de ejecutar:

1. **¿Dónde está el AVWAP del ATH?**
   - En precio actual → Camino 1
   - 5-10% arriba → Camino 3 (espera)

2. **¿Cómo está el mercado (SPY/QQQ)?**
   - Gap Down o rojo → Camino 2

3. **¿Ha habido un Flush?**
   - Caída matutina + volumen bajo → Camino 2

## Logs y Debugging

Los logs se guardan en `logs/triad_YYYYMMDD.log` con información detallada de cada scan.

## Datos de Mercado

El sistema usa **Yahoo Finance** (gratis) via `yfinance`:
- **Intraday**: Hasta 60 días de datos M1/M5/M15
- **Daily**: Histórico completo para ATH y bases
- **Cache**: 5 min para intraday, 24h para daily

## Próximos Pasos

- [x] Integración completa de datos (Yahoo Finance)
- [x] **Backtesting con visualización gráfica** ✨ NUEVO
- [x] Position sizing calculator
- [x] Market context analyzer
- [ ] Integración con broker (IBKR/Alpaca)
- [ ] Dashboard web interactivo
- [ ] Alertas por Telegram/Discord
- [ ] Backtesting avanzado con métricas detalladas

## Disclaimer

Este sistema es para **uso educacional**. No constituye asesoramiento financiero. Opera bajo tu propio riesgo.

---

**"Respetamos al Jefe Final (AVWAP ATH)"**
