# Validation Report: russell_baseline_e25_ex_xlv_2019_2025

Analyzed on: 2026-06-04 11:48:18

## Temporal Window Performance

| Window | Start | End | Net PnL ($) | Profit Factor | Trades | Win Rate % | Max DD % | Avg Return % |
|---|---|---|---|---|---|---|---|---|
| 2019-2020 (Bull & Pandemic) | 2019-01-01 | 2020-12-31 | $26,198.14 | 1.24 | 106 | 49.06% | -22.1% | 0.65% |
| 2021-2022 (Bubble & Bear) | 2021-01-01 | 2022-12-31 | $7,519.87 | 1.07 | 87 | 52.87% | -19.66% | 1.54% |
| 2023-2024 (AI Expansion) | 2023-01-01 | 2024-12-31 | $65,979.28 | 1.37 | 139 | 52.52% | -29.07% | 1.72% |
| 2025 (Current Year) | 2025-01-01 | 2025-06-30 | $-20,837.18 | 0.56 | 24 | 29.17% | -25.1% | -0.54% |

### Rule Validation Checklist
- **Temporal Consistency Check**: PASSED (3/4 positive windows, 3/4 PF >= 1.05)
- **Drawdown Excessiveness Check**: PASSED (Max local drawdown rule)
- **Concentration Check**: WARNING (Top 1 ticker is NVDA contributing 106.83%)

## Ticker Concentration (Top 10 Contributors)

| Ticker | Net PnL ($) | % of Net PnL |
|---|---|---|
| NVDA | $84,249.05 | 106.83% |
| VRT | $14,589.43 | 18.50% |
| HOOD | $12,884.21 | 16.34% |
| OKTA | $11,148.98 | 14.14% |
| PYPL | $10,887.65 | 13.81% |
| GE | $10,688.01 | 13.55% |
| SOFI | $10,491.84 | 13.30% |
| TSLA | $8,371.41 | 10.62% |
| NUE | $7,966.76 | 10.10% |
| AZO | $7,093.47 | 8.99% |

## Sector Performance

| Sector | Net PnL ($) | % of Net PnL |
|---|---|---|
| XLK | $49,108.17 | 62.27% |
| XLI | $21,381.54 | 27.11% |
| XLF | $20,955.01 | 26.57% |
| XLY | $10,290.60 | 13.05% |
| XLU | $9,109.25 | 11.55% |
| XLE | $2,892.22 | 3.67% |
| XLP | $-152.56 | -0.19% |
| XLB | $-2,701.46 | -3.43% |
| UNKNOWN | $-8,592.29 | -10.90% |
| XLC | $-23,430.38 | -29.71% |

## E25 Sizing Diagnostics

- **Mean Sizing Factor**: 0.6177
- **Minimum Sizing Factor**: 0.1200

