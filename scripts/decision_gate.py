#!/usr/bin/env python3
"""
Gate de decision final: consolida regression check + WF + costos
y produce un veredicto por combo.

Uso:
    python3 scripts/decision_gate.py
    python3 scripts/decision_gate.py --export-md

No corre ningun backtest — solo lee los JSONs generados por
validate_combo_regression, walk_forward_combos y cost_sensitivity.
"""
import argparse, json, sys, subprocess, logging
from pathlib import Path
from datetime import datetime

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

WF_DIR   = ROOT / "outputs" / "walk_forward"
COST_DIR = ROOT / "outputs" / "cost_sensitivity"
BL_FILE  = ROOT / "baseline_snapshots" / "2026-03-29_week1_real" / "baseline_metrics.json"
COMBOS   = [
    "combo_pure_momentum",
    "combo_stage2_breakout",
    "combo_universal_any",
    "combo_pullback_entry",
    "combo_aggressive_momentum",
    "combo_ideal_setup",
]

# Thresholds del gate
GATE = {
    # WF criterio regimen-robusto (alineado con walk_forward_combos.py):
    # La fuente de verdad es el campo "verdict" del WF JSON.
    # Los checks individuales son informativos, no bloqueantes por separado.
    "min_wf_sharpe_mean":  0.25,  # promedio folds OOS
    "min_wf_positive_folds": 2,   # al menos 2/3 folds con sharpe > 0
    "min_wf_pf_mean":      1.0,   # PF medio > 1
    "min_wf_trades_fold":  15,    # trades minimos por fold
    "min_cost_breakeven":  10,    # bps minimos de margen
    "max_pbo":             0.85,  # del baseline
    "min_pf":              1.2,   # del baseline
    "min_trades":          50,    # trades minimos IS
}


def load_json_safe(path):
    if path.exists():
        return json.load(open(path))
    return None


def evaluate_combo(combo_name):
    result = {
        "combo": combo_name,
        "checks": {},
        "warnings": [],
        "verdict": None,
    }

    # --- Check 1: Baseline (regression check) ---
    bl_data = load_json_safe(BL_FILE)
    if bl_data:
        bl_combos = {c["name"]: c for c in bl_data.get("combos", [])}
        bl = bl_combos.get(combo_name, {})
    else:
        bl = {}

    bl_trades = bl.get("trades", 0)
    bl_sharpe = bl.get("sharpe", 0)
    bl_pbo    = bl.get("pbo", 1.0)
    bl_pf     = bl.get("pf", 0)

    result["checks"]["baseline_trades_ok"] = bl_trades >= GATE["min_trades"]
    result["checks"]["baseline_pbo_ok"]    = bl_pbo    <= GATE["max_pbo"]
    result["checks"]["baseline_pf_ok"]     = bl_pf     >= GATE["min_pf"]
    result["checks"]["baseline_sharpe_ok"] = bl_sharpe > 0

    if bl_trades < 50:
        result["warnings"].append(f"Solo {bl_trades} trades IS — muestra insuficiente")
    if bl_pbo > 0.70:
        result["warnings"].append(f"PBO={bl_pbo:.0%} — alto riesgo overfitting")

    # --- Check 2: Walk-Forward ---
    wf_data = load_json_safe(WF_DIR / f"{combo_name}_wf.json")
    if wf_data:
        agg = wf_data.get("aggregate", {})
        wf_sharpe_mean  = agg.get("sharpe_mean", 0)
        wf_sharpe_min   = agg.get("sharpe_min", 0)
        wf_pf_consistent= agg.get("pf_consistent", False)
        wf_trades_fold  = agg.get("trades_per_fold", 0)

        wf_verdict       = agg.get("verdict", "NO-GO")
        positive_folds   = agg.get("sharpe_positive_folds", 0)
        wf_pf_mean       = agg.get("pf_mean", 0)

        # Fuente de verdad: el verdict del WF (criterio regimen-robusto 2/3 folds)
        result["checks"]["wf_verdict_ok"]      = wf_verdict == "GO"
        # Checks informativos adicionales
        result["checks"]["wf_sharpe_mean_ok"]  = wf_sharpe_mean >= GATE["min_wf_sharpe_mean"]
        result["checks"]["wf_positive_folds"]  = positive_folds >= GATE["min_wf_positive_folds"]
        result["checks"]["wf_pf_mean_ok"]      = wf_pf_mean    >= GATE["min_wf_pf_mean"]
        result["checks"]["wf_trades_ok"]       = wf_trades_fold >= GATE["min_wf_trades_fold"]
        result["wf_summary"] = {
            "sharpe_mean": wf_sharpe_mean, "sharpe_min": wf_sharpe_min,
            "pf_mean": wf_pf_mean, "pf_consistent": wf_pf_consistent,
            "positive_folds": positive_folds, "trades_per_fold": wf_trades_fold,
            "verdict": wf_verdict,
        }
        if wf_sharpe_min < 0:
            result["warnings"].append(f"Fold con Sharpe negativo ({wf_sharpe_min:.2f}) en WF — 2022 bear market")
    else:
        # WF no corrido aun
        result["checks"]["wf_verdict_ok"]     = None
        result["checks"]["wf_sharpe_mean_ok"] = None
        result["checks"]["wf_positive_folds"] = None
        result["checks"]["wf_pf_mean_ok"]     = None
        result["checks"]["wf_trades_ok"]      = None
        result["warnings"].append("Walk-forward NO ejecutado — correr walk_forward_combos.py primero")

    # --- Check 3: Costos ---
    cost_data = load_json_safe(COST_DIR / f"{combo_name}_costs.json")
    if cost_data:
        breakeven = cost_data.get("breakeven_bps", 0)
        assessment = cost_data.get("assessment", "?")
        sanity_issues = cost_data.get("sanity_issues", [])
        
        # Si hay sanity issues, degradamos el assessment
        if sanity_issues:
            assessment = f"{assessment} (ANOMALIA)"
            for issue in sanity_issues:
                result["warnings"].append(f"Costos: {issue}")
        
        result["checks"]["cost_ok"] = breakeven >= GATE["min_cost_breakeven"] and not sanity_issues
        result["cost_summary"] = {"breakeven_bps": breakeven, "assessment": assessment}
        if breakeven < 10:
            result["warnings"].append(f"Edge fragil — breakeven {breakeven}bps (necesita broker muy barato)")
    else:
        result["checks"]["cost_ok"] = None
        result["warnings"].append("Analisis de costos NO ejecutado — correr cost_sensitivity.py primero")

    # --- Veredicto final ---
    definitive_checks = [v for v in result["checks"].values() if v is not None]
    pending_checks    = [k for k, v in result["checks"].items() if v is None]
    failed_checks     = [k for k, v in result["checks"].items() if v is False]

    if pending_checks:
        result["verdict"] = "PENDING"
        result["verdict_reason"] = f"Faltan: {', '.join(pending_checks)}"
    elif failed_checks:
        result["verdict"] = "NO-GO"
        result["verdict_reason"] = f"Falla en: {', '.join(failed_checks)}"
    else:
        result["verdict"] = "GO"
        result["verdict_reason"] = "Todos los checks pasados"

    return result


