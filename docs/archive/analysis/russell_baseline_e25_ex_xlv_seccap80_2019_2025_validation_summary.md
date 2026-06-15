# Validation Report: russell_baseline_e25_ex_xlv_seccap80_2019_2025

Analyzed on: 2026-06-04 12:58:40

## Temporal Window Performance

| Window | Start | End | Net PnL ($) | Profit Factor | Trades | Win Rate % | Max DD % | Avg Return % |
|---|---|---|---|---|---|---|---|---|
| 2019-2020 (Bull & Pandemic) | 2019-01-01 | 2020-12-31 | $40,904.53 | 1.39 | 111 | 54.05% | -21.37% | 0.89% |
| 2021-2022 (Bubble & Bear) | 2021-01-01 | 2022-12-31 | $-12,249.1 | 0.9 | 91 | 46.15% | -26.41% | 0.06% |
| 2023-2024 (AI Expansion) | 2023-01-01 | 2024-12-31 | $-5,219.92 | 0.96 | 134 | 51.49% | -35.64% | 1.02% |
| 2025 (Current Year) | 2025-01-01 | 2025-06-30 | $339.46 | 1.02 | 20 | 45.0% | -13.59% | 2.22% |

### Rule Validation Checklist
- **Temporal Consistency Check**: FAILED (2/4 positive windows, 1/4 PF >= 1.05)
- **Drawdown Excessiveness Check**: FAILED (Max local drawdown rule)
- **Concentration Check**: WARNING (Top 1 ticker is NVDA contributing 105.01%)

## Ticker Concentration (Top 10 Contributors)

| Ticker | Net PnL ($) | % of Net PnL |
|---|---|---|
| NVDA | $24,966.11 | 105.01% |
| BAC | $15,412.37 | 64.83% |
| NET | $13,394.27 | 56.34% |
| PYPL | $10,375.21 | 43.64% |
| OKTA | $10,081.02 | 42.40% |
| SOFI | $9,986.75 | 42.01% |
| AMD | $9,705.08 | 40.82% |
| CMG | $9,672.97 | 40.69% |
| TSLA | $8,859.08 | 37.26% |
| LRCX | $7,706.95 | 32.42% |

## Sector Performance

| Sector | Net PnL ($) | % of Net PnL |
|---|---|---|
| XLK | $39,899.04 | 167.82% |
| XLF | $37,506.19 | 157.75% |
| XLY | $12,656.35 | 53.23% |
| XLI | $4,451.40 | 18.72% |
| XLU | $-420.55 | -1.77% |
| XLE | $-6,553.07 | -27.56% |
| XLP | $-10,405.57 | -43.77% |
| XLB | $-15,423.39 | -64.87% |
| XLC | $-17,526.21 | -73.72% |
| UNKNOWN | $-20,409.22 | -85.84% |

## E25 Sizing Diagnostics

- **Mean Sizing Factor**: 0.5891
- **Minimum Sizing Factor**: 0.1200

