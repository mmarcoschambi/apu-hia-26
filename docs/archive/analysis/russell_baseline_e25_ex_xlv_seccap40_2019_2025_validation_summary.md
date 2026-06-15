# Validation Report: russell_baseline_e25_ex_xlv_seccap40_2019_2025

Analyzed on: 2026-06-04 12:44:02

## Temporal Window Performance

| Window | Start | End | Net PnL ($) | Profit Factor | Trades | Win Rate % | Max DD % | Avg Return % |
|---|---|---|---|---|---|---|---|---|
| 2019-2020 (Bull & Pandemic) | 2019-01-01 | 2020-12-31 | $17,332.78 | 1.19 | 136 | 52.94% | -21.54% | 0.7% |
| 2021-2022 (Bubble & Bear) | 2021-01-01 | 2022-12-31 | $-21,204.34 | 0.78 | 103 | 39.81% | -24.59% | -0.71% |
| 2023-2024 (AI Expansion) | 2023-01-01 | 2024-12-31 | $20,392.85 | 1.17 | 158 | 51.27% | -26.57% | 1.26% |
| 2025 (Current Year) | 2025-01-01 | 2025-06-30 | $-16,918.58 | 0.36 | 27 | 25.93% | -26.36% | -1.69% |

### Rule Validation Checklist
- **Temporal Consistency Check**: FAILED (2/4 positive windows, 2/4 PF >= 1.05)
- **Drawdown Excessiveness Check**: PASSED (Max local drawdown rule)
- **Concentration Check**: PASSED (Top 1 ticker is BAC contributing 0.00%)

## Ticker Concentration (Top 10 Contributors)

| Ticker | Net PnL ($) | % of Net PnL |
|---|---|---|
| BAC | $13,253.61 | 0.00% |
| META | $10,510.88 | 0.00% |
| MRNA | $10,101.29 | 0.00% |
| CEG | $6,303.81 | 0.00% |
| ZS | $5,579.80 | 0.00% |
| UPS | $5,569.24 | 0.00% |
| MS | $5,229.17 | 0.00% |
| CCL | $4,643.41 | 0.00% |
| PYPL | $4,490.31 | 0.00% |
| AMD | $4,164.45 | 0.00% |

## Sector Performance

| Sector | Net PnL ($) | % of Net PnL |
|---|---|---|
| XLF | $30,633.76 | 0.00% |
| XLU | $8,402.20 | 0.00% |
| XLC | $5,438.90 | 0.00% |
| XLE | $4,101.16 | 0.00% |
| XLY | $650.90 | 0.00% |
| UNKNOWN | $-1,424.50 | 0.00% |
| XLI | $-5,486.37 | 0.00% |
| XLB | $-6,041.84 | 0.00% |
| XLP | $-6,561.29 | 0.00% |
| XLK | $-30,110.22 | 0.00% |

## E25 Sizing Diagnostics

- **Mean Sizing Factor**: 0.7236
- **Minimum Sizing Factor**: 0.1300

