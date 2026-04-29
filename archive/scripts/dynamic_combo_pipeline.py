#!/usr/bin/env python3
"""
Dynamic Combo Pipeline
======================
Integrates optimizer_3tier, walk_forward validation, and decision gate
to automatically generate and validate combo configs.

Pipeline:
    optimizer_3tier.py generates Golden Config
          │
          ▼
    walk_forward_combos.py validates OOS
          │
          ▼
    decision_gate.py emits GO/NO-GO
          │
          ├─ GO → writes configs/combos/combo_X.yaml with status: GO
          │        Streamlit detects on next reload
          │
          └─ NO-GO → writes status: NO-GO
                      Streamlit shows as unavailable but visible

Usage:
    python3 dynamic_combo_pipeline.py --name combo_new_setup --trials 50
    python3 dynamic_combo_pipeline.py --validate-all  # Re-validate all existing combos
"""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from config.combo_loader import (
    ComboConfig,
    load_combo_configs,
    save_combo_config,
)

logger = logging.getLogger(__name__)


# ============================================================================
# DECISION GATE
# ============================================================================

class DecisionGate:
    """Evaluates if a combo passes validation criteria."""

    def __init__(
        self,
        max_pbo: float = 0.30,
        min_wf_sharpe: float = 1.0,
        max_wf_drawdown: float = 0.25,
        min_wf_sharpe_min: float = 0.8,
        max_cost_bps: float = 60,
    ):
        self.max_pbo = max_pbo
        self.min_wf_sharpe = min_wf_sharpe
        self.max_wf_drawdown = max_wf_drawdown
        self.min_wf_sharpe_min = min_wf_sharpe_min
        self.max_cost_bps = max_cost_bps

    def evaluate(self, metrics: Dict) -> tuple[bool, List[str]]:
        """
        Evaluates combo metrics against decision criteria.

        Args:
            metrics: Dict with pbo, wf_sharpe_mean, wf_sharpe_min, wf_max_drawdown, etc.

        Returns:
            (passed, reasons) tuple
        """
        reasons = []
        passed = True

        # PBO check: PBO alto = MALO (overfitting), PBO bajo = BUENO
        pbo = metrics.get('pbo', 0.0)
        if pbo > self.max_pbo:
            passed = False
            reasons.append(f"PBO={pbo:.0%} > {self.max_pbo:.0%} (overfitting risk)")
        else:
            reasons.append(f"PBO={pbo:.0%} <= {self.max_pbo:.0%} (robust) ✅")
        
        # Walk-forward Sharpe mean
        wf_sharpe_mean = metrics.get('wf_sharpe_mean', 0.0)
        if wf_sharpe_mean < self.min_wf_sharpe:
            passed = False
            reasons.append(f"WF Sharpe mean={wf_sharpe_mean:.2f} < {self.min_wf_sharpe}")
        else:
            reasons.append(f"WF Sharpe mean={wf_sharpe_mean:.2f} >= {self.min_wf_sharpe} ✅")
        
        # Walk-forward Sharpe min
        wf_sharpe_min = metrics.get('wf_sharpe_min', 0.0)
        if wf_sharpe_min < self.min_wf_sharpe_min:
            passed = False
            reasons.append(f"WF Sharpe min={wf_sharpe_min:.2f} < {self.min_wf_sharpe_min}")
        else:
            reasons.append(f"WF Sharpe min={wf_sharpe_min:.2f} >= {self.min_wf_sharpe_min} ✅")
        
        # Max drawdown
        wf_max_dd = metrics.get('wf_max_drawdown', 1.0)
        if wf_max_dd > self.max_wf_drawdown:
            passed = False
            reasons.append(f"Max DD={wf_max_dd:.0%} > {self.max_wf_drawdown:.0%}")
        else:
            reasons.append(f"Max DD={wf_max_dd:.0%} <= {self.max_wf_drawdown:.0%} ✅")
        
        # Cost robustness
        fee_rate = metrics.get('fee_rate', 0.001)
        slippage_rate = metrics.get('slippage_rate', 0.001)
        total_cost_bps = (fee_rate + slippage_rate) * 10000 * 2
        if total_cost_bps > self.max_cost_bps:
            passed = False
            reasons.append(f"Costs={total_cost_bps:.0f}bps > {self.max_cost_bps:.0f}bps")
        else:
            reasons.append(f"Costs={total_cost_bps:.0f}bps <= {self.max_cost_bps:.0f}bps ✅")
        
        return passed, reasons


# ============================================================================
# OPTIMIZER SIMULATION (placeholder for real optimizer_3tier integration)
# ============================================================================

