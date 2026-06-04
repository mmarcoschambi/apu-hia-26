#!/usr/bin/env python3
import os
import re
import json
from glob import glob
from datetime import datetime

import os
import re
import json
from glob import glob
from datetime import datetime
from pathlib import Path
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent
AUTO_LEDGER_ROOT = PROJECT_ROOT / "outputs" / "live_paper_auto" / "runs"
DEMO_LEDGER_ROOT = PROJECT_ROOT / "outputs" / "paper_demo_telegram" / "runs"
SIGNALS_ROOT = PROJECT_ROOT / "outputs" / "live_signals"

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

def audit_paper_trading():
    import pytz
    tz = pytz.timezone("America/New_York")
    date = datetime.now(tz).strftime("%Y-%m-%d")
    
    # 1. Signals Audit
    signals_path = SIGNALS_ROOT / date / "combined.csv"
    signals_count = 0
    promoter_count = 0
    if signals_path.exists():
        try:
            df = pd.read_csv(signals_path)
            signals_count = len(df)
            if "decision_source" in df.columns:
                promoter_count = len(df[df["decision_source"] == "finviz_live_promoter"])
        except: pass
    
    # 2. Positions Audit
    def count_open(root, d):
        p = root / d / "positions.csv"
        if not p.exists(): return 0
        try:
            df = pd.read_csv(p)
            open_mask = (df["status"] == "open") & (~df.get("exited", False))
            return len(df[open_mask])
        except: return 0

    auto_open = count_open(AUTO_LEDGER_ROOT, date)
    demo_open = count_open(DEMO_LEDGER_ROOT, date)
    
    # 3. Log Audit
    last_actions = []
    log_path = AUTO_LEDGER_ROOT / date / "trade_log.txt"
    if log_path.exists():
        try:
            with open(log_path, "r") as f:
                last_actions = f.readlines()[-5:]
        except: pass

    # 4. Auto Guardrail Status
    auto_enabled = os.getenv("LIVE_AUTO_TRADER_ENABLED", "0") in ("1", "true", "yes")

    return {
        "date": date,
        "signals_file": signals_path.exists(),
        "signals_count": signals_count,
        "promoter_count": promoter_count,
        "auto_open": auto_open,
        "demo_open": demo_open,
        "last_actions": [a.strip() for a in last_actions],
        "auto_enabled": auto_enabled
    }

def show_status():
    variant, pct, green = get_current_variant()
    last_bt = get_last_backtest()
    audit = audit_paper_trading()
    
    print("\n" + "="*60)
    print(" 🚀 MOMENTUM-V2: ESTADO ACTUAL DEL ENTORNO")
    print("="*60)
    
    print(f"\n 📝 CONFIGURACIÓN ACTIVA EN CÓDIGO:")
    print(f"    ➤ VARIANTE:  {variant}")
    print(f"    ➤ RTS PCT:   {pct}%")
    print(f"    ➤ GREEN:     {green}")
    
    print(f"\n 🤖 PAPER TRADING AUDIT ({audit['date']}):")
    auto_status = "🔥 ENABLED" if audit['auto_enabled'] else "❄️ DISABLED"
    print(f"    ➤ AUTO TRADER:  {auto_status}")
    print(f"    ➤ SIGNALS:      {audit['signals_count']} total ({audit['promoter_count']} promoted by live)")
    print(f"    ➤ OPEN AUTO:    {audit['auto_open']} positions")
    print(f"    ➤ OPEN DEMO:    {audit['demo_open']} positions")
    
    if audit['last_actions']:
        print(f"\n 📜 ÚLTIMAS ACCIONES AUTO-TRADER:")
        for action in audit['last_actions']:
            print(f"    ➤ {action}")
    
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
