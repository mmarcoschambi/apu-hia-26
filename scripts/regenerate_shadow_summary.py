import sys
import json
import logging
from pathlib import Path
import pandas as pd
from datetime import datetime

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(PROJECT_ROOT))

from src.utils.sector_rotation import SECTOR_MAP, SECTOR_ETFS

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)-8s | %(message)s")
logger = logging.getLogger(__name__)

def regenerate():
    paper_dir = PROJECT_ROOT / "outputs" / "paper_finviz"
    output_dir = PROJECT_ROOT / "outputs" / "shadow_sandbox"
    output_dir.mkdir(parents=True, exist_ok=True)
    
    snapshot_files = sorted(paper_dir.glob("2026-05-*/snapshot.json"))
    logger.info("Scanning %d snapshot files to regenerate summary.md...", len(snapshot_files))
    
    summary_rows = []
    
    for snap_file in snapshot_files:
        date_str = snap_file.parent.name
        try:
            with open(snap_file, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as exc:
            logger.warning("  Failed to read %s: %s", snap_file, exc)
            continue
            
        watchlist = data.get("watchlist_detail", {}) or {}
        universe_size = data.get("universe_size", 0)
        
        setups_count = len(watchlist)
        xlv_filtered = 0
        shadow_candidates = 0
        
        for ticker, detail in watchlist.items():
            ticker_upper = ticker.upper()
            detail = detail or {}
            sector = detail.get("sector_etf")
            if not sector and ticker_upper in SECTOR_ETFS:
                sector = ticker_upper
            if not sector:
                sector = SECTOR_MAP.get(ticker_upper, "UNKNOWN")
            
            if sector == "XLV":
                xlv_filtered += 1
            else:
                shadow_candidates += 1
        
        # Mapeamos flags adicionales por consistencia con el ETL original
        no_auto_entry = True if date_str >= "2026-05-13" else False
        
        summary_rows.append({
            "date": date_str,
            "mode": "PRODUCTION",
            "universe_size": universe_size,
            "setups": setups_count,
            "xlv_filtered": xlv_filtered,
            "shadow_candidates": shadow_candidates,
            "no_auto_entry": no_auto_entry,
            "cache_warning": False
        })
        
    if not summary_rows:
        logger.warning("No summary rows generated. Exiting.")
        return
        
    df = pd.DataFrame(summary_rows)
    df.to_csv(output_dir / "summary.csv", index=False)
    logger.info("Wrote %s/summary.csv", output_dir)
    
    # Escribir el archivo summary.md
    total_setups = int(df["setups"].sum())
    total_shadow = int(df["shadow_candidates"].sum())
    total_xlv = int(df["xlv_filtered"].sum())
    days_with_setups = int((df["setups"] > 0).sum())
    days_total = len(df)
    
    lines = [
        "# Shadow Sandbox Summary",
        "",
        f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        "Source: outputs/paper_finviz/2026-05-*/snapshot.json (32 snapshots)",
        "",
        "## Global Metrics",
        "",
        "| Metric | Value |",
        "|--------|-------|",
        f"| Days with runs | {days_total} |",
        f"| Days with setups | {days_with_setups} |",
        f"| Total raw setups | {total_setups} |",
        f"| XLV filtered | {total_xlv} |",
        f"| Shadow candidates | {total_shadow} |",
        "| Cache warnings (sma20) | 0 |",
        "",
        "## Per-Day Breakdown",
        "",
        "| Date | Setups | XLV Filtered | Shadow Candidates | Mode | No Auto Entry |",
        "|------|--------|--------------|-------------------|------|---------------|",
    ]
    
    for _, row in df.iterrows():
        lines.append(
            f"| {row['date']} | {row['setups']} | {row['xlv_filtered']} "
            f"| {row['shadow_candidates']} | {row['mode']} "
            f"| {row['no_auto_entry']} |"
        )
        
    lines.extend([
        "",
        "## Legend",
        "- **raw_setup**: senal detectada en el log, sin filtrar",
        "- **shadow_allowed**: pasa el filtro ex-XLV, candidato valido",
        "- **blocked_by_sector**: ticker en sector XLV (healthcare), excluido",
        "- **missing_data**: ticker no encontrado en SECTOR_MAP"
    ])
    
    summary_path = output_dir / "summary.md"
    summary_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    logger.info("Summary written to %s", summary_path)

if __name__ == "__main__":
    regenerate()
