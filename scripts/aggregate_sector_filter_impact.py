#!/usr/bin/env python3
import argparse
import json
import logging
import pandas as pd
from pathlib import Path
from datetime import datetime, timedelta
import sys

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)-8s | %(message)s")
logger = logging.getLogger(__name__)

SIGNALS_DIR = PROJECT_ROOT / "outputs" / "live_signals"
MONITORING_DIR = SIGNALS_DIR / "monitoring"

def to_bool(series: pd.Series) -> pd.Series:
    """Convierte robustamente a booleanos, manejando strings 'True'/'False'."""
    return series.astype(str).str.lower().map({"true": True, "false": False, "1": True, "0": False, "1.0": True, "0.0": False})

def run_aggregation(start_date: str = None, end_date: str = None, last_n: int = None):
    logger.info("🚀 Iniciando agregación de impacto del filtro sectorial")
    MONITORING_DIR.mkdir(parents=True, exist_ok=True)

    # 1. Identificar carpetas a procesar
    all_dirs = sorted([d for d in SIGNALS_DIR.iterdir() if d.is_dir() and d.name != "monitoring"])
    
    if last_n:
        target_dirs = all_dirs[-last_n:]
    elif start_date and end_date:
        start_ts = pd.to_datetime(start_date)
        end_ts = pd.to_datetime(end_date)
        target_dirs = [d for d in all_dirs if start_ts <= pd.to_datetime(d.name) <= end_ts]
    else:
        # Default: last 20
        target_dirs = all_dirs[-20:]

    if not target_dirs:
        logger.warning("No se encontraron carpetas de señales en el rango especificado.")
        return

    logger.info(f"Procesando {len(target_dirs)} carpetas (desde {target_dirs[0].name} hasta {target_dirs[-1].name})")

    daily_rows = []
    all_candidates_rows = []
    files_found = 0
    files_used = 0
    skipped_legacy = 0

    required_cols = ["passed_without_sector", "blocked_by_sector", "passed_with_sector"]

    # 2. Recorrer archivos
    for d in target_dirs:
        audit_path = d / "rejection_audit.csv"
        files_found += 1
        if not audit_path.exists():
            continue
        
        try:
            df = pd.read_csv(audit_path)
            if df.empty:
                continue
            
            # Verificar formato (contrafactual vs legacy)
            if not all(c in df.columns for c in required_cols):
                skipped_legacy += 1
                continue
            
            files_used += 1
            # Normalizar booleanos
            for col in required_cols:
                df[col] = to_bool(df[col])
            
            # Filtrar solo candidatos contrafactuales (los que pasaron todo SALVO el sector)
            # Nota: En el formato nuevo, passed_without_sector ya indica esto.
            df_candidates = df[df["passed_without_sector"] == True].copy()
            all_candidates_rows.append(df_candidates)
            
            # Métricas diarias
            date_str = d.name
            count_candidates = len(df_candidates)
            count_blocked = df_candidates["blocked_by_sector"].sum()
            count_passed = df_candidates["passed_with_sector"].sum()
            
            daily_rows.append({
                "date": date_str,
                "counterfactual_candidates": int(count_candidates),
                "blocked_by_sector": int(count_blocked),
                "blocked_pct": round(count_blocked / count_candidates, 4) if count_candidates > 0 else 0.0,
                "passed_with_sector": int(count_passed),
                "net_signal_reduction": int(count_candidates - count_passed)
            })

        except Exception as e:
            logger.error(f"Error procesando {audit_path}: {e}")

    if not all_candidates_rows:
        logger.warning("No se encontraron datos contrafactuales válidos para agregar.")
        return

    # 3. Agregación Global
    df_all_candidates = pd.concat(all_candidates_rows, ignore_index=True)
    df_daily = pd.DataFrame(daily_rows)

    total_candidates = len(df_all_candidates)
    total_blocked = df_all_candidates["blocked_by_sector"].sum()
    total_passed = df_all_candidates["passed_with_sector"].sum()

    global_metrics = {
        "days_scanned": len(target_dirs),
        "files_found": files_found,
        "files_used": files_used,
        "skipped_legacy_format": skipped_legacy,
        "counterfactual_candidates_total": int(total_candidates),
        "blocked_by_sector_total": int(total_blocked),
        "blocked_by_sector_pct": round(total_blocked / total_candidates, 4) if total_candidates > 0 else 0.0,
        "passed_with_sector_total": int(total_passed),
        "net_signal_reduction": int(total_candidates - total_passed)
    }

    # 4. Agregación por Sector
    sector_summary = (
        df_all_candidates.groupby("sector_etf", dropna=False)
        .agg(
            counterfactual_candidates=("ticker", "count"),
            blocked_by_sector=("blocked_by_sector", "sum"),
            avg_dist_blocked=("sector_etf_dist", lambda x: x[df_all_candidates.loc[x.index, "blocked_by_sector"]].mean()),
            median_dist_blocked=("sector_etf_dist", lambda x: x[df_all_candidates.loc[x.index, "blocked_by_sector"]].median())
        )
    )
    sector_summary["blocked_pct"] = (sector_summary["blocked_by_sector"] / sector_summary["counterfactual_candidates"] * 100).round(1)
    sector_summary = sector_summary.sort_values("blocked_by_sector", ascending=False)

    # 5. Persistencia
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    summary_path = MONITORING_DIR / f"sector_filter_impact_summary_{ts}.json"
    daily_path = MONITORING_DIR / f"sector_filter_impact_daily_{ts}.csv"
    sector_path = MONITORING_DIR / f"sector_filter_impact_by_sector_{ts}.csv"

    with open(summary_path, "w") as f:
        json.dump({
            "parameters": {"start": start_date, "end": end_date, "last_n": last_n},
            "global_metrics": global_metrics,
            "top_blocked_sectors": sector_summary.head(5).to_dict(orient="index"),
            "timestamp": datetime.now().isoformat()
        }, f, indent=2)

    df_daily.to_csv(daily_path, index=False)
    sector_summary.to_csv(sector_path)

    # 6. Salida en Consola
    print("\n" + "="*60)
    print("SECTOR FILTER IMPACT SUMMARY (AGGREGATED)")
    print("="*60)
    print(f"Window:     {target_dirs[0].name} -> {target_dirs[-1].name}")
    print(f"Files used: {files_used} / {files_found} ({skipped_legacy} skipped legacy)")
    print("-" * 60)
    print(f"Counterfactual candidates: {global_metrics['counterfactual_candidates_total']}")
    print(f"Blocked by sector:         {global_metrics['blocked_by_sector_total']} ({global_metrics['blocked_by_sector_pct']*100:.1f}%)")
    print(f"Passed with sector:        {global_metrics['passed_with_sector_total']}")
    print(f"Net signal reduction:      {global_metrics['net_signal_reduction']}")
    print("-" * 60)
    print("TOP BLOCKED SECTORS:")
    top_print = sector_summary[sector_summary["blocked_by_sector"] > 0].head(5)
    if not top_print.empty:
        for idx, row in top_print.iterrows():
            sector = str(idx) if pd.notna(idx) else "UNKNOWN"
            print(f"{sector:<5} {int(row['blocked_by_sector']):>3} / {int(row['counterfactual_candidates']):<3} ({row['blocked_pct']:>5.1f}%) | Avg Dist: {row['avg_dist_blocked']:>+7.4f}")
    else:
        print("Ningún sector bloqueado en este periodo.")
    print("="*60)
    print(f"Artifacts saved in {MONITORING_DIR}")
    print("="*60 + "\n")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--start", help="Start date YYYY-MM-DD")
    parser.add_argument("--end", help="End date YYYY-MM-DD")
    parser.add_argument("--last-n", type=int, help="Process last N daily scans")
    args = parser.parse_args()

    run_aggregation(args.start, args.end, args.last_n)
