# Shadow Sandbox Summary

Generated: 2026-06-05 07:23
Source: logs/cron_finviz_monitor.log

## Global Metrics

| Metric | Value |
|--------|-------|
| Days with runs | 8 |
| Days with setups | 2 |
| Total raw setups | 2 |
| XLV filtered | 0 |
| Shadow candidates | 2 |
| Cache warnings (sma20) | 1 |

## Per-Day Breakdown

| Date | Setups | XLV Filtered | Shadow Candidates | Mode | No Auto Entry |
|------|--------|--------------|-------------------|------|---------------|
| 2026-05-08 | 0 | 0 | 0 | PRODUCTION | False |
| 2026-05-11 | 0 | 0 | 0 | PRODUCTION | False |
| 2026-05-12 | 0 | 0 | 0 | PRODUCTION | False |
| 2026-05-13 | 0 | 0 | 0 | PRODUCTION | True |
| 2026-05-14 | 0 | 0 | 0 | PRODUCTION | True |
| 2026-05-15 | 0 | 0 | 0 | PRODUCTION | True |
| 2026-05-18 | 1 | 0 | 1 | PRODUCTION | True |
| 2026-05-19 | 1 | 0 | 1 | PRODUCTION | True |

## Legend
- **raw_setup**: senal detectada en el log, sin filtrar
- **shadow_allowed**: pasa el filtro ex-XLV, candidato valido
- **blocked_by_sector**: ticker en sector XLV (healthcare), excluido
- **missing_data**: ticker no encontrado en SECTOR_MAP
