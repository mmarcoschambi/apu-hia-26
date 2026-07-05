#!/usr/bin/env python3
"""
scratch/count_real_shadow_triggers.py

Cruza los setups permitidos de la Joya (E25 Shadow) contra los precios 'high' reales
de data/ticker_cache.db para determinar cuántos de ellos gatillaron (hicieron trigger)
en la rueda real de trading durante los últimos 2 meses.
"""

import sqlite3
import pandas as pd
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "data" / "ticker_cache.db"
REPORT_CSV = ROOT / "outputs" / "shadow_sandbox" / "replay" / "report.csv"

def count_triggers():
    if not REPORT_CSV.exists():
        print(f"[ERROR] No se encuentra el reporte de replay en {REPORT_CSV}")
        return
        
    print(f"Loading shadow candidates from {REPORT_CSV}...")
    df = pd.read_csv(REPORT_CSV)
    
    # Filtrar solo los candidatos permitidos por E25 Shadow + ex-XLV
    allowed_df = df[df["allowed_shadow_candidate"] == True].copy()
    total_allowed = len(allowed_df)
    print(f"Total allowed shadow candidates: {total_allowed}")
    
    if total_allowed == 0:
        print("No allowed shadow candidates found.")
        return
        
    print(f"Connecting to database {DB_PATH} to match price data...")
    conn = sqlite3.connect(DB_PATH)
    
    triggers = []
    
    for idx, row in allowed_df.iterrows():
        ticker = str(row["ticker"]).strip().upper().replace(".", "-")
        date_str = str(row["date"]).split(" ")[0]
        breakout_lvl = float(row["breakout_lvl"])
        
        # Buscar el precio máximo (high) de ese día en la caché de producción limpia
        cur = conn.cursor()
        cur.execute(
            "SELECT high FROM ohlcv_cache WHERE ticker = ? AND date = ?",
            (ticker, date_str)
        )
        res = cur.fetchone()
        
        triggered = False
        high_price = None
        if res:
            high_price = res[0]
            if high_price is not None and high_price >= breakout_lvl:
                triggered = True
        
        triggers.append({
            "date": date_str,
            "ticker": ticker,
            "breakout_lvl": breakout_lvl,
            "high": high_price,
            "triggered": triggered
        })
        
    conn.close()
    
    res_df = pd.DataFrame(triggers)
    total_triggers = int(res_df["triggered"].sum())
    trigger_rate = (total_triggers / total_allowed) * 100 if total_allowed > 0 else 0
    
    print("\n" + "="*50)
    print("VEREDICTO DE TRIGGERS REALES (E25 SHADOW)")
    print("="*50)
    print(f"Candidatos Permitidos (E25 Shadow): {total_allowed}")
    print(f"Gatillaron Realmente (High >= Breakout): {total_triggers}")
    print(f"Tasa de Trigger: {trigger_rate:.2f}%")
    print("="*50)
    
    # Agrupar por semana ending Friday
    def to_friday_str(date_val):
        dt = pd.to_datetime(date_val)
        weekday = dt.weekday()
        from datetime import timedelta
        if weekday <= 4:
            friday = dt + timedelta(days=(4 - weekday))
        else:
            friday = dt + timedelta(days=(4 - weekday + 7))
        return friday.strftime("%Y-%m-%d")
        
    res_df["week_ending"] = res_df["date"].apply(to_friday_str)
    
    weekly = res_df.groupby("week_ending").agg(
        candidatos=("triggered", "count"),
        triggers=("triggered", "sum")
    ).reset_index()
    
    weekly["tasa_trigger"] = (weekly["triggers"] / weekly["candidatos"] * 100).round(2)
    print("\nDesglose Semanal de Ejecución Real:")
    print(weekly.to_string(index=False))
    print("="*50 + "\n")

if __name__ == "__main__":
    count_triggers()
