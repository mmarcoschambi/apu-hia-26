"""
auto_expand_ranges.py
=====================
Detecta cuando Optuna llega al limite de un rango y lo expande automaticamente.

Logica:
  - Lee signal_type del FINAL_CONFIG.json para saber que funcion tocar
  - Busca la funcion _<signal>_space() en pattern_configs.py
  - Si best_value == limite_superior -> expandir techo (+ margen)
  - Si best_value == limite_inferior -> expandir piso (- margen)
  - Soporta suggest_float (con step=) y suggest_int (sin step)
"""
import json
import re
import sys
from pathlib import Path

TOLERANCE = 0.001

# Margenes de expansion y limites absolutos por parametro
EXPANSION = {
    # param: (margin, abs_lo, abs_hi)
    "tp1_r":              (0.25, 1.25, 3.0),
    "tp2_r":              (0.25, 2.0,  6.0),
    "tp1_pct":            (0.05, 0.20, 0.70),
    "tp2_pct":            (0.05, 0.20, 0.55),
    "score_rs_weight":    (0.10, 0.0,  1.0),
    "pp_vol_lookback":    (2,    3,    20),
    "pp_vol_mult":        (0.2,  0.5,  3.0),
    "vcp_pivot_window":   (2,    5,    35),
    "vcp_atr_short":      (2,    3,    20),
    "vcp_atr_long":       (5,    15,   60),
    "vcp_atr_ratio":      (0.05, 0.50, 1.0),
    "vcp_volume_dry_periods": (2, 2,   15),
    "vcp_depth_max_pct":  (2.0,  5.0,  30.0),
    "vcp_pivot_dist_max_pct": (2.0, 2.0, 20.0),
    "fb_min_weeks":       (1,    3,    12),
    "fb_max_range":       (1.0,  2.0,  20.0),
}

# Mapeo signal_type -> nombre de funcion en pattern_configs.py
SIGNAL_TO_FUNC = {
    "pocket_pivot": "_pocket_pivot_space",
    "vcp":          "_vcp_space",
    "breakout":     "_breakout_space",
    "flat_base":    "_flat_base_space",
    "any":          "_breakout_space",  # any usa breakout space
}


def load_best_params(final_config_path: str) -> tuple:
    """Retorna (signal_type, best_params_dict)"""
    with open(final_config_path) as f:
        cfg = json.load(f)
    # signal_type puede estar en tier1_strategy o en el pipeline
    signal_type = (
        cfg.get("tier1_strategy", {}).get("signal_type")
        or cfg.get("signal_type")
        or "pocket_pivot"
    )
    # Intentar leer del pipeline si no esta en tier1
    if signal_type == "pocket_pivot":
        # doble check: leer del archivo de config si existe
        pass
    return signal_type, cfg.get("tier1_strategy", {})


def get_function_bounds(content: str, func_name: str) -> tuple:
    """Retorna (start_line_idx, end_line_idx) del cuerpo de la funcion."""
    lines = content.splitlines()
    start = None
    for i, line in enumerate(lines):
        if line.strip().startswith(f"def {func_name}("):
            start = i
            break
    if start is None:
        return None, None
    # Encontrar fin: proxima def al mismo nivel de indentacion
    end = len(lines)
    for i in range(start + 1, len(lines)):
        if lines[i].startswith("def ") or lines[i].startswith("class "):
            end = i
            break
    return start, end


def parse_params_in_func(content: str, func_name: str) -> dict:
    """Lee todos los suggest_float/int dentro de la funcion dada."""
    lines = content.splitlines()
    start, end = get_function_bounds(content, func_name)
    if start is None:
        return {}
    func_body = "\n".join(lines[start:end])

    params = {}
    # suggest_float("param", lo, hi, step=X)
    for m in re.finditer(r'suggest_float\("([^"]+)",\s*([\d.]+),\s*([\d.]+),\s*step=([\d.]+)\)', func_body):
        param, lo, hi, step = m.group(1), float(m.group(2)), float(m.group(3)), float(m.group(4))
        params[param] = {"lo": lo, "hi": hi, "step": step, "type": "float"}
    # suggest_int("param", lo, hi)
    for m in re.finditer(r'suggest_int\("([^"]+)",\s*(\d+),\s*(\d+)\)', func_body):
        param, lo, hi = m.group(1), int(m.group(2)), int(m.group(3))
        params[param] = {"lo": lo, "hi": hi, "step": 1, "type": "int"}
    return params


