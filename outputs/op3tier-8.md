2026-03-04 19:14:34,697 - INFO - ======================================================================
2026-03-04 19:14:34,772 - INFO - 3-TIER OPTIMIZATION PIPELINE
2026-03-04 19:14:34,772 - INFO - ======================================================================
2026-03-04 19:14:34,772 - INFO -   Date: 2026-03-04 19:14
2026-03-04 19:14:34,772 - INFO -   Period: 2022-01-01 to 2024-12-31
2026-03-04 19:14:34,772 - INFO -   Tickers: 80
2026-03-04 19:14:34,773 - INFO -   Trials: 100
2026-03-04 19:14:34,773 - INFO -   Capital: $100,000
2026-03-04 19:14:34,773 - INFO - 
  TIER 3 (Institutional - FIXED):
2026-03-04 19:14:34,773 - INFO -     rvol_danger/warning: 3.0/2.0
2026-03-04 19:14:34,773 - INFO -     max_exposure: 65%
2026-03-04 19:14:34,774 - INFO -     max_stop_hard: 0.08
2026-03-04 19:14:36,260 - INFO - PointInTimeUniverse: loaded 1230 ticker membership records
2026-03-04 19:14:36,266 - INFO - 
  Universe (PIT): 566 tickers (survivorship-bias-free superset)
2026-03-04 19:14:36,266 - INFO -     First 10: ['A', 'AAL', 'AAP', 'AAPL', 'ABBV', 'ABC', 'ABMD', 'ABNB', 'ABT', 'ACGL']
2026-03-04 19:14:36,266 - INFO - 
  Universe: 566 tickers (A, AAL, AAP, AAPL, ABBV...)
