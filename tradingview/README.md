# 🏎️ Bugatti Momentum System — TradingView Manual

Este indicador de TradingView (en **Pine Script v6**) es un **dashboard companion (aproximación visual)** del **Signal Engine** (`combo_pure_momentum`) que corre autónomamente en tu VPS con el scanner Finviz.

> [!WARNING]
> **LIMITACIÓN IMPORTANTE & FUENTE DE VERDAD:**
> El indicador de TradingView sirve únicamente para **apoyo visual y dashboard manual**. No debe considerarse la fuente de verdad del sistema por las siguientes limitaciones:
> 1. **Mapeo Sectorial Manual:** TradingView no tiene acceso dinámico a la base de datos de taxonomía del sector y requiere que configures manualmente el ETF sectorial en los inputs del indicador. Si el ETF no se configura o se mapea incorrectamente, la señal visual diferirá del backend.
> 2. **Motor Python Canónico:** La única fuente de verdad oficial es el backend en Python que se ejecuta en el laboratorio/VPS usando el motor de señal canónico (`src/signals/signal_engine.py`) con la configuración en `config/production_config.json`.

---

## 🌟 Características Clave

1. **Dashboard Multicriterio (Panel Inferior Derecho):**
   * **Screener (Qullamaggie):** Verifica alineación del MA Stack, Relative Strength (RS) superior al percentil 58.01 (fórmula canónica de fallback vs SPY), y Trend Intensity >= 108.
   * **Stage 2 (Minervini):** Monitorea en tiempo real los 7 criterios de Mark Minervini para confirmar si el ticker está en Stage 2 alcista.
   * **Tier 2 Filters:** Muestra las métricas exactas del Optuna Trial 380: RVOL, ADR%, Distancia a SMA20 y Dollar Volume promedio.
   * **Contexto y Filtros de Sector:** Compara en vivo si el Sector ETF de este ticker está por encima de su SMA20.
   * **Composite Signal:** Enciende un bloque **⚡ SIGNAL LONG** color verde intenso solo cuando **todos** los filtros pasan simultáneamente en el cierre del bar, o muestra un bloque **❌ BLOCKED** indicando exactamente qué regla técnica bloqueó la señal.

2. **Overlay Visual Premium:**
   * **Medias Móviles Clave:** EMA10 (amarillo), SMA20 (cyan), SMA50 (verde), SMA100 (naranja) y SMA200 (rojo).
   * **MA Stack Background:** El fondo del chart se tiñe de un verde muy sutil y elegante cuando el MA stack está perfectamente alineado.
   * **Nivel de Breakout:** Dibuja una línea punteada horizontal en base al High más alto de los últimos 20 días (excluyendo el día de hoy) que sirve como gatillo de breakout.

3. **Risk Management Avanzado:**
   * Calcula el Stop Loss de forma canónica a **2 × ATR(14)**.
   * Aplica los mismos topes del VPS: Stop máximo del 12%, mínimo del 0.5%, y un fallback del 7% si el ATR no es confiable.
   * Proyecta dinámicamente las líneas de salida: **TP1 (1.25R)** y **TP2 (3.0R)** en el chart al activarse la señal.
   * Calcula el **Position Size** exacto en acciones según tu riesgo parametrizado (ej. **$2,878** por operación).

---

## 🛠️ Instrucciones de Instalación en TradingView

Sigue estos pasos sencillos para añadir el indicador a tu plataforma:

