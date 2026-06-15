# Reporte de Validación Temporal y Robustez del Benchmark S5
> Generado automáticamente el: 2026-06-05 00:56:43

Este reporte presenta los resultados consolidados de la simulación del **Candidato Benchmark para S5** en el universo PIT del **Russell 1000** con exclusión de **XLV** y sizing penalizado **E25 v2**.

## 🏁 Resumen y Veredicto de Consistencia Temporal
- **Criterio de Aceptación**: Al menos 3 de 4 ventanas temporales positivas y PF de bootstrap >= 1.05.
- **Veredicto Temporal**: 🟢 **APROBADO** (4 de 4 ventanas cerradas en positivo).
- **Trades Totales en el Ciclo**: 640 trades.

### 📊 Tabla de Folds Históricos (OOS & IS)
| Ventana | Rango de Fechas | Retorno Total | Max Drawdown | Sharpe (VBT) | Trades | PF Bootstrap (p50) |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **2019-2020 (Bull / Crash COVID)** | `2019-01-01` a `2020-12-31` | 33.16% | -14.94% | 1.08 | 118 | 1.53 |
| **2021-2022 (Bear / Post-COVID)** | `2021-01-01` a `2022-12-31` | 18.62% | -21.21% | 0.60 | 148 | 1.20 |
| **2023-2024 (In-Sample Calibration)** | `2023-01-01` a `2024-12-31` | 45.69% | -28.63% | 0.79 | 231 | 1.37 |
| **2025-2026 (Reciente / Out-of-Sample)** | `2025-01-01` a `2026-06-01` | 50.33% | -20.13% | 1.32 | 143 | 1.57 |

## 🎲 Simulación Monte Carlo (Bootstrapping 5,000 Folds)
Simulación realizada sobre el pool de trades de todo el ciclo 2019-2026:
- **Win Rate (CI 95%)**: `50.94%` (Límite p5: `47.66%` a p95: `54.06%`)
- **Profit Factor (CI 95%)**: `1.40` (Límite p5: `1.18` a p95: `1.64`)
- **Sharpe basado en Trades (CI 95%)**: `0.151` (Límite p5: `0.090` a p95: `0.209`)

## 🔬 Desglose de Expectancia por Extensión (Z1 - Z6)
Análisis de rentabilidad y sizing promedio según la distancia porcentual del activo a su SMA20 en la entrada:
| Bucket | Trades | P&L Acumulado | Win Rate | Profit Factor | Sizing Factor Promedio |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **Z1 (<6.76%)** | 329 | $39547.94 | 48.0% | 1.20 | 1.00 |
| **Z2 (6.76-10%)** | 105 | $24100.49 | 51.4% | 1.40 | 0.66 |
| **Z3 (10-15%)** | 117 | $55552.07 | 57.3% | 2.02 | 0.37 |
| **Z4 (15-25%)** | 62 | $12430.81 | 48.4% | 1.28 | 0.41 |
| **Z5 (25-35%)** | 25 | $15800.97 | 64.0% | 3.24 | 0.21 |
| **Z6 (>35%)** | 2 | $-349.11 | 50.0% | 0.39 | 0.15 |

## 🛡️ Análisis de Concentración y Robustez (Ablación)
Auditoría para asegurar que el alfa de la estrategia no esté concentrada en unos pocos activos idiosincráticos:
- **Trades sin líderes principales** (NVDA, AMD, META, AAPL):
  * Cantidad de trades: 575
  * P&L Neto: $123529.35
  * Win Rate: 50.1% | Profit Factor: 1.38
- **Trades sin el mayor contribuidor individual** (`NVDA` - P&L: `$16961.51`):
  * Cantidad de trades: 615
  * P&L Neto: $130121.66
  * Win Rate: 50.7% | Profit Factor: 1.37

🟢 **Sin alertas de concentración**: La exposición está distribuida de forma robusta.