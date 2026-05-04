#!/usr/bin/env python3
import argparse
import json
import logging
import pandas as pd
from pathlib import Path
from datetime import datetime
import sys

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)-8s | %(message)s")
logger = logging.getLogger(__name__)

# Map sources to directories
SOURCES = {
    "live": PROJECT_ROOT / "outputs" / "live_signals",
    "finviz": PROJECT_ROOT / "outputs" / "paper_finviz"
}

REQUIRED_COLS = {
    "passed_with_sector",
    "passed_without_sector",
    "blocked_by_sector",
}

def to_bool(series: pd.Series) -> pd.Series:
    """Convierte robustamente a booleanos."""
    return series.astype(str).str.lower().map({
        "true": True, "false": False, "1": True, "0": False, 
        "1.0": True, "0.0": False, "nan": False, "none": False
    }).fillna(False)

def is_valid_date(date_str: str) -> bool:
    try:
        datetime.strptime(date_str, "%Y-%m-%d")
        return True
    except ValueError:
        return False

def get_valid_audit_files(base_dir: Path, start_date: str = None, end_date: str = None):
    """Retorna lista de paths a rejection_audit.csv validos y ordenados por fecha."""
    if not base_dir.exists():
        return []
    
    all_dirs = sorted([d for d in base_dir.iterdir() if d.is_dir() and is_valid_date(d.name)])
    
    valid_files = []
    skipped_legacy = 0
    
    for d in all_dirs:
        # Filtro de rango
        if start_date and d.name < start_date: continue
        if end_date and d.name > end_date: continue
        
        audit_path = d / "rejection_audit.csv"
        if audit_path.exists():
            try:
                # Chequeo rápido de columnas (solo 1 fila)
                df_head = pd.read_csv(audit_path, nrows=1)
                if REQUIRED_COLS.issubset(df_head.columns):
                    valid_files.append(audit_path)
                else:
                    skipped_legacy += 1
            except Exception:
                pass
                
    return valid_files, skipped_legacy

