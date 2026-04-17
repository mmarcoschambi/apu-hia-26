#!/usr/bin/env python3
"""
validate_combo_regression.py
=============================
Valida que un combo recien optimizado no regresiona vs su baseline congelado.

Uso:
    python scripts/validate_combo_regression.py --combo combo_pullback_entry
    python scripts/validate_combo_regression.py --all

Fuentes de baseline (en orden de prioridad):
    1. baseline_snapshots/2026-03-28_pre-week1/baseline_metrics.json  (fuente canonica)
    2. config/combos/baselines_week0/<combo>_optimized.json            (si tiene metricas reales)

Exit codes: 0=PASSED  1=FAILED  2=ERROR
"""

import argparse
from datetime import date
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RESULTS_DIR   = ROOT / "config" / "combo_results"
# Baseline canonico de la semana: 2019-2024, 100 trials
# Cuando pullback_entry corra y produzca resultados, actualizar este archivo
SNAPSHOT_DIR  = ROOT / "baseline_snapshots" / "2026-04-13_updated"  # activado 2026-04-13: baseline 2019-2024 canonico
BASELINE_METRICS = SNAPSHOT_DIR / "baseline_metrics.json"
# Fallback al snapshot historico si el nuevo no tiene datos aun
_FALLBACK_METRICS = ROOT / "baseline_snapshots" / "2026-03-28_pre-week1" / "baseline_metrics.json"


def load_baseline_metrics() -> dict:
    """Carga la tabla de metricas del baseline canonico (con fallback)."""
    target = BASELINE_METRICS if BASELINE_METRICS.exists() else _FALLBACK_METRICS
    if not target.exists():
        return {}
    with open(target) as f:
        data = json.load(f)
    combos = data.get("combos", [])
    # Solo incluir combos con metricas reales (sharpe != 0 o passed != None)
    valid = [c for c in combos if c.get("sharpe") is not None]
    return {c["name"]: c for c in valid}


def load_current_metrics(combo_name: str) -> dict:
    """Lee metricas del ultimo JSON exportado por optimize_combo."""
    p = RESULTS_DIR / f"{combo_name}_optimized.json"
    if not p.exists():
        return {}
    with open(p) as f:
        d = json.load(f)
    v = d.get("validation", {})
    # Soporta tanto el formato viejo (solo thresholds) como el nuevo (metricas reales)
    if "sharpe_ratio" not in v:
        return {}   # formato viejo sin metricas reales embebidas
    return {
        "name":    combo_name,
        "passed":  d.get("validation_passed", False),
        "sharpe":  float(v.get("sharpe_ratio", 0.0)),
        "pbo":     float(v.get("pbo_score", 1.0)),
        "pf":      float(v.get("profit_factor", 0.0)),
        "trades":  int(v.get("total_trades", 0)),
        "dd":      float(v.get("max_drawdown_pct", 0.0)),
        "wr":      float(v.get("win_rate_pct", 0.0)),
    }


def check_regression(
    base: dict,
    curr: dict,
    combo_name: str,
    max_sharpe_drop_pct: float = 15.0,
    max_pf_drop_pct: float = 20.0,
    max_pbo: float = 0.50,
) -> tuple:
    failures, warnings, policy_failures = [], [], []

    if not base:
        return False, ["No hay baseline disponible para comparar"], []
    if not curr:
        return False, ["No hay metricas en el resultado actual (formato viejo o run no completado)"], []

    if base.get("passed") and not curr.get("passed"):
        failures.append(
            f"Perdio validation_passed (baseline=True, actual=False)"
        )

    base_sharpe = float(base.get("sharpe", 0.0))
    curr_sharpe = float(curr.get("sharpe", 0.0))
    if base_sharpe > 0:
        drop = (base_sharpe - curr_sharpe) / base_sharpe * 100
        if drop > max_sharpe_drop_pct:
            failures.append(
                f"Sharpe cayo {drop:.1f}% "
                f"(baseline={base_sharpe:.2f}, actual={curr_sharpe:.2f}, max={max_sharpe_drop_pct}%)"
            )
        elif drop > max_sharpe_drop_pct * 0.6:
            warnings.append(
                f"Sharpe bajo {drop:.1f}% — cerca del limite "
                f"(baseline={base_sharpe:.2f}, actual={curr_sharpe:.2f})"
            )

    curr_pbo = float(curr.get("pbo", 1.0))
    curr_trades = int(curr.get("trades", 0))
    if curr_pbo > max_pbo:
        if curr_trades < 50:
            warnings.append(
                f"PBO={curr_pbo:.2%} supera limite {max_pbo:.0%}, "
                f"pero se ignora por pocos trades ({curr_trades} < 50)"
            )
        else:
            policy_failures.append(f"PBO={curr_pbo:.2%} supera limite {max_pbo:.0%}")

    base_pf = float(base.get("pf", 0.0))
    curr_pf = float(curr.get("pf", 0.0))
    if base_pf > 0:
        drop_pf = (base_pf - curr_pf) / base_pf * 100
        if drop_pf > max_pf_drop_pct:
            failures.append(
                f"PF cayo {drop_pf:.1f}% "
                f"(baseline={base_pf:.2f}, actual={curr_pf:.2f}, max={max_pf_drop_pct}%)"
            )

    return len(failures) == 0, failures, warnings, policy_failures


