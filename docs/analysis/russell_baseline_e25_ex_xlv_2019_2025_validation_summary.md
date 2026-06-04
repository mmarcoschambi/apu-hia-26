# Validation Report: russell_baseline_e25_ex_xlv_2019_2025

Analyzed on: 2026-06-04 09:38:02

## Temporal Window Performance

| Window | Start | End | Net PnL ($) | Profit Factor | Trades | Win Rate % | Max DD % | Avg Return % |
|---|---|---|---|---|---|---|---|---|
| 2019-2020 (Bull & Pandemic) | 2019-01-01 | 2020-12-31 | $42,301.32 | 2.61 | 33 | 60.61% | -12.67% | 3.65% |
| 2021-2022 (Bubble & Bear) | 2021-01-01 | 2022-12-31 | $9,676.77 | 1.21 | 27 | 44.44% | -11.81% | 0.76% |
| 2023-2024 (AI Expansion) | 2023-01-01 | 2024-12-31 | $36,455.89 | 1.34 | 52 | 46.15% | -16.26% | 0.75% |
| 2025 (Current Year) | 2025-01-01 | 2025-06-30 | $-11,328.55 | 0.64 | 9 | 33.33% | -12.23% | 0.28% |

### Rule Validation Checklist
- **Temporal Consistency Check**: PASSED (3/4 positive windows, 3/4 PF >= 1.05)
- **Drawdown Excessiveness Check**: PASSED (Max local drawdown rule)
- **Concentration Check**: WARNING (Top 1 ticker is PYPL contributing 39.88%)

## Ticker Concentration (Top 10 Contributors)

| Ticker | Net PnL ($) | % of Net PnL |
|---|---|---|
| PYPL | $30,752.75 | 39.88% |
| AMD | $17,474.76 | 22.66% |
| CRWD | $11,686.30 | 15.16% |
| AMAT | $11,500.83 | 14.92% |
| NVDA | $9,346.34 | 12.12% |
| META | $8,553.32 | 11.09% |
| NET | $8,142.52 | 10.56% |
| DDOG | $7,559.04 | 9.80% |
| ENPH | $7,189.98 | 9.32% |
| MSFT | $4,208.00 | 5.46% |

## Sector Performance

| Sector | Net PnL ($) | % of Net PnL |
|---|---|---|
| XLK | $76,238.00 | 98.88% |
| XLF | $18,045.83 | 23.40% |
| XLC | $8,553.32 | 11.09% |
| XLRE | $4,294.91 | 5.57% |
| XLI | $-4,549.43 | -5.90% |
| XLY | $-6,361.60 | -8.25% |
| XLE | $-19,115.60 | -24.79% |

## E25 Sizing Diagnostics

- **Mean Sizing Factor**: 0.9055
- **Minimum Sizing Factor**: 0.3000

| Sizing Reason | Trade Count | % of Total |
|---|---|---|
| 'comfort_zone' | 96 | 79.34% |
| 'v2_valley_penalty:0.33' | 2 | 1.65% |
| 'v2_valley_penalty:0.36' | 1 | 0.83% |
| 'v2_valley_penalty:0.69' | 1 | 0.83% |
| 'v2_high_ext_penalty:0.36' | 1 | 0.83% |
| 'v2_extreme_ext_penalty:0.30' | 1 | 0.83% |
| 'v2_valley_penalty:0.98' | 1 | 0.83% |
| 'v2_valley_penalty:0.87' | 1 | 0.83% |
| 'v2_valley_penalty:0.82' | 1 | 0.83% |
| 'v2_valley_penalty:0.63' | 1 | 0.83% |
| 'v2_atlas_sweetspot:0.33' | 1 | 0.83% |
| 'v2_valley_penalty:0.65' | 1 | 0.83% |
| 'v2_valley_penalty:0.83' | 1 | 0.83% |
| 'v2_atlas_sweetspot:0.47' | 1 | 0.83% |
| 'v2_valley_penalty:0.52' | 1 | 0.83% |
| 'v2_valley_penalty:0.81' | 1 | 0.83% |
| 'v2_high_ext_penalty:0.39' | 1 | 0.83% |
| 'v2_atlas_sweetspot:0.35' | 1 | 0.83% |
| 'v2_valley_penalty:0.70' | 1 | 0.83% |
| 'v2_high_ext_penalty:0.47' | 1 | 0.83% |
| 'v2_valley_penalty:0.54' | 1 | 0.83% |
| 'v2_atlas_sweetspot:0.49' | 1 | 0.83% |
| 'v2_atlas_sweetspot:0.31' | 1 | 0.83% |
| 'v2_valley_penalty:0.61' | 1 | 0.83% |
| 'v2_valley_penalty:0.42' | 1 | 0.83% |