def run_aggregation(source: str, start_date: str = None, end_date: str = None, last_n: int = 20):
    logger.info(f"🚀 Iniciando agregación para fuente: {source}")
    
    base_dir = SOURCES.get(source)
    if not base_dir:
        logger.error(f"Fuente no válida: {source}")
        return

    monitoring_dir = base_dir / "monitoring"
    monitoring_dir.mkdir(parents=True, exist_ok=True)

    # 1. Obtener archivos válidos
    all_valid_files, skipped_legacy = get_valid_audit_files(base_dir, start_date, end_date)
    
    # Aplicar last_n al final
    target_files = all_valid_files[-last_n:] if last_n else all_valid_files
    
    if not target_files:
        logger.warning(f"No se encontraron auditorías contrafactuales válidas para la fuente '{source}'.")
        print(f"\nResumen: 0 archivos encontrados ({skipped_legacy} legacy omitidos)")
        return

    logger.info(f"Procesando {len(target_files)} auditorías válidas.")

    daily_rows = []
    all_candidates_rows = []
    
    # 2. Procesar cada archivo
    for audit_path in target_files:
        date_str = audit_path.parent.name
        try:
            df = pd.read_csv(audit_path)
            # Normalizar
            for col in REQUIRED_COLS:
                df[col] = to_bool(df[col])
            
            # Candidatos contrafactuales (hubieran pasado sin el filtro sectorial)
            df_candidates = df[df["passed_without_sector"] == True].copy()
            if not df_candidates.empty:
                all_candidates_rows.append(df_candidates)
            
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

    if not daily_rows:
        logger.warning("No hay datos de candidatos para agregar.")
        return

    # 3. Agregación Global
    df_daily = pd.DataFrame(daily_rows)
    df_all_candidates = pd.concat(all_candidates_rows, ignore_index=True) if all_candidates_rows else pd.DataFrame()

    total_candidates = df_daily["counterfactual_candidates"].sum()
    total_blocked = df_daily["blocked_by_sector"].sum()
    total_passed = df_daily["passed_with_sector"].sum()

    global_metrics = {
        "source": source,
        "window_start": target_files[0].parent.name,
        "window_end": target_files[-1].parent.name,
        "valid_files_used": len(target_files),
        "skipped_legacy_format": skipped_legacy,
        "counterfactual_candidates_total": int(total_candidates),
        "blocked_marginally_by_sector": int(total_blocked),
        "blocked_pct": round(total_blocked / total_candidates, 4) if total_candidates > 0 else 0.0,
        "passed_with_sector_total": int(total_passed),
        "net_signal_reduction": int(total_candidates - total_passed)
    }

    # 4. Agregación por Sector
    sector_summary = pd.DataFrame()
    if not df_all_candidates.empty:
        sector_summary = (
            df_all_candidates.groupby("sector_etf", dropna=False)
            .agg(
                counterfactual_candidates=("ticker", "count"),
                blocked_by_sector=("blocked_by_sector", "sum"),
                avg_dist_blocked=("sector_etf_dist", lambda x: x[df_all_candidates.loc[x.index, "blocked_by_sector"]].mean() if any(df_all_candidates.loc[x.index, "blocked_by_sector"]) else None)
            )
        )
        sector_summary["blocked_pct"] = (sector_summary["blocked_by_sector"] / sector_summary["counterfactual_candidates"] * 100).round(1)
        sector_summary = sector_summary.sort_values("blocked_by_sector", ascending=False)

    # 5. Persistencia
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    prefix = f"sector_filter_impact_{source}"
    summary_path = monitoring_dir / f"{prefix}_summary_{ts}.json"
    daily_path = monitoring_dir / f"{prefix}_daily_{ts}.csv"
    
    with open(summary_path, "w") as f:
        json.dump({
            "metrics": global_metrics,
            "top_blocked_sectors": sector_summary.head(10).to_dict(orient="index") if not sector_summary.empty else {},
            "timestamp": datetime.now().isoformat()
        }, f, indent=2)

    df_daily.to_csv(daily_path, index=False)
    if not sector_summary.empty:
        sector_summary.to_csv(monitoring_dir / f"{prefix}_by_sector_{ts}.csv")

    # 6. Salida en Consola
    print("\n" + "="*60)
    print(f"SECTOR FILTER IMPACT SUMMARY ({source.upper()})")
    print("="*60)
    print(f"Window:     {global_metrics['window_start']} -> {global_metrics['window_end']}")
    print(f"Valid files used: {global_metrics['valid_files_used']} (skipped {skipped_legacy} legacy)")
    print("-" * 60)
    print(f"Counterfactual candidates: {global_metrics['counterfactual_candidates_total']}")
    print(f"Blocked marginally by sector: {global_metrics['blocked_marginally_by_sector']} ({global_metrics['blocked_pct']*100:.1f}%)")
    print(f"Passed with sector:        {global_metrics['passed_with_sector_total']}")
    print(f"Net signal reduction:      {global_metrics['net_signal_reduction']}")
    print("-" * 60)
    if not sector_summary.empty and total_blocked > 0:
        print("TOP BLOCKED SECTORS:")
        for idx, row in sector_summary[sector_summary["blocked_by_sector"] > 0].head(5).iterrows():
            s = str(idx) if pd.notna(idx) else "UNKNOWN"
            print(f"{s:<5} {int(row['blocked_by_sector']):>3} / {int(row['counterfactual_candidates']):<3} ({row['blocked_pct']:>5.1f}%) | Avg Dist: {row['avg_dist_blocked'] if row['avg_dist_blocked'] is not None else 0:>+7.4f}")
    else:
        print("Ningún bloqueo marginal detectado en este periodo.")
    print("="*60)
    print(f"Artifacts saved in {monitoring_dir}")
    print("="*60 + "\n")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", choices=["live", "finviz"], default="live")
    parser.add_argument("--start", help="Start date YYYY-MM-DD")
    parser.add_argument("--end", help="End date YYYY-MM-DD")
    parser.add_argument("--last-n", type=int, default=20, help="Last N valid audit files")
    args = parser.parse_args()

    run_aggregation(args.source, args.start, args.end, args.last_n)
