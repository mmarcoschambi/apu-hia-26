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
    tab_memory, tab_workflow, tab_tdd, tab_prompts = st.tabs([
        "🧠 Memory Board (ScrumBan)", 
        "🔄 Ciclo de Vida del Ticket", 
        "🧪 Test Harness & TDD", 
        "💬 Copiar Prompts Oficiales"
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

    # ──────────────────────────────────────────────────────────────────────
    # TAB 4: COPIAR PROMPTS OFICIALES
    # ──────────────────────────────────────────────────────────────────────
    with tab_prompts:
        st.subheader("💬 Plantillas de Prompts para usar con Agentes")
        st.markdown(
            "Copiá y pegá estas plantillas didácticas al iniciar un chat o al abrir un issue "
            "para alinear al agente con las reglas del repositorio."
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
