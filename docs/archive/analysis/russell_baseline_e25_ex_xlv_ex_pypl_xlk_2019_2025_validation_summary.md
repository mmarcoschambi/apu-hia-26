# Validation Report: russell_baseline_e25_ex_xlv_ex_pypl_xlk_2019_2025

Analyzed on: 2026-06-04 12:09:06

## Temporal Window Performance

| Window | Start | End | Net PnL ($) | Profit Factor | Trades | Win Rate % | Max DD % | Avg Return % |
|---|---|---|---|---|---|---|---|---|
| 2019-2020 (Bull & Pandemic) | 2019-01-01 | 2020-12-31 | $-4,677.04 | 0.92 | 74 | 41.89% | -19.43% | -0.53% |
| 2021-2022 (Bubble & Bear) | 2021-01-01 | 2022-12-31 | $-20,498.02 | 0.63 | 68 | 44.12% | -29.5% | -0.74% |
| 2023-2024 (AI Expansion) | 2023-01-01 | 2024-12-31 | $27,464.87 | 1.37 | 113 | 52.21% | -22.9% | 1.5% |
| 2025 (Current Year) | 2025-01-01 | 2025-06-30 | $-12,940.79 | 0.45 | 19 | 31.58% | -20.63% | -1.24% |

### Rule Validation Checklist
- **Temporal Consistency Check**: FAILED (1/4 positive windows, 1/4 PF >= 1.05)
- **Drawdown Excessiveness Check**: PASSED (Max local drawdown rule)
- **Concentration Check**: PASSED (Top 1 ticker is BAC contributing 0.00%)

## Ticker Concentration (Top 10 Contributors)

| Ticker | Net PnL ($) | % of Net PnL |
|---|---|---|
| BAC | $11,915.43 | 0.00% |
| GE | $10,638.64 | 0.00% |
| ANET | $8,303.89 | 0.00% |
| VRT | $6,750.11 | 0.00% |
| LLY | $5,609.78 | 0.00% |
| SBUX | $5,342.12 | 0.00% |
| LVS | $3,592.20 | 0.00% |
| CVNA | $3,499.17 | 0.00% |
| GOOG | $3,312.44 | 0.00% |
| MRNA | $3,091.22 | 0.00% |

## Sector Performance

| Sector | Net PnL ($) | % of Net PnL |
|---|---|---|
| XLI | $14,430.13 | 0.00% |
| XLY | $6,402.33 | 0.00% |
| XLF | $5,866.31 | 0.00% |
| XLP | $-485.15 | 0.00% |
| XLU | $-601.04 | 0.00% |
| XLRE | $-1,148.18 | 0.00% |
| XLE | $-3,251.93 | 0.00% |
| XLC | $-3,810.00 | 0.00% |
| XLV | $-4,581.69 | 0.00% |
| XLB | $-9,236.68 | 0.00% |
| UNKNOWN | $-14,235.08 | 0.00% |

## E25 Sizing Diagnostics

- **Mean Sizing Factor**: 0.6226
- **Minimum Sizing Factor**: 0.1400

