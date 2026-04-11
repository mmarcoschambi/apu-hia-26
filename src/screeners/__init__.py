"""
src/screeners/__init__.py
"""

from .base import BaseScreener, ScreenerResult, ScreenerConfig
from .registry import ScreenerRegistry
from .pipeline import ScreenerPipeline
from .combo_loader import load_combo, list_combos, build_combo_pipeline, get_combo_info

# Importar screeners para que se auto-registren via @ScreenerRegistry.register
from . import minervini_trend  # noqa: F401
from . import ema21_pullback  # noqa: F401
from . import qullamaggie_momentum  # noqa: F401
from . import vcp_enhanced  # noqa: F401
from . import universal_any  # noqa: F401
from . import triad_rts  # noqa: F401

__all__ = [
    "BaseScreener",
    "ScreenerResult",
    "ScreenerConfig",
    "ScreenerRegistry",
    "ScreenerPipeline",
    "load_combo",
    "list_combos",
    "build_combo_pipeline",
    "get_combo_info",
]
