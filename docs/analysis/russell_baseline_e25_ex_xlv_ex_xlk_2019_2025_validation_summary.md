# Validation Report: russell_baseline_e25_ex_xlv_ex_xlk_2019_2025

Analyzed on: 2026-06-04 12:02:43

## Temporal Window Performance

| Window | Start | End | Net PnL ($) | Profit Factor | Trades | Win Rate % | Max DD % | Avg Return % |
|---|---|---|---|---|---|---|---|---|
| 2019-2020 (Bull & Pandemic) | 2019-01-01 | 2020-12-31 | $-8,579.29 | 0.88 | 79 | 40.51% | -24.03% | -0.87% |
| 2021-2022 (Bubble & Bear) | 2021-01-01 | 2022-12-31 | $14,030.5 | 1.27 | 74 | 48.65% | -15.37% | 0.48% |
| 2023-2024 (AI Expansion) | 2023-01-01 | 2024-12-31 | $55,535.93 | 1.51 | 120 | 57.5% | -12.64% | 1.99% |
| 2025 (Current Year) | 2025-01-01 | 2025-06-30 | $-12,011.03 | 0.63 | 24 | 37.5% | -20.71% | -0.66% |

### Rule Validation Checklist
- **Temporal Consistency Check**: FAILED (2/4 positive windows, 2/4 PF >= 1.05)
- **Drawdown Excessiveness Check**: PASSED (Max local drawdown rule)
- **Concentration Check**: WARNING (Top 1 ticker is BAC contributing 27.39%)

## Ticker Concentration (Top 10 Contributors)

| Ticker | Net PnL ($) | % of Net PnL |
|---|---|---|
| BAC | $13,415.36 | 27.39% |
| PYPL | $12,040.70 | 24.58% |
| SOFI | $11,701.13 | 23.89% |
| GE | $11,059.97 | 22.58% |
| GOOG | $11,038.72 | 22.54% |
| AMZN | $8,519.66 | 17.40% |
| F | $6,116.89 | 12.49% |
| CCL | $5,997.38 | 12.25% |
| MCK | $5,074.75 | 10.36% |
| LVS | $4,862.29 | 9.93% |

## Sector Performance

| Sector | Net PnL ($) | % of Net PnL |
|---|---|---|
| XLF | $41,840.78 | 85.43% |
| XLI | $9,516.74 | 19.43% |
| XLY | $7,706.77 | 15.74% |
| XLU | $7,179.53 | 14.66% |
| XLC | $3,346.35 | 6.83% |
| XLV | $-827.33 | -1.69% |
| XLB | $-1,665.63 | -3.40% |
| XLE | $-2,150.99 | -4.39% |
| XLP | $-3,692.23 | -7.54% |
| UNKNOWN | $-12,277.87 | -25.07% |

## E25 Sizing Diagnostics

- **Mean Sizing Factor**: 0.6126
- **Minimum Sizing Factor**: 0.1100