| Sizing Reason | Trade Count | % of Total |
|---|---|---|
| 'comfort_zone' | 205 | 48.35% |
| 'v2_atlas_sweetspot:0.34' | 9 | 2.12% |
| 'v2_atlas_sweetspot:0.32' | 9 | 2.12% |
| 'v2_atlas_sweetspot:0.38' | 7 | 1.65% |
| 'v2_atlas_sweetspot:0.31' | 7 | 1.65% |
| 'v2_atlas_sweetspot:0.33' | 7 | 1.65% |
| 'v2_atlas_sweetspot:0.39' | 6 | 1.42% |
| 'v2_atlas_sweetspot:0.35' | 6 | 1.42% |
| 'v2_high_ext_penalty:0.41' | 6 | 1.42% |
| 'v2_high_ext_penalty:0.45' | 5 | 1.18% |
| 'v2_high_ext_penalty:0.42' | 5 | 1.18% |
| 'v2_valley_penalty:0.93' | 4 | 0.94% |
| 'v2_atlas_sweetspot:0.36' | 4 | 0.94% |
| 'v2_atlas_sweetspot:0.46' | 4 | 0.94% |
| 'v2_atlas_sweetspot:0.30' | 4 | 0.94% |
| 'v2_high_ext_penalty:0.46' | 4 | 0.94% |
| 'v2_atlas_sweetspot:0.40' | 4 | 0.94% |
| 'v2_high_ext_penalty:0.47' | 4 | 0.94% |
| 'v2_valley_penalty:0.50' | 3 | 0.71% |
| 'v2_valley_penalty:0.83' | 3 | 0.71% |
| 'v2_valley_penalty:0.94' | 3 | 0.71% |
| 'v2_high_ext_penalty:0.49' | 3 | 0.71% |
| 'v2_valley_penalty:0.33' | 3 | 0.71% |
| 'v2_atlas_sweetspot:0.37' | 3 | 0.71% |
| 'v2_valley_penalty:0.90' | 3 | 0.71% |
| 'v2_valley_penalty:0.87' | 3 | 0.71% |
| 'v2_valley_penalty:0.41' | 3 | 0.71% |
| 'v2_valley_penalty:0.97' | 2 | 0.47% |
| 'v2_valley_penalty:0.91' | 2 | 0.47% |
| 'v2_valley_penalty:0.76' | 2 | 0.47% |
| 'v2_valley_penalty:0.89' | 2 | 0.47% |
| 'v2_high_ext_penalty:0.40' | 2 | 0.47% |
| 'v2_valley_penalty:0.49' | 2 | 0.47% |
| 'v2_atlas_sweetspot:0.44' | 2 | 0.47% |
| 'v2_valley_penalty:0.30' | 2 | 0.47% |
| 'v2_valley_penalty:0.32' | 2 | 0.47% |
| 'v2_atlas_sweetspot:0.49' | 2 | 0.47% |
| 'v2_extreme_ext_penalty:0.20' | 2 | 0.47% |
| 'v2_high_ext_penalty:0.35' | 2 | 0.47% |
| 'v2_valley_penalty:0.85' | 2 | 0.47% |
| 'v2_atlas_sweetspot:0.47' | 2 | 0.47% |
| 'v2_high_ext_penalty:0.31' | 2 | 0.47% |
| 'v2_high_ext_penalty:0.48' | 2 | 0.47% |
| 'v2_high_ext_penalty:0.44' | 2 | 0.47% |
| 'v2_extreme_ext_penalty:0.14' | 2 | 0.47% |
| 'v2_high_ext_penalty:0.34' | 2 | 0.47% |
| 'v2_valley_penalty:0.47' | 2 | 0.47% |
| 'v2_valley_penalty:0.55' | 2 | 0.47% |
| 'v2_valley_penalty:0.95' | 2 | 0.47% |
| 'v2_valley_penalty:0.40' | 2 | 0.47% |
| 'v2_atlas_sweetspot:0.48' | 2 | 0.47% |
| 'v2_valley_penalty:0.98' | 2 | 0.47% |
| 'v2_extreme_ext_penalty:0.25' | 2 | 0.47% |
| 'v2_extreme_ext_penalty:0.13' | 2 | 0.47% |
| 'v2_valley_penalty:0.52' | 2 | 0.47% |
| 'v2_atlas_sweetspot:0.42' | 2 | 0.47% |
| 'v2_high_ext_penalty:0.32' | 2 | 0.47% |
| 'v2_valley_penalty:0.31' | 1 | 0.24% |
| 'v2_valley_penalty:0.73' | 1 | 0.24% |
| 'v2_valley_penalty:0.46' | 1 | 0.24% |
| 'v2_valley_penalty:0.44' | 1 | 0.24% |
| 'v2_valley_penalty:0.62' | 1 | 0.24% |
| 'v2_valley_penalty:0.63' | 1 | 0.24% |
| 'v2_extreme_ext_penalty:0.21' | 1 | 0.24% |
| 'v2_valley_penalty:0.74' | 1 | 0.24% |
| 'v2_valley_penalty:0.99' | 1 | 0.24% |
| 'v2_valley_penalty:0.64' | 1 | 0.24% |
| 'v2_high_ext_penalty:0.43' | 1 | 0.24% |
| 'v2_atlas_sweetspot:0.41' | 1 | 0.24% |
| 'v2_valley_penalty:0.51' | 1 | 0.24% |
| 'v2_extreme_ext_penalty:0.18' | 1 | 0.24% |
| 'v2_extreme_ext_penalty:0.26' | 1 | 0.24% |
| 'v2_high_ext_penalty:0.38' | 1 | 0.24% |
| 'v2_high_ext_penalty:0.36' | 1 | 0.24% |
| 'v2_valley_penalty:0.92' | 1 | 0.24% |
| 'v2_valley_penalty:0.39' | 1 | 0.24% |
| 'v2_valley_penalty:0.71' | 1 | 0.24% |
| 'v2_valley_penalty:0.53' | 1 | 0.24% |
| 'v2_high_ext_penalty:0.50' | 1 | 0.24% |
| 'v2_valley_penalty:0.65' | 1 | 0.24% |
| 'v2_atlas_sweetspot:0.45' | 1 | 0.24% |
| 'v2_valley_penalty:0.69' | 1 | 0.24% |
| 'v2_valley_penalty:0.35' | 1 | 0.24% |
| 'v2_extreme_ext_penalty:0.23' | 1 | 0.24% |
| 'extreme_adr_exception' | 1 | 0.24% |
| 'v2_valley_penalty:0.38' | 1 | 0.24% |
| 'v2_valley_penalty:0.86' | 1 | 0.24% |
| 'v2_high_ext_penalty:0.33' | 1 | 0.24% |
| 'v2_extreme_ext_penalty:0.15' | 1 | 0.24% |
| 'v2_extreme_ext_penalty:0.28' | 1 | 0.24% |
| 'v2_extreme_ext_penalty:0.22' | 1 | 0.24% |
| 'v2_extreme_ext_penalty:0.27' | 1 | 0.24% |
| 'v2_atlas_sweetspot:0.43' | 1 | 0.24% |
| 'v2_extreme_ext_penalty:0.19' | 1 | 0.24% |
