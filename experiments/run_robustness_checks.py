#!/usr/bin/env python3
import subprocess
from pathlib import Path
import sys

def run_cmd(args):
    print(f"🚀 Running: {' '.join(args)}")
    # Use Popen to stream progress to runner log so it is not buffered
    proc = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    for line in proc.stdout:
        print(line, end="")
    proc.wait()
    if proc.returncode != 0:
        print(f"❌ Error executing command")
        sys.exit(1)

def main():
    base_args = [
        ".venv/bin/python3",
        "-u",
        "scripts/backtest_via_signal_engine.py",
        "--start", "2019-01-01",
        "--end", "2025-06-30",
        "--capital", "100000",
        "--universe-size", "200",
        "--index", "RUSSELL1000",
        "--e25-sizing",
        "--e25-version", "v2_atlas_informed"
    ]

    scenarios = [
        # Original robustness checks (without variant-e)
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
        },
        # Validation Sprint 2 scenarios
        {
            "tag": "russell_baseline_e25_ex_xlv_ex_pypl_2019_2025",
            "extra": ["--exclude-sectors", "XLV", "--exclude-tickers", "PYPL"]
        },
        {
            "tag": "russell_baseline_e25_ex_xlv_ex_xlk_2019_2025",
            "extra": ["--exclude-sectors", "XLV", "--exclude-sectors", "XLK"]
        },
        {
            "tag": "russell_baseline_e25_ex_xlv_ex_pypl_xlk_2019_2025",
            "extra": ["--exclude-sectors", "XLV", "--exclude-tickers", "PYPL", "--exclude-sectors", "XLK"]
        },
        # Exposure caps
        {
            "tag": "russell_baseline_e25_ex_xlv_tickcap15_2019_2025",
            "extra": ["--exclude-sectors", "XLV", "--ticker-cap", "0.15"]
        },
        {
            "tag": "russell_baseline_e25_ex_xlv_tickcap20_2019_2025",
            "extra": ["--exclude-sectors", "XLV", "--ticker-cap", "0.20"]
        },
        {
            "tag": "russell_baseline_e25_ex_xlv_tickcap30_2019_2025",
            "extra": ["--exclude-sectors", "XLV", "--ticker-cap", "0.30"]
        },
        {
            "tag": "russell_baseline_e25_ex_xlv_seccap40_2019_2025",
            "extra": ["--exclude-sectors", "XLV", "--sector-cap", "0.40"]
        },
        {
            "tag": "russell_baseline_e25_ex_xlv_seccap60_2019_2025",
            "extra": ["--exclude-sectors", "XLV", "--sector-cap", "0.60"]
        },
        {
            "tag": "russell_baseline_e25_ex_xlv_seccap80_2019_2025",
            "extra": ["--exclude-sectors", "XLV", "--sector-cap", "0.80"]
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
            content = src_path.read_text()
            # Clean report description to match user rules (No "Thematic Divergence" unless --variant-e is on)
            content = content.replace("Thematic Divergence Filter + Dynamic Extension Sizing", "Russell 1000 + E25 Dynamic Extension Sizing + sector exclusion")
            content = content.replace("Thematic Divergence Filter", "Russell 1000 + E25 Dynamic Extension Sizing")
            dest_path.write_text(content)
            print(f"✅ Copied clean summary to: {dest_path}\n")

if __name__ == "__main__":
    main()
