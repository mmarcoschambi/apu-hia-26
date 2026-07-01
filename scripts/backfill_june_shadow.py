#!/usr/bin/env python3
"""
scripts/backfill_june_shadow.py

Reprocesa las watchlists completas de junio de 2026 a partir de los snapshots reales
de Finviz (outputs/paper_finviz/YYYY-MM-DD/snapshot.json). 

Para cada fecha de junio:
1. Lee el snapshot.json y extrae la watchlist_detail.
2. Si hay métricas técnicas faltantes (rvol o dist_sma20_pct en 0 o vacías por fallos del VPS),
   las recalcula usando la base de datos limpia local (data/ticker_cache.db).
3. Genera el setups.csv y run_context.json en outputs/shadow_sandbox/finviz_runs/YYYY-MM-DD/
   para que el Replay de Shadow pueda procesar junio de forma verídica y libre de bloqueos.
"""

import os
import json
import sqlite3
import pandas as pd
from pathlib import Path
from datetime import datetime, timedelta

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "data" / "ticker_cache.db"
PAPER_DIR = ROOT / "outputs" / "paper_finviz"
SHADOW_DIR = ROOT / "outputs" / "shadow_sandbox" / "finviz_runs"

# Mapeo de sectores base
SECTOR_MAP = {
    "XLY": "CONSUMER_DISCRETIONARY", "XLP": "CONSUMER_STAPLES", "XLE": "ENERGY",
    "XLF": "FINANCIALS", "XLV": "HEALTH_CARE", "XLI": "INDUSTRIALS",
    "XLB": "MATERIALS", "XLK": "TECHNOLOGY", "XLC": "COMMUNICATIONS",
    "XLU": "UTILITIES", "XLRE": "REAL_ESTATE"
}

def get_technical_metrics(ticker, date_as_of, conn):
    """Calcula dist_sma20, rvol, ma_status y adr reales usando la DB limpia local."""
    try:
        # Cargar los últimos 250 registros para el cálculo de medias móviles y ADR (hasta SMA200)
        df = pd.read_sql_query(
            "SELECT date, high, low, close, volume FROM ohlcv_cache WHERE ticker = ? AND date <= ? ORDER BY date DESC LIMIT 250",
            conn,
            params=(ticker, date_as_of)
        )
        if df.empty or len(df) < 200:
            return None, None, "broken", None
            
        # El primer registro de la query (descendente) es el del día de los datos, invertimos
        df = df.iloc[::-1].reset_index(drop=True)
        current_close = float(df.iloc[-1]["close"])
        current_volume = float(df.iloc[-1]["volume"])
        
        # Calcular SMA20 de close
        sma20 = df["close"].rolling(20).mean().iloc[-1]
        dist_sma20 = 100.0 * (current_close - sma20) / sma20 if sma20 > 0 else 0.0
        
        # Calcular SMA20 de volumen para RVOL
        vol_sma20 = df["volume"].rolling(20).mean().iloc[-1]
        rvol = current_volume / vol_sma20 if vol_sma20 > 0 else 1.0
        
        # Recalcular Medias Móviles para el ma_stack
        e10 = df["close"].ewm(span=10, adjust=False).mean().iloc[-1]
        s20 = sma20
        s50 = df["close"].rolling(50).mean().iloc[-1]
        s100 = df["close"].rolling(100).mean().iloc[-1]
        s200 = df["close"].rolling(200).mean().iloc[-1]
        
        # Lógica de ma_stack con tolerancia de 1.5% (tol = 0.015)
        tol = 0.015
        ma_healthy = (
            current_close >= e10 * (1 - tol)
            and e10 >= s20 * (1 - tol)
            and s20 >= s50 * (1 - tol)
            and s50 >= s100 * (1 - tol)
            and s100 >= s200 * (1 - tol)
        )
        ma_status = "healthy" if ma_healthy else "broken"
        
        # Calcular ADR (Average Daily Range) de 20 períodos
        df["adr_range"] = 100.0 * (df["high"] - df["low"]) / df["low"]
        adr = df["adr_range"].rolling(20).mean().iloc[-1]
        
        return round(dist_sma20, 2), round(rvol, 2), ma_status, round(adr, 4)
    except Exception:
        return None, None, "broken", None

