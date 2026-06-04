# Validation Report: russell_baseline_e25_ex_xlv_tickcap20_2019_2025

Analyzed on: 2026-06-04 12:26:53

## Temporal Window Performance

| Window | Start | End | Net PnL ($) | Profit Factor | Trades | Win Rate % | Max DD % | Avg Return % |
|---|---|---|---|---|---|---|---|---|
| 2019-2020 (Bull & Pandemic) | 2019-01-01 | 2020-12-31 | $31,800.76 | 1.5 | 122 | 52.46% | -14.94% | 1.2% |
| 2021-2022 (Bubble & Bear) | 2021-01-01 | 2022-12-31 | $29,031.92 | 1.49 | 88 | 56.82% | -9.73% | 1.18% |
| 2023-2024 (AI Expansion) | 2023-01-01 | 2024-12-31 | $56,601.25 | 1.33 | 163 | 51.53% | -15.89% | 1.47% |
| 2025 (Current Year) | 2025-01-01 | 2025-06-30 | $-20,648.19 | 0.54 | 30 | 33.33% | -17.48% | -1.49% |

### Rule Validation Checklist
- **Temporal Consistency Check**: PASSED (3/4 positive windows, 3/4 PF >= 1.05)
- **Drawdown Excessiveness Check**: PASSED (Max local drawdown rule)
- **Concentration Check**: PASSED (Top 1 ticker is NVDA contributing 22.30%)

## Ticker Concentration (Top 10 Contributors)

| Ticker | Net PnL ($) | % of Net PnL |
|---|---|---|
| NVDA | $21,578.61 | 22.30% |
| TSLA | $21,163.79 | 21.87% |
| NFLX | $15,371.71 | 15.88% |
| BAC | $15,092.55 | 15.59% |
| GOOG | $12,598.56 | 13.02% |
| CRWD | $9,103.56 | 9.41% |
| META | $7,275.59 | 7.52% |
| VRT | $7,135.32 | 7.37% |
| GE | $6,974.20 | 7.21% |
| NET | $6,212.11 | 6.42% |

## Sector Performance

| Sector | Net PnL ($) | % of Net PnL |
|---|---|---|
| XLF | $32,311.57 | 33.38% |
| XLC | $29,460.60 | 30.44% |
| XLK | $21,858.92 | 22.58% |
| XLI | $7,002.85 | 7.24% |
| UNKNOWN | $4,298.49 | 4.44% |
| XLE | $2,888.34 | 2.98% |
| XLRE | $2,366.71 | 2.45% |
| XLP | $1,323.05 | 1.37% |
| XLU | $120.13 | 0.12% |
| XLY | $-1,686.02 | -1.74% |
| XLB | $-3,158.91 | -3.26% |

## E25 Sizing Diagnostics

- **Mean Sizing Factor**: 0.7863
- **Minimum Sizing Factor**: 0.1300

