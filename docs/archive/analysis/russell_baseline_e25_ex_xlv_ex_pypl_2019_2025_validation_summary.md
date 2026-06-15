# Validation Report: russell_baseline_e25_ex_xlv_ex_pypl_2019_2025

Analyzed on: 2026-06-04 11:56:08

## Temporal Window Performance

| Window | Start | End | Net PnL ($) | Profit Factor | Trades | Win Rate % | Max DD % | Avg Return % |
|---|---|---|---|---|---|---|---|---|
| 2019-2020 (Bull & Pandemic) | 2019-01-01 | 2020-12-31 | $20,413.51 | 1.21 | 101 | 51.49% | -22.53% | 1.19% |
| 2021-2022 (Bubble & Bear) | 2021-01-01 | 2022-12-31 | $-7,674.83 | 0.93 | 92 | 40.22% | -26.77% | -0.38% |
| 2023-2024 (AI Expansion) | 2023-01-01 | 2024-12-31 | $49,459.8 | 1.39 | 137 | 53.28% | -21.23% | 1.86% |
| 2025 (Current Year) | 2025-01-01 | 2025-06-30 | $989.85 | 1.03 | 23 | 43.48% | -16.25% | 2.04% |

### Rule Validation Checklist
- **Temporal Consistency Check**: PASSED (3/4 positive windows, 2/4 PF >= 1.05)
- **Drawdown Excessiveness Check**: PASSED (Max local drawdown rule)
- **Concentration Check**: PASSED (Top 1 ticker is NET contributing 22.76%)

## Ticker Concentration (Top 10 Contributors)

| Ticker | Net PnL ($) | % of Net PnL |
|---|---|---|
| NET | $14,382.86 | 22.76% |
| HOOD | $13,767.26 | 21.79% |
| ANET | $13,171.62 | 20.85% |
| BAC | $12,927.24 | 20.46% |
| SOFI | $12,802.92 | 20.26% |
| TSLA | $12,725.93 | 20.14% |
| NVDA | $12,023.98 | 19.03% |
| OKTA | $9,503.46 | 15.04% |
| MS | $8,149.05 | 12.90% |
| DDOG | $7,540.03 | 11.93% |

## Sector Performance

| Sector | Net PnL ($) | % of Net PnL |
|---|---|---|
| XLF | $44,508.32 | 70.44% |
| XLK | $27,293.23 | 43.19% |
| XLI | $8,947.45 | 14.16% |
| XLE | $5,532.76 | 8.76% |
| XLU | $5,187.81 | 8.21% |
| XLY | $2,893.17 | 4.58% |
| UNKNOWN | $-568.22 | -0.90% |
| XLP | $-3,575.20 | -5.66% |
| XLB | $-9,995.73 | -15.82% |
| XLC | $-17,035.26 | -26.96% |

## E25 Sizing Diagnostics

- **Mean Sizing Factor**: 0.5869
- **Minimum Sizing Factor**: 0.1100

