# Validation Report: russell_baseline_e25_ex_xlv_seccap60_2019_2025

Analyzed on: 2026-06-04 12:51:40

## Temporal Window Performance

| Window | Start | End | Net PnL ($) | Profit Factor | Trades | Win Rate % | Max DD % | Avg Return % |
|---|---|---|---|---|---|---|---|---|
| 2019-2020 (Bull & Pandemic) | 2019-01-01 | 2020-12-31 | $33,275.91 | 1.34 | 109 | 55.05% | -21.21% | 1.36% |
| 2021-2022 (Bubble & Bear) | 2021-01-01 | 2022-12-31 | $-19,093.89 | 0.82 | 94 | 41.49% | -25.42% | -0.53% |
| 2023-2024 (AI Expansion) | 2023-01-01 | 2024-12-31 | $37,996.42 | 1.28 | 152 | 51.97% | -20.4% | 1.22% |
| 2025 (Current Year) | 2025-01-01 | 2025-06-30 | $-15,414.3 | 0.59 | 27 | 29.63% | -23.46% | -0.11% |

### Rule Validation Checklist
- **Temporal Consistency Check**: FAILED (2/4 positive windows, 2/4 PF >= 1.05)
- **Drawdown Excessiveness Check**: PASSED (Max local drawdown rule)
- **Concentration Check**: WARNING (Top 1 ticker is ANET contributing 41.49%)

## Ticker Concentration (Top 10 Contributors)

| Ticker | Net PnL ($) | % of Net PnL |
|---|---|---|
| ANET | $15,254.06 | 41.49% |
| PYPL | $12,815.98 | 34.86% |
| NUE | $12,651.08 | 34.41% |
| BAC | $11,540.27 | 31.39% |
| AMD | $9,289.06 | 25.27% |
| OKTA | $8,337.48 | 22.68% |
| TSLA | $7,723.46 | 21.01% |
| HOOD | $7,227.82 | 19.66% |
| GOOG | $6,853.16 | 18.64% |
| SOFI | $6,828.81 | 18.57% |

## Sector Performance

| Sector | Net PnL ($) | % of Net PnL |
|---|---|---|
| XLF | $36,855.15 | 100.25% |
| UNKNOWN | $14,175.93 | 38.56% |
| XLY | $3,422.20 | 9.31% |
| XLB | $2,876.61 | 7.82% |
| XLU | $2,499.60 | 6.80% |
| XLE | $532.73 | 1.45% |
| XLK | $-3,705.08 | -10.08% |
| XLP | $-4,542.11 | -12.35% |
| XLC | $-7,433.98 | -20.22% |
| XLI | $-7,916.90 | -21.53% |

## E25 Sizing Diagnostics

- **Mean Sizing Factor**: 0.6092
- **Minimum Sizing Factor**: 0.1200

