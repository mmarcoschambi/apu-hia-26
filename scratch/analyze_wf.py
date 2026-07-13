import json
import argparse
from pathlib import Path
import pandas as pd
import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parent.parent

def analyze_walkforward(mode):
    dir_name = "breadth_walkforward" if mode == "a" else "breadth_walkforward_b"
    wf_dir = PROJECT_ROOT / "outputs" / "experiments" / dir_name

    if not wf_dir.exists():
        print(f"Error: WF directory not found at {wf_dir}")
        return

    json_files = sorted(list(wf_dir.glob("*.json")))
    if not json_files:
        print("No JSON files found in directory.")
        return

    print(f"Analyzing {len(json_files)} walkforward folds in {dir_name}...\n")

    records = []
    
    for fpath in json_files:
        # El prefijo de archivo puede ser breadth_ o breadth_b_
        prefix = "breadth_b_" if mode == "b" else "breadth_"
        fold_name = fpath.stem.replace(prefix, "")
        with open(fpath, "r") as f:
            data = json.load(f)
            
        results = data.get("results", [])
        for res in results:
            cfg_name = res.get("name")
            is_metrics = res.get("is", {})
            oos_metrics = res.get("oos", {})
            
            # Breadth stats
            is_b = res.get("is_breadth_stats") or {}
            oos_b = res.get("oos_breadth_stats") or {}
            
            records.append({
                "fold": fold_name,
                "config": cfg_name,
                "is_sharpe": is_metrics.get("sharpe", 0.0),
                "is_mdd": is_metrics.get("max_drawdown", 0.0),
                "is_trades": is_metrics.get("total_trades", 0),
                "is_breadth_mean": is_b.get("mean", 0.0) if is_b else np.nan,
                "oos_sharpe": oos_metrics.get("sharpe", 0.0),
                "oos_mdd": oos_metrics.get("max_drawdown", 0.0),
                "oos_trades": oos_metrics.get("total_trades", 0),
                "oos_breadth_mean": oos_b.get("mean", 0.0) if oos_b else np.nan,
            })

    df = pd.DataFrame(records)
    
    # 1. Resumen promedio por configuración
    summary = df.groupby("config").agg({
        "is_sharpe": "mean",
        "is_mdd": "mean",
        "is_trades": "sum",
        "oos_sharpe": "mean",
        "oos_mdd": "mean",
        "oos_trades": "sum",
        "is_breadth_mean": "mean",
        "oos_breadth_mean": "mean",
    }).rename(columns={
        "is_sharpe": "IS Sharpe (Mean)",
        "is_mdd": "IS MaxDD (Mean)",
        "is_trades": "IS Total Trades",
        "oos_sharpe": "OOS Sharpe (Mean)",
        "oos_mdd": "OOS MaxDD (Mean)",
        "oos_trades": "OOS Total Trades",
        "is_breadth_mean": "IS Breadth Mean",
        "oos_breadth_mean": "OOS Breadth Mean",
    })
    
    # Redondear y formatear
    pd.set_option('display.max_columns', None)
    pd.set_option('display.width', 1000)
    print("=== SUMMARY METRICS (AVERAGE ACROSS ALL FOLDS) ===")
    print(summary.round(4).to_string())
    print("\n" + "="*50 + "\n")
    
    # 2. Análisis detallado por Fold (OOS Sharpe)
    print("=== OOS SHARPE DETAILED BY FOLD ===")
    pivot_sharpe = df.pivot(index="fold", columns="config", values="oos_sharpe")
    print(pivot_sharpe.round(3).to_string())
    print("\n" + "="*50 + "\n")
    
    # 3. ¿En cuántos folds cada config supera al baseline S0_Baseline?
    print("=== WIN RATE VS BASELINE (S0_Baseline) ===")
    s0_sharpes = pivot_sharpe["S0_Baseline"]
    for col in pivot_sharpe.columns:
        if col == "S0_Baseline":
            continue
        beats = (pivot_sharpe[col] > s0_sharpes).sum()
        pct = (beats / len(pivot_sharpe)) * 100
        print(f"Config '{col}' beat Baseline in {beats}/{len(pivot_sharpe)} folds ({pct:.1f}%)")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["a", "b"], default="b", help="Walkforward mode to analyze (a: SMA20, b: High/Low nh_nl)")
    args = parser.parse_args()
    
    analyze_walkforward(args.mode)