2026-03-04 19:14:36,266 - INFO - ======================================================================
2026-03-04 19:14:36,266 - INFO - PHASE 1: BASELINE RUN (Loose Filters)
2026-03-04 19:14:36,266 - INFO - ======================================================================
2026-03-04 19:14:36,266 - INFO -   Initial Capital: $100,000
2026-03-04 19:14:36,266 - INFO -   Risk Fraction (Tier 3): 1.00%
2026-03-04 19:14:36,266 - INFO -   Risk per Trade: $1,000
2026-03-04 19:14:36,266 - INFO -   Universe: 566 tickers
2026-03-04 19:14:36,266 - INFO -   Period: 2022-01-01 to 2024-12-31
2026-03-04 19:14:36,267 - INFO -   Filters: LOOSE (min_rvol=0.5, min_adr=1.0, max_dist_sma20=20.0)
2026-03-04 19:14:36,269 - INFO - ============================================================
2026-03-04 19:14:36,269 - INFO - 🚀 MODE: PRODUCTION (Fixed Dollar Risk)
2026-03-04 19:14:36,269 - INFO -    • Risk: FIXED DOLLAR ($1000)
2026-03-04 19:14:36,269 - INFO -    • Compounding: DISABLED
2026-03-04 19:14:36,269 - INFO - ============================================================
2026-03-04 19:14:36,353 - INFO - 🚀 Advanced VectorBT Engine initialized
2026-03-04 19:14:36,353 - INFO - 📅 Period: 2022-01-01 to 2024-12-31
2026-03-04 19:14:36,353 - INFO - 🎯 Universe: 566 tickers
2026-03-04 19:14:36,353 - INFO - 🎛️  Liquidity: vol≥100k, $vol≥$1M, ADR≥1.0%, RVOL≥0.5x
2026-03-04 19:14:36,353 - INFO - 🎛️  Position Size: RVOL Danger≥3.0x→50%, Warning≥2.0x→75%
2026-03-04 19:14:36,380 - INFO - 📥 Loading data from 2021-01-01 (buffer) to 2024-12-31...
2026-03-04 19:14:36,380 - INFO - 🎯 Universe size: 566 tickers
2026-03-04 19:14:36,380 - INFO - 🛡️  Survivorship bias protection: PIT mask will determine eligibility quarterly
2026-03-04 19:14:36,380 - INFO - ⚡ Fetching data for 566 tickers in parallel...
2026-03-04 19:14:38,531 - WARNING - ❌ SKIP AMTM: None returned
2026-03-04 19:14:38,574 - WARNING - ❌ SKIP ANSS: None returned
2026-03-04 19:14:39,033 - WARNING - ❌ SKIP ATVI: None returned
2026-03-04 19:14:40,552 - WARNING - ❌ SKIP CDAY: None returned
2026-03-04 19:14:40,768 - INFO -    100/566...
2026-03-04 19:14:42,178 - WARNING - ❌ SKIP CTXS: None returned
2026-03-04 19:14:43,037 - WARNING - ❌ SKIP DRE: None returned
2026-03-04 19:14:44,100 - INFO -    200/566...
2026-03-04 19:14:44,315 - WARNING - ❌ SKIP FB: None returned
2026-03-04 19:14:44,316 - WARNING - ❌ SKIP FBHS: None returned
2026-03-04 19:14:44,504 - WARNING - ❌ SKIP FI: None returned
2026-03-04 19:14:44,764 - WARNING - ❌ SKIP FISV: len=222 < min=408
2026-03-04 19:14:47,649 - INFO -    300/566...
2026-03-04 19:14:50,663 - INFO -    400/566...
2026-03-04 19:14:54,628 - INFO -    500/566...
2026-03-04 19:14:57,736 - WARNING - ⚠️  Skipped 26 tickers (insufficient data)
2026-03-04 19:14:57,737 - INFO -    First 10 failed: ['AMTM (None returned)', 'ANSS (None returned)', 'ATVI (None returned)', 'CDAY (None returned)', 'CTXS (None returned)', 'DRE (None returned)', 'FB (None returned)', 'FBHS (None returned)', 'FI (None returned)', 'FISV (len=222 < min=408)']
2026-03-04 19:14:57,737 - INFO - ℹ️  540 tickers with partial data (gaps in history)
2026-03-04 19:15:00,264 - INFO - Memory: 8.3 MB for 540 tickers (core DataFrames)
2026-03-04 19:15:00,265 - INFO - 🛡️  Building Point-in-Time tradeable mask (survivorship bias protection)...
2026-03-04 19:15:01,075 - INFO - PointInTimeUniverse: loaded 1230 ticker membership records
2026-03-04 19:15:01,384 - INFO - Tradeable mask: 489,512/542,700 cells (90.2%) across 540 S&P 500 + 0 non-S&P tickers, 1005 trading days
2026-03-04 19:15:01,537 - INFO -    🛡️  Masked out 53,188 cells (9.8%) as non-tradeable (pre-IPO, post-delist, not in S&P 500)
2026-03-04 19:15:01,611 - WARNING -    ⚠️ No precomputed metrics found in cache, will calculate on the fly
2026-03-04 19:15:03,946 - INFO -    ⚠️ Precomputed metrics not available, calculating on the fly...
2026-03-04 19:15:04,032 - INFO -    ⚠️ SMA50 missing in cache, calculating on the fly...
2026-03-04 19:15:05,600 - INFO -    Loading SPY and VIX data for Market Regime...
2026-03-04 19:15:05,601 - INFO - 📊 Loading SPY and VIX data (2021-01-01 to 2024-12-31) [offline=False]...
2026-03-04 19:15:05,605 - INFO -    ✅ SPY loaded from cache: 1005 bars
2026-03-04 19:15:05,829 - INFO -    ✅ VIX loaded from cache: 1005 bars
2026-03-04 19:15:05,829 - INFO -    ✅ Market data loaded successfully
2026-03-04 19:15:05,845 - INFO -    ✅ Market Data Loaded & Aligned
2026-03-04 19:15:05,845 - INFO - ✅ Loaded: 540 tickers
2026-03-04 19:15:05,845 - INFO - 🛡️  Filtered out 26 tickers (insufficient data)
2026-03-04 19:15:05,846 - INFO -    Date range: 2021-01-04 to 2024-12-31 (1005 days)
2026-03-04 19:15:05,846 - INFO -    🔧 Truncating data to start_date: 2022-01-01
2026-03-04 19:15:06,401 - INFO - Memory: ~21.8 MB total after float32 conversion
2026-03-04 19:15:06,419 - INFO - 🎯 Starting advanced backtest with partial exits...
2026-03-04 19:15:06,420 - INFO - 📥 Loading data from 2021-01-01 (buffer) to 2024-12-31...
2026-03-04 19:15:06,420 - INFO - 🎯 Universe size: 540 tickers
2026-03-04 19:15:06,420 - INFO - 🛡️  Survivorship bias protection: PIT mask will determine eligibility quarterly
2026-03-04 19:15:06,420 - INFO - ⚡ Fetching data for 540 tickers in parallel...