def print_report(results, export_md=False):
    lines = []
    lines.append(f"\n{'='*70}")
    lines.append(f"DECISION GATE — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    lines.append(f"{'='*70}")

    for r in results:
        v = r["verdict"]
        icon = {"GO": "[GO ]", "NO-GO": "[NOG]", "PENDING": "[PEN]"}.get(v, "[???]")
        lines.append(f"\n{icon} {r['combo']}")

        # Baseline
        bl_ok = all(v2 is True for k, v2 in r["checks"].items() if k.startswith("baseline"))
        lines.append(f"  Baseline:     {'OK' if bl_ok else 'FALLA'}")

        # WF
        wf_s = r.get("wf_summary", {})
        if wf_s:
            lines.append(f"  Walk-Fwd:     sharpe_mean={wf_s.get('sharpe_mean',0):.2f}  "
                         f"sharpe_min={wf_s.get('sharpe_min',0):.2f}  "
                         f"pf_consistent={wf_s.get('pf_consistent')}  "
                         f"verdict={wf_s.get('verdict')}")
        else:
            lines.append(f"  Walk-Fwd:     PENDIENTE")

        # Costos
        cs = r.get("cost_summary", {})
        if cs:
            lines.append(f"  Costos:       breakeven={cs.get('breakeven_bps',0)}bps  {cs.get('assessment','?')}")
        else:
            lines.append(f"  Costos:       PENDIENTE")

        # Warnings
        for w in r["warnings"]:
            lines.append(f"  AVISO:        {w}")

        lines.append(f"  RAZON:        {r.get('verdict_reason','')}")

    lines.append(f"\n{'='*70}")
    lines.append("RESUMEN EJECUTIVO")
    lines.append(f"{'='*70}")
    go     = [r["combo"] for r in results if r["verdict"] == "GO"]
    nogo   = [r["combo"] for r in results if r["verdict"] == "NO-GO"]
    pend   = [r["combo"] for r in results if r["verdict"] == "PENDING"]
    lines.append(f"  GO      ({len(go)}):  {', '.join(go) or 'ninguno'}")
    lines.append(f"  NO-GO   ({len(nogo)}):  {', '.join(nogo) or 'ninguno'}")
    lines.append(f"  PENDING ({len(pend)}):  {', '.join(pend) or 'ninguno'}")
    lines.append("")

    report = "\n".join(lines)
    print(report)

    if export_md:
        md_path = ROOT / "outputs" / "decision_gate_report.md"
        open(md_path, "w").write(report)
        logger.info(f"Reporte exportado: {md_path}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--export-md", action="store_true")
    args = parser.parse_args()

    results = []
    for combo in COMBOS:
        r = evaluate_combo(combo)
        results.append(r)

    print_report(results, export_md=args.export_md)


if __name__ == "__main__":
    main()
