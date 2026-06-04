# Validation Report: russell_baseline_e25_ex_bac_2019_2025

Analyzed on: 2026-06-04 08:40:23

## Temporal Window Performance

| Window | Start | End | Net PnL ($) | Profit Factor | Trades | Win Rate % | Max DD % | Avg Return % |
|---|---|---|---|---|---|---|---|---|
| 2019-2020 (Bull & Pandemic) | 2019-01-01 | 2020-12-31 | $12,593.01 | 1.37 | 37 | 45.95% | -21.8% | 1.38% |
| 2021-2022 (Bubble & Bear) | 2021-01-01 | 2022-12-31 | $4,450.27 | 1.12 | 29 | 48.28% | -13.81% | 0.86% |
| 2023-2024 (AI Expansion) | 2023-01-01 | 2024-12-31 | $20,112.37 | 1.23 | 56 | 46.43% | -18.35% | 0.68% |
| 2025 (Current Year) | 2025-01-01 | 2025-06-30 | $-8,221.82 | 0.64 | 9 | 33.33% | -12.21% | 0.29% |

### Rule Validation Checklist
- **Temporal Consistency Check**: PASSED (3/4 positive windows, 3/4 PF >= 1.05)
- **Drawdown Excessiveness Check**: PASSED (Max local drawdown rule)
- **Concentration Check**: WARNING (Top 1 ticker is PYPL contributing 46.56%)

## Ticker Concentration (Top 10 Contributors)

| Ticker | Net PnL ($) | % of Net PnL |
|---|---|---|
| PYPL | $13,470.15 | 46.56% |
| AMD | $12,843.20 | 44.39% |
| AMAT | $8,824.97 | 30.50% |
| CRWD | $8,501.07 | 29.38% |
| NVDA | $6,812.05 | 23.54% |
| META | $6,221.28 | 21.50% |
| NET | $6,083.87 | 21.03% |
| DDOG | $5,970.24 | 20.63% |
| AAPL | $5,749.52 | 19.87% |
| ENPH | $5,674.73 | 19.61% |

## Sector Performance

| Sector | Net PnL ($) | % of Net PnL |
|---|---|---|
| XLK | $58,597.13 | 202.52% |
| XLC | $6,221.28 | 21.50% |
| XLF | $4,233.60 | 14.63% |
| XLRE | $-2,832.78 | -9.79% |
| XLI | $-3,250.63 | -11.23% |
| XLY | $-7,339.87 | -25.37% |
| XLV | $-11,767.55 | -40.67% |
| XLE | $-14,927.36 | -51.59% |

## E25 Sizing Diagnostics

- **Mean Sizing Factor**: 0.9023
- **Minimum Sizing Factor**: 0.3000

| Sizing Reason | Trade Count | % of Total |
|---|---|---|
| 'comfort_zone' | 103 | 78.63% |
| 'v2_valley_penalty:0.33' | 2 | 1.53% |
| 'v2_atlas_sweetspot:0.33' | 2 | 1.53% |
| 'v2_valley_penalty:0.69' | 1 | 0.76% |
| 'v2_extreme_ext_penalty:0.30' | 1 | 0.76% |
| 'v2_valley_penalty:0.87' | 1 | 0.76% |
| 'v2_valley_penalty:0.98' | 1 | 0.76% |
| 'v2_valley_penalty:0.82' | 1 | 0.76% |
| 'v2_atlas_sweetspot:0.37' | 1 | 0.76% |
| 'v2_valley_penalty:0.94' | 1 | 0.76% |
| 'v2_valley_penalty:0.36' | 1 | 0.76% |
| 'v2_valley_penalty:0.63' | 1 | 0.76% |
| 'v2_atlas_sweetspot:0.36' | 1 | 0.76% |
| 'v2_valley_penalty:0.65' | 1 | 0.76% |
| 'v2_valley_penalty:0.83' | 1 | 0.76% |
| 'v2_atlas_sweetspot:0.47' | 1 | 0.76% |
| 'v2_valley_penalty:0.52' | 1 | 0.76% |
| 'v2_valley_penalty:0.81' | 1 | 0.76% |
| 'v2_high_ext_penalty:0.39' | 1 | 0.76% |
| 'v2_atlas_sweetspot:0.35' | 1 | 0.76% |
| 'v2_valley_penalty:0.70' | 1 | 0.76% |
| 'v2_high_ext_penalty:0.47' | 1 | 0.76% |
| 'v2_valley_penalty:0.54' | 1 | 0.76% |
| 'v2_atlas_sweetspot:0.49' | 1 | 0.76% |
| 'v2_atlas_sweetspot:0.31' | 1 | 0.76% |
| 'v2_valley_penalty:0.61' | 1 | 0.76% |
| 'v2_valley_penalty:0.42' | 1 | 0.76% |
