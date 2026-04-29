"""
src/integration/combo_loader.py

Loader unificado de configs de combo.

Jerarquía de resolución:
  1. config/combos/{name}.json          — base estructural (screener, pattern, tier2 base)
  2. outputs/best_combos_run/{name}_config.json  — parámetros optimizados (tier2, tier1, tier3)


Merge por secciones: los parámetros optimizados sobreescriben los base en
tier2_filters, tier1_strategy y tier3_risk. screener y pattern nunca se tocan.

Uso:
    from src.integration.combo_loader import load_combo_merged

    cfg, meta = load_combo_merged("combo_pure_momentum")
    # meta.source == "base_plus_best" | "base_only"
    # meta.best_combo_file == Path(...) | None
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Optional

logger = logging.getLogger(__name__)


# Rutas relativas a PROJECT_ROOT — se resuelven en runtime
_HERE = Path(__file__).resolve()
# src/integration/combo_loader.py → subir 3 niveles → PROJECT_ROOT
PROJECT_ROOT = _HERE.parents[2]


COMBOS_DIR = PROJECT_ROOT / "config" / "combos"
BEST_COMBOS_DIR = PROJECT_ROOT / "outputs" / "best_combos_run"

ComboSource = Literal["base_only", "base_plus_best"]


@dataclass
class ComboLoadMeta:
    name: str
    source: ComboSource
    base_file: Path
    best_combo_file: Optional[Path]
    sections_merged: list[str]  # qué secciones se sobreescribieron


def _deep_merge(base: dict, override: dict) -> dict:
    """Merge superficial por clave — override gana en conflicto."""
    result = dict(base)
    result.update(override)
    return result


def load_combo_merged(
    name: str,
    combos_dir: Optional[Path] = None,
    best_combos_dir: Optional[Path] = None,
    require_best: bool = False,
) -> tuple[dict, ComboLoadMeta]:
    """
    Carga config de combo con merge base + optimizado.

    Args:
        name:             nombre del combo (ej. "combo_pure_momentum")
        combos_dir:       override de COMBOS_DIR (útil en tests)
        best_combos_dir:  override de BEST_COMBOS_DIR (útil en tests)
        require_best:     si True, lanza FileNotFoundError si no hay best config

    Returns:
        (cfg, meta)
        cfg  — dict con config mergeada, lista para pasar a evaluate_ticker
        meta — ComboLoadMeta con trazabilidad del origen
    """
    _combos_dir = combos_dir or COMBOS_DIR
    _best_dir = best_combos_dir or BEST_COMBOS_DIR

    # 1. Cargar base — obligatorio
    base_path = _combos_dir / f"{name}.json"
    if not base_path.exists():
        # fallback: config/production_agents/{name}_config.json
        alt = PROJECT_ROOT / "config" / "production_agents" / f"{name}_config.json"

        if alt.exists():
            base_path = alt
        else:
            raise FileNotFoundError(
                f"Base combo config not found for '{name}'. Tried: {base_path}, {alt}"
            )

    cfg = json.loads(base_path.read_text())

    # 2. Intentar cargar optimizado
    best_path = _best_dir / f"{name}_config.json"
    if not best_path.exists():
        if require_best:
            raise FileNotFoundError(
                f"Best combo config required but not found: {best_path}"
            )
        logger.warning(
            "combo_loader: no best config found for '%s' at %s — using base only",
            name,
            best_path,
        )
        meta = ComboLoadMeta(
            name=name,
            source="base_only",
            base_file=base_path,
            best_combo_file=None,
            sections_merged=[],
        )
        return cfg, meta

    best = json.loads(best_path.read_text())
    sections_merged: list[str] = []

    # 3. Merge por secciones — screener y pattern nunca se tocan
    #    tier2_filters: merge profundo (best gana por clave, preserva claves base ausentes en best)
    if "tier2_filters" in best:
        base_t2 = cfg.get("tier2_filters", {})
        best_t2 = best["tier2_filters"]
        # filtrar claves internas de stats/debug que no son parámetros operativos
        best_t2_clean = {k: v for k, v in best_t2.items() if not k.startswith("_")}
        cfg["tier2_filters"] = _deep_merge(base_t2, best_t2_clean)
        sections_merged.append("tier2_filters")

    #    tier1_strategy: reemplaza completo si existe en best
    if "tier1_strategy" in best:
        cfg["tier1_strategy"] = best["tier1_strategy"]
        sections_merged.append("tier1_strategy")
    elif "tier1_exits" in best:
        # normalización: algunos runs exportan tier1_exits en vez de tier1_strategy
        cfg["tier1_strategy"] = best["tier1_exits"]

        sections_merged.append("tier1_strategy (from tier1_exits)")

    #    tier3_risk: reemplaza completo si existe en best
    if "tier3_risk" in best:
        cfg["tier3_risk"] = best["tier3_risk"]
        sections_merged.append("tier3_risk")
    elif "tier3_fixed" in cfg and "tier3_risk" not in cfg:
        # base usa tier3_fixed — mantener como está, no hay override
        pass

    meta = ComboLoadMeta(
        name=name,
        source="base_plus_best",
        base_file=base_path,
        best_combo_file=best_path,
        sections_merged=sections_merged,
    )

    logger.info(
        "combo_loader: '%s' loaded from base+best, merged sections: %s",
        name,
        sections_merged,
    )

    return cfg, meta


def load_combo_base_only(name: str, combos_dir: Optional[Path] = None) -> dict:
    """
    Carga solo la config base, sin merge. Equivalente al load_combo original.
    Útil para comparación o cuando se quiere comportamiento legacy.
    """

    _combos_dir = combos_dir or COMBOS_DIR
    for p in [
        _combos_dir / f"{name}.json",
        PROJECT_ROOT / "config" / "production_agents" / f"{name}_config.json",
    ]:
        if p.exists():
            return json.loads(p.read_text())
    raise FileNotFoundError(f"Combo {name} not found in base dirs")


def print_effective_combo_diff(combo_name: str) -> None:
    """
    Imprime diff entre base y config mergeada (para debugging/auditoría).
    """
    base, meta = load_combo_merged(combo_name)

    print(f"\n{'=' * 60}")
    print(f"CONFIG DIFF: {combo_name}")
    print(f"{'=' * 60}")
    print(f"Source: {meta.source}")
    if meta.best_combo_file:
        print(f"Best combo file: {meta.best_combo_file}")
    print(f"Merged sections: {meta.sections_merged}")

    if meta.source == "base_only":
        print("\nNo optimized config available — using base only.")
        return

    # Detectar valores críticos que cambiaron
    critical_keys = {
        "tier2_filters": ["min_rs_percentile", "min_dollar_volume", "min_rvol"],
        "tier1_strategy": ["tp1_r", "tp2_r", "tp1_pct", "tp2_pct"],
        "tier3_risk": ["risk_fraction"],
    }

    for section, keys in critical_keys.items():
        if section in meta.sections_merged:
            print(f"\n📂 {section} CHANGED:")
            base_section = base.get(section, {})
            for key in keys:
                if key in base_section:
                    print(f"  {key}: {base_section[key]} → {base[section][key]}")
                else:
                    print(f"  {key}: (new) {base[section][key]}")

    print(f"\n{'=' * 60}")