| Sizing Reason | Trade Count | % of Total |
|---|---|---|
| 'comfort_zone' | 124 | 32.46% |
| 'v2_atlas_sweetspot:0.33' | 15 | 3.93% |
| 'v2_atlas_sweetspot:0.31' | 14 | 3.66% |
| 'v2_atlas_sweetspot:0.35' | 13 | 3.40% |
| 'v2_atlas_sweetspot:0.37' | 8 | 2.09% |
| 'v2_atlas_sweetspot:0.36' | 8 | 2.09% |
| 'v2_atlas_sweetspot:0.34' | 8 | 2.09% |
| 'v2_atlas_sweetspot:0.32' | 7 | 1.83% |
| 'v2_atlas_sweetspot:0.38' | 7 | 1.83% |
| 'v2_high_ext_penalty:0.47' | 5 | 1.31% |
| 'v2_high_ext_penalty:0.45' | 5 | 1.31% |
| 'v2_atlas_sweetspot:0.30' | 5 | 1.31% |
| 'v2_atlas_sweetspot:0.43' | 4 | 1.05% |
| 'v2_atlas_sweetspot:0.49' | 4 | 1.05% |
| 'v2_high_ext_penalty:0.49' | 4 | 1.05% |
| 'v2_high_ext_penalty:0.41' | 4 | 1.05% |
| 'v2_valley_penalty:0.35' | 4 | 1.05% |
| 'v2_valley_penalty:0.39' | 4 | 1.05% |
| 'v2_extreme_ext_penalty:0.24' | 3 | 0.79% |
| 'v2_valley_penalty:0.32' | 3 | 0.79% |
| 'v2_high_ext_penalty:0.31' | 3 | 0.79% |
| 'v2_high_ext_penalty:0.36' | 3 | 0.79% |
| 'v2_atlas_sweetspot:0.48' | 3 | 0.79% |
| 'v2_valley_penalty:0.41' | 3 | 0.79% |
| 'v2_high_ext_penalty:0.44' | 3 | 0.79% |
| 'v2_atlas_sweetspot:0.47' | 3 | 0.79% |
| 'v2_valley_penalty:0.31' | 3 | 0.79% |
| 'v2_atlas_sweetspot:0.41' | 3 | 0.79% |
| 'v2_atlas_sweetspot:0.46' | 3 | 0.79% |
| 'v2_valley_penalty:0.50' | 3 | 0.79% |
| 'v2_valley_penalty:0.48' | 3 | 0.79% |
| 'v2_atlas_sweetspot:0.42' | 3 | 0.79% |
| 'v2_valley_penalty:0.33' | 3 | 0.79% |
| 'v2_high_ext_penalty:0.35' | 3 | 0.79% |
| 'v2_atlas_sweetspot:0.44' | 3 | 0.79% |
| 'v2_valley_penalty:0.69' | 2 | 0.52% |
| 'v2_valley_penalty:0.66' | 2 | 0.52% |
| 'v2_valley_penalty:0.55' | 2 | 0.52% |
| 'v2_high_ext_penalty:0.33' | 2 | 0.52% |
| 'v2_valley_penalty:0.75' | 2 | 0.52% |
| 'v2_valley_penalty:0.70' | 2 | 0.52% |
| 'v2_valley_penalty:0.47' | 2 | 0.52% |
| 'v2_atlas_sweetspot:0.39' | 2 | 0.52% |
| 'v2_atlas_sweetspot:0.45' | 2 | 0.52% |
| 'v2_valley_penalty:0.71' | 2 | 0.52% |
| 'v2_valley_penalty:0.30' | 2 | 0.52% |
| 'v2_high_ext_penalty:0.43' | 2 | 0.52% |
| 'v2_extreme_ext_penalty:0.25' | 2 | 0.52% |
| 'v2_valley_penalty:0.44' | 2 | 0.52% |
| 'v2_extreme_ext_penalty:0.21' | 2 | 0.52% |
| 'v2_valley_penalty:0.63' | 2 | 0.52% |
| 'v2_extreme_ext_penalty:0.20' | 2 | 0.52% |
| 'v2_valley_penalty:0.95' | 2 | 0.52% |
| 'v2_high_ext_penalty:0.42' | 2 | 0.52% |
| 'v2_high_ext_penalty:0.38' | 2 | 0.52% |
| 'v2_high_ext_penalty:0.48' | 2 | 0.52% |
| 'v2_valley_penalty:0.90' | 2 | 0.52% |
| 'v2_extreme_ext_penalty:0.23' | 2 | 0.52% |
| 'v2_high_ext_penalty:0.37' | 1 | 0.26% |
| 'v2_extreme_ext_penalty:0.26' | 1 | 0.26% |
| 'v2_valley_penalty:0.37' | 1 | 0.26% |
| 'v2_valley_penalty:0.46' | 1 | 0.26% |
| 'extreme_adr_exception' | 1 | 0.26% |
| 'v2_valley_penalty:0.76' | 1 | 0.26% |
| 'v2_valley_penalty:0.52' | 1 | 0.26% |
| 'v2_valley_penalty:0.54' | 1 | 0.26% |
| 'v2_valley_penalty:0.87' | 1 | 0.26% |
| 'v2_valley_penalty:0.61' | 1 | 0.26% |
| 'v2_extreme_ext_penalty:0.15' | 1 | 0.26% |
| 'v2_atlas_sweetspot:0.50' | 1 | 0.26% |
| 'v2_valley_penalty:0.85' | 1 | 0.26% |
| 'v2_valley_penalty:0.97' | 1 | 0.26% |
| 'v2_valley_penalty:0.89' | 1 | 0.26% |
| 'v2_valley_penalty:0.94' | 1 | 0.26% |
| 'v2_valley_penalty:0.49' | 1 | 0.26% |
| 'v2_valley_penalty:0.88' | 1 | 0.26% |
| 'v2_valley_penalty:0.93' | 1 | 0.26% |
| 'v2_valley_penalty:0.98' | 1 | 0.26% |
| 'v2_valley_penalty:0.68' | 1 | 0.26% |
| 'v2_valley_penalty:0.57' | 1 | 0.26% |
| 'v2_valley_penalty:0.42' | 1 | 0.26% |
| 'v2_high_ext_penalty:0.32' | 1 | 0.26% |
| 'v2_valley_penalty:0.91' | 1 | 0.26% |
| 'v2_high_ext_penalty:0.46' | 1 | 0.26% |
| 'v2_extreme_ext_penalty:0.29' | 1 | 0.26% |
| 'v2_extreme_ext_penalty:0.12' | 1 | 0.26% |
| 'v2_valley_penalty:0.38' | 1 | 0.26% |
| 'v2_valley_penalty:0.92' | 1 | 0.26% |
| 'v2_extreme_ext_penalty:0.13' | 1 | 0.26% |
| 'v2_valley_penalty:0.45' | 1 | 0.26% |
| 'v2_high_ext_penalty:0.50' | 1 | 0.26% |
| 'v2_valley_penalty:0.36' | 1 | 0.26% |
| 'v2_valley_penalty:0.43' | 1 | 0.26% |
| 'v2_extreme_ext_penalty:0.16' | 1 | 0.26% |
| 'v2_valley_penalty:0.40' | 1 | 0.26% |
| 'v2_extreme_ext_penalty:0.18' | 1 | 0.26% |
| 'v2_atlas_sweetspot:0.40' | 1 | 0.26% |
| 'v2_high_ext_penalty:0.39' | 1 | 0.26% |
| 'v2_valley_penalty:0.53' | 1 | 0.26% |
| 'v2_high_ext_penalty:0.34' | 1 | 0.26% |
