#!/usr/bin/env python3
"""
scripts/cleanup_backups.py
Busca y elimina de forma definitiva cualquier archivo de copia de seguridad o
backup huerfano (*.bak, *.backup, etc.) en el directorio src/, siguiendo las
pautas de higiene de DEVELOPER_RULES.md.
"""

import os
from pathlib import Path
import logging

# Configurar logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)-8s | %(message)s")
logger = logging.getLogger("cleanup_backups")

PROJECT_ROOT = Path(__file__).parent.parent
SRC_DIR = PROJECT_ROOT / "src"

# Patrones comunes de copias de seguridad a limpiar
BACKUP_PATTERNS = [".bak", ".backup", ".tmp", "copy", "_backup"]

def run_cleanup() -> None:
    """
    Busca archivos temporales o de backup recursivamente en src/ y los elimina.
    """
    logger.info(f"Iniciando escaneo de backups en {SRC_DIR}...")
    
    if not SRC_DIR.exists():
        logger.error(f"El directorio {SRC_DIR} no existe.")
        return
        
    cleaned_count = 0
    
    for root, dirs, files in os.walk(SRC_DIR):
        for f in files:
            f_lower = f.lower()
            # Identificar si coincide con algun patron de backup
            is_backup = any(f_lower.endswith(pat) or pat in f_lower for pat in BACKUP_PATTERNS)
            
            # Excepciones legitimas (e.g. archivos de test que contengan 'copy' o 'tmp' en el path)
            if "test" in root or f.startswith("test_"):
                continue
                
            if is_backup:
                file_path = Path(root) / f
                try:
                    try:
                        display_path = file_path.relative_to(PROJECT_ROOT)
                    except ValueError:
                        display_path = file_path
                    logger.info(f"Eliminando archivo de backup: {display_path}")
                    file_path.unlink()
                    cleaned_count += 1
                except Exception as e:
                    logger.error(f"Error al eliminar {file_path}: {e}")
                    
    logger.info(f"Limpieza completada. Archivos eliminados: {cleaned_count}")

if __name__ == "__main__":
    run_cleanup()
