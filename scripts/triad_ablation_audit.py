#!/usr/bin/env python3
import argparse, sys
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
PARQUET = ROOT / "data" / "screener_cache" / "triad_rts.parquet"

CONFIGS = {
    "T0": {"min_rts_pct": 90.0, "require_green_candle": True,  "label": "baseline actual"},
    "T1": {"min_rts_pct": 80.0, "require_green_candle": True,  "label": "rts80"},
    "T2": {"min_rts_pct": 70.0, "require_green_candle": True,  "label": "rts70"},
    "T3": {"min_rts_pct": 70.0, "require_green_candle": False, "label": "rts70_nogreen"},
    "T4": {"min_rts_pct": 60.0, "require_green_candle": False, "label": "rts60_nogreen"},
}
MIN_PASS_RATE_PCT = 10.0
MIN_PASS_DAYS = 180

def audit_config(name, cfg, df):
    min_rts = cfg["min_rts_pct"]
    if df["score"].max() < 1.0:
        filtered = df[df["passed"] == True]
        note = "WARN: score=0 en parquet, usando passed original"
    else:
        filtered = df[df["score"] >= min_rts]
        note = f"score >= {min_rts}"
    total_days = df["date"].nunique()
    days_with_pass = filtered["date"].nunique()
    pass_rate = (days_with_pass / total_days * 100) if total_days > 0 else 0.0
    approved = (pass_rate >= MIN_PASS_RATE_PCT) and (days_with_pass >= MIN_PASS_DAYS)
    date_min = str(filtered["date"].min())[:10] if len(filtered) > 0 else "N/A"
    date_max = str(filtered["date"].max())[:10] if len(filtered) > 0 else "N/A"
    return {"config": name, "label": cfg["label"], "min_rts_pct": min_rts,
            "require_green": cfg["require_green_candle"], "total_days": total_days,
            "days_with_pass": days_with_pass, "pass_rate_pct": round(pass_rate, 2),
            "tickers_uniq": filtered["ticker"].nunique(), "rows": len(filtered),
            "date_range": f"{date_min} -> {date_max}", "approved": approved, "note": note}

def print_result(r):
    g = "OK  APROBADA" if r["approved"] else "XX  RECHAZADA"
    print(f"\n{'='*60}\n  Config {r['config']} -- {r['label']}\n{'='*60}")
    print(f"  min_rts_pct    : {r['min_rts_pct']}")
    print(f"  require_green  : {r['require_green']}")
    print(f"  Total dias     : {r['total_days']}")
    print(f"  Dias con senal : {r['days_with_pass']}")
    print(f"  Pass rate      : {r['pass_rate_pct']}%  (minimo={MIN_PASS_RATE_PCT}%)")
    print(f"  Tickers unicos : {r['tickers_uniq']}")
    print(f"  Filas          : {r['rows']}")
    print(f"  Rango          : {r['date_range']}")
    print(f"  NOTA           : {r['note']}")
    print(f"\n  [{g}]")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", choices=list(CONFIGS.keys()))
    parser.add_argument("--all", action="store_true")
    args = parser.parse_args()
    if not args.config and not args.all:
        parser.print_help(); sys.exit(2)
    if not PARQUET.exists():
        print(f"ERROR: {PARQUET} no encontrado"); sys.exit(1)
    print(f"Cargando {PARQUET} ...")
    df = pd.read_parquet(PARQUET)
    print(f"  {len(df):,} filas | {df['date'].nunique()} fechas | {df['ticker'].nunique()} tickers")
    configs_to_run = CONFIGS if args.all else {args.config: CONFIGS[args.config]}
    results = []
    for name, cfg in configs_to_run.items():
        r = audit_config(name, cfg, df)
        print_result(r); results.append(r)
    if args.all:
        print(f"\n{'='*60}\n  RESUMEN ABLATION\n{'='*60}")
        print(f"  {'Config':<6} {'pass_rate':>10} {'dias':>6} {'tickers':>8} {'gate':>12}")
        print(f"  {'-'*50}")
        for r in results:
            g = "APROBADA" if r["approved"] else "RECHAZADA"
            print(f"  {r['config']:<6} {r['pass_rate_pct']:>9.1f}% {r['days_with_pass']:>6} {r['tickers_uniq']:>8} {g:>12}")
        first = next((r for r in results if r["approved"]), None)
        if first:
            print(f"\n  -> Config minima: {first['config']} ({first['label']})")
            print(f"     Editar src/screeners/triad_rts.py: min_rts_pct={first['min_rts_pct']}, require_green={first['require_green']}")
            print(f"     Rebuild: python3 scripts/populate_triad_rankings.py --days-back 2600 --overwrite --max-tickers 2000")
        else:
            print("\n  -> Ninguna config aprobada. Usar Triad como score suave, no gate binario.")

if __name__ == "__main__":
    main()
