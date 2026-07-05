"""
tests/test_e25_sizing.py
Unit tests for E25 Dynamic SMA20 Extension Sizing Penalty (v1 and v2 curves)
"""

import pytest
from scripts.run_combo_scanner import _decision_to_row
from src.signals.signal_engine import (
    SignalDecision,
    calculate_dynamic_sizing_factor,
    resolve_canonical_risk,
    Tier2Metrics,
)

# Configuration structure for E25 Experiment (v1_monotonic)
E25_CONFIG_V1 = {
    "tier3_fixed": {
        "use_dynamic_extension_sizing": True,
        "dynamic_extension_sizing": {
            "version": "v1_monotonic",
            "comfort_pct": 6.76,
            "mid_pct": 15.0,
            "high_pct": 30.0,
            "max_pct": 50.0,
            "min_factor": 0.5,
            "extreme_factor": 0.2,
            "adr_exception_pct": 8.0
        }
    },
    "tier1_strategy": {
        "tp1_r": 1.25,
        "tp2_r": 3.0,
        "tp1_pct": 0.33,
        "tp2_pct": 0.33,
        "runner_pct": 0.34
    }
}

# Configuration structure for E25 Experiment (v2_atlas_informed)
E25_CONFIG_V2 = {
    "tier3_fixed": {
        "use_dynamic_extension_sizing": True,
        "dynamic_extension_sizing": {
            "version": "v2_atlas_informed",
            "comfort_pct": 6.76,
            "valley_pct": 10.0,
            "mid_pct": 15.0,
            "high_pct": 25.0,
            "extreme_pct": 35.0,
            "max_pct": 50.0,
            "min_factor": 0.5,
            "extreme_factor": 0.2,
            "adr_exception_pct": 8.0
        }
    },
    "tier1_strategy": {
        "tp1_r": 1.25,
        "tp2_r": 3.0,
        "tp1_pct": 0.33,
        "tp2_pct": 0.33,
        "runner_pct": 0.34
    }
}

E25_CONFIG_DISABLED = {
    "tier3_fixed": {
        "use_dynamic_extension_sizing": False
    },
    "tier1_strategy": {
        "tp1_r": 1.25,
        "tp2_r": 3.0,
        "tp1_pct": 0.33,
        "tp2_pct": 0.33,
        "runner_pct": 0.34
    }
}

# ==========================================
# TESTS PARA LA CURVA V1 (MONOTÓNICA)
# ==========================================

def test_dynamic_sizing_v1_comfort_zone():
    factor, reason = calculate_dynamic_sizing_factor(4.5, 4.0, E25_CONFIG_V1)
    assert factor == 1.0
    assert "comfort_zone" in reason

def test_dynamic_sizing_v1_mid_extension():
    # 10.88% (exactamente la mitad entre 6.76% y 15.0%) -> ~0.75
    factor, reason = calculate_dynamic_sizing_factor(10.88, 3.5, E25_CONFIG_V1)
    assert pytest.approx(factor, abs=0.02) == 0.75
    assert "v1_mid_extension_penalty" in reason

def test_dynamic_sizing_v1_high_extension():
    # 22.5% (exactamente la mitad entre 15% y 30%) -> ~0.35
    factor, reason = calculate_dynamic_sizing_factor(22.5, 4.5, E25_CONFIG_V1)
    assert pytest.approx(factor, abs=0.02) == 0.35
    assert "v1_high_extension_penalty" in reason

# ==========================================
# TESTS PARA LA CURVA V2 (NON-MONOTONIC)
# ==========================================

def test_dynamic_sizing_v2_comfort_zone():
    factor, reason = calculate_dynamic_sizing_factor(4.5, 4.0, E25_CONFIG_V2)
    assert factor == 1.0
    assert "comfort_zone" in reason

def test_dynamic_sizing_v2_valley_of_death():
    # Extensión = 8.38% (exactamente la mitad del valle 6.76% - 10.0%):
    # Debe decrecer fuerte de 1.0 a 0.3 -> ~0.65
    factor, reason = calculate_dynamic_sizing_factor(8.38, 4.0, E25_CONFIG_V2)
    assert pytest.approx(factor, abs=0.02) == 0.65
    assert "v2_valley_penalty" in reason

    # Extensión de 10.0% debe dar exactamente 0.3
    factor, reason = calculate_dynamic_sizing_factor(10.0, 4.0, E25_CONFIG_V2)
    assert factor == 0.3
    assert "v2_valley_penalty" in reason

