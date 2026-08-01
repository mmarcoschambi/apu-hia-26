# S4 OOS Validation — 2026-08-01 (Bloque 2/3)

Evidencia de la validación Out-of-Sample de los 6 sobrevivientes del full run S4
(`momentum_s4_prod`, 1000 trials, IS 2019-2023).

## Veredicto
**Los 6 candidatos FALLAN la validación OOS (reserva 2024-2025). 0 pasan al Bloque 3.
No se promueve nada a producción.**

| trial | score IS | cost | PurgedCV degrad % | gate | OOS posiciones | DSR | PBO_mc | risk_of_loss |
|------:|---------:|------|------------------:|:----:|---------------:|----:|-------:|-------------:|
| 722 | 1.9992 | ROBUSTO | 40.94 | False | 30 | 0.0054 | 99.46% | 34.9% |
| 845 | 1.8310 | ROBUSTO | 100.00 | False | 34 | 0.0022 | 99.78% | 44.2% |
| 293 | 1.8192 | MODERADO | 100.00 | False | 35 | 0.0019 | 99.81% | 51.0% |
| 663 | 1.8166 | MODERADO | 100.00 | False | 31 | 0.0030 | 99.70% | 38.6% |
| 64  | 1.7442 | MODERADO | 190.36 | False | 28 | 0.0019 | 99.81% | 43.1% |
| 763 | 1.7379 | MODERADO | 304.21 | False | 33 | 0.0017 | 99.83% | 47.1% |

## Contenido
- `oos_verdict_6_survivors_CONSOLIDATED.json` — veredicto consolidado (MC + bootstrap +
  DSR/PBO + resumen Purged CV por candidato).
- `results_momentum_s4_prod_20260801_172540.json` — full run IS (gates de aceptación: 6/10 pasaron).
- `../purged_cv/purged_cv_report_*_s4trial*.json` — recibos físicos de Purged CV por candidato
  (consumibles por `ParamGate.assert_params_cleared`).
- `../s4_candidates/s4_candidate_trial*_params.json` — params (engine kwargs) de cada candidato
  (son el `params_json_source` de los recibos).

## Evidencia local (NO versionable, `*.db` gitignored)
- `optuna_s4_full.db` (raíz, 1.8MB) — estudio Optuna `momentum_s4_prod_pilot` (80) +
  `momentum_s4_prod` (920). Es la fuente bruta del full run; se conserva local para auditoría.

## Protocolo de reproducción
`scratch/validate_s4_oomc.py` (runner del Bloque 2). Uso: `--only <trial_id>` o todos.
- Purged CV: `src/validation/purged_walk_forward.py` (folds OOS 2024/2025, train 2019, purge 10d, embargo 5d).
- MC/bootstrap/DSR: helpers de `scratch/run_mc_combo_neutral.py` (mismo protocolo que `combo_neutral`),
  DSR deflactado por N=1000 trials del search.

## Bloque 1 (hallazgo previo)
`degradation_gate` de `s4_gates.py` está inerte (val_metrics=None en `apply_gates_to_candidates`);
documentado como **redundante** con el Purged CV. Ver DECISIONS.md 2026-08-01.
