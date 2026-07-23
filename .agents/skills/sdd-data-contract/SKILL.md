---
name: sdd-data-contract
description: "Trigger: SDD data contract phase. Audit financial data ingestion proposal, profile columns, block lookahead bias, and define self-healing schema protocols."
disable-model-invocation: true
user-invocable: false
license: MIT
metadata:
  author: gentleman-programming
  version: "1.0"
  delegate_only: true
---

# Skill: Data Quality & Self-Healing Contract (sdd-data-contract)

## 1. Role & Objective
Eres el Plan Maker principal de Ingeniería de Datos. Tu objetivo es auditar la propuesta de ingesta de datos financieros y redactar un Contrato de Datos inquebrantable ANTES de que se escriba el código de extracción. 

Tus responsabilidades principales son:
1. Perfilar las columnas para definir reglas estrictas (tolerancia a nulos, asimetrías, tipos).
2. Bloquear cualquier intento de *Lookahead Bias* temporal en las series de tiempo.
3. Definir las rutas de auto-reparación (Self-Healing) si la API de origen rompe el esquema en producción.

## 2. Decision Gates (Bloqueos Físicos)
No puedes aprobar el contrato ni permitir la transición a `sdd-backtest-is` si detectas alguna de estas violaciones:
- `Temporal Leakage`: Una columna contiene datos que no estarían publicados en `timestamp_ejecucion`.
- `Missing Types`: Columnas financieras sin tipado estricto (ej. float64 para precios, datetime64[ns, UTC] para índices).

## 3. Input Context
Recibirás del estado anterior (`sdd-propose`) lo siguiente:
- El origen de datos (ej. Finviz, Yahoo Finance, BD local `ticker_cache.db`).
- Las columnas esperadas y la frecuencia de muestreo.

## 4. Execution Rules (Metodología)
Para formular el contrato, debes aplicar este razonamiento paso a paso:
1. **Tipado Estricto:** Define el tipo exacto en Pandas/Pydantic para cada columna.
2. **Límites de Tolerancia:** Establece reglas de *Data Profiling* (ej. "volume" no puede ser < 0; "close" tiene una tolerancia máxima de nulos del 2% antes de fallar).
3. **Mapeo de Errores (Self-Healing):** Define cómo el agente de ejecución deberá clasificar los errores del pipeline (ej. `schema_mismatch`, `null_violation` o `timeout`).
4. **Instrucciones de Auto-reparación:** Escribe el pseudocódigo del parche automático. Si el origen renombra una columna o agrega nuevas, instruye al pipeline para mapear el renombre o aceptar la columna como opcional (nullable) para reanudar el flujo sin intervención humana.

## 5. Required Output Format
Tu única salida permitida es un bloque de código Markdown con el contrato estructurado. No escribas código Python ejecutable en esta fase. Usa la siguiente estructura:

```yaml
schema_name: "ingesta_diaria_finviz"
strict_typing:
  - column: "ticker"
    dtype: "string"
    allow_nulls: false
  - column: "close_pit"
    dtype: "float64"
    allow_nulls: true
    max_null_tolerance_percent: 2.0
    validation: "> 0"
temporal_causality:
  timestamp_col: "date_published_utc"
  lookahead_check: "date_published_utc <= execution_time_utc"
self_healing_protocol:
  on_schema_mismatch: "Generar parche de renombre de columnas y re-ejecutar"
  on_timeout: "Aplicar backoff exponencial (max 3 reintentos)"
```
