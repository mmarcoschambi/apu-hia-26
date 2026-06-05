# S5 Russell Optuna Design Spec
> Protocolo metodológico, parámetros congelados, espacio de búsqueda y gates anti-overfitting para la optimización S5.

Este documento establece formalmente el marco de diseño para el estudio de optimización de hiperparámetros **S5 Optuna**. Ninguna ejecución de optimización en producción debe iniciarse sin cumplir de forma estricta con las especificaciones y límites aquí descritos.

---

## 1. Definición del Benchmark Baseline (Ancla Comparativa)

El candidato benchmark validado sirve como baseline de control:
* **Universo**: Russell 1000 Point-in-Time (miembros de `pit_constituents` mapeados a `IWB`).
* **Riesgo por posición (Sizing)**: E25 v2 (`v2_atlas_informed` con riesgo base de $2,878 por trade).
* **Filtros Sectoriales**: Exclusión completa de `XLV` (salud bloqueado).
* **Variant E (Divergencia Temática)**: **Desactivada**.
* **Sector Caps**: **Desactivados** (no vbt limits).
* **E26 Exits/Scaling**: **Fuera de scope**.
* **Límite de Capital por Activo**: Máximo 20% expuesto por ticker (`ticker_cap = 0.20`).

---

## 2. Parámetros Congelados vs. Optimizables

Para garantizar la disciplina metodológica, se prohíbe explícitamente alterar la arquitectura básica de gestión de riesgo y exclusiones.

### 🚫 Parámetros Prohibidos (Congelados Estrictos)
| Parámetro | Valor Fijo | Razón |
| :--- | :---: | :--- |
| `exclude_sectors` | `["XLV"]` | Protección sectorial validada en shadow mode. |
| `ticker_cap` | `0.20` | Control estricto de concentración por posición. |
| `sector_cap` | `None` | Control de portfolio manager basado en correlación, no en límites arbitrarios. |
| `e25_version` | `"v2_atlas_informed"` | Curva de penalización no monotónica validada científicamente. |
| `variant_e_enabled` | `False` | Variant E queda excluida para evitar sesgos retrospectivos. |
| `use_dynamic_extension_sizing` | `True` | Sizing basado en extensión dinámico obligatorio. |

### 🟢 Parámetros Permitidos a Optimizar
| Parámetro | Tipo | Espacio de Búsqueda (S5 Range) | Propósito |
| :--- | :---: | :---: | :--- |
| `rs_window` | Entero | `[10, 20, 30, 40, 50]` | Ventana temporal de Relative Strength |
| `rs_percentile_min` | Flotante | `[75.0, 95.0]` (Paso 2.5) | Umbral percentil del RS |
| `rvol_window` | Entero | `[10, 15, 20, 30]` | Ventana de Relative Volume |
| `rvol_min` | Flotante | `[0.75, 2.0]` (Paso 0.1) | Umbral de participación de volumen |
| `max_dist_sma20` | Flotante | `[3.0, 15.0]` (Paso 0.5) | Extensión máxima a la SMA20 en entrada |
| `holding_days` | Entero | `[10, 15, 20, 25, 30]` | Duración de la posición |
| `tp1_r` | Flotante | `[1.0, 2.0]` (Paso 0.1) | Target parcial 1 en múltiplos de R |
| `tp2_r` | Flotante | `[2.5, 5.0]` (Paso 0.25) | Target parcial 2 en múltiplos de R |

---

## 3. Función Objetivo de Optimización

Optuna maximizará el **Calmar Ratio Robustecido (CRR)** durante el período In-Sample (IS: `2019-2023`). El CRR penaliza la concentración y los comportamientos inestables:

$$CRR = Calmar_{IS} \times (1 - PenalizacionConcentracion) \times FactorConsistencia \times PenalizacionDegradacion$$

Donde:
* **Calmar Ratio**: Retorno Anualizado / Max Drawdown.
* **Penalización de Concentración**: Si un activo representa >30% del PnL total:
  $$Penalizacion = 0.5 \times \left( \frac{PnL_{max\_ticker}}{PnL_{total}} - 0.30 \right)$$
* **Factor de Consistencia Temporal**: Penalización si alguno de los años IS cierra con PnL neto negativo (máximo 1 año negativo permitido antes de descarte).
* **Penalización de Degradación (2025-2026)**: Si el retorno en el período reciente es negativo o se degrada >50% frente al promedio anual IS, la prueba recibe una penalización multiplicativa.
* **Bajo Volumen de Trades**: Si la cantidad de trades totales en los 5 años es < 80, la iteración es podada inmediatamente (`pruned`).

---

## 4. Checklist de Gates Anti-Overfitting (Requisitos para Promoción)

El candidato propuesto por Optuna debe cumplir unánimemente con cada gate para calificar como "Gold Standard":

- [ ] **Temporalidad**: Al menos 3 de las 4 ventanas (folds) deben cerrar con retorno positivo.
- [ ] **Robustez Bootstrap**: El límite inferior de confianza al 95% (p5) del Profit Factor debe ser $\ge 1.05$.
- [ ] **Líder Único**: Ningún activo individual puede generar más del $30\%$ del PnL total.
- [ ] **Ablación de Líderes**: Al excluir la cohorte de líderes (`NVDA`, `AMD`, `META`, `AAPL`), el Profit Factor corregido debe ser $\ge 1.10$.
- [ ] **No Monocultivo Temporal**: La mejora de PnL no puede estar explicada por una única ventana atípica (ej: que el 100% de la ganancia provenga de la burbuja 2021).
- [ ] **Validación Externa Viva**: Los parámetros optimizados deben reproducir los trades del Track 1 (VPS logs reales) de forma coherente y sin desviaciones críticas de señal.

---

## 5. Comando Dry-Run Esperado

Para validar la correcta inicialización del motor, carga del universo Russell 1000 PIT y pre-cálculo de indicadores sin iniciar la optimización pesada, se utilizará el siguiente comando:

```bash
.venv/bin/python3 scripts/run_s5_optuna.py --dry-run \
  --index RUSSELL1000 \
  --start 2019-01-01 \
  --end 2023-12-31 \
  --e25-version v2_atlas_informed \
  --exclude-sectors XLV \
  --ticker-cap 0.20
```
