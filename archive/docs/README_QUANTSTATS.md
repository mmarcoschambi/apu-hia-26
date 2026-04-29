# 🎯 QuantStats Integration - Quick Reference

## TL;DR

**Problem**: Partial exits (TP1, TP2, RUNNER) distort your metrics  
**Solution**: QuantStats integration with proper trade grouping  
**Result**: Accurate metrics + professional analytics  

## 🚀 Quick Start

```bash
# After running your backtest, just run:
python3 analyze_with_quantstats.py

# That's it! You get:
# ✅ Corrected win rate, profit factor, R-multiples
# ✅ Sharpe, Sortino, max drawdown
# ✅ HTML tearsheet with charts
# ✅ Benchmark comparison (vs SPY)
```

## 📂 Files

| File | Purpose |
|------|---------|
| `analyze_with_quantstats.py` | **Main tool** - Run this after backtests |
| `demo_quantstats.py` | **Educational** - Shows the trade grouping problem |
| `example_quantstats_workflow.py` | **Example** - Full workflow integration |
| `QUANTSTATS_INTEGRATION.md` | **Guide** - Complete documentation |
| `QUANTSTATS_MIGRATION_SUMMARY.md` | **Summary** - What was implemented |

## 🎓 Learn by Doing

### 1. See the Problem
```bash
python3 demo_quantstats.py
```
Shows how partial exits distort metrics (9 trades vs 4 actual trades)

### 2. Run Analysis
```bash
python3 analyze_with_quantstats.py
```
Analyzes your latest backtest with correct grouping

### 3. See Full Example
```bash
python3 example_quantstats_workflow.py
```
Complete post-backtest analysis workflow

## 📊 What You Get

### Trade Metrics (Complete Trades)
- ✅ **Win Rate**: Actual % of winning trades (not inflated)
- ✅ **Profit Factor**: True gross wins / gross losses
- ✅ **R-Multiple**: Real expectancy (PnL / Risk)
- ✅ **Exit Analysis**: % hitting TP1, TP2, runners

### QuantStats Metrics (Time-Series)
- ✅ **Sharpe Ratio**: Risk-adjusted returns (>1.5 = good)
- ✅ **Sortino Ratio**: Downside risk focus
- ✅ **Max Drawdown**: Worst peak-to-trough decline
- ✅ **CAGR**: Compounded annual growth
- ✅ **VaR/CVaR**: Value at Risk metrics

### Benchmark Comparison
- ✅ **Alpha**: Excess return vs SPY/QQQ
- ✅ **Beta**: Market correlation
- ✅ **Information Ratio**: Consistency of alpha

### Visualizations (HTML Report)
- ✅ Equity curve with drawdowns
- ✅ Monthly return heatmap
- ✅ Return distribution histogram
- ✅ Rolling Sharpe/Sortino charts

## 🎯 The Trade Grouping Fix

### Before (WRONG ❌)
```
Raw Trade Log:
AAPL TP1:     +$270   (partial 1)
AAPL TP2:     +$432   (partial 2)
AAPL RUNNER:  +$360   (partial 3)

Metrics: 3 "trades", 100% win rate ← DISTORTED!
```

### After (CORRECT ✅)
```
Grouped Trades:
AAPL Complete: +$1,062 (TP1+TP2+RUNNER combined)

Metrics: 1 trade, accurate calculations ← TRUTH!
```

## 🔧 Usage Options

### Basic
```bash
python3 analyze_with_quantstats.py
```

### Custom Benchmark
```bash
python3 analyze_with_quantstats.py --benchmark QQQ
```

### Specific File
```bash
python3 analyze_with_quantstats.py outputs/backtests/trade_log_20240107.csv
```

### Skip HTML (Fast)
```bash
python3 analyze_with_quantstats.py --no-html
```

## 📈 Integration with Your Workflow

**No changes needed to existing code!**

```bash
# Your existing workflow:
python3 backtest_vectorbt_advanced.py  # Run backtest (unchanged)

# New addition:
python3 analyze_with_quantstats.py     # Analyze results (new!)
```

That's it! Your backtest engine stays the same, just add analysis at the end.

## 🎓 Learn More

| Topic | File | Description |
|-------|------|-------------|
| **Full Guide** | `QUANTSTATS_INTEGRATION.md` | Complete documentation with examples |
| **Implementation Details** | `QUANTSTATS_MIGRATION_SUMMARY.md` | What was built and why |
| **Core Module** | `src/analytics/quantstats_analyzer.py` | Source code with docstrings |

## 🎯 Key Metrics to Monitor

### Green Flags ✅
- Sharpe > 1.5
- Average R > 1.0
- Profit Factor > 2.0
- Max DD < 20%
- Positive Skewness

### Red Flags ⚠️
- Sharpe < 1.0
- Average R < 0.5
- Profit Factor < 1.5
- Max DD > 30%
- Negative Skewness

## 💡 Pro Tips

1. **Always analyze complete trades** - Partial exits are execution details
2. **Use R-multiples** - Better than % or $ for comparing trades
3. **Check drawdowns** - Shows real pain points
4. **Compare benchmarks** - Are you beating SPY?
5. **Study exit patterns** - Which sequences work best?

## 🚧 Quick Troubleshooting

**No trade logs found**
→ Run a backtest first: `python3 backtest_vectorbt_advanced.py`

**HTML generation fails**
→ Use `--no-html` flag for console-only output

**Benchmark download fails**
→ Check internet or use `--benchmark None`

## 📞 Need Help?

1. Run `python3 demo_quantstats.py` to understand the concept
2. Read `QUANTSTATS_INTEGRATION.md` for detailed guide
3. Check `example_quantstats_workflow.py` for usage patterns

---

**Ready?** Run `python3 analyze_with_quantstats.py` now! 🚀
