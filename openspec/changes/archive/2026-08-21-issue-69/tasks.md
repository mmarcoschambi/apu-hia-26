# Tasks: feat(microstructure): Cross-validation engine — Microstructure vs Time hybrid pipeline

## Slice 1 (applied)

- [x] 1.1 Red Test (TDD) — `tests/test_microstructure/test_data_pipeline.py` (8 tests) y
  `tests/test_microstructure/test_volume_bars.py` (17 tests) escritos ANTES del código de
  producción. RED observado: ambos archivos fallan con
  `ModuleNotFoundError: No module named 'src.microstructure'`.
- [x] 1.2 Implementation — `src/microstructure/__init__.py`,
  `src/microstructure/data_pipeline.py` (DuckDB lazy + RTH [09:30,16:00) NY +
  salida Polars), `src/microstructure/volume_bars.py` (volume bars con política
  de barra parcial conservada, Bollinger ddof=0, Signal A estricta sin filtro
  de volumen). Dependencias: `polars>=1.0` agregada a pyproject.toml y
  requirements.txt (duckdb ya existía; instalada en WSL). GREEN observado:
  25/25 passed (`python3 -m pytest tests/test_microstructure/ -q` en WSL).
  Commits: 8e2724f, 1b79b00.
- [x] 1.3 QA Verification — cerrada en el slice final 3B con la suite completa
  en WSL sobre HEAD 538ede4: 578 passed / 4 failed / 5 skipped. Los fallos:
  (a) test_cache_switch sqlite, test_fast_filters sqlite y test_quant_gate
  metrics son el ruido preexistente documentado desde los slices 1-3A;
  (b) test_universe_sync::test_scanner_stable_flag falló por timeout de
  subprocess bajo carga y PASÓ en ejecución aislada sobre esta rama; además,
  la suite completa del padre limpio 57bc323 (worktree desmontable) muestra
  la MISMA clase de ruido (sqlite x2 + quant_gate + yfinance network) y otro
  test HERMANO del mismo archivo (test_universe_stats_db_count) fallando allí
  -> ruido ambiental de suite completa, cero regresiones atribuibles al
  cambio. Aislamiento de baseline verificado por construcción:
  `git diff --name-only 93b4867..HEAD` (93b4867 = padre del primer commit del
  cambio) contiene SOLO src/microstructure/**, tests/test_microstructure/**,
  pyproject.toml y requirements.txt -> la estrategia existente no fue tocada
  (el backtest de baseline no se re-corre aquí: data/ es local-only).
  Criterios de aceptación del proposal recorridos uno a uno: 12/12
  evaluados (10 met, 1 parcialmente verificable aquí - límite de RAM de la
  ingesta DuckDB-, 1 verificado por construcción - baseline Return/MDD-).

## Slices siguientes (pendientes)

- [x] 2.x Pipeline B: time bars + Vol Buzz Z-Score + AVWAP + Signal B
  (`time_bars.py`) y feature engine (`feature_engine.py`). Strict TDD:
  RED observado (ModuleNotFoundError en ambos archivos de test antes del
  código). GREEN: 61/61 en tests/test_microstructure/ (36 nuevos: 27 de
  time_bars, 9 de feature_engine; 25 de slice 1 intactos). Ruff limpio.
  Regresión suite completa WSL: 490 passed / 3 failed / 5 skipped — los 3
  fallos (test_cache_switch sqlite, test_fast_filters sqlite,
  test_quant_gate metrics) verificados IDÉNTICOS en HEAD 1b79b00 sin estos
  cambios vía worktree desmontable -> cero regresiones del slice. Decisiones
  documentadas: grilla anclada al reloj con etiqueta left y borde inclusivo;
  vela parcial final conservada y buckets vacíos ralos; Vol Buzz con días
  previos únicamente (sin fuga temporal), std poblacional ddof=0, historia
  insuficiente -> NaN no-señal, std cero -> z=0.0; AVWAP anclado al primer
  bucket de cada día con precio típico (H+L+C)/3 y fallback por volumen
  cero; Signal B reutiliza compute_bollinger_bands del slice 1 con
  comparaciones estrictas; features as-of backward contra la última barra
  COMPLETADA (PIT); ADR = media móvil de rangos diarios previos; contexto
  opcional por join as-of con columna 'timestamp' (interfaz para RS /
  health_score del slice 3 sin tocar signal_engine ni market_health).
  Commits: c8c9a56, ceceb48.
- [x] 3a.1 Etiquetado PIT + ensamblado + contexto (`hybrid_model.py`):
  ``compute_atr_series`` (TR canónico del sistema con TR_0 = high-low
  documentado, primer valor válido en índice period-1);
  ``label_breakout_instants`` (R = stop_atr_mult * ATR con default 0.5 según
  propuesta sección 4; TP ESTRICTO ">2R", SL por toque "1R"; empate SL+TP en
  la misma ventana -> 0 conservador; sin resolución en N ventanas -> 0; ATR
  indefinido / R degenerado / sin barra de entrada -> etiqueta nula;
  invarianza al truncamiento y a mutaciones fuera de la ventana ATR como
  anti-fuga); ``assemble_dataset`` (contrato de columnas determinista,
  labels por join exacto con validación de duplicados, label nula uniforme);
  ``build_context_frame`` (adaptadores FINOS que LLAMAN compute_tier2_metrics
  y calculate_health_score_pit SIN modificarlos, recorte SOLO de días
  estrictamente previos al día del instante - PIT -, import perezoso para no
  arrastrar la cadena de screeners, degradación elegante a NULL).
- [x] 3a.2 Walk-forward LightGBM + inferencia: ``train_walk_forward``
  (K folds => K+1 chunks contiguos ordenados por timestamp: todo train <
  todo test por construcción; ventana EXPANSIVA; mínimos por fold
  constantes nombradas; scale_pos_weight automático n_neg/n_pos por fold
  documentado o valor explícito; métricas precision/recall/AUC por fold con
  AUC None si el fold tiene una sola clase; modelo final sobre TODO el
  dataset efectivo); ``predict_probability`` en [0,1] seleccionando solo las
  feature_columns; ``should_deploy_capital`` gate estricto (> 0.75 default)
  con validación de rango; ``save_model``/``load_model`` con saver NATIVO de
  LightGBM + sidecar JSON del contrato de columnas bajo
  outputs/microstructure/ (gitignored vía outputs/*).
- [x] 3a.3 Tests Strict TDD: RED observado ANTES del código
  (ModuleNotFoundError en collection). 40 tests nuevos en
  tests/test_microstructure/test_hybrid_model.py: escenarios de etiqueta
  calculados a mano (win 2R / loss 1R / empate / nunca resuelve / orden /
  bordes estrictos), anti-leakage por truncamiento y mutación, orden y
  expansión de folds, scale_pos_weight auto = 18/6, errores de dataset chico,
  bounds de probabilidad, gate true/false, round-trip save/load idéntico.
  GREEN: 101/101 en tests/test_microstructure/ (61 previos intactos).
  Ruff limpio. lightgbm ya figuraba en pyproject.toml y requirements.txt;
  import verificado en WSL (4.6.0, sin instalación extra). Regresión suite
  completa WSL: 530 passed / 3 failed / 5 skipped — los 3 fallos
  (test_cache_switch sqlite, test_fast_filters sqlite, test_quant_gate
  metrics) reproducen IDÉNTICOS en HEAD padre ceceb48 vía worktree
  desmontable -> cero regresiones del slice. Commit: 57bc323.
- [x] 3b.x Kernels vectorizados + sweep Optuna V/T/Z + QA final (Strict TDD):
  RED observado ANTES del código (ModuleNotFoundError en collection de ambos
  archivos de test). ``numba_kernels.py``: kernel @njit(cache=True)
  ``simulate_trades_kernel`` con TODO el bucle de gestión compilado
  (entrada al close de la barra con señal, R = stop_atr_mult * ATR con
  default 0.5, SL por toque, TP estricto > +2R con venta parcial de
  tp_exit_fraction default 0.33, resto con TRAILING STOP determinista =
  máx(SL, máximo high previo - trail_r_mult*R), empate SL+TP en la misma
  barra -> stop primero, horizonte -> salida al close; una posición por vez,
  señales solapadas ignoradas; frontera documentada: prep vectorizada fuera,
  loops SOLO dentro del njit, nada de pandas/polars cruza la frontera);
  wrapper ``simulate_trades`` valida/coerceciona a float64/int64 y convierte
  la máscara con flatnonzero (sin bucles Python). Salidas: matriz de trades
  (n,7) + curva de equity realizada en R por barra.
  ``sweep.py``: espacio exacto V∈{10k,25k,50k}, T∈{1m,3m,5m},
  Z∈[1.0,3.0] paso 0.25 (constantes nombradas); objetivo Sortino por
  operación en R MENOS penalización CUADRÁTICA del exceso de MDD sobre el
  umbral 5R (fórmula documentada en el módulo); TPESampler(seed=42) +
  MedianPruner + storage in-memory + MAXIMIZE; ``evaluate_configuration``
  cablea el pipeline REAL (volume bars -> Signal A trasladada as-of backward
  a la grilla de time bars, unión A|B, ATR canónico, kernel Numba).
  Dependencias: numba 0.56.4 y optuna 4.6.0 ya figuraban en pyproject.toml y
  requirements.txt; import verificado en WSL sin instalación extra.
  GREEN: 150/150 en tests/test_microstructure/ (101 previos intactos); 49
  tests nuevos (27 kernels: win/loss/tie contra matemática a mano, fracción
  TP variable, horizontes, no-trade plano, equity consistente, no-solape,
  ATR inválido/degenerado descartado, coerción dtypes, bordes chicos,
  evidencia de compilación via Dispatcher/signatures, defaults pinned;
  22 sweep: objetivo a mano normal/penalización cuadrática/cap sin downside/
  errores de contrato, wiring end-to-end con señales reales, bounds de TODO
  trial, dirección/pruner/sampler/seed/determinismo, ticks vacíos,
  validaciones). Ruff limpio. Suite completa WSL: 578 passed / 4 failed /
  5 skipped - los 4 fallos verificados como ruido preexistente/ambiental
  contra el padre limpio 57bc323 vía worktree desmontable (ver 1.3).
  Commits: 82feb1b (kernels), 538ede4 (sweep).
