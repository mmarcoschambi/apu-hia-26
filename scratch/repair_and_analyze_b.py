import json
import shutil
import sqlite3
from pathlib import Path
import pandas as pd
import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = PROJECT_ROOT / "data" / "ticker_cache.db"
EXP_DIR = PROJECT_ROOT / "outputs" / "experiments"
DEST_DIR = EXP_DIR / "breadth_walkforward_b"

# Definición correcta de los 15 pliegues teóricos del Walk-Forward
FOLDS = [
    {"id": 1, "is_start": "2022-01-01", "is_end": "2022-06-30", "oos_start": "2022-07-01", "oos_end": "2022-09-30"},
    {"id": 2, "is_start": "2022-04-01", "is_end": "2022-09-30", "oos_start": "2022-10-01", "oos_end": "2022-12-31"},
    {"id": 3, "is_start": "2022-07-01", "is_end": "2022-12-31", "oos_start": "2023-01-01", "oos_end": "2023-03-31"},
    {"id": 4, "is_start": "2022-10-01", "is_end": "2023-03-31", "oos_start": "2023-04-01", "oos_end": "2023-06-30"},
    {"id": 5, "is_start": "2023-01-01", "is_end": "2023-06-30", "oos_start": "2023-07-01", "oos_end": "2023-09-30"},
    {"id": 6, "is_start": "2023-04-01", "is_end": "2023-09-30", "oos_start": "2023-10-01", "oos_end": "2023-12-31"},
    {"id": 7, "is_start": "2023-07-01", "is_end": "2023-12-31", "oos_start": "2024-01-01", "oos_end": "2024-03-31"},
    {"id": 8, "is_start": "2023-10-01", "is_end": "2024-03-31", "oos_start": "2024-04-01", "oos_end": "2024-06-30"},
    {"id": 9, "is_start": "2024-01-01", "is_end": "2024-06-30", "oos_start": "2024-07-01", "oos_end": "2024-09-30"},
    {"id": 10, "is_start": "2024-04-01", "is_end": "2024-09-30", "oos_start": "2024-10-01", "oos_end": "2024-12-31"},
    {"id": 11, "is_start": "2024-07-01", "is_end": "2024-12-31", "oos_start": "2025-01-01", "oos_end": "2025-03-31"},
    {"id": 12, "is_start": "2024-10-01", "is_end": "2025-03-31", "oos_start": "2025-04-01", "oos_end": "2025-06-30"},
    {"id": 13, "is_start": "2025-01-01", "is_end": "2025-06-30", "oos_start": "2025-07-01", "oos_end": "2025-09-30"},
    {"id": 14, "is_start": "2025-04-01", "is_end": "2025-09-30", "oos_start": "2025-10-01", "oos_end": "2025-12-31"},
    {"id": 15, "is_start": "2025-07-01", "is_end": "2025-12-31", "oos_start": "2026-01-01", "oos_end": "2026-04-30"} # Corregido oos_start a 2026-01-01
]

def get_trading_days(conn, start_date, end_date):
    """Obtiene la cantidad de días hábiles de trading únicos normalizados."""
    query = "SELECT count(distinct date(date)) FROM ohlcv_cache WHERE ticker = 'SPY' AND date(date) BETWEEN date(?) AND date(?)"
    cursor = conn.cursor()
    cursor.execute(query, [start_date, end_date])
    return cursor.fetchone()[0]

def build_fingerprints():
    conn = sqlite3.connect(str(DB_PATH))
    fingerprints = []
    print("Calculating fingerprints for theoretical folds from database:")
    for f in FOLDS:
        is_days = get_trading_days(conn, f["is_start"], f["is_end"])
        oos_days = get_trading_days(conn, f["oos_start"], f["oos_end"])
        signature = (is_days, oos_days)
        fingerprints.append((f, signature))
        print(f"  Fold {f['id']} ({f['is_start']} -> {f['oos_end']}): IS={is_days}, OOS={oos_days} -> Signature={signature}")
    conn.close()
    return fingerprints

def repair_and_analyze():
    DEST_DIR.mkdir(parents=True, exist_ok=True)
    
    # 1. Calcular huellas teóricas
    theoretical_folds = build_fingerprints()
    
    # 2. Listar todos los archivos JSON generados hoy en outputs/experiments
    sandbox_files = list(EXP_DIR.glob("breadth_sandbox_20260713_*.json"))
    
    # 3. Filtrar exactamente las 15 corridas del walkforward
    # Las corridas reales se ejecutaron secuencialmente a partir de las 18:40
    # Descartamos cualquier archivo previo a las 18:00 (como la prueba de las 16:57)
    valid_runs = []
    for fpath in sandbox_files:
        try:
            # Extraer marca de tiempo del nombre de archivo (formato: breadth_sandbox_YYYYMMDD_HHMMSS.json)
            time_part = fpath.stem.split("_")[-1] # HHMMSS
            if int(time_part) < 180000:
                print(f"  Discarding manual run (pre-18:00): {fpath.name}")
                continue
                
            with open(fpath, "r") as f:
                data = json.load(f)
            results = data.get("results", [])
            if not results:
                continue
            has_mode_b = any("HighLow" in res.get("name", "") or res.get("breadth_mode") == "nh_nl" for res in results)
            if not has_mode_b:
                continue
                
            sample_stats = None
            for res in results:
                if res.get("is_breadth_stats"):
                    sample_stats = res
                    break
            
            if not sample_stats:
                continue
                
            is_days = sample_stats["is_breadth_stats"]["total_days"]
            oos_days = sample_stats["oos_breadth_stats"]["total_days"]
            signature = (is_days, oos_days)
            
            valid_runs.append((fpath.name, fpath, signature, results))
        except Exception as e:
            print(f"  Error reading {fpath.name}: {e}")
            
    # Ordenar cronológicamente por nombre de archivo (el timestamp garantiza el orden secuencial de ejecución)
    valid_runs.sort(key=lambda x: x[0])
    
    print(f"\nFound {len(valid_runs)} valid walkforward runs after filtering manual tests.")
    
    if len(valid_runs) != len(theoretical_folds):
        print(f"Error: Expected {len(theoretical_folds)} files but found {len(valid_runs)}.")
        return
        
    records = []
    
    # 4. Asignar secuencialmente y validar firmas
    print("\nMapping files sequentially and validating signatures:")
    for idx, (fname, src_path, signature, results) in enumerate(valid_runs):
        fold, theoretical_sig = theoretical_folds[idx]
        fold_key = f"{fold['is_start']}_{fold['oos_end']}"
        
        # Validar firma como salvaguarda
        if signature != theoretical_sig:
            print(f"  CRITICAL WARNING: Signature mismatch for Fold {fold['id']}! File={fname} {signature} vs Theoretical {theoretical_sig}")
        else:
            print(f"  MATCH: Fold {fold['id']} -> {fname} {signature}")
            
        dest_path = DEST_DIR / f"breadth_b_{fold_key}.json"
        shutil.copy2(src_path, dest_path)
        
        # Guardar registros para el análisis consolidado
        for res in results:
            cfg_name = res.get("name")
            is_metrics = res.get("is", {})
            oos_metrics = res.get("oos", {})
            is_b = res.get("is_breadth_stats") or {}
            oos_b = res.get("oos_breadth_stats") or {}
            
            records.append({
                "fold": fold_key,
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
            
    print(f"\nSuccessfully aligned and renamed {len(valid_runs)}/15 fold reports.\n")
    
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
    repair_and_analyze()