def run_optimizer_3tier(
    combo_name: str,
    trials: int = 50,
    tickers: Optional[List[str]] = None,
    start_date: str = "2023-01-01",
    end_date: str = "2024-12-31",
) -> Dict:
    """
    Simulates optimizer_3tier output.
    
    In production, this would call the real optimizer and return golden config.
    For now, returns simulated metrics for demonstration.
    """
    logger.info(f"Running optimizer_3tier for '{combo_name}' ({trials} trials)...")
    
    # TODO: Integrate with real optimizer_3tier.py
    # For now, simulate with realistic metrics
    np.random.seed(42)
    
    simulated_metrics = {
        'pbo': float(np.random.beta(20, 5)),  # ~80% mean
        'wf_sharpe_mean': float(np.random.normal(1.5, 0.3)),
        'wf_sharpe_min': float(np.random.normal(1.2, 0.2)),
        'wf_sortino_mean': float(np.random.normal(2.0, 0.4)),
        'wf_max_drawdown': float(np.random.beta(2, 10)),
        'fee_rate': 0.001,
        'slippage_rate': 0.001,
    }
    
    logger.info("Optimizer results:")
    for k, v in simulated_metrics.items():
        if isinstance(v, float) and v < 1:
            logger.info(f"  {k}: {v:.2%}" if v < 0.1 else f"  {k}: {v:.2f}")
        else:
            logger.info(f"  {k}: {v}")
    
    return simulated_metrics


# ============================================================================
# WALK-FORWARD VALIDATION (placeholder for real walk_forward_combos integration)
# ============================================================================

def run_walk_forward_validation(
    combo_name: str,
    optimizer_metrics: Dict,
) -> Dict:
    """
    Simulates walk-forward OOS validation.
    
    In production, this would call walk_forward_combos.py and return OOS metrics.
    """
    logger.info(f"Running walk-forward validation for '{combo_name}'...")
    
    # TODO: Integrate with real walk_forward_combos.py
    # Simulate OOS metrics (typically slightly worse than IS)
    degradation = np.random.uniform(0.05, 0.15)
    
    oos_metrics = {
        'oos_sharpe_mean': optimizer_metrics['wf_sharpe_mean'] * (1 - degradation),
        'oos_sharpe_min': optimizer_metrics['wf_sharpe_min'] * (1 - degradation),
        'oos_max_drawdown': optimizer_metrics['wf_max_drawdown'] * (1 + degradation),
        'oos_win_rate': float(np.random.normal(0.55, 0.1)),
        'degradation_pct': degradation,
    }
    
    logger.info("OOS results:")
    for k, v in oos_metrics.items():
        if isinstance(v, float) and v < 1:
            logger.info(f"  {k}: {v:.2%}" if v < 0.1 else f"  {k}: {v:.2f}")
        else:
            logger.info(f"  {k}: {v}")
    
    return oos_metrics


# ============================================================================
# COMBO GENERATOR
# ============================================================================

def generate_combo_config(
    name: str,
    optimizer_metrics: Dict,
    oos_metrics: Dict,
    gate_passed: bool,
    gate_reasons: List[str],
) -> ComboConfig:
    """Generates a ComboConfig from optimization and validation results."""
    
    status = "GO" if gate_passed else "NO-GO"
    
    # Generate alerts based on metrics
    alerts = []
    pbo = optimizer_metrics.get('pbo', 0)
    if pbo < 0.80:
        alerts.append(f"⚠️ PBO={pbo:.0%} — moderate, monitor closely")
    else:
        alerts.append(f"PBO={pbo:.0%} — robust")
    
    degradation = oos_metrics.get('degradation_pct', 0)
    if degradation > 0.10:
        alerts.append(f"⚠️ OOS degradation={degradation:.0%} — high")
    
    cost_bps = (optimizer_metrics.get('fee_rate', 0.001) + optimizer_metrics.get('slippage_rate', 0.001)) * 10000 * 2
    if cost_bps > 40:
        alerts.append(f"⚠️ Costs={cost_bps:.0f}bps — may reduce edge")
    
    # Generate notes
    notes = (
        f"Auto-generated by dynamic_combo_pipeline.py on {datetime.now().strftime('%Y-%m-%d')}.\n"
        f"Gate: {'PASSED' if gate_passed else 'FAILED'}\n"
        + "\n".join(gate_reasons)
    )
    
    return ComboConfig(
        name=name,
        status=status,
        pbo=optimizer_metrics.get('pbo', 0.0),
        wf_sharpe_mean=optimizer_metrics.get('wf_sharpe_mean', 0.0),
        wf_sharpe_min=optimizer_metrics.get('wf_sharpe_min', 0.0),
        wf_sortino_mean=optimizer_metrics.get('wf_sortino_mean', 0.0),
        wf_max_drawdown=optimizer_metrics.get('wf_max_drawdown', 0.0),
        fee_rate=optimizer_metrics.get('fee_rate', 0.001),
        slippage_rate=optimizer_metrics.get('slippage_rate', 0.001),
        alerts=alerts,
        notes=notes,
    )


