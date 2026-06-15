# Validation Report: russell_baseline_e25_ex_xlv_tickcap30_2019_2025

Analyzed on: 2026-06-04 12:35:31

## Temporal Window Performance

| Window | Start | End | Net PnL ($) | Profit Factor | Trades | Win Rate % | Max DD % | Avg Return % |
|---|---|---|---|---|---|---|---|---|
| 2019-2020 (Bull & Pandemic) | 2019-01-01 | 2020-12-31 | $30,388.3 | 1.35 | 127 | 53.54% | -21.63% | 1.17% |
| 2021-2022 (Bubble & Bear) | 2021-01-01 | 2022-12-31 | $21,044.75 | 1.19 | 106 | 51.89% | -19.04% | 0.96% |
| 2023-2024 (AI Expansion) | 2023-01-01 | 2024-12-31 | $41,752.16 | 1.19 | 170 | 50.59% | -26.72% | 1.2% |
| 2025 (Current Year) | 2025-01-01 | 2025-06-30 | $-21,669.38 | 0.56 | 30 | 36.67% | -24.01% | -0.85% |

### Rule Validation Checklist
- **Temporal Consistency Check**: PASSED (3/4 positive windows, 3/4 PF >= 1.05)
- **Drawdown Excessiveness Check**: PASSED (Max local drawdown rule)
- **Concentration Check**: WARNING (Top 1 ticker is ANET contributing 26.28%)

## Ticker Concentration (Top 10 Contributors)

| Ticker | Net PnL ($) | % of Net PnL |
|---|---|---|
| ANET | $18,797.62 | 26.28% |
| NVDA | $17,526.80 | 24.51% |
| GOOG | $16,019.03 | 22.40% |
| BAC | $15,046.40 | 21.04% |
| ZS | $11,526.95 | 16.12% |
| AMZN | $11,282.46 | 15.78% |
| MRNA | $9,421.55 | 13.17% |
| GE | $8,559.96 | 11.97% |
| ORCL | $8,305.78 | 11.61% |
| CCL | $8,155.13 | 11.40% |

## Sector Performance

| Sector | Net PnL ($) | % of Net PnL |
|---|---|---|
| UNKNOWN | $51,134.68 | 71.50% |
| XLC | $26,987.78 | 37.74% |
| XLF | $25,646.02 | 35.86% |
| XLY | $9,534.43 | 13.33% |
| XLK | $4,276.32 | 5.98% |
| XLP | $991.75 | 1.39% |
| XLE | $-2,134.26 | -2.98% |
| XLU | $-4,469.54 | -6.25% |
| XLI | $-16,975.27 | -23.74% |
| XLB | $-23,476.08 | -32.83% |

## E25 Sizing Diagnostics

- **Mean Sizing Factor**: 0.6932
- **Minimum Sizing Factor**: 0.1300

