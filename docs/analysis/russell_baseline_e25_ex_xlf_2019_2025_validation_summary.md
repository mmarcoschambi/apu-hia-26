# Validation Report: russell_baseline_e25_ex_xlf_2019_2025

Analyzed on: 2026-06-04 09:09:31

## Temporal Window Performance

| Window | Start | End | Net PnL ($) | Profit Factor | Trades | Win Rate % | Max DD % | Avg Return % |
|---|---|---|---|---|---|---|---|---|
| 2019-2020 (Bull & Pandemic) | 2019-01-01 | 2020-12-31 | $7,681.87 | 1.23 | 34 | 41.18% | -21.86% | 1.27% |
| 2021-2022 (Bubble & Bear) | 2021-01-01 | 2022-12-31 | $1,518.97 | 1.04 | 29 | 44.83% | -13.82% | 0.45% |
| 2023-2024 (AI Expansion) | 2023-01-01 | 2024-12-31 | $36,147.51 | 1.55 | 53 | 50.94% | -17.05% | 1.31% |
| 2025 (Current Year) | 2025-01-01 | 2025-06-30 | $-11,840.28 | 0.27 | 6 | 33.33% | -9.92% | -2.11% |

### Rule Validation Checklist
- **Temporal Consistency Check**: PASSED (3/4 positive windows, 2/4 PF >= 1.05)
- **Drawdown Excessiveness Check**: PASSED (Max local drawdown rule)
- **Concentration Check**: WARNING (Top 1 ticker is AMD contributing 35.99%)

## Ticker Concentration (Top 10 Contributors)

| Ticker | Net PnL ($) | % of Net PnL |
|---|---|---|
| AMD | $12,060.01 | 35.99% |
| AMZN | $10,525.30 | 31.41% |
| NVDA | $8,662.40 | 25.85% |
| AMAT | $8,340.89 | 24.89% |
| NET | $6,085.80 | 18.16% |
| CCI | $5,939.95 | 17.73% |
| DDOG | $5,665.99 | 16.91% |
| ENPH | $5,639.09 | 16.83% |
| AAPL | $5,488.38 | 16.38% |
| CRWD | $5,482.24 | 16.36% |

## Sector Performance

| Sector | Net PnL ($) | % of Net PnL |
|---|---|---|
| XLK | $48,780.84 | 145.58% |
| XLY | $6,631.50 | 19.79% |
| XLC | $413.72 | 1.23% |
| XLRE | $-632.13 | -1.89% |
| XLI | $-2,743.78 | -8.19% |
| XLV | $-4,981.07 | -14.87% |
| XLE | $-13,961.00 | -41.66% |

## E25 Sizing Diagnostics

- **Mean Sizing Factor**: 0.9161
- **Minimum Sizing Factor**: 0.3000

| Sizing Reason | Trade Count | % of Total |
|---|---|---|
| 'comfort_zone' | 100 | 81.97% |
| 'v2_valley_penalty:0.36' | 1 | 0.82% |
| 'v2_extreme_ext_penalty:0.30' | 1 | 0.82% |
| 'v2_valley_penalty:0.98' | 1 | 0.82% |
| 'v2_valley_penalty:0.87' | 1 | 0.82% |
| 'v2_valley_penalty:0.82' | 1 | 0.82% |
| 'v2_valley_penalty:0.33' | 1 | 0.82% |
| 'v2_atlas_sweetspot:0.37' | 1 | 0.82% |
| 'v2_valley_penalty:0.63' | 1 | 0.82% |
| 'v2_atlas_sweetspot:0.33' | 1 | 0.82% |
| 'v2_atlas_sweetspot:0.36' | 1 | 0.82% |
| 'v2_valley_penalty:0.65' | 1 | 0.82% |
| 'v2_valley_penalty:0.41' | 1 | 0.82% |
| 'v2_valley_penalty:0.83' | 1 | 0.82% |
| 'v2_atlas_sweetspot:0.47' | 1 | 0.82% |
| 'v2_valley_penalty:0.52' | 1 | 0.82% |
| 'v2_valley_penalty:0.81' | 1 | 0.82% |
| 'v2_high_ext_penalty:0.39' | 1 | 0.82% |
| 'v2_atlas_sweetspot:0.35' | 1 | 0.82% |
| 'v2_high_ext_penalty:0.47' | 1 | 0.82% |
| 'v2_atlas_sweetspot:0.49' | 1 | 0.82% |
| 'v2_valley_penalty:0.61' | 1 | 0.82% |
| 'v2_valley_penalty:0.42' | 1 | 0.82% |
