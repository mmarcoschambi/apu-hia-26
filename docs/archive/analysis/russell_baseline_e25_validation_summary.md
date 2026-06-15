# Validation Report: russell_baseline_e25_rs_fixed_2019_2025

Analyzed on: 2026-06-03 10:42:40

## Temporal Window Performance

| Window | Start | End | Net PnL ($) | Profit Factor | Trades | Win Rate % | Max DD % | Avg Return % |
|---|---|---|---|---|---|---|---|---|
| 2019-2020 (Bull & Pandemic) | 2019-01-01 | 2020-12-31 | $5,562.56 | 1.06 | 116 | 48.28% | -22.02% | 0.53% |
| 2021-2022 (Bubble & Bear) | 2021-01-01 | 2022-12-31 | $-15,414.49 | 0.82 | 100 | 43.0% | -20.57% | -0.5% |
| 2023-2024 (AI Expansion) | 2023-01-01 | 2024-12-31 | $43,950.61 | 1.41 | 148 | 58.78% | -26.22% | 2.33% |
| 2025 (Current Year) | 2025-01-01 | 2025-06-30 | $-7,669.3 | 0.73 | 24 | 33.33% | -22.27% | 0.44% |

### Rule Validation Checklist
- **Temporal Consistency Check**: FAILED (2/4 positive windows, 2/4 PF >= 1.05)
- **Drawdown Excessiveness Check**: PASSED (Max local drawdown rule)
- **Concentration Check**: WARNING (Top 1 ticker is BAC contributing 85.91%)

## Ticker Concentration (Top 10 Contributors)

| Ticker | Net PnL ($) | % of Net PnL |
|---|---|---|
| BAC | $22,705.31 | 85.91% |
| VRT | $16,293.32 | 61.65% |
| TSLA | $11,954.89 | 45.23% |
| ANET | $9,191.33 | 34.78% |
| HOOD | $8,287.77 | 31.36% |
| ZS | $5,718.19 | 21.64% |
| GOOGL | $5,188.58 | 19.63% |
| LRCX | $5,161.24 | 19.53% |
| NUE | $5,003.75 | 18.93% |
| UAL | $4,479.10 | 16.95% |

## Sector Performance

| Sector | Net PnL ($) | % of Net PnL |
|---|---|---|
| XLF | $32,969.82 | 124.75% |
| XLI | $11,787.14 | 44.60% |
| XLE | $5,044.45 | 19.09% |
| UNKNOWN | $5,005.06 | 18.94% |
| XLY | $2,302.83 | 8.71% |
| XLU | $1,445.14 | 5.47% |
| XLK | $642.84 | 2.43% |
| XLRE | $-1,439.12 | -5.45% |
| XLP | $-3,611.77 | -13.67% |
| XLB | $-3,629.74 | -13.73% |
| XLC | $-6,121.06 | -23.16% |
| XLV | $-17,966.19 | -67.98% |

## E25 Sizing Diagnostics

- **Mean Sizing Factor**: 0.5699
- **Minimum Sizing Factor**: 0.1200

