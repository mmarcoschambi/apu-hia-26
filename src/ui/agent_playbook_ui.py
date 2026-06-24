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
    tab_memory, tab_workflow, tab_tdd, tab_research, tab_evolution, tab_prompts = st.tabs([
        "🧠 Memory Board (ScrumBan)", 
        "🔄 Ciclo de Vida del Ticket", 
        "🧪 Test Harness & TDD", 
        "🔬 Ciclo de Investigación (Hipótesis)",
        "📈 Evolución & Arquitectura",
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

        # Slider interactivo de fases
        fases_opciones = [
            "1. Apertura & Branch (Fase 1)",
            "2. Plan & Diseño (SDD)",
            "3. Test Unitario (TDD Red)",
            "4. Implementación (TDD Green)",
            "5. Documentar (Local Memory)",
            "6. Commit & Cierre (Fase 3)"
        ]
        
        selected_fase = st.select_slider(
            "💡 Navegá las fases del Ciclo de Vida del Ticket para ver el flujo y los prompts correspondientes:",
            options=fases_opciones
        )

        # Configuración dinámica de colores para Graphviz
        node_colors = {
            "apertura": 'fillcolor="#1F2937" fontcolor="#9CA3AF" color="#374151"',
            "plan": 'fillcolor="#1F2937" fontcolor="#9CA3AF" color="#374151"',
            "tdd_red": 'fillcolor="#1F2937" fontcolor="#9CA3AF" color="#374151"',
            "tdd_green": 'fillcolor="#1F2937" fontcolor="#9CA3AF" color="#374151"',
            "docs": 'fillcolor="#1F2937" fontcolor="#9CA3AF" color="#374151"',
            "commit": 'fillcolor="#1F2937" fontcolor="#9CA3AF" color="#374151"'
        }

        fase_clave = ""
        if "1." in selected_fase:
            fase_clave = "apertura"
        elif "2." in selected_fase:
            fase_clave = "plan"
        elif "3." in selected_fase:
            fase_clave = "tdd_red"
        elif "4." in selected_fase:
            fase_clave = "tdd_green"
        elif "5." in selected_fase:
            fase_clave = "docs"
        elif "6." in selected_fase:
            fase_clave = "commit"

        if fase_clave:
            node_colors[fase_clave] = 'fillcolor="#059669" fontcolor="#FFFFFF" color="#34D399" penwidth=2'

        # Layout en 2 columnas
        col_flow, col_details = st.columns([1, 1])

        with col_flow:
            st.markdown("#### 📊 Diagrama de Flujo del Proceso")
            
            dot_flow = f"""
            digraph G {{
                bgcolor="transparent";
                node [style=filled, fontname="Courier New", fontsize=9, shape=box, penwidth=1];
                edge [color="#4B5563", penwidth=1.2, arrowhead=vee];
                
                apertura [{node_colors['apertura']} label="1. Apertura\\n(Issue & Branch)"];
                plan [{node_colors['plan']} label="2. Plan SDD\\n(Propuesta)"];
                tdd_red [{node_colors['tdd_red']} label="3. TDD Red\\n(Escribir Test)"];
                tdd_green [{node_colors['tdd_green']} label="4. TDD Green\\n(Escribir Código)"];
                docs [{node_colors['docs']} label="5. Documentar\\n(local_memory)"];
                commit [{node_colors['commit']} label="6. Cierre\\n(Commit & Close)"];
                
                apertura -> plan;
                plan -> tdd_red [label=" aprobado", fontcolor="#9CA3AF", fontsize=8];
                tdd_red -> tdd_green [label=" test falla", fontcolor="#9CA3AF", fontsize=8];
                tdd_green -> tdd_red [label=" refactor", fontcolor="#9CA3AF", fontsize=8];
                tdd_green -> docs [label=" test pasa", fontcolor="#9CA3AF", fontsize=8];
                docs -> commit;
            }}
            """
            st.graphviz_chart(dot_flow)

        with col_details:
            if fase_clave == "apertura":
                st.markdown("### 🔑 Fase 1: Apertura & Branch")
                st.markdown(
                    "**Regla de Oro:** Nunca dejes que el agente empiece a programar sin un ticket de issue "
                    "abierto en GitHub. Esto nos permite hacer el seguimiento en el backlog sin perder el norte."
                )
                st.markdown("**💻 Comandos recomendados en consola:**")
                st.code(
                    """
gh issue list --state open       # Ver issues abiertos en el backlog
gh issue view <ID>               # Inspeccionar criterios de aceptación
git checkout -b feat/<ID>-name   # Crear la rama limpia de trabajo
                    """,
                    language="bash"
                )
                st.markdown("**💬 Prompt de Inicialización:**")
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

            elif fase_clave == "plan":
                st.markdown("### 🗺️ Fase 2: Plan & Diseño (SDD)")
                st.markdown(
                    "**Regla de Oro:** Antes de escribir una sola línea de código, el agente debe "
                    "plantear el diseño de la solución técnica detallada. Esto evita que escriba código "
                    "que no entienda o que rompa las dependencias."
                )
                st.markdown("**🔍 Verificación estructural:**")
                st.markdown(
                    "El agente debe consultar `SYSTEM_CONTEXT.md` para entender qué archivos son la verdad "
                    "canónica y el impacto que tendrá el cambio en el simulador o el Live Scanner."
                )
                st.markdown("**💬 Prompt de Control de Planificación:**")
                st.code(
                    """
Leé el código de los archivos involucrados en la propuesta para el Issue #<ID>. 
Antes de modificar nada:
1. Explicame brevemente cómo se interconectan con el resto del sistema.
2. Confirmá si requiere cambiar un archivo core (como `signal_engine.py`) o solo agregar un script de experiments/scratch.
3. Detallame los casos de prueba unitaria que vas a escribir para validar este cambio.
                    """,
                    language="markdown"
                )

            elif fase_clave == "tdd_red":
                st.markdown("### 🧪 Fase 3: TDD Red (Escribir Test)")
                st.markdown(
                    "**Regla de Oro:** Escribir el test ANTES del código de producción (Fase RED). "
                    "Si no hay test que falle para el bug o feature, no entendemos el problema real."
                )
                st.markdown("**💻 Comandos de consola:**")
                st.code(
                    """
pytest tests/test_modulo_especifico.py  # Ejecutar el test recién creado (debe fallar)
                    """,
                    language="bash"
                )
                st.markdown("**💬 Prompt para forzar TDD Red:**")
                st.code(
                    """
Quiero que implementemos este feature siguiendo estrictamente la metodología TDD:
1. Escribí primero los tests unitarios en la carpeta `tests/` que capturen la lógica requerida.
2. Ejecutá pytest y mostrame que los nuevos tests fallen (estado RED). 
3. No escribas código de producción en `src/` todavía.
                    """,
                    language="markdown"
                )

            elif fase_clave == "tdd_green":
                st.markdown("### 🟢 Fase 4: Implementación (TDD Green)")
                st.markdown(
                    "**Regla de Oro:** Escribir el mínimo código de producción necesario en `src/` para que "
                    "los tests pasen a verde (Fase GREEN). Luego, refactorizar de forma segura."
                )
                st.markdown("**📂 Estructura de archivos requerida:**")
                st.markdown(
                    "- Producción: `src/` (ej: `src/signals/`, `src/backtest/`)\\n"
                    "- Tests: `tests/` (ej: `tests/test_signal_engine.py`)\\n"
                    "- Scripts temporales: Únicamente dentro de `scratch/`"
                )
                st.markdown("**💬 Prompt para pasar a Verde:**")
                st.code(
                    """
Now that the test fails:
1. Implementá el código mínimo indispensable dentro de `src/` para hacer que el test pase.
2. Recordá que el código de producción nuevo va en un subdirectorio bajo `src/`, y nada suelto en la raíz.
3. Ejecutá pytest y confirmá que la suite de tests quede al 100% en verde.
                    """,
                    language="markdown"
                )

            elif fase_clave == "docs":
                st.markdown("### 📝 Fase 5: Documentar (Local Memory)")
                st.markdown(
                    "**Regla de Oro:** Si un cambio no se documenta en la memoria local, no existe para "
                    "las siguientes sesiones. La documentación de arquitectura e hitos previene la entropía."
                )
                st.markdown("**📂 Archivos a actualizar:**")
                st.markdown(
                    "- **Decisiones locales:** `.cache/local_memory.json` (ScrumBan Memory Board)\\n"
                    "- **Modificaciones mayores de arquitectura:** `SYSTEM_CONTEXT.md`"
                )
                st.markdown("**💬 Prompt de Documentación:**")
                st.code(
                    """
El desarrollo técnico y los tests están listos. Por favor:
1. Agregá un registro del avance en `.cache/local_memory.json` siguiendo el formato JSON oficial (timestamp, title, type, scope, topic_key, content).
2. Si el cambio altera la arquitectura o las rutas de archivos, actualizá la sección correspondiente en `SYSTEM_CONTEXT.md`.
                    """,
                    language="markdown"
                )

            elif fase_clave == "commit":
                st.markdown("### 🏁 Fase 6: Commit & Cierre")
                st.markdown(
                    "**Regla de Oro:** Confirmar los cambios con un mensaje de commit convencional y "
                    "cerrar el ticket de GitHub informando la performance del cambio."
                )
                st.markdown("**💻 Comandos recomendados:**")
                st.code(
                    """
git commit -m "[Signals] Agregar filtro de volumen. Fixes #ID"
git push origin feat/ID-nombre
gh issue comment <ID> --body "✅ Desarrollado y testeado en la rama..."
gh issue close <ID>
                    """,
                    language="bash"
                )
                st.markdown("**💬 Prompt de Cierre:**")
                st.code(
                    """
Hacé el commit convencional con el formato `[Módulo] Breve descripción. Fixes #<ID>`.
Si el pre-commit hook falla localmente por argumentos demasiado largos, usá la bandera `--no-verify` al commitear y pushear.
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
    # TAB 5: EVOLUCIÓN & ARQUITECTURA (DINÁMICO)
    # ──────────────────────────────────────────────────────────────────────
    with tab_evolution:
        st.subheader("📈 Evolución y Arquitectura Dinámica del Sistema")
        st.markdown(
            "Visualizá la estructura viva del repositorio reconstruida desde Git "
            "y el estado actual de la documentación de los archivos core."
        )

        col_left, col_right = st.columns([1, 1])

        with col_left:
            st.markdown("#### 🏗️ Arquitectura de Momentum V2")
            st.markdown(
                "Flujo de datos y dependencias entre los distintos módulos del sistema:"
            )
            
            # Diagrama Graphviz interactivo
            dot_code = """
            digraph G {
                bgcolor="transparent";
                node [style=filled, fontname="Courier New", fontsize=10, shape=box, penwidth=0];
                edge [color="#4B5563", penwidth=1.2, arrowhead=vee];
                
                // Nodos
                db [label="SQLite Cache\\n(ticker_cache.db)", fillcolor="#1E3A8A", fontcolor="#FFFFFF"];
                fv [label="Finviz Live\\n(Scraper VPS)", fillcolor="#1E3A8A", fontcolor="#FFFFFF"];
                
                se [label="Signal Engine\\n(signal_engine.py)", fillcolor="#065F46", fontcolor="#FFFFFF"];
                tl [label="Thematic Logic\\n(thematic_logic.py)", fillcolor="#065F46", fontcolor="#FFFFFF"];
                
                ml [label="ML Scorer Gate\\n(entry_scorer_gate.py)", fillcolor="#701A75", fontcolor="#FFFFFF"];
                
                rm [label="Risk Manager\\n(risk_manager.py)", fillcolor="#991B1B", fontcolor="#FFFFFF"];
                ps [label="Position Sizing\\n(position_sizing.py)", fillcolor="#991B1B", fontcolor="#FFFFFF"];
                
                vbt [label="VectorBT Advanced\\n(vectorbt_engine_advanced.py)", fillcolor="#854D0E", fontcolor="#FFFFFF"];
                scanner [label="Live Scanner\\n(live_trading_scanner.py)", fillcolor="#854D0E", fontcolor="#FFFFFF"];
                
                // Flujos
                db -> se [label=" backtest", fontcolor="#9CA3AF", fontsize=8];
                fv -> se [label=" live", fontcolor="#9CA3AF", fontsize=8];
                se -> tl;
                tl -> ml;
                ml -> ps [label=" backtest", fontcolor="#9CA3AF", fontsize=8];
                ml -> rm [label=" live", fontcolor="#9CA3AF", fontsize=8];
                ps -> vbt;
                rm -> scanner;
            }
            """
            st.graphviz_chart(dot_code)

        with col_right:
            st.markdown("#### 🔬 Cobertura de Documentación")
            st.markdown(
                "Estado de docstrings en los archivos prioritarios de Phase 6:"
            )

            # Analizar archivos
            files_to_check = {
                "Signal Engine": "src/signals/signal_engine.py",
                "Thematic Logic": "src/signals/thematic_logic.py",
                "Risk Manager": "src/utils/risk_manager.py",
                "Position Sizing": "src/risk/position_sizing.py",
                "VectorBT Advanced": "src/backtest/vectorbt_engine_advanced.py",
                "ML Scorer Gate": "src/ml/entry_scorer_gate.py"
            }

            import ast
            doc_stats = []
            for name, relative_path in files_to_check.items():
                p = Path(relative_path)
                if p.exists():
                    try:
                        with open(p, "r", encoding="utf-8") as f:
                            tree = ast.parse(f.read(), filename=str(p))
                        
                        module_doc = ast.get_docstring(tree) is not None
                        nodes = [n for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))]
                        total = len(nodes)
                        documented = sum(1 for n in nodes if ast.get_docstring(n) is not None)
                        
                        doc_stats.append({
                            "Archivo": name,
                            "Ruta": relative_path,
                            "Módulo": "✅ Sí" if module_doc else "❌ No",
                            "Items": total,
                            "Doc": documented,
                            "Cobertura": (documented / total * 100) if total > 0 else 100.0
                        })
                    except Exception as e:
                        doc_stats.append({
                            "Archivo": name, "Ruta": relative_path, "Módulo": "⚠️ Error", "Items": 0, "Doc": 0, "Cobertura": 0.0
                        })
                else:
                    doc_stats.append({
                        "Archivo": name, "Ruta": relative_path, "Módulo": "🚫 N/A", "Items": 0, "Doc": 0, "Cobertura": 0.0
                    })

            for stat in doc_stats:
                st.markdown(f"**{stat['Archivo']}** (`{stat['Ruta']}`)")
                col1, col2, col3 = st.columns([2, 1, 1])
                with col1:
                    st.progress(stat['Cobertura'] / 100.0)
                with col2:
                    st.caption(f"{stat['Doc']}/{stat['Items']} items")
                with col3:
                    st.caption(f"**{stat['Cobertura']:.1f}%**")

        st.markdown("---")
        st.markdown("#### ⏳ Historial de Evolución del Código (Git Log)")
        st.markdown(
            "Últimos cambios registrados en la rama activa (`git log` ejecutado dinámicamente):"
        )

        import subprocess
        try:
            result = subprocess.run(
                ["git", "log", "-n", "12", "--pretty=format:%h|%ad|%an|%s", "--date=short"],
                capture_output=True,
                text=True,
                check=True
            )
            git_lines = result.stdout.splitlines()
            
            for line in git_lines:
                parts = line.split("|")
                if len(parts) >= 4:
                    commit_hash, commit_date, author, message = parts[0], parts[1], parts[2], "|".join(parts[3:])
                    
                    badge = "📝"
                    if "[UI]" in message:
                        badge = "🎨 [UI]"
                    elif "[Signals]" in message:
                        badge = "📈 [Signals]"
                    elif "[ML]" in message or "[Machine Learning]" in message:
                        badge = "🧠 [ML]"
                    elif "[Chore]" in message:
                        badge = "⚙️ [Chore]"
                    elif "[Docs]" in message:
                        badge = "📄 [Docs]"
                    elif "fix" in message.lower():
                        badge = "🐞 [Fix]"
                    
                    st.markdown(
                        f"🔹 **{commit_date}** · `{commit_hash}` · **{badge}** {message} *(por {author})*"
                    )
        except Exception as e:
            st.warning(f"No se pudo cargar el historial de Git: {e}")

    # ──────────────────────────────────────────────────────────────────────
    # TAB 6: CHEAT SHEET GENERAL DE PROMPTS
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

        st.markdown("#### 4. Remediación (Cuando se programó directo sin las buenas prácticas):")
        st.markdown(
            "Usá estas plantillas de prompts si vos o el agente anterior escribieron código "
            "directamente en la raíz, se saltearon los tests unitarios o dejaron archivos basura."
        )

        with st.expander("Remediación para un BUG / FIX (Saltearse TDD)"):
            st.code(
                """
Hice una corrección rápida en el archivo <ruta_del_archivo> para solucionar un bug de forma directa, pero no seguí el protocolo TDD ni creé pruebas. Por favor:
1. Analizá el cambio realizado y entendé la causa raíz.
2. Diseñá y escribí un test unitario formal dentro de la carpeta `tests/` que reproduzca el caso de falla.
3. Ejecutá la suite de tests (`pytest`) y confirmá que el fix pase y todo quede 100% verde.
4. Documentá el bugfix en `.cache/local_memory.json` con type "bugfix".
""",
                language="markdown"
            )

        with st.expander("Remediación para una FEATURE (Archivos sueltos en raíz o desorden)"):
            st.code(
                """
Estuve picando código para implementar el feature <nombre_feature> y tengo archivos temporales o lógicas mezcladas. Por favor:
1. Analizá qué archivos y cambios están fuera de su lugar.
2. Mové los scripts de prueba a `experiments/` y el código de producción oficial a su módulo bajo `src/`.
3. Limpiá cualquier archivo huérfano de la raíz del repositorio.
4. Actualizá `SYSTEM_CONTEXT.md` para mapear los nuevos componentes en la sección de módulos activos.
""",
                language="markdown"
            )

        with st.expander("Remediación para un CHORE / REFACTOR (Limpieza de residuales)"):
            st.code(
                """
Estuve haciendo pruebas locales y quedaron archivos temporales, backups o logs no rastreados por git. Por favor:
1. Mové o eliminá todos los archivos temporales residuales a la carpeta `scratch/` (asegurando que queden ignorados por git).
2. Ejecutá un chequeo del estado del repo (`git status`) y confirmá que no haya archivos residuales sueltos.
3. Si hubo algún refactor menor en las firmas del código, documentalo brevemente agregando una entrada en `.cache/local_memory.json`.
""",
                language="markdown"
            )
