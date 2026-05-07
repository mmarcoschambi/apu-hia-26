"""
src/screeners/combo_loader.py
Unificado con el cargador canónico en config/combo_loader.py.
"""

import logging
from typing import Dict, Any, List

from .registry import ScreenerRegistry
from .pipeline import ScreenerPipeline

# Importar del canónico (root config package)
try:
    from config.combo_loader import load_combo_configs, get_combo_by_name
except ImportError:
    # Si falla la importación directa, intentar via sys.path
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
    from config.combo_loader import load_combo_configs, get_combo_by_name

logger = logging.getLogger(__name__)


def load_combo(combo_name: str) -> Dict[str, Any]:
    """
    Carga configuración de un combo desde YAML (canónico)
    y lo devuelve como dict compatible con el sistema de screeners.
    """
    combos = load_combo_configs()
    combo = get_combo_by_name(combos, combo_name, require_go=False)
    if not combo:
        raise ValueError(f"Combo '{combo_name}' no encontrado en YAMLs (configs/combos/).")

    # Mapeo a estructura esperada por los screeners legacy (lo que antes era JSON)
    return {
        "name": combo.name,
        "status": combo.status,
        "description": combo.notes,
        "screener": {"name": combo.scanner_filter, "mode": "all"},
        "pattern": {"signal_type": combo.pattern_filter},
        "tier2_filters": {
            "min_rvol": combo.min_rvol,
            "min_adr": combo.min_adr,
            "min_consolidation_days": combo.min_consolidation_days,
            "rs_breakout_min": getattr(combo, "rs_breakout_min", None),
        },
        "tier3_fixed": {
            "max_positions": combo.max_positions,
            "max_position_pct": combo.max_position_pct,
            "max_exposure_pct": combo.max_exposure_pct,
        },
    }


def list_combos() -> List[str]:
    """Lista todos los combos disponibles (desde YAML)."""
    return [c.name for c in load_combo_configs()]


def build_combo_pipeline(combo_name: str) -> ScreenerPipeline:
    """
    Construye un ScreenerPipeline desde un combo YAML.
    Redirigido al cargador canónico para asegurar consistencia PBO.
    """
    combo_dict = load_combo(combo_name)
    screener_cfg = combo_dict["screener"]

    screener_name = screener_cfg["name"]
    mode = screener_cfg.get("mode", "all")

    # Cargar configuración desde el registro (buscará en config/screeners/)
    config = ScreenerRegistry.load_config(screener_name)
    screener = ScreenerRegistry.get(screener_name, config)

    return ScreenerPipeline([screener], mode=mode)


def get_combo_info(combo_name: str) -> Dict[str, Any]:
    """Retorna información resumida de un combo (desde YAML)."""
    return load_combo(combo_name)
