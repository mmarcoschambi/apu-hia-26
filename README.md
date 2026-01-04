# 🚀 Momentum Trading V2

Sistema de trading institucional automatizado basado en el protocolo "Triad" (Base + AVWAP + VWAP). Diseñado para capturar breakouts de momentum con gestión de riesgo profesional.

---

## ⚡ Inicio Rápido

### 1. Comandos Principales (Lo único que necesitas saber)

| Acción | Comando | Descripción |
|--------|---------|-------------|
| **Dashboard** | `streamlit run app.py` | Tu centro de comando. Ve gráficos, señales y corre backtests visuales. |
| **Scanner** | `python3 live_scanner.py` | Escanea el mercado en tiempo real buscando setups. |
| **Backtest** | `python3 backtest_dynamic_universe.py --start 2024-01-01 --end 2024-12-31` | Simula trading histórico (1 año recomendado). |
| **Universo** | `python3 manage_universe.py --info` | Gestiona tus tickers y el cache. |

### 2. Workflow Diario

1.  **Pre-Market (9:00 AM):** Ejecuta `python3 morning_workflow.py`. Verifica la salud del mercado y busca setups.
2.  **Market Open (9:30 AM):** Abre el dashboard con `streamlit run app.py` para monitorear.
3.  **Post-Market (4:00 PM):** Ejecuta `python3 position_tracker.py` para revisar tus posiciones.

---

## 📂 Estructura del Proyecto

```
momentum-v2/
├── app.py                     # 🖥️ Dashboard principal (Streamlit)
├── live_scanner.py            # 📡 Escáner de mercado en tiempo real
├── backtest_dynamic_universe.py # 🔬 Motor de Backtesting
├── manage_universe.py         # ⚙️ Gestor de tickers y descargas
│
├── data/
│   ├── cache/                 # 💾 Datos históricos (No borrar para velocidad)
│   └── universe/              # 📋 Listas de tickers (json)
│
├── docs/                      # 📚 Documentación detallada
│   ├── guides/                # Guías específicas (Backtesting, Filtros, etc.)
│   └── archive/               # Logs y notas antiguas
│
├── outputs/                   # 📊 Resultados generados
│   ├── backtests/             # CSVs de backtests
│   └── logs/                  # Logs de ejecución
│
└── src/                       # 🧠 Código fuente del núcleo
    ├── strategies/            # Lógica de compra/venta (Triad Protocol)
    ├── backtest/              # Motores de simulación
    └── data/                  # Gestores de datos
```

---

## 🛠️ Herramientas de Mantenimiento

### Cache y Datos
Si necesitas regenerar datos o arreglar gráficos:
*   `python3 populate_historical_cache.py`: Descarga historial completo (lento, pero exhaustivo).
*   `python3 inspect_cache.py`: Diagnostica el estado de tus datos.
*   `python3 quick_populate_cache.py`: Versión rápida para últimos 10 años.

### Gestión de Tickers
*   **Ver info:** `python3 manage_universe.py --info`
*   **Agregar:** `python3 manage_universe.py --add "TICKER1, TICKER2"`
*   **Refrescar índices:** `python3 add_major_indices.py` (Agrega S&P500 y NASDAQ100)

---

## 🧠 Lógica del Sistema (Resumen)

El sistema opera bajo 3 "Caminos" de entrada:

1.  **Camino 1 (Blue Sky):** Rompimiento de máximos históricos o bases claras sin resistencia cercana. Requiere **RVOL > 1.5x**.
2.  **Camino 2 (VWAP Reclaim):** Recuperación del VWAP intradía tras una caída (Flush).
3.  **Camino 3 (Safety):** Entradas conservadoras esperando confirmación de tendencia.

**Filtros de Mercado (Market Health):**
El sistema NO opera si:
*   SPY está debajo de SMA20 (Tendencia bajista).
*   VIX > 25 (Alta volatilidad).

---

## 📚 Documentación Adicional
Toda la documentación detallada se ha movido a la carpeta `docs/`:
*   `docs/guides/BACKTESTING_GUIDE.md`: Detalles profundos sobre cómo simular.
*   `docs/guides/LIVE_TRADING_GUIDE.md`: Protocolo para operar con dinero real.
*   `docs/guides/MARKET_FILTERS.md`: Explicación matemática de los filtros.

---
*Momentum V2 - Última actualización: Diciembre 2025*
