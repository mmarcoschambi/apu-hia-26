# Validation Report: russell_baseline_no_e25_rs_fixed_2019_2025

Analyzed on: 2026-06-03 11:55:15

## Temporal Window Performance

| Window | Start | End | Net PnL ($) | Profit Factor | Trades | Win Rate % | Max DD % | Avg Return % |
|---|---|---|---|---|---|---|---|---|
| 2019-2020 (Bull & Pandemic) | 2019-01-01 | 2020-12-31 | $44,925.92 | 1.41 | 62 | 53.23% | -24.17% | 0.8% |
| 2021-2022 (Bubble & Bear) | 2021-01-01 | 2022-12-31 | $-35,127.42 | 0.65 | 58 | 44.83% | -33.28% | -1.36% |
| 2023-2024 (AI Expansion) | 2023-01-01 | 2024-12-31 | $-13,112.7 | 0.89 | 69 | 47.83% | -28.08% | -0.2% |
| 2025 (Current Year) | 2025-01-01 | 2025-06-30 | $-9,498.31 | 0.58 | 12 | 16.67% | -19.67% | -3.41% |

### Rule Validation Checklist
- **Temporal Consistency Check**: FAILED (1/4 positive windows, 1/4 PF >= 1.05)
- **Drawdown Excessiveness Check**: FAILED (Max local drawdown rule)
- **Concentration Check**: PASSED (Top 1 ticker is TSLA contributing 0.00%)

## Ticker Concentration (Top 10 Contributors)

| Ticker | Net PnL ($) | % of Net PnL |
|---|---|---|
| TSLA | $14,929.63 | 0.00% |
| LRCX | $10,521.08 | 0.00% |
| AMD | $8,912.57 | 0.00% |
| VST | $8,224.23 | 0.00% |
| FANG | $7,450.48 | 0.00% |
| GOOGL | $7,153.50 | 0.00% |
| AAPL | $7,144.11 | 0.00% |
| OKTA | $6,238.08 | 0.00% |
| VEEV | $6,109.82 | 0.00% |
| NVDA | $4,732.85 | 0.00% |

## Sector Performance

| Sector | Net PnL ($) | % of Net PnL |
|---|---|---|
| XLE | $14,391.04 | 0.00% |
| XLU | $8,217.03 | 0.00% |
| XLK | $6,039.62 | 0.00% |
| XLY | $4,967.00 | 0.00% |
| XLI | $767.42 | 0.00% |
| XLC | $-3,158.22 | 0.00% |
| XLB | $-5,146.60 | 0.00% |
| XLV | $-5,320.27 | 0.00% |
| XLF | $-13,273.11 | 0.00% |
| UNKNOWN | $-20,296.42 | 0.00% |

## E25 Sizing Diagnostics

- **Mean Sizing Factor**: 1.0000
- **Minimum Sizing Factor**: 1.0000

| Sizing Reason | Trade Count | % of Total |
|---|---|---|
| 'disabled' | 201 | 100.00% |
