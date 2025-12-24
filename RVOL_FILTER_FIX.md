# RVOL Filter Implementation & Fix

## Issue Identified

AGI trade from 2023-11-28 entered as BLUE_SKY despite having RVOL of only 1.39x, which is below the 1.5x threshold required by the strategy.

## Root Cause: Look-Ahead Bias in RVOL Calculation

The RVOL calculation at signal generation time had a subtle look-ahead bias:

**BEFORE (Line 439-440):**
```python
avg_volume_20 = df['volume'].rolling(window=20).mean().iloc[-1]
rvol = current_bar['volume'] / avg_volume_20
```

This included the CURRENT bar in the 20-day average, artificially inflating RVOL.

**AFTER (Fixed):**
```python
prior_bars = df[df.index < today]
if len(prior_bars) >= 20:
    avg_volume_20 = prior_bars['volume'].tail(20).mean()
    rvol = current_bar['volume'] / avg_volume_20
```

Now RVOL is calculated using ONLY historical data (20 bars BEFORE entry day).

## Filter Rule (Already Implemented)

The filter in `triad_protocol.py` (lines 143-169) rejects Blue Sky breakouts when:

1. **RVOL < 1.5x** - No institutional volume confirmation
2. **Trend = 'Weak'** - Price below SMA20

Both conditions must be satisfied for Blue Sky entries:
- ✅ RVOL > 1.5x (preferably > 2.0x)
- ✅ Trend = 'Uptrend' (price above SMA20)

## Export Improvements

Added `context_rvol` and `context_trend` columns to Streamlit dashboard exports:

**New columns in Trade Log:**
- `context_rvol` - Shows RVOL at entry (e.g., "1.39x")
- `context_trend` - Shows trend status (e.g., "Uptrend" or "Weak")

This allows immediate verification of why trades were accepted/rejected.

## Verification

Run a new backtest and check:
```bash
python daily_backtest_runner.py
```

Then in Streamlit, export trades and verify:
1. All BLUE_SKY trades have `context_rvol >= 1.5`
2. All BLUE_SKY trades have `context_trend = 'Uptrend'`

## Expected Result

AGI (2023-11-28) should now be REJECTED because:
- RVOL: 1.39x < 1.5x threshold ❌
- Filter message: "REJECTED Blue Sky: RVOL (1.39x) is below 1.5x threshold"

