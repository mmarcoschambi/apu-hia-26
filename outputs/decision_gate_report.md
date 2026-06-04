
======================================================================
DECISION GATE — 2026-05-08 10:03
======================================================================

[NOG] combo_pure_momentum
  Baseline:     OK
  Walk-Fwd:     sharpe_mean=0.47  sharpe_min=0.10  pf_consistent=False  verdict=NO-GO
  Costos:       breakeven=200bps  ROBUSTO
  RAZON:        Falla en: wf_verdict_ok

[NOG] combo_stage2_breakout
  Baseline:     OK
  Walk-Fwd:     sharpe_mean=0.29  sharpe_min=-0.89  pf_consistent=False  verdict=NO-GO
  Costos:       breakeven=200bps  ROBUSTO
  AVISO:        Fold con Sharpe negativo (-0.89) en WF — 2022 bear market
  RAZON:        Falla en: wf_verdict_ok

[NOG] combo_universal_any
  Baseline:     OK
  Walk-Fwd:     sharpe_mean=-0.15  sharpe_min=-0.88  pf_consistent=False  verdict=NO-GO
  Costos:       breakeven=80bps  ROBUSTO
  AVISO:        Fold con Sharpe negativo (-0.88) en WF — 2022 bear market
  RAZON:        Falla en: wf_verdict_ok, wf_sharpe_mean_ok, wf_positive_folds, wf_pf_mean_ok

[NOG] combo_pullback_entry
  Baseline:     OK
  Walk-Fwd:     sharpe_mean=0.97  sharpe_min=0.82  pf_consistent=False  verdict=NO-GO
  Costos:       breakeven=200bps  ROBUSTO (ANOMALIA)
  AVISO:        PBO=82% — alto riesgo overfitting
  AVISO:        Costos: Sharpe mejora >0.20 al subir costos entre escenarios contiguos (revisar aplicacion de fees).
  RAZON:        Falla en: wf_verdict_ok, cost_ok

[NOG] combo_aggressive_momentum
  Baseline:     OK
  Walk-Fwd:     sharpe_mean=0.91  sharpe_min=-0.04  pf_consistent=False  verdict=NO-GO
  Costos:       breakeven=200bps  ROBUSTO
  AVISO:        Fold con Sharpe negativo (-0.04) en WF — 2022 bear market
  RAZON:        Falla en: wf_verdict_ok

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
  GO      (0):  ninguno
  NO-GO   (5):  combo_pure_momentum, combo_stage2_breakout, combo_universal_any, combo_pullback_entry, combo_aggressive_momentum
  PENDING (1):  combo_ideal_setup
