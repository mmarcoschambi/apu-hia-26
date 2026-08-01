import json
from pathlib import Path

import pytest

from src.validation.param_gate import (
    ParamGate,
    RejectedConfigError,
    assert_params_cleared,
)

RECEIPT_SOURCE = "config/validated_production_params.json"


@pytest.fixture
def mock_artifacts_dir(tmp_path, monkeypatch):
    """Inyecta un directorio de recibos en memoria para no tocar el disco real."""
    mock_dir = tmp_path / "artifacts" / "purged_cv"
    mock_dir.mkdir(parents=True)
    monkeypatch.setattr("src.validation.param_gate.ARTIFACTS_DIR", mock_dir)
    return mock_dir


def _write_receipt(artifacts_dir: Path, gate_passed: bool, **extra) -> None:
    report = {
        "params_json_source": RECEIPT_SOURCE,
        "gate_passed": gate_passed,
        "degradation_pct": 10.0 if gate_passed else 100.0,
        **extra,
    }
    path = artifacts_dir / "purged_cv_report_test.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(report, f)


def _valid_config(**overrides) -> dict:
    config = {
        "validation_passed": True,
        "params": {"a": 1},
        "oos_metrics": {"trades": 200, "dsr": 0.5, "mdd_pct": -15.0},
        "params_json_source": RECEIPT_SOURCE,
    }
    config.update(overrides)
    return config


# ── assert_params_cleared (recibo físico, restaurado de c219151) ────────


def test_assert_params_cleared_passed(mock_artifacts_dir):
    _write_receipt(mock_artifacts_dir, gate_passed=True)

    result = assert_params_cleared(RECEIPT_SOURCE)
    assert result["gate_passed"] is True


def test_assert_params_cleared_rejected(mock_artifacts_dir):
    _write_receipt(mock_artifacts_dir, gate_passed=False)

    with pytest.raises(RejectedConfigError, match="RECHAZADO"):
        assert_params_cleared(RECEIPT_SOURCE)


def test_assert_params_cleared_no_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "src.validation.param_gate.ARTIFACTS_DIR", tmp_path / "does_not_exist"
    )

    with pytest.raises(RejectedConfigError, match="Sin recibo"):
        assert_params_cleared(RECEIPT_SOURCE)


def test_assert_params_cleared_mismatched_source(mock_artifacts_dir):
    _write_receipt(mock_artifacts_dir, gate_passed=True)

    # El recibo existe pero para otro config → sin recibo para este
    with pytest.raises(RejectedConfigError, match="sin recibo"):
        assert_params_cleared("config/other_params.json")


# ── assert_promotable: contrato dual (métricas + recibo) ────────────────


def test_assert_promotable_passes_with_receipt(mock_artifacts_dir):
    """recibo presente + métricas OK → pasa."""
    _write_receipt(mock_artifacts_dir, gate_passed=True)

    receipt = ParamGate.assert_promotable(_valid_config())
    assert receipt["gate_passed"] is True


def test_assert_promotable_rejects_missing_receipt(mock_artifacts_dir):
    """recibo ausente (directorio sin reportes) → rechaza."""
    with pytest.raises(RejectedConfigError, match="sin recibo"):
        ParamGate.assert_promotable(_valid_config())


def test_assert_promotable_rejects_no_source(mock_artifacts_dir):
    """config sin params_json_source y sin path → rechaza por falta de recibo."""
    _write_receipt(mock_artifacts_dir, gate_passed=True)
    config = _valid_config()
    del config["params_json_source"]

    with pytest.raises(RejectedConfigError, match="Sin recibo"):
        ParamGate.assert_promotable(config)


def test_assert_promotable_rejects_metrics_below_threshold(mock_artifacts_dir):
    """métricas bajo umbral → rechaza, aunque exista recibo aprobado."""
    _write_receipt(mock_artifacts_dir, gate_passed=True)

    low_trades = _valid_config(oos_metrics={"trades": 50, "dsr": 0.5, "mdd_pct": -15.0})
    with pytest.raises(RejectedConfigError, match="Métricas bajo umbral"):
        ParamGate.assert_promotable(low_trades)

    low_dsr = _valid_config(oos_metrics={"trades": 200, "dsr": 0.1, "mdd_pct": -15.0})
    with pytest.raises(RejectedConfigError, match="Métricas bajo umbral"):
        ParamGate.assert_promotable(low_dsr)

    deep_mdd = _valid_config(oos_metrics={"trades": 200, "dsr": 0.5, "mdd_pct": -35.0})
    with pytest.raises(RejectedConfigError, match="Métricas bajo umbral"):
        ParamGate.assert_promotable(deep_mdd)


