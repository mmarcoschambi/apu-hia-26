# Performance Metrics Reference Guide

## Quick Reference: All Available Metrics

### 📊 Risk-Adjusted Returns

| Metric | Formula/Definition | Good Value | Interpretation |
|--------|-------------------|------------|----------------|
| **Sharpe Ratio** | (Return - RiskFree) / Volatility | > 1.0 | Risk-adjusted returns. Higher is better. |
| **Sortino Ratio** | (Return - RiskFree) / Downside Vol | > 1.5 | Like Sharpe but only penalizes downside volatility. |
| **Calmar Ratio** | CAGR / Max Drawdown | > 0.5 | Return per unit of maximum loss risk. |
| **Omega Ratio** | Prob(gains) / Prob(losses) | > 1.5 | Ratio of probability-weighted gains to losses. |

### 💰 Returns

| Metric | Formula/Definition | Good Value | Interpretation |
|--------|-------------------|------------|----------------|
| **CAGR** | Annualized compound growth | > 15% | Smooth annual growth rate. |
| **Total Return** | (End - Start) / Start | Varies | Overall % gain/loss. |
| **Max Drawdown** | Largest peak-to-trough decline | < -20% | Worst loss from peak. Lower is better. |
| **Avg Drawdown** | Average of all drawdowns | < -10% | Typical drawdown size. |

### 🎯 Trade Statistics

| Metric | Formula/Definition | Good Value | Interpretation |
|--------|-------------------|------------|----------------|
| **Total Trades** | Count of complete trades | 30+ | Sample size for statistical validity. |
| **Win Rate** | Winning Trades / Total Trades | 50-70% | % of profitable trades. |
| **Profit Factor** | Total Wins / Total Losses | > 1.5 | Dollars made per dollar lost. |
| **Avg Win/Loss Ratio** | Avg Win / Avg Loss | > 1.5 | Size of wins vs losses. |
| **Avg Holding Period** | Average days held | Varies | Strategy timeframe indicator. |

### ⚠️ Risk Metrics

| Metric | Formula/Definition | Good Value | Interpretation |
|--------|-------------------|------------|----------------|
| **VaR (95%)** | 95th percentile worst loss | -2% to -5% | Expected max daily loss 95% of time. |
| **CVaR (95%)** | Average loss beyond VaR | -3% to -7% | Expected loss in worst 5% of days. |
| **Volatility** | Std dev of returns (annual) | 15-30% | Price fluctuation magnitude. |
| **Tracking Error** | Std dev of (Return - Benchmark) | < 10% | Consistency vs benchmark. |

### 📈 Distribution

| Metric | Formula/Definition | Good Value | Interpretation |
|--------|-------------------|------------|----------------|
| **Skewness** | Asymmetry of return distribution | > 0 | Positive = more upside tail. |
| **Kurtosis** | Tail thickness | 0-5 | High = more extreme outliers. |
| **Exposure Time** | % of days with positions | 30-80% | Time in market vs cash. |

### 🎲 Streaks & Consistency

| Metric | Formula/Definition | Good Value | Interpretation |
|--------|-------------------|------------|----------------|
| **Max Consecutive Wins** | Longest winning streak | 5-15 | Momentum consistency. |
| **Max Consecutive Losses** | Longest losing streak | 2-5 | Risk of multiple bad trades. |
| **Recovery Time** | Days to recover from drawdown | < 90 | How fast strategy recovers. |

### 📊 Benchmark Comparison

| Metric | Formula/Definition | Good Value | Interpretation |
|--------|-------------------|------------|----------------|
| **Alpha** | Excess return vs benchmark | > 0 | Outperformance after adjusting for risk. |
| **Beta** | Correlation to benchmark | 0.3-0.7 | Market sensitivity. 1.0 = moves with market. |
| **Information Ratio** | Alpha / Tracking Error | > 0.5 | Quality of alpha generation. |
| **Excess Return** | Total Return - Benchmark Return | > 0% | Raw outperformance. |

## 🎯 Target Ranges for Momentum Strategy

### Excellent Performance
- CAGR: > 25%
- Sharpe: > 1.5
- Max DD: < -15%
- Win Rate: > 60%
- Profit Factor: > 2.0
- Calmar: > 1.0

