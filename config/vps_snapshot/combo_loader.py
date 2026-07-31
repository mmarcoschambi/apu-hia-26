"""
Combo Configuration Loader
===========================
Loads and validates combo configurations from YAML files in configs/combos/.

Usage:
    from config.combo_loader import load_combo_configs, get_combo_by_name

    combos = load_combo_configs()
    selected = get_combo_by_name(combos, "combo_pullback_entry")
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

import yaml

logger = logging.getLogger(__name__)

# Project root
BASE_DIR = Path(__file__).resolve().parent.parent
COMBOS_DIR = BASE_DIR / "configs" / "combos"


@dataclass
class ComboConfig:
    """Represents a validated combo configuration."""

    name: str
    status: str  # GO | NO-GO | PENDING

    # Validation metrics
    pbo: float = 0.0
    wf_sharpe_mean: float = 0.0
    wf_sharpe_min: float = 0.0
    wf_sortino_mean: float = 0.0
    wf_max_drawdown: float = 0.0

    # Scanner parameters
    scanner_filter: str = "default"
    screeners: List[str] = field(default_factory=list)
    mode: str = "all"
    pattern_filter: str = ""
    regime_blocked: List[int] = field(default_factory=list)

    # Transaction costs
    fee_rate: float = 0.001
    slippage_rate: float = 0.001

    # Market parameters
    spx_sma_period: int = 50
    vix_max: float = 25.0
    spx_vol_max: float = 20.0
    green_light_points: int = 5

    # Pattern parameters
    lookback_days: int = 180
    max_setups: int = 5
    flat_base_range_pct: float = 0.15
    vcp_contraction_threshold: float = 0.7
    min_rvol: float = 1.0
    min_adr: float = 1.0
    min_consolidation_days: int = 5
    rs_breakout_min: Optional[float] = None

    # Risk management
    max_positions: int = 4
    max_position_pct: float = 0.25
    max_exposure_pct: float = 0.65

    # UI alerts
    alerts: List[str] = field(default_factory=list)
    notes: str = ""

    @property
    def is_go(self) -> bool:
        return self.status == "GO"

    @property
    def cost_robustness(self) -> str:
        """Evaluates if combo can survive transaction costs."""
        total_cost_bps = (self.fee_rate + self.slippage_rate) * 10000 * 2  # entry + exit
        if total_cost_bps <= 20:
            return "ROBUSTO (breakeven ~20bps)"
        elif total_cost_bps <= 40:
            return "MODERADO (breakeven ~40bps)"
        else:
            return "FRAGIL (breakeven >40bps)"

    def validate(self) -> List[str]:
        """Validates combo config and returns list of warnings."""
        warnings = []

        # PBO alto = MALO (alto riesgo de overfitting)
        # PBO bajo = BUENO (robusto)
        if self.pbo > 0.70:
            warnings.append(f"PBO={self.pbo:.0%} — alto riesgo overfitting")
        elif self.pbo > 0.50:
            warnings.append(f"PBO={self.pbo:.0%} — moderado, monitorear")

        if self.wf_sharpe_mean < 1.0:
            warnings.append(f"Sharpe WF mean={self.wf_sharpe_mean:.2f} is low (<1.0)")

        if self.wf_max_drawdown > 0.25:
            warnings.append(f"Max drawdown={self.wf_max_drawdown:.0%} is high (>25%)")

        total_cost_bps = (self.fee_rate + self.slippage_rate) * 10000 * 2
        if total_cost_bps > 50:
            warnings.append(f"Total costs={total_cost_bps:.0f}bps are too high")

        return warnings


def load_combo_config(yaml_path: Path) -> ComboConfig:
    """Load a single combo config from YAML file."""
    if not yaml_path.exists():
        raise FileNotFoundError(f"Combo config not found: {yaml_path}")

    with open(yaml_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    # Validate required fields
    if "name" not in data:
        raise ValueError(f"Missing 'name' in {yaml_path}")
    if "status" not in data:
        raise ValueError(f"Missing 'status' in {yaml_path}")

    # Parse list fields
    regime_blocked = data.get("regime_blocked", [])
    if not isinstance(regime_blocked, list):
        regime_blocked = [int(regime_blocked)]

    alerts = data.get("alerts", [])
    if not isinstance(alerts, list):
        alerts = [alerts]

    return ComboConfig(
        name=data["name"],
        status=data["status"].upper(),
        pbo=float(data.get("pbo", 0.0)),
        wf_sharpe_mean=float(data.get("wf_sharpe_mean", 0.0)),
        wf_sharpe_min=float(data.get("wf_sharpe_min", 0.0)),
        wf_sortino_mean=float(data.get("wf_sortino_mean", 0.0)),
        wf_max_drawdown=float(data.get("wf_max_drawdown", 0.0)),
        scanner_filter=data.get("scanner_filter", "default"),
        screeners=data.get("screeners", []),
        mode=data.get("mode", "all"),
        pattern_filter=data.get("pattern_filter", ""),
        regime_blocked=regime_blocked,
        fee_rate=float(data.get("fee_rate", 0.001)),
        slippage_rate=float(data.get("slippage_rate", 0.001)),
        spx_sma_period=int(data.get("spx_sma_period", 50)),
        vix_max=float(data.get("vix_max", 25.0)),
        spx_vol_max=float(data.get("spx_vol_max", 20.0)),
        green_light_points=int(data.get("green_light_points", 5)),
        lookback_days=int(data.get("lookback_days", 180)),
        max_setups=int(data.get("max_setups", 5)),
        flat_base_range_pct=float(data.get("flat_base_range_pct", 0.15)),
        vcp_contraction_threshold=float(data.get("vcp_contraction_threshold", 0.7)),
        min_rvol=float(data.get("min_rvol", 1.0)),
        min_adr=float(data.get("min_adr", 1.0)),
        min_consolidation_days=int(data.get("min_consolidation_days", 5)),
        rs_breakout_min=(
            float(data["rs_breakout_min"]) if data.get("rs_breakout_min") is not None else None
        ),
        max_positions=int(data.get("max_positions", 4)),
        max_position_pct=float(data.get("max_position_pct", 0.25)),
        max_exposure_pct=float(data.get("max_exposure_pct", 0.65)),
        alerts=alerts,
        notes=data.get("notes", ""),
    )


def load_combo_configs(combos_dir: Path | None = None) -> List[ComboConfig]:
    """Load all combo configs from the combos directory."""
    target_dir = combos_dir or COMBOS_DIR

    if not target_dir.exists():
        logger.warning(f"Combos directory not found: {target_dir}")
        return []

    configs = []
    for yaml_file in sorted(target_dir.glob("combo_*.yaml")):
        try:
            config = load_combo_config(yaml_file)
            configs.append(config)

            # Log validation warnings
            warnings = config.validate()
            if warnings:
                logger.warning(f"Combo '{config.name}' warnings: {warnings}")
            else:
                logger.info(f"✅ Loaded combo '{config.name}' (status={config.status})")

        except Exception as e:
            logger.error(f"Failed to load {yaml_file}: {e}")

    return configs


def get_combo_by_name(
    combos: List[ComboConfig], name: str, require_go: bool = True
) -> Optional[ComboConfig]:
    """Get a specific combo by name."""
    for combo in combos:
        if combo.name == name:
            if require_go and not combo.is_go:
                logger.warning(f"Combo '{name}' is not GO (status={combo.status})")
                return None
            return combo

    logger.error(f"Combo '{name}' not found")
    return None


def get_go_combos(combos: List[ComboConfig]) -> List[ComboConfig]:
    """Filter only GO combos."""
    return [c for c in combos if c.is_go]


def save_combo_config(config: ComboConfig, combos_dir: Path | None = None) -> Path:
    """Save a combo config to YAML file. Used by optimizer_3tier."""
    target_dir = combos_dir or COMBOS_DIR
    target_dir.mkdir(parents=True, exist_ok=True)

    yaml_path = target_dir / f"{config.name}.yaml"

    data = {
        "name": config.name,
        "status": config.status,
        "pbo": config.pbo,
        "wf_sharpe_mean": config.wf_sharpe_mean,
        "wf_sharpe_min": config.wf_sharpe_min,
        "wf_sortino_mean": config.wf_sortino_mean,
        "wf_max_drawdown": config.wf_max_drawdown,
        "scanner_filter": config.scanner_filter,
        "screeners": getattr(config, "screeners", []),
        "mode": getattr(config, "mode", "all"),
        "pattern_filter": config.pattern_filter,
        "regime_blocked": config.regime_blocked,
        "fee_rate": config.fee_rate,
        "slippage_rate": config.slippage_rate,
        "spx_sma_period": config.spx_sma_period,
        "vix_max": config.vix_max,
        "spx_vol_max": config.spx_vol_max,
        "green_light_points": config.green_light_points,
        "lookback_days": config.lookback_days,
        "max_setups": config.max_setups,
        "flat_base_range_pct": config.flat_base_range_pct,
        "vcp_contraction_threshold": config.vcp_contraction_threshold,
        "min_rvol": config.min_rvol,
        "min_adr": config.min_adr,
        "min_consolidation_days": config.min_consolidation_days,
        "rs_breakout_min": config.rs_breakout_min,
        "max_positions": config.max_positions,
        "max_position_pct": config.max_position_pct,
        "max_exposure_pct": config.max_exposure_pct,
        "alerts": config.alerts,
        "notes": config.notes,
    }

    with open(yaml_path, "w", encoding="utf-8") as f:
        yaml.dump(data, f, default_flow_style=False, sort_keys=False, allow_unicode=True)

    logger.info(f"💾 Saved combo '{config.name}' to {yaml_path}")
    return yaml_path


if __name__ == "__main__":
    # Test loading combos
    logging.basicConfig(level=logging.INFO)

    combos = load_combo_configs()
    go_combos = get_go_combos(combos)

    print(f"\nLoaded {len(combos)} combos, {len(go_combos)} are GO:")
    for combo in go_combos:
        print(f"  - {combo.name}: Sharpe={combo.wf_sharpe_mean:.2f}, PBO={combo.pbo:.0%}")
