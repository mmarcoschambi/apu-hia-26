# Validation Report: russell_baseline_e25_ex_xlv_tickcap15_2019_2025

Analyzed on: 2026-06-04 12:16:39

## Temporal Window Performance

| Window | Start | End | Net PnL ($) | Profit Factor | Trades | Win Rate % | Max DD % | Avg Return % |
|---|---|---|---|---|---|---|---|---|
| 2019-2020 (Bull & Pandemic) | 2019-01-01 | 2020-12-31 | $29,633.55 | 1.47 | 170 | 57.06% | -18.14% | 1.14% |
| 2021-2022 (Bubble & Bear) | 2021-01-01 | 2022-12-31 | $5,315.07 | 1.07 | 129 | 44.96% | -12.22% | 0.25% |
| 2023-2024 (AI Expansion) | 2023-01-01 | 2024-12-31 | $45,568.91 | 1.35 | 215 | 50.7% | -10.89% | 1.24% |
| 2025 (Current Year) | 2025-01-01 | 2025-06-30 | $-15,822.28 | 0.55 | 35 | 40.0% | -15.28% | -1.45% |

### Rule Validation Checklist
- **Temporal Consistency Check**: PASSED (3/4 positive windows, 3/4 PF >= 1.05)
- **Drawdown Excessiveness Check**: PASSED (Max local drawdown rule)
- **Concentration Check**: WARNING (Top 1 ticker is NVDA contributing 30.05%)

## Ticker Concentration (Top 10 Contributors)

| Ticker | Net PnL ($) | % of Net PnL |
|---|---|---|
| NVDA | $19,440.00 | 30.05% |
| TSLA | $16,139.05 | 24.95% |
| BAC | $10,223.30 | 15.80% |
| COIN | $8,210.33 | 12.69% |
| CRWD | $7,821.77 | 12.09% |
| GOOGL | $7,268.84 | 11.24% |
| GOOG | $6,457.26 | 9.98% |
| NET | $5,275.83 | 8.15% |
| WFC | $5,057.22 | 7.82% |
| OKTA | $5,045.65 | 7.80% |

## Sector Performance

| Sector | Net PnL ($) | % of Net PnL |
|---|---|---|
| XLF | $34,041.34 | 52.62% |
| XLK | $25,840.22 | 39.94% |
| XLC | $9,059.75 | 14.00% |
| UNKNOWN | $8,420.47 | 13.02% |
| XLU | $4,667.49 | 7.21% |
| XLP | $-272.50 | -0.42% |
| XLE | $-1,042.42 | -1.61% |
| XLB | $-2,617.73 | -4.05% |
| XLRE | $-2,836.22 | -4.38% |
| XLI | $-3,137.11 | -4.85% |
| XLY | $-7,428.03 | -11.48% |

## E25 Sizing Diagnostics

- **Mean Sizing Factor**: 0.8413
- **Minimum Sizing Factor**: 0.1300

