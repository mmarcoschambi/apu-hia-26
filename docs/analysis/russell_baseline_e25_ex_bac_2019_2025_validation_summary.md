# Validation Report: russell_baseline_e25_ex_bac_2019_2025

Analyzed on: 2026-06-04 11:31:16

## Temporal Window Performance

| Window | Start | End | Net PnL ($) | Profit Factor | Trades | Win Rate % | Max DD % | Avg Return % |
|---|---|---|---|---|---|---|---|---|
| 2019-2020 (Bull & Pandemic) | 2019-01-01 | 2020-12-31 | $31,846.24 | 1.3 | 105 | 50.48% | -22.1% | 0.93% |
| 2021-2022 (Bubble & Bear) | 2021-01-01 | 2022-12-31 | $14,119.76 | 1.12 | 95 | 49.47% | -15.1% | 0.16% |
| 2023-2024 (AI Expansion) | 2023-01-01 | 2024-12-31 | $81,471.87 | 1.55 | 142 | 54.93% | -27.67% | 2.24% |
| 2025 (Current Year) | 2025-01-01 | 2025-06-30 | $-26,194.93 | 0.49 | 24 | 33.33% | -25.49% | -0.7% |

### Rule Validation Checklist
- **Temporal Consistency Check**: PASSED (3/4 positive windows, 3/4 PF >= 1.05)
- **Drawdown Excessiveness Check**: PASSED (Max local drawdown rule)
- **Concentration Check**: WARNING (Top 1 ticker is NVDA contributing 39.93%)

## Ticker Concentration (Top 10 Contributors)

| Ticker | Net PnL ($) | % of Net PnL |
|---|---|---|
| NVDA | $40,427.70 | 39.93% |
| TSLA | $15,989.02 | 15.79% |
| F | $15,329.53 | 15.14% |
| ANET | $13,369.25 | 13.21% |
| NUE | $12,634.39 | 12.48% |
| PYPL | $11,549.76 | 11.41% |
| HOOD | $11,275.86 | 11.14% |
| OKTA | $11,148.98 | 11.01% |
| CRWD | $9,689.26 | 9.57% |
| AMD | $7,253.73 | 7.16% |

## Sector Performance

| Sector | Net PnL ($) | % of Net PnL |
|---|---|---|
| XLK | $43,151.11 | 42.62% |
| XLF | $28,130.58 | 27.79% |
| UNKNOWN | $12,187.50 | 12.04% |
| XLU | $6,646.09 | 6.56% |
| XLV | $5,960.51 | 5.89% |
| XLI | $5,365.92 | 5.30% |
| XLE | $4,024.55 | 3.98% |
| XLB | $3,842.97 | 3.80% |
| XLY | $3,555.18 | 3.51% |
| XLP | $-217.61 | -0.21% |
| XLC | $-11,403.86 | -11.26% |

## E25 Sizing Diagnostics

- **Mean Sizing Factor**: 0.5811
- **Minimum Sizing Factor**: 0.1200