def test_assert_promotable_rejects_rejected_receipt(mock_artifacts_dir):
    """recibo con gate_passed=False → rechaza, aunque las métricas pasen."""
    _write_receipt(mock_artifacts_dir, gate_passed=False)

    with pytest.raises(RejectedConfigError, match="RECHAZADO"):
        ParamGate.assert_promotable(_valid_config())


def test_assert_promotable_rejects_missing_metrics(mock_artifacts_dir):
    """sin métricas → rechaza (validation_passed False o oos_metrics ausente)."""
    _write_receipt(mock_artifacts_dir, gate_passed=True)

    with pytest.raises(RejectedConfigError, match="Sin métricas"):
        ParamGate.assert_promotable(_valid_config(validation_passed=False))

    with pytest.raises(RejectedConfigError, match="Sin métricas"):
        ParamGate.assert_promotable(_valid_config(oos_metrics={}))


# ── validate_candidate: retrocompatibilidad (solo métricas) ─────────────


def test_param_gate_rejects_missing_validation():
    candidate = {
        "params": {"a": 1},
        "oos_metrics": {"trades": 200, "dsr": 0.5, "mdd_pct": -15.0}
    }
    assert not ParamGate.validate_candidate(candidate)


def test_param_gate_rejects_bad_metrics():
    candidate = {
        "validation_passed": True,
        "params": {"a": 1},
        "oos_metrics": {"trades": 50, "dsr": 0.5, "mdd_pct": -15.0}  # trades too low
    }
    assert not ParamGate.validate_candidate(candidate)

    candidate["oos_metrics"] = {"trades": 200, "dsr": 0.1, "mdd_pct": -15.0}  # DSR too low
    assert not ParamGate.validate_candidate(candidate)

    candidate["oos_metrics"] = {"trades": 200, "dsr": 0.5, "mdd_pct": -35.0}  # MDD too deep
    assert not ParamGate.validate_candidate(candidate)


def test_param_gate_rejects_missing_metrics():
    candidate = {"validation_passed": True, "params": {"a": 1}}
    assert not ParamGate.validate_candidate(candidate)


# ── promote: contrato dual aplicado a la promoción ──────────────────────


def test_promote_fails_without_receipt(mock_artifacts_dir, tmp_path):
    """Métricas OK pero sin recibo → la promoción se aborta (fail-closed)."""
    target = tmp_path / "promoted.json"
    assert not ParamGate.promote(_valid_config(), target)
    assert not target.exists()


def test_param_gate_tamper_detection(mock_artifacts_dir, tmp_path):
    _write_receipt(mock_artifacts_dir, gate_passed=True)
    candidate = _valid_config()

    # promote it
    target = tmp_path / "promoted.json"
    assert ParamGate.promote(candidate, target)

    # verify untouched
    assert ParamGate.verify_tampering(target)

    # tamper
    with open(target, 'r') as f:
        data = json.load(f)
    data["params"]["a"] = 999  # attacker changes param
    with open(target, 'w') as f:
        json.dump(data, f)

    # verify tampered
    assert not ParamGate.verify_tampering(target)


def test_param_gate_reproducible_hash():
    # Test that the hash algorithm is deterministic and stable
    candidate = {
        "params": {"a": 1, "b": "test"},
        "oos_metrics": {"trades": 200},
        # These keys should be ignored by the hash
        "governance_hash": "should_be_ignored",
        "promoted_at": "ignore_me",
        "validation_passed": True
    }

    hash_val = ParamGate.calculate_hash(candidate)

    # We expect a specific SHA-256 for {"oos_metrics": {"trades": 200}, "params": {"a": 1, "b": "test"}}
    # Let's dynamically assert it matches the known value.
    import hashlib
    clean = {"oos_metrics": {"trades": 200}, "params": {"a": 1, "b": "test"}}
    expected = hashlib.sha256(json.dumps(clean, sort_keys=True).encode('utf-8')).hexdigest()
    assert hash_val == expected
    # Hardcoded known hash to prevent silent algorithm changes
    assert hash_val == "436105c29a190ba5fb96e6354570cb62b678576386a9023b135caa623bc7d546"
