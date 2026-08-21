# Apply Progress: issue-67 — Narrative Telegram pre-market brief

## Status
All tasks complete. Strict TDD cycle executed (RED → GREEN → QA).

## Work Unit Evidence

| Evidence | Required value |
|---|---|
| Focused test command and exact result | `.venv\Scripts\python.exe -m pytest tests/test_telegram_brief.py -v` → **21 passed in 2.09s** |
| Runtime harness command/scenario and exact result | Rendered full brief via `build_telegram_brief(make_snapshot())` with mocked `fetch_gamma_data`/`_build_hot_sectors`/`get_ticker_sector_mapping`; visual output verified against proposal reference HTML (8 sections, real emojis, narrative states). Full suite as integration boundary: **450 passed / 5 skipped / 3 pre-existing failures** (see below). |
| Rollback boundary | Revert commit restores `src/utils/terminal_gui.py`; deleting `tests/test_telegram_brief.py` removes only the new tests. No other files touched by the feature. |

## TDD Cycle Evidence

| Task | RED (test first) | GREEN | REFACTOR |
|---|---|---|---|
| 1.1 Red Test | `pytest tests/test_telegram_brief.py -v` → **16 failed, 4 passed** (placeholders `[U+...]`/`[OK]`/`[WARN]` detected, all narrative sections missing, states not in natural language) | — | Hermetic fix: patched `_build_hot_sectors` in negative-gamma variant (was leaking to real sector analysis) |
| 1.2 Implementation | Mini-RED added mid-task: `test_candidatos_excluye_sectores_no_calientes` → **1 failed** (PBF leaked into Candidatos) | **21 passed** after restricting grouping to hot sectors only | Ruff fixes on untouched legacy lines (I001 import order, F541 dead f-prefixes, E722 bare excepts → typed exceptions) |
| 1.3 QA Verification | — | Full suite `pytest tests/` → **450 passed, 5 skipped, 3 failed**; ruff → **All checks passed** (exit 0) | Pre-existing failure proof: stashed change, same 3 tests fail on HEAD (`sqlite3.OperationalError` ×2, quant-gate assertion ×1; gitignored `data/` DBs absent in worktree). No test imports `terminal_gui`. |

## Completed Tasks
- [x] 1.1 Red Test (TDD): `tests/test_telegram_brief.py` created with 20 tests covering every acceptance criterion + the 8 sections (structure, content, placeholder regex `\[(U\+|OK|WARN|BOLT)[^\]]*\]`, natural-language states, numeric motivo, VIX/GEX/DIX narratives, Telegram-allowed HTML tags, return contract).
- [x] 1.2 Implementation: rewrote `build_telegram_brief` in `src/utils/terminal_gui.py` (signature `(snapshot, top_n=5, hq_n=5) -> tuple[str, list]` preserved for `scripts/finviz_monitor.py`). New module-level helpers/constants: `_semaphore_state`, `_narrativa_vix`, `_narrativa_gex`, `_narrativa_dix`, `_estado_narrativo`, `_join_natural`, `_to_float`, thresholds (`VIX_CALM_THRESHOLD=20`, `VIX_STRESS_THRESHOLD=30`, `DIX_STRONG_THRESHOLD=0.40`, `DIX_MODERATE_THRESHOLD=0.35`, `DEFAULT_MAX_DIST_SMA20=6.77`, etc.), state constants matching spec strings verbatim.
- [x] 1.3 QA Verification: focused tests 21/21 green; full suite green modulo 3 proven pre-existing environmental failures; ruff clean.

## Design Decisions / Deviations from Design
- `design.md` was a stub ("Target implementation"), so implementation followed proposal.md's reference format and technical notes.
- Candidate states are now deterministic from snapshot data; the old runtime dependency on `calculate_dynamic_sizing_factor`/`load_production_config` inside the state function was removed (the E25 sizing-factor display belonged to the replaced technical format). Documented behavioral consequence: extended candidates always show "Consolidar - no comprar aún" instead of being un-blocked when E25 sizing is active.
- Sector resolution became lazy: `get_ticker_sector_mapping` is only called when some candidate lacks `sector_etf`.
- Legacy operational blocks dropped intentionally per proposal: BREADTH HEALTH table, SHADOW/E25 AUDIT, SECTOR MONEY FLOW, NEAREST FLOW, PIPELINE STATUS, TradingView links. Buttons keep callback contract (`detail:`/`refresh:`/`regenerate:`/`shadow_audit:`) now with real emojis.
- Ruff auto-fixes touched legacy `print_terminal_brief` lines (import order, dead f-strings, bare excepts) because criterion requires ruff-clean *files*.

## Environment Note
Fresh worktree had no Python env; created gitignored `.venv` (CPython 3.13.2) via uv with full `requirements.txt` to run the complete suite.