| Sizing Reason | Trade Count | % of Total |
|---|---|---|
| 'comfort_zone' | 366 | 66.67% |
| 'v2_atlas_sweetspot:0.31' | 8 | 1.46% |
| 'v2_atlas_sweetspot:0.32' | 6 | 1.09% |
| 'v2_valley_penalty:0.68' | 5 | 0.91% |
| 'v2_valley_penalty:0.76' | 5 | 0.91% |
| 'v2_valley_penalty:0.85' | 4 | 0.73% |
| 'v2_atlas_sweetspot:0.44' | 4 | 0.73% |
| 'v2_high_ext_penalty:0.49' | 4 | 0.73% |
| 'v2_atlas_sweetspot:0.34' | 4 | 0.73% |
| 'v2_atlas_sweetspot:0.30' | 4 | 0.73% |
| 'v2_valley_penalty:0.49' | 4 | 0.73% |
| 'v2_atlas_sweetspot:0.47' | 4 | 0.73% |
| 'v2_valley_penalty:0.62' | 3 | 0.55% |
| 'v2_high_ext_penalty:0.50' | 3 | 0.55% |
| 'v2_high_ext_penalty:0.45' | 3 | 0.55% |
| 'v2_high_ext_penalty:0.41' | 3 | 0.55% |
| 'v2_high_ext_penalty:0.47' | 3 | 0.55% |
| 'v2_valley_penalty:0.93' | 3 | 0.55% |
| 'v2_valley_penalty:0.47' | 3 | 0.55% |
| 'v2_valley_penalty:0.37' | 3 | 0.55% |
| 'v2_atlas_sweetspot:0.33' | 3 | 0.55% |
| 'v2_valley_penalty:0.87' | 3 | 0.55% |
| 'v2_atlas_sweetspot:0.35' | 3 | 0.55% |
| 'v2_valley_penalty:0.98' | 3 | 0.55% |
| 'v2_valley_penalty:0.88' | 3 | 0.55% |
| 'v2_high_ext_penalty:0.48' | 3 | 0.55% |
| 'v2_valley_penalty:0.50' | 2 | 0.36% |
| 'v2_valley_penalty:0.81' | 2 | 0.36% |
| 'v2_valley_penalty:0.46' | 2 | 0.36% |
| 'v2_valley_penalty:0.66' | 2 | 0.36% |
| 'v2_valley_penalty:0.41' | 2 | 0.36% |
| 'v2_atlas_sweetspot:0.36' | 2 | 0.36% |
| 'v2_atlas_sweetspot:0.38' | 2 | 0.36% |
| 'v2_valley_penalty:0.67' | 2 | 0.36% |
| 'v2_atlas_sweetspot:0.46' | 2 | 0.36% |
| 'v2_valley_penalty:0.51' | 2 | 0.36% |
| 'v2_high_ext_penalty:0.40' | 2 | 0.36% |
| 'v2_valley_penalty:0.30' | 2 | 0.36% |
| 'v2_valley_penalty:0.95' | 2 | 0.36% |
| 'v2_valley_penalty:0.89' | 2 | 0.36% |
| 'v2_valley_penalty:0.63' | 2 | 0.36% |
| 'v2_high_ext_penalty:0.31' | 2 | 0.36% |
| 'v2_atlas_sweetspot:0.43' | 2 | 0.36% |
| 'v2_high_ext_penalty:0.35' | 2 | 0.36% |
| 'v2_valley_penalty:0.69' | 2 | 0.36% |
| 'v2_high_ext_penalty:0.46' | 2 | 0.36% |
| 'v2_valley_penalty:0.42' | 2 | 0.36% |
| 'v2_valley_penalty:0.75' | 2 | 0.36% |
| 'v2_valley_penalty:0.54' | 1 | 0.18% |
| 'v2_atlas_sweetspot:0.42' | 1 | 0.18% |
| 'v2_atlas_sweetspot:0.37' | 1 | 0.18% |
| 'v2_valley_penalty:0.35' | 1 | 0.18% |
| 'v2_valley_penalty:0.70' | 1 | 0.18% |
| 'v2_valley_penalty:0.61' | 1 | 0.18% |
| 'v2_valley_penalty:0.31' | 1 | 0.18% |
| 'v2_valley_penalty:0.59' | 1 | 0.18% |
| 'v2_valley_penalty:0.72' | 1 | 0.18% |
| 'v2_atlas_sweetspot:0.45' | 1 | 0.18% |
| 'v2_valley_penalty:0.43' | 1 | 0.18% |
| 'v2_valley_penalty:0.32' | 1 | 0.18% |
| 'v2_extreme_ext_penalty:0.28' | 1 | 0.18% |
| 'v2_extreme_ext_penalty:0.15' | 1 | 0.18% |
| 'v2_high_ext_penalty:0.42' | 1 | 0.18% |
| 'v2_high_ext_penalty:0.38' | 1 | 0.18% |
| 'v2_valley_penalty:0.99' | 1 | 0.18% |
| 'v2_valley_penalty:0.94' | 1 | 0.18% |
| 'v2_atlas_sweetspot:0.48' | 1 | 0.18% |
| 'v2_valley_penalty:0.86' | 1 | 0.18% |
| 'v2_valley_penalty:0.57' | 1 | 0.18% |
| 'v2_valley_penalty:0.96' | 1 | 0.18% |
| 'v2_valley_penalty:0.91' | 1 | 0.18% |
| 'v2_valley_penalty:0.64' | 1 | 0.18% |
| 'v2_valley_penalty:0.58' | 1 | 0.18% |
| 'v2_valley_penalty:0.38' | 1 | 0.18% |
| 'v2_extreme_ext_penalty:0.23' | 1 | 0.18% |
| 'v2_valley_penalty:0.79' | 1 | 0.18% |
| 'v2_valley_penalty:0.92' | 1 | 0.18% |
| 'v2_atlas_sweetspot:0.39' | 1 | 0.18% |
| 'v2_valley_penalty:0.60' | 1 | 0.18% |
| 'v2_extreme_ext_penalty:0.16' | 1 | 0.18% |
| 'v2_valley_penalty:0.36' | 1 | 0.18% |
| 'v2_extreme_ext_penalty:0.14' | 1 | 0.18% |
| 'v2_high_ext_penalty:0.39' | 1 | 0.18% |
| 'v2_high_ext_penalty:0.30' | 1 | 0.18% |
| 'v2_high_ext_penalty:0.37' | 1 | 0.18% |
| 'v2_extreme_ext_penalty:0.22' | 1 | 0.18% |
| 'v2_valley_penalty:0.84' | 1 | 0.18% |
| 'v2_valley_penalty:0.73' | 1 | 0.18% |
| 'v2_atlas_sweetspot:0.40' | 1 | 0.18% |
| 'v2_extreme_ext_penalty:0.13' | 1 | 0.18% |
| 'v2_high_ext_penalty:0.43' | 1 | 0.18% |
| 'v2_valley_penalty:0.77' | 1 | 0.18% |
| 'v2_valley_penalty:0.33' | 1 | 0.18% |
