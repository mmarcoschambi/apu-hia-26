"""
src/screeners/combo_loader.py
Carga y aplica combos Screener × Pattern desde config/combos/.
"""

import json
import logging
from pathlib import Path
from typing import Dict, Any, List

from .registry import ScreenerRegistry
from .pipeline import ScreenerPipeline

logger = logging.getLogger(__name__)

COMBOS_DIR = Path(__file__).resolve().parent.parent.parent / "config" / "combos"


def load_combo(combo_name: str) -> Dict[str, Any]:
    """Carga configuración de un combo desde JSON."""
    path = COMBOS_DIR / f"{combo_name}.json"
    if not path.exists():
        available = [c.stem for c in COMBOS_DIR.glob("*.json")]
        raise ValueError(
            f"Combo '{combo_name}' no encontrado. Disponibles: {available}"
        )
    with open(path, "r") as f:
        return json.load(f)


def list_combos() -> List[str]:
    """Lista todos los combos disponibles."""
    return [c.stem for c in COMBOS_DIR.glob("*.json")]


def build_combo_pipeline(combo_name: str) -> ScreenerPipeline:
    """
    Construye un ScreenerPipeline desde un combo config.

    Returns:
        ScreenerPipeline configurado con el screener y modo del combo.
    """
    combo = load_combo(combo_name)
    screener_cfg = combo["screener"]

    screener_name = screener_cfg["name"]
    mode = screener_cfg.get("mode", "all")
    config_path = screener_cfg.get("config")

    config = ScreenerRegistry.load_config(screener_name, config_path)
    screener = ScreenerRegistry.get(screener_name, config)

    return ScreenerPipeline([screener], mode=mode)


def get_combo_info(combo_name: str) -> Dict[str, Any]:
    """Retorna información resumida de un combo."""
    combo = load_combo(combo_name)
    return {
        "name": combo["name"],
        "description": combo.get("description", ""),
        "screener": combo["screener"]["name"],
        "pattern": combo["pattern"]["signal_type"],
        "tier2_filters": combo.get("tier2_filters", {}),
        "tier3_fixed": combo.get("tier3_fixed", {}),
    }
