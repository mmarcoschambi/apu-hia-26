# Apply Progress: issue-67 — Narrative Telegram pre-market brief

## Status
Batch 1 (tasks 1.1–1.3, narrative rewrite) complete. Batch 2 (tasks 1.4–1.6,
mini-línea de aprendizaje 'Objetivo' por candidato) complete.
Both batches executed Strict TDD cycles (RED → GREEN → QA).
All 6 tasks done; pending only orchestrator-side Telegram DEMO preview send.

## Work Unit Evidence

### Batch 1 — Narrative brief rewrite (tasks 1.1–1.3)

| Evidence | Required value |
|---|---|
| Focused test command and exact result | `.venv\Scripts\python.exe -m pytest tests/test_telegram_brief.py -v` → **21 passed in 2.09s** |
| Runtime harness command/scenario and exact result | Rendered full brief via `build_telegram_brief(make_snapshot())` with mocked `fetch_gamma_data`/`_build_hot_sectors`/`get_ticker_sector_mapping`; visual output verified against proposal reference HTML (8 sections, real emojis, narrative states). Full suite as integration boundary: **450 passed / 5 skipped / 3 pre-existing failures** (see below). |
| Rollback boundary | Revert commit restores `src/utils/terminal_gui.py`; deleting `tests/test_telegram_brief.py` removes only the new tests. No other files touched by the feature. |

### Batch 2 — Objetivo learning line (tasks 1.4–1.6)

| Evidence | Required value |
|---|---|
| Focused test command and exact result | `.venv\Scripts\python.exe -m pytest tests/test_telegram_brief.py -v` → RED **4 failed, 22 passed in 3.74s** → GREEN **26 passed in 2.51s** |
| Runtime harness command/scenario and exact result | `.venv\Scripts\python.exe scratch\preview_brief_67.py` → offline render to `scratch/brief_preview.html`: 2490 chars, 3 botones, zero placeholders. Visual check: JPM (Trigger listo) y BAC (Esperando ruptura) muestran `→ 🎯 <b>Objetivo:</b> Breakout de 210.40/45.80. Si cruza con RVOL &gt; 1.20, la señal es de alta convicción.` (byte-match del ejemplo aprobado); PYPL (Consolidar) conserva `→ Acción sugerida:` sin línea Objetivo. Envío a Telegram DEMO delegado al orquestador. |
| Rollback boundary | Revertir este commit elimina solo: constante `HIGH_CONVICTION_RVOL`, helper `_linea_objetivo`, condicional de última línea del bloque candidato y los 5 tests nuevos. El brief narrativo del batch 1 queda intacto. |

## TDD Cycle Evidence

### Batch 1

| Task | RED (test first) | GREEN | REFACTOR |
|---|---|---|---|
| 1.1 Red Test | `pytest tests/test_telegram_brief.py -v` → **16 failed, 4 passed** (placeholders `[U+...]`/`[OK]`/`[WARN]` detected, all narrative sections missing, states not in natural language) | — | Hermetic fix: patched `_build_hot_sectors` in negative-gamma variant (was leaking to real sector analysis) |
| 1.2 Implementation | Mini-RED added mid-task: `test_candidatos_excluye_sectores_no_calientes` → **1 failed** (PBF leaked into Candidatos) | **21 passed** after restricting grouping to hot sectors only | Ruff fixes on untouched legacy lines (I001 import order, F541 dead f-prefixes, E722 bare excepts → typed exceptions) |
| 1.3 QA Verification | — | Full suite `pytest tests/` → **450 passed, 5 skipped, 3 failed**; ruff → **All checks passed** (exit 0) | Pre-existing failure proof: stashed change, same 3 tests fail on HEAD (`sqlite3.OperationalError` ×2, quant-gate assertion ×1; gitignored `data/` DBs absent in worktree). No test imports `terminal_gui`. |

### Batch 2

| Task | RED (test first) | GREEN | REFACTOR |
|---|---|---|---|
| 1.4 Red Test | `pytest tests/test_telegram_brief.py -v` → **4 failed, 22 passed**: JPM/BAC sin `'→ 🎯 <b>Objetivo:</b>'`, aún con `'Acción sugerida:'`; `ImportError: cannot import name 'HIGH_CONVICTION_RVOL'`. El test guard de PYPL pasa en RED por diseño (caracteriza la regla 2 contra regresiones) | — | Limpieza: removido comentario `noqa: PLC0415` innecesario (regla fuera del select de Ruff del proyecto) |
| 1.5 Implementation | — | **26 passed** tras: constante `HIGH_CONVICTION_RVOL = 1.20` junto a los umbrales técnicos, helper `_linea_objetivo(nivel: float) -> str`, y reemplazo condicional de la última línea del bloque candidato cuando el estado es Trigger listo / Esperando ruptura | Ninguno adicional requerido |
| 1.6 QA Verification | — | Enfocado **26/26 green**; ruff → **All checks passed!** en ambos archivos (`src/utils/terminal_gui.py`, `tests/test_telegram_brief.py`) | Render offline verificado visualmente |