1. **Copiar el Código:**
   * Abre el archivo [bugatti_momentum.pine](file:///home/marcos/trade/momentum-v2/tradingview/bugatti_momentum.pine) y copia todo su contenido.

2. **Abrir el Pine Editor en TradingView:**
   * En TradingView, abre el chart de cualquier ticker.
   * En la barra inferior, haz clic en la pestaña **Pine Editor**.

3. **Pegar y Guardar:**
   * Borra cualquier código existente en el editor.
   * Pega el código completo de `bugatti_momentum.pine`.
   * Haz clic en **Save** (Guardar) en la esquina superior derecha del editor y asígnale el nombre: `Bugatti Momentum System`.

4. **Añadir al Gráfico:**
   * Haz clic en **Add to chart** (Añadir al gráfico).
   * ¡Listo! Verás el overlay visual (medias móviles, niveles) y la hermosa tabla de control en tu pantalla.

---

## ⚙️ Configuración y Mapeo de Sectores

El indicador cuenta con un panel de inputs extremadamente detallado para que lo adaptes a tu estilo de trading o actualices los umbrales:

### 1. Mapeo del Sector ETF (Crucial para el Filtro Sectorial)
TradingView no puede auto-detectar de forma 100% confiable el sector de todos los tickers en Pine. Por lo tanto, el indicador incluye un selector manual en los inputs bajo el grupo **Context & Regime**:
* Al abrir un gráfico (ej. `TSLA`), ve a los settings del indicador y selecciona el **Sector ETF** correcto en el selector:
  * **AMEX:XLK** ➔ Tecnología (AAPL, MSFT, NVDA, AMD)
  * **AMEX:XLY** ➔ Consumo Discrecional (AMZN, TSLA, MCD, NKE)
  * **AMEX:XLF** ➔ Financieros (BRK.B, JPM, GS, MS)
  * **AMEX:XLV** ➔ Salud / Pharma (LLY, UNH, JNJ, ABBV)
  * **AMEX:XLE** ➔ Energía / Oil (XOM, CVX, COP)
  * **AMEX:XLI** ➔ Industriales (CAT, GE, LMT, UNP)
  * **AMEX:XLC** ➔ Comunicaciones (GOOGL, META, NFLX)
  * **AMEX:XLP** ➔ Consumo Básico (WMT, PG, KO, PEP)
  * **AMEX:XLB** ➔ Materiales (LIN, FCX, APD)
  * **AMEX:XLRE** ➔ Inmobiliario (PLD, AMT, CCI)
  * **AMEX:XLU** ➔ Servicios Públicos / Utilities (NEE, SO, DUK)

> [!TIP]
> Si estás analizando una empresa de crecimiento fuera de estos sectores o que no responde a un ETF específico, puedes desmarcar la casilla **Enable Sector ETF Filter** en los inputs para desactivar esta regla técnica y no bloquear la señal.

### 2. Gestión de Riesgo (Risk Management)
Configura tu nivel de riesgo monetario exacto en la sección **Risk Management**:
* **Risk per Trade ($):** Por defecto en **$2,878** (Trial 380 para una cuenta de $100k al 2.878% de riesgo). El indicador te dirá exactamente cuántas acciones (`Shares`) debes comprar en el momento de la ruptura para no exceder esta pérdida máxima.

---

## 🔔 Configuración de Alertas en Gráfico

Puedes configurar alertas automáticas para que TradingView te notifique al instante en tu celular, navegador o correo cuando se active un breakout o se cumplan todos los filtros del sistema Bugatti:

1. Haz clic en el botón de **Alertas** (ícono de reloj despertador) en la barra lateral derecha o superior de TradingView.
2. En la opción **Condition** (Condición), selecciona **Bugatti Momentum System**.
3. Elige la señal que deseas monitorear:
   * **🏎️ Bugatti Signal LONG:** Se activa **únicamente** cuando el ticker hace un breakout y pasa **todos y cada uno de los filtros** (MA Stack, RVOL, ADR%, RS, Sector, SPY, etc.). Esta es la señal de alta convicción equivalente a la que verías en tu Telegram.
   * **📈 Breakout Detected:** Se activa simplemente cuando el precio supera el High de 20 días, ideal para radarizar e investigar candidatos de forma temprana.
   * **✅ MA Stack Restored:** Notifica cuando un ticker fuerte vuelve a alinear sus medias móviles en orden perfecto.
4. En **Action**, selecciona **Once Per Bar Close** (Una vez al cierre de la barra) para evitar señales falsas durante el día de trading.
5. El indicador enviará automáticamente un mensaje con formato premium idéntico al de tu VPS:
   ```text
   🏎️ BUGATTI SIGNAL: TSLA
   📍 Entry: $210.45
   🛑 Stop: $194.23 (2×ATR)
   🎯 TP1: $230.73 (1.25R)
   🎯 TP2: $259.11 (3.0R)
   📊 Shares: 177 | Risk: $2878
   📈 Score: 87.5 | RVOL: 2.34x | RS: 92.1%
   🏷️ Stage2: 7/7 | Sector: XLY
   ```