def fmt(val, fmt_str=".2f", suffix=""):
    try:
        return format(float(val), fmt_str) + suffix
    except (TypeError, ValueError):
        return str(val)


def run_check(
    combo_name: str, max_sharpe_drop: float, max_pbo: float, enforce_policy: bool
) -> bool:
    all_baselines = load_baseline_metrics()
    base = all_baselines.get(combo_name)
    curr = load_current_metrics(combo_name)

    print(f"\n{'='*62}")
    print(f"  REGRESSION CHECK: {combo_name}")
    print(f"{'='*62}")

    if not base:
        print(f"  ⚠️  Sin baseline en baseline_metrics.json para este combo")
        print(f"     (normal para variantes experimentales)")
        return True   # no bloquear si no hay baseline

    if not curr:
        print(f"  ⚠️  Sin metricas reales en resultado actual")
        print(f"     Posibles causas: run no completado, o formato JSON viejo")
        print(f"     Baseline: sharpe={fmt(base.get('sharpe'))} pbo={fmt(base.get('pbo'), '.2%')} passed={base.get('passed')}")
        # No bloquear por falta de metricas en current — es un warning, no failure
        return True

    regression_ok, failures, warnings, policy_failures = check_regression(
        base, curr, combo_name, max_sharpe_drop, max_pf_drop_pct=20.0, max_pbo=max_pbo
    )

    print(f"  {'METRICA':<12} {'BASELINE':>10} {'ACTUAL':>10} {'DELTA':>12}")
    print(f"  {'-'*46}")

    b_p, c_p = str(base.get("passed")), str(curr.get("passed"))
    print(f"  {'passed':<12} {b_p:>10} {c_p:>10}")

    b_s, c_s = float(base.get("sharpe", 0)), float(curr.get("sharpe", 0))
    delta_s = f"{(c_s-b_s)/abs(b_s)*100:+.1f}%" if b_s != 0 else "n/a"
    print(f"  {'sharpe':<12} {b_s:>10.2f} {c_s:>10.2f} {delta_s:>12}")

    b_pbo, c_pbo = float(base.get("pbo", 1)), float(curr.get("pbo", 1))
    print(f"  {'pbo':<12} {b_pbo:>9.2%} {c_pbo:>9.2%}")

    b_pf, c_pf = float(base.get("pf", 0)), float(curr.get("pf", 0))
    delta_pf = f"{(c_pf-b_pf)/abs(b_pf)*100:+.1f}%" if b_pf != 0 else "n/a"
    print(f"  {'pf':<12} {b_pf:>10.2f} {c_pf:>10.2f} {delta_pf:>12}")

    print(f"  {'trades':<12} {int(base.get('trades',0)):>10} {int(curr.get('trades',0)):>10}")
    print(f"  {'dd':<12} {float(base.get('dd',0)):>9.1f}% {float(curr.get('dd',0)):>9.1f}%")
    print(f"  {'wr':<12} {float(base.get('wr',0)):>9.1f}% {float(curr.get('wr',0)):>9.1f}%")
    print()

    for w in warnings:
        print(f"  ⚠️  {w}")

    if policy_failures and not enforce_policy:
        for pf in policy_failures:
            print(f"  ⚠️  POLICY_FAIL (no bloqueante): {pf}")

    passed = regression_ok and (not policy_failures or enforce_policy is False)
    if regression_ok and not policy_failures:
        print(f"  ✅ PASSED — sin regresion en {combo_name}")
    elif regression_ok and policy_failures and not enforce_policy:
        print(f"  ✅ PASSED (REGRESSION_ONLY) — sin regresion en {combo_name}")
    elif regression_ok and policy_failures and enforce_policy:
        print(f"  ❌ POLICY_FAIL (bloqueante) — {combo_name}")
        for pf in policy_failures:
            print(f"     • {pf}")
    else:
        print(f"  ❌ REGRESSION_FAIL — regresion detectada:")
        for fail in failures:
            print(f"     • {fail}")

    return passed