| Sizing Reason | Trade Count | % of Total |
|---|---|---|
| 'comfort_zone' | 101 | 28.61% |
| 'v2_atlas_sweetspot:0.33' | 16 | 4.53% |
| 'v2_atlas_sweetspot:0.31' | 11 | 3.12% |
| 'v2_atlas_sweetspot:0.36' | 8 | 2.27% |
| 'v2_atlas_sweetspot:0.30' | 7 | 1.98% |
| 'v2_atlas_sweetspot:0.32' | 7 | 1.98% |
| 'v2_atlas_sweetspot:0.37' | 6 | 1.70% |
| 'v2_atlas_sweetspot:0.38' | 6 | 1.70% |
| 'v2_atlas_sweetspot:0.44' | 6 | 1.70% |
| 'v2_atlas_sweetspot:0.35' | 6 | 1.70% |
| 'v2_high_ext_penalty:0.45' | 5 | 1.42% |
| 'v2_atlas_sweetspot:0.34' | 5 | 1.42% |
| 'v2_high_ext_penalty:0.47' | 5 | 1.42% |
| 'v2_atlas_sweetspot:0.46' | 5 | 1.42% |
| 'v2_atlas_sweetspot:0.41' | 4 | 1.13% |
| 'v2_atlas_sweetspot:0.49' | 4 | 1.13% |
| 'v2_atlas_sweetspot:0.43' | 4 | 1.13% |
| 'v2_atlas_sweetspot:0.45' | 4 | 1.13% |
| 'v2_valley_penalty:0.32' | 4 | 1.13% |
| 'v2_high_ext_penalty:0.36' | 3 | 0.85% |
| 'v2_high_ext_penalty:0.48' | 3 | 0.85% |
| 'v2_valley_penalty:0.57' | 3 | 0.85% |
| 'v2_atlas_sweetspot:0.47' | 3 | 0.85% |
| 'v2_high_ext_penalty:0.42' | 3 | 0.85% |
| 'v2_extreme_ext_penalty:0.27' | 3 | 0.85% |
| 'v2_high_ext_penalty:0.31' | 3 | 0.85% |
| 'v2_atlas_sweetspot:0.40' | 3 | 0.85% |
| 'v2_high_ext_penalty:0.49' | 3 | 0.85% |
| 'v2_high_ext_penalty:0.40' | 3 | 0.85% |
| 'v2_valley_penalty:0.52' | 3 | 0.85% |
| 'v2_high_ext_penalty:0.35' | 3 | 0.85% |
| 'v2_valley_penalty:0.44' | 3 | 0.85% |
| 'v2_valley_penalty:0.47' | 3 | 0.85% |
| 'v2_atlas_sweetspot:0.39' | 3 | 0.85% |
| 'v2_high_ext_penalty:0.34' | 3 | 0.85% |
| 'v2_valley_penalty:0.41' | 3 | 0.85% |
| 'v2_valley_penalty:0.73' | 2 | 0.57% |
| 'v2_valley_penalty:0.54' | 2 | 0.57% |
| 'v2_extreme_ext_penalty:0.24' | 2 | 0.57% |
| 'v2_high_ext_penalty:0.43' | 2 | 0.57% |
| 'v2_valley_penalty:0.50' | 2 | 0.57% |
| 'v2_valley_penalty:0.39' | 2 | 0.57% |
| 'v2_valley_penalty:0.40' | 2 | 0.57% |
| 'v2_valley_penalty:0.42' | 2 | 0.57% |
| 'v2_extreme_ext_penalty:0.21' | 2 | 0.57% |
| 'v2_valley_penalty:0.33' | 2 | 0.57% |
| 'v2_high_ext_penalty:0.46' | 2 | 0.57% |
| 'v2_valley_penalty:0.62' | 2 | 0.57% |
| 'v2_high_ext_penalty:0.41' | 2 | 0.57% |
| 'v2_valley_penalty:0.49' | 2 | 0.57% |
| 'extreme_adr_exception' | 2 | 0.57% |
| 'v2_valley_penalty:0.35' | 2 | 0.57% |
| 'v2_extreme_ext_penalty:0.13' | 2 | 0.57% |
| 'v2_valley_penalty:0.69' | 2 | 0.57% |
| 'v2_valley_penalty:0.95' | 2 | 0.57% |
| 'v2_valley_penalty:0.68' | 2 | 0.57% |
| 'v2_high_ext_penalty:0.32' | 2 | 0.57% |
| 'v2_extreme_ext_penalty:0.23' | 2 | 0.57% |
| 'v2_valley_penalty:0.55' | 2 | 0.57% |
| 'v2_valley_penalty:0.66' | 2 | 0.57% |
| 'v2_high_ext_penalty:0.44' | 2 | 0.57% |
| 'v2_valley_penalty:0.63' | 1 | 0.28% |
| 'v2_valley_penalty:0.76' | 1 | 0.28% |
| 'v2_valley_penalty:0.61' | 1 | 0.28% |
| 'v2_valley_penalty:0.75' | 1 | 0.28% |
| 'v2_valley_penalty:0.48' | 1 | 0.28% |
| 'v2_valley_penalty:0.60' | 1 | 0.28% |
| 'v2_extreme_ext_penalty:0.11' | 1 | 0.28% |
| 'v2_valley_penalty:0.85' | 1 | 0.28% |
| 'v2_high_ext_penalty:0.37' | 1 | 0.28% |
| 'v2_extreme_ext_penalty:0.16' | 1 | 0.28% |
| 'v2_valley_penalty:0.70' | 1 | 0.28% |
| 'v2_atlas_sweetspot:0.48' | 1 | 0.28% |
| 'v2_valley_penalty:0.88' | 1 | 0.28% |
| 'v2_valley_penalty:0.64' | 1 | 0.28% |
| 'v2_valley_penalty:0.93' | 1 | 0.28% |
| 'v2_valley_penalty:0.98' | 1 | 0.28% |
| 'v2_valley_penalty:0.92' | 1 | 0.28% |
| 'v2_atlas_sweetspot:0.42' | 1 | 0.28% |
| 'v2_valley_penalty:0.71' | 1 | 0.28% |
| 'v2_valley_penalty:0.91' | 1 | 0.28% |
| 'v2_valley_penalty:0.53' | 1 | 0.28% |
| 'v2_valley_penalty:0.59' | 1 | 0.28% |
| 'v2_extreme_ext_penalty:0.12' | 1 | 0.28% |
| 'v2_valley_penalty:0.56' | 1 | 0.28% |
| 'v2_valley_penalty:0.37' | 1 | 0.28% |
| 'v2_valley_penalty:0.58' | 1 | 0.28% |
| 'v2_high_ext_penalty:0.50' | 1 | 0.28% |
| 'v2_extreme_ext_penalty:0.20' | 1 | 0.28% |
| 'v2_valley_penalty:0.51' | 1 | 0.28% |
| 'v2_atlas_sweetspot:0.50' | 1 | 0.28% |
| 'v2_valley_penalty:0.43' | 1 | 0.28% |
| 'v2_extreme_ext_penalty:0.14' | 1 | 0.28% |
| 'v2_high_ext_penalty:0.30' | 1 | 0.28% |
| 'v2_valley_penalty:0.81' | 1 | 0.28% |
| 'v2_extreme_ext_penalty:0.26' | 1 | 0.28% |
| 'v2_high_ext_penalty:0.39' | 1 | 0.28% |
| 'v2_extreme_ext_penalty:0.19' | 1 | 0.28% |
| 'v2_extreme_ext_penalty:0.25' | 1 | 0.28% |
