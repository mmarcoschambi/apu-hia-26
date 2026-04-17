#!/usr/bin/env python3
"""
RUN BEST COMBOS — Ejecuta optimize_3tier.py sobre los combos ganadores del torneo.

Lee config/combos/top5.json, extrae screener + pattern de cada combo,
y corre optimize_3tier.py con esos parametros.

Usage:
    python3 run_best_combos.py --trials 200 --tickers 200
    python3 run_best_combos.py --combo combo_pullback_entry --trials 100
    python3 run_best_combos.py --top 3 --trials 150
"""

import argparse
import json
import sys
import logging
import subprocess
from pathlib import Path
from datetime import datetime

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("run_best_combos.log"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)

# Mapping combo_name -> (signal_type, screener_name)
COMBO_MAP = {
    "combo_universal_any": ("any", "universal_any"),
    "combo_pullback_entry": ("pocket_pivot", "ema21_pullback"),
    "combo_ideal_setup": ("vcp", "minervini_trend"),
    "combo_aggressive_momentum": ("pocket_pivot", "minervini_trend"),
    "combo_stage2_breakout": ("breakout", "minervini_trend"),
    "combo_pure_momentum": ("breakout", "qullamaggie_momentum"),
}

OUTPUT_DIR = Path("outputs/best_combos_run")
SUMMARY_PATH = OUTPUT_DIR / "summary.json"


def get_top_combos(top_n: int = 6) -> list:
    """Load top combos from top5.json or fallback to COMBO_MAP."""
    top5_path = Path("config/combos/top5.json")
    if top5_path.exists():
        with open(top5_path) as f:
            combos = json.load(f)
        combos.sort(key=lambda c: c.get("combo_score", 0), reverse=True)
        return combos[:top_n]
    return [
        {"combo": name, "combo_score": 0} for name in list(COMBO_MAP.keys())[:top_n]
    ]


def _safe(v, default="N/A"):
    """Safe value for formatting — never returns None."""
    return v if v is not None else default


def run_3tier_for_combo(
    combo_name: str,
    signal_type: str,
    screener_name: str,
    trials: int = 200,
    tickers: int = 200,
    start: str = "2019-01-01",
    end: str = "2024-12-31",
    jobs: int = 1,
    seed: int = 42,
    no_stratified: bool = False,
) -> dict:
    """Run optimize_3tier.py for a single combo with live output streaming."""
    output_path = str(OUTPUT_DIR / f"{combo_name}_config.json")

    cmd = [
        "python3",
        "optimize_3tier.py",
        "--signal-type",
        signal_type,
        "--screener",
        screener_name,
        "--trials",
        str(trials),
        "--tickers",
        str(tickers),
        "--start",
        start,
        "--end",
        end,
        "--jobs",
        str(jobs),
        "--seed",
        str(seed),
        "--output",
        output_path,
    ]

    if no_stratified:
        cmd.append("--no-stratified-universe")

    print(f"\n{'#' * 70}")
    print(f"# [{combo_name}] {screener_name} x {signal_type}")
    print(f"# Trials: {trials} | Tickers: {tickers} | Period: {start} to {end}")
    print(f"# Output: {output_path}")
    print(f"{'#' * 70}")
    sys.stdout.flush()

    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )

        full_output = []
        sharpe = None
        trades = None
        win_rate = None
        pbo = None
        approved = None
        current_phase = "Starting"
        start_time = datetime.now()

        for line in proc.stdout:
            full_output.append(line)

            if "PHASE 1:" in line:
                current_phase = "Baseline"
            elif "PHASE 2:" in line:
                current_phase = "Tier2 Derivation"
            elif "PHASE 3:" in line:
                current_phase = "Optuna Optimization"
            elif "PHASE 4:" in line:
                current_phase = "Walk-Forward Validation"
            elif "PHASE 5:" in line:
                current_phase = "Export to Streamlit"

            elapsed = (datetime.now() - start_time).total_seconds()
            prefix = f"[{combo_name:<28}] [{current_phase:<22}] [{elapsed:>6.0f}s] "
            print(f"  {prefix}{line.rstrip()}")
            sys.stdout.flush()

            line_lower = line.lower()
            if "sharpe" in line_lower and ":" in line:
                try:
                    val = line.split(":")[-1].strip()
                    sharpe = float(val.replace("%", ""))
                except ValueError:
                    pass
            if (
                "trades" in line_lower
                and ":" in line
                and "insufficient" not in line_lower
            ):
                try:
                    val = line.split(":")[-1].strip()
                    trades = int(float(val.replace("%", "")))
                except ValueError:
                    pass
            if "win rate" in line_lower and ":" in line:
                try:
                    val = line.split(":")[-1].strip().replace("%", "")
                    win_rate = float(val)
                except ValueError:
                    pass
            if "pbo" in line_lower and ":" in line:
                try:
                    val = line.split(":")[-1].strip().replace("%", "")
                    pbo = float(val)
                except ValueError:
                    pass
            if "approved" in line_lower or "aprobad" in line_lower:
                approved = "approved" in line_lower or "aprobada" in line_lower
                if "not" in line_lower or "ninguna" in line_lower:
                    approved = False

        returncode = proc.wait(timeout=10)
        passed = returncode == 0

        elapsed_total = (datetime.now() - start_time).total_seconds()
        status = "PASS" if passed else "FAIL"
        print(f"\n  [{combo_name}] {status} in {elapsed_total:.0f}s")
        if sharpe is not None:
            print(
                f"    Sharpe={sharpe:.2f}  Trades={trades}  WR={win_rate}%  PBO={pbo}%"
            )
        print()
        sys.stdout.flush()

        return {
            "combo": combo_name,
            "screener": screener_name,
            "signal_type": signal_type,
            "passed": passed,
            "sharpe": sharpe,
            "trades": trades,
            "win_rate": win_rate,
            "pbo": pbo,
            "approved": approved,
            "output_path": output_path,
            "returncode": returncode,
            "elapsed_seconds": elapsed_total,
        }

    except subprocess.TimeoutExpired:
        proc.kill()
        print(f"\n  [{combo_name}] TIMEOUT after 2h")
        return {
            "combo": combo_name,
            "screener": screener_name,
            "signal_type": signal_type,
            "passed": False,
            "error": "timeout",
            "output_path": None,
        }
    except Exception as e:
        print(f"\n  [{combo_name}] ERROR: {e}")
        return {
            "combo": combo_name,
            "screener": screener_name,
            "signal_type": signal_type,
            "passed": False,
            "error": str(e),
            "output_path": None,
        }


