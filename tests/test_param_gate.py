import pytest
from pathlib import Path
from src.validation.param_gate import ParamGate
import json

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

def test_param_gate_tamper_detection(tmp_path):
    candidate = {
        "validation_passed": True,
        "params": {"a": 1},
        "oos_metrics": {"trades": 200, "dsr": 0.5, "mdd_pct": -15.0}
    }
    
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
    import json
    clean = {"oos_metrics": {"trades": 200}, "params": {"a": 1, "b": "test"}}
    expected = hashlib.sha256(json.dumps(clean, sort_keys=True).encode('utf-8')).hexdigest()
    assert hash_val == expected
    # Hardcoded known hash to prevent silent algorithm changes
    assert hash_val == "436105c29a190ba5fb96e6354570cb62b678576386a9023b135caa623bc7d546"
