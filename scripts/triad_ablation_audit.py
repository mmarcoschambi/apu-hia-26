#!/usr/bin/env python3
"""
Auditoria robusta del cache triad_rts basada en passed/reason.

Importante:
- NO usa score para decidir pass/fail de ablation.
- Los resultados por config (T0..T4) son una cota superior ("upper bound")
  y requieren rebuild real del cache para validacion definitiva.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
PARQUET = ROOT / "data" / "screener_cache" / "triad_rts.parquet"

CONFIGS = {
    "T0": {
        "min_rts_pct": 90.0,
        "require_green_candle": True,
        "label": "baseline actual",
    },
    "T1": {
        "min_rts_pct": 80.0,
        "require_green_candle": True,
        "label": "rts80",
    },
    "T2": {
        "min_rts_pct": 70.0,
        "require_green_candle": True,
        "label": "rts70",
    },
    "T3": {
        "min_rts_pct": 70.0,
        "require_green_candle": False,
        "label": "rts70_nogreen",
    },
    "T4": {
        "min_rts_pct": 60.0,
        "require_green_candle": False,
        "label": "rts60_nogreen",
    },
}

MIN_PASS_RATE_PCT = 10.0
MIN_PASS_DAYS = 180
RTS_RE = re.compile(r"RTS:\s*([0-9]+(?:\.[0-9]+)?)")


def classify_reason(reason: str, passed: bool) -> str:
    if passed:
        return "PASSED"
    if reason.startswith("RTS:"):
        return "RTS_gate"
    if reason.startswith("DarkGreen:"):
        return "DarkGreen"
    if reason.startswith("Minervini"):
        return "Minervini"
    if reason.startswith("AS:"):
        return "AS_gate"
    if reason.startswith("Base:"):
        return "Base"
    return "Other"


def parse_rts(reason: str) -> Optional[float]:
    match = RTS_RE.search(reason or "")
    if not match:
        return None
    try:
        return float(match.group(1))
    except Exception:
        return None


def parse_darkgreen_failed_components(reason: str) -> List[str]:
    if not reason.startswith("DarkGreen:"):
        return []
    tail = reason.split(":", 1)[1].strip()
    if not tail:
        return []
    return [x.strip() for x in tail.split(",") if x.strip()]


def print_stage_distribution(df: pd.DataFrame) -> None:
    counts = (
        df["stage"].value_counts(dropna=False).reindex(
            ["PASSED", "Base", "AS_gate", "Minervini", "RTS_gate", "DarkGreen", "Other"],
            fill_value=0,
        )
    )
    total = len(df)
    print("\nStage distribution (rows):")
    for stage, n in counts.items():
        pct = (n / total * 100.0) if total > 0 else 0.0
        print(f"  {stage:<10} {n:>9,} ({pct:>6.2f}%)")


def print_top_reasons(df: pd.DataFrame, top_n: int) -> None:
    failed = df[df["passed"] == False]
    print(f"\nTop {top_n} reasons (failed rows):")
    if failed.empty:
        print("  (sin filas failed)")
        return
    vc = failed["reason"].fillna("").value_counts().head(top_n)
    for reason, n in vc.items():
        label = reason if reason else "<empty>"
        print(f"  {n:>9,}  {label}")


def print_rts_gate_stats(df: pd.DataFrame) -> None:
    rts_fail = df[df["stage"] == "RTS_gate"].copy()
    print("\nRTS gate diagnostics:")
    if rts_fail.empty:
        print("  No hay filas con fail en RTS gate.")
        return
    rts_fail["rts_value"] = rts_fail["reason"].map(parse_rts)
    valid = rts_fail["rts_value"].dropna()
    print(f"  rows RTS fail: {len(rts_fail):,}")
    print(f"  rows RTS parseable: {len(valid):,}")
    if valid.empty:
        print("  No se pudo parsear valor RTS desde reason.")
        return
    q = valid.quantile([0.1, 0.25, 0.5, 0.75, 0.9]).to_dict()
    print(
        "  rts quantiles:"
        f" p10={q.get(0.1, 0):.1f}, p25={q.get(0.25, 0):.1f},"
        f" p50={q.get(0.5, 0):.1f}, p75={q.get(0.75, 0):.1f}, p90={q.get(0.9, 0):.1f}"
    )
    for thr in (90.0, 80.0, 70.0, 60.0):
        rescued = ((valid >= thr) & (valid < 90.0)).sum()
        print(f"  potential rescue if min_rts={thr:.0f}: +{int(rescued):,} rows (upper bound)")


def print_darkgreen_stats(df: pd.DataFrame) -> Tuple[pd.DataFrame, int]:
    dg = df[df["stage"] == "DarkGreen"].copy()
    print("\nDarkGreen diagnostics:")
    if dg.empty:
        print("  No hay filas con fail en DarkGreen.")
        return dg, 0

    component_counter: Dict[str, int] = {}
    green_only = 0
    for reason in dg["reason"].fillna(""):
        comps = parse_darkgreen_failed_components(reason)
        if len(comps) == 1 and comps[0] == "green_ok":
            green_only += 1
        for c in comps:
            component_counter[c] = component_counter.get(c, 0) + 1

    print(f"  rows DarkGreen fail: {len(dg):,}")
    print(f"  rows fail ONLY green_ok: {green_only:,}")
    if component_counter:
        print("  component frequency:")
        for comp, n in sorted(component_counter.items(), key=lambda x: x[1], reverse=True):
            print(f"    - {comp}: {n:,}")
    return dg, green_only


def evaluate_config_upper_bound(
    df: pd.DataFrame, config_name: str, cfg: Dict[str, object]
) -> Dict[str, object]:
    min_rts = float(cfg["min_rts_pct"])
    require_green = bool(cfg["require_green_candle"])

    passed_df = df[df["passed"] == True]
    base_pass_rows = len(passed_df)
    base_pass_days = passed_df["date"].nunique()

    # Rescate potencial RTS: filas que hoy fallan en RTS con valor parseado dentro del nuevo threshold.
    rts_fail = df[df["stage"] == "RTS_gate"].copy()
    rts_fail["rts_value"] = rts_fail["reason"].map(parse_rts)
    rts_rescue = rts_fail[
        (rts_fail["rts_value"].notna())
        & (rts_fail["rts_value"] >= min_rts)
        & (rts_fail["rts_value"] < 90.0)
    ]

    # Rescate potencial green-only si se apaga require_green_candle.
    dark_green = df[df["stage"] == "DarkGreen"].copy()
    dark_green["components"] = dark_green["reason"].map(parse_darkgreen_failed_components)
    green_only = dark_green[
        dark_green["components"].map(lambda x: len(x) == 1 and x[0] == "green_ok")
    ]
    green_rescue = green_only if not require_green else dark_green.iloc[0:0]

    # Cota superior: union de passed actuales + potenciales rescates
    candidate_rows = pd.concat(
        [passed_df[["date", "ticker"]], rts_rescue[["date", "ticker"]], green_rescue[["date", "ticker"]]],
        ignore_index=True,
    ).drop_duplicates()

    days_with_signal_upper = int(candidate_rows["date"].nunique())
    pass_rate_upper = (days_with_signal_upper / df["date"].nunique() * 100.0) if len(df) > 0 else 0.0
    approved_upper = (pass_rate_upper >= MIN_PASS_RATE_PCT) and (days_with_signal_upper >= MIN_PASS_DAYS)

    return {
        "config": config_name,
        "label": str(cfg["label"]),
        "min_rts_pct": min_rts,
        "require_green": require_green,
        "base_pass_rows": base_pass_rows,
        "base_pass_days": int(base_pass_days),
        "rts_rescue_rows_upper": int(len(rts_rescue)),
        "green_only_rescue_rows_upper": int(len(green_rescue)),
        "rows_upper": int(len(candidate_rows)),
        "days_with_signal_upper": days_with_signal_upper,
        "pass_rate_upper_pct": round(pass_rate_upper, 2),
        "approved_upper": approved_upper,
        "note": "upper bound heuristico; requiere rebuild real para decision",
    }


def print_config_result(r: Dict[str, object]) -> None:
    gate = "OK  APROBADA_UPPER" if r["approved_upper"] else "XX  RECHAZADA_UPPER"
    print(f"\n{'=' * 64}")
    print(f"Config {r['config']} -- {r['label']}")
    print(f"{'=' * 64}")
    print(f"  min_rts_pct                  : {r['min_rts_pct']}")
    print(f"  require_green_candle         : {r['require_green']}")
    print(f"  base rows passed             : {r['base_pass_rows']}")
    print(f"  base days with signal        : {r['base_pass_days']}")
    print(f"  + RTS rescue rows (upper)    : {r['rts_rescue_rows_upper']}")
    print(f"  + green-only rescue (upper)  : {r['green_only_rescue_rows_upper']}")
    print(f"  rows with signal (upper)     : {r['rows_upper']}")
    print(f"  days with signal (upper)     : {r['days_with_signal_upper']}")
    print(f"  pass rate day-level (upper)  : {r['pass_rate_upper_pct']}%")
    print(f"  NOTE                         : {r['note']}")
    print(f"\n  [{gate}]")


def print_summary_table(results: Iterable[Dict[str, object]]) -> None:
    rows = list(results)
    print(f"\n{'=' * 64}")
    print("RESUMEN ABLATION (UPPER BOUND, NO FINAL)")
    print(f"{'=' * 64}")
    print(f"  {'Config':<6} {'pass_rate_up':>12} {'days_up':>8} {'rows_up':>9} {'gate':>18}")
    print("  " + "-" * 59)
    for r in rows:
        gate = "APROBADA_UPPER" if r["approved_upper"] else "RECHAZADA_UPPER"
        print(
            f"  {r['config']:<6} {r['pass_rate_upper_pct']:>11.1f}%"
            f" {r['days_with_signal_upper']:>8} {r['rows_upper']:>9} {gate:>18}"
        )

    best = sorted(rows, key=lambda x: (x["days_with_signal_upper"], x["rows_upper"]), reverse=True)[0]
    print("\nRecomendacion operacional:")
    print("  1) Elegir 1-2 configs con mejor upper bound (ej: T2/T3 o T4)")
    print("  2) Rebuild real del cache triad_rts para cada config")
    print("  3) Validar pass-rate REAL + trades IS/OOS antes de decidir")
    print(f"  Candidata inicial sugerida: {best['config']} ({best['label']})")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", choices=list(CONFIGS.keys()))
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--top-reasons", type=int, default=10)
    args = parser.parse_args()

    if not args.config and not args.all:
        parser.print_help()
        sys.exit(2)

    if not PARQUET.exists():
        print(f"ERROR: {PARQUET} no encontrado")
        sys.exit(1)

    print(f"Cargando {PARQUET} ...")
    df = pd.read_parquet(PARQUET)
    if df.empty:
        print("Parquet vacio.")
        sys.exit(1)

    required_cols = {"date", "ticker", "passed", "reason"}
    missing = required_cols - set(df.columns)
    if missing:
        print(f"ERROR: faltan columnas requeridas: {sorted(missing)}")
        sys.exit(1)

    df = df.copy()
    df["date"] = pd.to_datetime(df["date"])
    df["reason"] = df["reason"].fillna("").astype(str)
    df["stage"] = [
        classify_reason(reason=r, passed=bool(p))
        for r, p in zip(df["reason"], df["passed"])
    ]

    total_days = int(df["date"].nunique())
    days_with_pass = int(df[df["passed"] == True]["date"].nunique())
    day_pass_rate = (days_with_pass / total_days * 100.0) if total_days > 0 else 0.0

    print(
        f"  {len(df):,} filas | {total_days} fechas | {df['ticker'].nunique()} tickers"
    )
    print(
        f"  passed rows={int(df['passed'].sum()):,} | days_with_pass={days_with_pass} | day_pass_rate={day_pass_rate:.2f}%"
    )

    print_stage_distribution(df)
    print_top_reasons(df, max(1, args.top_reasons))
    print_rts_gate_stats(df)
    _dg, _green_only = print_darkgreen_stats(df)

    configs_to_run = CONFIGS if args.all else {args.config: CONFIGS[args.config]}
    results = []
    for name, cfg in configs_to_run.items():
        r = evaluate_config_upper_bound(df, name, cfg)
        print_config_result(r)
        results.append(r)

    if args.all:
        print_summary_table(results)


if __name__ == "__main__":
    main()
