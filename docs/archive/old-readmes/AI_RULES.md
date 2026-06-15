# AI_RULES.md — Reglas del Agente IA
> Subordinado a `AGENTS.md`. En caso de conflicto, `AGENTS.md` tiene prioridad.

---

## REGLAS DE COMPORTAMIENTO

- Verificar siempre los issues abiertos antes de tocar código: `gh issue list --state open`
- No iniciar trabajo sin un ID de issue asignado
- No trabajar directamente en `main` — siempre rama dedicada vía `make start`
- No refactorizar fuera del alcance del ticket activo
- No modificar `src/backtest/` ni `src/data/` sin autorización explícita
- Mantener los cambios alineados con el layout y comandos verificados en `AGENTS.md`
- Ejecutar el paso de verificación relevante antes de entregar cambios
- Scripts descartables van en `scratch/`, investigación en `experiments/`, tests formales en `tests/`
- No commitear datos locales ni bases de datos

## REGLA DE ORO

Si no hay un issue abierto que lo justifique, no se toca el código.
