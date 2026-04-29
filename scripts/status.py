#!/usr/bin/env python3
import os
import re
import json
from glob import glob
from datetime import datetime

def get_current_variant():
    file_path = "src/screeners/triad_rts.py"
    if not os.path.exists(file_path):
        return "Unknown", "N/A", "N/A"
    
    with open(file_path, 'r') as f:
        content = f.read()
    
    pct_match = re.search(r'"min_rts_pct":\s*(\d+\.\d+)', content)
    green_match = re.search(r'"require_green_candle":\s*(True|False)', content)
    
    pct = pct_match.group(1) if pct_match else "90.0"
    green = green_match.group(1) if green_match else "True"
    
    variant = "CUSTOM"
    if pct == "90.0" and green == "True": variant = "BASELINE (PCT 90)"
    elif pct == "70.0" and green == "False": variant = "T3 (PCT 70, No Green)"
    elif pct == "60.0" and green == "False": variant = "T4 (PCT 60, No Green)"
    
    return variant, pct, green

def get_last_backtest():
    outputs_dir = "outputs/backtests"
    files = sorted(glob(os.path.join(outputs_dir, "analytics_bt_*_IS.json")), key=os.path.getmtime, reverse=True)
    if not files:
        return "Ninguno encontrado"
    
    last_file = os.path.basename(files[0])
    mtime = datetime.fromtimestamp(os.path.getmtime(files[0])).strftime('%Y-%m-%d %H:%M:%S')
    return f"{last_file} ({mtime})"

def show_status():
    variant, pct, green = get_current_variant()
    last_bt = get_last_backtest()
    
    print("\n" + "="*60)
    print(" 🚀 MOMENTUM-V2: ESTADO ACTUAL DEL ENTORNO")
    print("="*60)
    
    print(f"\n 📝 CONFIGURACIÓN ACTIVA EN CÓDIGO:")
    print(f"    ➤ VARIANTE:  {variant}")
    print(f"    ➤ RTS PCT:   {pct}%")
    print(f"    ➤ GREEN:     {green}")
    
    print(f"\n 📊 ÚLTIMO BACKTEST GENERADO:")
    print(f"    ➤ ARCHIVO:   {last_bt}")
    
    print(f"\n 📂 VARIANTES GUARDADAS:")
    variant_files = glob("outputs/backtests/variant_*_IS.json")
    if not variant_files:
        print("    ➤ (Ninguna variante guardada aún)")
    for f in sorted(variant_files):
        name = os.path.basename(f).replace("variant_", "").replace("_IS.json", "")
        print(f"    ➤ {name}")

    print("\n" + "="*60)
    print(" 🛠️  COMANDOS RÁPIDOS:")
    print("  ./scripts/set_triad_variant.py T3       -> Cambiar a T3")
    print("  python3 scripts/runbook_backtest_validation.py --step 4 -> Rebuild Cache")
    print("  python3 scripts/runbook_backtest_validation.py --step 5 -> Run Backtest")
    print("  ./scripts/compare_variants.py           -> Ver Tabla Comparativa")
    print("="*60 + "\n")

if __name__ == "__main__":
    show_status()
