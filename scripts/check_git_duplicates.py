#!/usr/bin/env python3
import sys
import fnmatch
from pathlib import Path

# Salvaguarda para prevenir UnicodeEncodeError en terminales de Windows
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except (AttributeError, IOError):
        pass

# Directorios a excluir del escaneo de duplicados
EXCLUDE_DIRS = {
    ".git",
    ".venv",
    ".cache",
    "node_modules",
    "__pycache__",
    "archive",
    "outputs",
    "data",
    "baselines_week0"  # Excluir baselines históricos
}

# Archivos específicos o patrones a verificar obligatoriamente si tienen duplicados
CRITICAL_PATTERNS = [
    "combo_loader.py",
    "*_config.json"
]

def scan_repo(root_dir: Path):
    duplicates_found = False
    seen_basenames = {}  # basename -> list of paths
    
    for path in root_dir.rglob("*"):
        # Omitir si está en un directorio excluido por defecto
        if any(part in EXCLUDE_DIRS for part in path.parts):
            continue
            
        # Omitir directorios de backup históricos para evitar falsos positivos
        if any(part.startswith("vps_backup_") or "vps_snapshot" in part or "archive" in part for part in path.parts):
            continue
            
        # Omitir submódulos legítimos o carpetas de datos de terceros como sp500/sp500
        if "sp500" in path.parts:
            continue

        # Verificar carpetas anidadas recursivas (ej. vps_snapshot/vps_snapshot)
        parts = path.parts
        for i in range(len(parts) - 1):
            if parts[i] == parts[i+1]:
                print(f"❌ ERROR: Carpeta anidada recursiva detectada en la ruta: '{path}'", file=sys.stderr)
                duplicates_found = True
        
        # Procesar solo archivos
        if path.is_file():
            name = path.name
            
            # __init__.py no se considera duplicado
            if name == "__init__.py":
                continue
                
            # Excluir archivos de código fuente que legítimamente comparten nombres pero están en módulos distintos
            if name in ("backtest.py", "structure_pivot.py"):
                continue

            # Verificar si coincide con patrones críticos (combo_loader.py, *_config.json)
            # O si es un archivo de código/configuración crítico (.py, .json) en src/ o config/
            is_critical = any(fnmatch.fnmatch(name, pattern) for pattern in CRITICAL_PATTERNS)
            is_source_code = path.suffix in (".py", ".json") and any(p in path.parts for p in ("src", "config"))
            
            if is_critical or is_source_code:
                seen_basenames.setdefault(name, []).append(path)
                
    # 2. Validar si hay duplicados
    for name, paths in seen_basenames.items():
        if len(paths) > 1:
            # Filtrar rutas activas excluyendo directorios oficiales y wrappers legítimos
            active_paths = []
            for p in paths:
                p_str = p.as_posix()
                if "outputs/best_combos_run" in p_str or "config/combo_results" in p_str or "config/combos" in p_str or "config/production_agents" in p_str:
                    continue
                if name == "combo_loader.py" and (p_str.endswith("config/combo_loader.py") or p_str.endswith("src/screeners/combo_loader.py")):
                    continue
                active_paths.append(p)

            if len(active_paths) > 1:
                print(f"❌ ERROR: Archivo duplicado '{name}' encontrado en múltiples rutas activas:", file=sys.stderr)
                for p in paths:
                    print(f"  - {p}", file=sys.stderr)
                duplicates_found = True
            
    return duplicates_found

def main():
    root = Path(__file__).resolve().parent.parent
    has_errors = scan_repo(root)
    if has_errors:
        print("\n💥 Pre-commit hook FAILED. Por favor corrige los errores anteriores antes de hacer commit.", file=sys.stderr)
        sys.exit(1)
    else:
        print("✅ No se detectaron duplicados ni carpetas recursivas.")
        sys.exit(0)

if __name__ == "__main__":
    main()
