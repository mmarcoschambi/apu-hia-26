# QuantConnect PIT Assets Coverage Audit

Este documento provee un análisis detallado de la cobertura, rango de fechas y calidad de los datos de constituyentes Point-in-Time (PIT) almacenados en la carpeta `quantconnect/`. Esta auditoría es crítica para asegurar la veracidad del universo de backtesting y evitar sesgos de supervivencia o errores de categorización en los filtros de sector/estilo.

---

## 1. RESUMEN DE HALLAZGOS CRÍTICOS (GOTCHAS)

Durante la auditoría técnica de los archivos CSV se detectaron **anomalías graves de redundancia y corrupción de datos** mediante la comparación de hashes MD5 y listas de constituyentes activos:

> [!WARNING]
> **Corrupción de Sectores (XLV y XLF son copias de XLE):**
> Los archivos `XLV_pit_2019_2024.csv` (Healthcare) y `XLF_pit_2019_2024.csv` (Financials) tienen el mismo hash de contenido y contienen exactamente los mismos constituyentes que `XLE_pit_2019_2024.csv` (Energy). Esto significa que **cualquier filtro o exclusión que use XLV o XLF en base a estos archivos estará operando incorrectamente sobre empresas de Energía** (como `XOM`, `CVX`, `COP`).

> [!WARNING]
> **Placeholder de Universo Total (VTI es copia de DIA):**
> El archivo `VTI_pit_2019_2024.csv` (que debería representar el mercado total estadounidense con miles de activos) es idéntico a `DIA_pit_2019_2024.csv` (Dow Jones Industrial Average) y contiene únicamente los 30 constituyentes del Dow Jones. No debe utilizarse como proxy de universo amplio.

> [!NOTE]
> **Redundancia Temática (e11 es copia de VUG):**
> El archivo `e11_pit_2019_2024.csv` es idéntico a `VUG_pit_2019_2024.csv` (Vanguard Growth ETF). Representa un duplicado exacto del estilo de crecimiento.

---

## 2. MAPA COMPLETO DE ASSETS EN `quantconnect/`

A continuación se detalla el mapa de los 23 archivos analizados, clasificados por categoría:

| Archivo | Categoría | Rango de Fechas | Tickers Únicos | Filas Totales | Estado de Calidad | Observaciones |
| :--- | :--- | :--- | :---: | :---: | :--- | :--- |
| **iwb_pit_2019_2024.csv** | Index (Russell 1000) | 2019-01-01 a 2024-12-03 | 1,413 | 72,340 | ✅ OK | Base para Russell 1000 PIT. ~1,000 activos/mes. |
| **iwm_pit_2019_2024.csv** | Index (Russell 2000) | 2019-01-01 a 2024-12-03 | 3,548 | 141,699 | ✅ OK | Base para Russell 2000 PIT. ~1,900 activos/mes. |
| **sp500_pit_2019_2024.csv** | Index (S&P 500) | 2019-01-01 a 2024-12-03 | 637 | 36,226 | ✅ OK | Base para S&P 500 PIT. ~500 activos/mes. |
| **IVV_pit_2019_2024.csv** | Index (S&P 500 ETF) | 2019-01-01 a 2024-12-03 | 635 | 36,228 | ✅ OK | Duplicado funcional de `sp500_pit_2019_2024.csv`. |
| **qqq_pit_2019_2024.csv** | Index (Nasdaq 100) | 2019-01-01 a 2024-12-03 | 156 | 7,312 | ✅ OK | Base para Nasdaq 100. |
| **DIA_pit_2019_2024.csv** | Index (Dow Jones 30) | 2019-01-01 a 2024-12-03 | 39 | 2,162 | ✅ OK | Representa correctamente los 30 constituyentes del Dow. |
| **VTI_pit_2019_2024.csv** | Index (Total Market) | 2019-01-01 a 2024-12-03 | 39 | 2,162 | ❌ CORRUPTO | **Placeholder**. Copia idéntica de `DIA` (30 tickers). |
| **MDY_pit_2019_2024.csv** | Index (S&P MidCap 400) | 2019-01-01 a 2024-12-03 | 709 | 28,687 | ✅ OK | Base para MidCap PIT. |
| **SLY_pit_2019_2024.csv** | Index (S&P SmallCap 600) | 2019-01-01 a 2023-06-01 | 913 | 32,428 | ⚠️ INCOMPLETO | Los datos terminan en Junio de 2023. |
| **VUG_pit_2019_2024.csv** | Style (Growth) | 2019-01-01 a 2024-12-03 | 456 | 18,421 | ✅ OK | Filtro de Estilo de Crecimiento. ~180 activos/mes. |
| **VTV_pit_2019_2024.csv** | Style (Value) | 2019-01-01 a 2024-12-03 | 578 | 24,413 | ✅ OK | Filtro de Estilo de Valor. ~340 activos/mes. |
| **e11_pit_2019_2024.csv** | Thematic | 2019-01-01 a 2024-12-03 | 456 | 18,421 | ⚠️ DUPLICADO | Copia idéntica de `VUG`. |
| **XLB_pit_2019_2024.csv** | Sector (Materials) | 2019-01-01 a 2024-12-03 | 32 | 2,013 | ✅ OK | Materiales básicos. ~28 activos/mes. |
| **XLC_pit_2019_2024.csv** | Sector (Communication) | 2019-01-01 a 2024-12-03 | 36 | 1,806 | ✅ OK | Servicios de comunicación. ~22 activos/mes. |
| **XLE_pit_2019_2024.csv** | Sector (Energy) | 2019-01-01 a 2024-12-03 | 35 | 1,735 | ✅ OK | Energía. ~22 activos/mes. |
| **XLF_pit_2019_2024.csv** | Sector (Financials) | 2019-01-01 a 2024-12-03 | 35 | 1,735 | ❌ CORRUPTO | **Copia de XLE**. Contiene empresas de Energía. |
| **XLI_pit_2019_2024.csv** | Sector (Industrials) | 2019-01-01 a 2024-12-03 | 99 | 5,271 | ✅ OK | Industriales. ~78 activos/mes. |
| **XLK_pit_2019_2024.csv** | Sector (Technology) | 2019-01-01 a 2024-12-03 | 98 | 5,077 | ✅ OK | Tecnología. ~69 activos/mes. |
| **XLP_pit_2019_2024.csv** | Sector (Staples) | 2019-01-01 a 2024-12-03 | 39 | 2,455 | ✅ OK | Consumo Masivo. ~38 activos/mes. |
| **XLRE_pit_2019_2024.csv** | Sector (Real Estate) | 2019-01-23 a 2024-12-03 | 38 | 1,960 | ✅ OK | Real Estate. ~31 activos/mes. |
| **XLU_pit_2019_2024.csv** | Sector (Utilities) | 2019-01-01 a 2024-12-03 | 32 | 2,083 | ✅ OK | Servicios públicos. ~31 activos/mes. |
| **XLV_pit_2019_2024.csv** | Sector (Healthcare) | 2019-01-01 a 2024-12-03 | 35 | 1,735 | ❌ CORRUPTO | **Copia de XLE**. Contiene empresas de Energía. |
| **XLY_pit_2019_2024.csv** | Sector (Discretionary) | 2019-01-01 a 2024-12-03 | 78 | 4,231 | ✅ OK | Consumo discrecional. ~50 activos/mes. |

