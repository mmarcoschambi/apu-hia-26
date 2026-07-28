"""
Wrapper for Combo Configuration Loader
=======================================

⚠️ DEPRECATED: This module is a legacy wrapper.

The canonical combo loader is now in src/integration/combo_loader.py
which supports JSON-based configs (both base and optimized).

For backward compatibility, this module still works but delegates
to the canonical implementation.

Usage (NEW, recommended):
    from src.integration.combo_loader import load_combo_merged

    cfg, meta = load_combo_merged("combo_pure_momentum")

Usage (OLD, still supported):
    from config.combo_loader import load_combo_configs

    combos = load_combo_configs()
    selected = get_combo_by_name(combos, "combo_pullback_entry")
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import List, Optional

logger = logging.getLogger(__name__)

# Project root
BASE_DIR = Path(__file__).resolve().parent.parent


def load_combo_configs(combos_dir: Path | None = None) -> List[dict]:
    """
    LEGACY: Load all combo configs from base directory (JSON).
    
    Delegates to src/integration/combo_loader.py for consistency.
    Returns list of dicts for backward compatibility with YAML-based callers.
    """
    logger.warning(
        "load_combo_configs() is legacy and reads JSON from config/combos/. "
        "Use src.integration.combo_loader.load_combo_merged() for production."
    )
    
    from src.integration.combo_loader import load_combo_base_only
    
    target_dir = combos_dir or (BASE_DIR / "config" / "combos")
    
    if not target_dir.exists():
        logger.warning(f"Combos directory not found: {target_dir}")
        return []
    
    configs = []
    for json_file in sorted(target_dir.glob("combo_*.json")):
        try:
            cfg = load_combo_base_only(json_file.stem.replace("combo_", ""))
            configs.append(cfg)
            logger.info(f"✅ Loaded combo '{cfg.get('name', json_file.stem)}' (legacy loader)")
        except Exception as e:
            logger.error(f"Failed to load {json_file}: {e}")
    
    return configs


def get_combo_by_name(
    combos: List[dict], name: str, require_go: bool = True
) -> Optional[dict]:
    """
    LEGACY: Get a specific combo by name from list.
    
    Args:
        combos: List of combo dicts from load_combo_configs()
        name: Combo name
        require_go: Ignored (legacy param)
    
    Returns:
        Combo dict or None
    """
    for combo in combos:
        if combo.get("name") == name:
            return combo
    
    logger.error(f"Combo '{name}' not found")
    return None


def get_go_combos(combos: List[dict]) -> List[dict]:
    """LEGACY: Filter only GO combos (status='GO'). Ignores for JSON."""
    return [c for c in combos if c.get("status") in ("GO", None)]


def load_combo_merged_canonical(name: str) -> tuple[dict, dict]:
    """
    CANONICAL: Load combo with merge (base + optimized).
    
    Delegates to src/integration/combo_loader for the authoritative
    implementation. Use this for new code.
    
    Returns:
        (cfg, meta) — config and metadata about the merge
    """
    from src.integration.combo_loader import load_combo_merged
    
    cfg, meta = load_combo_merged(name)
    return cfg, meta.__dict__ if hasattr(meta, '__dict__') else meta


if __name__ == "__main__":
    # Test legacy loader
    logging.basicConfig(level=logging.INFO)
    
    combos = load_combo_configs()
    go_combos = get_go_combos(combos)
    
    print(f"\nLoaded {len(combos)} combos, {len(go_combos)} are GO:")
    for combo in go_combos:
        print(f"  - {combo.get('name')}: {combo.get('screener', 'N/A')}")
