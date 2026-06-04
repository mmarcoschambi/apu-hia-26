# Validation Report: russell_baseline_e25_ex_xlf_2019_2025

Analyzed on: 2026-06-04 11:40:06

## Temporal Window Performance

| Window | Start | End | Net PnL ($) | Profit Factor | Trades | Win Rate % | Max DD % | Avg Return % |
|---|---|---|---|---|---|---|---|---|
| 2019-2020 (Bull & Pandemic) | 2019-01-01 | 2020-12-31 | $9,414.9 | 1.09 | 99 | 48.48% | -28.53% | 0.7% |
| 2021-2022 (Bubble & Bear) | 2021-01-01 | 2022-12-31 | $15,930.68 | 1.19 | 82 | 50.0% | -16.76% | 1.4% |
| 2023-2024 (AI Expansion) | 2023-01-01 | 2024-12-31 | $41,890.42 | 1.31 | 125 | 52.0% | -23.48% | 1.52% |
| 2025 (Current Year) | 2025-01-01 | 2025-06-30 | $-25,654.51 | 0.32 | 20 | 30.0% | -25.27% | -2.72% |

### Rule Validation Checklist
- **Temporal Consistency Check**: PASSED (3/4 positive windows, 3/4 PF >= 1.05)
- **Drawdown Excessiveness Check**: PASSED (Max local drawdown rule)
- **Concentration Check**: WARNING (Top 1 ticker is TSLA contributing 53.97%)

## Ticker Concentration (Top 10 Contributors)

| Ticker | Net PnL ($) | % of Net PnL |
|---|---|---|
| TSLA | $22,442.06 | 53.97% |
| ANET | $13,870.67 | 33.36% |
| F | $13,768.69 | 33.11% |
| OKTA | $11,148.98 | 26.81% |
| RCL | $10,508.04 | 25.27% |
| VST | $10,396.55 | 25.00% |
| MRNA | $9,181.47 | 22.08% |
| AMD | $8,263.19 | 19.87% |
| NVDA | $8,167.19 | 19.64% |
| AZO | $7,093.47 | 17.06% |

## Sector Performance

| Sector | Net PnL ($) | % of Net PnL |
|---|---|---|
| UNKNOWN | $41,130.05 | 98.91% |
| XLK | $24,897.99 | 59.88% |
| XLU | $12,484.85 | 30.03% |
| XLY | $4,515.43 | 10.86% |
| XLP | $-1,687.91 | -4.06% |
| XLV | $-3,070.46 | -7.38% |
| XLE | $-6,464.13 | -15.55% |
| XLB | $-7,411.60 | -17.82% |
| XLC | $-10,847.03 | -26.09% |
| XLI | $-11,965.69 | -28.78% |

## E25 Sizing Diagnostics

- **Mean Sizing Factor**: 0.6058
- **Minimum Sizing Factor**: 0.1100