---

## 3. COBERTURA RUSSELL 1000 (IWB) VS UNIVERSO REAL

El archivo `iwb_pit_2019_2024.csv` constituye la fuente de verdad primaria para el universo de trading Russell 1000:

- **Estructura temporal:** Contiene **72 snapshots mensuales** continuos (desde `2019-01-01` hasta `2024-12-03`). Las fechas coinciden con el inicio de cada mes de negociación.
- **Constituyentes por snapshot:** En promedio, cada snapshot mensual contiene entre **973 y 1007 tickers activos**. Esto coincide exactamente con el tamaño objetivo de componentes del índice Russell 1000 (IWB ETF) a lo largo del tiempo.
- **Tickers únicos totales:** Hay **1,413 tickers únicos** registrados a lo largo del período. Esto demuestra la naturaleza Point-in-Time libre de sesgo de supervivencia, ya que preserva el historial de deslistamientos, fusiones y adquisiciones (e.g., empresas que salieron del índice).
- **Cobertura porcentual:** **100%** de los constituyentes del ETF `IWB` histórico a nivel de fin de mes.

---

## 4. RECOMENDACIONES DE USO POR CATEGORÍA

Basado en la auditoría de calidad, se establecen las siguientes reglas operativas para el uso de estos archivos en backtesting e ingesta a la base de datos `ticker_cache.db`:

### A. Índices de Referencia (Index)
- **Russell 1000:** Utilizar `iwb_pit_2019_2024.csv` (DB label: `RUSSELL1000`) sin restricciones. Es 100% confiable.
- **Russell 2000:** Utilizar `iwm_pit_2019_2024.csv` (DB label: `RUSSELL2000`). Es confiable.
- **S&P 500:** Utilizar `sp500_pit_2019_2024.csv` (DB label: `SP500`).
- **Dow Jones / Mercado Total:**
  - ✅ Utilizar `DIA_pit_2019_2024.csv` si se requiere simular el Dow.
  - 🚫 **PROHIBIDO usar `VTI_pit_2019_2024.csv`**. Si se requiere un universo amplio de mercado total, debe generarse uniendo `IWB` (Russell 1000) e `IWM` (Russell 2000).

### B. Sectores (Sector ETFs)
- **Sectores Válidos (Seguros para Backtest):** `XLB`, `XLC`, `XLE`, `XLI`, `XLK`, `XLP`, `XLRE`, `XLU`, `XLY`. Sus distribuciones de tickers son correctas.
- **Sectores Inválidos (🚫 PROHIBIDO usar):**
  - **`XLV` (Healthcare)**: No utilizar para backtests históricos basados en la tabla `pit_constituents`. Dado que es una copia de Energía, **el filtro de exclusión de salud (ex-XLV) no funcionará y terminará excluyendo Energía**.
  - **`XLF` (Financials)**: No utilizar bajo ningún concepto por el mismo motivo.
  - **Solución recomendada**: Mapear la pertenencia a sectores históricos (`XLV`/`XLF`) dinámicamente mediante la taxonomía oficial de Finviz o descargar y reconstruir un archivo PIT limpio para estos dos sectores antes de usarlos en simulaciones.

### C. Estilos y Temáticos (Style & Thematics)
- **VUG (Growth) y VTV (Value):** Son seguros para definir filtros de estilo.
- **e11 (Thematic):** Evitar. Al ser copia exacta de `VUG`, no aporta información adicional y causa redundancia de ingesta.