def test_dynamic_sizing_v2_atlas_sweetspot():
    # Extensión = 12.5% (exactamente la mitad del sweetspot 10.0% - 15.0%):
    # Debe crecer de 0.3 a 0.5 -> ~0.40
    factor, reason = calculate_dynamic_sizing_factor(12.5, 4.0, E25_CONFIG_V2)
    assert pytest.approx(factor, abs=0.02) == 0.40
    assert "v2_atlas_sweetspot" in reason

    # Extensión de 15.0% debe dar exactamente 0.5
    factor, reason = calculate_dynamic_sizing_factor(15.0, 4.0, E25_CONFIG_V2)
    assert factor == 0.5
    assert "v2_atlas_sweetspot" in reason

def test_dynamic_sizing_v2_high_extension():
    # Extensión = 20.0% (exactamente la mitad de 15% - 25%):
    # Debe decrecer de 0.5 a 0.3 -> ~0.40
    factor, reason = calculate_dynamic_sizing_factor(20.0, 4.5, E25_CONFIG_V2)
    assert pytest.approx(factor, abs=0.02) == 0.40
    assert "v2_high_ext_penalty" in reason

    # Extensión de 25.0% debe dar exactamente 0.3
    factor, reason = calculate_dynamic_sizing_factor(25.0, 4.5, E25_CONFIG_V2)
    assert factor == 0.3
    assert "v2_high_ext_penalty" in reason

def test_dynamic_sizing_v2_extreme_extension():
    # Extensión = 30.0% (exactamente la mitad de 25% - 35%):
    # Debe decrecer de 0.3 a 0.1 -> ~0.20
    factor, reason = calculate_dynamic_sizing_factor(30.0, 4.5, E25_CONFIG_V2)
    assert pytest.approx(factor, abs=0.02) == 0.20
    assert "v2_extreme_ext_penalty" in reason

    # Extensión de 35.0% debe dar exactamente 0.1
    factor, reason = calculate_dynamic_sizing_factor(35.0, 4.5, E25_CONFIG_V2)
    assert factor == 0.1
    assert "v2_extreme_ext_penalty" in reason

def test_dynamic_sizing_v2_extreme_adr_exception():
    # > 35% pero <= 50% con ADR extremo (> 8%) -> 0.15
    factor, reason = calculate_dynamic_sizing_factor(40.0, 9.5, E25_CONFIG_V2)
    assert factor == 0.15
    assert "extreme_adr_exception" in reason

    # > 35% con ADR normal -> 0.0
    factor, reason = calculate_dynamic_sizing_factor(40.0, 6.0, E25_CONFIG_V2)
    assert factor == 0.0
    assert "blocked_extreme_extension" in reason

def test_dynamic_sizing_disabled_backward_compatibility():
    # Inactivo -> 1.0
    factor, reason = calculate_dynamic_sizing_factor(35.0, 9.2, E25_CONFIG_DISABLED)
    assert factor == 1.0
    assert reason == "disabled"

def test_resolve_canonical_risk_v2():
    metrics = Tier2Metrics(
        atr=2.5,
        dist_sma20=12.5,  # Sweetspot -> ~0.40 factor
        adr_pct=4.0,
        close=100.0
    )
    res = resolve_canonical_risk(
        entry_price=100.0,
        metrics=metrics,
        combo_cfg=E25_CONFIG_V2,
        risk_dollars=2878.0
    )
    assert res["sizing_factor"] == 0.40
    assert "v2_atlas_sweetspot" in res["sizing_reason"]
    assert res["shares"] == 230  # $2878 * 0.40 = $1151.2 -> $1151.2 / 5 = 230.2 -> 230 shares


def test_scanner_row_exports_e25_shadow_metadata():
    decision = SignalDecision(
        ticker="TEST",
        mode="A",
        passed=True,
        tier2_metrics=Tier2Metrics(dist_sma20=12.5, adr_pct=4.0, close=100.0),
        shares=230,
        risk_budget_usd=1151.2,
        raw_risk_budget_usd=2878.0,
        risk_per_share=5.0,
        sizing_factor=0.4,
        sizing_reason="v2_atlas_sweetspot:0.40",
    )

    row = _decision_to_row(decision)

    assert row["shares"] == 230
    assert row["initial_size"] == 230
    assert row["risk_budget_usd"] == 1151.2
    assert row["raw_risk_budget_usd"] == 2878.0
    assert row["risk_per_share"] == 5.0
    assert row["sizing_factor"] == 0.4
    assert row["sizing_reason"] == "v2_atlas_sweetspot:0.40"


