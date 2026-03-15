"""
auto_expand_ranges.py
=====================
Detecta cuando Optuna llega al limite de un rango y lo expande automaticamente.

Logica:
  - Si best_value == limite_superior -> expandir techo (+ margen)
  - Si best_value == limite_inferior -> expandir piso (- margen)
  - Si best_value esta en el interior -> rango esta bien, no tocar

Se ejecuta automaticamente al final de cada run del optimizer.
"""
import json
import re
import sys
from pathlib import Path

# ============================================================
# DEFINICION DE RANGOS CONOCIDOS Y MARGENES DE EXPANSION
# ============================================================
PARAM_RANGES = {
    # param_name: (min, max, step, expansion_margin)
    # NOTA: estos son los valores BASE — el script lee los rangos actuales
    # del optimizer dinamicamente. Estos solo se usan como fallback.
    "tp1_r":              (1.25, 2.0,  0.25, 0.25),
    "tp2_r":              (2.0,  4.0,  0.25, 0.25),
    "tp1_pct":            (0.40, 0.60, 0.05, 0.05),
    "tp2_pct":            (0.20, 0.45, 0.05, 0.05),
    "score_rs_weight":    (0.4,  1.0,  0.1,  0.1),
    "pattern_bonus_high": (0.0,  0.30, 0.05, 0.05),
    "pattern_bonus_med":  (0.0,  0.20, 0.05, 0.05),
    "pattern_bonus_low":  (0.0,  0.10, 0.05, 0.05),
}

# Limites absolutos — nunca expandir mas alla de estos
ABSOLUTE_LIMITS = {
    "tp1_r":              (1.25, 3.0),  # <1.25R no rentable con fees+slippage
    "tp2_r":              (2.0,  6.0),  # <2.0R TP2 demasiado cerca de TP1
    "tp1_pct":            (0.25, 0.70),
    "tp2_pct":            (0.20, 0.55),
    "score_rs_weight":    (0.0,  1.0),
    "pattern_bonus_high": (0.0,  0.50),
    "pattern_bonus_med":  (0.0,  0.40),
    "pattern_bonus_low":  (0.0,  0.30),
}

TOLERANCE = 0.001  # tolerancia para considerar "llegó al límite"

def load_best_params(final_config_path: str) -> dict:
    with open(final_config_path) as f:
        cfg = json.load(f)
    return cfg.get("tier1_strategy", {})

def parse_current_ranges(optimizer_content: str) -> dict:
    """Lee los rangos ACTUALES del optimizer desde el archivo (no hardcodeados)."""
    import re
    current = {}
    # Buscar patrones: suggest_float("param", lo, hi, step=X)
    pattern = r'suggest_float\("([^"]+)",\s*([\d.]+),\s*([\d.]+),\s*step=([\d.]+)\)'
    for m in re.finditer(pattern, optimizer_content):
        param, lo, hi, step = m.group(1), float(m.group(2)), float(m.group(3)), float(m.group(4))
        if param in PARAM_RANGES:
            _, _, _, margin = PARAM_RANGES[param]
            current[param] = (lo, hi, step, margin)
    return current


def check_and_expand(best_params: dict, optimizer_path: str) -> list:
    """Detecta params en limite y expande rangos en el optimizer."""
    with open(optimizer_path) as f:
        content = f.read()

    # Leer rangos actuales del archivo (no del dict hardcodeado que puede estar desactualizado)
    current_ranges = parse_current_ranges(content)
    # Merge: usar current si existe, sino el hardcodeado
    effective_ranges = {**PARAM_RANGES, **current_ranges}

    expansions = []

    for param, (lo, hi, step, margin) in effective_ranges.items():
        if param not in best_params:
            continue

        val = float(best_params[param])
        abs_lo, abs_hi = ABSOLUTE_LIMITS.get(param, (-999, 999))

        hit_ceiling = abs(val - hi) <= TOLERANCE
        hit_floor   = abs(val - lo) <= TOLERANCE

        if not hit_ceiling and not hit_floor:
            continue

        if hit_ceiling:
            new_hi = min(hi + margin, abs_hi)
            if new_hi <= hi:
                expansions.append(f"  ⚠️  {param}: en techo {hi} pero ya en limite absoluto {abs_hi} — NO expandir")
                continue
            old_str = f'"{param}", {lo}, {hi}, step={step}'
            new_str = f'"{param}", {lo}, {new_hi}, step={step}'
            direction = f"↑ techo {hi} → {new_hi}"

        else:  # hit_floor
            new_lo = max(lo - margin, abs_lo)
            if new_lo >= lo:
                expansions.append(f"  ⚠️  {param}: en piso {lo} pero ya en limite absoluto {abs_lo} — NO expandir")
                continue
            old_str = f'"{param}", {lo}, {hi}, step={step}'
            new_str = f'"{param}", {new_lo}, {hi}, step={step}'
            direction = f"↓ piso {lo} → {new_lo}"

        # Intentar con el formato tal cual, y también con formato alternativo de floats
        found = False
        # Redondear a 2 decimales para evitar floats sucios como 0.6000000000000001
        lo = round(lo, 10)
        hi = round(hi, 10)
        for fmt_lo, fmt_hi in [
            (str(lo), str(hi)),
            (f"{lo:.2f}", f"{hi:.2f}"),
            (f"{lo:.1f}", f"{hi:.1f}"),
            (str(round(lo, 2)), str(round(hi, 2))),
        ]:
            test_str = f'"{param}", {fmt_lo}, {fmt_hi}, step={step}'
            if test_str in content:
                if hit_ceiling:
                    rep_str = f'"{param}", {fmt_lo}, {new_hi}, step={step}'
                else:
                    rep_str = f'"{param}", {new_lo}, {fmt_hi}, step={step}'
                content = content.replace(test_str, rep_str, 1)
                expansions.append(f"  ✅ {param}: valor={val} | {direction}")
                if hit_ceiling:
                    PARAM_RANGES[param] = (lo, new_hi, step, margin)
                else:
                    PARAM_RANGES[param] = (new_lo, hi, step, margin)
                found = True
                break
        if not found:
            expansions.append(f"  ❌ {param}: patron no encontrado en optimizer (revisar manualmente)")

    if expansions:
        with open(optimizer_path, 'w') as f:
            f.write(content)

    return expansions

def main():
    final_config = "outputs/3tier_optimization/FINAL_CONFIG.json"
    optimizer    = "optimize_3tier.py"

    if not Path(final_config).exists():
        print("❌ FINAL_CONFIG.json no encontrado — correr optimizer primero")
        sys.exit(1)

    print("=" * 60)
    print("  AUTO-EXPAND RANGES")
    print("  Detectando parámetros en límite de rango...")
    print("=" * 60)

    best = load_best_params(final_config)
    print(f"\nParámetros optimizados:")
    for k, v in best.items():
        if k in PARAM_RANGES:
            lo, hi, step, _ = PARAM_RANGES[k]
            at_limit = ""
            if abs(float(v) - hi) <= TOLERANCE: at_limit = " ← EN TECHO"
            if abs(float(v) - lo) <= TOLERANCE: at_limit = " ← EN PISO"
            print(f"  {k}: {v}  [rango: {lo}-{hi}]{at_limit}")

    print(f"\nExpansiones:")
    expansions = check_and_expand(best, optimizer)

    if not expansions:
        print("  ✅ Ningún parámetro en límite — rangos correctos")
    else:
        for e in expansions:
            print(e)

    print("\n" + "=" * 60)

if __name__ == "__main__":
    main()