# ============================================================================
# MAIN PIPELINE
# ============================================================================

def run_pipeline(
    combo_name: str,
    trials: int = 50,
    gate: Optional[DecisionGate] = None,
) -> ComboConfig:
    """
    Runs the complete dynamic combo pipeline.
    
    Args:
        combo_name: Name for the new combo
        trials: Number of optimization trials
        gate: DecisionGate instance (uses defaults if None)
        
    Returns:
        Generated ComboConfig
    """
    gate = gate or DecisionGate()
    
    print("\n" + "="*80)
    print(f"🚀 DYNAMIC COMBO PIPELINE — {combo_name}")
    print("="*80)
    
    # Step 1: Optimizer
    print("\n📊 Step 1: Running optimizer_3tier...")
    optimizer_metrics = run_optimizer_3tier(combo_name, trials)
    
    # Step 2: Walk-Forward Validation
    print("\n🔍 Step 2: Running walk-forward OOS validation...")
    oos_metrics = run_walk_forward_validation(combo_name, optimizer_metrics)
    
    # Step 3: Decision Gate
    print("\n🚦 Step 3: Evaluating decision gate...")
    combined_metrics = {**optimizer_metrics, **oos_metrics}
    gate_passed, gate_reasons = gate.evaluate(combined_metrics)
    
    print(f"\nGate: {'✅ PASSED' if gate_passed else '❌ FAILED'}")
    for reason in gate_reasons:
        print(f"  {reason}")
    
    # Step 4: Generate Combo Config
    print("\n📝 Step 4: Generating combo config...")
    combo_config = generate_combo_config(
        combo_name,
        optimizer_metrics,
        oos_metrics,
        gate_passed,
        gate_reasons,
    )
    
    # Step 5: Save to YAML
    print("\n💾 Step 5: Saving to YAML...")
    yaml_path = save_combo_config(combo_config)
    print(f"✅ Saved to {yaml_path}")
    
    return combo_config


def validate_all_existing_combos(
    gate: Optional[DecisionGate] = None,
) -> List[ComboConfig]:
    """Re-validates all existing combos and updates their status."""
    gate = gate or DecisionGate()
    
    combos = load_combo_configs()
    updated = []
    
    print("\n" + "="*80)
    print("🔄 RE-VALIDATING ALL EXISTING COMBOS")
    print("="*80)
    
    for combo in combos:
        print(f"\n{'─'*80}")
        print(f"Validating: {combo.name} (current status: {combo.status})")
        
        # Simulate re-validation (in production, would call real optimizer/WF)
        metrics = {
            'pbo': combo.pbo,
            'wf_sharpe_mean': combo.wf_sharpe_mean,
            'wf_sharpe_min': combo.wf_sharpe_min,
            'wf_max_drawdown': combo.wf_max_drawdown,
            'fee_rate': combo.fee_rate,
            'slippage_rate': combo.slippage_rate,
        }
        
        passed, reasons = gate.evaluate(metrics)
        
        # Update status
        old_status = combo.status
        combo.status = "GO" if passed else "NO-GO"
        
        print(f"  {old_status} → {combo.status}")
        for reason in reasons:
            print(f"    {reason}")
        
        # Save updated config
        save_combo_config(combo)
        updated.append(combo)
    
    print(f"\n✅ Updated {len(updated)} combos")
    go_count = sum(1 for c in updated if c.is_go)
    print(f"   GO: {go_count}, NO-GO: {len(updated) - go_count}")
    
    return updated


# ============================================================================
# CLI
# ============================================================================

def main():
    parser = argparse.ArgumentParser(description='Dynamic Combo Pipeline')
    parser.add_argument('--name', type=str, help='Name for new combo')
    parser.add_argument('--trials', type=int, default=50, help='Optimizer trials')
    parser.add_argument('--validate-all', action='store_true', help='Re-validate all existing combos')
    parser.add_argument('--min-pbo', type=float, default=0.70, help='Min PBO threshold')
    parser.add_argument('--min-sharpe', type=float, default=1.0, help='Min WF Sharpe mean')
    parser.add_argument('--max-dd', type=float, default=0.25, help='Max drawdown')
    parser.add_argument('--verbose', '-v', action='store_true', help='Verbose logging')
    
    args = parser.parse_args()
    
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    gate = DecisionGate(
        min_pbo=args.min_pbo,
        min_wf_sharpe=args.min_sharpe,
        max_wf_drawdown=args.max_dd,
    )
    
    if args.validate_all:
        validate_all_existing_combos(gate)
    elif args.name:
        run_pipeline(args.name, args.trials, gate)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