## Completed Tasks
- [x] 1.1 Red Test (TDD): `tests/test_telegram_brief.py` created with 20 tests covering every acceptance criterion + the 8 sections (structure, content, placeholder regex `\[(U\+|OK|WARN|BOLT)[^\]]*\]`, natural-language states, numeric motivo, VIX/GEX/DIX narratives, Telegram-allowed HTML tags, return contract).
- [x] 1.2 Implementation: rewrote `build_telegram_brief` in `src/utils/terminal_gui.py` (signature `(snapshot, top_n=5, hq_n=5) -> tuple[str, list]` preserved for `scripts/finviz_monitor.py`). New module-level helpers/constants: `_semaphore_state`, `_narrativa_vix`, `_narrativa_gex`, `_narrativa_dix`, `_estado_narrativo`, `_join_natural`, `_to_float`, thresholds (`VIX_CALM_THRESHOLD=20`, `VIX_STRESS_THRESHOLD=30`, `DIX_STRONG_THRESHOLD=0.40`, `DIX_MODERATE_THRESHOLD=0.35`, `DEFAULT_MAX_DIST_SMA20=6.77`, etc.), state constants matching spec strings verbatim.
- [x] 1.3 QA Verification: focused tests 21/21 green; full suite green modulo 3 proven pre-existing environmental failures; ruff clean.
- [x] 1.4 Red Test (batch 2): 5 tests nuevos en `tests/test_telegram_brief.py` — Objetivo en JPM (Trigger listo) con nivel 210.40 + literal 'RVOL' + 'alta convicción'; Objetivo en BAC (Esperando ruptura) con 45.80; reemplazo de 'Acción sugerida' en estados de ruptura; PYPL conserva enfriamiento SIN Objetivo; existencia de constante nombrada `HIGH_CONVICTION_RVOL ≈ 1.20`.
- [x] 1.5 Implementation (batch 2): constante `HIGH_CONVICTION_RVOL = 1.20` (comentario español, sin magic numbers), helper `_linea_objetivo` junto a los demás helpers narrativos, y condicional en el loop de candidatos que sustituye `→ Acción sugerida:` por la línea Objetivo solo para ESTADO_TRIGGER_LISTO / ESTADO_ESPERANDO_RUPTURA.
- [x] 1.6 QA Verification (batch 2): pytest enfocado 26/26, ruff limpio, render offline validado contra el ejemplo aprobado. Envío de preview a Telegram DEMO queda en manos del orquestador (instrucción explícita: no enviar desde apply).

## Design Decisions / Deviations from Design
- `design.md` was a stub ("Target implementation"), so implementation followed proposal.md's reference format and technical notes.
- Candidate states are now deterministic from snapshot data; the old runtime dependency on `calculate_dynamic_sizing_factor`/`load_production_config` inside the state function was removed (the E25 sizing-factor display belonged to the replaced technical format). Documented behavioral consequence: extended candidates always show "Consolidar - no comprar aún" instead of being un-blocked when E25 sizing is active.
- Sector resolution became lazy: `get_ticker_sector_mapping` is only called when some candidate lacks `sector_etf`.
- Legacy operational blocks dropped intentionally per proposal: BREADTH HEALTH table, SHADOW/E25 AUDIT, SECTOR MONEY FLOW, NEAREST FLOW, PIPELINE STATUS, TradingView links. Buttons keep callback contract (`detail:`/`refresh:`/`regenerate:`/`shadow_audit:`) now with real emojis.
- Ruff auto-fixes touched legacy `print_terminal_brief` lines (import order, dead f-strings, bare excepts) because criterion requires ruff-clean *files*.

### Decisiones del batch 2
- La línea Objetivo renderiza `RVOL &gt; 1.20` con entidad HTML, byte-match del ejemplo aprobado por el usuario. Convención consistente con el archivo (contenido dinámico escapado vía `html.escape`; plantillas estáticas evitan `>` crudo). Telegram acepta `>` crudo como texto seguro, pero se eligió la entidad para igualar el spec exacto.
- Regla de reemplazo implementada como chequeo de pertenencia inline sobre `(ESTADO_TRIGGER_LISTO, ESTADO_ESPERANDO_RUPTURA)`; estados no mencionados en el spec ('Esperando volumen', 'Datos incompletos') conservan su línea `Acción sugerida` original sin cambios.
- Todo lo demás del mensaje permanece byte-a-byte idéntico al batch 1 (verificado por los 21 tests previos, que siguen pasando sin modificación).

## Environment Note
Fresh worktree had no Python env; created gitignored `.venv` (CPython 3.13.2) via uv with full `requirements.txt` to run the complete suite.
