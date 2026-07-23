"""
test_integrity.py — Pruebas de integridad del repositorio y estructura de archivos
"""

import sys
from pathlib import Path

# Añadir la raíz al path para poder importar desde scripts
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.check_git_duplicates import scan_repo


def test_repository_integrity():
    """Verifica que no existan carpetas anidadas corruptas ni duplicados activos."""
    root_dir = Path(__file__).resolve().parent.parent
    has_errors = scan_repo(root_dir)
    assert has_errors is False, (
        "Se detectaron errores de duplicación o carpetas recursivas corruptas. "
        "Correr python3 scripts/check_git_duplicates.py para ver detalles."
    )
