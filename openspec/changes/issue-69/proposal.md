# Proposal: feat(microstructure): Cross-validation engine — Microstructure vs Time hybrid pipeline

## Intent
# Cross-Validation Engine: Microstructure vs Time Hybrid Pipeline

## References & Context
- **Hypothesis Origin (Gemini Discussion):** https://share.gemini.google/qRX72BxnsDBn
- **Relative Strength Reference (TradingView RS Rating):** https://fr.tradingview.com/script/pziQwiT2/

## Context
El sistema actual opera en horizonte swing (>= 10 dias) con barras diarias. Esta feature introduce un subsistema de **validacion cruzada intraday** que combina dos paradigmas de analisis complementarios:
- **Pipeline A (Microestructura):** Barras por volumen (Volume Bars) que capturan actividad institucional real.
- **Pipeline B (Temporal):** Barras por tiempo clasicas enriquecidas con Vol Buzz (Z-Score) y AVWAP como proxy institucional.

Un modelo LightGBM (ya parte del stack) fusiona ambas senales para decidir dinamicamente cual priorizar segun contexto.

## Architecture Overview

### New Module: `src/microstructure/`
```
src/microstructure/
  __init__.py
  data_pipeline.py       # DuckDB lazy ingestion + Polars conversion
  volume_bars.py         # Pipeline A: Volume Bar construction + Bollinger signal
  time_bars.py           # Pipeline B: Time Bar + Vol Buzz + AVWAP + Bollinger signal
  feature_engine.py      # Feature extraction from both pipelines
  hybrid_model.py        # LightGBM ensemble trainer + walk-forward CV
  numba_kernels.py       # JIT-compiled vectorized backtesting kernels
```

### Integration Points with Existing System
- `src/signals/signal_engine.py` — RS computation reused as ML feature
- `src/ml/` — LightGBM training infra reused
- `src/optimization/` — Optuna sweeping reused for hyperparameter search
- `src/utils/market_health.py` — `health_score` (0-7) injected as ML feature
- `src/indicators/` — ATR, Bollinger base calculations

### New Dependencies
- `duckdb` — Lazy disk-based SQL for tick data ingestion (RTH filtering)
- `polars` — Vectorized in-memory processing (replaces pandas for tick scale)
- `numba` — JIT compilation for backtesting kernels (no Python for-loops)

---

## Spec: 6 Sections

### 1. Data Pipeline (Ingestion Layer)
- **Input:** CSV/Parquet with tick-level data (Timestamp, Price, Volume, Bid, Ask)
- **Engine:** DuckDB lazy queries reading directly from disk, filtering RTH hours only
- **Output:** Polars DataFrame in RAM for vectorized downstream processing
- **Constraint:** Must handle millions of rows without collapsing physical memory

### 2. Pipeline A — Microstructure Motor (Volume Bars)
- **Resampling:** Iteratively group ticks until cumulative Volume reaches threshold V (candidates: V in {10k, 25k, 50k})
- **OHLC Construction:** Build Open/High/Low/Close per volume bar
- **Signal A (Pure Breakout):**
  - Bollinger Bands (period P, std dev D) over Volume Bar Close
  - Trigger: `Close_current > Bollinger_Upper_prev AND Close_current > Close_prev`
  - No volume filter needed — the bar itself guarantees institutional participation
- **Output:** Boolean matrix `Signal_A`

### 3. Pipeline B — Temporal Motor + Institutional Proxy (Time Bars)
- **Resampling:** Traditional candles at T-minute intervals (candidates: T in {1m, 3m, 5m})
- **Features:**
  - **Vol Buzz (Z-Score):** Group historical volume by minute-of-day (e.g., all 10:05 AM bars over 50 days). Z = (Current_Vol - Mean) / StdDev
  - **AVWAP:** Anchored VWAP from RTH open (9:30 AM EST)
- **Signal B (Conditioned Breakout):**
  - Bollinger Bands over Time Bar Close
  - Trigger: `Close_current > Bollinger_Upper_prev AND Z_Score > Threshold_Z AND Close_current > AVWAP_current`
- **Output:** Boolean matrix `Signal_B`

### 4. Vectorized Backtesting Engine
- **Implementation:** 3D vectorized matrix. Pipeline A/B logic compiled via Numba JIT (zero native Python loops)
- **Trade Management:**
  - Stop Loss: structural, SL <= 50% of ATR
  - Take Profit: dynamic scaled exit (e.g., 33% of position at 2R)
- **Hyperparameter Sweep:** Optuna optimization over V, T, Z
- **Objective Function:** Sharpe or Sortino ratio (penalizing deep drawdowns)

### 5. Hybrid Model (Ensemble + ML)
- **Dataset Construction:**
  - Rows = all price breakout instants (regardless of A or B validation)
  - Features from Pipeline A: distance to last Volume Bar close, bar creation speed (ms)
  - Features from Pipeline B: current Vol Buzz Z-Score, price distance % vs AVWAP, recent ADR volatility
  - **Context features (from existing system):**
    - **RS vs benchmark (SPY/sector ETF)** — reuse from `signal_engine.py`
    - **health_score (0-7) from Dynamic Switch** — reuse from `market_health.py`
- **Target Variable:** Binary classification. `1` if max return in next N windows reaches > 2R without hitting 1R Stop Loss; `0` otherwise
- **Training:** LightGBM with Walk-Forward cross-validation (no temporal data leakage)
- **Output:** Predictive model (.pkl or .onnx) returning probability 0.0-1.0. Capital deployed if probability > confidence threshold (e.g., 0.75)

### 6. Execution Environment
All analytical pipeline, iterative memory transformations, and final result dumps must be invoked natively from a robust terminal environment (PowerShell Core) pointing directly to the local filesystem, giving CPU unrestricted direct access to RAM. No virtualization bottlenecks.

---

## Acceptance Criteria
- [ ] `src/microstructure/` module created with all 6 submodules
- [ ] DuckDB ingestion loads tick CSV/Parquet lazily without exceeding 2GB RAM for 10M+ row files
- [ ] Volume Bars correctly aggregate to configurable V thresholds with OHLC output
- [ ] Time Bars resample at configurable T intervals with Vol Buzz and AVWAP computation
- [ ] Signal_A and Signal_B produce boolean matrices matching spec logic
- [ ] Numba kernels compile and execute backtesting without Python for-loops
- [ ] Optuna sweep runs over V, T, Z parameter space with Sharpe/Sortino objective
- [ ] LightGBM model trains with walk-forward CV, includes RS + health_score features
- [ ] Model inference returns probability [0.0, 1.0] and respects confidence threshold
- [ ] `pytest tests/test_microstructure/` passes at 100%
- [ ] Existing baseline unaffected: Return >= 96%, MDD <= -36%
- [ ] No regressions in `pytest` full suite


## Context
URL: https://github.com/mmarcoschambi/swing-momentum-v1/issues/69
Labels: feat