### Good Performance
- CAGR: 15-25%
- Sharpe: 1.0-1.5
- Max DD: -15% to -25%
- Win Rate: 50-60%
- Profit Factor: 1.5-2.0
- Calmar: 0.5-1.0

### Needs Improvement
- CAGR: < 15%
- Sharpe: < 1.0
- Max DD: > -25%
- Win Rate: < 50%
- Profit Factor: < 1.5
- Calmar: < 0.5

## 🔍 How to Interpret Your Results

### 1. Check Sharpe Ratio First
- < 0.5: Poor risk-adjusted returns
- 0.5-1.0: Acceptable
- 1.0-2.0: Good
- > 2.0: Excellent (rare)

### 2. Verify Win Rate + Profit Factor
You need EITHER:
- High win rate (>60%) with decent wins, OR
- Lower win rate (40-50%) with large wins (Profit Factor >2.0)

### 3. Assess Drawdown Risk
- Max DD > -30%: Too risky for most traders
- Max DD -20% to -30%: Moderate risk
- Max DD < -20%: Acceptable risk

### 4. Compare to Benchmark
- Alpha > 0: You're adding value
- Beta 0.3-0.7: Good diversification (not just riding market)
- Info Ratio > 0.5: Consistent alpha generation

### 5. Check Distribution Metrics
- Positive skewness: Good (upside tail)
- Kurtosis 3-7: Normal for trading strategies
- Kurtosis > 10: Extreme outliers (verify data quality)

## 📋 Checklist for Strategy Validation

✅ **Minimum Requirements:**
- [ ] Sharpe > 1.0
- [ ] Win Rate > 45% OR Profit Factor > 2.0
- [ ] Max Drawdown < -30%
- [ ] Total Trades > 30 (statistical validity)
- [ ] CAGR > Market benchmark (e.g., SPY)

✅ **Professional Standards:**
- [ ] Sharpe > 1.5
- [ ] Calmar > 0.5
- [ ] VaR (95%) > -5%
- [ ] Positive Alpha vs SPY
- [ ] Max Consecutive Losses < 5

✅ **Institutional Grade:**
- [ ] Sharpe > 2.0
- [ ] Calmar > 1.0
- [ ] Win Rate > 60% AND Profit Factor > 2.0
- [ ] Max DD < -20%
- [ ] Information Ratio > 0.75

## 💡 Common Issues & Solutions

### Issue: High Win Rate but Low Profit Factor
**Problem:** Wins too small compared to losses  
**Solution:** Widen take-profits or tighten stop-losses

### Issue: Good Returns but High Drawdown
**Problem:** Position sizing too aggressive  
**Solution:** Reduce risk per trade, add position sizing rules

### Issue: High Sharpe but Low CAGR
**Problem:** Strategy too conservative  
**Solution:** Increase exposure or position sizes (carefully)

### Issue: Negative Alpha vs Benchmark
**Problem:** Not adding value vs passive investing  
**Solution:** Review entry filters, optimize parameters, or consider indexing

### Issue: High Kurtosis (>10)
**Problem:** Extreme outliers present  
**Solution:** Check for data errors, add risk limits, review large trades

## 📚 Further Reading

- **Sharpe Ratio:** William Sharpe (1966) - "Mutual Fund Performance"
- **Sortino Ratio:** Frank Sortino (1994) - Focus on downside risk
- **Calmar Ratio:** Terry Young (1991) - Commodity traders' favorite
- **VaR/CVaR:** J.P. Morgan (1994) - RiskMetrics methodology
- **Information Ratio:** Grinold & Kahn (2000) - Active portfolio management

## 🎓 Pro Tips

1. **Don't Over-Optimize on Sharpe Alone:** A strategy with Sharpe 3.0 but 10 trades is less reliable than Sharpe 1.5 with 100 trades.

2. **Watch the Win Rate/Profit Factor Balance:** You can't have both low win rate AND low profit factor.

3. **Skewness Matters:** Positive skewness means occasional big wins (good). Negative means occasional big losses (bad).

4. **Compare Apples to Apples:** Always use the same time period when comparing strategies.

5. **Drawdown Recovery:** A -50% drawdown requires +100% return to recover. Keep Max DD reasonable!

---

**Remember:** These metrics tell a story together. Don't focus on just one metric in isolation!