| Sizing Reason | Trade Count | % of Total |
|---|---|---|
| 'comfort_zone' | 96 | 32.32% |
| 'v2_atlas_sweetspot:0.33' | 10 | 3.37% |
| 'v2_atlas_sweetspot:0.34' | 9 | 3.03% |
| 'v2_atlas_sweetspot:0.31' | 9 | 3.03% |
| 'v2_atlas_sweetspot:0.32' | 9 | 3.03% |
| 'v2_atlas_sweetspot:0.37' | 7 | 2.36% |
| 'v2_atlas_sweetspot:0.38' | 6 | 2.02% |
| 'v2_atlas_sweetspot:0.30' | 6 | 2.02% |
| 'v2_valley_penalty:0.35' | 6 | 2.02% |
| 'v2_atlas_sweetspot:0.35' | 5 | 1.68% |
| 'v2_atlas_sweetspot:0.49' | 5 | 1.68% |
| 'v2_atlas_sweetspot:0.36' | 4 | 1.35% |
| 'v2_atlas_sweetspot:0.47' | 4 | 1.35% |
| 'v2_atlas_sweetspot:0.41' | 4 | 1.35% |
| 'v2_atlas_sweetspot:0.39' | 4 | 1.35% |
| 'v2_valley_penalty:0.32' | 4 | 1.35% |
| 'v2_valley_penalty:0.33' | 3 | 1.01% |
| 'v2_valley_penalty:0.36' | 3 | 1.01% |
| 'v2_high_ext_penalty:0.34' | 3 | 1.01% |
| 'v2_atlas_sweetspot:0.44' | 3 | 1.01% |
| 'v2_valley_penalty:0.44' | 3 | 1.01% |
| 'v2_atlas_sweetspot:0.43' | 3 | 1.01% |
| 'v2_valley_penalty:0.31' | 3 | 1.01% |
| 'v2_high_ext_penalty:0.42' | 3 | 1.01% |
| 'v2_valley_penalty:0.54' | 2 | 0.67% |
| 'v2_extreme_ext_penalty:0.22' | 2 | 0.67% |
| 'v2_valley_penalty:0.39' | 2 | 0.67% |
| 'v2_valley_penalty:0.56' | 2 | 0.67% |
| 'v2_valley_penalty:0.58' | 2 | 0.67% |
| 'v2_high_ext_penalty:0.47' | 2 | 0.67% |
| 'v2_valley_penalty:0.70' | 2 | 0.67% |
| 'v2_valley_penalty:0.47' | 2 | 0.67% |
| 'v2_high_ext_penalty:0.32' | 2 | 0.67% |
| 'v2_high_ext_penalty:0.41' | 2 | 0.67% |
| 'v2_valley_penalty:0.91' | 2 | 0.67% |
| 'v2_valley_penalty:0.59' | 2 | 0.67% |
| 'v2_high_ext_penalty:0.49' | 2 | 0.67% |
| 'v2_valley_penalty:0.38' | 2 | 0.67% |
| 'v2_valley_penalty:0.42' | 2 | 0.67% |
| 'v2_valley_penalty:0.92' | 2 | 0.67% |
| 'v2_atlas_sweetspot:0.40' | 2 | 0.67% |
| 'v2_high_ext_penalty:0.43' | 2 | 0.67% |
| 'v2_high_ext_penalty:0.36' | 2 | 0.67% |
| 'v2_high_ext_penalty:0.48' | 2 | 0.67% |
| 'v2_valley_penalty:0.50' | 1 | 0.34% |
| 'v2_valley_penalty:0.76' | 1 | 0.34% |
| 'v2_extreme_ext_penalty:0.16' | 1 | 0.34% |
| 'v2_valley_penalty:0.48' | 1 | 0.34% |
| 'v2_valley_penalty:0.40' | 1 | 0.34% |
| 'v2_valley_penalty:0.94' | 1 | 0.34% |
| 'v2_valley_penalty:0.79' | 1 | 0.34% |
| 'v2_valley_penalty:0.82' | 1 | 0.34% |
| 'v2_atlas_sweetspot:0.42' | 1 | 0.34% |
| 'v2_valley_penalty:0.93' | 1 | 0.34% |
| 'v2_valley_penalty:0.51' | 1 | 0.34% |
| 'v2_high_ext_penalty:0.45' | 1 | 0.34% |
| 'v2_valley_penalty:0.61' | 1 | 0.34% |
| 'v2_valley_penalty:0.90' | 1 | 0.34% |
| 'v2_valley_penalty:0.45' | 1 | 0.34% |
| 'v2_valley_penalty:0.66' | 1 | 0.34% |
| 'v2_valley_penalty:0.77' | 1 | 0.34% |
| 'v2_extreme_ext_penalty:0.11' | 1 | 0.34% |
| 'v2_valley_penalty:0.34' | 1 | 0.34% |
| 'v2_valley_penalty:0.99' | 1 | 0.34% |
| 'v2_valley_penalty:0.57' | 1 | 0.34% |
| 'v2_valley_penalty:0.49' | 1 | 0.34% |
| 'v2_valley_penalty:0.62' | 1 | 0.34% |
| 'v2_valley_penalty:0.71' | 1 | 0.34% |
| 'v2_high_ext_penalty:0.50' | 1 | 0.34% |
| 'extreme_adr_exception' | 1 | 0.34% |
| 'v2_valley_penalty:0.60' | 1 | 0.34% |
| 'v2_valley_penalty:0.86' | 1 | 0.34% |
| 'v2_valley_penalty:0.43' | 1 | 0.34% |
| 'v2_valley_penalty:0.69' | 1 | 0.34% |
| 'v2_extreme_ext_penalty:0.23' | 1 | 0.34% |
| 'v2_extreme_ext_penalty:0.29' | 1 | 0.34% |
| 'v2_atlas_sweetspot:0.50' | 1 | 0.34% |
| 'v2_valley_penalty:0.46' | 1 | 0.34% |
| 'v2_valley_penalty:0.55' | 1 | 0.34% |
| 'v2_high_ext_penalty:0.33' | 1 | 0.34% |
| 'v2_valley_penalty:0.88' | 1 | 0.34% |
| 'v2_high_ext_penalty:0.35' | 1 | 0.34% |
| 'v2_extreme_ext_penalty:0.14' | 1 | 0.34% |
| 'v2_atlas_sweetspot:0.45' | 1 | 0.34% |
| 'v2_atlas_sweetspot:0.46' | 1 | 0.34% |
| 'v2_high_ext_penalty:0.39' | 1 | 0.34% |
| 'v2_valley_penalty:0.63' | 1 | 0.34% |
| 'v2_extreme_ext_penalty:0.26' | 1 | 0.34% |
| 'v2_high_ext_penalty:0.31' | 1 | 0.34% |
