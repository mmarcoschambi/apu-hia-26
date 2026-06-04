#!/usr/bin/env python3
import subprocess
from pathlib import Path
import sys

def run_cmd(args):
    print(f"🚀 Running: {' '.join(args)}")
    res = subprocess.run(args, capture_output=True, text=True)
    if res.returncode != 0:
        print(f"❌ Error executing command:\n{res.stderr}")
        sys.exit(1)
    print(res.stdout)

def main():
    base_args = [
        ".venv/bin/python3",
        "scripts/backtest_via_signal_engine.py",
        "--start", "2019-01-01",
        "--end", "2025-06-30",
        "--capital", "100000",
        "--universe-size", "200",
        "--index", "RUSSELL1000",
        "--variant-e",
        "--e25-sizing",
        "--e25-version", "v2_atlas_informed"
    ]

    scenarios = [
        {
            "tag": "russell_baseline_e25_ex_bac_2019_2025",
            "extra": ["--exclude-tickers", "BAC"]
        },
        {
            "tag": "russell_baseline_e25_ex_xlf_2019_2025",
            "extra": ["--exclude-sectors", "XLF"]
        },
        {
            "tag": "russell_baseline_e25_ex_xlv_2019_2025",
            "extra": ["--exclude-sectors", "XLV"]
        }
    ]

    # Ensure output directories exist
    Path("outputs/backtests").mkdir(parents=True, exist_ok=True)
    Path("docs/analysis").mkdir(parents=True, exist_ok=True)

    for sc in scenarios:
        tag = sc["tag"]
        print(f"\n==================================================")
        print(f"🏁 RUNNING ROBUSTNESS SCENARIO: {tag}")
        print(f"==================================================")
        
        args = base_args + ["--tag", tag] + sc["extra"]
        run_cmd(args)
        
        # Run validation analysis
        print(f"📊 Running validation analysis for: {tag}...")
        analysis_args = [
            ".venv/bin/python3",
            "scripts/experiments/run_validation_analysis.py",
            "--tag", tag
        ]
        run_cmd(analysis_args)
        
        # Copy to docs/analysis
        src_path = Path("outputs/backtests") / f"{tag}_validation_summary.md"
        dest_path = Path("docs/analysis") / f"{tag}_validation_summary.md"
        if src_path.exists():
            dest_path.write_text(src_path.read_text())
            print(f"✅ Copied summary to: {dest_path}\n")

if __name__ == "__main__":
    main()
