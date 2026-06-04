# DEVELOPER_RULES.md — Estándares Locales
> Subordinado a `AGENTS.md`. En caso de conflicto, `AGENTS.md` tiene prioridad.

---

## ORGANIZACIÓN DE CÓDIGO

- Código de producción → `src/<módulo>/`
- Automatización oficial → `scripts/`
- Investigación sandboxeada → `experiments/`
- Tests formales → `tests/`
- Trabajo descartable / debug → `scratch/`
- Sin scripts ad hoc en la raíz del repo
- Sin copias de backup dentro de `src/` — usar historial de Git

## DATOS Y BASES DE DATOS

- `data/` y `*.db` son locales — no commitear
- Caches y datos generados fuera de Git cuando sea posible

## CONVENCIONES PYTHON

- Type hints en todas las funciones nuevas
- Docstrings con propósito, parámetros y retorno
- Sin magic numbers — constantes nombradas
- Ruff: line length 100, checks E/F/I/W
- Comentarios en español, código y variables en inglés

## MÓDULOS SENSIBLES (requieren autorización explícita para modificar)

- `src/backtest/` — motor core del backtester
- `src/data/`     — mapeo de símbolos y fuentes históricas
