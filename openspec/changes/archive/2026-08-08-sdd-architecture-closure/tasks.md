# Tasks: SDD/FSM Architecture Closure

- [x] **Task 1: Phase 1 - Reconciliación de Pipeline**
  - Añadir en `SYSTEM_CONTEXT.md` la separación explícita de los baselines (Variante E 2.55% vs Histórico 96.12% return / -35.09% MDD).
  - Ejecutar `python scripts/check_git_duplicates.py` para validar que el repositorio está limpio antes de levantar la restricción.
  - Eliminar `-k "not test_integrity"` en las 3 ubicaciones de `openspec/config.yaml`.
  - Crear un script Python temporal `scratch/check_archive_hash.py` que hashee la carpeta `archive/2026-07-20-refactor-ticker-cache/`.
  - Usar PowerShell `Remove-Item -Recurse -Force openspec/changes/archive/2026-07-23-refactor-ticker-cache/` para borrar solo el directorio incorrecto sin wildcards.
  - *Verificación*: Correr `check_archive_hash.py` para asegurar que el hash de `2026-07-20` no mutó. `PYTHONPATH=. pytest tests/` incluye test_integrity y pasa.

- [x] **Task 2: Phase 2 - Lector y Persistencia Atómica de Memoria**
  - Crear copia de seguridad: PowerShell `Copy-Item .cache/local_memory.json .cache/local_memory.json.bak`.
  - Migrar atómicamente la estructura escribiendo a un archivo `.tmp` y renombrándolo. La estructura final debe ser `{"schema_version": "1.0", "entries": [...]}` conteniendo las 22 históricas + 3 reglas nuevas (Promotion, Look-Ahead, Live Status).
  - Crear `scripts/verify_memory_rules.py` que compruebe: schema=1.0, len(entries)=25, y las 3 reglas.
  - *Verificación*: `python scripts/verify_memory_rules.py` retorna exit code 0.

- [x] **Task 3: Phase 3 - Saneamiento y Matriz del Playbook**
  - Eliminar la línea completa `git push origin HEAD --no-verify` y su justificación textual `(si falla pre-commit por cuotas de API)` en `docs/playbook_sdd_scrumban.md`.
  - Insertar tabla estructurada (`| Señal | Riesgo | Acción Obligatoria |`) conteniendo los 5 olores de código listados en el Design.
  - *Prevención Histórica*: El validador siguiente leerá SÓLO el playbook; no debe alterar ni verificar la entrada histórica de `local_memory.json` (2026-06-15) que documenta por qué se usó legítimamente `--no-verify`.
  - *Verificación*: Crear el validador `scratch/check_playbook_smells.py` que lea *únicamente* el playbook y dispare assert si encuentra "--no-verify" o "cuotas de API". Ejecutar validador.

- [x] **Task 4: Phase 4 - Parchear Skill Hand-off (Adaptador Local)**
  - Reemplazar `codely-plan_phase-implement-github` por instrucciones directas para ejecutar comandos OpenSpec (`/sdd-ff` o `/sdd-new` para la fase generada) en las 4 ubicaciones del archivo `.agents/skills/codely-plan-create-github/SKILL.md` (frontmatter, paso 8 padre, paso 8 hijo, alerta IMPORTANT).
  - *Verificación*: Crear el validador `scratch/check_skill_handoff.py` que dispare assert si `codely-plan_phase-implement-github` existe en el archivo. Ejecutar validador.
