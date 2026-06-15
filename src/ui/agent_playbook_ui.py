import streamlit as st
import pandas as pd
import json
from pathlib import Path

def render_agent_playbook():
    """
    Renderiza el Playbook de Desarrollo con Agentes y ScrumBan Memory Board
    de forma didáctica y visual en Streamlit.
    """
    st.title("🤖 Agent Developer Center")
    st.caption("Guía interactiva y protocolo operativo para el desarrollo asistido por Agentes de IA")

    st.markdown(
        """
        Este centro de desarrollo define el **estándar de ingeniería** para interactuar con 
        los agentes en `momentum-v2`. Protege la ventana de contexto, evita la generación de 
        código basura en directorios incorrectos y mantiene el ScrumBan en sincronía.
        """
    )

    # Tabs principales
    tab_memory, tab_workflow, tab_tdd, tab_research, tab_prompts = st.tabs([
        "🧠 Memory Board (ScrumBan)", 
        "🔄 Ciclo de Vida del Ticket", 
        "🧪 Test Harness & TDD", 
        "🔬 Ciclo de Investigación (Hipótesis)",
        "💬 Cheat Sheet de Prompts"
    ])

    # ──────────────────────────────────────────────────────────────────────
    # TAB 1: MEMORY BOARD (ScrumBan)
    # ──────────────────────────────────────────────────────────────────────
    with tab_memory:
        st.subheader("🧠 Historial de Avances y Decisiones (local_memory.json)")
        st.markdown(
            "Cargado en tiempo real desde `.cache/local_memory.json`. Registra las decisiones "
            "de arquitectura, descubrimientos y refactorizaciones realizadas en cada sesión."
        )

        memory_file = Path(".cache/local_memory.json")
        if memory_file.exists():
            try:
                with open(memory_file, "r", encoding="utf-8") as f:
                    memory_data = json.load(f)
                
                # Convertir a DataFrame
                df = pd.DataFrame(memory_data)
                
                # Reordenar columnas para visualización amigable
                if not df.empty:
                    df["timestamp"] = pd.to_datetime(df["timestamp"], format="mixed", errors="coerce")
                    df = df.sort_values(by="timestamp", ascending=False)
                    
                    # Filtros interactivos en Streamlit
                    col1, col2 = st.columns(2)
                    with col1:
                        selected_type = st.multiselect(
                            "Filtrar por Tipo",
                            options=df["type"].unique(),
                            default=df["type"].unique()
                        )
                    with col2:
                        search_query = st.text_input("🔍 Buscar en el contenido", "")

                    # Aplicar filtros
                    filtered_df = df[df["type"].isin(selected_type)]
                    if search_query:
                        filtered_df = filtered_df[
                            filtered_df["title"].str.contains(search_query, case=False, na=False) |
                            filtered_df["content"].str.contains(search_query, case=False, na=False) |
                            filtered_df["topic_key"].str.contains(search_query, case=False, na=False)
                        ]

                    # Mostrar los registros en formato expander
                    for _, row in filtered_df.iterrows():
                        time_str = row["timestamp"].strftime("%d %b %Y, %H:%M")
                        type_emojis = {
                            "bugfix": "🐞 BUGFIX",
                            "discovery": "💡 DISCOVERY",
                            "pattern": "📐 PATTERN",
                            "decision": "🏛 DECISION",
                            "architecture": "🏗 ARCHITECTURE"
                        }
                        emoji = type_emojis.get(row["type"], "📝 RECORD")
                        
                        with st.expander(f"{emoji} · {row['title']} ({time_str})"):
                            st.markdown(f"**Tema Clave:** `{row['topic_key']}` | **Alcance:** `{row['scope']}`")
                            st.info(row["content"])
                else:
                    st.info("El archivo local_memory.json está vacío.")
            except Exception as e:
                st.error(f"Error al cargar local_memory.json: {e}")
        else:
            st.warning("⚠️ No se encontró el archivo `.cache/local_memory.json` en el repositorio.")

        # PROMPT MOCK PARA ESTE TAB
        st.markdown("---")
        st.markdown("#### 💬 Prompt para pedir al Agente que registre una Decisión/Avance:")
        st.code(
            """
Completamos esta tarea. Por favor, agregá un nuevo registro a nuestro archivo `.cache/local_memory.json`.
El registro debe seguir este formato JSON exacto:
{
  "timestamp": "<fecha_utc_actual>",
  "title": "<Título descriptivo de la decisión, bugfix o pattern>",
  "type": "bugfix | discovery | pattern | decision | architecture",
  "scope": "project",
  "topic_key": "<identificador-estable-del-tema>",
  "content": "<Descripción detallada de qué se hizo, por qué y qué aprendimos en esta sesión>"
}
""",
            language="markdown"
        )

    # ──────────────────────────────────────────────────────────────────────
    # TAB 2: CICLO DE VIDA DEL TICKET (VISUAL)
    # ──────────────────────────────────────────────────────────────────────
    with tab_workflow:
        st.subheader("🔄 Protocolo ScrumBan Paso a Paso")
        st.markdown(
            "El flujo mandatorio para cualquier modificación de código. Garantiza que el "
            "repositorio no acumule entropía o archivos duplicados."
        )

        st.markdown(
            """
            ### 1. Contexto e Inicio (Fase 1)
            *   **Regla de Oro:** Nunca dejes que el agente empiece a programar sin un ticket de issue en GitHub.
            *   **Comandos en consola:**
                ```bash
                gh issue list --state open       # Ver issues abiertos
                gh issue view <ID>               # Ver criterios de aceptación
                git checkout -b feat/<ID>-name   # Crear la rama limpia
                ```

            ### 2. Planeamiento y Diseño (SDD)
            *   Antes de escribir código, el agente debe plantear la solución técnica en el chat y definir qué archivos va a tocar.
            *   Debe confirmar que entiende las dependencias estructurales usando la verdad canónica del sistema en `SYSTEM_CONTEXT.md`.

            ### 3. Implementación y QA (Fase 2)
            *   **Strict TDD Mode:** Escribir primero el test (rojo) y luego implementar para que pase (verde).
            *   **Ubicación de archivos:**
                *   ✅ Producción: `src/` (ej: `src/signals/`, `src/backtest/`)
                *   ✅ Automatización / Scripts oficiales: `scripts/`
                *   ✅ Experimentos sandbox: `experiments/`
                *   ✅ Pruebas unitarias: `tests/`
                *   ✅ Debug descartable o scripts ad-hoc: `scratch/` (está en `.gitignore`)
                *   ❌ NUNCA crear scripts sueltos en la raíz del repositorio.

            ### 4. Cierre y Documentación (Fase 3)
            *   **Commit con formato convencional:** `[Módulo] Breve descripción. Fixes #<ID>` (ej: `[Signals] Agregar filtro SMA20. Fixes #48`).
            *   **Paso final en la terminal:**
                ```bash
                gh issue comment <ID> --body "✅ Build completado. Veredicto: ..."
                gh issue close <ID>
                ```
            """
        )

        # PROMPTS MOCKS PARA CADA FASE
        st.markdown("---")
        st.markdown("#### 💬 Prompts Listos para Copiar según cada Fase:")
        
        with st.expander("Fase 1: Contexto e Inicio (Prompt de Inicialización)"):
            st.code(
                """
Hola. Vamos a iniciar el desarrollo del Issue #<ID>. 
Por favor, seguí este protocolo:
1. Leé `SYSTEM_CONTEXT.md` para entender el roadmap y los módulos activos.
2. Leé `AGENTS.md` para alinear tu comportamiento con nuestras restricciones.
3. Creá o muévete a la rama `feat/<ID>-<nombre-corto>`.
4. Analizá los archivos afectados y presentame una propuesta paso a paso antes de programar.
""",
                language="markdown"
            )

        with st.expander("Fase 2: Desarrollo e Implementación (Prompt de Control)"):
            st.code(
                """
Procedé con la propuesta técnica aprobada.
Recordá las siguientes restricciones de directorios:
- El código de producción nuevo va en un subdirectorio bajo `src/`.
- Cualquier script temporal o debug debe guardarse únicamente en `scratch/` para que no se agregue a Git.
- Los tests unitarios deben estar en la carpeta `tests/`.
""",
                language="markdown"
            )

        with st.expander("Fase 3: Cierre y Commits (Prompt de Finalización)"):
            st.code(
                """
El desarrollo está completo. Por favor:
1. Agregá el registro correspondiente en `.cache/local_memory.json` con los detalles técnicos (timestamp, title, type, scope, topic_key, content).
2. Hace el commit convencional indicando `[Módulo] Breve descripción. Fixes #<ID>`.
3. Si el pre-commit hook falla localmente por argumentos muy largos, usá la bandera `--no-verify` al commitear y pushear.
""",
                language="markdown"
            )

    # ──────────────────────────────────────────────────────────────────────
    # TAB 3: TEST HARNESS & TDD
    # ──────────────────────────────────────────────────────────────────────
    with tab_tdd:
        st.subheader("🧪 Protegiendo la Calidad con Pruebas Unitarias")
        st.markdown(
            "El sistema cuenta con una robusta suite de pruebas unitarias que previene "
            "regresiones en el motor de señales y en el simulador."
        )

        st.success(
            "🚀 **Baseline actual: 255/255 pruebas pasando (100% green).**"
        )

        st.markdown(
            """
            ### ¿Cómo validar los cambios del agente?
            *   Exigile al agente que ejecute `pytest` de forma local para validar que no haya roto nada:
                ```bash
                pytest                     # Suite completa
                pytest tests/test_e25_sizing.py  # Test específico
                ```
            *   Si el pre-commit hook de Git falla localmente por límites de argumentos (`Argument list too long` debido a snapshots pesados), podés indicarle al agente que use `--no-verify` al commitear y pushear:
                ```bash
                git commit -m "[Módulo] ..." --no-verify
                git push origin <rama> --no-verify
                ```
            """
        )

        # PROMPT MOCK PARA TDD
        st.markdown("---")
        st.markdown("#### 💬 Prompt para guiar al Agente en Strict TDD Mode:")
        st.code(
            """
Quiero que implementemos este feature siguiendo estrictamente la metodología TDD (Test-Driven Development):
1. **Red**: Escribí primero los tests unitarios en la carpeta `tests/` y verifiquemos que fallen.
2. **Green**: Escribí el mínimo código de producción necesario en `src/` para que los tests pasen.
3. **Refactor**: Limpiá y optimizá el código asegurando que la suite de tests siga en 100% verde.
Ejecutá `pytest` en cada paso para validar el estado.
""",
            language="markdown"
        )

    # ──────────────────────────────────────────────────────────────────────
    # TAB 4: CICLO DE INVESTIGACIÓN (HIPÓTESIS)
    # ──────────────────────────────────────────────────────────────────────
    with tab_research:
        st.subheader("🔬 El Pipeline Cuantitativo Profesional (QUANT-FEATURE.md)")
        st.markdown(
            "Este es el flujo de trabajo metodológico para validar y evaluar nuevas "
            "hipótesis cuantitativas sin comprometer el motor ni la estabilidad del sistema en vivo."
        )

        st.markdown(
            """
            ### Las 4 Etapas del Ciclo de Investigación:

            #### 1. La Sandbox (Investigación y Ablación)
            *   **Dónde ocurre:** En `experiments/` (usando Jupyter notebooks o scripts aislados como `run_walkforward_hybrid.py`).
            *   **Objetivo:** Probar si la hipótesis (ej. *'¿Un filtro de distancia mínima a la SMA20 aporta alfa?'*) tiene ventaja estadística cruda.
            *   **Regla de Oro:** Si el concepto no sobrevive a salidas simples fijas (ej. holding de 10 días), **se descarta de inmediato**. No intentes arreglar una mala hipótesis optimizándola.

            #### 2. Integración al Core (El Enchufe)
            *   **Dónde ocurre:** En `src/backtest/vectorbt_engine_advanced.py` y `config/defaults.py`.
            *   **Objetivo:** Traducir la hipótesis ganadora a código oficial a través de un **Feature Flag** (e.g. `use_new_filter = True/False`).
            *   **Regla de Oro:** **NUNCA dupliques el motor completo** para probar una idea. Mantener un solo código es mandatorio.

            #### 3. Optimización y La Guillotina (ResearchGate)
            *   **Dónde ocurre:** Ejecutando `optimize_3tier.py` y el walk-forward stress testing.
            *   **Objetivo:** Optuna busca la gestión de salidas ideal (TP1, TP2, Runner). El ResearchGate somete la estrategia a comisiones dobles, slippage y stress testing para calcular el PBO (Probability of Backtest Overfitting).
            *   **Regla de Oro:** Si el PBO > 50% (REJECTED), la estrategia se descarta. Solo se confía en lo **APPROVED**.

            #### 4. Producción (Live Trading)
            *   **Dónde ocurre:** `live_trading_scanner.py` leyendo `production_config.json`.
            *   **Objetivo:** El Live Scanner ejecuta como robot tonto las reglas matemáticas validadas y congeladas de la Etapa 3. No se altera la lógica en producción.
            """
        )

        # PROMPT MOCK PARA INVESTIGACIÓN DE HIPÓTESIS
        st.markdown("---")
        st.markdown("#### 💬 Prompt para guiar al Agente en la Sandbox (Etapa 1 - Hipótesis):")
        st.code(
            """
Quiero investigar la siguiente hipótesis cuantitativa:
Hipótesis: <Describir la hipótesis, ej. 'Penalizar activos a menos del 1% de su SMA20 en el Sistema B'>

Por favor, seguí la Etapa 1 (Sandbox) del ciclo de investigación:
1. Creá un script aislado en el directorio `experiments/` (ej. `experiments/shadow_sma20_research.py`).
2. Utilizá los datos de `data/ticker_cache.db` e implementá la lógica de forma simplificada (sin tocar archivos de `src/`).
3. Corré una simulación con un holding fijo de 10 días para evaluar si la idea tiene edge real (Win Rate y Profit Factor OOS comparado con el baseline).
4. Mostrame los resultados y decime si la idea califica para pasar a la Etapa 2 (Integración al Core).
""",
            language="markdown"
        )

    # ──────────────────────────────────────────────────────────────────────
    # TAB 5: CHEAT SHEET GENERAL DE PROMPTS
    # ──────────────────────────────────────────────────────────────────────
    with tab_prompts:
        st.subheader("💬 Cheat Sheet de Prompts Rápidos")
        st.markdown(
            "Una recopilación rápida de plantillas didácticas para alinear a cualquier "
            "agente en una sesión de desarrollo."
        )

        st.markdown("#### 1. Iniciar un nuevo ticket de desarrollo:")
        st.code(
            """
Hola. Vamos a abrir el desarrollo para el Issue #<ID>. 
Antes de empezar:
1. Leé `SYSTEM_CONTEXT.md` para entender el roadmap y los módulos activos.
2. Leé `AGENTS.md` para seguir estrictamente las reglas de ScrumBan, TDD y estructuración de archivos.
3. Creá la rama de desarrollo correspondiente `feat/<ID>-<nombre-corto>` si no estamos en ella.

Planteame tu propuesta técnica paso a paso antes de escribir código.
            """,
            language="markdown"
        )

        st.markdown("#### 2. Evitar desorden en el directorio raíz:")
        st.code(
            """
Recordatorio de arquitectura:
- Está estrictamente PROHIBIDO guardar archivos de desarrollo sueltos en el directorio raíz.
- El código de producción nuevo debe ir en un subdirectorio bajo `src/`.
- Cualquier script de depuración o prueba rápida que crees debe guardarse únicamente dentro de la carpeta `scratch/` para que sea ignorado por git.
            """,
            language="markdown"
        )

        st.markdown("#### 3. Cierre y Guardado de Memoria (ScrumBan):")
        st.code(
            """
Completamos las modificaciones y los tests están pasando. Ahora:
1. Actualizá el archivo `.cache/local_memory.json` agregando un registro del avance con el formato del array de objetos JSON (timestamp, title, type, scope, topic_key, content).
2. Hacé el commit convencional indicando `[Módulo] Descripción. Fixes #<ID>`.
3. Si los pre-commits fallan en local por exceso de argumentos, usá la bandera `--no-verify` para commitear y pushear.
            """,
            language="markdown"
        )