| Sizing Reason | Trade Count | % of Total |
|---|---|---|
| 'comfort_zone' | 107 | 27.58% |
| 'v2_atlas_sweetspot:0.33' | 21 | 5.41% |
| 'v2_atlas_sweetspot:0.31' | 15 | 3.87% |
| 'v2_atlas_sweetspot:0.32' | 14 | 3.61% |
| 'v2_atlas_sweetspot:0.34' | 10 | 2.58% |
| 'v2_atlas_sweetspot:0.35' | 10 | 2.58% |
| 'v2_atlas_sweetspot:0.37' | 9 | 2.32% |
| 'v2_atlas_sweetspot:0.36' | 8 | 2.06% |
| 'v2_atlas_sweetspot:0.47' | 7 | 1.80% |
| 'v2_atlas_sweetspot:0.30' | 7 | 1.80% |
| 'v2_atlas_sweetspot:0.38' | 7 | 1.80% |
| 'v2_high_ext_penalty:0.49' | 6 | 1.55% |
| 'v2_high_ext_penalty:0.46' | 6 | 1.55% |
| 'v2_valley_penalty:0.39' | 6 | 1.55% |
| 'v2_valley_penalty:0.44' | 5 | 1.29% |
| 'v2_atlas_sweetspot:0.44' | 4 | 1.03% |
| 'v2_valley_penalty:0.48' | 4 | 1.03% |
| 'v2_atlas_sweetspot:0.40' | 4 | 1.03% |
| 'v2_atlas_sweetspot:0.42' | 4 | 1.03% |
| 'v2_atlas_sweetspot:0.45' | 4 | 1.03% |
| 'v2_extreme_ext_penalty:0.27' | 4 | 1.03% |
| 'v2_high_ext_penalty:0.43' | 4 | 1.03% |
| 'v2_atlas_sweetspot:0.46' | 4 | 1.03% |
| 'v2_high_ext_penalty:0.45' | 4 | 1.03% |
| 'v2_high_ext_penalty:0.34' | 3 | 0.77% |
| 'v2_high_ext_penalty:0.33' | 3 | 0.77% |
| 'v2_atlas_sweetspot:0.43' | 3 | 0.77% |
| 'v2_valley_penalty:0.40' | 3 | 0.77% |
| 'v2_high_ext_penalty:0.37' | 3 | 0.77% |
| 'v2_valley_penalty:0.33' | 3 | 0.77% |
| 'v2_atlas_sweetspot:0.48' | 3 | 0.77% |
| 'v2_high_ext_penalty:0.40' | 3 | 0.77% |
| 'v2_high_ext_penalty:0.39' | 3 | 0.77% |
| 'v2_high_ext_penalty:0.47' | 3 | 0.77% |
| 'v2_valley_penalty:0.53' | 3 | 0.77% |
| 'v2_valley_penalty:0.97' | 2 | 0.52% |
| 'extreme_adr_exception' | 2 | 0.52% |
| 'v2_valley_penalty:0.46' | 2 | 0.52% |
| 'v2_extreme_ext_penalty:0.23' | 2 | 0.52% |
| 'v2_extreme_ext_penalty:0.26' | 2 | 0.52% |
| 'v2_valley_penalty:0.87' | 2 | 0.52% |
| 'v2_valley_penalty:0.32' | 2 | 0.52% |
| 'v2_extreme_ext_penalty:0.20' | 2 | 0.52% |
| 'v2_high_ext_penalty:0.41' | 2 | 0.52% |
| 'v2_atlas_sweetspot:0.39' | 2 | 0.52% |
| 'v2_extreme_ext_penalty:0.14' | 2 | 0.52% |
| 'v2_extreme_ext_penalty:0.24' | 2 | 0.52% |
| 'v2_extreme_ext_penalty:0.25' | 2 | 0.52% |
| 'v2_extreme_ext_penalty:0.12' | 2 | 0.52% |
| 'v2_valley_penalty:0.61' | 2 | 0.52% |
| 'v2_extreme_ext_penalty:0.19' | 2 | 0.52% |
| 'v2_valley_penalty:0.43' | 2 | 0.52% |
| 'v2_valley_penalty:0.38' | 2 | 0.52% |
| 'v2_valley_penalty:0.41' | 2 | 0.52% |
| 'v2_high_ext_penalty:0.50' | 1 | 0.26% |
| 'v2_valley_penalty:0.73' | 1 | 0.26% |
| 'v2_valley_penalty:0.60' | 1 | 0.26% |
| 'v2_valley_penalty:0.50' | 1 | 0.26% |
| 'v2_valley_penalty:0.74' | 1 | 0.26% |
| 'v2_valley_penalty:0.76' | 1 | 0.26% |
| 'v2_valley_penalty:0.49' | 1 | 0.26% |
| 'v2_valley_penalty:0.68' | 1 | 0.26% |
| 'v2_valley_penalty:0.63' | 1 | 0.26% |
| 'v2_high_ext_penalty:0.44' | 1 | 0.26% |
| 'v2_valley_penalty:0.93' | 1 | 0.26% |
| 'v2_high_ext_penalty:0.38' | 1 | 0.26% |
| 'v2_extreme_ext_penalty:0.21' | 1 | 0.26% |
| 'v2_valley_penalty:0.56' | 1 | 0.26% |
| 'v2_valley_penalty:0.52' | 1 | 0.26% |
| 'v2_valley_penalty:0.34' | 1 | 0.26% |
| 'v2_valley_penalty:0.90' | 1 | 0.26% |
| 'v2_valley_penalty:0.54' | 1 | 0.26% |
| 'v2_valley_penalty:0.92' | 1 | 0.26% |
| 'v2_valley_penalty:0.69' | 1 | 0.26% |
| 'v2_valley_penalty:0.95' | 1 | 0.26% |
| 'v2_valley_penalty:0.91' | 1 | 0.26% |
| 'v2_valley_penalty:0.62' | 1 | 0.26% |
| 'v2_valley_penalty:0.86' | 1 | 0.26% |
| 'v2_valley_penalty:0.31' | 1 | 0.26% |
| 'v2_high_ext_penalty:0.32' | 1 | 0.26% |
| 'v2_valley_penalty:0.45' | 1 | 0.26% |
| 'v2_valley_penalty:0.83' | 1 | 0.26% |
| 'v2_valley_penalty:0.47' | 1 | 0.26% |
| 'v2_valley_penalty:0.65' | 1 | 0.26% |
| 'v2_valley_penalty:0.35' | 1 | 0.26% |
| 'v2_extreme_ext_penalty:0.29' | 1 | 0.26% |
| 'v2_extreme_ext_penalty:0.13' | 1 | 0.26% |
| 'v2_valley_penalty:0.30' | 1 | 0.26% |
| 'v2_valley_penalty:0.70' | 1 | 0.26% |
| 'v2_valley_penalty:0.94' | 1 | 0.26% |
| 'v2_high_ext_penalty:0.35' | 1 | 0.26% |
| 'v2_extreme_ext_penalty:0.18' | 1 | 0.26% |
| 'v2_atlas_sweetspot:0.49' | 1 | 0.26% |
| 'v2_high_ext_penalty:0.42' | 1 | 0.26% |
| 'v2_valley_penalty:0.55' | 1 | 0.26% |
| 'v2_valley_penalty:0.57' | 1 | 0.26% |
| 'v2_high_ext_penalty:0.31' | 1 | 0.26% |