| Sizing Reason | Trade Count | % of Total |
|---|---|---|
| 'comfort_zone' | 101 | 30.98% |
| 'v2_atlas_sweetspot:0.31' | 14 | 4.29% |
| 'v2_atlas_sweetspot:0.32' | 13 | 3.99% |
| 'v2_atlas_sweetspot:0.33' | 11 | 3.37% |
| 'v2_atlas_sweetspot:0.35' | 8 | 2.45% |
| 'v2_atlas_sweetspot:0.37' | 8 | 2.45% |
| 'v2_atlas_sweetspot:0.36' | 6 | 1.84% |
| 'v2_atlas_sweetspot:0.38' | 6 | 1.84% |
| 'v2_atlas_sweetspot:0.30' | 6 | 1.84% |
| 'v2_valley_penalty:0.32' | 5 | 1.53% |
| 'v2_atlas_sweetspot:0.46' | 5 | 1.53% |
| 'v2_high_ext_penalty:0.48' | 4 | 1.23% |
| 'v2_high_ext_penalty:0.40' | 4 | 1.23% |
| 'v2_high_ext_penalty:0.49' | 4 | 1.23% |
| 'v2_atlas_sweetspot:0.34' | 4 | 1.23% |
| 'v2_high_ext_penalty:0.47' | 4 | 1.23% |
| 'v2_atlas_sweetspot:0.40' | 3 | 0.92% |
| 'v2_atlas_sweetspot:0.48' | 3 | 0.92% |
| 'v2_valley_penalty:0.30' | 3 | 0.92% |
| 'v2_valley_penalty:0.33' | 3 | 0.92% |
| 'v2_high_ext_penalty:0.45' | 3 | 0.92% |
| 'v2_valley_penalty:0.44' | 3 | 0.92% |
| 'v2_valley_penalty:0.35' | 3 | 0.92% |
| 'v2_atlas_sweetspot:0.45' | 3 | 0.92% |
| 'v2_high_ext_penalty:0.46' | 3 | 0.92% |
| 'v2_valley_penalty:0.42' | 2 | 0.61% |
| 'v2_valley_penalty:0.48' | 2 | 0.61% |
| 'v2_high_ext_penalty:0.41' | 2 | 0.61% |
| 'v2_atlas_sweetspot:0.44' | 2 | 0.61% |
| 'v2_valley_penalty:0.52' | 2 | 0.61% |
| 'v2_valley_penalty:0.47' | 2 | 0.61% |
| 'v2_valley_penalty:0.61' | 2 | 0.61% |
| 'v2_valley_penalty:0.67' | 2 | 0.61% |
| 'v2_high_ext_penalty:0.42' | 2 | 0.61% |
| 'v2_high_ext_penalty:0.34' | 2 | 0.61% |
| 'v2_extreme_ext_penalty:0.27' | 2 | 0.61% |
| 'v2_valley_penalty:0.45' | 2 | 0.61% |
| 'v2_extreme_ext_penalty:0.21' | 2 | 0.61% |
| 'v2_high_ext_penalty:0.35' | 2 | 0.61% |
| 'v2_valley_penalty:0.40' | 2 | 0.61% |
| 'v2_valley_penalty:0.62' | 2 | 0.61% |
| 'v2_valley_penalty:0.49' | 2 | 0.61% |
| 'v2_valley_penalty:0.91' | 2 | 0.61% |
| 'v2_valley_penalty:0.68' | 2 | 0.61% |
| 'v2_high_ext_penalty:0.32' | 2 | 0.61% |
| 'v2_high_ext_penalty:0.43' | 2 | 0.61% |
| 'v2_atlas_sweetspot:0.41' | 2 | 0.61% |
| 'v2_valley_penalty:0.63' | 2 | 0.61% |
| 'v2_valley_penalty:0.39' | 2 | 0.61% |
| 'v2_valley_penalty:0.53' | 2 | 0.61% |
| 'v2_valley_penalty:0.50' | 1 | 0.31% |
| 'v2_valley_penalty:0.54' | 1 | 0.31% |
| 'v2_valley_penalty:0.73' | 1 | 0.31% |
| 'v2_valley_penalty:0.75' | 1 | 0.31% |
| 'v2_valley_penalty:0.76' | 1 | 0.31% |
| 'v2_valley_penalty:0.77' | 1 | 0.31% |
| 'v2_valley_penalty:0.64' | 1 | 0.31% |
| 'v2_high_ext_penalty:0.31' | 1 | 0.31% |
| 'v2_valley_penalty:0.34' | 1 | 0.31% |
| 'v2_valley_penalty:0.98' | 1 | 0.31% |
| 'extreme_adr_exception' | 1 | 0.31% |
| 'v2_high_ext_penalty:0.36' | 1 | 0.31% |
| 'v2_valley_penalty:0.93' | 1 | 0.31% |
| 'v2_atlas_sweetspot:0.47' | 1 | 0.31% |
| 'v2_valley_penalty:0.58' | 1 | 0.31% |
| 'v2_extreme_ext_penalty:0.11' | 1 | 0.31% |
| 'v2_valley_penalty:0.85' | 1 | 0.31% |
| 'v2_valley_penalty:0.72' | 1 | 0.31% |
| 'v2_high_ext_penalty:0.37' | 1 | 0.31% |
| 'v2_valley_penalty:0.92' | 1 | 0.31% |
| 'v2_valley_penalty:0.90' | 1 | 0.31% |
| 'v2_valley_penalty:0.71' | 1 | 0.31% |
| 'v2_valley_penalty:0.69' | 1 | 0.31% |
| 'v2_valley_penalty:0.95' | 1 | 0.31% |
| 'v2_valley_penalty:0.89' | 1 | 0.31% |
| 'v2_high_ext_penalty:0.50' | 1 | 0.31% |
| 'v2_atlas_sweetspot:0.42' | 1 | 0.31% |
| 'v2_extreme_ext_penalty:0.20' | 1 | 0.31% |
| 'v2_atlas_sweetspot:0.39' | 1 | 0.31% |
| 'v2_valley_penalty:0.86' | 1 | 0.31% |
| 'v2_valley_penalty:0.46' | 1 | 0.31% |
| 'v2_extreme_ext_penalty:0.23' | 1 | 0.31% |
| 'v2_valley_penalty:0.66' | 1 | 0.31% |
| 'v2_atlas_sweetspot:0.43' | 1 | 0.31% |
| 'v2_atlas_sweetspot:0.50' | 1 | 0.31% |
| 'v2_extreme_ext_penalty:0.29' | 1 | 0.31% |
| 'v2_high_ext_penalty:0.39' | 1 | 0.31% |
| 'v2_high_ext_penalty:0.33' | 1 | 0.31% |
| 'v2_atlas_sweetspot:0.49' | 1 | 0.31% |
| 'v2_valley_penalty:0.43' | 1 | 0.31% |
| 'v2_valley_penalty:0.81' | 1 | 0.31% |
| 'v2_extreme_ext_penalty:0.22' | 1 | 0.31% |
| 'v2_extreme_ext_penalty:0.13' | 1 | 0.31% |
| 'v2_valley_penalty:0.55' | 1 | 0.31% |
| 'v2_valley_penalty:0.57' | 1 | 0.31% |
| 'v2_extreme_ext_penalty:0.25' | 1 | 0.31% |