def expand_in_file(content: str, func_name: str, param: str, p: dict,
                   hit_floor: bool, hit_ceiling: bool) -> tuple:
    """
    Intenta expandir el rango del param dentro de func_name.
    Retorna (new_content, expansion_msg) o (content, error_msg).
    """
    margin, abs_lo, abs_hi = EXPANSION.get(param, (1, -999, 999))
    val = p["lo"] if hit_floor else p["hi"]

    if hit_floor:
        new_lo = max(p["lo"] - margin, abs_lo)
        if new_lo >= p["lo"]:
            return content, f"  ⚠️  {param}: en piso {p['lo']} pero ya en limite absoluto {abs_lo}"
        direction = f"↓ piso {p['lo']} → {new_lo}"
    else:
        new_hi = min(p["hi"] + margin, abs_hi)
        if new_hi <= p["hi"]:
            return content, f"  ⚠️  {param}: en techo {p['hi']} pero ya en limite absoluto {abs_hi}"
        direction = f"↑ techo {p['hi']} → {new_hi}"

    if p["type"] == "float":
        lo_s = str(p["lo"]) if p["lo"] != int(p["lo"]) else f"{p['lo']:.2f}"
        hi_s = str(p["hi"]) if p["hi"] != int(p["hi"]) else f"{p['hi']:.2f}"
        # Probar varios formatos de float
        lo_fmts = [str(p["lo"]), f"{p['lo']:.2f}", f"{p['lo']:.1f}", str(round(p["lo"], 2))]
        hi_fmts = [str(p["hi"]), f"{p['hi']:.2f}", f"{p['hi']:.1f}", str(round(p["hi"], 2))]
        for lf in lo_fmts:
            for hf in hi_fmts:
                step_s_opts = [str(p["step"]), f"{p['step']:.2f}", f"{p['step']:.1f}"]
                for sf in step_s_opts:
                    old_pat = f'"{param}", {lf}, {hf}, step={sf}'
                    if old_pat in content:
                        if hit_floor:
                            nlo = round(new_lo, 10)
                            new_lo_s = str(nlo) if nlo != int(nlo) else f"{nlo:.2f}"
                            new_pat = f'"{param}", {new_lo_s}, {hf}, step={sf}'
                        else:
                            nhi = round(new_hi, 10)
                            new_hi_s = str(nhi) if nhi != int(nhi) else f"{nhi:.2f}"
                            new_pat = f'"{param}", {lf}, {new_hi_s}, step={sf}'
                        # Reemplazar SOLO dentro de la funcion correcta
                        lines = content.splitlines()
                        start, end = get_function_bounds(content, func_name)
                        before = "\n".join(lines[:start])
                        func_body = "\n".join(lines[start:end])
                        after = "\n".join(lines[end:])
                        if old_pat in func_body:
                            func_body = func_body.replace(old_pat, new_pat, 1)
                            new_content = before + "\n" + func_body + "\n" + after
                            return new_content, f"  ✅ {param}: {direction}"
    else:  # int
        lo_i, hi_i = int(p["lo"]), int(p["hi"])
        old_pat = f'"{param}", {lo_i}, {hi_i})'
        if old_pat in content:
            lines = content.splitlines()
            start, end = get_function_bounds(content, func_name)
            before = "\n".join(lines[:start])
            func_body = "\n".join(lines[start:end])
            after = "\n".join(lines[end:])
            if old_pat in func_body:
                if hit_floor:
                    new_pat = f'"{param}", {int(new_lo)}, {hi_i})'
                else:
                    new_pat = f'"{param}", {lo_i}, {int(new_hi)})'
                func_body = func_body.replace(old_pat, new_pat, 1)
                new_content = before + "\n" + func_body + "\n" + after
                return new_content, f"  ✅ {param}: {direction} [int]"

    return content, f"  ❌ {param}: patron no encontrado en {func_name} (revisar manualmente)"


def main():
    final_config = "outputs/3tier_optimization/FINAL_CONFIG.json"
    pattern_cfg  = "src/config/pattern_configs.py"

    if not Path(final_config).exists():
        print("FINAL_CONFIG.json no encontrado")
        sys.exit(1)

    print("=" * 60)
    print("  AUTO-EXPAND RANGES")
    print("  Detectando parámetros en límite de rango...")
    print("=" * 60)

    signal_type, best = load_best_params(final_config)
    func_name = SIGNAL_TO_FUNC.get(signal_type, "_breakout_space")
    print(f"\n  signal_type: {signal_type} → funcion: {func_name}")

    with open(pattern_cfg) as f:
        content = f.read()

    # Leer rangos actuales de la funcion correcta
    current = parse_params_in_func(content, func_name)

    print(f"\nParámetros optimizados:")
    for k, v in best.items():
        if k in current:
            p = current[k]
            at_limit = ""
            try:
                val = float(v)
                if abs(val - p["hi"]) <= TOLERANCE: at_limit = " ← EN TECHO"
                if abs(val - p["lo"]) <= TOLERANCE: at_limit = " ← EN PISO"
            except (ValueError, TypeError):
                pass
            print(f"  {k}: {v}  [rango: {p['lo']}-{p['hi']}]{at_limit}")

    print(f"\nExpansiones:")
    expansions = []
    modified = False

    for param, p in current.items():
        if param not in best:
            continue
        try:
            val = float(best[param])
        except (ValueError, TypeError):
            continue

        hit_ceiling = abs(val - p["hi"]) <= TOLERANCE
        hit_floor   = abs(val - p["lo"]) <= TOLERANCE
        if not hit_ceiling and not hit_floor:
            continue

        content, msg = expand_in_file(content, func_name, param, p, hit_floor, hit_ceiling)
        expansions.append(msg)
        if "✅" in msg:
            modified = True

    if not expansions:
        print("  ✅ Ningún parámetro en límite — rangos correctos")
    else:
        for e in expansions:
            print(e)

    if modified:
        with open(pattern_cfg, "w") as f:
            f.write(content)
        print(f"\n  Guardado: {pattern_cfg}")

    print("\n" + "=" * 60)


if __name__ == "__main__":
    main()