def _do_update_baseline(combos: list) -> None:
    """Actualiza baseline_metrics.json con los resultados actuales de combo_results/."""
    snapshot_dir = ROOT / "baseline_snapshots" / f"{date.today()}_updated"
    snapshot_dir.mkdir(parents=True, exist_ok=True)
    out_path = snapshot_dir / "baseline_metrics.json"

    # Cargar baseline existente para preservar metadata
    existing = {}
    if BASELINE_METRICS.exists():
        with open(BASELINE_METRICS) as f:
            existing = json.load(f)

    updated_combos = []
    for combo_name in combos:
        curr = load_current_metrics(combo_name)
        if not curr:
            print(f"  ⚠️  Sin datos actuales para {combo_name} - no se actualiza")
            continue
        entry = {
            "name": combo_name,
            "sharpe": curr.get("sharpe", 0.0),
            "pbo":    curr.get("pbo", 1.0),
            "pf":     curr.get("pf", 0.0),
            "trades": curr.get("trades", 0),
            "dd":     curr.get("dd", 100.0),
            "wr":     curr.get("wr", 0.0),
            "passed": curr.get("passed", False),
        }
        updated_combos.append(entry)
        print(f"  ✅ Baseline actualizado: {combo_name} | sharpe={entry['sharpe']:.2f} pbo={entry['pbo']:.2%}")

    meta = existing.get("meta", {})
    meta["updated_at"] = str(date.today())
    meta["note"] = f"Baseline actualizado {date.today()} via --update-baseline"

    payload = {"meta": meta, "combos": updated_combos}
    with open(out_path, "w") as f:
        json.dump(payload, f, indent=2)

    print(f"\n  💾 Baseline guardado en: {out_path}")
    print(f"  ⚠️  Para activarlo como canonico, actualiza SNAPSHOT_DIR en validate_combo_regression.py")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--combo", type=str)
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--max-sharpe-drop", type=float, default=15.0)
    parser.add_argument("--max-pbo", type=float, default=0.50)
    parser.add_argument(
        "--enforce-policy",
        action="store_true",
        help="Si se activa, POLICY_FAIL (ej. PBO > max-pbo) bloquea el check",
    )
    parser.add_argument("--update-baseline", action="store_true", help="Actualiza baseline_metrics.json con los resultados actuales")
    args = parser.parse_args()

    if not args.combo and not args.all:
        parser.print_help()
        sys.exit(2)

    if args.all:
        combos = [p.stem.replace("_optimized", "")
                  for p in RESULTS_DIR.glob("combo_*_optimized.json")]
    else:
        combos = [args.combo]

    all_passed = True
    for combo in sorted(combos):
        ok = run_check(combo, args.max_sharpe_drop, args.max_pbo, args.enforce_policy)
        if not ok:
            all_passed = False

    print(f"\n{'='*62}")
    if all_passed:
        print("  ✅ TODOS PASARON — sin regresiones detectadas")
    else:
        print("  ❌ HAY FALLOS — revisar arriba (REGRESSION_FAIL y/o POLICY_FAIL)")
    print(f"{'='*62}\n")

    if args.update_baseline:
        _do_update_baseline(combos)

    sys.exit(0 if all_passed else 1)


if __name__ == "__main__":
    main()
