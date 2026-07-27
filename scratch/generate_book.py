import os
import shutil
import re

out_dir = "apps/playbook/Assets/Docs"

# Lista definitiva de los 35 capítulos con su prefijo para asegurar el orden.
chapters = [
    # I. FUNDAMENTOS
    ("01", "Primeros_Principios_Cuantitativos"),
    ("02", "Capital_y_Escalamiento_AUM"),
    ("03", "Stack_Tecnologico_y_Entornos"),
    ("04", "Evolucion_y_Arquitectura"),
    
    # II. AGENT TEAMS
    ("05", "Matriz_de_Roles_y_Agentes"),
    ("06", "Ciclo_de_Vida_del_Ticket"),
    ("07", "Control_de_Versiones_y_CICD"),
    ("08", "Cheat_Sheet_de_Prompts"),
    ("09", "Salvaguardas_y_Cierre"),
    
    # III. INVESTIGACIÓN
    ("10", "El_Pipeline_Cuantitativo"),
    ("11", "Rigor_Estadistico_y_Sobreajuste"),
    ("12", "Stress_Testing_Historico"),
    ("13", "Backlog_de_Experimentos"),
    
    # IV. MOTOR DE BACKTESTING
    ("14", "Diseno_del_Motor_VectorBT"),
    ("15", "Pipeline_Point_In_Time"),
    ("16", "Modelado_de_Costos_y_Friccion"),
    
    # V. CATÁLOGO
    ("17", "Regimenes_de_Mercado"),
    ("18", "Sistema_A_Combo_Momentum"),
    ("19", "Sistema_B_Joya_E25"),
    ("20", "Correlacion_y_Riesgo_de_Solapamiento"),
    ("21", "Asignacion_y_Rebalanceo_de_Capital"),
    
    # VI. PRODUCCIÓN
    ("22", "Arquitectura_del_Live_Scanner"),
    ("23", "Seguridad_y_Credenciales"),
    ("24", "Calidad_de_Ejecucion_Broker"),
    ("25", "Anatomia_de_un_Trade"),
    ("26", "Risk_Management_y_Kill_Switches"),
    ("27", "Observabilidad_y_Telemetria"),
    
    # VII. OPERACIONES
    ("28", "Gestion_de_Estado_y_Override"),
    ("29", "BCP_y_Disaster_Recovery"),
    ("30", "Tracking_de_Drift_y_Deprecacion"),
    ("31", "Reconciliacion_Contable"),
    ("32", "Cumplimiento_Regulatorio"),
    ("33", "Protocolo_de_Post_Mortem"),
    
    # VIII. APÉNDICES
    ("34", "Glosario_de_Metricas"),
    ("35", "Psicologia_Operativa_y_Drawdown")
]

# Diccionario para mapear los archivos viejos (de las pestañas extraídas) a los nuevos IDs
# Old file -> (New Prefix, New Name, Title)
mapping_old_to_new = {
    "6_Primeros_Principios.md": ("01", "Primeros_Principios_Cuantitativos", "I.1 Primeros Principios Cuantitativos"),
    "7_Evolucion_Arquitectura.md": ("04", "Evolucion_y_Arquitectura", "I.4 Evolución y Arquitectura"),
    "2_Ciclo_de_Vida.md": ("06", "Ciclo_de_Vida_del_Ticket", "II.2 Ciclo de Vida del Ticket (ScrumBan)"),
    "8_Cheat_Sheet_Prompts.md": ("08", "Cheat_Sheet_de_Prompts", "II.4 Cheat Sheet de Prompts"),
    "1_Memory_Board.md": ("09", "Salvaguardas_y_Cierre", "II.5 Salvaguardas y Protocolo de Cierre (Memory Board)"),
    "4_Investigacion.md": ("10", "El_Pipeline_Cuantitativo", "III.1 El Pipeline Cuantitativo"),
    "3_Test_Harness.md": ("14", "Diseno_del_Motor_VectorBT", "IV.1 Diseño del Motor (Test Harness)"),
    "5_Backlog.md": ("13", "Backlog_de_Experimentos", "III.4 Backlog de Experimentos"),
}

# 1. Leer el contenido existente
old_contents = {}
for old_file, (pref, name, title) in mapping_old_to_new.items():
    path = os.path.join(out_dir, old_file)
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            old_contents[pref] = f.read()
        os.remove(path) # Limpiamos el viejo archivo

# 2. Generar todos los capítulos
for prefix, name in chapters:
    filename = f"{prefix}_{name}.md"
    filepath = os.path.join(out_dir, filename)
    
    # Título para el placeholder
    title_str = name.replace("_", " ")
    
    # Si tenemos contenido viejo, lo inyectamos; si no, dejamos un placeholder estructurado.
    content = old_contents.get(prefix)
    if not content:
        content = f"# {title_str}\n\n> 💡 **INFO**: Este capítulo está pendiente de redacción. Aquí se documentarán los procesos, arquitectura y reglas operativas correspondientes."
        
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)
        
    print(f"Created/Updated {filename}")

print("Book skeleton generated successfully.")