| Sizing Reason | Trade Count | % of Total |
|---|---|---|
| 'comfort_zone' | 119 | 33.43% |
| 'v2_atlas_sweetspot:0.36' | 11 | 3.09% |
| 'v2_atlas_sweetspot:0.32' | 11 | 3.09% |
| 'v2_atlas_sweetspot:0.31' | 10 | 2.81% |
| 'v2_atlas_sweetspot:0.33' | 8 | 2.25% |
| 'v2_high_ext_penalty:0.45' | 7 | 1.97% |
| 'v2_atlas_sweetspot:0.30' | 7 | 1.97% |
| 'v2_atlas_sweetspot:0.34' | 6 | 1.69% |
| 'v2_atlas_sweetspot:0.37' | 6 | 1.69% |
| 'v2_high_ext_penalty:0.42' | 5 | 1.40% |
| 'v2_high_ext_penalty:0.40' | 5 | 1.40% |
| 'v2_atlas_sweetspot:0.38' | 5 | 1.40% |
| 'v2_atlas_sweetspot:0.41' | 5 | 1.40% |
| 'v2_atlas_sweetspot:0.35' | 5 | 1.40% |
| 'v2_atlas_sweetspot:0.39' | 4 | 1.12% |
| 'v2_atlas_sweetspot:0.44' | 4 | 1.12% |
| 'v2_high_ext_penalty:0.39' | 4 | 1.12% |
| 'v2_atlas_sweetspot:0.47' | 4 | 1.12% |
| 'v2_high_ext_penalty:0.44' | 3 | 0.84% |
| 'v2_valley_penalty:0.69' | 3 | 0.84% |
| 'v2_high_ext_penalty:0.31' | 3 | 0.84% |
| 'v2_extreme_ext_penalty:0.26' | 3 | 0.84% |
| 'v2_extreme_ext_penalty:0.25' | 3 | 0.84% |
| 'v2_valley_penalty:0.30' | 3 | 0.84% |
| 'v2_valley_penalty:0.68' | 3 | 0.84% |
| 'v2_atlas_sweetspot:0.43' | 3 | 0.84% |
| 'v2_valley_penalty:0.32' | 3 | 0.84% |
| 'v2_valley_penalty:0.49' | 3 | 0.84% |
| 'v2_atlas_sweetspot:0.46' | 3 | 0.84% |
| 'v2_valley_penalty:0.47' | 2 | 0.56% |
| 'v2_valley_penalty:0.62' | 2 | 0.56% |
| 'v2_valley_penalty:0.44' | 2 | 0.56% |
| 'v2_high_ext_penalty:0.47' | 2 | 0.56% |
| 'v2_valley_penalty:0.94' | 2 | 0.56% |
| 'v2_atlas_sweetspot:0.48' | 2 | 0.56% |
| 'v2_high_ext_penalty:0.32' | 2 | 0.56% |
| 'v2_high_ext_penalty:0.34' | 2 | 0.56% |
| 'v2_atlas_sweetspot:0.42' | 2 | 0.56% |
| 'v2_valley_penalty:0.75' | 2 | 0.56% |
| 'v2_extreme_ext_penalty:0.18' | 2 | 0.56% |
| 'v2_valley_penalty:0.63' | 2 | 0.56% |
| 'v2_valley_penalty:0.42' | 2 | 0.56% |
| 'v2_high_ext_penalty:0.49' | 2 | 0.56% |
| 'v2_high_ext_penalty:0.41' | 2 | 0.56% |
| 'v2_high_ext_penalty:0.46' | 2 | 0.56% |
| 'v2_valley_penalty:0.50' | 2 | 0.56% |
| 'v2_extreme_ext_penalty:0.13' | 2 | 0.56% |
| 'v2_valley_penalty:0.33' | 2 | 0.56% |
| 'v2_valley_penalty:0.39' | 2 | 0.56% |
| 'v2_valley_penalty:0.66' | 2 | 0.56% |
| 'v2_high_ext_penalty:0.50' | 2 | 0.56% |
| 'v2_valley_penalty:0.92' | 2 | 0.56% |
| 'v2_valley_penalty:0.31' | 2 | 0.56% |
| 'v2_extreme_ext_penalty:0.28' | 2 | 0.56% |
| 'v2_high_ext_penalty:0.48' | 2 | 0.56% |
| 'v2_high_ext_penalty:0.43' | 2 | 0.56% |
| 'v2_valley_penalty:0.55' | 2 | 0.56% |
| 'v2_valley_penalty:0.43' | 2 | 0.56% |
| 'v2_extreme_ext_penalty:0.24' | 1 | 0.28% |
| 'v2_valley_penalty:0.48' | 1 | 0.28% |
| 'v2_valley_penalty:0.76' | 1 | 0.28% |
| 'v2_valley_penalty:0.54' | 1 | 0.28% |
| 'v2_valley_penalty:0.73' | 1 | 0.28% |
| 'v2_valley_penalty:0.61' | 1 | 0.28% |
| 'v2_valley_penalty:0.52' | 1 | 0.28% |
| 'v2_extreme_ext_penalty:0.21' | 1 | 0.28% |
| 'v2_extreme_ext_penalty:0.23' | 1 | 0.28% |
| 'v2_valley_penalty:0.64' | 1 | 0.28% |
| 'v2_valley_penalty:0.34' | 1 | 0.28% |
| 'v2_valley_penalty:0.78' | 1 | 0.28% |
| 'v2_valley_penalty:0.51' | 1 | 0.28% |
| 'v2_high_ext_penalty:0.30' | 1 | 0.28% |
| 'v2_valley_penalty:0.98' | 1 | 0.28% |
| 'v2_extreme_ext_penalty:0.17' | 1 | 0.28% |
| 'v2_valley_penalty:0.41' | 1 | 0.28% |
| 'v2_valley_penalty:0.86' | 1 | 0.28% |
| 'v2_valley_penalty:0.91' | 1 | 0.28% |
| 'v2_valley_penalty:0.71' | 1 | 0.28% |
| 'v2_valley_penalty:0.80' | 1 | 0.28% |
| 'v2_valley_penalty:0.35' | 1 | 0.28% |
| 'v2_high_ext_penalty:0.38' | 1 | 0.28% |
| 'v2_extreme_ext_penalty:0.12' | 1 | 0.28% |
| 'v2_valley_penalty:0.37' | 1 | 0.28% |
| 'v2_valley_penalty:0.95' | 1 | 0.28% |
| 'v2_valley_penalty:0.74' | 1 | 0.28% |
| 'v2_valley_penalty:0.58' | 1 | 0.28% |
| 'v2_valley_penalty:0.45' | 1 | 0.28% |
| 'v2_valley_penalty:0.65' | 1 | 0.28% |
| 'v2_high_ext_penalty:0.37' | 1 | 0.28% |
| 'v2_extreme_ext_penalty:0.14' | 1 | 0.28% |
| 'v2_valley_penalty:0.84' | 1 | 0.28% |
| 'v2_valley_penalty:0.53' | 1 | 0.28% |
| 'v2_atlas_sweetspot:0.49' | 1 | 0.28% |
| 'v2_atlas_sweetspot:0.40' | 1 | 0.28% |
| 'v2_valley_penalty:0.57' | 1 | 0.28% |
| 'v2_extreme_ext_penalty:0.19' | 1 | 0.28% |
| 'v2_high_ext_penalty:0.36' | 1 | 0.28% |
