--python3 optimize_3tier.py --start 2022-01-01 --end 2024-12-31 --trials 300 --tickers 76  --use-pit-universe
rvivorship bias protection)...
2026-02-26 14:07:38,738 - INFO - PointInTimeUniverse: loaded 1230 ticker membership records
2026-02-26 14:07:38,808 - INFO - Tradeable mask: 376,609/418,564 cells (90.0%) across 538 S&P 500 + 0 non-S&P tickers, 778 trading days
2026-02-26 14:07:38,830 - INFO -    🛡️  Masked out 41,955 cells (10.0%) as non-tradeable (pre-IPO, post-delist, not in S&P 500)
2026-02-26 14:07:38,852 - WARNING -    ⚠️ No precomputed metrics found in cache, will calculate on the fly
2026-02-26 14:07:39,567 - INFO -    ⚠️ Precomputed metrics not available, calculating on the fly...
2026-02-26 14:07:39,602 - INFO -    ⚠️ SMA50 missing in cache, calculating on the fly...
2026-02-26 14:07:40,914 - INFO -    Loading SPY and VIX data for Market Regime...
2026-02-26 14:07:40,914 - INFO - 📊 Loading SPY and VIX data (2021-01-01 to 2024-02-06)...
2026-02-26 14:07:40,917 - INFO -    ✅ SPY loaded from cache: 778 bars
2026-02-26 14:07:40,920 - INFO -    ✅ VIX loaded from cache: 778 bars
2026-02-26 14:07:40,920 - INFO -    ✅ Market data loaded successfully
2026-02-26 14:07:40,927 - INFO -    ✅ Market Data Loaded & Aligned
2026-02-26 14:07:40,927 - INFO - ✅ Loaded: 538 tickers
2026-02-26 14:07:40,927 - INFO -    Date range: 2021-01-04 to 2024-02-06 (778 days)
2026-02-26 14:07:40,927 - INFO -    🔧 Truncating data to start_date: 2022-01-01
2026-02-26 14:07:41,150 - INFO - Memory: ~15.2 MB total after float32 conversion
2026-02-26 14:07:41,193 - INFO - 🔍 Calculating entry signals...
2026-02-26 14:07:41,195 - INFO -    🎯 Using TREND signal (close > SMA20)
2026-02-26 14:07:41,196 - INFO -    📊 ADVANCED MODE entries (before Adaptive Filter): 133000
2026-02-26 14:07:41,197 - INFO -       Base entry passed: 133000
2026-02-26 14:07:41,221 - INFO - 🛡️  PIT Universe filter: blocked 0 entries on non-member dates (133000 remaining)
2026-02-26 14:07:41,239 - INFO - 🔧 Applying Adaptive Filter Engine (TIER 1-2-3) - OPTIMIZADO...
2026-02-26 14:07:41,239 - INFO - 🔧 AdaptiveFilterEngine initialized
   ⚡ Applying Adaptive Filter: 100%|████| 526/526 [00:01<00:00, 283.08day/s]
2026-02-26 14:07:43,099 - INFO -    📊 Entries antes de Adaptive Filter: 133000
2026-02-26 14:07:43,099 - INFO -    ❌ Entries rechazadas por TIER:
2026-02-26 14:07:43,100 - INFO -       TIER 1 (Market Safety): 37907
2026-02-26 14:07:43,100 - INFO -       TIER 2 (Dynamic Quality): 38906
2026-02-26 14:07:43,100 - INFO -       TIER 3 (Optional): 84
2026-02-26 14:07:43,100 - INFO -    ✅ Entries finales: 56103

======================================================================
📊 ADAPTIVE FILTER ENGINE - RESUMEN (OPTIMIZADO)
======================================================================
  Total de Rechazos: 76897
  • TIER 1 (Market Safety): 37907
  • TIER 2 (Dynamic Quality): 38906
  TIER 3 (Optional): 84
======================================================================
2026-02-26 14:07:43,218 - INFO - 🔍 Clasificando riesgo por RVOL (VolTrig)...
2026-02-26 14:07:43,222 - INFO -    ☔ Danger (RVOL>=3.0x): 206 entries → Size 50%
2026-02-26 14:07:43,223 - INFO -    ⚠️  Warning (RVOL>=2.0x): 1204 entries → Size 75%
2026-02-26 14:07:43,223 - INFO -    ✅ Safe (RVOL<2.0x): 54693 entries → Size 100%
2026-02-26 14:07:43,223 - INFO - 🔍 Clasificando riesgo por ADR (volatilidad)...
2026-02-26 14:07:43,294 - INFO -    🔥 High ADR (>6.0%): 155 entries → Size 25%
2026-02-26 14:07:43,295 - INFO -    ⚠️  Med ADR (>5.0%): 331 entries → Size 33%
2026-02-26 14:07:43,335 - INFO - 📊 Multi-chunk mode: 526 days → 2 chunks of ~500 days
2026-02-26 14:07:43,335 - INFO - 🔄 Running multi-chunk backtest: 2 chunks...
2026-02-26 14:07:43,340 - INFO -    📦 Chunk 1/2: days 0-263 (capital: $100,000)
2026-02-26 14:07:43,345 - INFO - 🔄 Running single-chunk backtest with Numba Core...
2026-02-26 14:07:43,346 - INFO - 🔄 Converting DataFrames to NumPy arrays (float32 optimization)...
2026-02-26 14:07:43,382 - INFO -    ✅ Arrays prepared: 7.0 MB total
2026-02-26 14:07:43,382 - INFO -    📊 Array shapes: close=(263, 538), high=(263, 538)
2026-02-26 14:07:43,382 - INFO - ⚡ Ejecutando simulación ultra-rápida (Numba Core)...
2026-02-26 14:07:43,382 - INFO -    🚀 Using pre-calculated NumPy arrays (memory optimized - float32)
2026-02-26 14:07:43,389 - INFO -    💰 Numba Core usando FIXED DOLLAR RISK: $1000 → risk_pct=0.0100
2026-02-26 14:07:43,389 - INFO - 🔧 NUMBA CORE PARAMETERS:
2026-02-26 14:07:43,389 - INFO -    Initial Capital: $100,000.00
2026-02-26 14:07:43,389 - INFO -    Risk per Trade: $1,000.00
2026-02-26 14:07:43,389 - INFO -    Use Fixed Risk: True
2026-02-26 14:07:43,389 - INFO -    TP1/TP2 Targets: 1.5837873676730527R / 3.0591361868855493R
2026-02-26 14:07:43,389 - INFO -    TP Distribution: 45% / 30% / 25%
2026-02-26 14:07:43,389 - INFO -    Max Stop %%: 8.0% (decimal: 0.08)
2026-02-26 14:07:43,389 - INFO -    Trailing Stop: False
2026-02-26 14:07:43,389 - INFO -    ATR Stop Mode: False
2026-02-26 14:07:43,390 - INFO -    Total Entries Signals: 21669
2026-02-26 14:07:43,391 - INFO - 🚀 Numba Simulation Time: 0.0012s
2026-02-26 14:07:43,391 - INFO - 📊 Numba Core Results:
2026-02-26 14:07:43,392 - INFO -    Entry signals found: 21669
2026-02-26 14:07:43,392 - INFO -    Trades executed: 37
2026-02-26 14:07:43,392 - INFO -    Conversion rate: 0.2%
2026-02-26 14:07:43,392 - INFO -    Final equity: $94,015.11
2026-02-26 14:07:43,392 - WARNING -    ⚠️ Low conversion rate (0.2%) - Check parameters
2026-02-26 14:07:43,392 - WARNING -    May indicate: Restrictive filters, large stop distances, or insufficient capital
2026-02-26 14:07:43,392 - INFO -    Exit distribution: STOP=18, TP1=11, TP2=4, RUNNER=4
2026-02-26 14:07:43,853 - INFO -    ✅ Chunk 1 complete: 37 trades, final equity $94,015
2026-02-26 14:07:44,306 - INFO -    📦 Chunk 2/2: days 263-526 (capital: $94,015)
2026-02-26 14:07:44,310 - INFO - 🔄 Running single-chunk backtest with Numba Core...
2026-02-26 14:07:44,311 - INFO - 🔄 Converting DataFrames to NumPy arrays (float32 optimization)...
2026-02-26 14:07:44,348 - INFO -    ✅ Arrays prepared: 7.0 MB total
2026-02-26 14:07:44,348 - INFO -    📊 Array shapes: close=(263, 538), high=(263, 538)
2026-02-26 14:07:44,349 - INFO - ⚡ Ejecutando simulación ultra-rápida (Numba Core)...
2026-02-26 14:07:44,349 - INFO -    🚀 Using pre-calculated NumPy arrays (memory optimized - float32)
2026-02-26 14:07:44,355 - INFO -    💰 Numba Core usando FIXED DOLLAR RISK: $1000 → risk_pct=0.0106
2026-02-26 14:07:44,355 - INFO - 🔧 NUMBA CORE PARAMETERS:
2026-02-26 14:07:44,355 - INFO -    Initial Capital: $94,015.11
2026-02-26 14:07:44,355 - INFO -    Risk per Trade: $1,000.00
2026-02-26 14:07:44,356 - INFO -    Use Fixed Risk: True
2026-02-26 14:07:44,356 - INFO -    TP1/TP2 Targets: 1.5837873676730527R / 3.0591361868855493R
2026-02-26 14:07:44,356 - INFO -    TP Distribution: 45% / 30% / 25%
2026-02-26 14:07:44,356 - INFO -    Max Stop %%: 8.0% (decimal: 0.08)
2026-02-26 14:07:44,356 - INFO -    Trailing Stop: False
2026-02-26 14:07:44,356 - INFO -    ATR Stop Mode: False
2026-02-26 14:07:44,356 - INFO -    Total Entries Signals: 34434
2026-02-26 14:07:44,357 - INFO - 🚀 Numba Simulation Time: 0.0011s
2026-02-26 14:07:44,358 - INFO - 📊 Numba Core Results:
2026-02-26 14:07:44,358 - INFO -    Entry signals found: 34434
2026-02-26 14:07:44,358 - INFO -    Trades executed: 49
2026-02-26 14:07:44,358 - INFO -    Conversion rate: 0.1%
2026-02-26 14:07:44,358 - INFO -    Final equity: $104,407.29
2026-02-26 14:07:44,358 - WARNING -    ⚠️ Low conversion rate (0.1%) - Check parameters
2026-02-26 14:07:44,358 - WARNING -    May indicate: Restrictive filters, large stop distances, or insufficient capital
2026-02-26 14:07:44,358 - INFO -    Exit distribution: STOP=20, TP1=16, TP2=9, RUNNER=4
2026-02-26 14:07:44,822 - INFO -    ✅ Chunk 2 complete: 49 trades, final equity $104,407
2026-02-26 14:07:45,276 - INFO - ✅ Multi-chunk backtest complete: 86 total trades
2026-02-26 14:07:45,279 - INFO - ✅ Backtest complete!
2026-02-26 14:07:45,280 - INFO -    Return: 4.41%
2026-02-26 14:07:45,280 - INFO -    Annualized Return: 2.09%
2026-02-26 14:07:45,280 - INFO -    Sharpe: 0.22
2026-02-26 14:07:45,280 - INFO -    Max DD: -19.20%
2026-02-26 14:07:45,280 - INFO -    MAR Ratio: 0.11
2026-02-26 14:07:45,280 - INFO -    Calmar Ratio: 0.11
2026-02-26 14:07:45,280 - INFO -    Win Rate: 54.7%
2026-02-26 14:07:45,280 - INFO -    Trades: 56103 entries → 86 total exits (including partial)
2026-02-26 14:07:45,287 - INFO - ============================================================
2026-02-26 14:07:45,288 - INFO - 🚀 MODE: PRODUCTION (Fixed Dollar Risk)
2026-02-26 14:07:45,288 - INFO -    • Risk: FIXED DOLLAR ($1000)
2026-02-26 14:07:45,288 - INFO -    • Compounding: DISABLED
2026-02-26 14:07:45,288 - INFO - ============================================================
2026-02-26 14:07:45,289 - INFO - 🚀 Advanced VectorBT Engine initialized
2026-02-26 14:07:45,290 - INFO - 📅 Period: 2022-01-01 to 2024-02-06
2026-02-26 14:07:45,290 - INFO - 🎯 Universe: 566 tickers
2026-02-26 14:07:45,290 - INFO - 🎛️  Liquidity: vol≥100k, $vol≥$98M, ADR≥1.625364855660093%, RVOL≥0.6325630936066489x
2026-02-26 14:07:45,290 - INFO - 🎛️  Position Size: RVOL Danger≥3.0x→50%, Warning≥2.0x→75%
2026-02-26 14:07:45,290 - INFO - ============================================================
2026-02-26 14:07:45,290 - INFO - 🌍 MARKET REGIME FILTER ENABLED
2026-02-26 14:07:45,290 - INFO - ============================================================
2026-02-26 14:07:45,290 - INFO - 📊 Loading SPY and VIX data (2022-01-01 to 2024-02-06)...
2026-02-26 14:07:45,292 - INFO -    ✅ SPY loaded from cache: 526 bars
2026-02-26 14:07:45,294 - INFO -    ✅ VIX loaded from cache: 526 bars
2026-02-26 14:07:45,295 - INFO -    ✅ Market data loaded successfully
2026-02-26 14:07:45,300 - INFO -    ✅ Market regime classifier initialized
2026-02-26 14:07:45,300 - INFO -    🚫 Block Stage 3: True
2026-02-26 14:07:45,300 - INFO -    🚫 Block Stage 4: True
2026-02-26 14:07:45,300 - INFO -    📊 Adjust risk by regime: True
2026-02-26 14:07:45,318 - INFO - 📥 Loading data from 2021-01-01 (buffer) to 2024-02-06...
2026-02-26 14:07:45,318 - INFO - 🎯 Universe size: 566 tickers
2026-02-26 14:07:45,318 - INFO - 🛡️  Survivorship bias protection: PIT mask will determine eligibility quarterly
2026-02-26 14:07:45,318 - INFO - ⚡ Fetching data for 566 tickers in parallel...
2026-02-26 14:07:45,616 - WARNING - ❌ SKIP AMTM: None returned
2026-02-26 14:07:45,620 - WARNING - ❌ SKIP ANSS: None returned
2026-02-26 14:07:45,907 - WARNING - ❌ SKIP ATVI: None returned
2026-02-26 14:07:46,104 - INFO -    100/566...
2026-02-26 14:07:46,215 - WARNING - ❌ SKIP CDAY: None returned
2026-02-26 14:07:46,454 - WARNING - ❌ SKIP CTXS: None returned
2026-02-26 14:07:46,762 - INFO -    200/566...
2026-02-26 14:07:46,767 - WARNING - ❌ SKIP DRE: None returned
2026-02-26 14:07:46,813 - WARNING - ❌ SKIP FB: None returned
2026-02-26 14:07:46,815 - WARNING - ❌ SKIP FBHS: None returned
2026-02-26 14:07:46,821 - WARNING - ❌ SKIP FI: None returned
2026-02-26 14:07:46,832 - WARNING - ❌ SKIP FLT: None returned
2026-02-26 14:07:47,460 - INFO -    300/566...
2026-02-26 14:07:49,039 - INFO -    400/566...
2026-02-26 14:07:49,767 - INFO -    500/566...
2026-02-26 14:07:50,218 - WARNING - ⚠️  Skipped 28 tickers (insufficient data)
2026-02-26 14:07:50,219 - INFO -    First 10 failed: ['AMTM (None returned)', 'ANSS (None returned)', 'ATVI (None returned)', 'CDAY (None returned)', 'CTXS (None returned)', 'DRE (None returned)', 'FB (None returned)', 'FBHS (None returned)', 'FI (None returned)', 'FLT (None returned)']
2026-02-26 14:07:50,219 - INFO - ℹ️  538 tickers with partial data (gaps in history)
2026-02-26 14:07:50,451 - INFO - Memory: 6.4 MB for 538 tickers (core DataFrames)
2026-02-26 14:07:50,451 - INFO - 🛡️  Building Point-in-Time tradeable mask (survivorship bias protection)...
2026-02-26 14:07:50,507 - INFO - PointInTimeUniverse: loaded 1230 ticker membership records
2026-02-26 14:07:50,577 - INFO - Tradeable mask: 376,609/418,564 cells (90.0%) across 538 S&P 500 + 0 non-S&P tickers, 778 trading days
2026-02-26 14:07:50,598 - INFO -    🛡️  Masked out 41,955 cells (10.0%) as non-tradeable (pre-IPO, post-delist, not in S&P 500)
2026-02-26 14:07:50,613 - WARNING -    ⚠️ No precomputed metrics found in cache, will calculate on the fly
2026-02-26 14:07:51,228 - INFO -    ⚠️ Precomputed metrics not available, calculating on the fly...
2026-02-26 14:07:51,262 - INFO -    ⚠️ SMA50 missing in cache, calculating on the fly...
2026-02-26 14:07:52,139 - INFO -    Loading SPY and VIX data for Market Regime...
2026-02-26 14:07:52,139 - INFO - 📊 Loading SPY and VIX data (2021-01-01 to 2024-02-06)...
2026-02-26 14:07:52,142 - INFO -    ✅ SPY loaded from cache: 778 bars
2026-02-26 14:07:52,145 - INFO -    ✅ VIX loaded from cache: 778 bars
2026-02-26 14:07:52,146 - INFO -    ✅ Market data loaded successfully
2026-02-26 14:07:52,153 - INFO -    ✅ Market Data Loaded & Aligned
2026-02-26 14:07:52,154 - INFO - ✅ Loaded: 538 tickers
2026-02-26 14:07:52,154 - INFO - 🛡️  Filtered out 28 tickers (insufficient data)
2026-02-26 14:07:52,154 - INFO -    Date range: 2021-01-04 to 2024-02-06 (778 days)
2026-02-26 14:07:52,154 - INFO -    🔧 Truncating data to start_date: 2022-01-01
2026-02-26 14:07:52,368 - INFO - Memory: ~15.2 MB total after float32 conversion
2026-02-26 14:07:52,386 - INFO - 🎯 Starting advanced backtest with partial exits...
2026-02-26 14:07:52,387 - INFO - 📥 Loading data from 2021-01-01 (buffer) to 2024-02-06...
2026-02-26 14:07:52,387 - INFO - 🎯 Universe size: 538 tickers
2026-02-26 14:07:52,387 - INFO - 🛡️  Survivorship bias protection: PIT mask will determine eligibility quarterly
2026-02-26 14:07:52,388 - INFO - ⚡ Fetching data for 538 tickers in parallel...
2026-02-26 14:07:53,179 - INFO -    100/538...
2026-02-26 14:07:53,835 - INFO -    200/538...
2026-02-26 14:07:54,471 - INFO -    300/538...
2026-02-26 14:07:55,265 - INFO -    400/538...
2026-02-26 14:07:56,001 - INFO -    500/538...
2026-02-26 14:07:56,258 - INFO - ℹ️  538 tickers with partial data (gaps in history)
2026-02-26 14:07:56,483 - INFO - Memory: 6.4 MB for 538 tickers (core DataFrames)
2026-02-26 14:07:56,484 - INFO - 🛡️  Building Point-in-Time tradeable mask (survivorship bias protection)...
2026-02-26 14:07:56,535 - INFO - PointInTimeUniverse: loaded 1230 ticker membership records
2026-02-26 14:07:56,606 - INFO - Tradeable mask: 376,609/418,564 cells (90.0%) across 538 S&P 500 + 0 non-S&P tickers, 778 trading days
2026-02-26 14:07:56,626 - INFO -    🛡️  Masked out 41,955 cells (10.0%) as non-tradeable (pre-IPO, post-delist, not in S&P 500)
2026-02-26 14:07:56,646 - WARNING -    ⚠️ No precomputed metrics found in cache, will calculate on the fly
2026-02-26 14:07:57,231 - INFO -    ⚠️ Precomputed metrics not available, calculating on the fly...
2026-02-26 14:07:57,263 - INFO -    ⚠️ SMA50 missing in cache, calculating on the fly...
2026-02-26 14:07:58,507 - INFO -    Loading SPY and VIX data for Market Regime...
2026-02-26 14:07:58,507 - INFO - 📊 Loading SPY and VIX data (2021-01-01 to 2024-02-06)...
2026-02-26 14:07:58,509 - INFO -    ✅ SPY loaded from cache: 778 bars
2026-02-26 14:07:58,513 - INFO -    ✅ VIX loaded from cache: 778 bars
2026-02-26 14:07:58,513 - INFO -    ✅ Market data loaded successfully
2026-02-26 14:07:58,520 - INFO -    ✅ Market Data Loaded & Aligned
2026-02-26 14:07:58,520 - INFO - ✅ Loaded: 538 tickers
2026-02-26 14:07:58,521 - INFO -    Date range: 2021-01-04 to 2024-02-06 (778 days)
2026-02-26 14:07:58,521 - INFO -    🔧 Truncating data to start_date: 2022-01-01
2026-02-26 14:07:58,727 - INFO - Memory: ~15.2 MB total after float32 conversion
2026-02-26 14:07:58,778 - INFO - 🔍 Calculating entry signals...
2026-02-26 14:07:58,782 - INFO -    🎯 Using TREND signal (close > SMA20)
2026-02-26 14:07:58,783 - INFO -    📊 ADVANCED MODE entries (before Adaptive Filter): 133000
2026-02-26 14:07:58,784 - INFO -       Base entry pass3000
2026-02-26 14:07:58,812 - INFO - 🛡️  PIT Universe filter: blocked 0 entries on non-member dates (133000 remaining)
2026-02-26 14:07:58,827 - INFO - 🔧 Applying Adaptive Filter Engine (TIER 1-2-3) - OPTIMIZADO...
2026-02-26 14:07:58,827 - INFO - 🔧 AdaptiveFilterEngine initialized
   ⚡ Applying Adaptive Filter: 100%|████| 526/526 [00:01<00:00, 291.01day/s]
2026-02-26 14:08:00,636 - INFO -    📊 Entries antes de Adaptive Filter: 133000
2026-02-26 14:08:00,636 - INFO -    ❌ Entries rechazadas por TIER:
2026-02-26 14:08:00,636 - INFO -       TIER 1 (Market Safety): 37907
2026-02-26 14:08:00,636 - INFO -       TIER 2 (Dynamic Quality): 34470
2026-02-26 14:08:00,637 - INFO -       TIER 3 (Optional): 90
2026-02-26 14:08:00,637 - INFO -    ✅ Entries finales: 60533

======================================================================
📊 ADAPTIVE FILTER ENGINE - RESUMEN (OPTIMIZADO)
======================================================================
  Total de Rechazos: 72467
  • TIER 1 (Market Safety): 37907
  • TIER 2 (Dynamic Quality): 34470
  TIER 3 (Optional): 90
======================================================================
2026-02-26 14:08:00,743 - INFO - 🔍 Clasificando riesgo por RVOL (VolTrig)...
2026-02-26 14:08:00,747 - INFO -    ☔ Danger (RVOL>=3.0x): 215 entries → Size 50%
2026-02-26 14:08:00,748 - INFO -    ⚠️  Warning (RVOL>=2.0x): 1255 entries → Size 75%
2026-02-26 14:08:00,748 - INFO -    ✅ Safe (RVOL<2.0x): 59063 entries → Size 100%
2026-02-26 14:08:00,748 - INFO - 🔍 Clasificando riesgo por ADR (volatilidad)...
2026-02-26 14:08:00,822 - INFO -    🔥 High ADR (>6.0%): 169 entries → Size 25%
2026-02-26 14:08:00,822 - INFO -    ⚠️  Med ADR (>5.0%): 364 entries → Size 33%
2026-02-26 14:08:00,860 - INFO - 📊 Multi-chunk mode: 526 days → 2 chunks of ~500 days
2026-02-26 14:08:00,861 - INFO - 🔄 Running multi-chunk backtest: 2 chunks...
2026-02-26 14:08:00,865 - INFO -    📦 Chunk 1/2: days 0-263 (capital: $100,000)
2026-02-26 14:08:00,871 - INFO - 🔄 Running single-chunk backtest with Numba Core...
2026-02-26 14:08:00,871 - INFO - 🔄 Converting DataFrames to NumPy arrays (float32 optimization)...
2026-02-26 14:08:00,908 - INFO -    ✅ Arrays prepared: 7.0 MB total
2026-02-26 14:08:00,908 - INFO -    📊 Array shapes: close=(263, 538), high=(263, 538)
2026-02-26 14:08:00,908 - INFO - ⚡ Ejecutando simulación ultra-rápida (Numba Core)...
2026-02-26 14:08:00,908 - INFO -    🚀 Using pre-calculated NumPy arrays (memory optimized - float32)
2026-02-26 14:08:00,914 - INFO -    💰 Numba Core usando FIXED DOLLAR RISK: $1000 → risk_pct=0.0100
2026-02-26 14:08:00,915 - INFO - 🔧 NUMBA CORE PARAMETERS:
2026-02-26 14:08:00,915 - INFO -    Initial Capital: $100,000.00
2026-02-26 14:08:00,915 - INFO -    Risk per Trade: $1,000.00
2026-02-26 14:08:00,915 - INFO -    Use Fixed Risk: True
2026-02-26 14:08:00,915 - INFO -    TP1/TP2 Targets: 1.8087227697292492R / 2.8985065141357405R
2026-02-26 14:08:00,915 - INFO -    TP Distribution: 45% / 30% / 25%
2026-02-26 14:08:00,915 - INFO -    Max Stop %%: 8.0% (decimal: 0.08)
2026-02-26 14:08:00,915 - INFO -    Trailing Stop: False
2026-02-26 14:08:00,915 - INFO -    ATR Stop Mode: False
2026-02-26 14:08:00,915 - INFO -    Total Entries Signals: 23278
2026-02-26 14:08:00,917 - INFO - 🚀 Numba Simulation Time: 0.0013s
2026-02-26 14:08:00,917 - INFO - 📊 Numba Core Results:
2026-02-26 14:08:00,917 - INFO -    Entry signals found: 23278
2026-02-26 14:08:00,917 - INFO -    Trades executed: 35
2026-02-26 14:08:00,917 - INFO -    Conversion rate: 0.2%
2026-02-26 14:08:00,917 - INFO -    Final equity: $92,927.91
2026-02-26 14:08:00,917 - WARNING -    ⚠️ Low conversion rate (0.2%) - Check parameters
2026-02-26 14:08:00,917 - WARNING -    May indicate: Restrictive filters, large stop distances, or insufficient capital
2026-02-26 14:08:00,918 - INFO -    Exit distribution: STOP=19, TP1=8, TP2=4, RUNNER=4
2026-02-26 14:08:01,377 - INFO -    ✅ Chunk 1 complete: 35 trades, final equity $92,928
2026-02-26 14:08:01,826 - INFO -    📦 Chunk 2/2: days 263-526 (capital: $92,928)
2026-02-26 14:08:01,832 - INFO - 🔄 Running single-chunk backtest with Numba Core...
2026-02-26 14:08:01,832 - INFO - 🔄 Converting DataFrames to NumPy arrays (float32 optimization)...
2026-02-26 14:08:01,869 - INFO -    ✅ Arrays prepared: 7.0 MB total
2026-02-26 14:08:01,869 - INFO -    📊 Array shapes: close=(263, 538), high=(263, 538)
2026-02-26 14:08:01,870 - INFO - ⚡ Ejecutando simulación ultra-rápida (Numba Core)...
2026-02-26 14:08:01,870 - INFO -    🚀 Using pre-calculated NumPy arrays (memory optimized - float32)
2026-02-26 14:08:01,876 - INFO -    💰 Numba Core usando FIXED DOLLAR RISK: $1000 → risk_pct=0.0108
2026-02-26 14:08:01,876 - INFO - 🔧 NUMBA CORE PARAMETERS:
2026-02-26 14:08:01,876 - INFO -    Initial Capital: $92,927.91
2026-02-26 14:08:01,876 - INFO -    Risk per Trade: $1,000.00
2026-02-26 14:08:01,876 - INFO -    Use Fixed Risk: True
2026-02-26 14:08:01,876 - INFO -    TP1/TP2 Targets: 1.8087227697292492R / 2.8985065141357405R
2026-02-26 14:08:01,876 - INFO -    TP Distribution: 45% / 30% / 25%
2026-02-26 14:08:01,876 - INFO -    Max Stop %%: 8.0% (decimal: 0.08)
2026-02-26 14:08:01,876 - INFO -    Trailing Stop: False
2026-02-26 14:08:01,876 - INFO -    ATR Stop Mode: False
2026-02-26 14:08:01,876 - INFO -    Total Entries Signals: 37255
2026-02-26 14:08:01,878 - INFO - 🚀 Numba Simulation Time: 0.0009s
2026-02-26 14:08:01,878 - INFO - 📊 Numba Core Results:
2026-02-26 14:08:01,878 - INFO -    Entry signals found: 37255
2026-02-26 14:08:01,878 - INFO -    Trades executed: 44
2026-02-26 14:08:01,878 - INFO -    Conversion rate: 0.1%
2026-02-26 14:08:01,878 - INFO -    Final equity: $104,561.56
2026-02-26 14:08:01,878 - WARNING -    ⚠️ Low conversion rate (0.1%) - Check parameters
2026-02-26 14:08:01,878 - WARNING -    May indicate: Restrictive filters, large stop distances, or insufficient capital
2026-02-26 14:08:01,878 - INFO -    Exit distribution: STOP=17, TP1=11, TP2=10, RUNNER=6
2026-02-26 14:08:02,340 - INFO -    ✅ Chunk 2 complete: 44 trades, final equity $104,562
2026-02-26 14:08:02,815 - INFO - ✅ Multi-chunk backtest complete: 79 total trades
2026-02-26 14:08:02,819 - INFO - ✅ Backtest complete!
2026-02-26 14:08:02,820 - INFO -    Return: 4.56%
2026-02-26 14:08:02,820 - INFO -    Annualized Return: 2.16%
2026-02-26 14:08:02,820 - INFO -    Sharpe: 0.22
2026-02-26 14:08:02,820 - INFO -    Max DD: -20.76%
2026-02-26 14:08:02,820 - INFO -    MAR Ratio: 0.10
2026-02-26 14:08:02,820 - INFO -    Calmar Ratio: 0.10
2026-02-26 14:08:02,820 - INFO -    Win Rate: 53.2%
2026-02-26 14:08:02,820 - INFO -    Trades: 60533 entries → 79 total exits (including partial)
2026-02-26 14:08:02,828 - INFO - ============================================================
2026-02-26 14:08:02,829 - INFO - 🚀 MODE: PRODUCTION (Fixed Dollar Risk)
2026-02-26 14:08:02,829 - INFO -    • Risk: FIXED DOLLAR ($1000)
2026-02-26 14:08:02,829 - INFO -    • Compounding: DISABLED
2026-02-26 14:08:02,829 - INFO - ============================================================
2026-02-26 14:08:02,830 - INFO - 🚀 Advanced VectorBT Engine initialized
2026-02-26 14:08:02,831 - INFO - 📅 Period: 2022-01-01 to 2024-02-06
2026-02-26 14:08:02,831 - INFO - 🎯 Universe: 566 tickers
2026-02-26 14:08:02,831 - INFO - 🎛️  Liquidity: vol≥100k, $vol≥$98M, ADR≥1.7008664659999222%, RVOL≥0.6618789458705968x
2026-02-26 14:08:02,831 - INFO - 🎛️  Position Size: RVOL Danger≥3.0x→50%, Warning≥2.0x→75%
2026-02-26 14:08:02,831 - INFO - ============================================================
2026-02-26 14:08:02,831 - INFO - 🌍 MARKET REGIME FILTER ENABLED
2026-02-26 14:08:02,831 - INFO - ============================================================
2026-02-26 14:08:02,831 - INFO - 📊 Loading SPY and VIX data (2022-01-01 to 2024-02-06)...
2026-02-26 14:08:02,834 - INFO -    ✅ SPY loaded from cache: 526 bars
2026-02-26 14:08:02,836 - INFO -    ✅ VIX loaded from cache: 526 bars
2026-02-26 14:08:02,837 - INFO -    ✅ Market data loaded successfully
2026-02-26 14:08:02,843 - INFO -    ✅ Market regime classifier initialized
2026-02-26 14:08:02,843 - INFO -    🚫 Block Stage 3: True
2026-02-26 14:08:02,843 - INFO -    🚫 Block Stage 4: True
2026-02-26 14:08:02,843 - INFO -    📊 Adjust risk by regime: True
2026-02-26 14:08:02,859 - INFO - 📥 Loading data from 2021-01-01 (buffer) to 2024-02-06...
2026-02-26 14:08:02,859 - INFO - 🎯 Universe size: 566 tickers
2026-02-26 14:08:02,859 - INFO - 🛡️  Survivorship bias protection: PIT mask will determine eligibility quarterly
2026-02-26 14:08:02,859 - INFO - ⚡ Fetching data for 566 tickers in parallel...
2026-02-26 14:08:03,171 - WARNING - ❌ SKIP AMTM: None returned
2026-02-26 14:08:03,172 - WARNING - ❌ SKIP ANSS: None returned
2026-02-26 14:08:03,431 - WARNING - ❌ SKIP ATVI: None returned
2026-02-26 14:08:03,620 - INFO -    100/566...
2026-02-26 14:08:03,750 - WARNING - ❌ SKIP CDAY: None returned
2026-02-26 14:08:03,963 - WARNING - ❌ SKIP CTXS: None returned
2026-02-26 14:08:04,253 - INFO -    200/566...
2026-02-26 14:08:04,264 - WARNING - ❌ SKIP DRE: None returned
2026-02-26 14:08:04,305 - WARNING - ❌ SKIP FB: None returned
2026-02-26 14:08:04,306 - WARNING - ❌ SKIP FBHS: None returned
2026-02-26 14:08:04,310 - WARNING - ❌ SKIP FI: None returned
2026-02-26 14:08:04,320 - WARNING - ❌ SKIP FISV: None returned
2026-02-26 14:08:04,946 - INFO -    300/566...
2026-02-26 14:08:05,724 - INFO -    400/566...
2026-02-26 14:08:06,442 - INFO -    500/566...
2026-02-26 14:08:06,910 - WARNING - ⚠️  Skipped 28 tickers (insufficient data)
2026-02-26 14:08:06,910 - INFO -    First 10 failed: ['AMTM (None returned)', 'ANSS (None returned)', 'ATVI (None returned)', 'CDAY (None returned)', 'CTXS (None returned)', 'DRE (None returned)', 'FB (None returned)', 'FBHS (None returned)', 'FI (None returned)', 'FISV (None returned)']
2026-02-26 14:08:06,910 - INFO - ℹ️  538 tickers with partial data (gaps in history)
2026-02-26 14:08:07,140 - INFO - Memory: 6.4 MB for 538 tickers (core DataFrames)
2026-02-26 14:08:07,141 - INFO - 🛡️  Building Point-in-Time tradeable mask (survivorship bias protection)...
2026-02-26 14:08:07,194 - INFO - PointInTimeUniverse: loaded 1230 ticker membership records
2026-02-26 14:08:07,264 - INFO - Tradeable mask: 376,609/418,564 cells (90.0%) across 538 S&P 500 + 0 non-S&P tickers, 778 trading days
2026-02-26 14:08:07,284 - INFO -    🛡️  Masked out 41,955 cells (10.0%) as non-tradeable (pre-IPO, post-delist, not in S&P 500)
2026-02-26 14:08:07,301 - WARNING -    ⚠️ No precomputed metrics found in cache, will calculate on the fly
2026-02-26 14:08:07,919 - INFO -    ⚠️ Precomputed metrics not available, calculating on the fly...
2026-02-26 14:08:07,953 - INFO -    ⚠️ SMA50 missing in cache, calculating on the fly...
2026-02-26 14:08:08,820 - INFO -    Loading SPY and VIX data for Market Regime...
2026-02-26 14:08:08,820 - INFO - 📊 Loading SPY and VIX data (2021-01-01 to 2024-02-06)...
2026-02-26 14:08:08,823 - INFO -    ✅ SPY loaded from cache: 778 bars
2026-02-26 14:08:08,826 - INFO -    ✅ VIX loaded from cache: 778 bars
2026-02-26 14:08:08,826 - INFO -    ✅ Market data loaded successfully
2026-02-26 14:08:08,833 - INFO -    ✅ Market Data Loaded & Aligned
2026-02-26 14:08:08,833 - INFO - ✅ Loaded: 538 tickers
2026-02-26 14:08:08,834 - INFO - 🛡️  Filtered out 28 tickers (insufficient data)
2026-02-26 14:08:08,834 - INFO -    Date range: 2021-01-04 to 2024-02-06 (778 days)
2026-02-26 14:08:08,834 - INFO -    🔧 Truncating data to start_date: 2022-01-01
2026-02-26 14:08:09,050 - INFO - Memory: ~15.2 MB total after float32 conversion
2026-02-26 14:08:09,068 - INFO - 🎯 Starting advanced backtest with partial exits...
2026-02-26 14:08:09,069 - INFO - 📥 Loading data from 2021-01-01 (buffer) to 2024-02-06...
2026-02-26 14:08:09,069 - INFO - 🎯 Universe size: 538 tickers
2026-02-26 14:08:09,070 - INFO - 🛡️  Survivorship bias protection: PIT mask will determine eligibility quarterly
2026-02-26 14:08:09,070 - INFO - ⚡ Fetching data for 538 tickers in parallel...
2026-02-26 14:08:09,900 - INFO -    100/538...
2026-02-26 14:08:10,575 - INFO -    200/538...
2026-02-26 14:08:11,241 - INFO -    300/538...
2026-02-26 14:08:11,984 - INFO -    400/538...
2026-02-26 14:08:12,722 - INFO -    500/538...
2026-02-26 14:08:13,002 - INFO - ℹ️  538 tickers with partial data (gaps in history)
2026-02-26 14:08:13,239 - INFO - Memory: 6.4 MB for 538 tickers (core DataFrames)
2026-02-26 14:08:13,239 - INFO - 🛡️  Building Point-in-Time tradeable mask (survivorship bias protection)...
2026-02-26 14:08:13,296 - INFO - PointInTimeUniverse: loaded 1230 ticker membership records
2026-02-26 14:08:13,371 - INFO - Tradeable mask: 376,609/418,564 cells (90.0%) across 538 S&P 500 + 0 non-S&P tickers, 778 trading days
2026-02-26 14:08:13,392 - INFO -    🛡️  Masked out 41,955 cells (10.0%) as non-tradeable (pre-IPO, post-delist, not in S&P 500)
2026-02-26 14:08:13,412 - WARNING -    ⚠️ No precomputed metrics found in cache, will calculate on the fly
2026-02-26 14:08:14,036 - INFO -    ⚠️ Precomputed metrics not available, calculating on the fly...
2026-02-26 14:08:14,069 - INFO -    ⚠️ SMA50 missing in cache, calculating on the fly...
2026-02-26 14:08:15,389 - INFO -    Loading SPY and VIX data for Market Regime...
2026-02-26 14:08:15,389 - INFO - 📊 Loading SPY and VIX data (2021-01-01 to 2024-02-06)...
2026-02-26 14:08:15,391 - INFO -    ✅ SPY loaded from cache: 778 bars
2026-02-26 14:08:15,394 - INFO -    ✅ VIX loaded from cache: 778 bars
2026-02-26 14:08:15,394 - INFO -    ✅ Market data loaded successfully
2026-02-26 14:08:15,402 - INFO -    ✅ Market Data Loaded & Aligned
2026-02-26 14:08:15,403 - INFO - ✅ Loaded: 538 tickers
2026-02-26 14:08:15,403 - INFO -    Date range: 2021-01-04 to 2024-02-06 (778 days)
2026-02-26 14:08:15,403 - INFO -    🔧 Truncating data to start_date: 2022-01-01
2026-02-26 14:08:15,619 - INFO - Memory: ~15.2 MB total after float32 conversion
2026-02-26 14:08:15,660 - INFO - 🔍 Calculating entry signals...
2026-02-26 14:08:15,663 - INFO -    🎯 Using TREND signal (close > SMA20)
2026-02-26 14:08:15,664 - INFO -    📊 ADVANCED MODE entries (before Adaptive Filter): 133000
2026-02-26 14:08:15,665 - INFO -       Base entry passed: 133000
2026-02-26 14:08:15,689 - INFO - 🛡️  PIT Universe filter: blocked 0 entries on non-member dates (133000 remaining)
2026-02-26 14:08:15,705 - INFO - 🔧 Applying Adaptive Filter Engine (TIER 1-2-3) - OPTIMIZADO...
2026-02-26 14:08:15,706 - INFO - 🔧 AdaptiveFilterEngine initialized
   ⚡ Applying Adaptive Filter: 100%|████| 526/526 [00:01<00:00, 279.02day/s]
2026-02-26 14:08:17,592 - INFO -    📊 Entries antes de Adaptive Filter: 133000
2026-02-26 14:08:17,593 - INFO -    ❌ Entries rechazadas por TIER:
2026-02-26 14:08:17,593 - INFO -       TIER 1 (Market Safety): 37907
2026-02-26 14:08:17,593 - INFO -       TIER 2 (Dynamic Quality): 42523
2026-02-26 14:08:17,593 - INFO -       TIER 3 (Optional): 82
2026-02-26 14:08:17,593 - INFO -    ✅ Entries finales: 52488

======================================================================
📊 ADAPTIVE FILTER ENGINE - RESUMEN (OPTIMIZADO)
======================================================================
  Total de Rechazos: 80512
  • TIER 1 (Market Safety): 37907
  • TIER 2 (Dynamic Quality): 42523
  TIER 3 (Optional): 82
======================================================================
2026-02-26 14:08:17,720 - INFO - 🔍 Clasificando riesgo por RVOL (VolTrig)...
2026-02-26 14:08:17,725 - INFO -    ☔ Danger (RVOL>=3.0x): 192 entries → Size 50%
2026-02-26 14:08:17,725 - INFO -    ⚠️  Warning (RVOL>=2.0x): 1110 entries → Size 75%
2026-02-26 14:08:17,726 - INFO -    ✅ Safe (RVOL<2.0x): 51186 entries → Size 100%
2026-02-26 14:08:17,726 - INFO - 🔍 Clasificando riesgo por ADR (volatilidad)...
2026-02-26 14:08:17,799 - INFO -    🔥 High ADR (>6.0%): 147 entries → Size 25%
2026-02-26 14:08:17,799 - INFO -    ⚠️  Med ADR (>5.0%): 316 entries → Size 33%
2026-02-26 14:08:17,838 - INFO - 📊 Multi-chunk mode: 526 days → 2 chunks of ~500 days
2026-02-26 14:08:17,838 - INFO - 🔄 Running multi-chunk backtest: 2 chunks...
2026-02-26 14:08:17,843 - INFO -    📦 Chunk 1/2: days 0-263 (capital: $100,000)
2026-02-26 14:08:17,849 - INFO - 🔄 Running single-chunk backtest with Numba Core...
2026-02-26 14:08:17,849 - INFO - 🔄 Converting DataFrames to NumPy arrays (float32 optimization)...
2026-02-26 14:08:17,885 - INFO -    ✅ Arrays prepared: 7.0 MB total
2026-02-26 14:08:17,885 - INFO -    📊 Array shapes: close=(263, 538), high=(263, 538)
2026-02-26 14:08:17,885 - INFO - ⚡ Ejecutando simulación ultra-rápida (Numba Core)...
2026-02-26 14:08:17,885 - INFO -    🚀 Using pre-calculated NumPy arrays (memory optimized - float32)
2026-02-26 14:08:17,890 - INFO -    💰 Numba Core usando FIXED DOLLAR RISK: $1000 → risk_pct=0.0100
2026-02-26 14:08:17,891 - INFO - 🔧 NUMBA CORE PARAMETERS:
2026-02-26 14:08:17,891 - INFO -    Initial Capital: $100,000.00
2026-02-26 14:08:17,891 - INFO -    Risk per Trade: $1,000.00
2026-02-26 14:08:17,891 - INFO -    Use Fixed Risk: True
2026-02-26 14:08:17,891 - INFO -    TP1/TP2 Targets: 1.8997173797313318R / 2.9571819376044006R
2026-02-26 14:08:17,891 - INFO -    TP Distribution: 45% / 30% / 25%
2026-02-26 14:08:17,891 - INFO -    Max Stop %%: 8.0% (decimal: 0.08)
2026-02-26 14:08:17,891 - INFO -    Trailing Stop: False
2026-02-26 14:08:17,891 - INFO -    ATR Stop Mode: False
2026-02-26 14:08:17,892 - INFO -    Total Entries Signals: 20552
2026-02-26 14:08:17,893 - INFO - 🚀 Numba Simulation Time: 0.0014s
2026-02-26 14:08:17,894 - INFO - 📊 Numba Core Results:
2026-02-26 14:08:17,894 - INFO -    Entry signals found: 20552
2026-02-26 14:08:17,894 - INFO -    Trades executed: 35
2026-02-26 14:08:17,894 - INFO -    Conversion rate: 0.2%
2026-02-26 14:08:17,894 - INFO -    Final equity: $90,700.00
2026-02-26 14:08:17,894 - WARNING -    ⚠️ Low conversion rate (0.2%) - Check parameters
2026-02-26 14:08:17,894 - WARNING -    May indicate: Restrictive filters, large stop distances, or insufficient capital
2026-02-26 14:08:17,894 - INFO -    Exit distribution: STOP=20, TP1=7, TP2=4, RUNNER=4
2026-02-26 14:08:18,359 - INFO -    ✅ Chunk 1 complete: 35 trades, final equity $90,700
2026-02-26 14:08:18,818 - INFO -    📦 Chunk 2/2: days 263-526 (capital: $90,700)
2026-02-26 14:08:18,823 - INFO - 🔄 Running single-chunk backtest with Numba Core...
2026-02-26 14:08:18,824 - INFO - 🔄 Converting DataFrames to NumPy arrays (float32 optimization)...
2026-02-26 14:08:18,861 - INFO -    ✅ Arrays prepared: 7.0 MB total
2026-02-26 14:08:18,862 - INFO -    📊 Array shapes: close=(263, 538), high=(263, 538)
2026-02-26 14:08:18,862 - INFO - ⚡ Ejecutando simulación ultra-rápida (Numba Core)...
2026-02-26 14:08:18,862 - INFO -    🚀 Using pre-calculated NumPy arrays (memory optimized - float32)
2026-02-26 14:08:18,867 - INFO -    💰 Numba Core usando FIXED DOLLAR RISK: $1000 → risk_pct=0.0110
2026-02-26 14:08:18,867 - INFO - 🔧 NUMBA CORE PARAMETERS:
2026-02-26 14:08:18,867 - INFO -    Initial Capital: $90,700.00
2026-02-26 14:08:18,867 - INFO -    Risk per Trade: $1,000.00
2026-02-26 14:08:18,867 - INFO -    Use Fixed Risk: True
2026-02-26 14:08:18,868 - INFO -    TP1/TP2 Targets: 1.8997173797313318R / 2.9571819376044006R
2026-02-26 14:08:18,868 - INFO -    TP Distribution: 45% / 30% / 25%
2026-02-26 14:08:18,868 - INFO -    Max Stop %%: 8.0% (decimal: 0.08)
2026-02-26 14:08:18,868 - INFO -    Trailing Stop: False
2026-02-26 14:08:18,868 - INFO -    ATR Stop Mode: False
2026-02-26 14:08:18,868 - INFO -    Total Entries Signals: 31936
2026-02-26 14:08:18,869 - INFO - 🚀 Numba Simulation Time: 0.0009s
2026-02-26 14:08:18,869 - INFO - 📊 Numba Core Results:
2026-02-26 14:08:18,869 - INFO -    Entry signals found: 31936
2026-02-26 14:08:18,869 - INFO -    Trades executed: 43
2026-02-26 14:08:18,869 - INFO -    Conversion rate: 0.1%
2026-02-26 14:08:18,870 - INFO -    Final equity: $98,072.10
2026-02-26 14:08:18,870 - WARNING -    ⚠️ Low conversion rate (0.1%) - Check parameters
2026-02-26 14:08:18,870 - WARNING -    May indicate: Restrictive filters, largistances, or insufficient capital
2026-02-26 14:08:18,870 - INFO -    Exit distribution: STOP=18, TP1=11, TP2=9, RUNNER=5
2026-02-26 14:08:19,330 - INFO -    ✅ Chunk 2 complete: 43 trades, final equity $98,072
2026-02-26 14:08:19,787 - INFO - ✅ Multi-chunk backtest complete: 78 total trades
2026-02-26 14:08:19,791 - INFO - ✅ Backtest complete!
2026-02-26 14:08:19,791 - INFO -    Return: -1.93%
2026-02-26 14:08:19,791 - INFO -    Annualized Return: -0.93%
2026-02-26 14:08:19,791 - INFO -    Sharpe: 0.01
2026-02-26 14:08:19,791 - INFO -    Max DD: -22.50%
2026-02-26 14:08:19,791 - INFO -    MAR Ratio: -0.04
2026-02-26 14:08:19,791 - INFO -    Calmar Ratio: -0.04
2026-02-26 14:08:19,791 - INFO -    Win Rate: 50.0%
2026-02-26 14:08:19,791 - INFO -    Trades: 52488 entries → 78 total exits (including partial)
2026-02-26 14:08:19,798 - INFO - ============================================================
2026-02-26 14:08:19,799 - INFO - 🚀 MODE: PRODUCTION (Fixed Dollar Risk)
2026-02-26 14:08:19,799 - INFO -    • Risk: FIXED DOLLAR ($1000)
2026-02-26 14:08:19,799 - INFO -    • Compounding: DISABLED
2026-02-26 14:08:19,799 - INFO - ============================================================
2026-02-26 14:08:19,800 - INFO - 🚀 Advanced VectorBT Engine initialized
2026-02-26 14:08:19,801 - INFO - 📅 Period: 2022-01-01 to 2024-02-06
2026-02-26 14:08:19,801 - INFO - 🎯 Universe: 566 tickers
2026-02-26 14:08:19,801 - INFO - 🎛️  Liquidity: vol≥100k, $vol≥$98M, ADR≥1.8199277694426135%, RVOL≥0.6025868102740569x
2026-02-26 14:08:19,801 - INFO - 🎛️  Position Size: RVOL Danger≥3.0x→50%, Warning≥2.0x→75%
2026-02-26 14:08:19,801 - INFO - ============================================================
2026-02-26 14:08:19,801 - INFO - 🌍 MARKET REGIME FILTER ENABLED
2026-02-26 14:08:19,801 - INFO - ============================================================
2026-02-26 14:08:19,801 - INFO - 📊 Loading SPY and VIX data (2022-01-01 to 2024-02-06)...
2026-02-26 14:08:19,803 - INFO -    ✅ SPY loaded from cache: 526 bars
2026-02-26 14:08:19,806 - INFO -    ✅ VIX loaded from cache: 526 bars
2026-02-26 14:08:19,806 - INFO -    ✅ Market data loaded successfully
2026-02-26 14:08:19,812 - INFO -    ✅ Market regime classifier initialized
2026-02-26 14:08:19,812 - INFO -    🚫 Block Stage 3: True
2026-02-26 14:08:19,812 - INFO -    🚫 Block Stage 4: True
2026-02-26 14:08:19,812 - INFO -    📊 Adjust risk by regime: True
2026-02-26 14:08:19,826 - INFO - 📥 Loading data from 2021-01-01 (buffer) to 2024-02-06...
2026-02-26 14:08:19,827 - INFO - 🎯 Universe size: 566 tickers
2026-02-26 14:08:19,827 - INFO - 🛡️  Survivorship bias protection: PIT mask will determine eligibility quarterly
2026-02-26 14:08:19,827 - INFO - ⚡ Fetching data for 566 tickers in parallel...
2026-02-26 14:08:20,119 - WARNING - ❌ SKIP AMTM: None returned
2026-02-26 14:08:20,122 - WARNING - ❌ SKIP ANSS: None returned
2026-02-26 14:08:20,388 - WARNING - ❌ SKIP ATVI: None returned
2026-02-26 14:08:20,576 - INFO -    100/566...
2026-02-26 14:08:21,491 - WARNING - ❌ SKIP CDAY: None returned
2026-02-26 14:08:21,685 - WARNING - ❌ SKIP CTXS: None returned
2026-02-26 14:08:21,984 - INFO -    200/566...
2026-02-26 14:08:21,993 - WARNING - ❌ SKIP DRE: None returned
2026-02-26 14:08:22,034 - WARNING - ❌ SKIP FB: None returned
2026-02-26 14:08:22,043 - WARNING - ❌ SKIP FBHS: None returned
2026-02-26 14:08:22,045 - WARNING - ❌ SKIP FI: None returned
2026-02-26 14:08:22,051 - WARNING - ❌ SKIP FISV: None returned
2026-02-26 14:08:22,676 - INFO -    300/566...
2026-02-26 14:08:23,465 - INFO -    400/566...
2026-02-26 14:08:24,194 - INFO -    500/566...
2026-02-26 14:08:24,655 - WARNING - ⚠️  Skipped 28 tickers (insufficient data)
2026-02-26 14:08:24,655 - INFO -    First 10 failed: ['AMTM (None returned)', 'ANSS (None returned)', 'ATVI (None returned)', 'CDAY (None returned)', 'CTXS (None returned)', 'DRE (None returned)', 'FB (None returned)', 'FBHS (None returned)', 'FI (None returned)', 'FISV (None returned)']
2026-02-26 14:08:24,655 - INFO - ℹ️  538 tickers with partial data (gaps in history)
2026-02-26 14:08:24,888 - INFO - Memory: 6.4 MB for 538 tickers (core DataFrames)
2026-02-26 14:08:24,888 - INFO - 🛡️  Building Point-in-Time tradeable mask (survivorship bias protection)...
2026-02-26 14:08:24,948 - INFO - PointInTimeUniverse: loaded 1230 ticker membership records
2026-02-26 14:08:25,021 - INFO - Tradeable mask: 376,609/418,564 cells (90.0%) across 538 S&P 500 + 0 non-S&P tickers, 778 trading days
2026-02-26 14:08:25,049 - INFO -    🛡️  Masked out 41,955 cells (10.0%) as non-tradeable (pre-IPO, post-delist, not in S&P 500)
2026-02-26 14:08:25,066 - WARNING -    ⚠️ No precomputed metrics found in cache, will calculate on the fly
2026-02-26 14:08:25,756 - INFO -    ⚠️ Precomputed metrics not available, calculating on the fly...
2026-02-26 14:08:25,790 - INFO -    ⚠️ SMA50 missing in cache, calculating on the fly...
2026-02-26 14:08:26,747 - INFO -    Loading SPY and VIX data for Market Regime...
2026-02-26 14:08:26,747 - INFO - 📊 Loading SPY and VIX data (2021-01-01 to 2024-02-06)...
2026-02-26 14:08:26,750 - INFO -    ✅ SPY loaded from cache: 778 bars
2026-02-26 14:08:26,753 - INFO -    ✅ VIX loaded from cache: 778 bars
2026-02-26 14:08:26,753 - INFO -    ✅ Market data loaded successfully
2026-02-26 14:08:26,761 - INFO -    ✅ Market Data Loaded & Aligned
2026-02-26 14:08:26,761 - INFO - ✅ Loaded: 538 tickers
2026-02-26 14:08:26,762 - INFO - 🛡️  Filtered out 28 tickers (insufficient data)
2026-02-26 14:08:26,762 - INFO -    Date range: 2021-01-04 to 2024-02-06 (778 days)
2026-02-26 14:08:26,762 - INFO -    🔧 Truncating data to start_date: 2022-01-01
2026-02-26 14:08:26,993 - INFO - Memory: ~15.2 MB total after float32 conversion
2026-02-26 14:08:27,014 - INFO - 🎯 Starting advanced backtest with partial exits...
2026-02-26 14:08:27,015 - INFO - 📥 Loading data from 2021-01-01 (buffer) to 2024-02-06...
2026-02-26 14:08:27,015 - INFO - 🎯 Universe size: 538 tickers
2026-02-26 14:08:27,015 - INFO - 🛡️  Survivorship bias protection: PIT mask will determine eligibility quarterly
2026-02-26 14:08:27,015 - INFO - ⚡ Fetching data for 538 tickers in parallel...
2026-02-26 14:08:27,860 - INFO -    100/538...
2026-02-26 14:08:28,510 - INFO -    200/538...
2026-02-26 14:08:29,308 - INFO -    300/538...
2026-02-26 14:08:30,031 - INFO -    400/538...
2026-02-26 14:08:30,728 - INFO -    500/538...
2026-02-26 14:08:30,998 - INFO - ℹ️  538 tickers with partial data (gaps in history)
2026-02-26 14:08:31,231 - INFO - Memory: 6.4 MB for 538 tickers (core DataFrames)
2026-02-26 14:08:31,231 - INFO - 🛡️  Building Point-in-Time tradeable mask (survivorship bias protection)...
2026-02-26 14:08:31,280 - INFO - PointInTimeUniverse: loaded 1230 ticker membership records
2026-02-26 14:08:31,350 - INFO - Tradeable mask: 376,609/418,564 cells (90.0%) across 538 S&P 500 + 0 non-S&P tickers, 778 trading days
2026-02-26 14:08:31,371 - INFO -    🛡️  Masked out 41,955 cells (10.0%) as non-tradeable (pre-IPO, post-delist, not in S&P 500)
2026-02-26 14:08:31,390 - WARNING -    ⚠️ No precomputed metrics found in cache, will calculate on the fly
2026-02-26 14:08:31,997 - INFO -    ⚠️ Precomputed metrics not available, calculating on the fly...
2026-02-26 14:08:32,031 - INFO -    ⚠️ SMA50 missing in cache, calculating on the fly...
2026-02-26 14:08:33,309 - INFO -    Loading SPY and VIX data for Market Regime...
2026-02-26 14:08:33,309 - INFO - 📊 Loading SPY and VIX data (2021-01-01 to 2024-02-06)...
2026-02-26 14:08:33,312 - INFO -    ✅ SPY loaded from cache: 778 bars
2026-02-26 14:08:33,315 - INFO -    ✅ VIX loaded from cache: 778 bars
2026-02-26 14:08:33,315 - INFO -    ✅ Market data loaded successfully
2026-02-26 14:08:33,322 - INFO -    ✅ Market Data Loaded & Aligned
2026-02-26 14:08:33,322 - INFO - ✅ Loaded: 538 tickers
2026-02-26 14:08:33,322 - INFO -    Date range: 2021-01-04 to 2024-02-06 (778 days)
2026-02-26 14:08:33,322 - INFO -    🔧 Truncating data to start_date: 2022-01-01
2026-02-26 14:08:33,543 - INFO - Memory: ~15.2 MB total after float32 conversion
2026-02-26 14:08:33,587 - INFO - 🔍 Calculating entry signals...
2026-02-26 14:08:33,589 - INFO -    🎯 Using TREND signal (close > SMA20)
2026-02-26 14:08:33,590 - INFO -    📊 ADVANCED MODE entries (before Adaptive Filter): 133000
2026-02-26 14:08:33,591 - INFO -       Base entry passed: 133000
2026-02-26 14:08:33,615 - INFO - 🛡️  PIT Universe filter: blocked 0 entries on non-member dates (133000 remaining)
2026-02-26 14:08:33,632 - INFO - 🔧 Applying Adaptive Filter Engine (TIER 1-2-3) - OPTIMIZADO...
2026-02-26 14:08:33,633 - INFO - 🔧 AdaptiveFilterEngine initialized
   ⚡ Applying Adaptive Filter: 100%|████| 526/526 [00:01<00:00, 278.31day/s]
2026-02-26 14:08:35,525 - INFO -    📊 Entries antes de Adaptive Filter: 133000
2026-02-26 14:08:35,526 - INFO -    ❌ Entries rechazadas por TIER:
2026-02-26 14:08:35,526 - INFO -       TIER 1 (Market Safety): 37907
2026-02-26 14:08:35,526 - INFO -       TIER 2 (Dynamic Quality): 40176
2026-02-26 14:08:35,526 - INFO -       TIER 3 (Optional): 97
2026-02-26 14:08:35,526 - INFO -    ✅ Entries finales: 54820

======================================================================
📊 ADAPTIVE FILTER ENGINE - RESUMEN (OPTIMIZADO)
======================================================================
  Total de Rechazos: 78180
  • TIER 1 (Market Safety): 37907
  • TIER 2 (Dynamic Quality): 40176
  TIER 3 (Optional): 97
======================================================================
2026-02-26 14:08:35,648 - INFO - 🔍 Clasificando riesgo por RVOL (VolTrig)...
2026-02-26 14:08:35,652 - INFO -    ☔ Danger (RVOL>=3.0x): 198 entries → Size 50%
2026-02-26 14:08:35,652 - INFO -    ⚠️  Warning (RVOL>=2.0x): 1108 entries → Size 75%
2026-02-26 14:08:35,652 - INFO -    ✅ Safe (RVOL<2.0x): 53514 entries → Size 100%
2026-02-26 14:08:35,652 - INFO - 🔍 Clasificando riesgo por ADR (volatilidad)...
2026-02-26 14:08:35,726 - INFO -    🔥 High ADR (>6.0%): 194 entries → Size 25%
2026-02-26 14:08:35,726 - INFO -    ⚠️  Med ADR (>5.0%): 419 entries → Size 33%
2026-02-26 14:08:35,766 - INFO - 📊 Multi-chunk mode: 526 days → 2 chunks of ~500 days
2026-02-26 14:08:35,766 - INFO - 🔄 Running multi-chunk backtest: 2 chunks...
2026-02-26 14:08:35,771 - INFO -    📦 Chunk 1/2: days 0-263 (capital: $100,000)
2026-02-26 14:08:35,778 - INFO - 🔄 Running single-chunk backtest with Numba Core...
2026-02-26 14:08:35,778 - INFO - 🔄 Converting DataFrames to NumPy arrays (float32 optimization)...
2026-02-26 14:08:35,816 - INFO -    ✅ Arrays prepared: 7.0 MB total
2026-02-26 14:08:35,816 - INFO -    📊 Array shapes: close=(263, 538), high=(263, 538)
2026-02-26 14:08:35,816 - INFO - ⚡ Ejecutando simulación ultra-rápida (Numba Core)...
2026-02-26 14:08:35,816 - INFO -    🚀 Using pre-calculated NumPy arrays (memory optimized - float32)
2026-02-26 14:08:35,822 - INFO -    💰 Numba Core usando FIXED DOLLAR RISK: $1000 → risk_pct=0.0100
2026-02-26 14:08:35,822 - INFO - 🔧 NUMBA CORE PARAMETERS:
2026-02-26 14:08:35,822 - INFO -    Initial Capital: $100,000.00
2026-02-26 14:08:35,823 - INFO -    Risk per Trade: $1,000.00
2026-02-26 14:08:35,823 - INFO -    Use Fixed Risk: True
2026-02-26 14:08:35,823 - INFO -    TP1/TP2 Targets: 1.8064610472482552R / 2.9287610205951093R
2026-02-26 14:08:35,823 - INFO -    TP Distribution: 45% / 30% / 25%
2026-02-26 14:08:35,823 - INFO -    Max Stop %%: 8.0% (decimal: 0.08)
2026-02-26 14:08:35,823 - INFO -    Trailing Stop: False
2026-02-26 14:08:35,823 - INFO -    ATR Stop Mode: False
2026-02-26 14:08:35,823 - INFO -    Total Entries Signals: 22962
2026-02-26 14:08:35,824 - INFO - 🚀 Numba Simulation Time: 0.0010s
2026-02-26 14:08:35,825 - INFO - 📊 Numba Core Results:
2026-02-26 14:08:35,825 - INFO -    Entry signals found: 22962
2026-02-26 14:08:35,825 - INFO -    Trades executed: 40
2026-02-26 14:08:35,825 - INFO -    Conversion rate: 0.2%
2026-02-26 14:08:35,825 - INFO -    Final equity: $85,964.41
2026-02-26 14:08:35,825 - WARNING -    ⚠️ Low conversion rate (0.2%) - Check parameters
2026-02-26 14:08:35,825 - WARNING -    May indicate: Restrictive filters, large stop distances, or insufficient capital
2026-02-26 14:08:35,825 - INFO -    Exit distribution: STOP=24, TP1=8, TP2=4, RUNNER=4
2026-02-26 14:08:36,297 - INFO -    ✅ Chunk 1 complete: 40 trades, final equity $85,964
2026-02-26 14:08:36,751 - INFO -    📦 Chunk 2/2: days 263-526 (capital: $85,964)
2026-02-26 14:08:36,755 - INFO - 🔄 Running single-chunk backtest with Numba Core...
2026-02-26 14:08:36,756 - INFO - 🔄 Converting DataFrames to NumPy arrays (float32 optimization)...
2026-02-26 14:08:36,792 - INFO -    ✅ Arrays prepared: 7.0 MB total
2026-02-26 14:08:36,792 - INFO -    📊 Array shapes: close=(263, 538), high=(263, 538)
2026-02-26 14:08:36,793 - INFO - ⚡ Ejecutando simulación ultra-rápida (Numba Core)...
2026-02-26 14:08:36,793 - INFO -    🚀 Using pre-calculated NumPy arrays (memory optimized - float32)
2026-02-26 14:08:36,798 - INFO -    💰 Numba Core usando FIXED DOLLAR RISK: $1000 → risk_pct=0.0116
2026-02-26 14:08:36,798 - INFO - 🔧 NUMBA CORE PARAMETERS:
2026-02-26 14:08:36,798 - INFO -    Initial Capital: $85,964.41
2026-02-26 14:08:36,798 - INFO -    Risk per Trade: $1,000.00
2026-02-26 14:08:36,798 - INFO -    Use Fixed Risk: True
2026-02-26 14:08:36,798 - INFO -    TP1/TP2 Targets: 1.8064610472482552R / 2.9287610205951093R
2026-02-26 14:08:36,798 - INFO -    TP Distribution: 45% / 30% / 25%
2026-02-26 14:08:36,798 - INFO -    Max Stop %%: 8.0% (decimal: 0.08)
2026-02-26 14:08:36,798 - INFO -    Trailing Stop: False
2026-02-26 14:08:36,798 - INFO -    ATR Stop Mode: False
2026-02-26 14:08:36,798 - INFO -    Total Entries Signals: 31858
2026-02-26 14:08:36,799 - INFO - 🚀 Numba Simulation Time: 0.0009s
2026-02-26 14:08:36,800 - INFO - 📊 Numba Core Results:
2026-02-26 14:08:36,800 - INFO -    Entry signals found: 31858
2026-02-26 14:08:36,800 - INFO -    Trades executed: 39
2026-02-26 14:08:36,800 - INFO -    Conversion rate: 0.1%
2026-02-26 14:08:36,800 - INFO -    Final equity: $98,302.64
2026-02-26 14:08:36,800 - WARNING -    ⚠️ Low conversion rate (0.1%) - Check parameters
2026-02-26 14:08:36,800 - WARNING -    May indicate: Restrictive filters, large stop distances, or insufficient capital
2026-02-26 14:08:36,800 - INFO -    Exit distribution: STOP=16, TP1=11, TP2=8, RUNNER=4
2026-02-26 14:08:37,267 - INFO -    ✅ Chunk 2 complete: 39 trades, final equity $98,303
2026-02-26 14:08:37,724 - INFO - ✅ Multi-chunk backtest complete: 79 total trades
2026-02-26 14:08:37,728 - INFO - ✅ Backtest complete!
2026-02-26 14:08:37,728 - INFO -    Return: -1.70%
2026-02-26 14:08:37,728 - INFO -    Annualized Return: -0.82%
2026-02-26 14:08:37,728 - INFO -    Sharpe: 0.01
2026-02-26 14:08:37,728 - INFO -    Max DD: -24.52%
2026-02-26 14:08:37,728 - INFO -    MAR Ratio: -0.03
2026-02-26 14:08:37,729 - INFO -    Calmar Ratio: -0.03
2026-02-26 14:08:37,729 - INFO -    Win Rate: 48.1%
2026-02-26 14:08:37,729 - INFO -    Trades: 54820 entries → 79 total exits (including partial)
2026-02-26 14:08:37,736 - INFO - ============================================================
2026-02-26 14:08:37,736 - INFO - 🚀 MODE: PRODUCTION (Fixed Dollar Risk)
2026-02-26 14:08:37,736 - INFO -    • Risk: FIXED DOLLAR ($1000)
2026-02-26 14:08:37,736 - INFO -    • Compounding: DISABLED
2026-02-26 14:08:37,736 - INFO - ============================================================
2026-02-26 14:08:37,738 - INFO - 🚀 Advanced VectorBT Engine initialized
2026-02-26 14:08:37,738 - INFO - 📅 Period: 2022-01-01 to 2024-02-06
2026-02-26 14:08:37,738 - INFO - 🎯 Universe: 566 tickers
2026-02-26 14:08:37,738 - INFO - 🎛️  Liquidity: vol≥100k, $vol≥$98M, ADR≥1.7315338308550605%, RVOL≥0.6068927190488428x
2026-02-26 14:08:37,738 - INFO - 🎛️  Position Size: RVOL Danger≥3.0x→50%, Warning≥2.0x→75%
2026-02-26 14:08:37,738 - INFO - ============================================================
2026-02-26 14:08:37,739 - INFO - 🌍 MARKET REGIME FILTER ENABLED
2026-02-26 14:08:37,739 - INFO - ============================================================
2026-02-26 14:08:37,739 - INFO - 📊 Loading SPY and VIX data (2022-01-01 to 2024-02-06)...
2026-02-26 14:08:37,741 - INFO -    ✅ SPY loaded from cache: 526 bars
2026-02-26 14:08:37,743 - INFO -    ✅ VIX loaded from cache: 526 bars
2026-02-26 14:08:37,744 - INFO -    ✅ Market data loaded successfully
2026-02-26 14:08:37,750 - INFO -    ✅ Market regime classifier initialized
2026-02-26 14:08:37,750 - INFO -    🚫 Block Stage 3: True
2026-02-26 14:08:37,750 - INFO -    🚫 Block Stage 4: True
2026-02-26 14:08:37,750 - INFO -    📊 Adjust risk by regime: True
2026-02-26 14:08:37,766 - INFO - 📥 Loading data from 2021-01-01 (buffer) to 2024-02-06...
2026-02-26 14:08:37,767 - INFO - 🎯 Universe size: 566 tickers
2026-02-26 14:08:37,767 - INFO - 🛡️  Survivorship bias protection: PIT mask will determine eligibility quarterly
2026-02-26 14:08:37,767 - INFO - ⚡ Fetching data for 566 tickers in parallel...
2026-02-26 14:08:38,064 - WARNING - ❌ SKIP AMTM: None returned
2026-02-26 14:08:38,068 - WARNING - ❌ SKIP ANSS: None returned
2026-02-26 14:08:38,321 - WARNING - ❌ SKIP ATVI: None returned
2026-02-26 14:08:38,518 - INFO -    100/566...
2026-02-26 14:08:38,673 - WARNING - ❌ SKIP CDAY: None returned
2026-02-26 14:08:38,840 - WARNING - ❌ SKIP CTXS: None returned
2026-02-26 14:08:39,135 - INFO -    200/566...
2026-02-26 14:08:39,143 - WARNING - ❌ SKIP DRE: None returned
2026-02-26 14:08:39,186 - WARNING - ❌ SKIP FB: None returned
2026-02-26 14:08:39,187 - WARNING - ❌ SKIP FBHS: None returned
2026-02-26 14:08:39,196 - WARNING - ❌ SKIP FI: None returned
2026-02-26 14:08:39,204 - WARNING - ❌ SKIP FISV: None returned
2026-02-26 14:08:39,877 - INFO -    300/566...
2026-02-26 14:08:40,661 - INFO -    400/566...
2026-02-26 14:08:41,383 - INFO -    500/566...
2026-02-26 14:08:41,849 - WARNING - ⚠️  Skipped 28 tickers (insufficient data)
2026-02-26 14:08:41,849 - INFO -    First 10 failed: ['AMTM (None returned)', 'ANSS (None returned)', 'ATVI (None returned)', 'CDAY (None returned)', 'CTXS (None returned)', 'DRE (None returned)', 'FB (None returned)', 'FBHS (None returned)', 'FI (None returned)', 'FISV (None returned)']
2026-02-26 14:08:41,849 - INFO - ℹ️  538 tickers with partial data (gaps in history)
2026-02-26 14:08:42,076 - INFO - Memory: 6.4 MB for 538 tickers (core DataFrames)
2026-02-26 14:08:42,077 - INFO - 🛡️  Building Point-in-Time tradeable mask (survivorship bias protection)...
2026-02-26 14:08:42,132 - INFO - PointInTimeUniverse: loaded 1230 ticker membership records
2026-02-26 14:08:42,201 - INFO - Tradeable mask: 376,609/418,564 cells (90.0%) across 538 S&P 500 + 0 non-S&P tickers, 778 trading days
2026-02-26 14:08:42,221 - INFO -    🛡️  Masked out 41,955 cells (10.0%) as non-tradeable (pre-IPO, post-delist, not in S&P 500)
2026-02-26 14:08:42,237 - WARNING -    ⚠️ No precomputed metrics found in cache, will calculate on the fly
2026-02-26 14:08:42,838 - INFO -    ⚠️ Precomputed metrics not available, calculating on the fly...
2026-02-26 14:08:42,871 - INFO -    ⚠️ SMA50 missing in cache, calculating on the fly...
2026-02-26 14:08:43,738 - INFO -    Loading SPY and VIX data for Market Regime...
2026-02-26 14:08:43,739 - INFO - 📊 Loading SPY and VIX data (2021-01-01 to 2024-02-06)...
2026-02-26 14:08:43,741 - INFO -    ✅ SPY loaded from cache: 778 bars
2026-02-26 14:08:43,744 - INFO -    ✅ VIX loaded from cache: 778 bars
2026-02-26 14:08:43,745 - INFO -    ✅ Market data loaded successfully
2026-02-26 14:08:43,751 - INFO -    ✅ Market Data Loaded & Aligned
2026-02-26 14:08:43,752 - INFO - ✅ Loaded: 538 tickers
2026-02-26 14:08:43,752 - INFO - 🛡️  Filtered out 28 tickers (insufficient data)
2026-02-26 14:08:43,752 - INFO -    Date range: 2021-01-04 to 2024-02-06 (778 days)
2026-02-26 14:08:43,752 - INFO -    🔧 Truncating data to start_date: 2022-01-01
2026-02-26 14:08:43,966 - INFO - Memory: ~15.2 MB total after float32 conversion
2026-02-26 14:08:43,984 - INFO - 🎯 Starting advanced backtest with partial exits...
2026-02-26 14:08:43,986 - INFO - 📥 Loading data from 2021-01-01 (buffer) to 2024-02-06...
2026-02-26 14:08:43,986 - INFO - 🎯 Universe size: 538 tickers
2026-02-26 14:08:43,986 - INFO - 🛡️  Survivorship bias protection: PIT mask will determine eligibility quarterly
2026-02-26 14:08:43,986 - INFO - ⚡ Fetching data for 538 tickers in parallel...
2026-02-26 14:08:44,781 - INFO -    100/538...
2026-02-26 14:08:45,423 - INFO -    200/538...
2026-02-26 14:08:46,077 - INFO -    300/538...
2026-02-26 14:08:46,816 - INFO -    400/538...
2026-02-26 14:08:47,525 - INFO -    500/538...
2026-02-26 14:08:47,808 - INFO - ℹ️  538 tickers with partial data (gaps in history)
2026-02-26 14:08:48,044 - INFO - Memory: 6.4 MB for 538 tickers (core DataFrames)
2026-02-26 14:08:48,044 - INFO - 🛡️  Building Point-in-Time tradeable mask (survivorship bias protection)...
2026-02-26 14:08:48,101 - INFO - PointInTimeUniverse: loaded 1230 ticker membership records
2026-02-26 14:08:48,170 - INFO - Tradeable mask: 376,609/418,564 cells (90.0%) across 538 S&P 500 + 0 non-S&P tickers, 778 trading days
2026-02-26 14:08:48,192 - INFO -    🛡️  Masked out 41,955 cells (10.0%) as non-tradeable (pre-IPO, post-delist, not in S&P 500)
2026-02-26 14:08:48,211 - WARNING -    ⚠️ No precomputed metrics found in cache, will calculate on the fly
2026-02-26 14:08:48,835 - INFO -    ⚠️ Precomputed metrics not available, calculating on the fly...
2026-02-26 14:08:48,869 - INFO -    ⚠️ SMA50 missing in cache, calculating on the fly...
2026-02-26 14:08:50,207 - INFO -    Loading SPY and VIX data for Market Regime...
2026-02-26 14:08:50,208 - INFO - 📊 Loading SPY and VIX data (2021-01-01 to 2024-02-06)...
2026-02-26 14:08:50,210 - INFO -    ✅ SPY loaded from cache: 778 bars
2026-02-26 14:08:50,213 - INFO -    ✅ VIX loaded from cache: 778 bars
2026-02-26 14:08:50,214 - INFO -    ✅ Market data loaded successfully
2026-02-26 14:08:50,221 - INFO -    ✅ Market Data Loaded & Aligned
2026-02-26 14:08:50,221 - INFO - ✅ Loaded: 538 tickers
2026-02-26 14:08:50,222 - INFO -    Date range: 2021-01-04 to 2024-02-06 (778 days)
2026-02-26 14:08:50,222 - INFO -    🔧 Truncating data to start_date: 2022-01-01
2026-02-26 14:08:50,442 - INFO - Memory: ~15.2 MB total after float32 conversion
2026-02-26 14:08:50,486 - INFO - 🔍 Calculating entry signals...
2026-02-26 14:08:50,488 - INFO -    🎯 Using TREND signal (close > SMA20)
2026-02-26 14:08:50,489 - INFO -    📊 ADVANCED MODE entries (before Adaptive Filter): 133000
2026-02-26 14:08:50,490 - INFO -       Base entry passed: 133000
2026-02-26 14:08:50,517 - INFO - 🛡️  PIT Universe filter: blocked 0 entries on non-member dates (133000 remaining)
2026-02-26 14:08:50,531 - INFO - 🔧 Applying Adaptive Filter Engine (TIER 1-2-3) - OPTIMIZADO...
2026-02-26 14:08:50,531 - INFO - 🔧 AdaptiveFilterEngine initialized
   ⚡ Applying Adaptive Filter: 100%|████| 526/526 [00:01<00:00, 281.82day/s]
2026-02-26 14:08:52,399 - INFO -    📊 Entries antes de Adaptive Filter: 133000
2026-02-26 14:08:52,400 - INFO -    ❌ Entries rechazadas por TIER:
2026-02-26 14:08:52,400 - INFO -       TIER 1 (Market Safety): 37907
2026-02-26 14:08:52,400 - INFO -       TIER 2 (Dynamic Quality): 37811
2026-02-26 14:08:52,400 - INFO -       TIER 3 (Optional): 94
2026-02-26 14:08:52,400 - INFO -    ✅ Entries finales: 57188

======================================================================
📊 ADAPTIVE FILTER ENGINE - RESUMEN (OPTIMIZADO)
======================================================================
  Total de Rechazos: 75812
  • TIER 1 (Market Safety): 37907
  • TIER 2 (Dynamic Quality): 37811
  TIER 3 (Optional): 94
======================================================================
2026-02-26 14:08:52,516 - INFO - 🔍 Clasificando riesgo por RVOL (VolTrig)...
2026-02-26 14:08:52,521 - INFO -    ☔ Danger (RVOL>=3.0x): 203 entries → Size 50%
2026-02-26 14:08:52,521 - INFO -    ⚠️  Warning (RVOL>=2.0x): 1141 entries → Size 75%
2026-02-26 14:08:52,521 - INFO -    ✅ Safe (RVOL<2.0x): 55844 entries → Size 100%
2026-02-26 14:08:52,521 - INFO - 🔍 Clasificando riesgo por ADR (volatilidad)...
2026-02-26 14:08:52,595 - INFO -    🔥 High ADR (>6.0%): 176 entries → Size 25%
2026-02-26 14:08:52,595 - INFO -    ⚠️  Med ADR (>5.0%): 392 entries → Size 33%
2026-02-26 14:08:52,636 - INFO - 📊 Multi-chunk mode: 526 days → 2 chunks of ~500 days
2026-02-26 14:08:52,636 - INFO - 🔄 Running multi-chunk backtest: 2 chunks...
2026-02-26 14:08:52,641 - INFO -    📦 Chunk 1/2: days 0-263 (capital: $100,000)
2026-02-26 14:08:52,648 - INFO - 🔄 Running single-chunk backtest with Numba Core...
2026-02-26 14:08:52,648 - INFO - 🔄 Converting DataFrames to NumPy arrays (float32 optimization)...
2026-02-26 14:08:52,684 - INFO -    ✅ Arrays prepared: 7.0 MB total
2026-02-26 14:08:52,685 - INFO -    📊 Array shapes: close=(263, 538), high=(263, 538)
2026-02-26 14:08:52,685 - INFO - ⚡ Ejecutando simulación ultra-rápida (Numba Core)...
2026-02-26 14:08:52,685 - INFO -    🚀 Using pre-calculated NumPy arrays (memory optimized - float32)
2026-02-26 14:08:52,692 - INFO -    💰 Numba Core usando FIXED DOLLAR RISK: $1000 → risk_pct=0.0100
2026-02-26 14:08:52,692 - INFO - 🔧 NUMBA CORE PARAMETERS:
2026-02-26 14:08:52,692 - INFO -    Initial Capital: $100,000.00
2026-02-26 14:08:52,692 - INFO -    Risk per Trade: $1,000.00
2026-02-26 14:08:52,692 - INFO -    Use Fixed Risk: True
2026-02-26 14:08:52,692 - INFO -    TP1/TP2 Targets: 1.911908607761142R / 3.0594984249440365R
2026-02-26 14:08:52,692 - INFO -    TP Distribution: 45% / 30% / 25%
2026-02-26 14:08:52,692 - INFO -    Max Stop %%: 8.0% (decimal: 0.08)
2026-02-26 14:08:52,692 - INFO -    Trailing Stop: False
2026-02-26 14:08:52,693 - INFO -    ATR Stop Mode: False
2026-02-26 14:08:52,693 - INFO -    Total Entries Signals: 22966
2026-02-26 14:08:52,694 - INFO - 🚀 Numba Simulation Time: 0.0015s
2026-02-26 14:08:52,695 - INFO - 📊 Numba Core Results:
2026-02-26 14:08:52,695 - INFO -    Entry signals found: 22966
2026-02-26 14:08:52,695 - INFO -    Trades executed: 33
2026-02-26 14:08:52,695 - INFO -    Conversion rate: 0.1%
2026-02-26 14:08:52,695 - INFO -    Final equity: $94,184.36
2026-02-26 14:08:52,695 - WARNING -    ⚠️ Low conversion rate (0.1%) - Check parameters
2026-02-26 14:08:52,695 - WARNING -    May indicate: Restrictive filters, large stop distances, or insufficient capital
2026-02-26 14:08:52,695 - INFO -    Exit distribution: STOP=18, TP1=7, TP2=4, RUNNER=4
2026-02-26 14:08:53,161 - INFO -    ✅ Chunk 1 complete: 33 trades, final equity $94,184
2026-02-26 14:08:53,616 - INFO -    📦 Chunk 2/2: days 263-526 (capital: $94,184)
2026-02-26 14:08:53,620 - INFO - 🔄 Running single-chunk backtest with Numba Core...
2026-02-26 14:08:53,620 - INFO - 🔄 Converting DataFrames to NumPy arrays (float32 optimization)...
2026-02-26 14:08:53,658 - INFO -    ✅ Arrays prepared: 7.0 MB total
2026-02-26 14:08:53,658 - INFO -    📊 Array shapes: close=(263, 538), high=(263, 538)
2026-02-26 14:08:53,659 - INFO - ⚡ Ejecutando simulación ultra-rápida (Numba Core)...
2026-02-26 14:08:53,659 - INFO -    🚀 Using pre-calculated NumPy arrays (memory optimized - float32)
2026-02-26 14:08:53,664 - INFO -    💰 Numba Core usando FIXED DOLLAR RISK: $1000 → risk_pct=0.0106
2026-02-26 14:08:53,664 - INFO - 🔧 NUMBA CORE PARAMETERS:
2026-02-26 14:08:53,664 - INFO -    Initial Capital: $94,184.36
2026-02-26 14:08:53,664 - INFO -    Risk per Trade: $1,000.00
2026-02-26 14:08:53,664 - INFO -    Use Fixed Risk: True
2026-02-26 14:08:53,664 - INFO -    TP1/TP2 Targets: 1.911908607761142R / 3.0594984249440365R
2026-02-26 14:08:53,664 - INFO -    TP Distribution: 45% / 30% / 25%
2026-02-26 14:08:53,664 - INFO -    Max Stop %%: 8.0% (decimal: 0.08)
2026-02-26 14:08:53,664 - INFO -    Trailing Stop: False
2026-02-26 14:08:53,665 - INFO -    ATR Stop Mode: False
2026-02-26 14:08:53,665 - INFO -    Total Entries Signals: 34222
2026-02-26 14:08:53,666 - INFO - 🚀 Numba Simulation Time: 0.0010s
2026-02-26 14:08:53,666 - INFO - 📊 Numba Core Results:
2026-02-26 14:08:53,666 - INFO -    Entry signals found: 34222
2026-02-26 14:08:53,666 - INFO -    Trades executed: 42
2026-02-26 14:08:53,666 - INFO -    Conversion rate: 0.1%
2026-02-26 14:08:53,666 - INFO -    Final equity: $97,151.21
2026-02-26 14:08:53,666 - WARNING -    ⚠️ Low conversion rate (0.1%) - Check parameters
2026-02-26 14:08:53,666 - WARNING -    May indicate: Restrictive filters, large stop distances, or insufficient capital
2026-02-26 14:08:53,667 - INFO -    Exit distribution: STOP=21, TP1=11, TP2=6, RUNNER=4
2026-02-26 14:08:54,916 - INFO -    ✅ Chunk 2 complete: 42 trades, final equity $97,151
2026-02-26 14:08:55,400 - INFO - ✅ Multi-chunk backtest complete: 75 total trades
2026-02-26 14:08:55,404 - INFO - ✅ Backtest complete!
2026-02-26 14:08:55,404 - INFO -    Return: -2.85%
2026-02-26 14:08:55,404 - INFO -    Annualized Return: -1.38%
2026-02-26 14:08:55,405 - INFO -    Sharpe: -0.03
2026-02-26 14:08:55,405 - INFO -    Max DD: -18.98%
2026-02-26 14:08:55,405 - INFO -    MAR Ratio: -0.07
2026-02-26 14:08:55,405 - INFO -    Calmar Ratio: -0.07
2026-02-26 14:08:55,405 - INFO -    Win Rate: 46.7%
2026-02-26 14:08:55,405 - INFO -    Trades: 57188 entries → 75 total exits (including partial)
2026-02-26 14:08:55,412 - INFO - ============================================================
2026-02-26 14:08:55,412 - INFO - 🚀 MODE: PRODUCTION (Fixed Dollar Risk)
2026-02-26 14:08:55,412 - INFO -    • Risk: FIXED DOLLAR ($1000)
2026-02-26 14:08:55,412 - INFO -    • Compounding: DISABLED
2026-02-26 14:08:55,413 - INFO - ============================================================
2026-02-26 14:08:55,414 - INFO - 🚀 Advanced VectorBT Engine initialized
2026-02-26 14:08:55,414 - INFO - 📅 Period: 2022-01-01 to 2024-02-06
2026-02-26 14:08:55,414 - INFO - 🎯 Universe: 566 tickers
2026-02-26 14:08:55,414 - INFO - 🎛️  Liquidity: vol≥100k, $vol≥$98M, ADR≥1.806713014294313%, RVOL≥0.5985392847872089x
2026-02-26 14:08:55,414 - INFO - 🎛️  Position Size: RVOL Danger≥3.0x→50%, Warning≥2.0x→75%
2026-02-26 14:08:55,415 - INFO - ============================================================
2026-02-26 14:08:55,415 - INFO - 🌍 MARKET REGIME FILTER ENABLED
2026-02-26 14:08:55,415 - INFO - ============================================================
2026-02-26 14:08:55,415 - INFO - 📊 Loading SPY and VIX data (2022-01-01 to 2024-02-06)...
2026-02-26 14:08:55,417 - INFO -    ✅ SPY loaded from cache: 526 bars
2026-02-26 14:08:55,419 - INFO -    ✅ VIX loaded from cache: 526 bars
2026-02-26 14:08:55,420 - INFO -    ✅ Market data loaded successfully
2026-02-26 14:08:55,425 - INFO -    ✅ Market regime classifier initialized
2026-02-26 14:08:55,426 - INFO -    🚫 Block Stage 3: True
2026-02-26 14:08:55,426 - INFO -    🚫 Block Stage 4: True
2026-02-26 14:08:55,426 - INFO -    📊 Adjust risk by regime: True
2026-02-26 14:08:55,441 - INFO - 📥 Loading data from 2021-01-01 (buffer) to 2024-02-06...
2026-02-26 14:08:55,441 - INFO - 🎯 Universe size: 566 tickers
2026-02-26 14:08:55,441 - INFO - 🛡️  Survivorship bias protection: PIT mask will determine eligibility quarterly
2026-02-26 14:08:55,441 - INFO - ⚡ Fetching data for 566 tickers in parallel...
2026-02-26 14:08:55,736 - WARNING - ❌ SKIP AMTM: None returned
2026-02-26 14:08:55,742 - WARNING - ❌ SKIP ANSS: None returned
2026-02-26 14:08:56,013 - WARNING - ❌ SKIP ATVI: None returned
2026-02-26 14:08:56,203 - INFO -    100/566...
2026-02-26 14:08:56,311 - WARNING - ❌ SKIP CDAY: None returned
2026-02-26 14:08:56,563 - WARNING - ❌ SKIP CTXS: None returned
2026-02-26 14:08:56,864 - INFO -    200/566...
2026-02-26 14:08:56,872 - WARNING - ❌ SKIP DRE: None returned
2026-02-26 14:08:56,914 - WARNING - ❌ SKIP FB: None returned
2026-02-26 14:08:56,915 - WARNING - ❌ SKIP FBHS: None returned
2026-02-26 14:08:56,920 - WARNING - ❌ SKIP FI: None returned
2026-02-26 14:08:56,934 - WARNING - ❌ SKIP FISV: None returned
2026-02-26 14:08:57,574 - INFO -    300/566...
2026-02-26 14:08:58,377 - INFO -    400/566...
2026-02-26 14:08:59,131 - INFO -    500/566...
2026-02-26 14:08:59,608 - WARNING - ⚠️  Skipped 28 tickers (insufficient data)
2026-02-26 14:08:59,608 - INFO -    First 10 failed: ['AMTM (None returned)', 'ANSS (None returned)', 'ATVI (None returned)', 'CDAY (None returned)', 'CTXS (None returned)', 'DRE (None returned)', 'FB (None returned)', 'FBHS (None returned)', 'FI (None returned)', 'FISV (None returned)']
2026-02-26 14:08:59,608 - INFO - ℹ️  538 tickers with partial data (gaps in history)
2026-02-26 14:08:59,843 - INFO - Memory: 6.4 MB for 538 tickers (core DataFrames)
2026-02-26 14:08:59,843 - INFO - 🛡️  Building Point-in-Time tradeable mask (survivorship bias protection)...
2026-02-26 14:08:59,899 - INFO - PointInTimeUniverse: loaded 1230 ticker membership records
2026-02-26 14:08:59,971 - INFO - Tradeable mask: 376,609/418,564 cells (90.0%) across 538 S&P 500 + 0 non-S&P tickers, 778 trading days
2026-02-26 14:08:59,994 - INFO -    🛡️  Masked out 41,955 cells (10.0%) as non-tradeable (pre-IPO, post-delist, not in S&P 500)
2026-02-26 14:09:00,015 - WARNING -    ⚠️ No precomputed metrics found in cache, will calculate on the fly
2026-02-26 14:09:00,642 - INFO -    ⚠️ Precomputed metrics not available, calculating on the fly...
2026-02-26 14:09:00,676 - INFO -    ⚠️ SMA50 missing in cache, calculating on the fly...
2026-02-26 14:09:01,541 - INFO -    Loading SPY and VIX data for Market Regime...
2026-02-26 14:09:01,541 - INFO - 📊 Loading SPY and VIX data (2021-01-01 to 2024-02-06)...
2026-02-26 14:09:01,544 - INFO -    ✅ SPY loaded from cache: 778 bars
2026-02-26 14:09:01,547 - INFO -    ✅ VIX loaded from cache: 778 bars
2026-02-26 14:09:01,547 - INFO -    ✅ Market data loaded successfully
2026-02-26 14:09:01,556 - INFO -    ✅ Market Data Loaded & Aligned
2026-02-26 14:09:01,556 - INFO - ✅ Loaded: 538 tickers
2026-02-26 14:09:01,556 - INFO - 🛡️  Filtered out 28 tickers (insufficient data)
2026-02-26 14:09:01,556 - INFO -    Date range: 2021-01-04 to 2024-02-06 (778 days)
2026-02-26 14:09:01,556 - INFO -    🔧 Truncating data to start_date: 2022-01-01
2026-02-26 14:09:01,755 - INFO - Memory: ~15.2 MB total after float32 conversion
2026-02-26 14:09:01,772 - INFO - 🎯 Starting advanced backtest with partial exits...
2026-02-26 14:09:01,773 - INFO - 📥 Loading data from 2021-01-01 (buffer) to 2024-02-06...
2026-02-26 14:09:01,773 - INFO - 🎯 Universe size: 538 tickers
2026-02-26 14:09:01,773 - INFO - 🛡️  Survivorship bias protection: PIT mask will determine eligibility quarterly
2026-02-26 14:09:01,773 - INFO - ⚡ Fetching data for 538 tickers in parallel...
2026-02-26 14:09:02,503 - INFO -    100/538...
2026-02-26 14:09:03,099 - INFO -    200/538...
2026-02-26 14:09:03,753 - INFO -    300/538...
2026-02-26 14:09:04,483 - INFO -    400/538...
2026-02-26 14:09:05,193 - INFO -    500/538...
2026-02-26 14:09:05,501 - INFO - ℹ️  538 tickers with partial data (gaps in history)
2026-02-26 14:09:05,736 - INFO - Memory: 6.4 MB for 538 tickers (core DataFrames)
2026-02-26 14:09:05,736 - INFO - 🛡️  Building Point-in-Time tradeable mask (survivorship bias protection)...
2026-02-26 14:09:05,789 - INFO - PointInTimeUniverse: loaded 1230 ticker membership records
2026-02-26 14:09:05,860 - INFO - Tradeable mask: 376,609/418,564 cells (90.0%) across 538 S&P 500 + 0 non-S&P tickers, 778 trading days
2026-02-26 14:09:05,881 - INFO -    🛡️  Masked out 41,955 cells (10.0%) as non-tradeable (pre-IPO, post-delist, not in S&P 500)
2026-02-26 14:09:05,902 - WARNING -    ⚠️ No precomputed metrics found in cache, will calculate on the fly
2026-02-26 14:09:06,527 - INFO -    ⚠️ Precomputed metrics not available, calculating on the fly...
2026-02-26 14:09:06,560 - INFO -    ⚠️ SMA50 missing in cache, calculating on the fly...
2026-02-26 14:09:07,885 - INFO -    Loading SPY and VIX data for Market Regime...
2026-02-26 14:09:07,886 - INFO - 📊 Loading SPY and VIX data (2021-01-01 to 2024-02-06)...
2026-02-26 14:09:07,888 - INFO -    ✅ SPY loaded from cache: 778 bars
2026-02-26 14:09:07,891 - INFO -    ✅ VIX loaded from cache: 778 bars
2026-02-26 14:09:07,891 - INFO -    ✅ Market data loaded successfully
2026-02-26 14:09:07,898 - INFO -    ✅ Market Data Loaded & Aligned
2026-02-26 14:09:07,898 - INFO - ✅ Loaded: 538 tickers
2026-02-26 14:09:07,898 - INFO -    Date range: 2021-01-04 to 2024-02-06 (778 days)
2026-02-26 14:09:07,899 - INFO -    🔧 Truncating data to start_date: 2022-01-01
2026-02-26 14:09:08,114 - INFO - Memory: ~15.2 MB total after float32 conversion
2026-02-26 14:09:08,157 - INFO - 🔍 Calculating entry signals...
2026-02-26 14:09:08,160 - INFO -    🎯 Using TREND signal (close > SMA20)
2026-02-26 14:09:08,161 - INFO -    📊 ADVANCED MODE entries (before Adaptive Filter): 133000
2026-02-26 14:09:08,162 - INFO -       Base entry passed: 133000
2026-02-26 14:09:08,186 - INFO - 🛡️  PIT Universe filter: blocked 0 entries on non-member dates (133000 remaining)
2026-02-26 14:09:08,204 - INFO - 🔧 Applying Adaptive Filter Engine (TIER 1-2-3) - OPTIMIZADO...
2026-02-26 14:09:08,204 - INFO - 🔧 AdaptiveFilterEngine initialized
   ⚡ Applying Adaptive Filter: 100%|████| 526/526 [00:01<00:00, 272.24day/s]
2026-02-26 14:09:10,138 - INFO -    📊 Entries antes de Adaptive Filter: 133000
2026-02-26 14:09:10,138 - INFO -    ❌ Entries rechazadas por TIER:
2026-02-26 14:09:10,138 - INFO -       TIER 1 (Market Safety): 37907
2026-02-26 14:09:10,138 - INFO -       TIER 2 (Dynamic Quality): 42182
2026-02-26 14:09:10,138 - INFO -       TIER 3 (Optional): 93
2026-02-26 14:09:10,138 - INFO -    ✅ Entries finales: 52818

======================================================================
📊 ADAPTIVE FILTER ENGINE - RESUMEN (OPTIMIZADO)
======================================================================
  Total de Rechazos: 80182
  • TIER 1 (Market Safety): 37907
  • TIER 2 (Dynamic Quality): 42182
  TIER 3 (Optional): 93
======================================================================
2026-02-26 14:09:10,270 - INFO - 🔍 Clasificando riesgo por RVOL (VolTrig)...
2026-02-26 14:09:10,275 - INFO -    ☔ Danger (RVOL>=3.0x): 181 entries → Size 50%
2026-02-26 14:09:10,275 - INFO -    ⚠️  Warning (RVOL>=2.0x): 1032 entries → Size 75%
2026-02-26 14:09:10,275 - INFO -    ✅ Safe (RVOL<2.0x): 51605 entries → Size 100%
2026-02-26 14:09:10,275 - INFO - 🔍 Clasificando riesgo por ADR (volatilidad)...
2026-02-26 14:09:10,347 - INFO -    🔥 High ADR (>6.0%): 176 entries → Size 25%
2026-02-26 14:09:10,348 - INFO -    ⚠️  Med ADR (>5.0%): 388 entries → Size 33%
2026-02-26 14:09:10,386 - INFO - 📊 Multi-chunk mode: 526 days → 2 chunks of ~500 days
2026-02-26 14:09:10,386 - INFO - 🔄 Running multi-chunk backtest: 2 chunks...
2026-02-26 14:09:10,391 - INFO -    📦 Chunk 1/2: days 0-263 (capital: $100,000)
2026-02-26 14:09:10,397 - INFO - 🔄 Running single-chunk backtest with Numba Core...
2026-02-26 14:09:10,398 - INFO - 🔄 Converting DataFrames to NumPy arrays (float32 optimization)...
2026-02-26 14:09:10,433 - INFO -    ✅ Arrays prepared: 7.0 MB total
2026-02-26 14:09:10,433 - INFO -    📊 Array shapes: close=(263, 538), high=(263, 538)
2026-02-26 14:09:10,433 - INFO - ⚡ Ejecutando simulación ultra-rápida (Numba Core)...
2026-02-26 14:09:10,433 - INFO -    🚀 Using pre-calculated NumPy arrays (memory optimized - float32)
2026-02-26 14:09:10,438 - INFO -    💰 Numba Core usando FIXED DOLLAR RISK: $1000 → risk_pct=0.0100
2026-02-26 14:09:10,439 - INFO - 🔧 NUMBA CORE PARAMETERS:
2026-02-26 14:09:10,439 - INFO -    Initial Capital: $100,000.00
2026-02-26 14:09:10,439 - INFO -    Risk per Trade: $1,000.00
2026-02-26 14:09:10,439 - INFO -    Use Fixed Risk: True
2026-02-26 14:09:10,439 - INFO -    TP1/TP2 Targets: 1.5515700732935087R / 3.2452974873584886R
2026-02-26 14:09:10,439 - INFO -    TP Distribution: 45% / 30% / 25%
2026-02-26 14:09:10,439 - INFO -    Max Stop %%: 8.0% (decimal: 0.08)
2026-02-26 14:09:10,439 - INFO -    Trailing Stop: False
2026-02-26 14:09:10,439 - INFO -    ATR Stop Mode: False
2026-02-26 14:09:10,440 - INFO -    Total Entries Signals: 21754
2026-02-26 14:09:10,441 - INFO - 🚀 Numba Simulation Time: 0.0014s
2026-02-26 14:09:10,442 - INFO - 📊 Numba Core Results:
2026-02-26 14:09:10,442 - INFO -    Entry signals found: 21754
2026-02-26 14:09:10,442 - INFO -    Trades executed: 33
2026-02-26 14:09:10,442 - INFO -    Conversion rate: 0.2%
2026-02-26 14:09:10,442 - INFO -    Final equity: $97,643.08
2026-02-26 14:09:10,442 - WARNING -    ⚠️ Low conversion rate (0.2%) - Check parameters
2026-02-26 14:09:10,442 - WARNING -    May indicate: Restrictive filters, large stop distances, or insufficient capital
2026-02-26 14:09:10,442 - INFO -    Exit distribution: STOP=16, TP1=11, TP2=3, RUNNER=3
2026-02-26 14:09:10,905 - INFO -    ✅ Chunk 1 complete: 33 trades, final equity $97,643
2026-02-26 14:09:11,355 - INFO -    📦 Chunk 2/2: days 263-526 (capital: $97,643)
2026-02-26 14:09:11,359 - INFO - 🔄 Running single-chunk backtest with Numba Core...
2026-02-26 14:09:11,360 - INFO - 🔄 Converting DataFrames to NumPy arrays (float32 optimization)...
2026-02-26 14:09:11,396 - INFO -    ✅ Arrays prepared: 7.0 MB total
2026-02-26 14:09:11,396 - INFO -    📊 Array shapes: close=(263, 538), high=(263, 538)
2026-02-26 14:09:11,396 - INFO - ⚡ Ejecutando simulación ultra-rápida (Numba Core)...
2026-02-26 14:09:11,396 - INFO -    🚀 Using pre-calculated NumPy arrays (memory optimized - float32)
2026-02-26 14:09:11,402 - INFO -    💰 Numba Core usando FIXED DOLLAR RISK: $1000 → risk_pct=0.0102
2026-02-26 14:09:11,403 - INFO - 🔧 NUMBA CORE PARAMETERS:
2026-02-26 14:09:11,403 - INFO -    Initial Capital: $97,643.08
2026-02-26 14:09:11,403 - INFO -    Risk per Trade: $1,000.00
2026-02-26 14:09:11,403 - INFO -    Use Fixed Risk: True
2026-02-26 14:09:11,403 - INFO -    TP1/TP2 Targets: 1.5515700732935087R / 3.2452974873584886R
2026-02-26 14:09:11,403 - INFO -    TP Distribution: 45% / 30% / 25%
2026-02-26 14:09:11,403 - INFO -    Max Stop %%: 8.0% (decimal: 0.08)
2026-02-26 14:09:11,403 - INFO -    Trailing Stop: False
2026-02-26 14:09:11,403 - INFO -    ATR Stop Mode: False
2026-02-26 14:09:11,403 - INFO -    Total Entries Signals: 31064
2026-02-26 14:09:11,405 - INFO - 🚀 Numba Simulation Time: 0.0013s
2026-02-26 14:09:11,406 - INFO - 📊 Numba Core Results:
2026-02-26 14:09:11,406 - INFO -    Entry signals found: 31064
2026-02-26 14:09:11,406 - INFO -    Trades executed: 39
2026-02-26 14:09:11,406 - INFO -    Conversion rate: 0.1%
2026-02-26 14:09:11,406 - INFO -    Final equity: $106,344.99
2026-02-26 14:09:11,406 - WARNING -    ⚠️ Low conversion rate (0.1%) - Check parameters
2026-02-26 14:09:11,406 - WARNING -    May indicate: Restrictive filters, large stop distances, or insufficient capital
2026-02-26 14:09:11,406 - INFO -    Exit distribution: STOP=19, TP1=13, TP2=5, RUNNER=2
2026-02-26 14:09:11,875 - INFO -    ✅ Chunk 2 complete: 39 trades, final equity $106,345
2026-02-26 14:09:12,328 - INFO - ✅ Multi-chunk backtest complete: 72 total trades
2026-02-26 14:09:12,332 - INFO - ✅ Backtest complete!
2026-02-26 14:09:12,332 - INFO -    Return: 6.34%
2026-02-26 14:09:12,332 - INFO -    Annualized Return: 2.99%
2026-02-26 14:09:12,332 - INFO -    Sharpe: 0.28
2026-02-26 14:09:12,332 - INFO -    Max DD: -15.05%
2026-02-26 14:09:12,332 - INFO -    MAR Ratio: 0.20
2026-02-26 14:09:12,332 - INFO -    Calmar Ratio: 0.20
2026-02-26 14:09:12,332 - INFO -    Win Rate: 50.0%
2026-02-26 14:09:12,332 - INFO -    Trades: 52818 entries → 72 total exits (including partial)
2026-02-26 14:09:12,340 - INFO - ============================================================
2026-02-26 14:09:12,341 - INFO - 🚀 MODE: PRODUCTION (Fixed Dollar Risk)
2026-02-26 14:09:12,341 - INFO -    • Risk: FIXED DOLLAR ($1000)
2026-02-26 14:09:12,341 - INFO -    • Compounding: DISABLED
2026-02-26 14:09:12,341 - INFO - ============================================================
2026-02-26 14:09:12,343 - INFO - 🚀 Advanced VectorBT Engine initialized
2026-02-26 14:09:12,343 - INFO - 📅 Period: 2022-01-01 to 2024-02-06
2026-02-26 14:09:12,343 - INFO - 🎯 Universe: 566 tickers
2026-02-26 14:09:12,343 - INFO - 🎛️  Liquidity: vol≥100k, $vol≥$98M, ADR≥1.6856012333006554%, RVOL≥0.6626489787954711x
2026-02-26 14:09:12,343 - INFO - 🎛️  Position Size: RVOL Danger≥3.0x→50%, Warning≥2.0x→75%
2026-02-26 14:09:12,343 - INFO - ============================================================
2026-02-26 14:09:12,343 - INFO - 🌍 MARKET REGIME FILTER ENABLED
2026-02-26 14:09:12,343 - INFO - ============================================================
2026-02-26 14:09:12,343 - INFO - 📊 Loading SPY and VIX data (2022-01-01 to 2024-02-06)...
2026-02-26 14:09:12,345 - INFO -    ✅ SPY loaded from cache: 526 bars
2026-02-26 14:09:12,348 - INFO -    ✅ VIX loaded from cache: 526 bars
2026-02-26 14:09:12,348 - INFO -    ✅ Market data loaded successfully
2026-02-26 14:09:12,353 - INFO -    ✅ Market regime classifier initialized
2026-02-26 14:09:12,353 - INFO -    🚫 Block Stage 3: True
2026-02-26 14:09:12,353 - INFO -    🚫 Block Stage 4: True
2026-02-26 14:09:12,353 - INFO -    📊 Adjust risk by regime: True
2026-02-26 14:09:12,369 - INFO - 📥 Loading data from 2021-01-01 (buffer) to 2024-02-06...
2026-02-26 14:09:12,370 - INFO - 🎯 Universe size: 566 tickers
2026-02-26 14:09:12,370 - INFO - 🛡️  Survivorship bias protection: PIT mask will determine eligibility quarterly
2026-02-26 14:09:12,370 - INFO - ⚡ Fetching data for 566 tickers in parallel...
2026-02-26 14:09:12,666 - WARNING - ❌ SKIP AMTM: None returned
2026-02-26 14:09:12,669 - WARNING - ❌ SKIP ANSS: None returned
2026-02-26 14:09:12,919 - WARNING - ❌ SKIP ATVI: None returned
2026-02-26 14:09:13,118 - INFO -    100/566...
2026-02-26 14:09:13,250 - WARNING - ❌ SKIP CDAY: None returned
2026-02-26 14:09:13,451 - WARNING - ❌ SKIP CTXS: None returned
2026-02-26 14:09:13,733 - INFO -    200/566...
2026-02-26 14:09:13,742 - WARNING - ❌ SKIP DRE: None returned
2026-02-26 14:09:13,781 - WARNING - ❌ SKIP FB: None returned
2026-02-26 14:09:13,783 - WARNING - ❌ SKIP FBHS: None returned
2026-02-26 14:09:13,785 - WARNING - ❌ SKIP FI: None returned
2026-02-26 14:09:13,800 - WARNING - ❌ SKIP FISV: None returned
2026-02-26 14:09:14,397 - INFO -    300/566...
2026-02-26 14:09:15,159 - INFO -    400/566...
2026-02-26 14:09:15,888 - INFO -    500/566...
2026-02-26 14:09:16,341 - WARNING - ⚠️  Skipped 28 tickers (insufficient data)
2026-02-26 14:09:16,341 - INFO -    First 10 failed: ['AMTM (None returned)', 'ANSS (None returned)', 'ATVI (None returned)', 'CDAY (None returned)', 'CTXS (None returned)', 'DRE (None returned)', 'FB (None returned)', 'FBHS (None returned)', 'FI (None returned)', 'FISV (None returned)']
2026-02-26 14:09:16,341 - INFO - ℹ️  538 tickers with partial data (gaps in history)
2026-02-26 14:09:16,570 - INFO - Memory: 6.4 MB for 538 tickers (core DataFrames)
2026-02-26 14:09:16,570 - INFO - 🛡️  Building Point-in-Time tradeable mask (survivorship bias protection)...
2026-02-26 14:09:16,623 - INFO - PointInTimeUniverse: loaded 1230 ticker membership records
2026-02-26 14:09:16,692 - INFO - Tradeable mask: 376,609/418,564 cells (90.0%) across 538 S&P 500 + 0 non-S&P tickers, 778 trading days
2026-02-26 14:09:16,713 - INFO -    🛡️  Masked out 41,955 cells (10.0%) as non-tradeable (pre-IPO, post-delist, not in S&P 500)
2026-02-26 14:09:16,728 - WARNING -    ⚠️ No precomputed metrics found in cache, will calculate on the fly
2026-02-26 14:09:17,335 - INFO -    ⚠️ Precomputed metrics not available, calculating on the fly...
2026-02-26 14:09:17,369 - INFO -    ⚠️ SMA50 missing in cache, calculating on the fly...
2026-02-26 14:09:18,232 - INFO -    Loading SPY and VIX data for Market Regime...
2026-02-26 14:09:18,232 - INFO - 📊 Loading SPY and VIX data (2021-01-01 to 2024-02-06)...
2026-02-26 14:09:18,235 - INFO -    ✅ SPY loaded from cache: 778 bars
2026-02-26 14:09:18,238 - INFO -    ✅ VIX loaded from cache: 778 bars
2026-02-26 14:09:18,238 - INFO -    ✅ Market data loaded successfully
2026-02-26 14:09:18,246 - INFO -    ✅ Market Data Loaded & Aligned
2026-02-26 14:09:18,246 - INFO - ✅ Loaded: 538 tickers
2026-02-26 14:09:18,247 - INFO - 🛡️  Filtered out 28 tickers (insufficient data)
2026-02-26 14:09:18,247 - INFO -    Date range: 2021-01-04 to 2024-02-06 (778 days)
2026-02-26 14:09:18,247 - INFO -    🔧 Truncating data to start_date: 2022-01-01
2026-02-26 14:09:18,458 - INFO - Memory: ~15.2 MB total after float32 conversion
2026-02-26 14:09:18,477 - INFO - 🎯 Starting advanced backtest with partial exits...
2026-02-26 14:09:18,478 - INFO - 📥 Loading data from 2021-01-01 (buffer) to 2024-02-06...
2026-02-26 14:09:18,478 - INFO - 🎯 Universe size: 538 tickers
2026-02-26 14:09:18,478 - INFO - 🛡️  Survivorship bias protection: PIT mask will determine eligibility quarterly
2026-02-26 14:09:18,478 - INFO - ⚡ Fetching data for 538 tickers in parallel...
2026-02-26 14:09:19,252 - INFO -    100/538...
2026-02-26 14:09:19,895 - INFO -    200/538...
2026-02-26 14:09:20,563 - INFO -    300/538...
2026-02-26 14:09:21,305 - INFO -    400/538...
2026-02-26 14:09:22,074 - INFO -    500/538...
2026-02-26 14:09:22,374 - INFO - ℹ️  538 tickers with partial data (gaps in history)
2026-02-26 14:09:22,610 - INFO - Memory: 6.4 MB for 538 tickers (core DataFrames)
2026-02-26 14:09:22,610 - INFO - 🛡️  Building Point-in-Time tradeable mask (survivorship bias protection)...
2026-02-26 14:09:22,663 - INFO - PointInTimeUniverse: loaded 1230 ticker membership records
2026-02-26 14:09:22,733 - INFO - Tradeable mask: 376,609/418,564 cells (90.0%) across 538 S&P 500 + 0 non-S&P tickers, 778 trading days
2026-02-26 14:09:22,755 - INFO -    🛡️  Masked out 41,955 cells (10.0%) as non-tradeable (pre-IPO, post-delist, not in S&P 500)
2026-02-26 14:09:22,776 - WARNING -    ⚠️ No precomputed metrics found in cache, will calculate on the fly
2026-02-26 14:09:23,396 - INFO -    ⚠️ Precomputed metrics not available, calculating on the fly...
2026-02-26 14:09:23,430 - INFO -    ⚠️ SMA50 missing in cache, calculating on the fly...
2026-02-26 14:09:24,746 - INFO -    Loading SPY and VIX data for Market Regime...
2026-02-26 14:09:24,746 - INFO - 📊 Loading SPY and VIX data (2021-01-01 to 2024-02-06)...
2026-02-26 14:09:24,749 - INFO -    ✅ SPY loaded from cache: 778 bars
2026-02-26 14:09:24,751 - INFO -    ✅ VIX loaded from cache: 778 bars
2026-02-26 14:09:24,752 - INFO -    ✅ Market data loaded successfully
2026-02-26 14:09:24,759 - INFO -    ✅ Market Data Loaded & Aligned
2026-02-26 14:09:24,759 - INFO - ✅ Loaded: 538 tickers
2026-02-26 14:09:24,759 - INFO -    Date range: 2021-01-04 to 2024-02-06 (778 days)
2026-02-26 14:09:24,760 - INFO -    🔧 Truncating data to start_date: 2022-01-01
2026-02-26 14:09:24,976 - INFO - Memory: ~15.2 MB total after float32 conversion
2026-02-26 14:09:25,018 - INFO - 🔍 Calculating entry signals...
2026-02-26 14:09:25,021 - INFO -    🎯 Using TREND signal (close > SMA20)
2026-02-26 14:09:25,022 - INFO -    📊 ADVANCED MODE entries (before Adaptive Filter): 133000
2026-02-26 14:09:25,023 - INFO -       Base entry passed: 133000
2026-02-26 14:09:25,046 - INFO - 🛡️  PIT Universe filter: blocked 0 entries on non-member dates (133000 remaining)
2026-02-26 14:09:25,062 - INFO - 🔧 Applying Adaptive Filter Engine (TIER 1-2-3) - OPTIMIZADO...
2026-02-26 14:09:25,062 - INFO - 🔧 AdaptiveFilterEngine initialized
   ⚡ Applying Adaptive Filter: 100%|████| 526/526 [00:02<00:00, 196.62day/s]
2026-02-26 14:09:27,739 - INFO -    📊 Entries antes de Adaptive Filter: 133000
2026-02-26 14:09:27,739 - INFO -    ❌ Entries rechazadas por TIER:
2026-02-26 14:09:27,739 - INFO -       TIER 1 (Market Safety): 37907
2026-02-26 14:09:27,739 - INFO -       TIER 2 (Dynamic Quality): 41129
2026-02-26 14:09:27,740 - INFO -       TIER 3 (Optional): 82
2026-02-26 14:09:27,740 - INFO -    ✅ Entries finales: 53882

======================================================================
📊 ADAPTIVE FILTER ENGINE - RESUMEN (OPTIMIZADO)
======================================================================
  Total de Rechazos: 79118
  • TIER 1 (Market Safety): 37907
  • TIER 2 (Dynamic Quality): 41129
  TIER 3 (Optional): 82
======================================================================
2026-02-26 14:09:27,863 - INFO - 🔍 Clasificando riesgo por RVOL (VolTrig)...
2026-02-26 14:09:27,867 - INFO -    ☔ Danger (RVOL>=3.0x): 196 entries → Size 50%
2026-02-26 14:09:27,867 - INFO -    ⚠️  Warning (RVOL>=2.0x): 1139 entries → Size 75%
2026-02-26 14:09:27,867 - INFO -    ✅ Safe (RL<2.0x): 52547 entries → Size 100%
2026-02-26 14:09:27,867 - INFO - 🔍 Clasificando riesgo por ADR (volatilidad)...
2026-02-26 14:09:27,940 - INFO -    🔥 High ADR (>6.0%): 151 entries → Size 25%
2026-02-26 14:09:27,941 - INFO -    ⚠️  Med ADR (>5.0%): 328 entries → Size 33%
2026-02-26 14:09:27,980 - INFO - 📊 Multi-chunk mode: 526 days → 2 chunks of ~500 days
2026-02-26 14:09:27,980 - INFO - 🔄 Running multi-chunk backtest: 2 chunks...
2026-02-26 14:09:27,985 - INFO -    📦 Chunk 1/2: days 0-263 (capital: $100,000)
2026-02-26 14:09:27,991 - INFO - 🔄 Running single-chunk backtest with Numba Core...
2026-02-26 14:09:27,991 - INFO - 🔄 Converting DataFrames to NumPy arrays (float32 optimization)...
2026-02-26 14:09:28,028 - INFO -    ✅ Arrays prepared: 7.0 MB total
2026-02-26 14:09:28,028 - INFO -    📊 Array shapes: close=(263, 538), high=(263, 538)
2026-02-26 14:09:28,028 - INFO - ⚡ Ejecutando simulación ultra-rápida (Numba Core)...
2026-02-26 14:09:28,028 - INFO -    🚀 Using pre-calculated NumPy arrays (memory optimized - float32)
2026-02-26 14:09:28,034 - INFO -    💰 Numba Core usando FIXED DOLLAR RISK: $1000 → risk_pct=0.0100
2026-02-26 14:09:28,034 - INFO - 🔧 NUMBA CORE PARAMETERS:
2026-02-26 14:09:28,035 - INFO -    Initial Capital: $100,000.00
2026-02-26 14:09:28,035 - INFO -    Risk per Trade: $1,000.00
2026-02-26 14:09:28,035 - INFO -    Use Fixed Risk: True
2026-02-26 14:09:28,035 - INFO -    TP1/TP2 Targets: 1.8353241992858402R / 3.0664182991871756R
2026-02-26 14:09:28,035 - INFO -    TP Distribution: 45% / 30% / 25%
2026-02-26 14:09:28,035 - INFO -    Max Stop %%: 8.0% (decimal: 0.08)
2026-02-26 14:09:28,035 - INFO -    Trailing Stop: False
2026-02-26 14:09:28,035 - INFO -    ATR Stop Mode: False
2026-02-26 14:09:28,035 - INFO -    Total Entries Signals: 21072
2026-02-26 14:09:28,036 - INFO - 🚀 Numba Simulation Time: 0.0011s
2026-02-26 14:09:28,037 - INFO - 📊 Numba Core Results:
2026-02-26 14:09:28,037 - INFO -    Entry signals found: 21072
2026-02-26 14:09:28,037 - INFO -    Trades executed: 34
2026-02-26 14:09:28,037 - INFO -    Conversion rate: 0.2%
2026-02-26 14:09:28,037 - INFO -    Final equity: $92,593.90
2026-02-26 14:09:28,037 - WARNING -    ⚠️ Low conversion rate (0.2%) - Check parameters
2026-02-26 14:09:28,037 - WARNING -    May indicate: Restrictive filters, large stop distances, or insufficient capital
2026-02-26 14:09:28,037 - INFO -    Exit distribution: STOP=19, TP1=7, TP2=4, RUNNER=4
2026-02-26 14:09:28,508 - INFO -    ✅ Chunk 1 complete: 34 trades, final equity $92,594
2026-02-26 14:09:28,971 - INFO -    📦 Chunk 2/2: days 263-526 (capital: $92,594)
2026-02-26 14:09:28,977 - INFO - 🔄 Running single-chunk backtest with Numba Core...
2026-02-26 14:09:28,977 - INFO - 🔄 Converting DataFrames to NumPy arrays (float32 optimization)...
2026-02-26 14:09:29,016 - INFO -    ✅ Arrays prepared: 7.0 MB total
2026-02-26 14:09:29,016 - INFO -    📊 Array shapes: close=(263, 538), high=(263, 538)
2026-02-26 14:09:29,017 - INFO - ⚡ Ejecutando simulación ultra-rápida (Numba Core)...
2026-02-26 14:09:29,017 - INFO -    🚀 Using pre-calculated NumPy arrays (memory optimized - float32)
2026-02-26 14:09:29,024 - INFO -    💰 Numba Core usando FIXED DOLLAR RISK: $1000 → risk_pct=0.0108
2026-02-26 14:09:29,024 - INFO - 🔧 NUMBA CORE PARAMETERS:
2026-02-26 14:09:29,024 - INFO -    Initial Capital: $92,593.90
2026-02-26 14:09:29,024 - INFO -    Risk per Trade: $1,000.00
2026-02-26 14:09:29,024 - INFO -    Use Fixed Risk: True
2026-02-26 14:09:29,024 - INFO -    TP1/TP2 Targets: 1.8353241992858402R / 3.0664182991871756R
2026-02-26 14:09:29,024 - INFO -    TP Distribution: 45% / 30% / 25%
2026-02-26 14:09:29,024 - INFO -    Max Stop %%: 8.0% (decimal: 0.08)
2026-02-26 14:09:29,024 - INFO -    Trailing Stop: False
2026-02-26 14:09:29,024 - INFO -    ATR Stop Mode: False
2026-02-26 14:09:29,025 - INFO -    Total Entries Signals: 32810
2026-02-26 14:09:29,026 - INFO - 🚀 Numba Simulation Time: 0.0016s
2026-02-26 14:09:29,027 - INFO - 📊 Numba Core Results:
2026-02-26 14:09:29,027 - INFO -    Entry signals found: 32810
2026-02-26 14:09:29,027 - INFO -    Trades executed: 34
2026-02-26 14:09:29,027 - INFO -    Conversion rate: 0.1%
2026-02-26 14:09:29,027 - INFO -    Final equity: $101,133.61
2026-02-26 14:09:29,027 - WARNING -    ⚠️ Low conversion rate (0.1%) - Check parameters
2026-02-26 14:09:29,027 - WARNING -    May indicate: Restrictive filters, large stop distances, or insufficient capital
2026-02-26 14:09:29,027 - INFO -    Exit distribution: STOP=15, TP1=10, TP2=6, RUNNER=3
2026-02-26 14:09:29,523 - INFO -    ✅ Chunk 2 complete: 34 trades, final equity $101,134
2026-02-26 14:09:29,985 - INFO - ✅ Multi-chunk backtest complete: 68 total trades
2026-02-26 14:09:29,990 - INFO - ✅ Backtest complete!
2026-02-26 14:09:29,991 - INFO -    Return: 1.13%
2026-02-26 14:09:29,991 - INFO -    Annualized Return: 0.54%
2026-02-26 14:09:29,991 - INFO -    Sharpe: 0.11
2026-02-26 14:09:29,991 - INFO -    Max DD: -20.14%
2026-02-26 14:09:29,991 - INFO -    MAR Ratio: 0.03
2026-02-26 14:09:29,991 - INFO -    Calmar Ratio: 0.03
2026-02-26 14:09:29,991 - INFO -    Win Rate: 48.5%
2026-02-26 14:09:29,991 - INFO -    Trades: 53882 entries → 68 total exits (including partial)
2026-02-26 14:09:29,999 - INFO - ============================================================
2026-02-26 14:09:29,999 - INFO - 🚀 MODE: PRODUCTION (Fixed Dollar Risk)
2026-02-26 14:09:29,999 - INFO -    • Risk: FIXED DOLLAR ($1000)
2026-02-26 14:09:29,999 - INFO -    • Compounding: DISABLED
2026-02-26 14:09:29,999 - INFO - ============================================================
2026-02-26 14:09:30,001 - INFO - 🚀 Advanced VectorBT Engine initialized
2026-02-26 14:09:30,001 - INFO - 📅 Period: 2022-01-01 to 2024-02-06
2026-02-26 14:09:30,001 - INFO - 🎯 Universe: 566 tickers
2026-02-26 14:09:30,001 - INFO - 🎛️  Liquidity: vol≥100k, $vol≥$98M, ADR≥1.8018723350428347%, RVOL≥0.718013860286473x
2026-02-26 14:09:30,001 - INFO - 🎛️  Position Size: RVOL Danger≥3.0x→50%, Warning≥2.0x→75%
2026-02-26 14:09:30,001 - INFO - ============================================================
2026-02-26 14:09:30,002 - INFO - 🌍 MARKET REGIME FILTER ENABLED
2026-02-26 14:09:30,002 - INFO - ============================================================
2026-02-26 14:09:30,002 - INFO - 📊 Loading SPY and VIX data (2022-01-01 to 2024-02-06)...
2026-02-26 14:09:30,004 - INFO -    ✅ SPY loaded from cache: 526 bars
2026-02-26 14:09:30,008 - INFO -    ✅ VIX loaded from cache: 526 bars
2026-02-26 14:09:30,008 - INFO -    ✅ Market data loaded successfully
2026-02-26 14:09:30,013 - INFO -    ✅ Market regime classifier initialized
2026-02-26 14:09:30,013 - INFO -    🚫 Block Stage 3: True
2026-02-26 14:09:30,014 - INFO -    🚫 Block Stage 4: True
2026-02-26 14:09:30,014 - INFO -    📊 Adjust risk by regime: True
2026-02-26 14:09:30,028 - INFO - 📥 Loading data from 2021-01-01 (buffer) to 2024-02-06...
2026-02-26 14:09:30,028 - INFO - 🎯 Universe size: 566 tickers
2026-02-26 14:09:30,028 - INFO - 🛡️  Survivorship bias protection: PIT mask will determine eligibility quarterly
2026-02-26 14:09:30,028 - INFO - ⚡ Fetching data for 566 tickers in parallel...
2026-02-26 14:09:30,333 - WARNING - ❌ SKIP AMTM: None returned
2026-02-26 14:09:30,340 - WARNING - ❌ SKIP ANSS: None returned
2026-02-26 14:09:30,595 - WARNING - ❌ SKIP ATVI: None returned
2026-02-26 14:09:30,804 - INFO -    100/566...
2026-02-26 14:09:30,941 - WARNING - ❌ SKIP CDAY: None returned
2026-02-26 14:09:31,145 - WARNING - ❌ SKIP CTXS: None returned
2026-02-26 14:09:31,449 - INFO -    200/566...
2026-02-26 14:09:31,459 - WARNING - ❌ SKIP DRE: None returned
2026-02-26 14:09:31,503 - WARNING - ❌ SKIP FB: None returned
2026-02-26 14:09:31,504 - WARNING - ❌ SKIP FBHS: None returned
2026-02-26 14:09:31,504 - WARNING - ❌ SKIP FI: None returned
2026-02-26 14:09:31,528 - WARNING - ❌ SKIP FISV: None returned
2026-02-26 14:09:32,146 - INFO -    300/566...
2026-02-26 14:09:32,957 - INFO -    400/566...
2026-02-26 14:09:33,683 - INFO -    500/566...
2026-02-26 14:09:34,163 - WARNING - ⚠️  Skipped 28 tickers (insufficient data)
2026-02-26 14:09:34,163 - INFO -    First 10 failed: ['AMTM (None returned)', 'ANSS (None returned)', 'ATVI (None returned)', 'CDAY (None returned)', 'CTXS (None returned)', 'DRE (None returned)', 'FB (None returned)', 'FBHS (None returned)', 'FI (None returned)', 'FISV (None returned)']
2026-02-26 14:09:34,163 - INFO - ℹ️  538 tickers with partial data (gaps in history)
2026-02-26 14:09:34,381 - INFO - Memory: 6.4 MB for 538 tickers (core DataFrames)
2026-02-26 14:09:34,382 - INFO - 🛡️  Building Point-in-Time tradeable mask (survivorship bias protection)...
2026-02-26 14:09:34,433 - INFO - PointInTimeUniverse: loaded 1230 ticker membership records
2026-02-26 14:09:34,500 - INFO - Tradeable mask: 376,609/418,564 cells (90.0%) across 538 S&P 500 + 0 non-S&P tickers, 778 trading days
2026-02-26 14:09:34,520 - INFO -    🛡️  Masked out 41,955 cells (10.0%) as non-tradeable (pre-IPO, post-delist, not in S&P 500)
2026-02-26 14:09:34,535 - WARNING -    ⚠️ No precomputed metrics found in cache, will calculate on the fly
2026-02-26 14:09:35,129 - INFO -    ⚠️ Precomputed metrics not available, calculating on the fly...
2026-02-26 14:09:35,160 - INFO -    ⚠️ SMA50 missing in cache, calculating on the fly...
2026-02-26 14:09:35,978 - INFO -    Loading SPY and VIX data for Market Regime...
2026-02-26 14:09:35,978 - INFO - 📊 Loading SPY and VIX data (2021-01-01 to 2024-02-06)...
2026-02-26 14:09:35,981 - INFO -    ✅ SPY loaded from cache: 778 bars
2026-02-26 14:09:35,984 - INFO -    ✅ VIX loaded from cache: 778 bars
2026-02-26 14:09:35,985 - INFO -    ✅ Market data loaded successfully
2026-02-26 14:09:35,992 - INFO -    ✅ Market Data Loaded & Aligned
2026-02-26 14:09:35,992 - INFO - ✅ Loaded: 538 tickers
2026-02-26 14:09:35,992 - INFO - 🛡️  Filtered out 28 tickers (insufficient data)
2026-02-26 14:09:35,992 - INFO -    Date range: 2021-01-04 to 2024-02-06 (778 days)
2026-02-26 14:09:35,993 - INFO -    🔧 Truncating data to start_date: 2022-01-01
2026-02-26 14:09:36,193 - INFO - Memory: ~15.2 MB total after float32 conversion
2026-02-26 14:09:36,210 - INFO - 🎯 Starting advanced backtest with partial exits...
2026-02-26 14:09:36,211 - INFO - 📥 Loading data from 2021-01-01 (buffer) to 2024-02-06...
2026-02-26 14:09:36,211 - INFO - 🎯 Universe size: 538 tickers
2026-02-26 14:09:36,211 - INFO - 🛡️  Survivorship bias protection: PIT mask will determine eligibility quarterly
2026-02-26 14:09:36,211 - INFO - ⚡ Fetching data for 538 tickers in parallel...
2026-02-26 14:09:36,953 - INFO -    100/538...
2026-02-26 14:09:37,559 - INFO -    200/538...
2026-02-26 14:09:38,205 - INFO -    300/538...
2026-02-26 14:09:38,935 - INFO -    400/538...
2026-02-26 14:09:39,751 - INFO -    500/538...
2026-02-26 14:09:40,043 - INFO - ℹ️  538 tickers with partial data (gaps in history)
2026-02-26 14:09:40,285 - INFO - Memory: 6.4 MB for 538 tickers (core DataFrames)
2026-02-26 14:09:40,285 - INFO - 🛡️  Building Point-in-Time tradeable mask (survivorship bias protection)...
2026-02-26 14:09:40,338 - INFO - PointInTimeUniverse: loaded 1230 ticker membership records
2026-02-26 14:09:40,409 - INFO - Tradeable mask: 376,609/418,564 cells (90.0%) across 538 S&P 500 + 0 non-S&P tickers, 778 trading days
2026-02-26 14:09:40,430 - INFO -    🛡️  Masked out 41,955 cells (10.0%) as non-tradeable (pre-IPO, post-delist, not in S&P 500)
2026-02-26 14:09:40,453 - WARNING -    ⚠️ No precomputed metrics found in cache, will calculate on the fly
2026-02-26 14:09:41,069 - INFO -    ⚠️ Precomputed metrics not available, calculating on the fly...
2026-02-26 14:09:41,103 - INFO -    ⚠️ SMA50 missing in cache, calculating on the fly...
2026-02-26 14:09:42,415 - INFO -    Loading SPY and VIX data for Market Regime...
2026-02-26 14:09:42,415 - INFO - 📊 Loading SPY and VIX data (2021-01-01 to 2024-02-06)...
2026-02-26 14:09:42,418 - INFO -    ✅ SPY loaded from cache: 778 bars
2026-02-26 14:09:42,421 - INFO -    ✅ VIX loaded from cache: 778 bars
2026-02-26 14:09:42,421 - INFO -    ✅ Market data loaded successfully
2026-02-26 14:09:42,428 - INFO -    ✅ Market Data Loaded & Aligned
2026-02-26 14:09:42,428 - INFO - ✅ Loaded: 538 tickers
2026-02-26 14:09:42,428 - INFO -    Date range: 2021-01-04 to 2024-02-06 (778 days)
2026-02-26 14:09:42,429 - INFO -    🔧 Truncating data to start_date: 2022-01-01
2026-02-26 14:09:42,645 - INFO - Memory: ~15.2 MB total after float32 conversion
2026-02-26 14:09:42,688 - INFO - 🔍 Calculating entry signals...
2026-02-26 14:09:42,691 - INFO -    🎯 Using TREND signal (close > SMA20)
2026-02-26 14:09:42,692 - INFO -    📊 ADVANCED MODE entries (before Adaptive Filter): 133000
2026-02-26 14:09:42,692 - INFO -       Base entry passed: 133000
2026-02-26 14:09:42,717 - INFO - 🛡️  PIT Universe filter: blocked 0 entries on non-member dates (133000 remaining)
2026-02-26 14:09:42,733 - INFO - 🔧 Applying Adaptive Filter Engine (TIER 1-2-3) - OPTIMIZADO...
2026-02-26 14:09:42,733 - INFO - 🔧 AdaptiveFilterEngine initialized
   ⚡ Applying Adaptive Filter: 100%|████| 526/526 [00:01<00:00, 278.09day/s]
2026-02-26 14:09:44,626 - INFO -    📊 Entries antes de Adaptive Filter: 133000
2026-02-26 14:09:44,627 - INFO -    ❌ Entries rechazadas por TIER:
2026-02-26 14:09:44,636 - INFO -       TIER 1 (Market Safety): 37907
2026-02-26 14:09:44,636 - INFO -       TIER 2 (Dynamic Quality): 50101
2026-02-26 14:09:44,636 - INFO -       TIER 3 (Optional): 68
2026-02-26 14:09:44,636 - INFO -    ✅ Entries finales: 44924

======================================================================
📊 ADAPTIVE FILTER ENGINE - RESUMEN (OPTIMIZADO)
======================================================================
  Total de Rechazos: 88076
  • TIER 1 (Market Safety): 37907
  • TIER 2 (Dynamic Quality): 50101
  TIER 3 (Optional): 68
======================================================================
2026-02-26 14:09:44,784 - INFO - 🔍 Clasificando riesgo por RVOL (VolTrig)...
2026-02-26 14:09:44,789 - INFO -    ☔ Danger (RVOL>=3.0x): 194 entries → Size 50%
2026-02-26 14:09:44,790 - INFO -    ⚠️  Warning (RVOL>=2.0x): 1091 entries → Size 75%
2026-02-26 14:09:44,790 - INFO -    ✅ Safe (RVOL<2.0x): 43639 entries → Size 100%
2026-02-26 14:09:44,790 - INFO - 🔍 Clasificando riesgo por ADR (volatilidad)...
2026-02-26 14:09:44,860 - INFO -    🔥 High ADR (>6.0%): 137 entries → Size 25%
2026-02-26 14:09:44,861 - INFO -    ⚠️  Med ADR (>5.0%): 297 entries → Size 33%
2026-02-26 14:09:44,899 - INFO - 📊 Multi-chunk mode: 526 days → 2 chunks of ~500 days
2026-02-26 14:09:44,900 - INFO - 🔄 Running multi-chunk backtest: 2 chunks...
2026-02-26 14:09:44,905 - INFO -    📦 Chunk 1/2: days 0-263 (capital: $100,000)
2026-02-26 14:09:44,910 - INFO - 🔄 Running single-chunk backtest with Numba Core...
2026-02-26 14:09:44,910 - INFO - 🔄 Converting DataFrames to NumPy arrays (float32 optimization)...
2026-02-26 14:09:44,944 - INFO -    ✅ Arrays prepared: 7.0 MB total
2026-02-26 14:09:44,944 - INFO -    📊 Array shapes: close=(263, 538), high=(263, 538)
2026-02-26 14:09:44,944 - INFO - ⚡ Ejecutando simulación ultra-rápida (Numba Core)...
2026-02-26 14:09:44,944 - INFO -    🚀 Using pre-calculated NumPy arrays (memory optimized - float32)
2026-02-26 14:09:44,949 - INFO -    💰 Numba Core usando FIXED DOLLAR RISK: $1000 → risk_pct=0.0100
2026-02-26 14:09:44,950 - INFO - 🔧 NUMBA CORE PARAMETERS:
2026-02-26 14:09:44,950 - INFO -    Initial Capital: $100,000.00
2026-02-26 14:09:44,950 - INFO -    Risk per Trade: $1,000.00
2026-02-26 14:09:44,950 - INFO -    Use Fixed Risk: True
2026-02-26 14:09:44,950 - INFO -    TP1/TP2 Targets: 1.996531929576393R / 3.5182545027770864R
2026-02-26 14:09:44,950 - INFO -    TP Distribution: 45% / 30% / 25%
2026-02-26 14:09:44,950 - INFO -    Max Stop %%: 8.0% (decimal: 0.08)
2026-02-26 14:09:44,950 - INFO -    Trailing Stop: False
2026-02-26 14:09:44,950 - INFO -    ATR Stop Mode: False
2026-02-26 14:09:44,950 - INFO -    Total Entries Signals: 18559
2026-02-26 14:09:44,952 - INFO - 🚀 Numba Simulation Time: 0.0012s
2026-02-26 14:09:44,952 - INFO - 📊 Numba Core Results:
2026-02-26 14:09:44,952 - INFO -    Entry signals found: 18559
2026-02-26 14:09:44,952 - INFO -    Trades executed: 24
2026-02-26 14:09:44,952 - INFO -    Conversion rate: 0.1%
2026-02-26 14:09:44,952 - INFO -    Final equity: $89,813.38
2026-02-26 14:09:44,952 - WARNING -    ⚠️ Low conversion rate (0.1%) - Check parameters
2026-02-26 14:09:44,952 - WARNING -    May indicate: Restrictive filters, large stop distances, or insufficient capital
2026-02-26 14:09:44,953 - INFO -    Exit distribution: STOP=17, TP1=5, TP2=1, RUNNER=1
202-26 14:09:45,416 - INFO -    ✅ Chunk 1 complete: 24 trades, final equity $89,813
2026-02-26 14:09:45,872 - INFO -    📦 Chunk 2/2: days 263-526 (capital: $89,813)
2026-02-26 14:09:45,878 - INFO - 🔄 Running single-chunk backtest with Numba Core...
2026-02-26 14:09:45,878 - INFO - 🔄 Converting DataFrames to NumPy arrays (float32 optimization)...
2026-02-26 14:09:45,914 - INFO -    ✅ Arrays prepared: 7.0 MB total
2026-02-26 14:09:45,914 - INFO -    📊 Array shapes: close=(263, 538), high=(263, 538)
2026-02-26 14:09:45,914 - INFO - ⚡ Ejecutando simulación ultra-rápida (Numba Core)...
2026-02-26 14:09:45,914 - INFO -    🚀 Using pre-calculated NumPy arrays (memory optimized - float32)
2026-02-26 14:09:45,919 - INFO -    💰 Numba Core usando FIXED DOLLAR RISK: $1000 → risk_pct=0.0111
2026-02-26 14:09:45,920 - INFO - 🔧 NUMBA CORE PARAMETERS:
2026-02-26 14:09:45,920 - INFO -    Initial Capital: $89,813.38
2026-02-26 14:09:45,920 - INFO -    Risk per Trade: $1,000.00
2026-02-26 14:09:45,920 - INFO -    Use Fixed Risk: True
2026-02-26 14:09:45,920 - INFO -    TP1/TP2 Targets: 1.996531929576393R / 3.5182545027770864R
2026-02-26 14:09:45,920 - INFO -    TP Distribution: 45% / 30% / 25%
2026-02-26 14:09:45,920 - INFO -    Max Stop %%: 8.0% (decimal: 0.08)
2026-02-26 14:09:45,920 - INFO -    Trailing Stop: False
2026-02-26 14:09:45,920 - INFO -    ATR Stop Mode: False
2026-02-26 14:09:45,920 - INFO -    Total Entries Signals: 26365
2026-02-26 14:09:45,922 - INFO - 🚀 Numba Simulation Time: 0.0013s
2026-02-26 14:09:45,923 - INFO - 📊 Numba Core Results:
2026-02-26 14:09:45,923 - INFO -    Entry signals found: 26365
2026-02-26 14:09:45,923 - INFO -    Trades executed: 32
2026-02-26 14:09:45,923 - INFO -    Conversion rate: 0.1%
2026-02-26 14:09:45,923 - INFO -    Final equity: $99,407.04
2026-02-26 14:09:45,923 - WARNING -    ⚠️ Low conversion rate (0.1%) - Check parameters
2026-02-26 14:09:45,923 - WARNING -    May indicate: Restrictive filters, large stop distances, or insufficient capital
2026-02-26 14:09:45,924 - INFO -    Exit distribution: STOP=14, TP1=10, TP2=5, RUNNER=3
2026-02-26 14:09:46,393 - INFO -    ✅ Chunk 2 complete: 32 trades, final equity $99,407
2026-02-26 14:09:46,854 - INFO - ✅ Multi-chunk backtest complete: 56 total trades
2026-02-26 14:09:46,858 - INFO - ✅ Backtest complete!
2026-02-26 14:09:46,858 - INFO -    Return: -0.59%
2026-02-26 14:09:46,858 - INFO -    Annualized Return: -0.28%
2026-02-26 14:09:46,858 - INFO -    Sharpe: 0.05
2026-02-26 14:09:46,858 - INFO -    Max DD: -18.20%
2026-02-26 14:09:46,858 - INFO -    MAR Ratio: -0.02
2026-02-26 14:09:46,858 - INFO -    Calmar Ratio: -0.02
2026-02-26 14:09:46,858 - INFO -    Win Rate: 44.6%
2026-02-26 14:09:46,858 - INFO -    Trades: 44924 entries → 56 total exits (including partial)
2026-02-26 14:09:46,866 - INFO - ============================================================
2026-02-26 14:09:46,866 - INFO - 🚀 MODE: PRODUCTION (Fixed Dollar Risk)
2026-02-26 14:09:46,866 - INFO -    • Risk: FIXED DOLLAR ($1000)
2026-02-26 14:09:46,866 - INFO -    • Compounding: DISABLED
2026-02-26 14:09:46,866 - INFO - ============================================================
2026-02-26 14:09:46,868 - INFO - 🚀 Advanced VectorBT Engine initialized
2026-02-26 14:09:46,868 - INFO - 📅 Period: 2022-01-01 to 2024-02-06
2026-02-26 14:09:46,868 - INFO - 🎯 Universe: 566 tickers
2026-02-26 14:09:46,868 - INFO - 🎛️  Liquidity: vol≥100k, $vol≥$98M, ADR≥1.5181059144961198%, RVOL≥0.6198697378393272x
2026-02-26 14:09:46,868 - INFO - 🎛️  Position Size: RVOL Danger≥3.0x→50%, Warning≥2.0x→75%
2026-02-26 14:09:46,868 - INFO - ============================================================
2026-02-26 14:09:46,869 - INFO - 🌍 MARKET REGIME FILTER ENABLED
2026-02-26 14:09:46,869 - INFO - ============================================================
2026-02-26 14:09:46,869 - INFO - 📊 Loading SPY and VIX data (2022-01-01 to 2024-02-06)...
2026-02-26 14:09:46,871 - INFO -    ✅ SPY loaded from cache: 526 bars
2026-02-26 14:09:46,873 - INFO -    ✅ VIX loaded from cache: 526 bars
2026-02-26 14:09:46,874 - INFO -    ✅ Market data loaded successfully
2026-02-26 14:09:46,878 - INFO -    ✅ Market regime classifier initialized
2026-02-26 14:09:46,879 - INFO -    🚫 Block Stage 3: True
2026-02-26 14:09:46,879 - INFO -    🚫 Block Stage 4: True
2026-02-26 14:09:46,879 - INFO -    📊 Adjust risk by regime: True
2026-02-26 14:09:46,894 - INFO - 📥 Loading data from 2021-01-01 (buffer) to 2024-02-06...
2026-02-26 14:09:46,895 - INFO - 🎯 Universe size: 566 tickers
2026-02-26 14:09:46,895 - INFO - 🛡️  Survivorship bias protection: PIT mask will determine eligibility quarterly
2026-02-26 14:09:46,895 - INFO - ⚡ Fetching data for 566 tickers in parallel...
2026-02-26 14:09:47,195 - WARNING - ❌ SKIP AMTM: None returned
2026-02-26 14:09:47,197 - WARNING - ❌ SKIP ANSS: None returned
2026-02-26 14:09:47,456 - WARNING - ❌ SKIP ATVI: None returned
2026-02-26 14:09:47,642 - INFO -    100/566...
2026-02-26 14:09:47,666 - WARNING - ❌ SKIP CDAY: None returned
2026-02-26 14:09:48,034 - WARNING - ❌ SKIP CTXS: None returned
2026-02-26 14:09:48,325 - INFO -    200/566...
2026-02-26 14:09:48,334 - WARNING - ❌ SKIP DRE: None returned
2026-02-26 14:09:48,377 - WARNING - ❌ SKIP FB: None returned
2026-02-26 14:09:48,379 - WARNING - ❌ SKIP FBHS: None returned
2026-02-26 14:09:48,380 - WARNING - ❌ SKIP FI: None returned
2026-02-26 14:09:48,403 - WARNING - ❌ SKIP FISV: None returned
2026-02-26 14:09:49,495 - INFO -    300/566...
2026-02-26 14:09:50,269 - INFO -    400/566...
2026-02-26 14:09:51,007 - INFO -    500/566...
2026-02-26 14:09:51,462 - WARNING - ⚠️  Skipped 28 tickers (insufficient data)
2026-02-26 14:09:51,462 - INFO -    First 10 failed: ['AMTM (None returned)', 'ANSS (None returned)', 'ATVI (None returned)', 'CDAY (None returned)', 'CTXS (None returned)', 'DRE (None returned)', 'FB (None returned)', 'FBHS (None returned)', 'FI (None returned)', 'FISV (None returned)']
2026-02-26 14:09:51,462 - INFO - ℹ️  538 tickers with partial data (gaps in history)
2026-02-26 14:09:51,693 - INFO - Memory: 6.4 MB for 538 tickers (core DataFrames)
2026-02-26 14:09:51,693 - INFO - 🛡️  Building Point-in-Time tradeable mask (survivorship bias protection)...
2026-02-26 14:09:51,748 - INFO - PointInTimeUniverse: loaded 1230 ticker membership records
2026-02-26 14:09:51,816 - INFO - Tradeable mask: 376,609/418,564 cells (90.0%) across 538 S&P 500 + 0 non-S&P tickers, 778 trading days
2026-02-26 14:09:51,836 - INFO -    🛡️  Masked out 41,955 cells (10.0%) as non-tradeable (pre-IPO, post-delist, not in S&P 500)
2026-02-26 14:09:51,853 - WARNING -    ⚠️ No precomputed metrics found in cache, will calculate on the fly
2026-02-26 14:09:52,461 - INFO -    ⚠️ Precomputed metrics not available, calculating on the fly...
2026-02-26 14:09:52,494 - INFO -    ⚠️ SMA50 missing in cache, calculating on the fly...
2026-02-26 14:09:53,362 - INFO -    Loading SPY and VIX data for Market Regime...
2026-02-26 14:09:53,362 - INFO - 📊 Loading SPY and VIX data (2021-01-01 to 2024-02-06)...
2026-02-26 14:09:53,365 - INFO -    ✅ SPY loaded from cache: 778 bars
2026-02-26 14:09:53,368 - INFO -    ✅ VIX loaded from cache: 778 bars
2026-02-26 14:09:53,368 - INFO -    ✅ Market data loaded successfully
2026-02-26 14:09:53,375 - INFO -    ✅ Market Data Loaded & Aligned
2026-02-26 14:09:53,376 - INFO - ✅ Loaded: 538 tickers
2026-02-26 14:09:53,376 - INFO - 🛡️  Filtered out 28 tickers (insufficient data)
2026-02-26 14:09:53,376 - INFO -    Date range: 2021-01-04 to 2024-02-06 (778 days)
2026-02-26 14:09:53,376 - INFO -    🔧 Truncating data to start_date: 2022-01-01
2026-02-26 14:09:53,589 - INFO - Memory: ~15.2 MB total after float32 conversion
2026-02-26 14:09:53,607 - INFO - 🎯 Starting advanced backtest with partial exits...
2026-02-26 14:09:53,608 - INFO - 📥 Loading data from 2021-01-01 (buffer) to 2024-02-06...
2026-02-26 14:09:53,608 - INFO - 🎯 Universe size: 538 tickers
2026-02-26 14:09:53,608 - INFO - 🛡️  Survivorship bias protection: PIT mask will determine eligibility quarterly
2026-02-26 14:09:53,609 - INFO - ⚡ Fetching data for 538 tickers in parallel...
2026-02-26 14:09:54,380 - INFO -    100/538...
2026-02-26 14:09:55,019 - INFO -    200/538...
2026-02-26 14:09:55,678 - INFO -    300/538...
2026-02-26 14:09:56,457 - INFO -    400/538...
2026-02-26 14:09:57,188 - INFO -    500/538...
2026-02-26 14:09:57,457 - INFO - ℹ️  538 tickers with partial data (gaps in history)
2026-02-26 14:09:57,694 - INFO - Memory: 6.4 MB for 538 tickers (core DataFrames)
2026-02-26 14:09:57,695 - INFO - 🛡️  Building Point-in-Time tradeable mask (survivorship bias protection)...
2026-02-26 14:09:57,750 - INFO - PointInTimeUniverse: loaded 1230 ticker membership records
2026-02-26 14:09:57,822 - INFO - Tradeable mask: 376,609/418,564 cells (90.0%) across 538 S&P 500 + 0 non-S&P tickers, 778 trading days
2026-02-26 14:09:57,843 - INFO -    🛡️  Masked out 41,955 cells (10.0%) as non-tradeable (pre-IPO, post-delist, not in S&P 500)
2026-02-26 14:09:57,863 - WARNING -    ⚠️ No precomputed metrics found in cache, will calculate on the fly
2026-02-26 14:09:58,552 - INFO -    ⚠️ Precomputed metrics not available, calculating on the fly...
2026-02-26 14:09:58,587 - INFO -    ⚠️ SMA50 missing in cache, calculating on the fly...
2026-02-26 14:10:00,701 - INFO -    Loading SPY and VIX data for Market Regime...
2026-02-26 14:10:00,702 - INFO - 📊 Loading SPY and VIX data (2021-01-01 to 2024-02-06)...
2026-02-26 14:10:00,705 - INFO -    ✅ SPY loaded from cache: 778 bars
2026-02-26 14:10:00,708 - INFO -    ✅ VIX loaded from cache: 778 bars
2026-02-26 14:10:00,708 - INFO -    ✅ Market data loaded successfully
2026-02-26 14:10:00,715 - INFO -    ✅ Market Data Loaded & Aligned
2026-02-26 14:10:00,716 - INFO - ✅ Loaded: 538 tickers
2026-02-26 14:10:00,716 - INFO -    Date range: 2021-01-04 to 2024-02-06 (778 days)
2026-02-26 14:10:00,716 - INFO -    🔧 Truncating data to start_date: 2022-01-01
2026-02-26 14:10:00,941 - INFO - Memory: ~15.2 MB total after float32 conversion
2026-02-26 14:10:00,983 - INFO - 🔍 Calculating entry signals...
2026-02-26 14:10:00,986 - INFO -    🎯 Using TREND signal (close > SMA20)
2026-02-26 14:10:00,987 - INFO -    📊 ADVANCED MODE entries (before Adaptive Filter): 133000
2026-02-26 14:10:00,988 - INFO -       Base entry passed: 133000
2026-02-26 14:10:01,012 - INFO - 🛡️  PIT Universe filter: blocked 0 entries on non-member dates (133000 remaining)
2026-02-26 14:10:01,030 - INFO - 🔧 Applying Adaptive Filter Engine (TIER 1-2-3) - OPTIMIZADO...
2026-02-26 14:10:01,030 - INFO - 🔧 AdaptiveFilterEngine initialized
   ⚡ Applying Adaptive Filter: 100%|████| 526/526 [00:01<00:00, 276.65day/s]
2026-02-26 14:10:02,933 - INFO -    📊 Entries antes de Adaptive Filter: 133000
2026-02-26 14:10:02,933 - INFO -    ❌ Entries rechazadas por TIER:
2026-02-26 14:10:02,933 - INFO -       TIER 1 (Market Safety): 37907
2026-02-26 14:10:02,933 - INFO -       TIER 2 (Dynamic Quality): 29842
2026-02-26 14:10:02,933 - INFO -       TIER 3 (Optional): 97
2026-02-26 14:10:02,934 - INFO -    ✅ Entries finales: 65154

======================================================================
📊 ADAPTIVE FILTER ENGINE - RESUMEN (OPTIMIZADO)
======================================================================
  Total de Rechazos: 67846
  • TIER 1 (Market Safety): 37907
  • TIER 2 (Dynamic Quality): 29842
  TIER 3 (Optional): 97
======================================================================
2026-02-26 14:10:03,027 - INFO - 🔍 Clasificando riesgo por RVOL (VolTrig)...
2026-02-26 14:10:03,033 - INFO -    ☔ Danger (RVOL>=3.0x): 226 entries → Size 50%
2026-02-26 14:10:03,034 - INFO -    ⚠️  Warning (RVOL>=2.0x): 1317 entries → Size 75%
2026-02-26 14:10:03,034 - INFO -    ✅ Safe (RVOL<2.0x): 63611 entries → Size 100%
2026-02-26 14:10:03,034 - INFO - 🔍 Clasificando riesgo por ADR (volatilidad)...
2026-02-26 14:10:03,108 - INFO -    🔥 High ADR (>6.0%): 173 entries → Size 25%
2026-02-26 14:10:03,109 - INFO -    ⚠️  Med ADR (>5.0%): 367 entries → Size 33%
2026-02-26 14:10:03,147 - INFO - 📊 Multi-chunk mode: 526 days → 2 chunks of ~500 days
2026-02-26 14:10:03,148 - INFO - 🔄 Running multi-chunk backtest: 2 chunks...
2026-02-26 14:10:03,153 - INFO -    📦 Chunk 1/2: days 0-263 (capital: $100,000)
2026-02-26 14:10:03,159 - INFO - 🔄 Running single-chunk backtest with Numba Core...
2026-02-26 14:10:03,159 - INFO - 🔄 Converting DataFrames to NumPy arrays (float32 optimization)...
2026-02-26 14:10:03,195 - INFO -    ✅ Arrays prepared: 7.0 MB total
2026-02-26 14:10:03,196 - INFO -    📊 Array shapes: close=(263, 538), high=(263, 538)
2026-02-26 14:10:03,196 - INFO - ⚡ Ejecutando simulación ultra-rápida (Numba Core)...
2026-02-26 14:10:03,196 - INFO -    🚀 Using pre-calculated NumPy arrays (memory optimized - float32)
2026-02-26 14:10:03,202 - INFO -    💰 Numba Core usando FIXED DOLLAR RISK: $1000 → risk_pct=0.0100
2026-02-26 14:10:03,203 - INFO - 🔧 NUMBA CORE PARAMETERS:
2026-02-26 14:10:03,203 - INFO -    Initial Capital: $100,000.00
2026-02-26 14:10:03,203 - INFO -    Risk per Trade: $1,000.00
2026-02-26 14:10:03,203 - INFO -    Use Fixed Risk: True
2026-02-26 14:10:03,203 - INFO -    TP1/TP2 Targets: 1.971483973387136R / 2.848780189500621R
2026-02-26 14:10:03,203 - INFO -    TP Distribution: 45% / 30% / 25%
2026-02-26 14:10:03,203 - INFO -    Max Stop %%: 8.0% (decimal: 0.08)
2026-02-26 14:10:03,203 - INFO -    Trailing Stop: False
2026-02-26 14:10:03,203 - INFO -    ATR Stop Mode: False
2026-02-26 14:10:03,203 - INFO -    Total Entries Signals: 24024
2026-02-26 14:10:03,205 - INFO - 🚀 Numba Simulation Time: 0.0016s
2026-02-26 14:10:03,205 - INFO - 📊 Numba Core Results:
2026-02-26 14:10:03,206 - INFO -    Entry signals found: 24024
2026-02-26 14:10:03,206 - INFO -    Trades executed: 34
2026-02-26 14:10:03,206 - INFO -    Conversion rate: 0.1%
2026-02-26 14:10:03,206 - INFO -    Final equity: $92,760.48
2026-02-26 14:10:03,206 - WARNING -    ⚠️ Low conversion rate (0.1%) - Check parameters
2026-02-26 14:10:03,206 - WARNING -    May indicate: Restrictive filters, large stop distances, or insufficient capital
2026-02-26 14:10:03,206 - INFO -    Exit distribution: STOP=19, TP1=7, TP2=4, RUNNER=4
2026-02-26 14:10:03,688 - INFO -    ✅ Chunk 1 complete: 34 trades, final equity $92,760
2026-02-26 14:10:04,148 - INFO -    📦 Chunk 2/2: days 263-526 (capital: $92,760)
2026-02-26 14:10:04,153 - INFO - 🔄 Running single-chunk backtest with Numba Core...
2026-02-26 14:10:04,154 - INFO - 🔄 Converting DataFrames to NumPy arrays (float32 optimization)...
2026-02-26 14:10:04,191 - INFO -    ✅ Arrays prepared: 7.0 MB total
2026-02-26 14:10:04,191 - INFO -    📊 Array shapes: close=(263, 538), high=(263, 538)
2026-02-26 14:10:04,191 - INFO - ⚡ Ejecutando simulación ultra-rápida (Numba Core)...
2026-02-26 14:10:04,191 - INFO -    🚀 Using pre-calculated NumPy arrays (memory optimized - float32)
2026-02-26 14:10:04,197 - INFO -    💰 Numba Core usando FIXED DOLLAR RISK: $1000 → risk_pct=0.0108
2026-02-26 14:10:04,197 - INFO - 🔧 NUMBA CORE PARAMETERS:
2026-02-26 14:10:04,197 - INFO -    Initial Capital: $92,760.48
2026-02-26 14:10:04,197 - INFO -    Risk per Trade: $1,000.00
2026-02-26 14:10:04,197 - INFO -    Use Fixed Risk: True
2026-02-26 14:10:04,197 - INFO -    TP1/TP2 Targets: 1.971483973387136R / 2.848780189500621R
2026-02-26 14:10:04,197 - INFO -    TP Distribution: 45% / 30% / 25%
2026-02-26 14:10:04,197 - INFO -    Max Stop %%: 8.0% (decimal: 0.08)
2026-02-26 14:10:04,197 - INFO -    Trailing Stop: False
2026-02-26 14:10:04,197 - INFO -    ATR Stop Mode: False
2026-02-26 14:10:04,198 - INFO -    Total Entries Signals: 41130
2026-02-26 14:10:04,199 - INFO - 🚀 Numba Simulation Time: 0.0014s
2026-02-26 14:10:04,200 - INFO - 📊 Numba Core Results:
2026-02-26 14:10:04,200 - INFO -    Entry signals found: 41130
2026-02-26 14:10:04,200 - INFO -    Trades executed: 37
2026-02-26 14:10:04,200 - INFO -    Conversion rate: 0.1%
2026-02-26 14:10:04,200 - INFO -    Final equity: $97,629.76
2026-02-26 14:10:04,200 - WARNING -    ⚠️ Low conversion rate (0.1%) - Check parameters
2026-02-26 14:10:04,200 - WARNING -    May indicate: Restrictive filters, large stop distances, or insufficient capital
2026-02-26 14:10:04,200 - INFO -    Exit distribution: STOP=18, TP1=8, TP2=8, RUNNER=3
2026-02-26 14:10:04,677 - INFO -    ✅ Chunk 2 complete: 37 trades, final equity $97,630
2026-02-26 14:10:05,142 - INFO - ✅ Multi-chunk backtest complete: 71 total trades
2026-02-26 14:10:05,146 - INFO - ✅ Backtest complete!
2026-02-26 14:10:05,146 - INFO -    Return: -2.37%
2026-02-26 14:10:05,146 - INFO -    Annualized Return: -1.14%
2026-02-26 14:10:05,146 - INFO -    Sharpe: -0.01
2026-02-26 14:10:05,146 - INFO -    Max DD: -20.65%
2026-02-26 14:10:05,146 - INFO -    MAR Ratio: -0.06
2026-02-26 14:10:05,146 - INFO -    Calmar Ratio: -0.06
2026-02-26 14:10:05,146 - INFO -    Win Rate: 46.5%
2026-02-26 14:10:05,146 - INFO -    Trades: 65154 entries → 71 total exits (including partial)
2026-02-26 14:10:05,153 - INFO - ============================================================
2026-02-26 14:10:05,153 - INFO - 🚀 MODE: PRODUCTION (Fixed Dollar Risk)
2026-02-26 14:10:05,154 - INFO -    • Risk: FIXED DOLLAR ($1000)
2026-02-26 14:10:05,154 - INFO -    • Compounding: DISABLED
2026-02-26 14:10:05,154 - INFO - ============================================================
2026-02-26 14:10:05,155 - INFO - 🚀 Advanced VectorBT Engine initialized
2026-02-26 14:10:05,155 - INFO - 📅 Period: 2022-01-01 to 2024-02-06
2026-02-26 14:10:05,155 - INFO - 🎯 Universe: 566 tickers
2026-02-26 14:10:05,155 - INFO - 🎛️  Liquidity: vol≥100k, $vol≥$98M, ADR≥1.622155611115659%, RVOL≥0.7033933512080547x
2026-02-26 14:10:05,155 - INFO - 🎛️  Position Size: RVOL Danger≥3.0x→50%, Warning≥2.0x→75%
2026-02-26 14:10:05,156 - INFO - ============================================================
2026-02-26 14:10:05,156 - INFO - 🌍 MARKET REGIME FILTER ENABLED
2026-02-26 14:10:05,156 - INFO - ============================================================
2026-02-26 14:10:05,156 - INFO - 📊 Loading SPY and VIX data (2022-01-01 to 2024-02-06)...
2026-02-26 14:10:05,158 - INFO -    ✅ SPY loaded from cache: 526 bars
2026-02-26 14:10:05,161 - INFO -    ✅ VIX loaded from cache: 526 bars
2026-02-26 14:10:05,161 - INFO -    ✅ Market data loaded successfully
2026-02-26 14:10:05,166 - INFO -    ✅ Market regime classifier initialized
2026-02-26 14:10:05,167 - INFO -    🚫 Block Stage 3: True
2026-02-26 14:10:05,167 - INFO -    🚫 Block Stage 4: True
2026-02-26 14:10:05,167 - INFO -    📊 Adjust risk by regime: True
2026-02-26 14:10:05,180 - INFO - 📥 Loading data from 2021-01-01 (buffer) to 2024-02-06...
2026-02-26 14:10:05,180 - INFO - 🎯 Universe size: 566 tickers
2026-02-26 14:10:05,180 - INFO - 🛡️  Survivorship bias protection: PIT mask will determine eligibility quarterly
2026-02-26 14:10:05,180 - INFO - ⚡ Fetching data for 566 tickers in parallel...
2026-02-26 14:10:05,488 - WARNING - ❌ SKIP AMTM: None returned
2026-02-26 14:10:05,490 - WARNING - ❌ SKIP ANSS: None returned
2026-02-26 14:10:05,750 - WARNING - ❌ SKIP ATVI: None returned
2026-02-26 14:10:05,972 - INFO -    100/566...
2026-02-26 14:10:06,039 - WARNING - ❌ SKIP CDAY: None returned
2026-02-26 14:10:06,352 - WARNING - ❌ SKIP CTXS: None returned
2026-02-26 14:10:06,646 - INFO -    200/566...
2026-02-26 14:10:06,658 - WARNING - ❌ SKIP DRE: None returned
2026-02-26 14:10:06,698 - WARNING - ❌ SKIP FB: None returned
2026-02-26 14:10:06,700 - WARNING - ❌ SKIP FBHS: None returned
2026-02-26 14:10:06,701 - WARNING - ❌ SKIP FI: None returned
2026-02-26 14:10:06,720 - WARNING - ❌ SKIP FISV: None returned
2026-02-26 14:10:07,328 - INFO -    300/566...
2026-02-26 14:10:08,077 - INFO -    400/566...
2026-02-26 14:10:08,763 - INFO -    500/566...
2026-02-26 14:10:09,190 - WARNING - ⚠️  Skipped 28 tickers (insufficient data)
2026-02-26 14:10:09,190 - INFO -    First 10 failed: ['AMTM (None returned)', 'ANSS (None returned)', 'ATVI (None returned)', 'CDAY (None returned)', 'CTXS (None returned)', 'DRE (None returned)', 'FB (None returned)', 'FBHS (None returned)', 'FI (None returned)', 'FISV (None returned)']
2026-02-26 14:10:09,190 - INFO - ℹ️  538 tickers with partial data (gaps in history)
2026-02-26 14:10:09,409 - INFO - Memory: 6.4 MB for 538 tickers (core DataFrames)
2026-02-26 14:10:09,409 - INFO - 🛡️  Building Point-in-Time tradeable mask (survivorship bias protection)...
2026-02-26 14:10:09,463 - INFO - PointInTimeUniverse: loaded 1230 ticker membership records
2026-02-26 14:10:09,529 - INFO - Tradeable mask: 376,609/418,564 cells (90.0%) across 538 S&P 500 + 0 non-S&P tickers, 778 trading days
2026-02-26 14:10:09,549 - INFO -    🛡️  Masked out 41,955 cells (10.0%) as non-tradeable (pre-IPO, post-delist, not in S&P 500)
2026-02-26 14:10:09,564 - WARNING -    ⚠️ No precomputed metrics found in cache, will calculate on the fly
2026-02-26 14:10:10,211 - INFO -    ⚠️ Precomputed metrics not available, calculating on the fly...
2026-02-26 14:10:10,244 - INFO -    ⚠️ SMA50 missing in cache, calculating on the fly...
2026-02-26 14:10:11,073 - INFO -    Loading SPY and VIX data for Market Regime...
2026-02-26 14:10:11,074 - INFO - 📊 Loading SPY and VIX data (2021-01-01 to 2024-02-06)...
2026-02-26 14:10:11,076 - INFO -    ✅ SPY loaded from cache: 778 bars
2026-02-26 14:10:11,079 - INFO -    ✅ VIX loaded from cache: 778 bars
2026-02-26 14:10:11,080 - INFO -    ✅ Market data loaded successfully
2026-02-26 14:10:11,086 - INFO -    ✅ Market Data Loaded & Aligned
2026-02-26 14:10:11,087 - INFO - ✅ Loaded: 538 tickers
2026-02-26 14:10:11,087 - INFO - 🛡️  Filtered out 28 tickers (insufficient data)
2026-02-26 14:10:11,087 - INFO -    Date range: 2021-01-04 to 2024-02-06 (778 days)
2026-02-26 14:10:11,087 - INFO -    🔧 Truncating data to start_date: 2022-01-01
2026-02-26 14:10:11,290 - INFO - Memory: ~15.2 MB total after float32 conversion
2026-02-26 14:10:11,307 - INFO - 🎯 Starting advanced backtest with partial exits...
2026-02-26 14:10:11,308 - INFO - 📥 Loading data from 2021-01-01 (buffer) to 2024-02-06...
2026-02-26 14:10:11,308 - INFO - 🎯 Universe size: 538 tickers
2026-02-26 14:10:11,308 - INFO - 🛡️  Survivorship bias protection: PIT mask will determine eligibility quarterly
2026-02-26 14:10:11,308 - INFO - ⚡ Fetching data for 538 tickers in parallel...
2026-02-26 14:10:12,043 - INFO -    100/538...
2026-02-26 14:10:12,680 - INFO -    200/538...
2026-02-26 14:10:13,370 - INFO -    300/538...
2026-02-26 14:10:14,114 - INFO -    400/538...
2026-02-26 14:10:14,818 - INFO -    500/538...
2026-02-26 14:10:15,095 - INFO - ℹ️  538 tickers with partial data (gaps in history)
2026-02-26 14:10:15,334 - INFO - Memory: 6.4 MB for 538 tickers (core DataFrames)
2026-02-26 14:10:15,335 - INFO - 🛡️  Building Point-in-Time tradeable mask (survivorship bias protection)...
2026-02-26 14:10:15,390 - INFO - PointInTimeUniverse: loaded 1230 ticker membership records
2026-02-26 14:10:15,461 - INFO - Tradeable mask: 376,609/418,564 cells (90.0%) across 538 S&P 500 + 0 non-S&P tickers, 778 trading days
2026-02-26 14:10:15,482 - INFO -    🛡️  Masked out 41,955 cells (10.0%) as non-tradeable (pre-IPO, post-delist, not in S&P 500)
2026-02-26 14:10:15,503 - WARNING -    ⚠️ No precomputed metrics found in cache, will calculate on the fly
2026-02-26 14:10:16,122 - INFO -    ⚠️ Precomputed metrics not available, calculating on the fly...
2026-02-26 14:10:16,156 - INFO -    ⚠️ SMA50 missing in cache, calculating on the fly...
2026-02-26 14:10:17,463 - INFO -    Loading SPY and VIX data for Market Regime...
2026-02-26 14:10:17,464 - INFO - 📊 Loading SPY and VIX data (2021-01-01 to 2024-02-06)...
2026-02-26 14:10:17,466 - INFO -    ✅ SPY loaded from cache: 778 bars
2026-02-26 14:10:17,469 - INFO -    ✅ VIX loaded from cache: 778 bars
2026-02-26 14:10:17,469 - INFO -    ✅ Market data loaded successfully
2026-02-26 14:10:17,479 - INFO -    ✅ Market Data Loaded & Aligned
2026-02-26 14:10:17,480 - INFO - ✅ Loaded: 538 tickers
2026-02-26 14:10:17,480 - INFO -    Date range: 2021-01-04 to 2024-02-06 (778 days)
2026-02-26 14:10:17,480 - INFO -    🔧 Truncating data to start_date: 2022-01-01
2026-02-26 14:10:17,712 - INFO - Memory: ~15.2 MB total after float32 conversion
2026-02-26 14:10:17,766 - INFO - 🔍 Calculating entry signals...
2026-02-26 14:10:17,769 - INFO -    🎯 Using TREND signal (close > SMA20)
2026-02-26 14:10:17,771 - INFO -    📊 ADVANCED MODE entries (before Adaptive Filter): 133000
2026-02-26 14:10:17,772 - INFO -       Base entry passed: 133000
2026-02-26 14:10:17,799 - INFO - 🛡️  PIT Universe filter: blocked 0 entries on non-member dates (133000 remaining)
2026-02-26 14:10:17,817 - INFO - 🔧 Applying Adaptive Filter Engine (TIER 1-2-3) - OPTIMIZADO...
2026-02-26 14:10:17,818 - INFO - 🔧 AdaptiveFilterEngine initialized
   ⚡ Applying Adaptive Filter: 100%|████| 526/526 [00:01<00:00, 272.17day/s]
2026-02-26 14:10:19,753 - INFO -    📊 Entries antes de Adaptive Filter: 133000
2026-02-26 14:10:19,753 - INFO -    ❌ Enrechazadas por TIER:
2026-02-26 14:10:19,753 - INFO -       TIER 1 (Market Safety): 37907
2026-02-26 14:10:19,753 - INFO -       TIER 2 (Dynamic Quality): 41822
2026-02-26 14:10:19,753 - INFO -       TIER 3 (Optional): 75
2026-02-26 14:10:19,753 - INFO -    ✅ Entries finales: 53196

======================================================================
📊 ADAPTIVE FILTER ENGINE - RESUMEN (OPTIMIZADO)
======================================================================
  Total de Rechazos: 79804
  • TIER 1 (Market Safety): 37907
  • TIER 2 (Dynamic Quality): 41822
  TIER 3 (Optional): 75
======================================================================
2026-02-26 14:10:19,878 - INFO - 🔍 Clasificando riesgo por RVOL (VolTrig)...
2026-02-26 14:10:19,883 - INFO -    ☔ Danger (RVOL>=3.0x): 208 entries → Size 50%
2026-02-26 14:10:19,884 - INFO -    ⚠️  Warning (RVOL>=2.0x): 1223 entries → Size 75%
2026-02-26 14:10:19,884 - INFO -    ✅ Safe (RVOL<2.0x): 51765 entries → Size 100%
2026-02-26 14:10:19,884 - INFO - 🔍 Clasificando riesgo por ADR (volatilidad)...
2026-02-26 14:10:19,957 - INFO -    🔥 High ADR (>6.0%): 138 entries → Size 25%
2026-02-26 14:10:19,957 - INFO -    ⚠️  Med ADR (>5.0%): 299 entries → Size 33%
2026-02-26 14:10:19,996 - INFO - 📊 Multi-chunk mode: 526 days → 2 chunks of ~500 days
2026-02-26 14:10:19,996 - INFO - 🔄 Running multi-chunk backtest: 2 chunks...
2026-02-26 14:10:20,001 - INFO -    📦 Chunk 1/2: days 0-263 (capital: $100,000)
2026-02-26 14:10:20,007 - INFO - 🔄 Running single-chunk backtest with Numba Core...
2026-02-26 14:10:20,007 - INFO - 🔄 Converting DataFrames to NumPy arrays (float32 optimization)...
2026-02-26 14:10:20,043 - INFO -    ✅ Arrays prepared: 7.0 MB total
2026-02-26 14:10:20,043 - INFO -    📊 Array shapes: close=(263, 538), high=(263, 538)
2026-02-26 14:10:20,043 - INFO - ⚡ Ejecutando simulación ultra-rápida (Numba Core)...
2026-02-26 14:10:20,043 - INFO -    🚀 Using pre-calculated NumPy arrays (memory optimized - float32)
2026-02-26 14:10:20,049 - INFO -    💰 Numba Core usando FIXED DOLLAR RISK: $1000 → risk_pct=0.0100
2026-02-26 14:10:20,049 - INFO - 🔧 NUMBA CORE PARAMETERS:
2026-02-26 14:10:20,049 - INFO -    Initial Capital: $100,000.00
2026-02-26 14:10:20,050 - INFO -    Risk per Trade: $1,000.00
2026-02-26 14:10:20,050 - INFO -    Use Fixed Risk: True
2026-02-26 14:10:20,050 - INFO -    TP1/TP2 Targets: 1.691555577086978R / 3.0270653059795483R
2026-02-26 14:10:20,050 - INFO -    TP Distribution: 45% / 30% / 25%
2026-02-26 14:10:20,050 - INFO -    Max Stop %%: 8.0% (decimal: 0.08)
2026-02-26 14:10:20,050 - INFO -    Trailing Stop: False
2026-02-26 14:10:20,050 - INFO -    ATR Stop Mode: False
2026-02-26 14:10:20,050 - INFO -    Total Entries Signals: 20349
2026-02-26 14:10:20,052 - INFO - 🚀 Numba Simulation Time: 0.0013s
2026-02-26 14:10:20,052 - INFO - 📊 Numba Core Results:
2026-02-26 14:10:20,052 - INFO -    Entry signals found: 20349
2026-02-26 14:10:20,052 - INFO -    Trades executed: 36
2026-02-26 14:10:20,052 - INFO -    Conversion rate: 0.2%
2026-02-26 14:10:20,052 - INFO -    Final equity: $91,657.35
2026-02-26 14:10:20,052 - WARNING -    ⚠️ Low conversion rate (0.2%) - Check parameters
2026-02-26 14:10:20,052 - WARNING -    May indicate: Restrictive filters, large stop distances, or insufficient capital
2026-02-26 14:10:20,053 - INFO -    Exit distribution: STOP=20, TP1=9, TP2=4, RUNNER=3
2026-02-26 14:10:20,515 - INFO -    ✅ Chunk 1 complete: 36 trades, final equity $91,657
2026-02-26 14:10:20,966 - INFO -    📦 Chunk 2/2: days 263-526 (capital: $91,657)
2026-02-26 14:10:20,971 - INFO - 🔄 Running single-chunk backtest with Numba Core...
2026-02-26 14:10:20,971 - INFO - 🔄 Converting DataFrames to NumPy arrays (float32 optimization)...
2026-02-26 14:10:21,009 - INFO -    ✅ Arrays prepared: 7.0 MB total
2026-02-26 14:10:21,009 - INFO -    📊 Array shapes: close=(263, 538), high=(263, 538)
2026-021,009 - INFO - ⚡ Ejecutando simulación ultra-rápida (Numba Core)...
2026-02-26 14:10:21,009 - INFO -    🚀 Using pre-calculated NumPy arrays (memory optimized - float32)
2026-02-26 14:10:21,016 - INFO -    💰 Numba Core usando FIXED DOLLAR RISK: $1000 → risk_pct=0.0109
2026-02-26 14:10:21,016 - INFO - 🔧 NUMBA CORE PARAMETERS:
2026-02-26 14:10:21,016 - INFO -    Initial Capital: $91,657.35
2026-02-26 14:10:21,016 - INFO -    Risk per Trade: $1,000.00
2026-02-26 14:10:21,016 - INFO -    Use Fixed Risk: True
2026-02-26 14:10:21,016 - INFO -    TP1/TP2 Targets: 1.691555577086978R / 3.0270653059795483R
2026-02-26 14:10:21,017 - INFO -    TP Distribution: 45% / 30% / 25%
2026-02-26 14:10:21,017 - INFO -    Max Stop %%: 8.0% (decimal: 0.08)
2026-02-26 14:10:21,017 - INFO -    Trailing Stop: False
2026-02-26 14:10:21,017 - INFO -    ATR Stop Mode: False
2026-02-26 14:10:21,017 - INFO -    Total Entries Signals: 32847
2026-02-26 14:10:21,018 - INFO - 🚀 Numba Simulation Time: 0.0010s
2026-02-26 14:10:21,018 - INFO - 📊 Numba Core Results:
2026-02-26 14:10:21,018 - INFO -    Entry signals found: 32847
2026-02-26 14:10:21,018 - INFO -    Trades executed: 42
2026-02-26 14:10:21,019 - INFO -    Conversion rate: 0.1%
2026-02-26 14:10:21,019 - INFO -    Final equity: $97,593.14
2026-02-26 14:10:21,019 - WARNING -    ⚠️ Low conversion rate (0.1%) - Check parameters
2026-02-26 14:10:21,019 - WARNING -    May indicate: Restrictive filters, large stop distances, or insufficient capital
2026-02-26 14:10:21,019 - INFO -    Exit distribution: STOP=18, TP1=11, TP2=8, RUNNER=5
2026-02-26 14:10:21,490 - INFO -    ✅ Chunk 2 complete: 42 trades, final equity $97,593
2026-02-26 14:10:21,942 - INFO - ✅ Multi-chunk backtest complete: 78 total trades
2026-02-26 14:10:21,946 - INFO - ✅ Backtest complete!
2026-02-26 14:10:21,946 - INFO -    Return: -2.41%
2026-02-26 14:10:21,946 - INFO -    Annualized Return: -1.16%
2026-02-26 14:10:21,946 - INFO -    Sharpe: -0.03
2026-02-26 14:10:21,946 - INFO -    Max DD: -19.42%
2026-02-26 14:10:21,946 - INFO -    MAR Ratio: -0.06
2026-02-26 14:10:21,946 - INFO -    Calmar Ratio: -0.06
2026-02-26 14:10:21,947 - INFO -    Win Rate: 51.3%
2026-02-26 14:10:21,947 - INFO -    Trades: 53196 entries → 78 total exits (including partial)
2026-02-26 14:10:21,954 - INFO - ============================================================
2026-02-26 14:10:21,954 - INFO - 🚀 MODE: PRODUCTION (Fixed Dollar Risk)
2026-02-26 14:10:21,954 - INFO -    • Risk: FIXED DOLLAR ($1000)
2026-02-26 14:10:21,954 - INFO -    • Compounding: DISABLED
2026-02-26 14:10:21,955 - INFO - ============================================================
2026-02-26 14:10:21,956 - INFO - 🚀 Advanced VectorBT Engine initialized
2026-02-26 14:10:21,956 - INFO - 📅 Period: 2022-01-01 to 2024-02-06
2026-02-26 14:10:21,956 - INFO - 🎯 Universe: 566 tickers
2026-02-26 14:10:21,956 - INFO - 🎛️  Liquidity: vol≥100k, $vol≥$98M, ADR≥1.5278999149890435%, RVOL≥0.6998900014595334x
2026-02-26 14:10:21,956 - INFO - 🎛️  Position Size: RVOL Danger≥3.0x→50%, Warning≥2.0x→75%
2026-02-26 14:10:21,957 - INFO - ============================================================
2026-02-26 14:10:21,957 - INFO - 🌍 MARKET REGIME FILTER ENABLED
2026-02-26 14:10:21,957 - INFO - ============================================================
2026-02-26 14:10:21,957 - INFO - 📊 Loading SPY and VIX data (2022-01-01 to 2024-02-06)...
2026-02-26 14:10:21,959 - INFO -    ✅ SPY loaded from cache: 526 bars
2026-02-26 14:10:21,961 - INFO -    ✅ VIX loaded from cache: 526 bars
2026-02-26 14:10:21,962 - INFO -    ✅ Market data loaded successfully
2026-02-26 14:10:21,967 - INFO -    ✅ Market regime classifier initialized
2026-02-26 14:10:21,967 - INFO -    🚫 Block Stage 3: True
2026-02-26 14:10:21,967 - INFO -    🚫 Block Stage 4: True
2026-02-26 14:10:21,968 - INFO -    📊 Adjust risk by regime: True
2026-02-26 14:10:21,983 - INFO - 📥 Loading d01-01 (buffer) to 2024-02-06...
2026-02-26 14:10:21,984 - INFO - 🎯 Universe size: 566 tickers
2026-02-26 14:10:21,984 - INFO - 🛡️  Survivorship bias protection: PIT mask will determine eligibility quarterly
2026-02-26 14:10:21,984 - INFO - ⚡ Fetching data for 566 tickers in parallel...
2026-02-26 14:10:22,285 - WARNING - ❌ SKIP AMTM: None returned
2026-02-26 14:10:22,291 - WARNING - ❌ SKIP ANSS: None returned
2026-02-26 14:10:22,548 - WARNING - ❌ SKIP ATVI: None returned
2026-02-26 14:10:22,737 - INFO -    100/566...
2026-02-26 14:10:22,834 - WARNING - ❌ SKIP CDAY: None returned
2026-02-26 14:10:23,099 - WARNING - ❌ SKIP CTXS: None returned
2026-02-26 14:10:23,414 - INFO -    200/566...
2026-02-26 14:10:23,421 - WARNING - ❌ SKIP DRE: None returned
2026-02-26 14:10:23,468 - WARNING - ❌ SKIP FB: None returned
2026-02-26 14:10:23,473 - WARNING - ❌ SKIP FBHS: None returned
2026-02-26 14:10:23,475 - WARNING - ❌ SKIP FI: None returned
2026-02-26 14:10:23,482 - WARNING - ❌ SKIP FISV: None returned
2026-02-26 14:10:24,101 - INFO -    300/566...
2026-02-26 14:10:24,898 - INFO -    400/566...
2026-02-26 14:10:25,631 - INFO -    500/566...
2026-02-26 14:10:26,095 - WARNING - ⚠️  Skipped 28 tickers (insufficient data)
2026-02-26 14:10:26,095 - INFO -    First 10 failed: ['AMTM (None returned)', 'ANSS (None returned)', 'ATVI (None returned)', 'CDAY (None returned)', 'CTXS (None returned)', 'DRE (None returned)', 'FB (None returned)', 'FBHS (None returned)', 'FI (None returned)', 'FISV (None returned)']
2026-02-26 14:10:26,095 - INFO - ℹ️  538 tickers with partial data (gaps in history)
2026-02-26 14:10:26,331 - INFO - Memory: 6.4 MB for 538 tickers (core DataFrames)
2026-02-26 14:10:26,332 - INFO - 🛡️  Building Point-in-Time tradeable mask (survivorship bias protection)...
2026-02-26 14:10:26,387 - INFO - PointInTimeUniverse: loaded 1230 ticker membership records
2026-02-26 14:10:26,460 - INFO - Tradeable mask: 376,609/418,564 cells (90.0%) across 538 S&P 500 + 0 non-S&P tickers, 778 trading days
2026-02-26 14:10:26,481 - INFO -    🛡️  Masked out 41,955 cells (10.0%) as non-tradeable (pre-IPO, post-delist, not in S&P 500)
2026-02-26 14:10:26,500 - WARNING -    ⚠️ No precomputed metrics found in cache, will calculate on the fly
2026-02-26 14:10:27,121 - INFO -    ⚠️ Precomputed metrics not available, calculating on the fly...
2026-02-26 14:10:27,154 - INFO -    ⚠️ SMA50 missing in cache, calculating on the fly...
2026-02-26 14:10:28,032 - INFO -    Loading SPY and VIX data for Market Regime...
2026-02-26 14:10:28,032 - INFO - 📊 Loading SPY and VIX data (2021-01-01 to 2024-02-06)...
2026-02-26 14:10:28,035 - INFO -    ✅ SPY loaded from cache: 778 bars
2026-02-26 14:10:28,038 - INFO -    ✅ VIX loaded from cache: 778 bars
2026-02-26 14:10:28,038 - INFO -    ✅ Market data loaded successfully
2026-02-26 14:10:28,045 - INFO -    ✅ Market Data Loaded & Aligned
2026-02-26 14:10:28,046 - INFO - ✅ Loaded: 538 tickers
2026-02-26 14:10:28,046 - INFO - 🛡️  Filtered out 28 tickers (insufficient data)
2026-02-26 14:10:28,046 - INFO -    Date range: 2021-01-04 to 2024-02-06 (778 days)
2026-02-26 14:10:28,046 - INFO -    🔧 Truncating data to start_date: 2022-01-01
2026-02-26 14:10:28,262 - INFO - Memory: ~15.2 MB total after float32 conversion
2026-02-26 14:10:28,282 - INFO - 🎯 Starting advanced backtest with partial exits...
2026-02-26 14:10:28,284 - INFO - 📥 Loading data from 2021-01-01 (buffer) to 2024-02-06...
2026-02-26 14:10:28,284 - INFO - 🎯 Universe size: 538 tickers
2026-02-26 14:10:28,284 - INFO - 🛡️  Survivorship bias protection: PIT mask will determine eligibility quarterly
2026-02-26 14:10:28,284 - INFO - ⚡ Fetching data for 538 tickers in parallel...
2026-02-26 14:10:29,086 - INFO -    100/538...
2026-02-26 14:10:29,722 - INFO -    200/538...
2026-02-26 14:10:30,418 - INFO -    300/538...
2026-02-26 14:10:31,195 - INFO -    400/538...
2026-02-26 14:10:31,970 - INFO -    500/538...
2026-02-26 14:10:32,275 - INFO - ℹ️  538 tickers with partial data (gaps in history)
2026-02-26 14:10:32,514 - INFO - Memory: 6.4 MB for 538 tickers (core DataFrames)
2026-02-26 14:10:32,514 - INFO - 🛡️  Building Point-in-Time tradeable mask (survivorship bias protection)...
2026-02-26 14:10:32,568 - INFO - PointInTimeUniverse: loaded 1230 ticker membership records
2026-02-26 14:10:32,640 - INFO - Tradeable mask: 376,609/418,564 cells (90.0%) across 538 S&P 500 + 0 non-S&P tickers, 778 trading days
2026-02-26 14:10:32,661 - INFO -    🛡️  Masked out 41,955 cells (10.0%) as non-tradeable (pre-IPO, post-delist, not in S&P 500)
2026-02-26 14:10:32,681 - WARNING -    ⚠️ No precomputed metrics found in cache, will calculate on the fly
2026-02-26 14:10:34,069 - INFO -    ⚠️ Precomputed metrics not available, calculating on the fly...
2026-02-26 14:10:34,102 - INFO -    ⚠️ SMA50 missing in cache, calculating on the fly...
2026-02-26 14:10:35,422 - INFO -    Loading SPY and VIX data for Market Regime...
2026-02-26 14:10:35,423 - INFO - 📊 Loading SPY and VIX data (2021-01-01 to 2024-02-06)...
2026-02-26 14:10:35,425 - INFO -    ✅ SPY loaded from cache: 778 bars
2026-02-26 14:10:35,428 - INFO -    ✅ VIX loaded from cache: 778 bars
2026-02-26 14:10:35,428 - INFO -    ✅ Market data loaded successfully
2026-02-26 14:10:35,435 - INFO -    ✅ Market Data Loaded & Aligned
2026-02-26 14:10:35,435 - INFO - ✅ Loaded: 538 tickers
2026-02-26 14:10:35,436 - INFO -    Date range: 2021-01-04 to 2024-02-06 (778 days)
2026-02-26 14:10:35,436 - INFO -    🔧 Truncating data to start_date: 2022-01-01
2026-02-26 14:10:35,652 - INFO - Memory: ~15.2 MB total after float32 conversion
2026-02-26 14:10:35,696 - INFO - 🔍 Calculating entry signals...
2026-02-26 14:10:35,698 - INFO -    🎯 Using TREND signal (close > SMA20)
2026-02-26 14:10:35,699 - INFO -    📊 ADVANCED MODE entries (before Adaptive Filter): 133000
2026-02-26 14:10:35,700 - INFO -       Base entry passed: 133000
2026-02-26 14:10:35,725 - INFO - 🛡️  PIT Universe filter: blocked 0 entries on non-member dates (133000 remaining)
2026-02-26 14:10:35,742 - INFO - 🔧 Applying Adaptive Filter Engine (TIER 1-2-3) - OPTIMIZADO...
2026-02-26 14:10:35,742 - INFO - 🔧 AdaptiveFilterEngine initialized
   ⚡ Applying Adaptive Filter: 100%|████| 526/526 [00:01<00:00, 280.33day/s]
2026-02-26 14:10:37,620 - INFO -    📊 Entries antes de Adaptive Filter: 133000
2026-02-26 14:10:37,620 - INFO -    ❌ Entries rechazadas por TIER:
2026-02-26 14:10:37,621 - INFO -       TIER 1 (Market Safety): 37907
2026-02-26 14:10:37,621 - INFO -       TIER 2 (Dynamic Quality): 35268
2026-02-26 14:10:37,621 - INFO -       TIER 3 (Optional): 78
2026-02-26 14:10:37,621 - INFO -    ✅ Entries finales: 59747

======================================================================
📊 ADAPTIVE FILTER ENGINE - RESUMEN (OPTIMIZADO)
======================================================================
  Total de Rechazos: 73253
  • TIER 1 (Market Safety): 37907
  • TIER 2 (Dynamic Quality): 35268
  TIER 3 (Optional): 78
======================================================================
2026-02-26 14:10:37,729 - INFO - 🔍 Clasificando riesgo por RVOL (VolTrig)...
2026-02-26 14:10:37,733 - INFO -    ☔ Danger (RVOL>=3.0x): 248 entries → Size 50%
2026-02-26 14:10:37,733 - INFO -    ⚠️  Warning (RVOL>=2.0x): 1399 entries → Size 75%
2026-02-26 14:10:37,733 - INFO -    ✅ Safe (RVOL<2.0x): 58100 entries → Size 100%
2026-02-26 14:10:37,733 - INFO - 🔍 Clasificando riesgo por ADR (volatilidad)...
2026-02-26 14:10:37,805 - INFO -    🔥 High ADR (>6.0%): 154 entries → Size 25%
2026-02-26 14:10:37,806 - INFO -    ⚠️  Med ADR (>5.0%): 333 entries → Size 33%
2026-02-26 14:10:37,845 - INFO - 📊 Multi-chunk mode: 526 days → 2 chunks of ~500 days
2026-02-26 14:10:37,845 - INFO - 🔄 Running multi-chunk backtest: 2 chunks...
2026-02-26 14:10:37,850 - INFO -    📦 Chunk 1/2: days 0-263 (capital: $100,000)
2026-02-26 14:10:37,856 - INFO - 🔄 Running single-chunk backtest with Numba Core...
2026-02-26 14:10:37,856 - INFO - 🔄 Converting DataFrames to NumPy arrays (float32 optimization)...
2026-02-26 14:10:37,893 - INFO -    ✅ Arrays prepared: 7.0 MB total
2026-02-26 14:10:37,894 - INFO -    📊 Array shapes: close=(263, 538), high=(263, 538)
2026-02-26 14:10:37,894 - INFO - ⚡ Ejecutando simulación ultra-rápida (Numba Core)...
2026-02-26 14:10:37,894 - INFO -    🚀 Using pre-calculated NumPy arrays (memory optimized - float32)
2026-02-26 14:10:37,900 - INFO -    💰 Numba Core usando FIXED DOLLAR RISK: $1000 → risk_pct=0.0100
2026-02-26 14:10:37,900 - INFO - 🔧 NUMBA CORE PARAMETERS:
2026-02-26 14:10:37,900 - INFO -    Initial Capital: $100,000.00
2026-02-26 14:10:37,900 - INFO -    Risk per Trade: $1,000.00
2026-02-26 14:10:37,900 - INFO -    Use Fixed Risk: True
2026-02-26 14:10:37,900 - INFO -    TP1/TP2 Targets: 1.7724154436580803R / 2.8999011193503934R
2026-02-26 14:10:37,900 - INFO -    TP Distribution: 45% / 30% / 25%
2026-02-26 14:10:37,900 - INFO -    Max Stop %%: 8.0% (decimal: 0.08)
2026-02-26 14:10:37,901 - INFO -    Trailing Stop: False
2026-02-26 14:10:37,901 - INFO -    ATR Stop Mode: False
2026-02-26 14:10:37,901 - INFO -    Total Entries Signals: 22406
2026-02-26 14:10:37,902 - INFO - 🚀 Numba Simulation Time: 0.0014s
2026-02-26 14:10:37,903 - INFO - 📊 Numba Core Results:
2026-02-26 14:10:37,903 - INFO -    Entry signals found: 22406
2026-02-26 14:10:37,903 - INFO -    Trades executed: 37
2026-02-26 14:10:37,903 - INFO -    Conversion rate: 0.2%
2026-02-26 14:10:37,903 - INFO -    Final equity: $85,175.94
2026-02-26 14:10:37,903 - WARNING -    ⚠️ Low conversion rate (0.2%) - Check parameters
2026-02-26 14:10:37,903 - WARNING -    May indicate: Restrictive filters, large stop distances, or insufficient capital
2026-02-26 14:10:37,903 - INFO -    Exit distribution: STOP=23, TP1=8, TP2=3, RUNNER=3
2026-02-26 14:10:38,376 - INFO -    ✅ Chunk 1 complete: 37 trades, final equity $85,176
2026-02-26 14:10:38,833 - INFO -    📦 Chunk 2/2: days 263-526 (capital: $85,176)
2026-02-26 14:10:38,838 - INFO - 🔄 Running single-chunk backtest with Numba Core...
2026-02-26 14:10:38,838 - INFO - 🔄 Converting DataFrames to NumPy arrays (float32 optimization)...
2026-02-26 14:10:38,876 - INFO -    ✅ Arrays prepared: 7.0 MB total
2026-02-26 14:10:38,876 - INFO -    📊 Array shapes: close=(263, 538), high=(263, 538)
2026-02-26 14:10:38,876 - INFO - ⚡ Ejecutando simulación ultra-rápida (Numba Core)...
2026-02-26 14:10:38,876 - INFO -    🚀 Using pre-calculated NumPy arrays (memory optimized - float32)
2026-02-26 14:10:38,882 - INFO -    💰 Numba Core usando FIXED DOLLAR RISK: $1000 → risk_pct=0.0117
2026-02-26 14:10:38,883 - INFO - 🔧 NUMBA CORE PARAMETERS:
2026-02-26 14:10:38,883 - INFO -    Initial Capital: $85,175.94
2026-02-26 14:10:38,883 - INFO -    Risk per Trade: $1,000.00
2026-02-26 14:10:38,883 - INFO -    Use Fixed Risk: True
2026-02-26 14:10:38,883 - INFO -    TP1/TP2 Targets: 1.7724154436580803R / 2.8999011193503934R
2026-02-26 14:10:38,883 - INFO -    TP Distribution: 45% / 30% / 25%
2026-02-26 14:10:38,883 - INFO -    Max Stop %%: 8.0% (decimal: 0.08)
2026-02-26 14:10:38,883 - INFO -    Trailing Stop: False
2026-02-26 14:10:38,883 - INFO -    ATR Stop Mode: False
2026-02-26 14:10:38,883 - INFO -    Total Entries Signals: 37341
2026-02-26 14:10:38,884 - INFO - 🚀 Numba Simulation Time: 0.0012s
2026-02-26 14:10:38,885 - INFO - 📊 Numba Core Results:
2026-02-26 14:10:38,885 - INFO -    Entry signals found: 37341
2026-02-26 14:10:38,885 - INFO -    Trades executed: 29
2026-02-26 14:10:38,885 - INFO -    Conversion rate: 0.1%
2026-02-26 14:10:38,885 - INFO -    Final equity: $92,709.91
2026-02-26 14:10:38,885 - WARNING -    ⚠️ Low conversion rate (0.1%) - Check parameters
2026-02-26 14:10:38,885 - WARNING -    May indicate: Restrictive filters, large stop distances, or insufficient capital
2026-02-26 14:10:38,885 - INFO -    Exit distribution: STOP=14, TP1=8, TP2=5, RUNNER=2
2026-02-26 14:10:39,349 - INFO -    ✅ Chunk 2 complete: 29 trades, final equity $92,710
2026-02-26 14:10:39,816 - INFO - ✅ Multi-chunk backtest complete: 66 total trades
2026-02-26 14:10:39,822 - INFO - ✅ Backtest complete!
2026-02-26 14:10:39,823 - INFO -    Return: -7.29%
2026-02-26 14:10:39,823 - INFO -    Annualized Return: -3.56%
2026-02-26 14:10:39,823 - INFO -    Sharpe: -0.18
2026-02-26 14:10:39,823 - INFO -    Max DD: -25.33%
2026-02-26 14:10:39,823 - INFO -    MAR Ratio: -0.14
2026-02-26 14:10:39,823 - INFO -    Calmar Ratio: -0.14
2026-02-26 14:10:39,823 - INFO -    Win Rate: 43.9%
2026-02-26 14:10:39,823 - INFO -    Trades: 59747 entries → 66 total exits (including partial)
2026-02-26 14:10:39,832 - INFO - ============================================================
2026-02-26 14:10:39,832 - INFO - 🚀 MODE: PRODUCTION (Fixed Dollar Risk)
2026-02-26 14:10:39,832 - INFO -    • Risk: FIXED DOLLAR ($1000)
2026-02-26 14:10:39,833 - INFO -    • Compounding: DISABLED
2026-02-26 14:10:39,833 - INFO - ============================================================
2026-02-26 14:10:39,835 - INFO - 🚀 Advanced VectorBT Engine initialized
2026-02-26 14:10:39,835 - INFO - 📅 Period: 2022-01-01 to 2024-02-06
2026-02-26 14:10:39,835 - INFO - 🎯 Universe: 566 tickers
2026-02-26 14:10:39,835 - INFO - 🎛️  Liquidity: vol≥100k, $vol≥$98M, ADR≥1.775364117103915%, RVOL≥0.5947289194603156x
2026-02-26 14:10:39,835 - INFO - 🎛️  Position Size: RVOL Danger≥3.0x→50%, Warning≥2.0x→75%
2026-02-26 14:10:39,835 - INFO - ============================================================
2026-02-26 14:10:39,836 - INFO - 🌍 MARKET REGIME FILTER ENABLED
2026-02-26 14:10:39,836 - INFO - ============================================================
2026-02-26 14:10:39,836 - INFO - 📊 Loading SPY and VIX data (2022-01-01 to 2024-02-06)...
2026-02-26 14:10:39,838 - INFO -    ✅ SPY loaded from cache: 526 bars
2026-02-26 14:10:39,841 - INFO -    ✅ VIX loaded from cache: 526 bars
2026-02-26 14:10:39,842 - INFO -    ✅ Market data loaded successfully
2026-02-26 14:10:39,848 - INFO -    ✅ Market regime classifier initialized
2026-02-26 14:10:39,849 - INFO -    🚫 Block Stage 3: True
2026-02-26 14:10:39,849 - INFO -    🚫 Block Stage 4: True
2026-02-26 14:10:39,849 - INFO -    📊 Adjust risk by regime: True
2026-02-26 14:10:39,865 - INFO - 📥 Loading data from 2021-01-01 (buffer) to 2024-02-06...
2026-02-26 14:10:39,866 - INFO - 🎯 Universe size: 566 tickers
2026-02-26 14:10:39,866 - INFO - 🛡️  Survivorship bias protection: PIT mask will determine eligibility quarterly
2026-02-26 14:10:39,866 - INFO - ⚡ Fetching data for 566 tickers in parallel...
2026-02-26 14:10:40,194 - WARNING - ❌ SKIP AMTM: None returned
2026-02-26 14:10:40,207 - WARNING - ❌ SKIP ANSS: None returned
2026-02-26 14:10:40,487 - WARNING - ❌ SKIP ATVI: None returned
2026-02-26 14:10:40,677 - INFO -    100/566...
2026-02-26 14:10:40,818 - WARNING - ❌ SKIP CDAY: None returned
2026-02-26 14:10:41,011 - WARNING - ❌ SKIP CTXS: None returned
2026-02-26 14:10:41,297 - INFO -    200/566...
2026-02-26 14:10:41,312 - WARNING - ❌ SKIP DRE: None returned
2026-02-26 14:10:41,348 - WARNING - ❌ SKIP FB: None returned
2026-02-26 14:10:41,356 - WARNING - ❌ SKIP FBHS: None returned
2026-02-26 14:10:41,361 - WARNING - ❌ SKIP FI: None returned
2026-02-26 14:10:41,373 - WARNING - ❌ SKIP FISV: None returned
2026-02-26 14:10:41,999 - INFO -    300/566...
2026-02-26 14:10:42,778 - INFO -    400/566...
2026-02-26 14:10:43,512 - INFO -    500/566...
2026-02-26 14:10:43,959 - WARNING - ⚠️  Skipped 28 tickers (insufficient data)
2026-02-26 14:10:43,959 - INFO -    First 10 failed: ['AMTM (None returned)', 'ANSS (None returned)', 'ATVI (None returned)', 'CDAY (None returned)', 'CTXS (None returned)', 'DRE (None returned)', 'FB (None returned)', 'FBHS (None returned)', 'FI (None returned)', 'FISV (None returned)']
2026-02-26 14:10:43,959 - INFO - ℹ️  538 tickers with partial data (gaps in history)
2026-02-26 14:10:44,187 - INFO - Memory: 6.4 MB for 538 tickers (core DataFrames)
2026-02-26 14:10:44,187 - INFO - 🛡️  Building Point-in-Time tradeable mask (survivorship bias protection)...
2026-02-26 14:10:44,241 - INFO - PointInTimeUniverse: loaded 1230 ticker membership records
2026-02-26 14:10:44,310 - INFO - Tradeable mask: 376,609/418,564 cells (90.0%) across 538 S&P 500 + 0 non-S&P tickers, 778 trading days
2026-02-26 14:10:44,331 - INFO -    🛡️  Masked out 41,955 cells (10.0%) as non-tradeable (pre-IPO, post-delist, not in S&P 500)
2026-02-26 14:10:44,346 - WARNING -    ⚠️ No precomputed metrics found in cache, will calculate on the fly
2026-02-26 14:10:44,948 - INFO -    ⚠️ Precomputed metrics not available, calculating on the fly...
2026-02-26 14:10:44,981 - INFO -    ⚠️ SMA50 missing in cache, calculating on the fly...
2026-02-26 14:10:45,842 - INFO -    Loading SPY and VIX data for Market Regime...
2026-02-26 14:10:45,842 - INFO - 📊 Loading SPY and VIX data (2021-01-01 to 2024-02-06)...
2026-02-26 14:10:45,845 - INFO -    ✅ SPY loaded from cache: 778 bars
2026-02-26 14:10:45,848 - INFO -    ✅ VIX loaded from cache: 778 bars
2026-02-26 14:10:45,848 - INFO -    ✅ Market data loaded successfully
2026-02-26 14:10:45,855 - INFO -    ✅ Market Data Loaded & Aligned
2026-02-26 14:10:45,855 - INFO - ✅ Loaded: 538 tickers
2026-02-26 14:10:45,856 - INFO - 🛡️  Filtered out 28 tickers (insufficient data)
2026-02-26 14:10:45,856 - INFO -    Date range: 2021-01-04 to 2024-02-06 (778 days)
2026-02-26 14:10:45,856 - INFO -    🔧 Truncating data to start_date: 2022-01-01
2026-02-26 14:10:46,071 - INFO - Memory: ~15.2 MB total after float32 conversion
2026-02-26 14:10:46,089 - INFO - 🎯 Starting advanced backtest with partial exits...
2026-02-26 14:10:46,090 - INFO - 📥 Loading data from 2021-01-01 (buffer) to 2024-02-06...
2026-02-26 14:10:46,090 - INFO - 🎯 Universe size: 538 tickers
2026-02-26 14:10:46,091 - INFO - 🛡️  Survivorship bias protection: PIT mask will determine eligibility quarterly
2026-02-26 14:10:46,091 - INFO - ⚡ Fetching data for 538 tickers in parallel...
2026-02-26 14:10:46,898 - INFO -    100/538...
2026-02-26 14:10:47,579 - INFO -    200/538...
2026-02-26 14:10:48,299 - INFO -    300/538...
2026-02-26 14:10:49,095 - INFO -    400/538...
2026-02-26 14:10:49,806 - INFO -    500/538...
2026-02-26 14:10:50,075 - INFO - ℹ️  538 tickers with partial data (gaps in history)
2026-02-26 14:10:50,312 - INFO - Memory: 6.4 MB for 538 tickers (core DataFrames)
2026-02-26 14:10:50,312 - INFO - 🛡️  Building Point-in-Time tradeable mask (survivorship bias protection)...
2026-02-26 14:10:50,367 - INFO - PointInTimeUniverse: loaded 1230 ticker membership records
2026-02-26 14:10:50,439 - INFO - Tradeable mask: 376,609/418,564 cells (90.0%) across 538 S&P 500 + 0 non-S&P tickers, 778 trading days
2026-02-26 14:10:50,460 - INFO -    🛡️  Masked out 41,955 cells (10.0%) as non-tradeable (pre-IPO, post-delist, not in S&P 500)
2026-02-26 14:10:50,480 - WARNING -    ⚠️ No precomputed metrics found in cache, will calculate on the fly
2026-02-26 14:10:51,108 - INFO -    ⚠️ Precomputed metrics not available, calculating on the fly...
2026-02-26 14:10:51,141 - INFO -    ⚠️ SMA50 missing in cache, calculating on the fly...
2026-02-26 14:10:52,447 - INFO -    Loading SPY and VIX data for Market Regime...
2026-02-26 14:10:52,447 - INFO - 📊 Loading SPY and VIX data (2021-01-01 to 2024-02-06)...
2026-02-26 14:10:52,451 - INFO -    ✅ SPY loaded from cache: 778 bars
2026-02-26 14:10:52,454 - INFO -    ✅ VIX loaded from cache: 778 bars
2026-02-26 14:10:52,454 - INFO -    ✅ Market data loaded successfully
2026-02-26 14:10:52,463 - INFO -    ✅ Market Data Loaded & Aligned
2026-02-26 14:10:52,463 - INFO - ✅ Loaded: 538 tickers
2026-02-26 14:10:52,463 - INFO -    Date range: 2021-01-04 to 2024-02-06 (778 days)
2026-02-26 14:10:52,463 - INFO -    🔧 Truncating data to start_date: 2022-01-01
2026-02-26 14:10:52,676 - INFO - Memory: ~15.2 MB total after float32 conversion
2026-02-26 14:10:52,718 - INFO - 🔍 Calculating entry signals...
2026-02-26 14:10:52,721 - INFO -    🎯 Using TREND signal (close > SMA20)
2026-02-26 14:10:52,722 - INFO -    📊 ADVANCED MODE entries (before Adaptive Filter): 133000
2026-02-26 14:10:52,722 - INFO -       Base entry passed: 133000
2026-02-26 14:10:52,748 - INFO - 🛡️  PIT Universe filter: blocked 0 entries on non-member dates (133000 remaining)
2026-02-26 14:10:52,762 - INFO - 🔧 Applying Adaptive Filter Engine (TIER 1-2-3) - OPTIMIZADO...
2026-02-26 14:10:52,762 - INFO - 🔧 AdaptiveFilterEngine initialized
   ⚡ Applying Adaptive Filter: 100%|████| 526/526 [00:01<00:00, 279.93day/s]
2026-02-26 14:10:54,643 - INFO -    📊 Entries antes de Adaptive Filter: 133000
2026-02-26 14:10:54,643 - INFO -    ❌ Entries rechazadas por TIER:
2026-02-26 14:10:54,644 - INFO -       TIER 1 (Market Safety): 37907
2026-02-26 14:10:54,644 - INFO -       TIER 2 (Dynamic Quality): 38227
2026-02-26 14:10:54,644 - INFO -       TIER 3 (Optional): 96
2026-02-26 14:10:54,644 - INFO -    ✅ Entries finales: 56770

======================================================================
📊 ADAPTIVE FILTER ENGINE - RESUMEN (OPTIMIZADO)
======================================================================
  Total de Rechazos: 76230
  • TIER 1 (Market Safety): 37907
  • TIER 2 (Dynamic Quality): 38227
  TIER 3 (Optional): 96
======================================================================
2026-02-26 14:10:54,760 - INFO - 🔍 Clasificando riesgo por RVOL (VolTrig)...
2026-02-26 14:10:54,765 - INFO -    ☔ Danger (RVOL>=3.0x): 201 entries → Size 50%
2026-02-26 14:10:54,765 - INFO -    ⚠️  Warning (RVOL>=2.0x): 1134 entries → Size 75%
2026-02-26 14:10:54,765 - INFO -    ✅ Safe (RVOL<2.0x): 55435 entries → Size 100%
2026-02-26 14:10:54,765 - INFO - 🔍 Clasificando riesgo por ADR (volatilidad)...
2026-02-26 14:10:54,841 - INFO -    🔥 High ADR (>6.0%): 191 entries → Size 25%
2026-02-26 14:10:54,841 - INFO -    ⚠️  Med ADR (>5.0%): 408 entries → Size 33%
2026-02-26 14:10:54,881 - INFO - 📊 Multi-chunk mode: 526 days → 2 chunks of ~500 days
2026-02-26 14:10:54,882 - INFO - 🔄 Running multi-chunk backtest: 2 chunks...
2026-02-26 14:10:54,887 - INFO -    📦 Chunk 1/2: days 0-263 (capital: $100,000)
2026-02-26 14:10:54,894 - INFO - 🔄 Running single-chunk backtest with Numba Core...
2026-02-26 14:10:54,894 - INFO - 🔄 Converting DataFrames to NumPy arrays (float32 optimization)...
2026-02-26 14:10:54,929 - INFO -    ✅ Arrays prepared: 7.0 MB total
2026-02-26 14:10:54,930 - INFO -    📊 Array shapes: close=(263, 538), high=(263, 538)
2026-02-26 14:10:54,930 - INFO - ⚡ Ejecutando simulación ultra-rápida (Numba Core)...
2026-02-26 14:10:54,930 - INFO -    🚀 Using pre-calculated NumPy arrays (memory optimized - float32)
2026-02-26 14:10:54,937 - INFO -    💰 Numba Core usando FIXED DOLLAR RISK: $1000 → risk_pct=0.0100
2026-02-26 14:10:54,937 - INFO - 🔧 NUMBA CORE PARAMETERS:
2026-02-26 14:10:54,937 - INFO -    Initial Capital: $100,000.00
2026-02-26 14:10:54,937 - INFO -    Risk per Trade: $1,000.00
2026-02-26 14:10:54,937 - INFO -    Use Fixed Risk: True
2026-02-26 14:10:54,937 - INFO -    TP1/TP2 Targets: 1.892928503880745R / 2.956247789495818R
2026-02-26 14:10:54,937 - INFO -    TP Distribution: 45% / 30% / 25%
2026-02-26 14:10:54,937 - INFO -    Max Stop %%: 8.0% (decimal: 0.08)
2026-02-26 14:10:54,937 - INFO -    Trailing Stop: False
2026-02-26 14:10:54,938 - INFO -    ATR Stop Mode: False
2026-02-26 14:10:54,938 - INFO -    Total Entries Signals: 23353
2026-02-26 14:10:54,939 - INFO - 🚀 Numba Simulation Time: 0.0011s
2026-02-26 14:10:54,939 - INFO - 📊 Numba Core Results:
2026-02-26 14:10:54,939 - INFO -    Entry signals found: 23353
2026-02-26 14:10:54,939 - INFO -    Trades executed: 35
2026-02-26 14:10:54,940 - INFO -    Conversion rate: 0.1%
2026-02-26 14:10:54,940 - INFO -    Final equity: $96,295.14
2026-02-26 14:10:54,940 - WARNING -    ⚠️ Low conversion rate (0.1%) - Check parameters
2026-02-26 14:10:54,940 - WARNING -    May indicate: Restrictive filters, large stop distances, or insufficient capital
2026-02-26 14:10:54,940 - INFO -    Exit distribution: STOP=18, TP1=8, TP2=5, RUNNER=4
2026-02-26 14:10:55,410 - INFO -    ✅ Chunk 1 complete: 35 trades, final equity $96,295
2026-02-26 14:10:55,857 - INFO -    📦 Chunk 2/2: days 263-526 (capital: $96,295)
2026-02-26 14:10:55,861 - INFO - 🔄 Running single-chunk backtest with Numba Core...
2026-02-26 14:10:55,862 - INFO - 🔄 Converting DataFrames to NumPy arrays (float32 optimization)...
2026-02-26 14:10:55,898 - INFO -    ✅ Arrays prepared: 7.0 MB total
2026-02-26 14:10:55,898 - INFO -    📊 Array shapes: close=(263, 538), high=(263, 538)
2026-02-26 14:10:55,898 - INFO - ⚡ Ejecutando simulación ultra-rápida (Numba Core)...
2026-02-26 14:10:55,898 - INFO -    🚀 Using pre-calculated NumPy arrays (memory optimized - float32)
2026-02-26 14:10:55,903 - INFO -    💰 Numba Core usando FIXED DOLLAR RISK: $1000 → risk_pct=0.0104
2026-02-26 14:10:55,904 - INFO - 🔧 NUMBA CORE PARAMETERS:
2026-02-26 14:10:55,904 - INFO -    Initial Capital: $96,295.14
2026-02-26 14:10:55,904 - INFO -    Risk per Trade: $1,000.00
2026-02-26 14:10:55,904 - INFO -    Use Fixed Risk: True
2026-02-26 14:10:55,904 - INFO -    TP1/TP2 Targets: 1.892928503880745R / 2.956247789495818R
2026-02-26 14:10:55,904 - INFO -    TP Distribution: 45% / 30% / 25%
2026-02-26 14:10:55,904 - INFO -    Max Stop %%: 8.0% (decimal: 0.08)
2026-02-26 14:10:55,904 - INFO -    Trailing Stop: False
2026-02-26 14:10:55,904 - INFO -    ATR Stop Mode: False
2026-02-26 14:10:55,904 - INFO -    Total Entries Signals: 33417
2026-02-26 14:10:55,905 - INFO - 🚀 Numba Simulation Time: 0.0009s
2026-02-26 14:10:55,905 - INFO - 📊 Numba Core Results:
2026-02-26 14:10:55,906 - INFO -    Entry signals found: 33417
2026-02-26 14:10:55,906 - INFO -    Trades executed: 44
2026-02-26 14:10:55,906 - INFO -    Conversion rate: 0.1%
2026-02-26 14:10:55,906 - INFO -    Final equity: $108,564.68
2026-02-26 14:10:55,906 - WARNING -    ⚠️ Low conversion rate (0.1%) - Check parameters
2026-02-26 14:10:55,906 - WARNING -    May indicate: Restrictive filters, large stop distances, or insufficient capital
2026-02-26 14:10:55,906 - INFO -    Exit distribution: STOP=18, TP1=12, TP2=9, RUNNER=5
2026-02-26 14:10:56,375 - INFO -    ✅ Chunk 2 complete: 44 trades, final equity $108,565
2026-02-26 14:10:56,828 - INFO - ✅ Multi-chunk backtest complete: 79 total trades
2026-02-26 14:10:56,832 - INFO - ✅ Backtest complete!
2026-02-26 14:10:56,832 - INFO -    Return: 8.56%
2026-02-26 14:10:56,832 - INFO -    Annualized Return: 4.02%
2026-02-26 14:10:56,832 - INFO -    Sharpe: 0.35
2026-02-26 14:10:56,832 - INFO -    Max DD: -16.60%
2026-02-26 14:10:56,832 - INFO -    MAR Ratio: 0.24
2026-02-26 14:10:56,832 - INFO -    Calmar Ratio: 0.24
2026-02-26 14:10:56,832 - INFO -    Win Rate: 53.2%
2026-02-26 14:10:56,832 - INFO -    Trades: 56770 entries → 79 total exits (including partial)
2026-02-26 14:10:56,839 - INFO - ============================================================
2026-02-26 14:10:56,840 - INFO - 🚀 MODE: PRODUCTION (Fixed Dollar Risk)
2026-02-26 14:10:56,840 - INFO -    • Risk: FIXED DOLLAR ($1000)
2026-02-26 14:10:56,840 - INFO -    • Compounding: DISABLED
2026-02-26 14:10:56,840 - INFO - ============================================================
2026-02-26 14:10:56,841 - INFO - 🚀 Advanced VectorBT Engine initialized
2026-02-26 14:10:56,842 - INFO - 📅 Period: 2022-01-01 to 2024-02-06
2026-02-26 14:10:56,842 - INFO - 🎯 Universe: 566 tickers
2026-02-26 14:10:56,842 - INFO - 🎛️  Liquidity: vol≥100k, $vol≥$98M, ADR≥1.622727553333787%, RVOL≥0.6037738940288999x
2026-02-26 14:10:56,842 - INFO - 🎛️  Position Size: RVOL Danger≥3.0x→50%, Warning≥2.0x→75%
2026-02-26 14:10:56,842 - INFO - ============================================================
2026-02-26 14:10:56,842 - INFO - 🌍 MARKET REGIME FILTER ENABLED
2026-02-26 14:10:56,842 - INFO - ============================================================
2026-02-26 14:10:56,842 - INFO - 📊 Loading SPY and VIX data (2022-01-01 to 2024-02-06)...
2026-02-26 14:10:56,844 - INFO -    ✅ SPY loaded from cache: 526 bars
2026-02-26 14:10:56,846 - INFO -    ✅ VIX loaded from cache: 526 bars
2026-02-26 14:10:56,847 - INFO -    ✅ Market data loaded successfully
2026-02-26 14:10:56,851 - INFO -    ✅ Market regime classifier initialized
2026-02-26 14:10:56,851 - INFO -    🚫 Block Stage 3: True
2026-02-26 14:10:56,851 - INFO -    🚫 Block Stage 4: True
2026-02-26 14:10:56,851 - INFO -    📊 Adjust risk by regime: True
2026-02-26 14:10:56,867 - INFO - 📥 Loading data from 2021-01-01 (buffer) to 2024-02-06...
2026-02-26 14:10:56,867 - INFO - 🎯 Universe size: 566 tickers
2026-02-26 14:10:56,867 - INFO - 🛡️  Survivorship bias protection: PIT mask will determine eligibility quarterly
2026-02-26 14:10:56,867 - INFO - ⚡ Fetching data for 566 tickers in parallel...
2026-02-26 14:10:57,164 - WARNING - ❌ SKIP AMTM: None returned
2026-02-26 14:10:57,165 - WARNING - ❌ SKIP ANSS: None returned
2026-02-26 14:10:57,427 - WARNING - ❌ SKIP ATVI: None returned
2026-02-26 14:10:57,614 - INFO -    100/566...
2026-02-26 14:10:57,730 - WARNING - ❌ SKIP CDAY: None returned
2026-02-26 14:10:57,959 - WARNING - ❌ SKIP CTXS: None returned
2026-02-26 14:10:58,249 - INFO -    200/566...
2026-02-26 14:10:58,258 - WARNING - ❌ SKIP DRE: None returned
2026-02-26 14:10:58,297 - WARNING - ❌ SKIP FB: None returned
2026-02-26 14:10:58,303 - WARNING - ❌ SKIP FBHS: None returned
2026-02-26 14:10:58,316 - WARNING - ❌ SKIP FI: None returned
2026-02-26 14:10:58,326 - WARNING - ❌ SKIP FLT: None returned
2026-02-26 14:10:58,977 - INFO -    300/566...
2026-02-26 14:10:59,781 - INFO -    400/566...
2026-02-26 14:11:00,505 - INFO -    500/566...
2026-02-26 14:11:00,948 - WARNING - ⚠️  Skipped 28 tickers (insufficient data)
2026-02-26 14:11:00,948 - INFO -    First 10 failed: ['AMTM (None returned)', 'ANSS (None returned)', 'ATVI (None returned)', 'CDAY (None returned)', 'CTXS (None returned)', 'DRE (None returned)', 'FB (None returned)', 'FBHS (None returned)', 'FI (None returned)', 'FLT (None returned)']
2026-02-26 14:11:00,948 - INFO - ℹ️  538 tickers with partial data (gaps in history)
2026-02-26 14:11:01,178 - INFO - Memory: 6.4 MB for 538 tickers (core DataFrames)
2026-02-26 14:11:01,179 - INFO - 🛡️  Building Point-in-Time tradeable mask (survivorship bias protection)...
2026-02-26 14:11:01,235 - INFO - PointInTimeUniverse: loaded 1230 ticker membership records
2026-02-26 14:11:01,305 - INFO - Tradeable mask: 376,609/418,564 cells (90.0%) across 538 S&P 500 + 0 non-S&P tickers, 778 trading days
2026-02-26 14:11:01,329 - INFO -    🛡️  Masked out 41,955 cells (10.0%) as non-tradeable (pre-IPO, post-delist, not in S&P 500)
2026-02-26 14:11:01,345 - WARNING -    ⚠️ No precomputed metrics found in cache, will calculate on the fly
2026-02-26 14:11:01,961 - INFO -    ⚠️ Precomputed metrics not available, calculating on the fly...
2026-02-26 14:11:01,997 - INFO -    ⚠️ SMA50 missing in cache, calculating on the fly...
2026-02-26 14:11:02,860 - INFO -    Loading SPY and VIX data for Market Regime...
2026-02-26 14:11:02,861 - INFO - 📊 Loading SPY and VIX data (2021-01-01 to 2024-02-06)...
2026-02-26 14:11:02,863 - INFO -    ✅ SPY loaded from cache: 778 bars
2026-02-26 14:11:02,867 - INFO -    ✅ VIX loaded from cache: 778 bars
2026-02-26 14:11:02,867 - INFO -    ✅ Market data loaded successfully
2026-02-26 14:11:02,875 - INFO -    ✅ Market Data Loaded & Aligned
2026-02-26 14:11:02,876 - INFO - ✅ Loaded: 538 tickers
2026-02-26 14:11:02,876 - INFO - 🛡️  Filtered out 28 tickers (insufficient data)
2026-02-26 14:11:02,876 - INFO -    Date range: 2021-01-04 to 2024-02-06 (778 days)
2026-02-26 14:11:02,876 - INFO -    🔧 Truncating data to start_date: 2022-01-01
2026-02-26 14:11:03,088 - INFO - Memory: ~15.2 MB total after float32 conversion
2026-02-26 14:11:03,106 - INFO - 🎯 Starting advanced backtest with partial exits...
2026-02-26 14:11:03,107 - INFO - 📥 Loading data from 2021-01-01 (buffer) to 2024-02-06...
2026-02-26 14:11:03,107 - INFO - 🎯 Universe size: 538 tickers
2026-02-26 14:11:03,108 - INFO - 🛡️  Survivorship bias protection: PIT mask will determine eligibility quarterly
2026-02-26 14:11:03,108 - INFO - ⚡ Fetching data for 538 tickers in parallel...
2026-02-26 14:11:03,902 - INFO -    100/538...
2026-02-26 14:11:04,560 - INFO -    200/538...
2026-02-26 14:11:05,197 - INFO -    300/538...
2026-02-26 14:11:06,572 - INFO -    400/538...
2026-02-26 14:11:07,314 - INFO -    500/538...
2026-02-26 14:11:07,597 - INFO - ℹ️  538 tickers with partial data (gaps in history)
2026-02-26 14:11:07,835 - INFO - Memory: 6.4 MB for 538 tickers (core DataFrames)
2026-02-26 14:11:07,835 - INFO - 🛡️  Building Point-in-Time tradeable mask (survivorship bias protection)...
2026-02-26 14:11:07,891 - INFO - PointInTimeUniverse: loaded 1230 ticker membership records
2026-02-26 14:11:07,959 - INFO - Tradeable mask: 376,609/418,564 cells (90.0%) across 538 S&P 500 + 0 non-S&P tickers, 778 trading days
2026-02-26 14:11:07,981 - INFO -    🛡️  Masked out 41,955 cells (10.0%) as non-tradeable (pre-IPO, post-delist, not in S&P 500)
2026-02-26 14:11:08,003 - WARNING -    ⚠️ No precomputed metrics found in cache, will calculate on the fly
2026-02-26 14:11:08,620 - INFO -    ⚠️ Precomputed metrics not available, calculating on the fly...
2026-02-26 14:11:08,653 - INFO -    ⚠️ SMA50 missing in cache, calculating on the fly...
2026-02-26 14:11:10,014 - INFO -    Loading SPY and VIX data for Market Regime...
2026-02-26 14:11:10,014 - INFO - 📊 Loading SPY and VIX data (2021-01-01 to 2024-02-06)...
2026-02-26 14:11:10,016 - INFO -    ✅ SPY loaded from cache: 778 bars
2026-02-26 14:11:10,019 - INFO -    ✅ VIX loaded from cache: 778 bars
2026-02-26 14:11:10,020 - INFO -    ✅ Market data loaded successfully
2026-02-26 14:11:10,026 - INFO -    ✅ Market Data Loaded & Aligned
2026-02-26 14:11:10,027 - INFO - ✅ Loaded: 538 tickers
2026-02-26 14:11:10,027 - INFO -    Date range: 2021-01-04 to 2024-02-06 (778 days)
2026-02-26 14:11:10,027 - INFO -    🔧 Truncating data to start_date: 2022-01-01
2026-02-26 14:11:10,240 - INFO - Memory: ~15.2 MB total after float32 conversion
2026-02-26 14:11:10,282 - INFO - 🔍 Calculating entry signals...
2026-02-26 14:11:10,285 - INFO -    🎯 Using TREND signal (close > SMA20)
2026-02-26 14:11:10,285 - INFO -    📊 ADVANCED MODE entries (before Adaptive Filter): 133000
2026-02-26 14:11:10,286 - INFO -       Base entry passed: 133000
2026-02-26 14:11:10,310 - INFO - 🛡️  PIT Universe filter: blocked 0 entries on non-member dates (133000 remaining)
2026-02-26 14:11:10,327 - INFO - 🔧 Applying Adaptive Filter Engine (TIER 1-2-3) - OPTIMIZADO...
2026-02-26 14:11:10,327 - INFO - 🔧 AdaptiveFilterEngine initialized
   ⚡ Applying Adaptive Filter: 100%|████| 526/526 [00:01<00:00, 283.72day/s]
2026-02-26 14:11:12,183 - INFO -    📊 Entries antes de Adaptive Filter: 133000
2026-02-26 14:11:12,183 - INFO -    ❌ Entries rechazadas por TIER:
2026-02-26 14:11:12,183 - INFO -       TIER 1 (Market Safety): 37907
2026-02-26 14:11:12,183 - INFO -       TIER 2 (Dynamic Quality): 33822
2026-02-26 14:11:12,183 - INFO -       TIER 3 (Optional): 93
2026-02-26 14:11:12,183 - INFO -    ✅ Entries finales: 61178

======================================================================
📊 ADAPTIVE FILTER ENGINE - RESUMEN (OPTIMIZADO)
======================================================================
  Total de Rechazos: 71822
  • TIER 1 (Market Safety): 37907
  • TIER 2 (Dynamic Quality): 33822
  TIER 3 (Optional): 93
======================================================================
2026-02-26 14:11:12,287 - INFO - 🔍 Clasificando riesgo por RVOL (VolTrig)...
2026-02-26 14:11:12,292 - INFO -    ☔ Danger (RVOL>=3.0x): 200 entries → Size 50%
2026-02-26 14:11:12,292 - INFO -    ⚠️  Warning (RVOL>=2.0x): 1192 entries → Size 75%
2026-02-26 14:11:12,292 - INFO -    ✅ Safe (RVOL<2.0x): 59786 entries → Size 100%
2026-02-26 14:11:12,292 - INFO - 🔍 Clasificando riesgo por ADR (volatilidad)...
2026-02-26 14:11:12,365 - INFO -    🔥 High ADR (>6.0%): 168 entries → Size 25%
2026-02-26 14:11:12,365 - INFO -    ⚠️  Med ADR (>5.0%): 372 entries → Size 33%
2026-02-26 14:11:12,403 - INFO - 📊 Multi-chunk mode: 526 days → 2 chunks of ~500 days
2026-02-26 14:11:12,403 - INFO - 🔄 Running multi-chunk backtest: 2 chunks...
2026-02-26 14:11:12,407 - INFO -    📦 Chunk 1/2: days 0-263 (capital: $100,000)
2026-02-26 14:11:12,414 - INFO - 🔄 Running single-chunk backtest with Numba Core...
2026-02-26 14:11:12,415 - INFO - 🔄 Converting DataFrames to NumPy arrays (float32 optimization)...
2026-02-26 14:11:12,451 - INFO -    ✅ Arrays prepared: 7.0 MB total
2026-02-26 14:11:12,451 - INFO -    📊 Array shapes: close=(263, 538), high=(263, 538)
2026-02-26 14:11:12,452 - INFO - ⚡ Ejecutando simulación ultra-rápida (Numba Core)...
2026-02-26 14:11:12,452 - INFO -    🚀 Using pre-calculated NumPy arrays (memory optimized - float32)
2026-02-26 14:11:12,457 - INFO -    💰 Numba Core usando FIXED DOLLAR RISK: $1000 → risk_pct=0.0100
2026-02-26 14:11:12,458 - INFO - 🔧 NUMBA CORE PARAMETERS:
2026-02-26 14:11:12,458 - INFO -    Initial Capital: $100,000.00
2026-02-26 14:11:12,458 - INFO -    Risk per Trade: $1,000.00
2026-02-26 14:11:12,458 - INFO -    Use Fixed Risk: True
2026-02-26 14:11:12,458 - INFO -    TP1/TP2 Targets: 1.8702287632215184R / 3.514488588018797R
2026-02-26 14:11:12,458 - INFO -    TP Distribution: 45% / 30% / 25%
2026-02-26 14:11:12,458 - INFO -    Max Stop %%: 8.0% (decimal: 0.08)
2026-02-26 14:11:12,458 - INFO -    Trailing Stop: False
2026-02-26 14:11:12,458 - INFO -    ATR Stop Mode: False
2026-02-26 14:11:12,459 - INFO -    Total Entries Signals: 23320
2026-02-26 14:11:12,460 - INFO - 🚀 Numba Simulation Time: 0.0014s
2026-02-26 14:11:12,461 - INFO - 📊 Numba Core Results:
2026-02-26 14:11:12,461 - INFO -    Entry signals found: 23320
2026-02-26 14:11:12,461 - INFO -    Trades executed: 29
2026-02-26 14:11:12,461 - INFO -    Conversion rate: 0.1%
2026-02-26 14:11:12,461 - INFO -    Final equity: $93,166.36
2026-02-26 14:11:12,461 - WARNING -    ⚠️ Low conversion rate (0.1%) - Check parameters
2026-02-26 14:11:12,461 - WARNING -    May indicate: Restrictive filters, large stop distances, or insufficient capital
2026-02-26 14:11:12,461 - INFO -    Exit distribution: STOP=19, TP1=8, TP2=1, RUNNER=1
2026-02-26 14:11:12,918 - INFO -    ✅ Chunk 1 complete: 29 trades, final equity $93,166
2026-02-26 14:11:13,375 - INFO -    📦 Chunk 2/2: days 263-526 (capital: $93,166)
2026-02-26 14:11:13,381 - INFO - 🔄 Running single-chunk backtest with Numba Core...
2026-02-26 14:11:13,381 - INFO - 🔄 Converting DataFrames to NumPy arrays (float32 optimization)...
2026-02-26 14:11:13,418 - INFO -    ✅ Arrays prepared: 7.0 MB total
2026-02-26 14:11:13,418 - INFO -    📊 Array shapes: close=(263, 538), high=(263, 538)
2026-02-26 14:11:13,419 - INFO - ⚡ Ejecutando simulación ultra-rápida (Numba Core)...
2026-02-26 14:11:13,419 - INFO -    🚀 Using pre-calculated NumPy arrays (memory optimized - float32)
2026-02-26 14:11:13,425 - INFO -    💰 Numba Core usando FIXED DOLLAR RISK: $1000 → risk_pct=0.0107
2026-02-26 14:11:13,425 - INFO - 🔧 NUMBA CORE PARAMETERS:
2026-02-26 14:11:13,425 - INFO -    Initial Capital: $93,166.36
2026-02-26 14:11:13,425 - INFO -    Risk per Trade: $1,000.00
2026-02-26 14:11:13,425 - INFO -    Use Fixed Risk: True
2026-02-26 14:11:13,425 - INFO -    TP1/TP2 Targets: 1.8702287632215184R / 3.514488588018797R
2026-02-26 14:11:13,426 - INFO -    TP Distribution: 45% / 30% / 25%
2026-02-26 14:11:13,426 - INFO -    Max Stop %%: 8.0% (decimal: 0.08)
2026-02-26 14:11:13,426 - INFO -    Trailing Stop: False
2026-02-26 14:11:13,426 - INFO -    ATR Stop Mode: False
2026-02-26 14:11:13,426 - INFO -    Total Entries Signals: 37858
2026-02-26 14:11:13,427 - INFO - 🚀 Numba Simulation Time: 0.0008s
2026-02-26 14:11:13,427 - INFO - 📊 Numba Core Results:
2026-02-26 14:11:13,427 - INFO -    Entry signals found: 37858
2026-02-26 14:11:13,427 - INFO -    Trades executed: 40
2026-02-26 14:11:13,427 - INFO -    Conversion rate: 0.1%
2026-02-26 14:11:13,428 - INFO -    Final equity: $99,376.86
2026-02-26 14:11:13,428 - WARNING -    ⚠️ Low conversion rate (0.1%) - Check parameters
2026-02-26 14:11:13,428 - WARNING -    May indicate: Restrictive filters, large stop distances, or insufficient capital
2026-02-26 14:11:13,428 - INFO -    Exit distribution: STOP=18, TP1=10, TP2=8, RUNNER=4
2026-02-26 14:11:13,893 - INFO -    ✅ Chunk 2 complete: 40 trades, final equity $99,377
2026-02-26 14:11:14,344 - INFO - ✅ Multi-chunk backtest complete: 69 total trades
2026-02-26 14:11:14,348 - INFO - ✅ Backtest complete!
2026-02-26 14:11:14,348 - INFO -    Return: -0.62%
2026-02-26 14:11:14,348 - INFO -    Annualized Return: -0.30%
2026-02-26 14:11:14,348 - INFO -    Sharpe: 0.05
2026-02-26 14:11:14,348 - INFO -    Max DD: -18.68%
2026-02-26 14:11:14,348 - INFO -    MAR Ratio: -0.02
2026-02-26 14:11:14,348 - INFO -    Calmar Ratio: -0.02
2026-02-26 14:11:14,348 - INFO -    Win Rate: 46.4%
2026-02-26 14:11:14,348 - INFO -    Trades: 61178 entries → 69 total exits (including partial)
2026-02-26 14:11:14,355 - INFO - ============================================================
2026-02-26 14:11:14,355 - INFO - 🚀 MODE: PRODUCTION (Fixed Dollar Risk)
2026-02-26 14:11:14,356 - INFO -    • Risk: FIXED DOLLAR ($1000)
2026-02-26 14:11:14,356 - INFO -    • Compounding: DISABLED
2026-02-26 14:11:14,356 - INFO - ============================================================
2026-02-26 14:11:14,357 - INFO - 🚀 Advanced VectorBT Engine initialized
2026-02-26 14:11:14,357 - INFO - 📅 Period: 2022-01-01 to 2024-02-06
2026-02-26 14:11:14,357 - INFO - 🎯 Universe: 566 tickers
2026-02-26 14:11:14,358 - INFO - 🎛️  Liquidity: vol≥100k, $vol≥$98M, ADR≥1.524228488995532%, RVOL≥0.6376785392805497x
2026-02-26 14:11:14,358 - INFO - 🎛️  Position Size: RVOL Danger≥3.0x→50%, Warning≥2.0x→75%
2026-02-26 14:11:14,358 - INFO - ============================================================
2026-02-26 14:11:14,358 - INFO - 🌍 MARKET REGIME FILTER ENABLED
2026-02-26 14:11:14,359 - INFO - ============================================================
2026-02-26 14:11:14,359 - INFO - 📊 Loading SPY and VIX data (2022-01-01 to 2024-02-06)...
2026-02-26 14:11:14,361 - INFO -    ✅ SPY loaded from cache: 526 bars
2026-02-26 14:11:14,363 - INFO -    ✅ VIX loaded from cache: 526 bars
2026-02-26 14:11:14,364 - INFO -    ✅ Market data loaded successfully
2026-02-26 14:11:14,368 - INFO -    ✅ Market regime classifier initialized
2026-02-26 14:11:14,369 - INFO -    🚫 Block Stage 3: True
2026-02-26 14:11:14,369 - INFO -    🚫 Block Stage 4: True
2026-02-26 14:11:14,369 - INFO -    📊 Adjust risk by regime: True
2026-02-26 14:11:14,384 - INFO - 📥 Loading data from 2021-01-01 (buffer) to 2024-02-06...
2026-02-26 14:11:14,385 - INFO - 🎯 Universe size: 566 tickers
2026-02-26 14:11:14,385 - INFO - 🛡️  Survivorship bias protection: PIT mask will determine eligibility quarterly
2026-02-26 14:11:14,385 - INFO - ⚡ Fetching data for 566 tickers in parallel...
2026-02-26 14:11:14,690 - WARNING - ❌ SKIP AMTM: None returned
2026-02-26 14:11:14,691 - WARNING - ❌ SKIP ANSS: None returned
2026-02-26 14:11:14,930 - WARNING - ❌ SKIP ATVI: None returned
2026-02-26 14:11:15,149 - INFO -    100/566...
2026-02-26 14:11:15,282 - WARNING - ❌ SKIP CDAY: None returned
2026-02-26 14:11:15,480 - WARNING - ❌ SKIP CTXS: None returned
2026-02-26 14:11:15,779 - INFO -    200/566...
2026-02-26 14:11:15,783 - WARNING - ❌ SKIP DRE: None returned
2026-02-26 14:11:15,828 - WARNING - ❌ SKIP FB: None returned
2026-02-26 14:11:15,830 - WARNING - ❌ SKIP FBHS: None returned
2026-02-26 14:11:15,832 - WARNING - ❌ SKIP FI: None returned
2026-02-26 14:11:15,861 - WARNING - ❌ SKIP FLT: None returned
2026-02-26 14:11:16,462 - INFO -    300/566...
2026-02-26 14:11:17,249 - INFO -    400/566...
2026-02-26 14:11:17,971 - INFO -    500/566...
2026-02-26 14:11:18,443 - WARNING - ⚠️  Skipped 28 tickers (insufficient data)
2026-02-26 14:11:18,443 - INFO -    First 10 failed: ['AMTM (None returned)', 'ANSS (None returned)', 'ATVI (None returned)', 'CDAY (None returned)', 'CTXS (None returned)', 'DRE (None returned)', 'FB (None returned)', 'FBHS (None returned)', 'FI (None returned)', 'FLT (None returned)']
2026-02-26 14:11:18,443 - INFO - ℹ️  538 tickers with partial data (gaps in history)
2026-02-26 14:11:18,671 - INFO - Memory: 6.4 MB for 538 tickers (core DataFrames)
2026-02-26 14:11:18,671 - INFO - 🛡️  Building Point-in-Time tradeable mask (survivorship bias protection)...
2026-02-26 14:11:18,726 - INFO - PointInTimeUniverse: loaded 1230 ticker membership records
2026-02-26 14:11:18,795 - INFO - Tradeable mask: 376,609/418,564 cells (90.0%) across 538 S&P 500 + 0 non-S&P tickers, 778 trading days
2026-02-26 14:11:18,815 - INFO -    🛡️  Masked out 41,955 cells (10.0%) as non-tradeable (pre-IPO, post-delist, not in S&P 500)
2026-02-26 14:11:18,833 - WARNING -    ⚠️ No precomputed metrics found in cache, will calculate on the fly
2026-02-26 14:11:19,433 - INFO -    ⚠️ Precomputed metrics not available, calculating on the fly...
2026-02-26 14:11:19,467 - INFO -    ⚠️ SMA50 missing in cache, calculating on the fly...
2026-02-26 14:11:20,327 - INFO -    Loading SPY and VIX data for Market Regime...
2026-02-26 14:11:20,328 - INFO - 📊 Loading SPY and VIX data (2021-01-01 to 2024-02-06)...
2026-02-26 14:11:20,330 - INFO -    ✅ SPY loaded from cache: 778 bars
2026-02-26 14:11:20,332 - INFO -    ✅ VIX loaded from cache: 778 bars
2026-02-26 14:11:20,333 - INFO -    ✅ Market data loaded successfully
2026-02-26 14:11:20,339 - INFO -    ✅ Market Data Loaded & Aligned
2026-02-26 14:11:20,340 - INFO - ✅ Loaded: 538 tickers
2026-02-26 14:11:20,340 - INFO - 🛡️  Filtered out 28 tickers (insufficient data)
2026-02-26 14:11:20,340 - INFO -    Date range: 2021-01-04 to 2024-02-06 (778 days)
2026-02-26 14:11:20,340 - INFO -    🔧 Truncating data to start_date: 2022-01-01
2026-02-26 14:11:20,549 - INFO - Memory: ~15.2 MB total after float32 conversion
2026-02-26 14:11:20,567 - INFO - 🎯 Starting advanced backtest with partial exits...
2026-02-26 14:11:20,568 - INFO - 📥 Loading data from 2021-01-01 (buffer) to 2024-02-06...
2026-02-26 14:11:20,568 - INFO - 🎯 Universe size: 538 tickers
2026-02-26 14:11:20,568 - INFO - 🛡️  Survivorship bias protection: PIT mask will determine eligibility quarterly
2026-02-26 14:11:20,569 - INFO - ⚡ Fetching data for 538 tickers in parallel...
2026-02-26 14:11:21,343 - INFO -    100/538...
2026-02-26 14:11:21,979 - INFO -    200/538...
2026-02-26 14:11:22,637 - INFO -    300/538...
2026-02-26 14:11:23,394 - INFO -    400/538...
2026-02-26 14:11:24,115 - INFO -    500/538...
2026-02-26 14:11:24,378 - INFO - ℹ️  538 tickers with partial data (gaps in history)
2026-02-26 14:11:24,615 - INFO - Memory: 6.4 MB for 538 tickers (core DataFrames)
2026-02-26 14:11:24,615 - INFO - 🛡️  Building Point-in-Time tradeable mask (survivorship bias protection)...
2026-02-26 14:11:24,669 - INFO - PointInTimeUniverse: loaded 1230 ticker membership records
2026-02-26 14:11:24,738 - INFO - Tradeable mask: 376,609/418,564 cells (90.0%) across 538 S&P 500 + 0 non-S&P tickers, 778 trading days
2026-02-26 14:11:24,759 - INFO -    🛡️  Masked out 41,955 cells (10.0%) as non-tradeable (pre-IPO, post-delist, not in S&P 500)
2026-02-26 14:11:24,779 - WARNING -    ⚠️ No precomputed metrics found in cache, will calculate on the fly
2026-02-26 14:11:25,413 - INFO -    ⚠️ Precomputed metrics not available, calculating on the fly...
2026-02-26 14:11:25,448 - INFO -    ⚠️ SMA50 missing in cache, calculating on the fly...
2026-02-26 14:11:26,753 - INFO -    Loading SPY and VIX data for Market Regime...
2026-02-26 14:11:26,754 - INFO - 📊 Loading SPY and VIX data (2021-01-01 to 2024-02-06)...
2026-02-26 14:11:26,756 - INFO -    ✅ SPY loaded from cache: 778 bars
2026-02-26 14:11:26,759 - INFO -    ✅ VIX loaded from cache: 778 bars
2026-02-26 14:11:26,759 - INFO -    ✅ Market data loaded successfully
2026-02-26 14:11:26,766 - INFO -    ✅ Market Data Loaded & Aligned
2026-02-26 14:11:26,766 - INFO - ✅ Loaded: 538 tickers
2026-02-26 14:11:26,767 - INFO -    Date range: 2021-01-04 to 2024-02-06 (778 days)
2026-02-26 14:11:26,767 - INFO -    🔧 Truncating data to start_date: 2022-01-01
2026-02-26 14:11:26,979 - INFO - Memory: ~15.2 MB total after float32 conversion
2026-02-26 14:11:27,021 - INFO - 🔍 Calculating entry signals...
2026-02-26 14:11:27,024 - INFO -    🎯 Using TREND signal (close > SMA20)
2026-02-26 14:11:27,024 - INFO -    📊 ADVANCED MODE entries (before Adaptive Filter): 133000
2026-02-26 14:11:27,025 - INFO -       Base entry passed: 133000
2026-02-26 14:11:27,050 - INFO - 🛡️  PIT Universe filter: blocked 0 entries on non-member dates (133000 remaining)
2026-02-26 14:11:27,066 - INFO - 🔧 Applying Adaptive Filter Engine (TIER 1-2-3) - OPTIMIZADO...
2026-02-26 14:11:27,066 - INFO - 🔧 AdaptiveFilterEngine initialized
   ⚡ Applying Adaptive Filter: 100%|████| 526/526 [00:01<00:00, 277.63day/s]
2026-02-26 14:11:28,962 - INFO -    📊 Entries antes de Adaptive Filter: 133000
2026-02-26 14:11:28,962 - INFO -    ❌ Entries rechazadas por TIER:
2026-02-26 14:11:28,963 - INFO -       TIER 1 (Market Safety): 37907
2026-02-26 14:11:28,963 - INFO -       TIER 2 (Dynamic Quality): 31622
2026-02-26 14:11:28,963 - INFO -       TIER 3 (Optional): 92
2026-02-26 14:11:28,963 - INFO -    ✅ Entries finales: 63379

======================================================================
📊 ADAPTIVE FILTER ENGINE - RESUMEN (OPTIMIZADO)
======================================================================
  Total de Rechazos: 69621
  • TIER 1 (Market Safety): 37907
  • TIER 2 (Dynamic Quality): 31622
  TIER 3 (Optional): 92
======================================================================
2026-02-26 14:11:29,068 - INFO - 🔍 Clasificando riesgo por RVOL (VolTrig)...
2026-02-26 14:11:29,072 - INFO -    ☔ Danger (RVOL>=3.0x): 226 entries → Size 50%
2026-02-26 14:11:29,073 - INFO -    ⚠️  Warning (RVOL>=2.0x): 1305 entries → Size 75%
2026-02-26 14:11:29,073 - INFO -    ✅ Safe (RVOL<2.0x): 61848 entries → Size 100%
2026-02-26 14:11:29,073 - INFO - 🔍 Clasificando riesgo por ADR (volatilidad)...
2026-02-26 14:11:29,148 - INFO -    🔥 High ADR (>6.0%): 165 entries → Size 25%
2026-02-26 14:11:29,148 - INFO -    ⚠️  Med ADR (>5.0%): 355 entries → Size 33%
2026-02-26 14:11:29,187 - INFO - 📊 Multi-chunk mode: 526 days → 2 chunks of ~500 days
2026-02-26 14:11:29,187 - INFO - 🔄 Running multi-chunk backtest: 2 chunks...
2026-02-26 14:11:29,191 - INFO -    📦 Chunk 1/2: days 0-263 (capital: $100,000)
2026-02-26 14:11:29,198 - INFO - 🔄 Running single-chunk backtest with Numba Core...
2026-02-26 14:11:29,198 - INFO - 🔄 Converting DataFrames to NumPy arrays (float32 optimization)...
2026-02-26 14:11:29,233 - INFO -    ✅ Arrays prepared: 7.0 MB total
2026-02-26 14:11:29,234 - INFO -    📊 Array shapes: close=(263, 538), high=(263, 538)
2026-02-26 14:11:29,234 - INFO - ⚡ Ejecutando simulación ultra-rápida (Numba Core)...
2026-02-26 14:11:29,234 - INFO -    🚀 Using pre-calculated NumPy arrays (memory optimized - float32)
2026-02-26 14:11:29,240 - INFO -    💰 Numba Core usando FIXED DOLLAR RISK: $1000 → risk_pct=0.0100
2026-02-26 14:11:29,240 - INFO - 🔧 NUMBA CORE PARAMETERS:
2026-02-26 14:11:29,240 - INFO -    Initial Capital: $100,000.00
2026-02-26 14:11:29,240 - INFO -    Risk per Trade: $1,000.00
2026-02-26 14:11:29,240 - INFO -    Use Fixed Risk: True
2026-02-26 14:11:29,241 - INFO -    TP1/TP2 Targets: 1.9406292985846867R / 3.370215673656869R
2026-02-26 14:11:29,241 - INFO -    TP Distribution: 45% / 30% / 25%
2026-02-26 14:11:29,241 - INFO -    Max Stop %%: 8.0% (decimal: 0.08)
2026-02-26 14:11:29,241 - INFO -    Trailing Stop: False
2026-02-26 14:11:29,241 - INFO -    ATR Stop Mode: False
2026-02-26 14:11:29,241 - INFO -    Total Entries Signals: 23392
2026-02-26 14:11:29,243 - INFO - 🚀 Numba Simulation Time: 0.0013s
2026-02-26 14:11:29,243 - INFO - 📊 Numba Core Results:
2026-02-26 14:11:29,243 - INFO -    Entry signals found: 23392
2026-02-26 14:11:29,243 - INFO -    Trades executed: 27
2026-02-26 14:11:29,243 - INFO -    Conversion rate: 0.1%
2026-02-26 14:11:29,243 - INFO -    Final equity: $93,626.42
2026-02-26 14:11:29,243 - WARNING -    ⚠️ Low conversion rate (0.1%) - Check parameters
2026-02-26 14:11:29,243 - WARNING -    May indicate: Restrictive filters, large stop distances, or insufficient capital
2026-02-26 14:11:29,243 - INFO -    Exit distribution: STOP=17, TP1=6, TP2=2, RUNNER=2
2026-02-26 14:11:29,700 - INFO -    ✅ Chunk 1 complete: 27 trades, final equity $93,626
2026-02-26 14:11:30,149 - INFO -    📦 Chunk 2/2: days 263-526 (capital: $93,626)
2026-02-26 14:11:30,154 - INFO - 🔄 Running single-chunk backtest with Numba Core...
2026-02-26 14:11:30,155 - INFO - 🔄 Converting DataFrames to NumPy arrays (float32 optimization)...
2026-02-26 14:11:30,192 - INFO -    ✅ Arrays prepared: 7.0 MB total
2026-02-26 14:11:30,193 - INFO -    📊 Array shapes: close=(263, 538), high=(263, 538)
2026-02-26 14:11:30,193 - INFO - ⚡ Ejecutando simulación ultra-rápida (Numba Core)...
2026-02-26 14:11:30,193 - INFO -    🚀 Using pre-calculated NumPy arrays (memory optimized - float32)
2026-02-26 14:11:30,199 - INFO -    💰 Numba Core usando FIXED DOLLAR RISK: $1000 → risk_pct=0.0107
2026-02-26 14:11:30,199 - INFO - 🔧 NUMBA CORE PARAMETERS:
2026-02-26 14:11:30,199 - INFO -    Initial Capital: $93,626.42
2026-02-26 14:11:30,199 - INFO -    Risk per Trade: $1,000.00
2026-02-26 14:11:30,199 - INFO -    Use Fixed Risk: True
2026-02-26 14:11:30,199 - INFO -    TP1/TP2 Targets: 1.9406292985846867R / 3.370215673656869R
2026-02-26 14:11:30,200 - INFO -    TP Distribution: 45% / 30% / 25%
2026-02-26 14:11:30,200 - INFO -    Max Stop %%: 8.0% (decimal: 0.08)
2026-02-26 14:11:30,200 - INFO -    Trailing Stop: False
2026-02-26 14:11:30,200 - INFO -    ATR Stop Mode: False
2026-02-26 14:11:30,200 - INFO -    Total Entries Signals: 39987
2026-02-26 14:11:30,201 - INFO - 🚀 Numba Simulation Time: 0.0009s
2026-02-26 14:11:30,201 - INFO - 📊 Numba Core Results:
2026-02-26 14:11:30,201 - INFO -    Entry signals found: 39987
2026-02-26 14:11:30,201 - INFO -    Trades executed: 37
2026-02-26 14:11:30,201 - INFO -    Conversion rate: 0.1%
2026-02-26 14:11:30,202 - INFO -    Final equity: $101,291.23
2026-02-26 14:11:30,202 - WARNING -    ⚠️ Low conversion rate (0.1%) - Check parameters
2026-02-26 14:11:30,202 - WARNING -    May indicate: Restrictive filters, large stop distances, or insufficient capital
2026-02-26 14:11:30,202 - INFO -    Exit distribution: STOP=17, TP1=10, TP2=7, RUNNER=3
2026-02-26 14:11:30,660 - INFO -    ✅ Chunk 2 complete: 37 trades, final equity $101,291
2026-02-26 14:11:31,112 - INFO - ✅ Multi-chunk backtest complete: 64 total trades
2026-02-26 14:11:31,115 - INFO - ✅ Backtest complete!
2026-02-26 14:11:31,115 - INFO -    Return: 1.29%
2026-02-26 14:11:31,116 - INFO -    Annualized Return: 0.62%
2026-02-26 14:11:31,116 - INFO -    Sharpe: 0.11
2026-02-26 14:11:31,116 - INFO -    Max DD: -20.34%
2026-02-26 14:11:31,116 - INFO -    MAR Ratio: 0.03
2026-02-26 14:11:31,116 - INFO -    Calmar Ratio: 0.03
2026-02-26 14:11:31,116 - INFO -    Win Rate: 45.3%
2026-02-26 14:11:31,116 - INFO -    Trades: 63379 entries → 64 total exits (including partial)
2026-02-26 14:11:31,122 - INFO - ============================================================
2026-02-26 14:11:31,123 - INFO - 🚀 MODE: PRODUCTION (Fixed Dollar Risk)
2026-02-26 14:11:31,123 - INFO -    • Risk: FIXED DOLLAR ($1000)
2026-02-26 14:11:31,123 - INFO -    • Compounding: DISABLED
2026-02-26 14:11:31,123 - INFO - ============================================================
2026-02-26 14:11:31,124 - INFO - 🚀 Advanced VectorBT Engine initialized
2026-02-26 14:11:31,124 - INFO - 📅 Period: 2022-01-01 to 2024-02-06
2026-02-26 14:11:31,125 - INFO - 🎯 Universe: 566 tickers
2026-02-26 14:11:31,125 - INFO - 🎛️  Liquidity: vol≥100k, $vol≥$98M, ADR≥1.7993290560204933%, RVOL≥0.6781575862188881x
2026-02-26 14:11:31,125 - INFO - 🎛️  Position Size: RVOL Danger≥3.0x→50%, Warning≥2.0x→75%
2026-02-26 14:11:31,125 - INFO - ============================================================
2026-02-26 14:11:31,125 - INFO - 🌍 MARKET REGIME FILTER ENABLED
2026-02-26 14:11:31,125 - INFO - ============================================================
2026-02-26 14:11:31,125 - INFO - 📊 Loading SPY and VIX data (2022-01-01 to 2024-02-06)...
2026-02-26 14:11:31,127 - INFO -    ✅ SPY loaded from cache: 526 bars
2026-02-26 14:11:31,130 - INFO -    ✅ VIX loaded from cache: 526 bars
2026-02-26 14:11:31,131 - INFO -    ✅ Market data loaded successfully
2026-02-26 14:11:31,137 - INFO -    ✅ Market regime classifier initialized
2026-02-26 14:11:31,137 - INFO -    🚫 Block Stage 3: True
2026-02-26 14:11:31,138 - INFO -    🚫 Block Stage 4: True
2026-02-26 14:11:31,138 - INFO -    📊 Adjust risk by regime: True
2026-02-26 14:11:31,152 - INFO - 📥 Loading data from 2021-01-01 (buffer) to 2024-02-06...
2026-02-26 14:11:31,152 - INFO - 🎯 Universe size: 566 tickers
2026-02-26 14:11:31,152 - INFO - 🛡️  Survivorship bias protection: PIT mask will determine eligibility quarterly
2026-02-26 14:11:31,152 - INFO - ⚡ Fetching data for 566 tickers in parallel...
2026-02-26 14:11:31,454 - WARNING - ❌ SKIP AMTM: None returned
2026-02-26 14:11:31,459 - WARNING - ❌ SKIP ANSS: None returned
2026-02-26 14:11:31,713 - WARNING - ❌ SKIP ATVI: None returned
2026-02-26 14:11:31,905 - INFO -    100/566...
2026-02-26 14:11:32,058 - WARNING - ❌ SKIP CDAY: None returned
2026-02-26 14:11:32,228 - WARNING - ❌ SKIP CTXS: None returned
2026-02-26 14:11:32,549 - INFO -    200/566...
2026-02-26 14:11:32,558 - WARNING - ❌ SKIP DRE: None returned
2026-02-26 14:11:32,599 - WARNING - ❌ SKIP FB: None returned
2026-02-26 14:11:32,602 - WARNING - ❌ SKIP FBHS: None returned
2026-02-26 14:11:32,609 - WARNING - ❌ SKIP FI: None returned
2026-02-26 14:11:32,624 - WARNING - ❌ SKIP FLT: None returned
2026-02-26 14:11:33,239 - INFO -    300/566...
2026-02-26 14:11:34,018 - INFO -    400/566...
2026-02-26 14:11:34,744 - INFO -    500/566...
2026-02-26 14:11:35,196 - WARNING - ⚠️  Skipped 28 tickers (insufficient data)
2026-02-26 14:11:35,196 - INFO -    First 10 failed: ['AMTM (None returned)', 'ANSS (None returned)', 'ATVI (None returned)', 'CDAY (None returned)', 'CTXS (None returned)', 'DRE (None returned)', 'FB (None returned)', 'FBHS (None returned)', 'FI (None returned)', 'FLT (None returned)']
2026-02-26 14:11:35,196 - INFO - ℹ️  538 tickers with partial data (gaps in history)
2026-02-26 14:11:35,426 - INFO - Memory: 6.4 MB for 538 tickers (core DataFrames)
2026-02-26 14:11:35,426 - INFO - 🛡️  Building Point-in-Time tradeable mask (survivorship bias protection)...
2026-02-26 14:11:35,481 - INFO - PointInTimeUniverse: loaded 1230 ticker membership records
2026-02-26 14:11:35,558 - INFO - Tradeable mask: 376,609/418,564 cells (90.0%) across 538 S&P 500 + 0 non-S&P tickers, 778 trading days
2026-02-26 14:11:35,578 - INFO -    🛡️  Masked out 41,955 cells (10.0%) as non-tradeable (pre-IPO, post-delist, not in S&P 500)
2026-02-26 14:11:35,594 - WARNING -    ⚠️ No precomputed metrics found in cache, will calculate on the fly
2026-02-26 14:11:36,211 - INFO -    ⚠️ Precomputed metrics not available, calculating on the fly...
2026-02-26 14:11:36,245 - INFO -    ⚠️ SMA50 missing in cache, calculating on the fly...
2026-02-26 14:11:37,110 - INFO -    Loading SPY and VIX data for Market Regime...
2026-02-26 14:11:37,110 - INFO - 📊 Loading SPY and VIX data (2021-01-01 to 2024-02-06)...
2026-02-26 14:11:37,113 - INFO -    ✅ SPY loaded from cache: 778 bars
2026-02-26 14:11:37,116 - INFO -    ✅ VIX loaded from cache: 778 bars
2026-02-26 14:11:37,117 - INFO -    ✅ Market data loaded successfully
2026-02-26 14:11:37,124 - INFO -    ✅ Market Data Loaded & Aligned
2026-02-26 14:11:37,124 - INFO - ✅ Loaded: 538 tickers
2026-02-26 14:11:37,124 - INFO - 🛡️  Filtered out 28 tickers (insufficient data)
2026-02-26 14:11:37,124 - INFO -    Date range: 2021-01-04 to 2024-02-06 (778 days)
2026-02-26 14:11:37,124 - INFO -    🔧 Truncating data to start_date: 2022-01-01
2026-02-26 14:11:37,339 - INFO - Memory: ~15.2 MB total after float32 conversion
2026-02-26 14:11:37,358 - INFO - 🎯 Starting advanced backtest with partial exits...
2026-02-26 14:11:37,359 - INFO - 📥 Loading data from 2021-01-01 (buffer) to 2024-02-06...
2026-02-26 14:11:37,359 - INFO - 🎯 Universe size: 538 tickers
2026-02-26 14:11:37,360 - INFO - 🛡️  Survivorship bias protection: PIT mask will determine eligibility quarterly
2026-02-26 14:11:37,360 - INFO - ⚡ Fetching data for 538 tickers in parallel...
2026-02-26 14:11:38,162 - INFO -    100/538...
2026-02-26 14:11:39,505 - INFO -    200/538...
2026-02-26 14:11:40,185 - INFO -    300/538...
2026-02-26 14:11:40,971 - INFO -    400/538...
2026-02-26 14:11:41,718 - INFO -    500/538...
2026-02-26 14:11:41,987 - INFO - ℹ️  538 tickers with partial data (gaps in history)
2026-02-26 14:11:42,223 - INFO - Memory: 6.4 MB for 538 tickers (core DataFrames)
2026-02-26 14:11:42,223 - INFO - 🛡️  Building Point-in-Time tradeable mask (survivorship bias protection)...
2026-02-26 14:11:42,277 - INFO - PointInTimeUniverse: loaded 1230 ticker membership records
2026-02-26 14:11:42,349 - INFO - Tradeable mask: 376,609/418,564 cells (90.0%) across 538 S&P 500 + 0 non-S&P tickers, 778 trading days
2026-02-26 14:11:42,370 - INFO -    🛡️  Masked out 41,955 cells (10.0%) as non-tradeable (pre-IPO, post-delist, not in S&P 500)
2026-02-26 14:11:42,391 - WARNING -    ⚠️ No precomputed metrics found in cache, will calculate on the fly
2026-02-26 14:11:43,010 - INFO -    ⚠️ Precomputed metrics not available, calculating on the fly...
2026-02-26 14:11:43,044 - INFO -    ⚠️ SMA50 missing in cache, calculating on the fly...
2026-02-26 14:11:44,349 - INFO -    Loading SPY and VIX data for Market Regime...
2026-02-26 14:11:44,350 - INFO - 📊 Loading SPY and VIX data (2021-01-01 to 2024-02-06)...
2026-02-26 14:11:44,352 - INFO -    ✅ SPY loaded from cache: 778 bars
2026-02-26 14:11:44,355 - INFO -    ✅ VIX loaded from cache: 778 bars
2026-02-26 14:11:44,355 - INFO -    ✅ Market data loaded successfully
2026-02-26 14:11:44,362 - INFO -    ✅ Market Data Loaded & Aligned
2026-02-26 14:11:44,363 - INFO - ✅ Loaded: 538 tickers
2026-02-26 14:11:44,363 - INFO -    Date range: 2021-01-04 to 2024-02-06 (778 days)
2026-02-26 14:11:44,363 - INFO -    🔧 Truncating data to start_date: 2022-01-01
2026-02-26 14:11:44,580 - INFO - Memory: ~15.2 MB total after float32 conversion
2026-02-26 14:11:44,623 - INFO - 🔍 Calculating entry signals...
2026-02-26 14:11:44,625 - INFO -    🎯 Using TREND signal (close > SMA20)
2026-02-26 14:11:44,626 - INFO -    📊 ADVANCED MODE entries (before Adaptive Filter): 133000
2026-02-26 14:11:44,627 - INFO -       Base entry passed: 133000
2026-02-26 14:11:44,652 - INFO - 🛡️  PIT Universe filter: blocked 0 entries on non-member dates (133000 remaining)
2026-02-26 14:11:44,669 - INFO - 🔧 Applying Adaptive Filter Engine (TIER 1-2-3) - OPTIMIZADO...
2026-02-26 14:11:44,670 - INFO - 🔧 AdaptiveFilterEngine initialized
   ⚡ Applying Adaptive Filter: 100%|████| 526/526 [00:01<00:00, 283.59day/s]
2026-02-26 14:11:46,526 - INFO -    📊 Entries antes de Adaptive Filter: 133000
2026-02-26 14:11:46,526 - INFO -    ❌ Entries rechazadas por TIER:
2026-02-26 14:11:46,526 - INFO -       TIER 1 (Market Safety): 37907
2026-02-26 14:11:46,526 - INFO -       TIER 2 (Dynamic Quality): 46824
2026-02-26 14:11:46,536 - INFO -       TIER 3 (Optional): 79
2026-02-26 14:11:46,536 - INFO -    ✅ Entries finales: 48190

======================================================================
📊 ADAPTIVE FILTER ENGINE - RESUMEN (OPTIMIZADO)
======================================================================
  Total de Rechazos: 84810
  • TIER 1 (Market Safety): 37907
  • TIER 2 (Dynamic Quality): 46824
  TIER 3 (Optional): 79
======================================================================
2026-02-26 14:11:46,673 - INFO - 🔍 Clasificando riesgo por RVOL (VolTrig)...
2026-02-26 14:11:46,677 - INFO -    ☔ Danger (RVOL>=3.0x): 190 entries → Size 50%
2026-02-26 14:11:46,678 - INFO -    ⚠️  Warning (RVOL>=2.0x): 1078 entries → Size 75%
2026-02-26 14:11:46,678 - INFO -    ✅ Safe (RVOL<2.0x): 46922 entries → Size 100%
2026-02-26 14:11:46,678 - INFO - 🔍 Clasificando riesgo por ADR (volatilidad)...
2026-02-26 14:11:46,752 - INFO -    🔥 High ADR (>6.0%): 150 entries → Size 25%
2026-02-26 14:11:46,753 - INFO -    ⚠️  Med ADR (>5.0%): 331 entries → Size 33%
2026-02-26 14:11:46,791 - INFO - 📊 Multi-chunk mode: 526 days → 2 chunks of ~500 days
2026-02-26 14:11:46,791 - INFO - 🔄 Running multi-chunk backtest: 2 chunks...
2026-02-26 14:11:46,796 - INFO -    📦 Chunk 1/2: days 0-263 (capital: $100,000)
2026-02-26 14:11:46,801 - INFO - 🔄 Running single-chunk backtest with Numba Core...
2026-02-26 14:11:46,802 - INFO - 🔄 Converting DataFrames to NumPy arrays (float32 optimization)...
2026-02-26 14:11:46,838 - INFO -    ✅ Arrays prepared: 7.0 MB total
2026-02-26 14:11:46,838 - INFO -    📊 Array shapes: close=(263, 538), high=(263, 538)
2026-02-26 14:11:46,838 - INFO - ⚡ Ejecutando simulación ultra-rápida (Numba Core)...
2026-02-26 14:11:46,838 - INFO -    🚀 Using pre-calculated NumPy arrays (memory optimized - float32)
2026-02-26 14:11:46,845 - INFO -    💰 Numba Core usando FIXED DOLLAR RISK: $1000 → risk_pct=0.0100
2026-02-26 14:11:46,845 - INFO - 🔧 NUMBA CORE PARAMETERS:
2026-02-26 14:11:46,845 - INFO -    Initial Capital: $100,000.00
2026-02-26 14:11:46,845 - INFO -    Risk per Trade: $1,000.00
2026-02-26 14:11:46,845 - INFO -    Use Fixed Risk: True
2026-02-26 14:11:46,845 - INFO -    TP1/TP2 Targets: 1.6582212440640423R / 3.473866023879612R
2026-02-26 14:11:46,845 - INFO -    TP Distribution: 45% / 30% / 25%
2026-02-26 14:11:46,845 - INFO -    Max Stop %%: 8.0% (decimal: 0.08)
2026-02-26 14:11:46,845 - INFO -    Trailing Stop: False
2026-02-26 14:11:46,845 - INFO -    ATR Stop Mode: False
2026-02-26 14:11:46,846 - INFO -    Total Entries Signals: 19853
2026-02-26 14:11:46,847 - INFO - 🚀 Numba Simulation Time: 0.0013s
2026-02-26 14:11:46,847 - INFO - 📊 Numba Core Results:
2026-02-26 14:11:46,848 - INFO -    Entry signals found: 19853
2026-02-26 14:11:46,848 - INFO -    Trades executed: 33
2026-02-26 14:11:46,848 - INFO -    Conversion rate: 0.2%
2026-02-26 14:11:46,848 - INFO -    Final equity: $96,607.09
2026-02-26 14:11:46,848 - WARNING -    ⚠️ Low conversion rate (0.2%) - Check parameters
2026-02-26 14:11:46,848 - WARNING -    May indicate: Restrictive filters, large stop distances, or insufficient capital
2026-02-26 14:11:46,848 - INFO -    Exit distribution: STOP=18, TP1=11, TP2=2, RUNNER=2
2026-02-26 14:11:47,311 - INFO -    ✅ Chunk 1 complete: 33 trades, final equity $96,607
2026-02-26 14:11:47,761 - INFO -    📦 Chunk 2/2: days 263-526 (capital: $96,607)
2026-02-26 14:11:47,766 - INFO - 🔄 Running single-chunk backtest with Numba Core...
2026-02-26 14:11:47,766 - INFO - 🔄 Converting DataFrames to NumPy arrays (float32 optimization)...
2026-02-26 14:11:47,804 - INFO -    ✅ Arrays prepared: 7.0 MB total
2026-02-26 14:11:47,804 - INFO -    📊 Array shapes: close=(263, 538), high=(263, 538)
2026-02-26 14:11:47,804 - INFO - ⚡ Ejecutando simulación ultra-rápida (Numba Core)...
2026-02-26 14:11:47,804 - INFO -    🚀 Using pre-calculated NumPy arrays (memory optimized - float32)
2026-02-26 14:11:47,810 - INFO -    💰 Numba Core usando FIXED DOLLAR RISK: $1000 → risk_pct=0.0104
2026-02-26 14:11:47,810 - INFO - 🔧 NUMBA CORE PARAMETERS:
2026-02-26 14:11:47,810 - INFO -    Initial Capital: $96,607.09
2026-02-26 14:11:47,810 - INFO -    Risk per Trade: $1,000.00
2026-02-26 14:11:47,810 - INFO -    Use Fixed Risk: True
2026-02-26 14:11:47,810 - INFO -    TP1/TP2 Targets: 1.6582212440640423R / 3.473866023879612R
2026-02-26 14:11:47,811 - INFO -    TP Distribution: 45% / 30% / 25%
2026-02-26 14:11:47,811 - INFO -    Max Stop %%: 8.0% (decimal: 0.08)
2026-02-26 14:11:47,811 - INFO -    Trailing Stop: False
2026-02-26 14:11:47,811 - INFO -    ATR Stop Mode: False
2026-02-26 14:11:47,811 - INFO -    Total Entries Signals: 28337
2026-02-26 14:11:47,812 - INFO - 🚀 Numba Simulation Time: 0.0011s
2026-02-26 14:11:47,813 - INFO - 📊 Numba Core Results:
2026-02-26 14:11:47,813 - INFO -    Entry signals found: 28337
2026-02-26 14:11:47,813 - INFO -    Trades executed: 46
2026-02-26 14:11:47,813 - INFO -    Conversion rate: 0.2%
2026-02-26 14:11:47,813 - INFO -    Final equity: $113,542.31
2026-02-26 14:11:47,813 - WARNING -    ⚠️ Low conversion rate (0.2%) - Check parameters
2026-02-26 14:11:47,813 - WARNING -    May indicate: Restrictive filters, large stop distances, or insufficient capital
2026-02-26 14:11:47,813 - INFO -    Exit distribution: STOP=17, TP1=15, TP2=9, RUNNER=5
2026-02-26 14:11:48,284 - INFO -    ✅ Chunk 2 complete: 46 trades, final equity $113,542
2026-02-26 14:11:48,739 - INFO - ✅ Multi-chunk backtest complete: 79 total trades
2026-02-26 14:11:48,742 - INFO - ✅ Backtest complete!
2026-02-26 14:11:48,743 - INFO -    Return: 13.54%
2026-02-26 14:11:48,743 - INFO -    Annualized Return: 6.27%
2026-02-26 14:11:48,743 - INFO -    Sharpe: 0.50
2026-02-26 14:11:48,743 - INFO -    Max DD: -17.21%
2026-02-26 14:11:48,743 - INFO -    MAR Ratio: 0.36
2026-02-26 14:11:48,743 - INFO -    Calmar Ratio: 0.36
2026-02-26 14:11:48,743 - INFO -    Win Rate: 54.4%
2026-02-26 14:11:48,743 - INFO -    Trades: 48190 entries → 79 total exits (including partial)
2026-02-26 14:11:48,750 - INFO - ============================================================
2026-02-26 14:11:48,750 - INFO - 🚀 MODE: PRODUCTION (Fixed Dollar Risk)
2026-02-26 14:11:48,751 - INFO -    • Risk: FIXED DOLLAR ($1000)
2026-02-26 14:11:48,751 - INFO -    • Compounding: DISABLED
2026-02-26 14:11:48,751 - INFO - ============================================================
2026-02-26 14:11:48,752 - INFO - 🚀 Advanced VectorBT Engine initialized
2026-02-26 14:11:48,753 - INFO - 📅 Period: 2022-01-01 to 2024-02-06
2026-02-26 14:11:48,753 - INFO - 🎯 Universe: 566 tickers
2026-02-26 14:11:48,753 - INFO - 🎛️  Liquidity: vol≥100k, $vol≥$98M, ADR≥1.690466583988212%, RVOL≥0.6944236264174306x
2026-02-26 14:11:48,753 - INFO - 🎛️  Position Size: RVOL Danger≥3.0x→50%, Warning≥2.0x→75%
2026-02-26 14:11:48,753 - INFO - ============================================================
2026-02-26 14:11:48,753 - INFO - 🌍 MARKET REGIME FILTER ENABLED
2026-02-26 14:11:48,753 - INFO - ============================================================
2026-02-26 14:11:48,753 - INFO - 📊 Loading SPY and VIX data (2022-01-01 to 2024-02-06)...
2026-02-26 14:11:48,756 - INFO -    ✅ SPY loaded from cache: 526 bars
2026-02-26 14:11:48,758 - INFO -    ✅ VIX loaded from cache: 526 bars
2026-02-26 14:11:48,758 - INFO -    ✅ Market data loaded successfully
2026-02-26 14:11:48,763 - INFO -    ✅ Market regime classifier initialized
2026-02-26 14:11:48,763 - INFO -    🚫 Block Stage 3: True
2026-02-26 14:11:48,763 - INFO -    🚫 Block Stage 4: True
2026-02-26 14:11:48,763 - INFO -    📊 Adjust risk by regime: True
2026-02-26 14:11:48,778 - INFO - 📥 Loading data from 2021-01-01 (buffer) to 2024-02-06...
2026-02-26 14:11:48,779 - INFO - 🎯 Universe size: 566 tickers
2026-02-26 14:11:48,779 - INFO - 🛡️  Survivorship bias protection: PIT mask will determine eligibility quarterly
2026-02-26 14:11:48,779 - INFO - ⚡ Fetching data for 566 tickers in parallel...
2026-02-26 14:11:49,066 - WARNING - ❌ SKIP AMTM: None returned
2026-02-26 14:11:49,072 - WARNING - ❌ SKIP ANSS: None returned
2026-02-26 14:11:49,330 - WARNING - ❌ SKIP ATVI: None returned
2026-02-26 14:11:49,521 - INFO -    100/566...
2026-02-26 14:11:49,615 - WARNING - ❌ SKIP CDAY: None returned
2026-02-26 14:11:49,873 - WARNING - ❌ SKIP CTXS: None returned
2026-02-26 14:11:50,181 - INFO -    200/566...
2026-02-26 14:11:50,191 - WARNING - ❌ SKIP DRE: None returned
2026-02-26 14:11:50,234 - WARNING - ❌ SKIP FB: None returned
2026-02-26 14:11:50,236 - WARNING - ❌ SKIP FBHS: None returned
2026-02-26 14:11:50,242 - WARNING - ❌ SKIP FI: None returned
2026-02-26 14:11:50,262 - WARNING - ❌ SKIP FLT: None returned
2026-02-26 14:11:50,871 - INFO -    300/566...
2026-02-26 14:11:51,680 - INFO -    400/566...
2026-02-26 14:11:52,400 - INFO -    500/566...
2026-02-26 14:11:52,836 - WARNING - ⚠️  Skipped 28 tickers (insufficient data)
2026-02-26 14:11:52,836 - INFO -    First 10 failed: ['AMTM (None returned)', 'ANSS (None returned)', 'ATVI (None returned)', 'CDAY (None returned)', 'CTXS (None returned)', 'DRE (None returned)', 'FB (None returned)', 'FBHS (None returned)', 'FI (None returned)', 'FLT (None returned)']
2026-02-26 14:11:52,836 - INFO - ℹ️  538 tickers with partial data (gaps in history)
2026-02-26 14:11:53,065 - INFO - Memory: 6.4 MB for 538 tickers (core DataFrames)
2026-02-26 14:11:53,066 - INFO - 🛡️  Building Point-in-Time tradeable mask (survivorship bias protection)...
2026-02-26 14:11:53,121 - INFO - PointInTimeUniverse: loaded 1230 ticker membership records
2026-02-26 14:11:53,191 - INFO - Tradeable mask: 376,609/418,564 cells (90.0%) across 538 S&P 500 + 0 non-S&P tickers, 778 trading days
2026-02-26 14:11:53,212 - INFO -    🛡️  Masked out 41,955 cells (10.0%) as non-tradeable (pre-IPO, post-delist, not in S&P 500)
2026-02-26 14:11:53,228 - WARNING -    ⚠️ No precomputed metrics found in cache, will calculate on the fly
2026-02-26 14:11:53,845 - INFO -    ⚠️ Precomputed metrics not available, calculating on the fly...
2026-02-26 14:11:53,879 - INFO -    ⚠️ SMA50 missing in cache, calculating on the fly...
2026-02-26 14:11:54,749 - INFO -    Loading SPY and VIX data for Market Regime...
2026-02-26 14:11:54,749 - INFO - 📊 Loading SPY and VIX data (2021-01-01 to 2024-02-06)...
2026-02-26 14:11:54,752 - INFO -    ✅ SPY loaded from cache: 778 bars
2026-02-26 14:11:54,755 - INFO -    ✅ VIX loaded from cache: 778 bars
2026-02-26 14:11:54,756 - INFO -    ✅ Market data loaded successfully
2026-02-26 14:11:54,763 - INFO -    ✅ Market Data Loaded & Aligned
2026-02-26 14:11:54,763 - INFO - ✅ Loaded: 538 tickers
2026-02-26 14:11:54,763 - INFO - 🛡️  Filtered out 28 tickers (insufficient data)
2026-02-26 14:11:54,763 - INFO -    Date range: 2021-01-04 to 2024-02-06 (778 days)
2026-02-26 14:11:54,764 - INFO -    🔧 Truncating data to start_date: 2022-01-01
2026-02-26 14:11:54,981 - INFO - Memory: ~15.2 MB total after float32 conversion
2026-02-26 14:11:55,000 - INFO - 🎯 Starting advanced backtest with partial exits...
2026-02-26 14:11:55,001 - INFO - 📥 Loading data from 2021-01-01 (buffer) to 2024-02-06...
2026-02-26 14:11:55,001 - INFO - 🎯 Universe size: 538 tickers
2026-02-26 14:11:55,001 - INFO - 🛡️  Survivorship bias protection: PIT mask will determine eligibility quarterly
2026-02-26 14:11:55,001 - INFO - ⚡ Fetching data for 538 tickers in parallel...
2026-02-26 14:11:55,800 - INFO -    100/538...
2026-02-26 14:11:56,439 - INFO -    200/538...
2026-02-26 14:11:57,049 - INFO -    300/538...
2026-02-26 14:11:57,774 - INFO -    400/538...
2026-02-26 14:11:58,522 - INFO -    500/538...
2026-02-26 14:11:58,848 - INFO - ℹ️  538 tickers with partial data (gaps in history)
2026-02-26 14:11:59,083 - INFO - Memory: 6.4 MB for 538 tickers (core DataFrames)
2026-02-26 14:11:59,083 - INFO - 🛡️  Building Point-in-Time tradeable mask (survivorship bias protection)...
2026-02-26 14:11:59,138 - INFO - PointInTimeUniverse: loaded 1230 ticker membership records
2026-02-26 14:11:59,210 - INFO - Tradeable mask: 376,609/418,564 cells (90.0%) across 538 S&P 500 + 0 non-S&P tickers, 778 trading days
2026-02-26 14:11:59,232 - INFO -    🛡️  Masked out 41,955 cells (10.0%) as non-tradeable (pre-IPO, post-delist, not in S&P 500)
2026-02-26 14:11:59,252 - WARNING -    ⚠️ No precomputed metrics found in cache, will calculate on the fly
2026-02-26 14:11:59,883 - INFO -    ⚠️ Precomputed metrics not available, calculating on the fly...
2026-02-26 14:11:59,917 - INFO -    ⚠️ SMA50 missing in cache, calculating on the fly...
2026-02-26 14:12:01,229 - INFO -    Loading SPY and VIX data for Market Regime...
2026-02-26 14:12:01,230 - INFO - 📊 Loading SPY and VIX data (2021-01-01 to 2024-02-06)...
2026-02-26 14:12:01,232 - INFO -    ✅ SPY loaded from cache: 778 bars
2026-02-26 14:12:01,235 - INFO -    ✅ VIX loaded from cache: 778 bars
2026-02-26 14:12:01,236 - INFO -    ✅ Market data loaded successfully
2026-02-26 14:12:01,242 - INFO -    ✅ Market Data Loaded & Aligned
2026-02-26 14:12:01,243 - INFO - ✅ Loaded: 538 tickers
2026-02-26 14:12:01,243 - INFO -    Date range: 2021-01-04 to 2024-02-06 (778 days)
2026-02-26 14:12:01,243 - INFO -    🔧 Truncating data to start_date: 2022-01-01
2026-02-26 14:12:01,456 - INFO - Memory: ~15.2 MB total after float32 conversion
2026-02-26 14:12:01,499 - INFO - 🔍 Calculating entry signals...
2026-02-26 14:12:01,501 - INFO -    🎯 Using TREND signal (close > SMA20)
2026-02-26 14:12:01,502 - INFO -    📊 ADVANCED MODE entries (before Adaptive Filter): 133000
2026-02-26 14:12:01,503 - INFO -       Base entry passed: 133000
2026-02-26 14:12:01,527 - INFO - 🛡️  PIT Universe filter: blocked 0 entries on non-member dates (133000 remaining)
2026-02-26 14:12:01,543 - INFO - 🔧 Applying Adaptive Filter Engine (TIER 1-2-3) - OPTIMIZADO...
2026-02-26 14:12:01,543 - INFO - 🔧 AdaptiveFilterEngine initialized
   ⚡ Applying Adaptive Filter: 100%|████| 526/526 [00:01<00:00, 270.53day/s]
2026-02-26 14:12:03,489 - INFO -    📊 Entries antes de Adaptive Filter: 133000
2026-02-26 14:12:03,490 - INFO -    ❌ Entries rechazadas por TIER:
2026-02-26 14:12:03,490 - INFO -       TIER 1 (Market Safety): 37907
2026-02-26 14:12:03,490 - INFO -       TIER 2 (Dynamic Quality): 41868
2026-02-26 14:12:03,490 - INFO -       TIER 3 (Optional): 77
2026-02-26 14:12:03,490 - INFO -    ✅ Entries finales: 53148

======================================================================
📊 ADAPTIVE FILTER ENGINE - RESUMEN (OPTIMIZADO)
======================================================================
  Total de Rechazos: 79852
  • TIER 1 (Market Safety): 37907
  • TIER 2 (Dynamic Quality): 41868
  TIER 3 (Optional): 77
======================================================================
2026-02-26 14:12:03,628 - INFO - 🔍 Clasificando riesgo por RVOL (VolTrig)...
2026-02-26 14:12:03,632 - INFO -    ☔ Danger (RVOL>=3.0x): 222 entries → Size 50%
2026-02-26 14:12:03,633 - INFO -    ⚠️  Warning (RVOL>=2.0x): 1229 entries → Size 75%
2026-02-26 14:12:03,633 - INFO -    ✅ Safe (RVOL<2.0x): 51697 entries → Size 100%
2026-02-26 14:12:03,633 - INFO - 🔍 Clasificando riesgo por ADR (volatilidad)...
2026-02-26 14:12:03,706 - INFO -    🔥 High ADR (>6.0%): 150 entries → Size 25%
2026-02-26 14:12:03,707 - INFO -    ⚠️  Med ADR (>5.0%): 328 entries → Size 33%
2026-02-26 14:12:03,745 - INFO - 📊 Multi-chunk mode: 526 days → 2 chunks of ~500 days
2026-02-26 14:12:03,745 - INFO - 🔄 Running multi-chunk backtest: 2 chunks...
2026-02-26 14:12:03,749 - INFO -    📦 Chunk 1/2: days 0-263 (capital: $100,000)
2026-02-26 14:12:03,755 - INFO - 🔄 Running single-chunk backtest with Numba Core...
2026-02-26 14:12:03,756 - INFO - 🔄 Converting DataFrames to NumPy arrays (float32 optimization)...
2026-02-26 14:12:03,792 - INFO -    ✅ Arrays prepared: 7.0 MB total
2026-02-26 14:12:03,792 - INFO -    📊 Array shapes: close=(263, 538), high=(263, 538)
2026-02-26 14:12:03,792 - INFO - ⚡ Ejecutando simulación ultra-rápida (Numba Core)...
2026-02-26 14:12:03,792 - INFO -    🚀 Using pre-calculated NumPy arrays (memory optimized - float32)
2026-02-26 14:12:03,797 - INFO -    💰 Numba Core usando FIXED DOLLAR RISK: $1000 → risk_pct=0.0100
2026-02-26 14:12:03,797 - INFO - 🔧 NUMBA CORE PARAMETERS:
2026-02-26 14:12:03,797 - INFO -    Initial Capital: $100,000.00
2026-02-26 14:12:03,797 - INFO -    Risk per Trade: $1,000.00
2026-02-26 14:12:03,798 - INFO -    Use Fixed Risk: True
2026-02-26 14:12:03,798 - INFO -    TP1/TP2 Targets: 1.5502869791176084R / 3.45791366754242R
2026-02-26 14:12:03,798 - INFO -    TP Distribution: 45% / 30% / 25%
2026-02-26 14:12:03,798 - INFO -    Max Stop %%: 8.0% (decimal: 0.08)
2026-02-26 14:12:03,798 - INFO -    Trailing Stop: False
2026-02-26 14:12:03,798 - INFO -    ATR Stop Mode: False
2026-02-26 14:12:03,798 - INFO -    Total Entries Signals: 21150
2026-02-26 14:12:03,799 - INFO - 🚀 Numba Simulation Time: 0.0013s
2026-02-26 14:12:03,800 - INFO - 📊 Numba Core Results:
2026-02-26 14:12:03,800 - INFO -    Entry signals found: 21150
2026-02-26 14:12:03,800 - INFO -    Trades executed: 33
2026-02-26 14:12:03,800 - INFO -    Conversion rate: 0.2%
2026-02-26 14:12:03,800 - INFO -    Final equity: $96,082.61
2026-02-26 14:12:03,800 - WARNING -    ⚠️ Low conversion rate (0.2%) - Check parameters
2026-02-26 14:12:03,800 - WARNING -    May indicate: Restrictive filters, large stop distances, or insufficient capital
2026-02-26 14:12:03,801 - INFO -    Exit distribution: STOP=18, TP1=11, TP2=2, RUNNER=2
2026-02-26 14:12:04,260 - INFO -    ✅ Chunk 1 complete: 33 trades, final equity $96,083
2026-02-26 14:12:04,721 - INFO -    📦 Chunk 2/2: days 263-526 (capital: $96,083)
2026-02-26 14:12:04,726 - INFO - 🔄 Running single-chunk backtest with Numba Core...
2026-02-26 14:12:04,727 - INFO - 🔄 Converting DataFrames to NumPy arrays (float32 optimization)...
2026-02-26 14:12:04,767 - INFO -    ✅ Arrays prepared: 7.0 MB total
2026-02-26 14:12:04,768 - INFO -    📊 Array shapes: close=(263, 538), high=(263, 538)
2026-02-26 14:12:04,768 - INFO - ⚡ Ejecutando simulación ultra-rápida (Numba Core)...
2026-02-26 14:12:04,768 - INFO -    🚀 Using pre-calculated NumPy arrays (memory optimized - float32)
2026-02-26 14:12:04,773 - INFO -    💰 Numba Core usando FIXED DOLLAR RISK: $1000 → risk_pct=0.0104
2026-02-26 14:12:04,773 - INFO - 🔧 NUMBA CORE PARAMETERS:
2026-02-26 14:12:04,773 - INFO -    Initial Capital: $96,082.61
2026-02-26 14:12:04,773 - INFO -    Risk per Trade: $1,000.00
2026-02-26 14:12:04,773 - INFO -    Use Fixed Risk: True
2026-02-26 14:12:04,773 - INFO -    TP1/TP2 Targets: 1.5502869791176084R / 3.45791366754242R
2026-02-26 14:12:04,774 - INFO -    TP Distribution: 45% / 30% / 25%
2026-02-26 14:12:04,774 - INFO -    Max Stop %%: 8.0% (decimal: 0.08)
2026-02-26 14:12:04,774 - INFO -    Trailing Stop: False
2026-02-26 14:12:04,774 - INFO -    ATR Stop Mode: False
2026-02-26 14:12:04,774 - INFO -    Total Entries Signals: 31998
2026-02-26 14:12:04,775 - INFO - 🚀 Numba Simulation Time: 0.0014s
2026-02-26 14:12:04,776 - INFO - 📊 Numba Core Results:
2026-02-26 14:12:04,776 - INFO -    Entry signals found: 31998
2026-02-26 14:12:04,777 - INFO -    Trades executed: 46
2026-02-26 14:12:04,777 - INFO -    Conversion rate: 0.1%
2026-02-26 14:12:04,777 - INFO -    Final equity: $103,979.23
2026-02-26 14:12:04,777 - WARNING -    ⚠️ Low conversion rate (0.1%) - Check parameters
2026-02-26 14:12:04,777 - WARNING -    May indicate: Restrictive filters, large stop distances, or insufficient capital
2026-02-26 14:12:04,777 - INFO -    Exit distribution: STOP=20, TP1=14, TP2=8, RUNNER=4
2026-02-26 14:12:05,242 - INFO -    ✅ Chunk 2 complete: 46 trades, final equity $103,979
2026-02-26 14:12:05,694 - INFO - ✅ Multi-chunk backtest complete: 79 total trades
2026-02-26 14:12:05,699 - INFO - ✅ Backtest complete!
2026-02-26 14:12:05,699 - INFO -    Return: 3.98%
2026-02-26 14:12:05,699 - INFO -    Annualized Return: 1.89%
2026-02-26 14:12:05,700 - INFO -    Sharpe: 0.21
2026-02-26 14:12:05,700 - INFO -    Max DD: -17.71%
2026-02-26 14:12:05,700 - INFO -    MAR Ratio: 0.11
2026-02-26 14:12:05,700 - INFO -    Calmar Ratio: 0.11
2026-02-26 14:12:05,700 - INFO -    Win Rate: 50.6%
2026-02-26 14:12:05,700 - INFO -    Trades: 53148 entries → 79 total exits (including partial)
2026-02-26 14:12:36,803 - INFO -    PBO Score: 46.47% (from 20 param variations)
2026-02-26 14:12:36,962 - INFO -    Bootstrap OOS Returns:
2026-02-26 14:12:36,962 - INFO -      p5:  -18.13%
2026-02-26 14:12:36,962 - INFO -      p10: -15.29%
2026-02-26 14:12:36,962 - INFO -      p50: -1.10%
2026-02-26 14:12:36,963 - INFO -    Max Drawdown: 7.89%
2026-02-26 14:12:36,963 - INFO -    DD Duration: 105 days
2026-02-26 14:12:36,963 - INFO - 
🔥 PHASE 3: PRODUCTIONIZATION (Stress Testing)
2026-02-26 14:12:36,964 - INFO - ============================================================
2026-02-26 14:12:36,965 - INFO - 🚀 MODE: PRODUCTION (Fixed Dollar Risk)
2026-02-26 14:12:36,965 - INFO -    • Risk: FIXED DOLLAR ($1000)
2026-02-26 14:12:36,965 - INFO -    • Compounding: DISABLED
2026-02-26 14:12:36,965 - INFO - ============================================================
2026-02-26 14:12:36,967 - INFO - 🚀 Advanced VectorBT Engine initialized
2026-02-26 14:12:36,967 - INFO - 📅 Period: 2024-02-06 to 2024-12-30
2026-02-26 14:12:36,967 - INFO - 🎯 Universe: 566 tickers
2026-02-26 14:12:36,967 - INFO - 🎛️  Liquidity: vol≥100k, $vol≥$98M, ADR≥1.67%, RVOL≥0.66x
2026-02-26 14:12:36,967 - INFO - 🎛️  Position Size: RVOL Danger≥3.0x→50%, Warning≥2.0x→75%
2026-02-26 14:12:36,967 - INFO - ============================================================
2026-02-26 14:12:36,967 - INFO - 🌍 MARKET REGIME FILTER ENABLED
2026-02-26 14:12:36,967 - INFO - ============================================================
2026-02-26 14:12:36,967 - INFO - 📊 Loading SPY and VIX data (2024-02-06 to 2024-12-30)...
2026-02-26 14:12:36,970 - INFO -    ✅ SPY loaded from cache: 227 bars
2026-02-26 14:12:36,973 - INFO -    ✅ VIX loaded from cache: 227 bars
2026-02-26 14:12:36,974 - INFO -    ✅ Market data loaded successfully
2026-02-26 14:12:36,979 - INFO -    ✅ Market regime classifier initialized
2026-02-26 14:12:36,979 - INFO -    🚫 Block Stage 3: True
2026-02-26 14:12:36,979 - INFO -    🚫 Block Stage 4: True
2026-02-26 14:12:36,979 - INFO -    📊 Adjust risk by regime: True
2026-02-26 14:12:36,979 - INFO - 📥 Loading data from 2023-02-06 (buffer) to 2024-12-30...
2026-02-26 14:12:36,980 - INFO - 🎯 Universe size: 566 tickers
2026-02-26 14:12:36,980 - INFO - 🛡️  Survivorship bias protection: PIT mask will determine eligibility quarterly
2026-02-26 14:12:36,980 - INFO - ⚡ Fetching data for 566 tickers in parallel...
2026-02-26 14:12:37,282 - WARNING - ❌ SKIP AMTM: None returned
2026-02-26 14:12:37,285 - WARNING - ❌ SKIP ANSS: None returned
2026-02-26 14:12:37,449 - WARNING - ❌ SKIP ATVI: None returned
2026-02-26 14:12:37,731 - INFO -    100/566...
2026-02-26 14:12:37,800 - WARNING - ❌ SKIP CDAY: None returned
2026-02-26 14:12:38,090 - WARNING - ❌ SKIP CTXS: None returned
2026-02-26 14:12:38,365 - WARNING - ❌ SKIP DRE: None returned
2026-02-26 14:12:38,396 - INFO -    200/566...
2026-02-26 14:12:38,445 - WARNING - ❌ SKIP FB: None returned
2026-02-26 14:12:38,449 - WARNING - ❌ SKIP FBHS: None returned
2026-02-26 14:12:38,452 - WARNING - ❌ SKIP FI: None returned
2026-02-26 14:12:38,482 - WARNING - ❌ SKIP FLT: None returned
2026-02-26 14:12:39,100 - INFO -    300/566...
2026-02-26 14:12:39,883 - INFO -    400/566...
2026-02-26 14:12:40,547 - INFO -    500/566...
2026-02-26 14:12:40,962 - WARNING - ⚠️  Skipped 25 tickers (insufficient data)
2026-02-26 14:12:40,962 - INFO -    First 10 failed: ['AMTM (None returned)', 'ANSS (None returned)', 'ATVI (None returned)', 'CDAY (None returned)', 'CTXS (None returned)', 'DRE (None returned)', 'FB (None returned)', 'FBHS (None returned)', 'FI (None returned)', 'FLT (None returned)']
2026-02-26 14:12:40,962 - INFO - ℹ️  541 tickers with partial data (gaps in history)
2026-02-26 14:12:41,189 - INFO - Memory: 4.0 MB for 541 tickers (core DataFrames)
2026-02-26 14:12:41,189 - INFO - 🛡️  Building Point-in-Time tradeable mask (survivorship bias protection)...
2026-02-26 14:12:41,244 - INFO - PointInTimeUniverse: loaded 1230 ticker membership records
2026-02-26 14:12:41,313 - INFO - Tradeable mask: 236,388/258,598 cells (91.4%) across 541 S&P 500 + 0 non-S&P tickers, 478 trading days
2026-02-26 14:12:41,330 - INFO -    🛡️  Masked out 22,210 cells (8.6%) as non-tradeable (pre-IPO, post-delist, not in S&P 500)
2026-02-26 14:12:41,344 - WARNING -    ⚠️ No precomputed metrics found in cache, will calculate on the fly
2026-02-26 14:12:41,948 - INFO -    ⚠️ Precomputed metrics not available, calculating on the fly...
2026-02-26 14:12:41,979 - INFO -    ⚠️ SMA50 missing in cache, calculating on the fly...
2026-02-26 14:12:42,845 - INFO -    Loading SPY and VIX data for Market Regime...
2026-02-26 14:12:42,846 - INFO - 📊 Loading SPY and VIX data (2023-02-06 to 2024-12-30)...
2026-02-26 14:12:42,848 - INFO -    ✅ SPY loaded from cache: 478 bars
2026-02-26 14:12:42,851 - INFO -    ✅ VIX loaded from cache: 478 bars
2026-02-26 14:12:42,851 - INFO -    ✅ Market data loaded successfully
2026-02-26 14:12:42,857 - INFO -    ✅ Market Data Loaded & Aligned
2026-02-26 14:12:42,858 - INFO - ✅ Loaded: 541 tickers
2026-02-26 14:12:42,858 - INFO - 🛡️  Filtered out 25 tickers (insufficient data)
2026-02-26 14:12:42,858 - INFO -    Date range: 2023-02-06 to 2024-12-30 (478 days)
2026-02-26 14:12:42,858 - INFO -    🔧 Truncating data to start_date: 2024-02-06
2026-02-26 14:12:43,072 - INFO - Memory: ~6.6 MB total after float32 conversion
2026-02-26 14:12:43,090 - INFO - 🎯 Starting advanced backtest with partial exits...
2026-02-26 14:12:43,090 - INFO - 📥 Loading data from 2023-02-06 (buffer) to 2024-12-30...
2026-02-26 14:12:43,091 - INFO - 🎯 Universe size: 541 tickers
2026-02-26 14:12:43,091 - INFO - 🛡️  Survivorship bias protection: PIT mask will determine eligibility quarterly
2026-02-26 14:12:43,092 - INFO - ⚡ Fetching data for 541 tickers in parallel...
2026-02-26 14:12:43,869 - INFO -    100/541...
2026-02-26 14:12:44,497 - INFO -    200/541...
2026-02-26 14:12:45,888 - INFO -    300/541...
2026-02-26 14:12:46,667 - INFO -    400/541...
2026-02-26 14:12:47,398 - INFO -    500/541...
2026-02-26 14:12:47,701 - INFO - ℹ️  541 tickers with partial data (gaps in history)
2026-02-26 14:12:47,930 - INFO - Memory: 4.0 MB for 541 tickers (core DataFrames)
2026-02-26 14:12:47,930 - INFO - 🛡️  Building Point-in-Time tradeable mask (survivorship bias protection)...
2026-02-26 14:12:47,985 - INFO - PointInTimeUniverse: loaded 1230 ticker membership records
2026-02-26 14:12:48,053 - INFO - Tradeable mask: 236,388/258,598 cells (91.4%) across 541 S&P 500 + 0 non-S&P tickers, 478 trading days
2026-02-26 14:12:48,071 - INFO -    🛡️  Masked out 22,210 cells (8.6%) as non-tradeable (pre-IPO, post-delist, not in S&P 500)
2026-02-26 14:12:48,086 - WARNING -    ⚠️ No precomputed metrics found in cache, will calculate on the fly
2026-02-26 14:12:48,697 - INFO -    ⚠️ Precomputed metrics not available, calculating on the fly...
2026-02-26 14:12:48,727 - INFO -    ⚠️ SMA50 missing in cache, calculating on the fly...
2026-02-26 14:12:49,595 - INFO -    Loading SPY and VIX data for Market Regime...
2026-02-26 14:12:49,595 - INFO - 📊 Loading SPY and VIX data (2023-02-06 to 2024-12-30)...
2026-02-26 14:12:49,598 - INFO -    ✅ SPY loaded from cache: 478 bars
2026-02-26 14:12:49,600 - INFO -    ✅ VIX loaded from cache: 478 bars
2026-02-26 14:12:49,601 - INFO -    ✅ Market data loaded successfully
2026-02-26 14:12:49,609 - INFO -    ✅ Market Data Loaded & Aligned
2026-02-26 14:12:49,610 - INFO - ✅ Loaded: 541 tickers
2026-02-26 14:12:49,610 - INFO -    Date range: 2023-02-06 to 2024-12-30 (478 days)
2026-02-26 14:12:49,610 - INFO -    🔧 Truncating data to start_date: 2024-02-06
2026-02-26 14:12:49,822 - INFO - Memory: ~6.6 MB total after float32 conversion
2026-02-26 14:12:49,863 - INFO - 🔍 Calculating entry signals...
2026-02-26 14:12:49,864 - INFO -    🎯 Using TREND signal (close > SMA20)
2026-02-26 14:12:49,865 - INFO -    📊 ADVANCED MODE entries (before Adaptive Filter): 63754
2026-02-26 14:12:49,866 - INFO -       Base entry passed: 63754
2026-02-26 14:12:49,886 - INFO - 🛡️  PIT Universe filter: blocked 0 entries on non-member dates (63754 remaining)
2026-02-26 14:12:49,894 - INFO - 🔧 Applying Adaptive Filter Engine (TIER 1-2-3) - OPTIMIZADO...
2026-02-26 14:12:49,895 - INFO - 🔧 AdaptiveFilterEngine initialized
   ⚡ Applying Adaptive Filter: 100%|████| 227/227 [00:01<00:00, 186.76day/s]
2026-02-26 14:12:51,112 - INFO -    📊 Entries antes de Adaptive Filter: 63754
2026-02-26 14:12:51,112 - INFO -    ❌ Entries rechazadas por TIER:
2026-02-26 14:12:51,112 - INFO -       TIER 1 (Market Safety): 5169
2026-02-26 14:12:51,112 - INFO -       TIER 2 (Dynamic Quality): 27223
2026-02-26 14:12:51,112 - INFO -       TIER 3 (Optional): 47
2026-02-26 14:12:51,112 - INFO -    ✅ Entries finales: 31315

======================================================================
📊 ADAPTIVE FILTER ENGINE - RESUMEN (OPTIMIZADO)
======================================================================
  Total de Rechazos: 32439
  • TIER 1 (Market Safety): 5169
  • TIER 2 (Dynamic Quality): 27223
  TIER 3 (Optional): 47
======================================================================
2026-02-26 14:12:51,196 - INFO - 🔍 Clasificando riesgo por RVOL (VolTrig)...
2026-02-26 14:12:51,200 - INFO -    ☔ Danger (RVOL>=3.0x): 217 entries → Size 50%
2026-02-26 14:12:51,200 - INFO -    ⚠️  Warning (RVOL>=2.0x): 818 entries → Size 75%
2026-02-26 14:12:51,200 - INFO -    ✅ Safe (RVOL<2.0x): 30280 entries → Size 100%
2026-02-26 14:12:51,200 - INFO - 🔍 Clasificando riesgo por ADR (volatilidad)...
2026-02-26 14:12:51,270 - INFO -    🔥 High ADR (>6.0%): 85 entries → Size 25%
2026-02-26 14:12:51,271 - INFO -    ⚠️  Med ADR (>5.0%): 102 entries → Size 33%
2026-02-26 14:12:51,302 - INFO - 📊 Single-chunk mode: 227 days (≤ 500)
2026-02-26 14:12:51,302 - INFO - 🔄 Running single-chunk backtest with Numba Core...
2026-02-26 14:12:51,302 - INFO - 🔄 Converting DataFrames to NumPy arrays (float32 optimization)...
2026-02-26 14:12:51,338 - INFO -    ✅ Arrays prepared: 5.7 MB total
2026-02-26 14:12:51,338 - INFO -    📊 Array shapes: close=(227, 541), high=(227, 541)
2026-02-26 14:12:51,338 - INFO - ⚡ Ejecutando simulación ultra-rápida (Numba Core)...
2026-02-26 14:12:51,338 - INFO -    🚀 Using pre-calculated NumPy arrays (memory optimized - float32)
2026-02-26 14:12:51,343 - INFO -    💰 Numba Core usando FIXED DOLLAR RISK: $1000 → risk_pct=0.0100
2026-02-26 14:12:51,343 - INFO - 🔧 NUMBA CORE PARAMETERS:
2026-02-26 14:12:51,343 - INFO -    Initial Capital: $100,000.00
2026-02-26 14:12:51,343 - INFO -    Risk per Trade: $1,000.00
2026-02-26 14:12:51,343 - INFO -    Use Fixed Risk: True
2026-02-26 14:12:51,343 - INFO -    TP1/TP2 Targets: 1.75R / 3.25R
2026-02-26 14:12:51,343 - INFO -    TP Distribution: 45% / 30% / 25%
2026-02-26 14:12:51,343 - INFO -    Max Stop %%: 8.0% (decimal: 0.08)
2026-02-26 14:12:51,343 - INFO -    Trailing Stop: False
2026-02-26 14:12:51,343 - INFO -    ATR Stop Mode: False
2026-02-26 14:12:51,344 - INFO -    Total Entries Signals: 31315
2026-02-26 14:12:51,345 - INFO - 🚀 Numba Simulation Time: 0.0011s
2026-02-26 14:12:51,345 - INFO - 📊 Numba Core Results:
2026-02-26 14:12:51,345 - INFO -    Entry signals found: 31315
2026-02-26 14:12:51,346 - INFO -    Trades executed: 21
2026-02-26 14:12:51,346 - INFO -    Conversion rate: 0.1%
2026-02-26 14:12:51,346 - INFO -    Final equity: $96,120.65
2026-02-26 14:12:51,346 - WARNING -    ⚠️ Low conversion rate (0.1%) - Check parameters
2026-02-26 14:12:51,346 - WARNING -    May indicate: Restrictive filters, large stop distances, or insufficient capital
2026-02-26 14:12:51,346 - INFO -    Exit distribution: STOP=11, TP1=4, TP2=3, RUNNER=3
2026-02-26 14:12:51,830 - INFO - ✅ Backtest complete!
2026-02-26 14:12:51,830 - INFO -    Return: -3.88%
2026-02-26 14:12:51,830 - INFO -    Annualized Return: -4.30%
2026-02-26 14:12:51,830 - INFO -    Sharpe: -0.37
2026-02-26 14:12:51,830 - INFO -    Max DD: -9.74%
2026-02-26 14:12:51,830 - INFO -    MAR Ratio: -0.44
2026-02-26 14:12:51,830 - INFO -    Calmar Ratio: -0.44
2026-02-26 14:12:51,830 - INFO -    Win Rate: 47.6%
2026-02-26 14:12:51,830 - INFO -    Trades: 31315 entries → 21 total exits (including partial)
2026-02-26 14:12:51,834 - INFO - ============================================================
2026-02-26 14:12:51,835 - INFO - 🚀 MODE: PRODUCTION (Fixed Dollar Risk)
2026-02-26 14:12:51,835 - INFO -    • Risk: FIXED DOLLAR ($1000)
2026-02-26 14:12:51,835 - INFO -    • Compounding: DISABLED
2026-02-26 14:12:51,835 - INFO - ============================================================
2026-02-26 14:12:51,836 - INFO - 🚀 Advanced VectorBT Engine initialized
2026-02-26 14:12:51,836 - INFO - 📅 Period: 2024-02-06 to 2024-12-30
2026-02-26 14:12:51,836 - INFO - 🎯 Universe: 566 tickers
2026-02-26 14:12:51,837 - INFO - 🎛️  Liquidity: vol≥100k, $vol≥$98M, ADR≥1.67%, RVOL≥0.66x
2026-02-26 14:12:51,837 - INFO - 🎛️  Position Size: RVOL Danger≥3.0x→50%, Warning≥2.0x→75%
2026-02-26 14:12:51,837 - INFO - ============================================================
2026-02-26 14:12:51,837 - INFO - 🌍 MARKET REGIME FILTER ENABLED
2026-02-26 14:12:51,837 - INFO - ============================================================
2026-02-26 14:12:51,837 - INFO - 📊 Loading SPY and VIX data (2024-02-06 to 2024-12-30)...
2026-02-26 14:12:51,839 - INFO -    ✅ SPY loaded from cache: 227 bars
2026-02-26 14:12:51,842 - INFO -    ✅ VIX loaded from cache: 227 bars
2026-02-26 14:12:51,843 - INFO -    ✅ Market data loaded successfully
2026-02-26 14:12:51,847 - INFO -    ✅ Market regime classifier initialized
2026-02-26 14:12:51,848 - INFO -    🚫 Block Stage 3: True
2026-02-26 14:12:51,848 - INFO -    🚫 Block Stage 4: True
2026-02-26 14:12:51,848 - INFO -    📊 Adjust risk by regime: True
2026-02-26 14:12:51,848 - INFO - 📥 Loading data from 2023-02-06 (buffer) to 2024-12-30...
2026-02-26 14:12:51,848 - INFO - 🎯 Universe size: 566 tickers
2026-02-26 14:12:51,848 - INFO - 🛡️  Survivorship bias protection: PIT mask will determine eligibility quarterly
2026-02-26 14:12:51,848 - INFO - ⚡ Fetching data for 566 tickers in parallel...
2026-02-26 14:12:52,134 - WARNING - ❌ SKIP AMTM: None returned
2026-02-26 14:12:52,135 - WARNING - ❌ SKIP ANSS: None returned
2026-02-26 14:12:52,362 - WARNING - ❌ SKIP ATVI: None returned
2026-02-26 14:12:52,561 - INFO -    100/566...
2026-02-26 14:12:52,627 - WARNING - ❌ SKIP CDAY: None returned
2026-02-26 14:12:52,909 - WARNING - ❌ SKIP CTXS: None returned
2026-02-26 14:12:53,187 - WARNING - ❌ SKIP DRE: None returned
2026-02-26 14:12:53,212 - INFO -    200/566...
2026-02-26 14:12:53,257 - WARNING - ❌ SKIP FB: None returned
2026-02-26 14:12:53,258 - WARNING - ❌ SKIP FBHS: None returned
2026-02-26 14:12:53,263 - WARNING - ❌ SKIP FI: None returned
2026-02-26 14:12:53,294 - WARNING - ❌ SKIP FLT: None returned
2026-02-26 14:12:53,866 - INFO -    300/566...
2026-02-26 14:12:54,613 - INFO -    400/566...
2026-02-26 14:12:55,276 - INFO -    500/566...
2026-02-26 14:12:55,727 - WARNING - ⚠️  Skipped 25 tickers (insufficient data)
2026-02-26 14:12:55,727 - INFO -    First 10 failed: ['AMTM (None returned)', 'ANSS (None returned)', 'ATVI (None returned)', 'CDAY (None returned)', 'CTXS (None returned)', 'DRE (None returned)', 'FB (None returned)', 'FBHS (None returned)', 'FI (None returned)', 'FLT (None returned)']
2026-02-26 14:12:55,727 - INFO - ℹ️  541 tickers with partial data (gaps in history)
2026-02-26 14:12:55,951 - INFO - Memory: 4.0 MB for 541 tickers (core DataFrames)
2026-02-26 14:12:55,951 - INFO - 🛡️  Building Point-in-Time tradeable mask (survivorship bias protection)...
2026-02-26 14:12:56,004 - INFO - PointInTimeUniverse: loaded 1230 ticker membership records
2026-02-26 14:12:56,070 - INFO - Tradeable mask: 236,388/258,598 cells (91.4%) across 541 S&P 500 + 0 non-S&P tickers, 478 trading days
2026-02-26 14:12:56,087 - INFO -    🛡️  Masked out 22,210 cells (8.6%) as non-tradeable (pre-IPO, post-delist, not in S&P 500)
2026-02-26 14:12:56,099 - WARNING -    ⚠️ No precomputed metrics found in cache, will calculate on the fly
2026-02-26 14:12:56,689 - INFO -    ⚠️ Precomputed metrics not available, calculating on the fly...
2026-02-26 14:12:56,721 - INFO -    ⚠️ SMA50 missing in cache, calculating on the fly...
2026-02-26 14:12:57,608 - INFO -    Loading SPY and VIX data for Market Regime...
2026-02-26 14:12:57,608 - INFO - 📊 Loading SPY and VIX data (2023-02-06 to 2024-12-30)...
2026-02-26 14:12:57,610 - INFO -    ✅ SPY loaded from cache: 478 bars
2026-02-26 14:12:57,613 - INFO -    ✅ VIX loaded from cache: 478 bars
2026-02-26 14:12:57,613 - INFO -    ✅ Market data loaded successfully
2026-02-26 14:12:57,620 - INFO -    ✅ Market Data Loaded & Aligned
2026-02-26 14:12:57,620 - INFO - ✅ Loaded: 541 tickers
2026-02-26 14:12:57,620 - INFO - 🛡️  Filtered out 25 tickers (insufficient data)
2026-02-26 14:12:57,620 - INFO -    Date range: 2023-02-06 to 2024-12-30 (478 days)
2026-02-26 14:12:57,621 - INFO -    🔧 Truncating data to start_date: 2024-02-06
2026-02-26 14:12:57,835 - INFO - Memory: ~6.6 MB total after float32 conversion
2026-02-26 14:12:57,854 - INFO - 🎯 Starting advanced backtest with partial exits...
2026-02-26 14:12:57,855 - INFO - 📥 Loading data from 2023-02-06 (buffer) to 2024-12-30...
2026-02-26 14:12:57,855 - INFO - 🎯 Universe size: 541 tickers
2026-02-26 14:12:57,856 - INFO - 🛡️  Survivorship bias protection: PIT mask will determine eligibility quarterly
2026-02-26 14:12:57,856 - INFO - ⚡ Fetching data for 541 tickers in parallel...
2026-02-26 14:12:58,623 - INFO -    100/541...
2026-02-26 14:12:59,289 - INFO -    200/541...
2026-02-26 14:13:00,006 - INFO -    300/541...
2026-02-26 14:13:00,801 - INFO -    400/541...
2026-02-26 14:13:01,549 - INFO -    500/541...
2026-02-26 14:13:01,848 - INFO - ℹ️  541 tickers with partial data (gaps in history)
2026-02-26 14:13:02,079 - INFO - Memory: 4.0 MB for 541 tickers (core DataFrames)
2026-02-26 14:13:02,079 - INFO - 🛡️  Building Point-in-Time tradeable mask (survivorship bias protection)...
2026-02-26 14:13:02,136 - INFO - PointInTimeUniverse: loaded 1230 ticker membership records
2026-02-26 14:13:02,204 - INFO - Tradeable mask: 236,388/258,598 cells (91.4%) across 541 S&P 500 + 0 non-S&P tickers, 478 trading days
2026-02-26 14:13:02,222 - INFO -    🛡️  Masked out 22,210 cells (8.6%) as non-tradeable (pre-IPO, post-delist, not in S&P 500)
2026-02-26 14:13:02,237 - WARNING -    ⚠️ No precomputed metrics found in cache, will calculate on the fly
2026-02-26 14:13:02,849 - INFO -    ⚠️ Precomputed metrics not available, calculating on the fly...
2026-02-26 14:13:02,880 - INFO -    ⚠️ SMA50 missing in cache, calculating on the fly...
2026-02-26 14:13:03,771 - INFO -    Loading SPY and VIX data for Market Regime...
2026-02-26 14:13:03,772 - INFO - 📊 Loading SPY and VIX data (2023-02-06 to 2024-12-30)...
2026-02-26 14:13:03,774 - INFO -    ✅ SPY loaded from cache: 478 bars
2026-02-26 14:13:03,777 - INFO -    ✅ VIX loaded from cache: 478 bars
2026-02-26 14:13:03,777 - INFO -    ✅ Market data loaded successfully
2026-02-26 14:13:03,783 - INFO -    ✅ Market Data Loaded & Aligned
2026-02-26 14:13:03,784 - INFO - ✅ Loaded: 541 tickers
2026-02-26 14:13:03,784 - INFO -    Date range: 2023-02-06 to 2024-12-30 (478 days)
2026-02-26 14:13:03,784 - INFO -    🔧 Truncating data to start_date: 2024-02-06
2026-02-26 14:13:03,994 - INFO - Memory: ~6.6 MB total after float32 conversion
2026-02-26 14:13:04,035 - INFO - 🔍 Calculating entry signals...
2026-02-26 14:13:04,037 - INFO -    🎯 Using TREND signal (close > SMA20)
2026-02-26 14:13:04,038 - INFO -    📊 ADVANCED MODE entries (before Adaptive Filter): 63754
2026-02-26 14:13:04,038 - INFO -       Base entry passed: 63754
2026-02-26 14:13:04,058 - INFO - 🛡️  PIT Universe filter: blocked 0 entries on non-member dates (63754 remaining)
2026-02-26 14:13:04,068 - INFO - 🔧 Applying Adaptive Filter Engine (TIER 1-2-3) - OPTIMIZADO...
2026-02-26 14:13:04,068 - INFO - 🔧 AdaptiveFilterEngine initialized
   ⚡ Applying Adaptive Filter: 100%|████| 227/227 [00:01<00:00, 183.37day/s]
2026-02-26 14:13:05,308 - INFO -    📊 Entries antes de Adaptive Filter: 63754
2026-02-26 14:13:05,308 - INFO -    ❌ Entries rechazadas por TIER:
2026-02-26 14:13:05,309 - INFO -       TIER 1 (Market Safety): 5169
2026-02-26 14:13:05,309 - INFO -       TIER 2 (Dynamic Quality): 27223
2026-02-26 14:13:05,309 - INFO -       TIER 3 (Optional): 47
2026-02-26 14:13:05,309 - INFO -    ✅ Entries finales: 31315

======================================================================
📊 ADAPTIVE FILTER ENGINE - RESUMEN (OPTIMIZADO)
======================================================================
  Total de Rechazos: 32439
  • TIER 1 (Market Safety): 5169
  • TIER 2 (Dynamic Quality): 27223
  TIER 3 (Optional): 47
======================================================================
2026-02-26 14:13:05,392 - INFO - 🔍 Clasificando riesgo por RVOL (VolTrig)...
2026-02-26 14:13:05,396 - INFO -    ☔ Danger (RVOL>=3.0x): 217 entries → Size 50%
2026-02-26 14:13:05,396 - INFO -    ⚠️  Warning (RVOL>=2.0x): 818 entries → Size 75%
2026-02-26 14:13:05,396 - INFO -    ✅ Safe (RVOL<2.0x): 30280 entries → Size 100%
2026-02-26 14:13:05,396 - INFO - 🔍 Clasificando riesgo por ADR (volatilidad)...
2026-02-26 14:13:05,471 - INFO -    🔥 High ADR (>6.0%): 85 entries → Size 25%
2026-02-26 14:13:05,471 - INFO -    ⚠️  Med ADR (>5.0%): 102 entries → Size 33%
2026-02-26 14:13:05,503 - INFO - 📊 Single-chunk mode: 227 days (≤ 500)
2026-02-26 14:13:05,504 - INFO - 🔄 Running single-chunk backtest with Numba Core...
2026-02-26 14:13:05,504 - INFO - 🔄 Converting DataFrames to NumPy arrays (float32 optimization)...
2026-02-26 14:13:05,539 - INFO -    ✅ Arrays prepared: 5.7 MB total
2026-02-26 14:13:05,540 - INFO -    📊 Array shapes: close=(227, 541), high=(227, 541)
2026-02-26 14:13:05,540 - INFO - ⚡ Ejecutando simulación ultra-rápida (Numba Core)...
2026-02-26 14:13:05,540 - INFO -    🚀 Using pre-calculated NumPy arrays (memory optimized - float32)
2026-02-26 14:13:05,544 - INFO -    💰 Numba Core usando FIXED DOLLAR RISK: $1000 → risk_pct=0.0100
2026-02-26 14:13:05,545 - INFO - 🔧 NUMBA CORE PARAMETERS:
2026-02-26 14:13:05,545 - INFO -    Initial Capital: $100,000.00
2026-02-26 14:13:05,545 - INFO -    Risk per Trade: $1,000.00
2026-02-26 14:13:05,545 - INFO -    Use Fixed Risk: True
2026-02-26 14:13:05,545 - INFO -    TP1/TP2 Targets: 1.75R / 3.25R
2026-02-26 14:13:05,545 - INFO -    TP Distribution: 45% / 30% / 25%
2026-02-26 14:13:05,545 - INFO -    Max Stop %%: 8.0% (decimal: 0.08)
2026-02-26 14:13:05,545 - INFO -    Trailing Stop: False
2026-02-26 14:13:05,545 - INFO -    ATR Stop Mode: False
2026-02-26 14:13:05,545 - INFO -    Total Entries Signals: 31315
2026-02-26 14:13:05,547 - INFO - 🚀 Numba Simulation Time: 0.0013s
2026-02-26 14:13:05,547 - INFO - 📊 Numba Core Results:
2026-02-26 14:13:05,547 - INFO -    Entry signals found: 31315
2026-02-26 14:13:05,547 - INFO -    Trades executed: 20
2026-02-26 14:13:05,547 - INFO -    Conversion rate: 0.1%
2026-02-26 14:13:05,548 - INFO -    Final equity: $98,344.80
2026-02-26 14:13:05,548 - WARNING -    ⚠️ Low conversion rate (0.1%) - Check parameters
2026-02-26 14:13:05,548 - WARNING -    May indicate: Restrictive filters, large stop distances, or insufficient capital
2026-02-26 14:13:05,548 - INFO -    Exit distribution: STOP=10, TP1=4, TP2=3, RUNNER=3
2026-02-26 14:13:06,055 - INFO - ✅ Backtest complete!
2026-02-26 14:13:06,055 - INFO -    Return: -1.66%
2026-02-26 14:13:06,065 - INFO -    Annualized Return: -1.84%
2026-02-26 14:13:06,066 - INFO -    Sharpe: -0.13
2026-02-26 14:13:06,066 - INFO -    Max DD: -7.89%
2026-02-26 14:13:06,066 - INFO -    MAR Ratio: -0.23
2026-02-26 14:13:06,066 - INFO -    Calmar Ratio: -0.23
2026-02-26 14:13:06,066 - INFO -    Win Rate: 50.0%
2026-02-26 14:13:06,066 - INFO -    Trades: 31315 entries → 20 total exits (including partial)
2026-02-26 14:13:06,071 - INFO - ============================================================
2026-02-26 14:13:06,071 - INFO - 🚀 MODE: PRODUCTION (Fixed Dollar Risk)
2026-02-26 14:13:06,071 - INFO -    • Risk: FIXED DOLLAR ($1000)
2026-02-26 14:13:06,071 - INFO -    • Compounding: DISABLED
2026-02-26 14:13:06,071 - INFO - ============================================================
2026-02-26 14:13:06,073 - INFO - 🚀 Advanced VectorBT Engine initialized
2026-02-26 14:13:06,073 - INFO - 📅 Period: 2024-02-06 to 2024-12-30
2026-02-26 14:13:06,073 - INFO - 🎯 Universe: 566 tickers
2026-02-26 14:13:06,073 - INFO - 🎛️  Liquidity: vol≥100k, $vol≥$98M, ADR≥1.67%, RVOL≥0.66x
2026-02-26 14:13:06,073 - INFO - 🎛️  Position Size: RVOL Danger≥3.0x→50%, Warning≥2.0x→75%
2026-02-26 14:13:06,073 - INFO - ============================================================
2026-02-26 14:13:06,073 - INFO - 🌍 MARKET REGIME FILTER ENABLED
2026-02-26 14:13:06,073 - INFO - ============================================================
2026-02-26 14:13:06,073 - INFO - 📊 Loading SPY and VIX data (2024-02-06 to 2024-12-30)...
2026-02-26 14:13:06,075 - INFO -    ✅ SPY loaded from cache: 227 bars
2026-02-26 14:13:06,078 - INFO -    ✅ VIX loaded from cache: 227 bars
2026-02-26 14:13:06,078 - INFO -    ✅ Market data loaded successfully
2026-02-26 14:13:06,083 - INFO -    ✅ Market regime classifier initialized
2026-02-26 14:13:06,083 - INFO -    🚫 Block Stage 3: True
2026-02-26 14:13:06,083 - INFO -    🚫 Block Stage 4: True
2026-02-26 14:13:06,083 - INFO -    📊 Adjust risk by regime: True
2026-02-26 14:13:06,084 - INFO - 📥 Loading data from 2023-02-06 (buffer) to 2024-12-30...
2026-02-26 14:13:06,084 - INFO - 🎯 Universe size: 566 tickers
2026-02-26 14:13:06,084 - INFO - 🛡️  Survivorship bias protection: PIT mask will determine eligibility quarterly
2026-02-26 14:13:06,084 - INFO - ⚡ Fetching data for 566 tickers in parallel...
2026-02-26 14:13:06,369 - WARNING - ❌ SKIP AMTM: None returned
2026-02-26 14:13:06,373 - WARNING - ❌ SKIP ANSS: None returned
2026-02-26 14:13:06,610 - WARNING - ❌ SKIP ATVI: None returned
2026-02-26 14:13:06,790 - INFO -    100/566...
2026-02-26 14:13:06,852 - WARNING - ❌ SKIP CDAY: None returned
2026-02-26 14:13:07,151 - WARNING - ❌ SKIP CTXS: None returned
2026-02-26 14:13:07,437 - INFO -    200/566...
2026-02-26 14:13:07,445 - WARNING - ❌ SKIP DRE: None returned
2026-02-26 14:13:07,479 - WARNING - ❌ SKIP FB: None returned
2026-02-26 14:13:07,483 - WARNING - ❌ SKIP FBHS: None returned
2026-02-26 14:13:07,486 - WARNING - ❌ SKIP FI: None returned
2026-02-26 14:13:07,504 - WARNING - ❌ SKIP FLT: None returned
2026-02-26 14:13:08,099 - INFO -    300/566...
2026-02-26 14:13:08,841 - INFO -    400/566...
2026-02-26 14:13:09,533 - INFO -    500/566...
2026-02-26 14:13:09,984 - WARNING - ⚠️  Skipped 25 tickers (insufficient data)
2026-02-26 14:13:09,984 - INFO -    First 10 failed: ['AMTM (None returned)', 'ANSS (None returned)', 'ATVI (None returned)', 'CDAY (None returned)', 'CTXS (None returned)', 'DRE (None returned)', 'FB (None returned)', 'FBHS (None returned)', 'FI (None returned)', 'FLT (None returned)']
2026-02-26 14:13:09,985 - INFO - ℹ️  541 tickers with partial data (gaps in history)
2026-02-26 14:13:10,207 - INFO - Memory: 4.0 MB for 541 tickers (core DataFrames)
2026-02-26 14:13:10,207 - INFO - 🛡️  Building Point-in-Time tradeable mask (survivorship bias protection)...
2026-02-26 14:13:10,261 - INFO - PointInTimeUniverse: loaded 1230 ticker membership records
2026-02-26 14:13:10,327 - INFO - Tradeable mask: 236,388/258,598 cells (91.4%) across 541 S&P 500 + 0 non-S&P tickers, 478 trading days
2026-02-26 14:13:10,344 - INFO -    🛡️  Masked out 22,210 cells (8.6%) as non-tradeable (pre-IPO, post-delist, not in S&P 500)
2026-02-26 14:13:10,357 - WARNING -    ⚠️ No precomputed metrics found in cache, will calculate on the fly
2026-02-26 14:13:10,949 - INFO -    ⚠️ Precomputed metrics not available, calculating on the fly...
2026-02-26 14:13:10,980 - INFO -    ⚠️ SMA50 missing in cache, calculating on the fly...
2026-02-26 14:13:11,883 - INFO -    Loading SPY and VIX data for Market Regime...
2026-02-26 14:13:11,883 - INFO - 📊 Loading SPY and VIX data (2023-02-06 to 2024-12-30)...
2026-02-26 14:13:11,897 - INFO -    ✅ SPY loaded from cache: 478 bars
2026-02-26 14:13:11,899 - INFO -    ✅ VIX loaded from cache: 478 bars
2026-02-26 14:13:11,900 - INFO -    ✅ Market data loaded successfully
2026-02-26 14:13:11,907 - INFO -    ✅ Market Data Loaded & Aligned
2026-02-26 14:13:11,907 - INFO - ✅ Loaded: 541 tickers
2026-02-26 14:13:11,908 - INFO - 🛡️  Filtered out 25 tickers (insufficient data)
2026-02-26 14:13:11,908 - INFO -    Date range: 2023-02-06 to 2024-12-30 (478 days)
2026-02-26 14:13:11,908 - INFO -    🔧 Truncating data to start_date: 2024-02-06
2026-02-26 14:13:12,134 - INFO - Memory: ~6.6 MB total after float32 conversion
2026-02-26 14:13:12,152 - INFO - 🎯 Starting advanced backtest with partial exits...
2026-02-26 14:13:12,153 - INFO - 📥 Loading data from 2023-02-06 (buffer) to 2024-12-30...
2026-02-26 14:13:12,154 - INFO - 🎯 Universe size: 541 tickers
2026-02-26 14:13:12,154 - INFO - 🛡️  Survivorship bias protection: PIT mask will determine eligibility quarterly
2026-02-26 14:13:12,154 - INFO - ⚡ Fetching data for 541 tickers in parallel...
2026-02-26 14:13:12,916 - INFO -    100/541...
2026-02-26 14:13:13,582 - INFO -    200/541...
2026-02-26 14:13:14,315 - INFO -    300/541...
2026-02-26 14:13:15,100 - INFO -    400/541...
2026-02-26 14:13:15,834 - INFO -    500/541...
2026-02-26 14:13:16,129 - INFO - ℹ️  541 tickers with partial data (gaps in history)
2026-02-26 14:13:16,363 - INFO - Memory: 4.0 MB for 541 tickers (core DataFrames)
2026-02-26 14:13:16,363 - INFO - 🛡️  Building Point-in-Time tradeable mask (survivorship bias protection)...
2026-02-26 14:13:16,417 - INFO - PointInTimeUniverse: loaded 1230 ticker membership records
2026-02-26 14:13:16,486 - INFO - Tradeable mask: 236,388/258,598 cells (91.4%) across 541 S&P 500 + 0 non-S&P tickers, 478 trading days
2026-02-26 14:13:16,505 - INFO -    🛡️  Masked out 22,210 cells (8.6%) as non-tradeable (pre-IPO, post-delist, not in S&P 500)
2026-02-26 14:13:16,520 - WARNING -    ⚠️ No precomputed metrics found in cache, will calculate on the fly
2026-02-26 14:13:17,124 - INFO -    ⚠️ Precomputed metrics not available, calculating on the fly...
2026-02-26 14:13:17,155 - INFO -    ⚠️ SMA50 missing in cache, calculating on the fly...
2026-02-26 14:13:18,776 - INFO -    Loading SPY and VIX data for Market Regime...
2026-02-26 14:13:18,777 - INFO - 📊 Loading SPY and VIX data (2023-02-06 to 2024-12-30)...
2026-02-26 14:13:18,779 - INFO -    ✅ SPY loaded from cache: 478 bars
2026-02-26 14:13:18,782 - INFO -    ✅ VIX loaded from cache: 478 bars
2026-02-26 14:13:18,782 - INFO -    ✅ Market data loaded successfully
2026-02-26 14:13:18,789 - INFO -    ✅ Market Data Loaded & Aligned
2026-02-26 14:13:18,790 - INFO - ✅ Loaded: 541 tickers
2026-02-26 14:13:18,790 - INFO -    Date range: 2023-02-06 to 2024-12-30 (478 days)
2026-02-26 14:13:18,790 - INFO -    🔧 Truncating data to start_date: 2024-02-06
2026-02-26 14:13:18,995 - INFO - Memory: ~6.6 MB total after float32 conversion
2026-02-26 14:13:19,036 - INFO - 🔍 Calculating entry signals...
2026-02-26 14:13:19,038 - INFO -    🎯 Using TREND signal (close > SMA20)
2026-02-26 14:13:19,039 - INFO -    📊 ADVANCED MODE entries (before Adaptive Filter): 63754
2026-02-26 14:13:19,039 - INFO -       Base entry passed: 63754
2026-02-26 14:13:19,059 - INFO - 🛡️  PIT Universe filter: blocked 0 entries on non-member dates (63754 remaining)
2026-02-26 14:13:19,068 - INFO - 🔧 Applying Adaptive Filter Engine (TIER 1-2-3) - OPTIMIZADO...
2026-02-26 14:13:19,069 - INFO - 🔧 AdaptiveFilterEngine initialized
   ⚡ Applying Adaptive Filter: 100%|████| 227/227 [00:01<00:00, 187.65day/s]
2026-02-26 14:13:20,280 - INFO -    📊 Entries antes de Adaptive Filter: 63754
2026-02-26 14:13:20,281 - INFO -    ❌ Entries rechazadas por TIER:
2026-02-26 14:13:20,281 - INFO -       TIER 1 (Market Safety): 5169
2026-02-26 14:13:20,281 - INFO -       TIER 2 (Dynamic Quality): 27223
2026-02-26 14:13:20,281 - INFO -       TIER 3 (Optional): 47
2026-02-26 14:13:20,281 - INFO -    ✅ Entries finales: 31315

======================================================================
📊 ADAPTIVE FILTER ENGINE - RESUMEN (OPTIMIZADO)
======================================================================
  Total de Rechazos: 32439
  • TIER 1 (Market Safety): 5169
  • TIER 2 (Dynamic Quality): 27223
  TIER 3 (Optional): 47
======================================================================
2026-02-26 14:13:20,365 - INFO - 🔍 Clasificando riesgo por RVOL (VolTrig)...
2026-02-26 14:13:20,369 - INFO -    ☔ Danger (RVOL>=3.0x): 217 entries → Size 50%
2026-02-26 14:13:20,370 - INFO -    ⚠️  Warning (RVOL>=2.0x): 818 entries → Size 75%
2026-02-26 14:13:20,370 - INFO -    ✅ Safe (RVOL<2.0x): 30280 entries → Size 100%
2026-02-26 14:13:20,370 - INFO - 🔍 Clasificando riesgo por ADR (volatilidad)...
2026-02-26 14:13:20,441 - INFO -    🔥 High ADR (>6.0%): 85 entries → Size 25%
2026-02-26 14:13:20,442 - INFO -    ⚠️  Med ADR (>5.0%): 102 entries → Size 33%
2026-02-26 14:13:20,472 - INFO - 📊 Single-chunk mode: 227 days (≤ 500)
2026-02-26 14:13:20,473 - INFO - 🔄 Running single-chunk backtest with Numba Core...
2026-02-26 14:13:20,473 - INFO - 🔄 Converting DataFrames to NumPy arrays (float32 optimization)...
2026-02-26 14:13:20,507 - INFO -    ✅ Arrays prepared: 5.7 MB total
2026-02-26 14:13:20,507 - INFO -    📊 Array shapes: close=(227, 541), high=(227, 541)
2026-02-26 14:13:20,507 - INFO - ⚡ Ejecutando simulación ultra-rápida (Numba Core)...
2026-02-26 14:13:20,507 - INFO -    🚀 Using pre-calculated NumPy arrays (memory optimized - float32)
2026-02-26 14:13:20,512 - INFO -    💰 Numba Core usando FIXED DOLLAR RISK: $1000 → risk_pct=0.0100
2026-02-26 14:13:20,512 - INFO - 🔧 NUMBA CORE PARAMETERS:
2026-02-26 14:13:20,512 - INFO -    Initial Capital: $100,000.00
2026-02-26 14:13:20,512 - INFO -    Risk per Trade: $1,000.00
2026-02-26 14:13:20,512 - INFO -    Use Fixed Risk: True
2026-02-26 14:13:20,512 - INFO -    TP1/TP2 Targets: 1.75R / 3.25R
2026-02-26 14:13:20,512 - INFO -    TP Distribution: 45% / 30% / 25%
2026-02-26 14:13:20,512 - INFO -    Max Stop %%: 8.0% (decimal: 0.08)
2026-02-26 14:13:20,513 - INFO -    Trailing Stop: False
2026-02-26 14:13:20,513 - INFO -    ATR Stop Mode: False
2026-02-26 14:13:20,513 - INFO -    Total Entries Signals: 31315
2026-02-26 14:13:20,514 - INFO - 🚀 Numba Simulation Time: 0.0010s
2026-02-26 14:13:20,514 - INFO - 📊 Numba Core Results:
2026-02-26 14:13:20,514 - INFO -    Entry signals found: 31315
2026-02-26 14:13:20,514 - INFO -    Trades executed: 20
2026-02-26 14:13:20,515 - INFO -    Conversion rate: 0.1%
2026-02-26 14:13:20,515 - INFO -    Final equity: $98,344.80
2026-02-26 14:13:20,515 - WARNING -    ⚠️ Low conversion rate (0.1%) - Check parameters
2026-02-26 14:13:20,515 - WARNING -    May indicate: Restrictive filters, large stop distances, or insufficient capital
2026-02-26 14:13:20,515 - INFO -    Exit distribution: STOP=10, TP1=4, TP2=3, RUNNER=3
2026-02-26 14:13:21,058 - INFO - ✅ Backtest complete!
2026-02-26 14:13:21,058 - INFO -    Return: -1.66%
2026-02-26 14:13:21,058 - INFO -    Annualized Return: -1.84%
2026-02-26 14:13:21,058 - INFO -    Sharpe: -0.13
2026-02-26 14:13:21,058 - INFO -    Max DD: -7.89%
2026-02-26 14:13:21,058 - INFO -    MAR Ratio: -0.23
2026-02-26 14:13:21,058 - INFO -    Calmar Ratio: -0.23
2026-02-26 14:13:21,058 - INFO -    Win Rate: 50.0%
2026-02-26 14:13:21,058 - INFO -    Trades: 31315 entries → 20 total exits (including partial)
2026-02-26 14:13:21,108 - INFO -    2x_costs: -2.22% impact
2026-02-26 14:13:21,109 - INFO -    3x_costs: +0.00% impact
2026-02-26 14:13:21,109 - INFO -    wider_spreads: +0.00% impact
2026-02-26 14:13:21,109 - INFO -    ✅ Productionization phase passed
2026-02-26 14:13:21,109 - INFO - 
======================================================================
2026-02-26 14:13:21,109 - INFO - ❌ STRATEGY REJECTED
2026-02-26 14:13:21,109 - INFO -    • OOS p5 too low: -18.13% < -5.00%
2026-02-26 14:13:21,109 - INFO -    • OOS p10 too low: -15.29% < -2.00%
2026-02-26 14:13:21,109 - INFO -    • Drawdown duration too long: 105 days > 90 days
2026-02-26 14:13:21,109 - INFO -    • Sharpe too low: -0.13 < 0.50
2026-02-26 14:13:21,109 - INFO -    • Profit factor too low: 0.73 < 1.20
2026-02-26 14:13:21,109 - INFO - ======================================================================
2026-02-26 14:13:21,171 - INFO - 
  ✅ Best Walk-Forward Window Selected:
2026-02-26 14:13:21,172 - INFO -      Sharpe: 2.18
2026-02-26 14:13:21,173 - INFO -      Max DD: 7.33%
2026-02-26 14:13:21,173 - INFO -      Approved: True
2026-02-26 14:13:21,173 - INFO - 
======================================================================
2026-02-26 14:13:21,173 - INFO - PIPELINE COMPLETE - FINAL REPORT
2026-02-26 14:13:21,173 - INFO - ======================================================================
2026-02-26 14:13:21,186 - INFO - 
  TIER 3 (Risk - Fixed):
2026-02-26 14:13:21,187 - INFO -     rvol_danger: 3.0x
2026-02-26 14:13:21,187 - INFO -     rvol_warning: 2.0x
2026-02-26 14:13:21,187 - INFO -     max_exposure: 65%
2026-02-26 14:13:21,187 - INFO - 
  TIER 2 (Quality - Derived from 120 trades):
2026-02-26 14:13:21,187 - INFO -     min_rvol: 0.61
2026-02-26 14:13:21,187 - INFO -     min_adr: 1.58
2026-02-26 14:13:21,187 - INFO -     max_dist_sma20: 6.31
2026-02-26 14:13:21,187 - INFO -     min_dollar_volume: 92371057.9670906
2026-02-26 14:13:21,187 - INFO -     min_consolidation_days: 5
2026-02-26 14:13:21,187 - INFO -     min_volume: 100000
2026-02-26 14:13:21,187 - INFO -     _raw_derived: {'rvol_raw': 0.61, 'adr_raw': 1.58, 'dist_sma20_raw': 6.31, 'dollar_volume_raw': 92371057.9670906}
2026-02-26 14:13:21,187 - INFO -     _dollar_volume_stats: {'p10': 108588459.14154053, 'p25': 170543067.77996063, 'median': 291883616.00723267, 'p75': 470721366.06521606, 'p90': 1121480961.2083435, 'max': 17804752640.30713, 'derived_raw': 92371057.9670906}
2026-02-26 14:13:21,187 - INFO -     _rvol_stats: {'p10': 0.68, 'median': 0.95, 'p90': 1.46, 'max': 2.14}
2026-02-26 14:13:21,187 - INFO -     _adr_stats: {'p10': 1.61, 'median': 2.24, 'p90': 3.81, 'max': 5.13}
2026-02-26 14:13:21,187 - INFO -     _dist_sma20_stats: {'p10': 0.54, 'median': 1.56, 'p90': 4.62, 'max': 8.94}
2026-02-26 14:13:21,187 - INFO - 
  TIER 1 (Strategy - Optimized, score=-10.85):
2026-02-26 14:13:21,187 - INFO -     tp1_r: 1.75
2026-02-26 14:13:21,187 - INFO -     tp2_r: 3.25
2026-02-26 14:13:21,187 - INFO -     tp1_pct: 0.45
2026-02-26 14:13:21,187 - INFO -     tp2_pct: 0.3
2026-02-26 14:13:21,188 - INFO -     runner_pct: 0.25
2026-02-26 14:13:21,188 - INFO - 
  VALIDATION: APPROVED FOR PRODUCTION
2026-02-26 14:13:21,197 - INFO - ======================================================================
2026-02-26 14:13:21,197 - INFO - PHASE 5: AUTO-EXPORT TO STREAMLIT
2026-02-26 14:13:21,197 - INFO - ======================================================================
2026-02-26 14:13:21,230 - INFO -   ✅ Backed up existing config to: config/production_config.json.bak
2026-02-26 14:13:21,233 - INFO -   ✅ Exported to: config/production_config.json<2-t_��>hlua require"cmp.utils.feedkeys".run(3)
ý
2026-02-26 14:13:21,234 - INFO -   📊 Strategy ready for Streamlit app testing
2026-02-26 14:13:21,234 - INFO - ======================================================================
2026-02-26 14:13:21,234 - INFO - 
  🚀 Strategy exported to Streamlit app!
2026-02-26 14:13:21,234 - INFO -      Run: streamlit run app.py
2026-02-26 14:13:21,234 - INFO - 
  Output: outputs/3tier_optimization/FINAL_CONFIG.json
2026-02-26 14:13:21,234 - INFO - ======================================================================