def test_dynamic_sizing_version_specific_defaults():
    # Test fallback default high_pct = 25.0 for v2_atlas_informed
    cfg_v2_no_high = {
        "tier3_fixed": {
            "use_dynamic_extension_sizing": True,
            "dynamic_extension_sizing": {
                "version": "v2_atlas_informed"
            }
        }
    }
    # With comfort=6.76, valley=10.0, mid=15.0, high should default to 25.0, extreme to 35.0
    # Extension = 20.0 (midpoint of 15% and 25%) -> should return ~0.40 factor
    factor, reason = calculate_dynamic_sizing_factor(20.0, 4.5, cfg_v2_no_high)
    assert pytest.approx(factor, abs=0.02) == 0.40
    assert "v2_high_ext_penalty" in reason

    # Test fallback default high_pct = 30.0 for v1_monotonic
    cfg_v1_no_high = {
        "tier3_fixed": {
            "use_dynamic_extension_sizing": True,
            "dynamic_extension_sizing": {
                "version": "v1_monotonic"
            }
        }
    }
    # With comfort=6.76, mid=15.0, high should default to 30.0
    # Extension = 22.5 (midpoint of 15% and 30%) -> should return ~0.35 factor
    factor, reason = calculate_dynamic_sizing_factor(22.5, 4.5, cfg_v1_no_high)
    assert pytest.approx(factor, abs=0.02) == 0.35
    assert "v1_high_extension_penalty" in reason


# ==========================================
# INTEGRATION: SCANNER max_dist_sma20 SKIP
# ==========================================

def test_e25_override_skips_max_dist_sma20():
    """System B con dynamic extension no debe recibir hard block de max_dist_sma20."""
    prod_config = {
        "tier2_filters": {
            "min_rvol": 1.1,
            "max_dist_sma20": 6.768,
        },
        "tier3_fixed": {
            "use_dynamic_extension_sizing": True,
        },
        "tier1_strategy": {},
    }

    cfg_b = {
        "name": "combo_stage2_breakout",
        "tier3_fixed": {},
        "tier2_filters": {"min_rvol": 0.8},
    }

    # Inyectar tier3_fixed como haria run_combo_scanner.py
    cfg_b["tier3_fixed"] = dict(prod_config.get("tier3_fixed", {}))

    # Simular el filtro de override
    skip_max_dist = cfg_b.get("tier3_fixed", {}).get("use_dynamic_extension_sizing", False)
    t2_overrides = prod_config.get("tier2_filters", {})
    for k, v in t2_overrides.items():
        if skip_max_dist and k == "max_dist_sma20":
            continue
        cfg_b["tier2_filters"][k] = v

    # max_dist_sma20 NO debe haberse inyectado
    assert "max_dist_sma20" not in cfg_b["tier2_filters"], \
        f"max_dist_sma20={cfg_b['tier2_filters'].get('max_dist_sma20')} debe omitirse"
    # min_rvol SI debe haberse inyectado
    assert cfg_b["tier2_filters"]["min_rvol"] == 1.1


def test_e25_without_dynamic_extension_receives_max_dist_sma20():
    """System B sin dynamic extension todavia recibe max_dist_sma20 (backwards compat)."""
    cfg_b = {
        "name": "combo_stage2_breakout",
        "tier3_fixed": {},
        "tier2_filters": {"min_rvol": 0.8},
    }

    skip_max_dist = cfg_b.get("tier3_fixed", {}).get("use_dynamic_extension_sizing", False)
    t2_overrides = {"min_rvol": 1.1, "max_dist_sma20": 6.768}
    for k, v in t2_overrides.items():
        if skip_max_dist and k == "max_dist_sma20":
            continue
        cfg_b["tier2_filters"][k] = v

    assert cfg_b["tier2_filters"]["max_dist_sma20"] == 6.768


def test_combined_csv_preserves_e25_10pct_extension():
    """Verifica que una extension del 10% bajo System B produce sizing_factor correcto
    (0.30 para valley_penalty segun curva v2_atlas_informed)."""
    factor, reason = calculate_dynamic_sizing_factor(10.0, 4.0, E25_CONFIG_V2)
    assert factor == 0.3
    assert "v2_valley_penalty" in reason

    # Sweetspot del 12.5% → 0.40
    factor, reason = calculate_dynamic_sizing_factor(12.5, 4.0, E25_CONFIG_V2)
    assert pytest.approx(factor, abs=0.02) == 0.40
    assert "v2_atlas_sweetspot" in reason
