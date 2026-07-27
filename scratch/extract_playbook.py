import ast
import os
import re
import textwrap

file_path = "src/ui/agent_playbook_ui.py"
out_dir = "apps/playbook/Assets/Docs"
os.makedirs(out_dir, exist_ok=True)

with open(file_path, "r", encoding="utf-8") as f:
    source = f.read()

tree = ast.parse(source)

def replace_unicode_tags(text):
    # Reemplaza [U+XXXX] por el emoji real
    def replacer(match):
        hex_val = match.group(1)
        try:
            return chr(int(hex_val, 16))
        except:
            return match.group(0)
    return re.sub(r"\[U\+([0-9A-Fa-f]+)\]", replacer, text)

def extract_strings(node):
    text_blocks = []
    for child in ast.walk(node):
        if isinstance(child, ast.Call):
            if isinstance(child.func, ast.Attribute) and getattr(child.func.value, "id", "") == "st":
                func_name = child.func.attr
                if func_name in ["markdown", "subheader", "title", "text", "success", "info", "warning", "error", "code"]:
                    if child.args and isinstance(child.args[0], ast.Constant):
                        val = child.args[0].value
                        if isinstance(val, str):
                            val = replace_unicode_tags(val)
                            
                            # Si es un string multilínea, aplicamos dedent para que no se rompa el markdown
                            if "\n" in val:
                                val = textwrap.dedent(val).strip()

                            if func_name == "subheader":
                                text_blocks.append(f"## {val}")
                            elif func_name == "title":
                                text_blocks.append(f"# {val}")
                            elif func_name == "code":
                                lang = "text"
                                for kw in child.keywords:
                                    if kw.arg == "language" and isinstance(kw.value, ast.Constant):
                                        lang = kw.value.value
                                text_blocks.append(f"```{lang}\n{val}\n```")
                            elif func_name == "success":
                                text_blocks.append(f"> ✔️ **ÉXITO**: {val}")
                            elif func_name == "info":
                                text_blocks.append(f"> 💡 **INFO**: {val}")
                            elif func_name == "warning":
                                text_blocks.append(f"> ⚠️ **ADVERTENCIA**: {val}")
                            elif func_name == "error":
                                text_blocks.append(f"> ❌ **ERROR**: {val}")
                            else:
                                text_blocks.append(val)
    return "\n\n".join(text_blocks)

chapters = [
    ("1_Memory_Board", "tab_memory"),
    ("2_Ciclo_de_Vida", "tab_workflow"),
    ("3_Test_Harness", "tab_tdd"),
    ("4_Investigacion", "tab_research"),
    ("5_Backlog", "tab_backlog"),
    ("6_Primeros_Principios", "tab_first_principles"),
    ("7_Evolucion_Arquitectura", "tab_evolution"),
    ("8_Cheat_Sheet_Prompts", "tab_prompts")
]

for class_node in tree.body:
    if isinstance(class_node, ast.FunctionDef) and class_node.name == "render_agent_playbook":
        for stmt in class_node.body:
            if isinstance(stmt, ast.With):
                for item in stmt.items:
                    context_expr = item.context_expr
                    if isinstance(context_expr, ast.Name):
                        for title, tab_var in chapters:
                            if context_expr.id == tab_var:
                                content = extract_strings(stmt)
                                with open(os.path.join(out_dir, f"{title}.md"), "w", encoding="utf-8") as out_f:
                                    out_f.write(content)
                                print(f"Extracted {title}.md")

print("Done.")