| Sizing Reason | Trade Count | % of Total |
|---|---|---|
| 'comfort_zone' | 234 | 58.06% |
| 'v2_atlas_sweetspot:0.32' | 10 | 2.48% |
| 'v2_atlas_sweetspot:0.31' | 8 | 1.99% |
| 'v2_atlas_sweetspot:0.34' | 8 | 1.99% |
| 'v2_atlas_sweetspot:0.44' | 6 | 1.49% |
| 'v2_atlas_sweetspot:0.30' | 4 | 0.99% |
| 'v2_atlas_sweetspot:0.36' | 4 | 0.99% |
| 'v2_valley_penalty:0.47' | 3 | 0.74% |
| 'v2_atlas_sweetspot:0.38' | 3 | 0.74% |
| 'v2_valley_penalty:0.76' | 3 | 0.74% |
| 'v2_atlas_sweetspot:0.35' | 3 | 0.74% |
| 'v2_high_ext_penalty:0.49' | 3 | 0.74% |
| 'v2_atlas_sweetspot:0.47' | 3 | 0.74% |
| 'v2_high_ext_penalty:0.38' | 3 | 0.74% |
| 'v2_valley_penalty:0.31' | 3 | 0.74% |
| 'v2_valley_penalty:0.60' | 3 | 0.74% |
| 'v2_valley_penalty:0.37' | 3 | 0.74% |
| 'v2_extreme_ext_penalty:0.14' | 2 | 0.50% |
| 'v2_extreme_ext_penalty:0.25' | 2 | 0.50% |
| 'v2_valley_penalty:0.91' | 2 | 0.50% |
| 'v2_valley_penalty:0.34' | 2 | 0.50% |
| 'v2_valley_penalty:0.92' | 2 | 0.50% |
| 'v2_valley_penalty:0.49' | 2 | 0.50% |
| 'v2_extreme_ext_penalty:0.30' | 2 | 0.50% |
| 'v2_valley_penalty:0.70' | 2 | 0.50% |
| 'v2_high_ext_penalty:0.48' | 2 | 0.50% |
| 'v2_valley_penalty:0.94' | 2 | 0.50% |
| 'v2_high_ext_penalty:0.41' | 2 | 0.50% |
| 'v2_valley_penalty:0.50' | 2 | 0.50% |
| 'v2_valley_penalty:0.85' | 2 | 0.50% |
| 'v2_valley_penalty:0.39' | 2 | 0.50% |
| 'v2_high_ext_penalty:0.47' | 2 | 0.50% |
| 'v2_extreme_ext_penalty:0.19' | 2 | 0.50% |
| 'v2_valley_penalty:0.86' | 2 | 0.50% |
| 'v2_atlas_sweetspot:0.45' | 2 | 0.50% |
| 'v2_valley_penalty:0.87' | 2 | 0.50% |
| 'v2_valley_penalty:0.93' | 2 | 0.50% |
| 'v2_high_ext_penalty:0.39' | 2 | 0.50% |
| 'v2_valley_penalty:0.69' | 2 | 0.50% |
| 'v2_valley_penalty:0.79' | 2 | 0.50% |
| 'v2_valley_penalty:0.81' | 1 | 0.25% |
| 'v2_valley_penalty:0.57' | 1 | 0.25% |
| 'v2_high_ext_penalty:0.35' | 1 | 0.25% |
| 'v2_valley_penalty:0.46' | 1 | 0.25% |
| 'v2_valley_penalty:0.62' | 1 | 0.25% |
| 'v2_high_ext_penalty:0.44' | 1 | 0.25% |
| 'v2_valley_penalty:0.71' | 1 | 0.25% |
| 'v2_valley_penalty:0.63' | 1 | 0.25% |
| 'v2_valley_penalty:0.99' | 1 | 0.25% |
| 'v2_valley_penalty:0.36' | 1 | 0.25% |
| 'v2_atlas_sweetspot:0.46' | 1 | 0.25% |
| 'v2_valley_penalty:0.64' | 1 | 0.25% |
| 'v2_valley_penalty:0.88' | 1 | 0.25% |
| 'v2_atlas_sweetspot:0.39' | 1 | 0.25% |
| 'v2_valley_penalty:0.97' | 1 | 0.25% |
| 'v2_valley_penalty:0.65' | 1 | 0.25% |
| 'v2_valley_penalty:0.95' | 1 | 0.25% |
| 'v2_valley_penalty:0.53' | 1 | 0.25% |
| 'v2_high_ext_penalty:0.46' | 1 | 0.25% |
| 'v2_valley_penalty:0.68' | 1 | 0.25% |
| 'v2_valley_penalty:0.51' | 1 | 0.25% |
| 'v2_valley_penalty:0.42' | 1 | 0.25% |
| 'v2_valley_penalty:0.41' | 1 | 0.25% |
| 'v2_high_ext_penalty:0.42' | 1 | 0.25% |
| 'v2_valley_penalty:0.55' | 1 | 0.25% |
| 'v2_valley_penalty:0.72' | 1 | 0.25% |
| 'v2_valley_penalty:0.80' | 1 | 0.25% |
| 'v2_valley_penalty:0.78' | 1 | 0.25% |
| 'v2_valley_penalty:0.74' | 1 | 0.25% |
| 'v2_valley_penalty:0.38' | 1 | 0.25% |
| 'v2_valley_penalty:0.75' | 1 | 0.25% |
| 'v2_valley_penalty:0.30' | 1 | 0.25% |
| 'v2_extreme_ext_penalty:0.23' | 1 | 0.25% |
| 'v2_valley_penalty:0.90' | 1 | 0.25% |
| 'v2_high_ext_penalty:0.32' | 1 | 0.25% |
| 'v2_extreme_ext_penalty:0.13' | 1 | 0.25% |
| 'v2_atlas_sweetspot:0.48' | 1 | 0.25% |
| 'v2_valley_penalty:0.67' | 1 | 0.25% |
| 'v2_extreme_ext_penalty:0.28' | 1 | 0.25% |
| 'v2_valley_penalty:0.89' | 1 | 0.25% |
| 'v2_high_ext_penalty:0.30' | 1 | 0.25% |
| 'v2_valley_penalty:0.40' | 1 | 0.25% |
| 'v2_extreme_ext_penalty:0.26' | 1 | 0.25% |
| 'v2_valley_penalty:0.98' | 1 | 0.25% |
| 'v2_valley_penalty:0.59' | 1 | 0.25% |
| 'v2_high_ext_penalty:0.40' | 1 | 0.25% |
| 'v2_atlas_sweetspot:0.43' | 1 | 0.25% |
| 'v2_valley_penalty:0.66' | 1 | 0.25% |
| 'v2_extreme_ext_penalty:0.18' | 1 | 0.25% |
| 'v2_high_ext_penalty:0.36' | 1 | 0.25% |
| 'v2_valley_penalty:0.52' | 1 | 0.25% |
| 'v2_high_ext_penalty:0.31' | 1 | 0.25% |
| 'v2_valley_penalty:0.33' | 1 | 0.25% |
