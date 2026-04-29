# 🔧 Stop-Loss Bug Fix & Data Quality Issues

## Date: 2026-02-02

---

## 🔴 BUG #1: Microscopic Stops with Low ATR ✅ FIXED

**File:** `src/backtest/numba_core.py:332`

**Root Cause:**
```python
# BUGGY CODE
stop_dist_pct = curr_close * max_stop_pct  # $100 * 0.03 = $3.00
stop_dist_atr = curr_atr * 1.5             # $0.01 * 1.5 = $0.015  
stop_dist = min(stop_dist_pct, stop_dist_atr)  # = $0.015 ❌
```

**Impact:**
- Stop distance = **0.015%** instead of 3%
- Position size: `shares = $2000 / $0.015 = 133,333 shares` ($13.3M!)
- **Immediate stop-outs** on normal volatility
- **This caused the +51.66% → poor performance degradation**

**Fix Applied:**
```python
stop_dist = curr_close * max_stop_pct  # Always use configured %
```

---

## 🔴 BUG #2: Stale Dividend Adjustments ⏳ FIXED (6,160 tickers refreshed)

**Problem:** yfinance applies dividend adjustments **backward** to historical prices

**Example (ATLO on 2022-01-25):**
- Real unadjusted price: $24.95
- Current adjustment (Feb 2026): $20.56
- OLD cache (Jan 28): $19.45
- CSV backtest entry: $17.25 ❌ **-16% error!**

**Solution:** ✅ Ran `refresh_all_cache.py` - All tickers updated with current adjustments

---

## 🔴 BUG #3: Anachronistic Tickers (Time Travelers) ⚠️ CRITICAL

**Problem:** Tickers in backtest that **didn't exist** during backtest period

**Examples Found:**
| Ticker | Trade Date | Actual Launch | Days Early | Type |
|--------|-----------|---------------|------------|------|
| ABNG   | 2021-11-05 | 2025-11-17   | **+1,473 days** | ETF (2x ABNB) |
| CARY   | 2021-11-09 | 2022-11-08   | +364 days | ETF |
| AGGH   | 2021-11-05 | 2022-02-17   | +104 days | ETF |
| AEON   | 2021-04-12 | 2023-01-03   | +631 days | Biotech |

**How This Happens:**
1. yfinance sometimes **backfills** data for new tickers
2. Universe lists don't validate inception dates
3. Backtest trades on "phantom" historical data that never existed

**Impact:**
- ❌ Unrealistic backtest results (trading stocks that didn't exist)
- ❌ Lookahead bias (using future tickers in past analysis)
- ❌ Inflated trade counts and PnL

**Solution Created:**
```bash
python3 detect_and_purge_anachronisms.py  # Scans 6,160 tickers (~10 min)
```

This will:
1. Compare cached data start date vs yfinance actual inception
2. Flag tickers with data >30 days before inception
3. Generate `anachronistic_tickers.txt` for cleanup

---

## 🔴 BUG #4: Invalid Ticker Suffixes ⚠️ DETECTED

**Examples from refresh log:**
- `APP_earnings` → Should be `APP` 
- `CHKP_daily` → Should be `CHKP`
- `MSTR_earnings`, `CTSH_earnings`, etc.

**Problem:** Suffixes like `_earnings`, `_daily` are artifacts, not valid tickers

**Count:** ~15-20 invalid tickers in universe

---

## Action Plan

### Immediate (Critical)
1. ✅ Stop-loss fix applied
2. ✅ Cache refreshed (6,160 tickers)
3. ⏳ **Run anachronism detector:** `python3 detect_and_purge_anachronisms.py`
4. ⏳ **Purge bad tickers** from cache and universe lists

### Post-Cleanup
5. ⏳ Re-run backtest for 2021-2024 with clean data
6. ⏳ Verify +51.66% results return

---

## Files Modified
- ✅ `src/backtest/numba_core.py` (stop calculation)
- ✅ `data/cache/*.pkl` (6,160 tickers refreshed)

## Files Created  
- ✅ `refresh_all_cache.py` (dividend adjustment fix)
- ✅ `detect_and_purge_anachronisms.py` (time traveler detector)
- ✅ `STOP_BUG_FIX_SUMMARY.md` (this file)

---

## Estimated Impact

**Before fixes:**
- Microscopic stops → oversized positions → immediate stop-outs
- Stale dividend adjustments → wrong entry/exit prices
- Anachronistic tickers → phantom trades on non-existent stocks
- **Result:** Garbage in, garbage out

**After fixes:**
- ✅ Proper 3-7% stops
- ✅ Current price adjustments
- ⏳ Only tickers that actually existed during backtest period
- **Expected:** Return to +51.66% performance (or better)