| Sizing Reason | Trade Count | % of Total |
|---|---|---|
| 'comfort_zone' | 102 | 27.87% |
| 'v2_atlas_sweetspot:0.32' | 13 | 3.55% |
| 'v2_atlas_sweetspot:0.33' | 11 | 3.01% |
| 'v2_atlas_sweetspot:0.31' | 11 | 3.01% |
| 'v2_atlas_sweetspot:0.30' | 9 | 2.46% |
| 'v2_atlas_sweetspot:0.37' | 9 | 2.46% |
| 'v2_atlas_sweetspot:0.36' | 8 | 2.19% |
| 'v2_high_ext_penalty:0.45' | 8 | 2.19% |
| 'v2_atlas_sweetspot:0.35' | 6 | 1.64% |
| 'v2_high_ext_penalty:0.42' | 6 | 1.64% |
| 'v2_valley_penalty:0.32' | 5 | 1.37% |
| 'v2_high_ext_penalty:0.39' | 5 | 1.37% |
| 'v2_atlas_sweetspot:0.34' | 5 | 1.37% |
| 'v2_valley_penalty:0.33' | 5 | 1.37% |
| 'v2_atlas_sweetspot:0.47' | 5 | 1.37% |
| 'v2_atlas_sweetspot:0.44' | 4 | 1.09% |
| 'v2_high_ext_penalty:0.46' | 4 | 1.09% |
| 'v2_atlas_sweetspot:0.41' | 4 | 1.09% |
| 'v2_valley_penalty:0.49' | 4 | 1.09% |
| 'v2_atlas_sweetspot:0.46' | 4 | 1.09% |
| 'v2_valley_penalty:0.39' | 4 | 1.09% |
| 'v2_valley_penalty:0.50' | 4 | 1.09% |
| 'v2_atlas_sweetspot:0.39' | 4 | 1.09% |
| 'v2_atlas_sweetspot:0.45' | 4 | 1.09% |
| 'v2_valley_penalty:0.35' | 4 | 1.09% |
| 'v2_high_ext_penalty:0.40' | 3 | 0.82% |
| 'v2_high_ext_penalty:0.34' | 3 | 0.82% |
| 'v2_atlas_sweetspot:0.38' | 3 | 0.82% |
| 'v2_high_ext_penalty:0.44' | 3 | 0.82% |
| 'v2_valley_penalty:0.34' | 3 | 0.82% |
| 'v2_extreme_ext_penalty:0.25' | 3 | 0.82% |
| 'v2_high_ext_penalty:0.49' | 3 | 0.82% |
| 'v2_high_ext_penalty:0.41' | 3 | 0.82% |
| 'v2_valley_penalty:0.41' | 2 | 0.55% |
| 'v2_extreme_ext_penalty:0.13' | 2 | 0.55% |
| 'v2_high_ext_penalty:0.43' | 2 | 0.55% |
| 'v2_valley_penalty:0.61' | 2 | 0.55% |
| 'v2_high_ext_penalty:0.47' | 2 | 0.55% |
| 'v2_extreme_ext_penalty:0.22' | 2 | 0.55% |
| 'v2_valley_penalty:0.92' | 2 | 0.55% |
| 'v2_atlas_sweetspot:0.40' | 2 | 0.55% |
| 'v2_valley_penalty:0.75' | 2 | 0.55% |
| 'v2_valley_penalty:0.86' | 2 | 0.55% |
| 'v2_valley_penalty:0.46' | 2 | 0.55% |
| 'v2_valley_penalty:0.43' | 2 | 0.55% |
| 'v2_valley_penalty:0.68' | 2 | 0.55% |
| 'v2_valley_penalty:0.62' | 2 | 0.55% |
| 'v2_valley_penalty:0.47' | 2 | 0.55% |
| 'v2_valley_penalty:0.44' | 2 | 0.55% |
| 'v2_valley_penalty:0.52' | 2 | 0.55% |
| 'v2_valley_penalty:0.40' | 2 | 0.55% |
| 'v2_high_ext_penalty:0.31' | 2 | 0.55% |
| 'v2_valley_penalty:0.36' | 2 | 0.55% |
| 'v2_high_ext_penalty:0.48' | 2 | 0.55% |
| 'v2_valley_penalty:0.69' | 2 | 0.55% |
| 'v2_high_ext_penalty:0.35' | 2 | 0.55% |
| 'v2_valley_penalty:0.53' | 2 | 0.55% |
| 'v2_atlas_sweetspot:0.42' | 2 | 0.55% |
| 'v2_valley_penalty:0.42' | 1 | 0.27% |
| 'v2_valley_penalty:0.48' | 1 | 0.27% |
| 'v2_valley_penalty:0.54' | 1 | 0.27% |
| 'v2_valley_penalty:0.73' | 1 | 0.27% |
| 'v2_extreme_ext_penalty:0.26' | 1 | 0.27% |
| 'v2_extreme_ext_penalty:0.24' | 1 | 0.27% |
| 'v2_valley_penalty:0.76' | 1 | 0.27% |
| 'v2_valley_penalty:0.63' | 1 | 0.27% |
| 'v2_high_ext_penalty:0.33' | 1 | 0.27% |
| 'v2_extreme_ext_penalty:0.21' | 1 | 0.27% |
| 'v2_valley_penalty:0.98' | 1 | 0.27% |
| 'v2_extreme_ext_penalty:0.17' | 1 | 0.27% |
| 'v2_valley_penalty:0.45' | 1 | 0.27% |
| 'v2_valley_penalty:0.59' | 1 | 0.27% |
| 'v2_atlas_sweetspot:0.50' | 1 | 0.27% |
| 'v2_valley_penalty:0.56' | 1 | 0.27% |
| 'v2_high_ext_penalty:0.37' | 1 | 0.27% |
| 'v2_valley_penalty:0.88' | 1 | 0.27% |
| 'v2_valley_penalty:0.64' | 1 | 0.27% |
| 'v2_valley_penalty:0.31' | 1 | 0.27% |
| 'v2_valley_penalty:0.37' | 1 | 0.27% |
| 'v2_high_ext_penalty:0.50' | 1 | 0.27% |
| 'v2_valley_penalty:0.95' | 1 | 0.27% |
| 'v2_valley_penalty:0.71' | 1 | 0.27% |
| 'v2_extreme_ext_penalty:0.27' | 1 | 0.27% |
| 'v2_valley_penalty:0.79' | 1 | 0.27% |
| 'v2_valley_penalty:0.87' | 1 | 0.27% |
| 'v2_valley_penalty:0.91' | 1 | 0.27% |
| 'extreme_adr_exception' | 1 | 0.27% |
| 'v2_valley_penalty:0.38' | 1 | 0.27% |
| 'v2_extreme_ext_penalty:0.29' | 1 | 0.27% |
| 'v2_extreme_ext_penalty:0.12' | 1 | 0.27% |
| 'v2_valley_penalty:0.66' | 1 | 0.27% |
| 'v2_valley_penalty:0.84' | 1 | 0.27% |
| 'v2_atlas_sweetspot:0.48' | 1 | 0.27% |
| 'v2_high_ext_penalty:0.38' | 1 | 0.27% |
| 'v2_valley_penalty:0.30' | 1 | 0.27% |
| 'v2_extreme_ext_penalty:0.14' | 1 | 0.27% |
| 'v2_high_ext_penalty:0.30' | 1 | 0.27% |
| 'v2_atlas_sweetspot:0.49' | 1 | 0.27% |
| 'v2_valley_penalty:0.55' | 1 | 0.27% |
| 'v2_valley_penalty:0.57' | 1 | 0.27% |
| 'v2_atlas_sweetspot:0.43' | 1 | 0.27% |
| 'v2_high_ext_penalty:0.36' | 1 | 0.27% |
