#!/usr/bin/env python3
import json
import hashlib
import subprocess
from pathlib import Path

def get_git_head():
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"]).decode("utf-8").strip()
    except Exception:
        return "unknown"

def get_canonical_config_hash(path: Path):
    if not path.exists():
        return "missing"
    try:
        content = path.read_bytes()
        return hashlib.sha256(content).hexdigest()
    except Exception:
        return "error"

def get_dynamic_sizing(path: Path):
    if not path.exists():
        return None
    try:
        with open(path, "r") as f:
            data = json.load(f)
        return data.get("tier3_fixed", {}).get("use_dynamic_extension_sizing", None)
    except Exception:
        return None

def get_trade_count():
    # Last reference backtest metrics
    ref_path = Path("outputs/backtests/baseline_phase1_20260723_metrics.json")
    if ref_path.exists():
        try:
            with open(ref_path, "r") as f:
                return json.load(f).get("total_trades", 0)
        except Exception:
            pass
            
    # Fallback to the latest modified metrics file
    backtests_dir = Path("outputs/backtests")
    if backtests_dir.exists():
        metrics_files = list(backtests_dir.glob("*_metrics.json"))
        if metrics_files:
            latest_file = max(metrics_files, key=lambda p: p.stat().st_mtime)
            try:
                with open(latest_file, "r") as f:
                    return json.load(f).get("total_trades", 0)
            except Exception:
                pass
    return 0

def main():
    config_path = Path("config/production_config.json")
    state = {
        "canonical_loader": "src/config/config_loader.py",
        "canonical_config_path": config_path.as_posix(),
        "use_dynamic_extension_sizing": get_dynamic_sizing(config_path),
        "canonical_config_hash": get_canonical_config_hash(config_path),
        "commit_head": get_git_head(),
        "reference_backtest_trade_count": get_trade_count()
    }
    print(json.dumps(state, indent=2))

if __name__ == "__main__":
    main()