| Sizing Reason | Trade Count | % of Total |
|---|---|---|
| 'comfort_zone' | 193 | 44.57% |
| 'v2_atlas_sweetspot:0.33' | 9 | 2.08% |
| 'v2_atlas_sweetspot:0.32' | 9 | 2.08% |
| 'v2_atlas_sweetspot:0.38' | 9 | 2.08% |
| 'v2_atlas_sweetspot:0.31' | 9 | 2.08% |
| 'v2_atlas_sweetspot:0.46' | 7 | 1.62% |
| 'v2_atlas_sweetspot:0.30' | 7 | 1.62% |
| 'v2_atlas_sweetspot:0.37' | 7 | 1.62% |
| 'v2_high_ext_penalty:0.49' | 6 | 1.39% |
| 'v2_atlas_sweetspot:0.35' | 6 | 1.39% |
| 'v2_atlas_sweetspot:0.34' | 6 | 1.39% |
| 'v2_valley_penalty:0.33' | 4 | 0.92% |
| 'v2_high_ext_penalty:0.50' | 4 | 0.92% |
| 'v2_extreme_ext_penalty:0.25' | 4 | 0.92% |
| 'v2_high_ext_penalty:0.42' | 4 | 0.92% |
| 'v2_high_ext_penalty:0.46' | 4 | 0.92% |
| 'v2_high_ext_penalty:0.38' | 4 | 0.92% |
| 'v2_high_ext_penalty:0.41' | 4 | 0.92% |
| 'v2_valley_penalty:0.31' | 4 | 0.92% |
| 'v2_extreme_ext_penalty:0.13' | 3 | 0.69% |
| 'v2_valley_penalty:0.39' | 3 | 0.69% |
| 'v2_valley_penalty:0.91' | 3 | 0.69% |
| 'v2_valley_penalty:0.95' | 3 | 0.69% |
| 'v2_atlas_sweetspot:0.40' | 3 | 0.69% |
| 'v2_valley_penalty:0.46' | 3 | 0.69% |
| 'v2_valley_penalty:0.69' | 3 | 0.69% |
| 'v2_valley_penalty:0.49' | 3 | 0.69% |
| 'v2_high_ext_penalty:0.44' | 3 | 0.69% |
| 'v2_valley_penalty:0.75' | 3 | 0.69% |
| 'v2_atlas_sweetspot:0.42' | 3 | 0.69% |
| 'v2_valley_penalty:0.37' | 3 | 0.69% |
| 'v2_high_ext_penalty:0.39' | 3 | 0.69% |
| 'v2_atlas_sweetspot:0.43' | 2 | 0.46% |
| 'v2_high_ext_penalty:0.48' | 2 | 0.46% |
| 'v2_valley_penalty:0.70' | 2 | 0.46% |
| 'v2_valley_penalty:0.85' | 2 | 0.46% |
| 'v2_valley_penalty:0.65' | 2 | 0.46% |
| 'v2_valley_penalty:0.30' | 2 | 0.46% |
| 'v2_high_ext_penalty:0.31' | 2 | 0.46% |
| 'v2_valley_penalty:0.92' | 2 | 0.46% |
| 'v2_atlas_sweetspot:0.41' | 2 | 0.46% |
| 'v2_valley_penalty:0.55' | 2 | 0.46% |
| 'v2_valley_penalty:0.42' | 2 | 0.46% |
| 'v2_valley_penalty:0.97' | 2 | 0.46% |
| 'v2_valley_penalty:0.50' | 2 | 0.46% |
| 'v2_valley_penalty:0.34' | 2 | 0.46% |
| 'v2_high_ext_penalty:0.45' | 2 | 0.46% |
| 'v2_high_ext_penalty:0.34' | 2 | 0.46% |
| 'v2_atlas_sweetspot:0.47' | 2 | 0.46% |
| 'v2_high_ext_penalty:0.32' | 2 | 0.46% |
| 'v2_valley_penalty:0.43' | 2 | 0.46% |
| 'v2_valley_penalty:0.67' | 2 | 0.46% |
| 'v2_valley_penalty:0.41' | 2 | 0.46% |
| 'v2_atlas_sweetspot:0.36' | 2 | 0.46% |
| 'v2_atlas_sweetspot:0.49' | 2 | 0.46% |
| 'v2_valley_penalty:0.90' | 2 | 0.46% |
| 'v2_valley_penalty:0.35' | 2 | 0.46% |
| 'v2_high_ext_penalty:0.43' | 2 | 0.46% |
| 'v2_high_ext_penalty:0.47' | 2 | 0.46% |
| 'v2_extreme_ext_penalty:0.26' | 1 | 0.23% |
| 'v2_valley_penalty:0.63' | 1 | 0.23% |
| 'v2_high_ext_penalty:0.35' | 1 | 0.23% |
| 'v2_valley_penalty:0.76' | 1 | 0.23% |
| 'v2_valley_penalty:0.38' | 1 | 0.23% |
| 'v2_valley_penalty:0.54' | 1 | 0.23% |
| 'v2_valley_penalty:0.72' | 1 | 0.23% |
| 'v2_valley_penalty:0.73' | 1 | 0.23% |
| 'v2_valley_penalty:0.52' | 1 | 0.23% |
| 'v2_valley_penalty:0.77' | 1 | 0.23% |
| 'v2_extreme_ext_penalty:0.17' | 1 | 0.23% |
| 'v2_valley_penalty:0.66' | 1 | 0.23% |
| 'v2_valley_penalty:0.88' | 1 | 0.23% |
| 'v2_atlas_sweetspot:0.44' | 1 | 0.23% |
| 'v2_valley_penalty:0.32' | 1 | 0.23% |
| 'v2_valley_penalty:0.68' | 1 | 0.23% |
| 'v2_extreme_ext_penalty:0.19' | 1 | 0.23% |
| 'v2_valley_penalty:0.93' | 1 | 0.23% |
| 'v2_high_ext_penalty:0.36' | 1 | 0.23% |
| 'v2_valley_penalty:0.71' | 1 | 0.23% |
| 'v2_high_ext_penalty:0.40' | 1 | 0.23% |
| 'v2_valley_penalty:0.64' | 1 | 0.23% |
| 'v2_valley_penalty:0.40' | 1 | 0.23% |
| 'v2_atlas_sweetspot:0.45' | 1 | 0.23% |
| 'v2_valley_penalty:0.56' | 1 | 0.23% |
| 'extreme_adr_exception' | 1 | 0.23% |
| 'v2_valley_penalty:0.47' | 1 | 0.23% |
| 'v2_extreme_ext_penalty:0.29' | 1 | 0.23% |
| 'v2_valley_penalty:0.87' | 1 | 0.23% |
| 'v2_extreme_ext_penalty:0.20' | 1 | 0.23% |
| 'v2_atlas_sweetspot:0.39' | 1 | 0.23% |
| 'v2_atlas_sweetspot:0.50' | 1 | 0.23% |
| 'v2_high_ext_penalty:0.33' | 1 | 0.23% |
| 'v2_valley_penalty:0.89' | 1 | 0.23% |
| 'v2_extreme_ext_penalty:0.14' | 1 | 0.23% |
| 'v2_extreme_ext_penalty:0.22' | 1 | 0.23% |
| 'v2_extreme_ext_penalty:0.21' | 1 | 0.23% |
| 'v2_valley_penalty:0.98' | 1 | 0.23% |
| 'v2_extreme_ext_penalty:0.18' | 1 | 0.23% |
| 'v2_high_ext_penalty:0.37' | 1 | 0.23% |
