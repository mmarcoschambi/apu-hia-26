
======================================================================
DECISION GATE — 2026-04-14 18:40
======================================================================

[GO ] combo_pure_momentum
  Baseline:     OK
  Walk-Fwd:     sharpe_mean=0.74  sharpe_min=0.45  pf_consistent=True  verdict=GO
  Costos:       breakeven=200bps  ROBUSTO
  RAZON:        Todos los checks pasados

[NOG] combo_stage2_breakout
  Baseline:     OK
  Walk-Fwd:     sharpe_mean=0.13  sharpe_min=-0.93  pf_consistent=False  verdict=NO-GO
  Costos:       breakeven=200bps  ROBUSTO
  AVISO:        Fold con Sharpe negativo (-0.93) en WF — 2022 bear market
  RAZON:        Falla en: wf_verdict_ok, wf_sharpe_mean_ok, wf_pf_mean_ok

[NOG] combo_universal_any
  Baseline:     OK
  Walk-Fwd:     sharpe_mean=0.25  sharpe_min=-0.14  pf_consistent=False  verdict=NO-GO
  Costos:       breakeven=200bps  ROBUSTO
  AVISO:        Fold con Sharpe negativo (-0.14) en WF — 2022 bear market
  RAZON:        Falla en: wf_verdict_ok, wf_pf_mean_ok

[GO ] combo_pullback_entry
  Baseline:     OK
  Walk-Fwd:     sharpe_mean=1.36  sharpe_min=1.30  pf_consistent=True  verdict=GO
  Costos:       breakeven=200bps  ROBUSTO
  AVISO:        PBO=82% — alto riesgo overfitting
  RAZON:        Todos los checks pasados

[GO ] combo_aggressive_momentum
  Baseline:     OK
  Walk-Fwd:     sharpe_mean=0.90  sharpe_min=0.10  pf_consistent=False  verdict=GO
  Costos:       breakeven=200bps  ROBUSTO
  RAZON:        Todos los checks pasados

[PEN] combo_ideal_setup
  Baseline:     FALLA
  Walk-Fwd:     PENDIENTE
  Costos:       PENDIENTE
  AVISO:        Solo 18 trades IS — muestra insuficiente
  AVISO:        PBO=79% — alto riesgo overfitting
  AVISO:        Walk-forward NO ejecutado — correr walk_forward_combos.py primero
  AVISO:        Analisis de costos NO ejecutado — correr cost_sensitivity.py primero
  RAZON:        Faltan: wf_verdict_ok, wf_sharpe_mean_ok, wf_positive_folds, wf_pf_mean_ok, wf_trades_ok, cost_ok

======================================================================
RESUMEN EJECUTIVO
======================================================================
  GO      (3):  combo_pure_momentum, combo_pullback_entry, combo_aggressive_momentum
  NO-GO   (2):  combo_stage2_breakout, combo_universal_any
  PENDING (1):  combo_ideal_setup