| Sizing Reason | Trade Count | % of Total |
|---|---|---|
| 'comfort_zone' | 89 | 32.48% |
| 'v2_atlas_sweetspot:0.32' | 9 | 3.28% |
| 'v2_atlas_sweetspot:0.34' | 8 | 2.92% |
| 'v2_atlas_sweetspot:0.33' | 8 | 2.92% |
| 'v2_atlas_sweetspot:0.30' | 8 | 2.92% |
| 'v2_atlas_sweetspot:0.37' | 7 | 2.55% |
| 'v2_atlas_sweetspot:0.41' | 6 | 2.19% |
| 'v2_atlas_sweetspot:0.31' | 5 | 1.82% |
| 'v2_atlas_sweetspot:0.36' | 5 | 1.82% |
| 'v2_atlas_sweetspot:0.35' | 4 | 1.46% |
| 'v2_atlas_sweetspot:0.38' | 4 | 1.46% |
| 'v2_valley_penalty:0.59' | 4 | 1.46% |
| 'v2_atlas_sweetspot:0.45' | 4 | 1.46% |
| 'v2_valley_penalty:0.31' | 4 | 1.46% |
| 'v2_high_ext_penalty:0.40' | 3 | 1.09% |
| 'v2_high_ext_penalty:0.31' | 3 | 1.09% |
| 'v2_high_ext_penalty:0.37' | 3 | 1.09% |
| 'v2_atlas_sweetspot:0.49' | 3 | 1.09% |
| 'v2_high_ext_penalty:0.39' | 3 | 1.09% |
| 'v2_atlas_sweetspot:0.48' | 3 | 1.09% |
| 'v2_valley_penalty:0.40' | 2 | 0.73% |
| 'v2_valley_penalty:0.32' | 2 | 0.73% |
| 'v2_high_ext_penalty:0.45' | 2 | 0.73% |
| 'v2_high_ext_penalty:0.49' | 2 | 0.73% |
| 'v2_atlas_sweetspot:0.47' | 2 | 0.73% |
| 'v2_valley_penalty:0.71' | 2 | 0.73% |
| 'v2_valley_penalty:0.99' | 2 | 0.73% |
| 'v2_valley_penalty:0.42' | 2 | 0.73% |
| 'v2_valley_penalty:0.33' | 2 | 0.73% |
| 'v2_valley_penalty:0.76' | 2 | 0.73% |
| 'v2_high_ext_penalty:0.41' | 2 | 0.73% |
| 'v2_atlas_sweetspot:0.39' | 2 | 0.73% |
| 'v2_valley_penalty:0.35' | 2 | 0.73% |
| 'v2_high_ext_penalty:0.42' | 2 | 0.73% |
| 'v2_valley_penalty:0.36' | 2 | 0.73% |
| 'v2_atlas_sweetspot:0.44' | 2 | 0.73% |
| 'v2_high_ext_penalty:0.43' | 2 | 0.73% |
| 'v2_valley_penalty:0.88' | 2 | 0.73% |
| 'v2_high_ext_penalty:0.36' | 2 | 0.73% |
| 'v2_valley_penalty:0.37' | 2 | 0.73% |
| 'v2_valley_penalty:0.65' | 2 | 0.73% |
| 'v2_high_ext_penalty:0.35' | 2 | 0.73% |
| 'v2_valley_penalty:0.61' | 2 | 0.73% |
| 'v2_valley_penalty:0.38' | 2 | 0.73% |
| 'v2_atlas_sweetspot:0.40' | 2 | 0.73% |
| 'v2_valley_penalty:0.54' | 1 | 0.36% |
| 'v2_valley_penalty:0.48' | 1 | 0.36% |
| 'v2_valley_penalty:0.74' | 1 | 0.36% |
| 'v2_valley_penalty:0.47' | 1 | 0.36% |
| 'v2_valley_penalty:0.91' | 1 | 0.36% |
| 'v2_valley_penalty:0.44' | 1 | 0.36% |
| 'v2_valley_penalty:0.77' | 1 | 0.36% |
| 'v2_valley_penalty:0.64' | 1 | 0.36% |
| 'v2_valley_penalty:0.75' | 1 | 0.36% |
| 'v2_atlas_sweetspot:0.46' | 1 | 0.36% |
| 'v2_valley_penalty:0.92' | 1 | 0.36% |
| 'v2_valley_penalty:0.45' | 1 | 0.36% |
| 'v2_valley_penalty:0.39' | 1 | 0.36% |
| 'v2_valley_penalty:0.66' | 1 | 0.36% |
| 'v2_valley_penalty:0.53' | 1 | 0.36% |
| 'v2_atlas_sweetspot:0.42' | 1 | 0.36% |
| 'extreme_adr_exception' | 1 | 0.36% |
| 'v2_valley_penalty:0.94' | 1 | 0.36% |
| 'v2_valley_penalty:0.46' | 1 | 0.36% |
| 'v2_atlas_sweetspot:0.50' | 1 | 0.36% |
| 'v2_valley_penalty:0.67' | 1 | 0.36% |
| 'v2_valley_penalty:0.69' | 1 | 0.36% |
| 'v2_extreme_ext_penalty:0.24' | 1 | 0.36% |
| 'v2_valley_penalty:0.57' | 1 | 0.36% |
| 'v2_valley_penalty:0.78' | 1 | 0.36% |
| 'v2_high_ext_penalty:0.32' | 1 | 0.36% |
| 'v2_extreme_ext_penalty:0.25' | 1 | 0.36% |
| 'v2_valley_penalty:0.84' | 1 | 0.36% |
| 'v2_high_ext_penalty:0.46' | 1 | 0.36% |
| 'v2_valley_penalty:0.55' | 1 | 0.36% |
| 'v2_valley_penalty:0.41' | 1 | 0.36% |
| 'v2_valley_penalty:0.43' | 1 | 0.36% |
| 'v2_extreme_ext_penalty:0.14' | 1 | 0.36% |
| 'v2_high_ext_penalty:0.47' | 1 | 0.36% |
| 'v2_valley_penalty:0.95' | 1 | 0.36% |
| 'v2_extreme_ext_penalty:0.22' | 1 | 0.36% |
| 'v2_valley_penalty:0.63' | 1 | 0.36% |
| 'v2_valley_penalty:0.68' | 1 | 0.36% |
| 'v2_valley_penalty:0.93' | 1 | 0.36% |
| 'v2_atlas_sweetspot:0.43' | 1 | 0.36% |
| 'v2_high_ext_penalty:0.34' | 1 | 0.36% |
