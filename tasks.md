# Tasks: chore(clean): eliminar dead code en terminal_gui (resto siempre vacio, hq_n sin uso)

## Problema
La verificación formal de #67 (verify-report, sección Suggestions) dejó registrados dos hallazgos de código muerto / innecesario en `src/utils/terminal_gui.py` que quedaron fuera de alcance:

1. **S1 — Dead code (~L951-961):** `resto = [t for t in rendered_tickers if t not in rendered_set]` es siempre lista vacía porque `rendered_set == set(rendered_tickers)` por construcción. Consecuencia: la línea "En espera" del mensaje nunca renderiza.
2. **S2 — Parámetro `hq_n` retenido pero sin uso** (documentado como shim de compatibilidad).

## Alcance propuesto
- [x] Eliminar el bloque dead code de `resto` (y su render nunca-ejecutado) — decisión: eliminación. La línea "En espera" nunca renderizó (por construcción `rendered_set == set(rendered_tickers)`); implementarla exigiría una fuente de datos nueva, fuera de alcance de esta chore.
- [x] Decidir destino de `hq_n`: **removido** de `build_telegram_brief` tras grep de callers (`scripts/finviz_monitor.py:271` llama con solo `snapshot`; tests ídem). Se conserva en `print_terminal_brief` donde sí se usa (L576, caller `scripts/paper_finviz.py`).
- [x] Suite `pytest tests/test_telegram_brief.py` verde sin cambios de comportamiento visible: 28 passed + snapshot antes/después byte-idéntico (2490 chars).
- [x] Ruff limpio.

## Notas
- Origen exacto: sección Suggestions del verify-report del cambio issue-67 (`.openspec/changes/issue-67/verify-report.md` en la rama `issue-67`).
- Issue pequeña, ideal para cleanup entre features. No tocar nada de `src/backtest/` ni `src/data/`.


URL: https://github.com/mmarcoschambi/swing-momentum-v1/issues/76
Labels: chore:clean, tech-debt