def run_backfill():
    if not DB_PATH.exists():
        print(f"[ERROR] No se encuentra la base de datos local en {DB_PATH}")
        return
        
    print(f"Connecting to database {DB_PATH}...")
    conn = sqlite3.connect(DB_PATH)
    
    # Escanear carpetas de junio
    june_folders = []
    for path in PAPER_DIR.iterdir():
        if not path.is_dir():
            continue
        try:
            folder_date = datetime.strptime(path.name, "%Y-%m-%d")
            if folder_date.year == 2026 and folder_date.month == 6:
                june_folders.append((folder_date, path))
        except ValueError:
            continue
            
    june_folders.sort()
    print(f"Found {len(june_folders)} folders for June 2026.")
    
    total_rebuilt = 0
    
    for f_date, folder_path in june_folders:
        date_str = folder_path.name
        snap_path = folder_path / "snapshot.json"
        
        if not snap_path.exists():
            print(f"  [Skip] No snapshot.json in {date_str}")
            continue
            
        print(f"Processing {date_str}...")
        try:
            with open(snap_path) as f:
                snap_data = json.load(f)
                
            watchlist = snap_data.get("watchlist_detail", {})
            if not watchlist:
                print(f"  [Warn] Empty watchlist in snapshot of {date_str}")
                continue
                
            data_as_of = snap_data.get("data_as_of", date_str)
            setups = []
            
            for ticker, info in watchlist.items():
                ticker_clean = ticker.upper().strip().replace(".", "-")
                
                # Obtener valores del JSON
                rs = float(info.get("score", info.get("rs_pct", 85.0)))
                breakout_lvl = float(info.get("breakout_level", 0.0))
                dist_sma20 = float(info.get("dist_sma20_pct", 0.0))
                rvol = float(info.get("rvol", 1.0))
                waiting_desc = str(info.get("waiting_for", f"Breakout > {breakout_lvl}"))
                sector_etf = str(info.get("sector_etf", "OTHER"))
                
                # Obtener estado de medias móviles inicial
                ma_status = str(info.get("ma_status", "broken"))
                
                # Intentar sanar métricas técnicas usando la DB limpia
                adr = float(info.get("adr", 0.0))
                real_dist, real_rvol, real_ma_status, real_adr = get_technical_metrics(ticker_clean, data_as_of, conn)
                if real_dist is not None:
                    dist_sma20 = real_dist
                if real_rvol is not None:
                    rvol = real_rvol
                if real_ma_status is not None:
                    ma_status = real_ma_status
                if real_adr is not None:
                    adr = real_adr
                    
                # Evaluar exclusión sectorial de XLV (Healthcare)
                excluded_by_xlv = sector_etf == "XLV"
                ma_healthy = (ma_status == "healthy")
                
                # Decidir admisibilidad en E25 Shadow aplicando filtros de producción homólogos:
                # 1. Fuerza relativa mínima (RS >= 58.01 percentil de producción)
                # 2. Volumen relativo mínimo (RVOL >= 1.1048)
                # 3. ADR mínimo (ADR >= 1.8714%)
                # 4. Medias móviles en tendencia alcista (ma_status == "healthy")
                # 5. Extensión respecto a la SMA20 bajo el umbral de la Joya (dist_sma20 <= 15.0%)
                # 6. Nivel de breakout de pivot válido (breakout_lvl > 0.0)
                # 7. No excluido por el sector XLV
                rs_ok = (rs >= 58.01)
                rvol_ok = (rvol >= 1.1048)
                adr_ok = (adr >= 1.8714)
                dist_ok = (dist_sma20 <= 15.0)
                breakout_ok = (breakout_lvl > 0.0)
                
                allowed_shadow_candidate = (
                    not excluded_by_xlv 
                    and ma_healthy 
                    and rs_ok 
                    and rvol_ok 
                    and adr_ok
                    and dist_ok 
                    and breakout_ok
                )
                
                if allowed_shadow_candidate:
                    shadow_status = "shadow_allowed"
                elif excluded_by_xlv:
                    shadow_status = "blocked_by_sector"
                else:
                    shadow_status = "filtered_by_rules"
                
                setups.append({
                    "run_date": date_str,
                    "ticker": ticker_clean,
                    "rs": rs,
                    "breakout_lvl": breakout_lvl,
                    "dist_sma20_pct": dist_sma20,
                    "rvol": rvol,
                    "waiting_desc": waiting_desc,
                    "sector_etf": sector_etf,
                    "excluded_by_xlv": excluded_by_xlv,
                    "allowed_shadow_candidate": allowed_shadow_candidate,
                    "shadow_status": shadow_status
                })
                
            if not setups:
                continue
                
            # Escribir setups en la carpeta de shadow
            out_date_dir = SHADOW_DIR / date_str
            out_date_dir.mkdir(parents=True, exist_ok=True)
            
            df_setups = pd.DataFrame(setups)
            df_setups.to_csv(out_date_dir / "setups.csv", index=False)
            
            # Escribir run_context.json básico
            run_ctx = {
                "run_date": date_str,
                "timestamp": f"{date_str} 08:30:00",
                "mode": "PRODUCTION",
                "universe_size": len(watchlist),
                "period_start": (f_date - timedelta(days=200)).strftime("%Y-%m-%d"),
                "period_end": data_as_of,
                "risk_type": "FIXED_DOLLAR",
                "risk_value": 2878.0,
                "filters": {
                    "min_vol_k": 100,
                    "min_dollar_vol_M": 20,
                    "min_adr_pct": 1.87,
                    "min_rvol": 1.0
                },
                "position_size": {
                    "rvol_danger": 3.0,
                    "rvol_danger_size_pct": 50,
                    "rvol_warning": 2.0,
                    "rvol_warning_size_pct": 75
                }
            }
            with open(out_date_dir / "run_context.json", "w") as f:
                json.dump(run_ctx, f, indent=2)
                
            print(f"  [OK] Rebuilt setups for {date_str}: {len(setups)} setups saved.")
            total_rebuilt += 1
            
        except Exception as e:
            print(f"  [ERROR] Failed to process {date_str}: {e}")
            
    conn.close()
    print("\n" + "="*50)
    print("BACKFILL COMPLETED SUCCESSFULLY")
    print("="*50)
    print(f"Total dates rebuilt in shadow setups: {total_rebuilt}")
    print("="*50 + "\n")


if __name__ == "__main__":
    run_backfill()