def print_summary(results: list):
    """Print summary table — safe against None values."""
    logger.info(f"\n{'=' * 90}")
    logger.info("SUMMARY")
    logger.info(f"{'=' * 90}")
    logger.info(
        f"{'Combo':<30} {'Screener':<22} {'Signal':<15} {'Sharpe':>7} "
        f"{'Trades':>6} {'WR%':>5} {'PBO%':>5} {'Status':>8}"
    )
    logger.info("-" * 90)

    for r in results:
        logger.info(
            f"{_safe(r.get('combo')):<30} {_safe(r.get('screener')):<22} "
            f"{_safe(r.get('signal_type')):<15} "
            f"{_safe(r.get('sharpe'), '—'):>7} {_safe(r.get('trades'), '—'):>6} "
            f"{_safe(r.get('win_rate'), '—'):>5} {_safe(r.get('pbo'), '—'):>5} "
            f"{'PASS' if r.get('passed') else 'FAIL':>8}"
        )

    logger.info(f"{'=' * 90}")
    passed_count = sum(1 for r in results if r.get("passed"))
    logger.info(f"Total: {passed_count}/{len(results)} passed")


def save_summary(results: list, args: dict):
    """Save summary to JSON — called after each combo for incremental saves."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    summary = {
        "run_at": datetime.now().isoformat(),
        "args": args,
        "results": results,
    }
    with open(SUMMARY_PATH, "w") as f:
        json.dump(summary, f, indent=2, default=str)
    logger.info(f"Summary saved to: {SUMMARY_PATH}")


def main():
    parser = argparse.ArgumentParser(
        description="Run best combos through optimize_3tier.py"
    )
    parser.add_argument("--combo", type=str, default=None, help="Run single combo")
    parser.add_argument("--top", type=int, default=6, help="Top N combos to run")
    parser.add_argument(
        "--trials", type=int, default=200, help="Optuna trials per combo"
    )
    parser.add_argument("--tickers", type=int, default=200, help="Universe size")
    parser.add_argument("--start", type=str, default="2019-01-01", help="Start date")
    parser.add_argument("--end", type=str, default="2024-12-31", help="End date")
    parser.add_argument(
        "--jobs",
        type=int,
        default=4,
        help="Parallel jobs (1=safe, 2=rec, 4=aggressive)",
    )
    parser.add_argument("--seed", type=int, default=42, help="Random seed")
    parser.add_argument(
        "--no-stratified",
        action="store_true",
        default=False,
        help="Use legacy top-by-count universe (default: stratified)",
    )
    args = parser.parse_args()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    if args.combo:
        if args.combo not in COMBO_MAP:
            logger.error(
                f"Unknown combo: {args.combo}. Valid: {list(COMBO_MAP.keys())}"
            )
            sys.exit(1)
        combos_to_run = [args.combo]
    else:
        top_combos = get_top_combos(args.top)
        combos_to_run = [c["combo"] for c in top_combos]

    logger.info(f"Running {len(combos_to_run)} combos: {combos_to_run}")

    results = []
    for combo_name in combos_to_run:
        if combo_name not in COMBO_MAP:
            logger.warning(f"Skipping {combo_name}: not in COMBO_MAP")
            continue

        signal_type, screener_name = COMBO_MAP[combo_name]
        result = run_3tier_for_combo(
            combo_name=combo_name,
            signal_type=signal_type,
            screener_name=screener_name,
            trials=args.trials,
            tickers=args.tickers,
            start=args.start,
            end=args.end,
            jobs=args.jobs,
            seed=args.seed,
            no_stratified=args.no_stratified,
        )
        results.append(result)

        # Incremental save after each combo (survive crashes)
        save_summary(results, vars(args))
        logger.info(f"  Saved incremental result for {combo_name}")

    print_summary(results)
    save_summary(results, vars(args))


if __name__ == "__main__":
    main()
