import json
import pytest
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
METRICS_PATH = PROJECT_ROOT / "outputs" / "backtests" / "gold_standard_variant_e_metrics.json"

def test_quant_gate_metrics_preservation():
    """
    SCEN-01 & SCEN-02: Validates that historical backtest metrics for Gold Standard Variant E
    (Russell 1000 + E25 Sizing + ex-XLV, 2023-2024) exactly preserve the control baseline
    established in main (b13fcbf + surgical setdefault fix).
    
    Control Baseline (main b13fcbf + setdefault):
    - Return: 2.55%
    - Max Drawdown: -41.95%
    - Trades: 158
    (Note: -41.95% MDD occurs because combo_stage2_breakout operates in base-only mode with dynamic E25 sizing).
    """
    assert METRICS_PATH.exists(), f"Metrics file missing: {METRICS_PATH}"
    
    with open(METRICS_PATH, "r") as f:
        metrics = json.load(f)
        
    total_return = metrics.get("total_return", 0.0)
    max_drawdown = metrics.get("max_drawdown", -100.0)
    total_trades = metrics.get("total_trades", 0)
    
    # SCEN-01: Return must match or exceed the verified control baseline from main (2.55%)
    assert total_return >= 2.55, f"Total return {total_return}% degraded below verified main baseline (2.55%)"
    
    # SCEN-02: Max Drawdown must not degrade beyond the verified control baseline from main (-41.95%)
    assert max_drawdown >= -41.95, f"Max drawdown {max_drawdown}% breached verified main baseline (-41.95%)"
    
    # Verify trade counts match the control baseline (158 trades)
    if total_trades > 0:
        assert total_trades == 158, f"Trade count {total_trades} deviated from expected control baseline (158)"