| Sizing Reason | Trade Count | % of Total |
|---|---|---|
| 'comfort_zone' | 103 | 28.93% |
| 'v2_atlas_sweetspot:0.31' | 13 | 3.65% |
| 'v2_atlas_sweetspot:0.33' | 12 | 3.37% |
| 'v2_atlas_sweetspot:0.30' | 10 | 2.81% |
| 'v2_atlas_sweetspot:0.35' | 9 | 2.53% |
| 'v2_atlas_sweetspot:0.32' | 9 | 2.53% |
| 'v2_atlas_sweetspot:0.36' | 9 | 2.53% |
| 'v2_atlas_sweetspot:0.37' | 6 | 1.69% |
| 'v2_atlas_sweetspot:0.34' | 5 | 1.40% |
| 'v2_atlas_sweetspot:0.47' | 5 | 1.40% |
| 'v2_atlas_sweetspot:0.39' | 5 | 1.40% |
| 'v2_high_ext_penalty:0.48' | 4 | 1.12% |
| 'v2_valley_penalty:0.42' | 4 | 1.12% |
| 'v2_atlas_sweetspot:0.41' | 4 | 1.12% |
| 'v2_atlas_sweetspot:0.44' | 4 | 1.12% |
| 'v2_atlas_sweetspot:0.38' | 4 | 1.12% |
| 'v2_valley_penalty:0.32' | 4 | 1.12% |
| 'v2_valley_penalty:0.39' | 4 | 1.12% |
| 'v2_valley_penalty:0.30' | 4 | 1.12% |
| 'v2_high_ext_penalty:0.44' | 3 | 0.84% |
| 'v2_atlas_sweetspot:0.42' | 3 | 0.84% |
| 'v2_high_ext_penalty:0.31' | 3 | 0.84% |
| 'v2_atlas_sweetspot:0.48' | 3 | 0.84% |
| 'v2_atlas_sweetspot:0.46' | 3 | 0.84% |
| 'v2_high_ext_penalty:0.43' | 3 | 0.84% |
| 'v2_valley_penalty:0.92' | 3 | 0.84% |
| 'v2_extreme_ext_penalty:0.24' | 3 | 0.84% |
| 'v2_high_ext_penalty:0.38' | 3 | 0.84% |
| 'v2_atlas_sweetspot:0.43' | 3 | 0.84% |
| 'v2_high_ext_penalty:0.50' | 3 | 0.84% |
| 'v2_extreme_ext_penalty:0.21' | 3 | 0.84% |
| 'v2_high_ext_penalty:0.47' | 3 | 0.84% |
| 'v2_high_ext_penalty:0.34' | 3 | 0.84% |
| 'v2_atlas_sweetspot:0.49' | 2 | 0.56% |
| 'v2_extreme_ext_penalty:0.20' | 2 | 0.56% |
| 'v2_valley_penalty:0.95' | 2 | 0.56% |
| 'v2_valley_penalty:0.52' | 2 | 0.56% |
| 'v2_valley_penalty:0.94' | 2 | 0.56% |
| 'v2_high_ext_penalty:0.35' | 2 | 0.56% |
| 'v2_valley_penalty:0.50' | 2 | 0.56% |
| 'v2_high_ext_penalty:0.45' | 2 | 0.56% |
| 'v2_valley_penalty:0.76' | 2 | 0.56% |
| 'v2_valley_penalty:0.49' | 2 | 0.56% |
| 'v2_valley_penalty:0.44' | 2 | 0.56% |
| 'v2_high_ext_penalty:0.46' | 2 | 0.56% |
| 'v2_valley_penalty:0.47' | 2 | 0.56% |
| 'v2_valley_penalty:0.36' | 2 | 0.56% |
| 'v2_high_ext_penalty:0.36' | 2 | 0.56% |
| 'v2_valley_penalty:0.48' | 2 | 0.56% |
| 'v2_valley_penalty:0.37' | 2 | 0.56% |
| 'v2_valley_penalty:0.57' | 2 | 0.56% |
| 'v2_valley_penalty:0.71' | 2 | 0.56% |
| 'v2_high_ext_penalty:0.40' | 2 | 0.56% |
| 'v2_high_ext_penalty:0.39' | 2 | 0.56% |
| 'v2_valley_penalty:0.64' | 2 | 0.56% |
| 'v2_high_ext_penalty:0.37' | 2 | 0.56% |
| 'v2_valley_penalty:0.91' | 2 | 0.56% |
| 'v2_high_ext_penalty:0.42' | 2 | 0.56% |
| 'v2_valley_penalty:0.55' | 2 | 0.56% |
| 'v2_atlas_sweetspot:0.40' | 2 | 0.56% |
| 'v2_valley_penalty:0.68' | 2 | 0.56% |
| 'v2_valley_penalty:0.31' | 2 | 0.56% |
| 'v2_extreme_ext_penalty:0.25' | 2 | 0.56% |
| 'extreme_adr_exception' | 2 | 0.56% |
| 'v2_valley_penalty:0.63' | 2 | 0.56% |
| 'v2_valley_penalty:0.33' | 1 | 0.28% |
| 'v2_valley_penalty:0.61' | 1 | 0.28% |
| 'v2_valley_penalty:0.73' | 1 | 0.28% |
| 'v2_valley_penalty:0.62' | 1 | 0.28% |
| 'v2_valley_penalty:0.81' | 1 | 0.28% |
| 'v2_valley_penalty:0.98' | 1 | 0.28% |
| 'v2_extreme_ext_penalty:0.16' | 1 | 0.28% |
| 'v2_extreme_ext_penalty:0.26' | 1 | 0.28% |
| 'v2_valley_penalty:0.75' | 1 | 0.28% |
| 'v2_high_ext_penalty:0.41' | 1 | 0.28% |
| 'v2_valley_penalty:0.88' | 1 | 0.28% |
| 'v2_high_ext_penalty:0.30' | 1 | 0.28% |
| 'v2_valley_penalty:0.85' | 1 | 0.28% |
| 'v2_extreme_ext_penalty:0.23' | 1 | 0.28% |
| 'v2_valley_penalty:0.78' | 1 | 0.28% |
| 'v2_high_ext_penalty:0.49' | 1 | 0.28% |
| 'v2_valley_penalty:0.69' | 1 | 0.28% |
| 'v2_valley_penalty:0.35' | 1 | 0.28% |
| 'v2_valley_penalty:0.53' | 1 | 0.28% |
| 'v2_atlas_sweetspot:0.45' | 1 | 0.28% |
| 'v2_extreme_ext_penalty:0.29' | 1 | 0.28% |
| 'v2_high_ext_penalty:0.32' | 1 | 0.28% |
| 'v2_valley_penalty:0.89' | 1 | 0.28% |
| 'v2_valley_penalty:0.41' | 1 | 0.28% |
| 'v2_extreme_ext_penalty:0.12' | 1 | 0.28% |
| 'v2_extreme_ext_penalty:0.13' | 1 | 0.28% |
| 'v2_extreme_ext_penalty:0.14' | 1 | 0.28% |
| 'v2_valley_penalty:0.54' | 1 | 0.28% |
| 'v2_extreme_ext_penalty:0.22' | 1 | 0.28% |
| 'v2_valley_penalty:0.38' | 1 | 0.28% |
| 'v2_extreme_ext_penalty:0.18' | 1 | 0.28% |
| 'v2_valley_penalty:0.83' | 1 | 0.28% |
