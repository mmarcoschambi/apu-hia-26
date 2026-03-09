#!/usr/bin/env python3
"""
Comparacion: Backtest SIN vs CON bonus de patrones
Uso: python3 scripts/optimization/quick_compare.py
"""
import sys, warnings, sqlite3, pickle
warnings.filterwarnings("ignore")
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import pandas as pd
import numpy as np
from src.backtest.vectorbt_engine_advanced import AdvancedVectorBTEngine
from src.config.dynamic_config import load_production_config

ROOT = Path(__file__).resolve().parent.parent.parent

# --- Cargar config ---
config = load_production_config(str(ROOT / "config" / "production_config.json"))
t1 = config["tier1_strategy"]
t2 = config["tier2_filters"]
t3 = config["tier3_risk"]

# --- Universo: solo tickers que esten en AMBOS (DB + pattern cache) ---
def get_valid_universe(start, end, min_days=600):
    # Tickers con datos suficientes en DB
    conn = sqlite3.connect(str(ROOT / "data" / "ticker_cache.db"))
    rows = conn.execute("""
        SELECT ticker FROM ohlcv_cache
        WHERE date BETWEEN ? AND ?
        GROUP BY ticker HAVING COUNT(*) >= ?
        ORDER BY ticker
    """, (start, end, min_days)).fetchall()
    conn.close()
    db_tickers = {r[0] for r in rows}

    # Tickers en pattern cache
    cache_file = ROOT / "data" / "pattern_matrix.pkl"
    with open(cache_file, "rb") as f:
        matrix = pickle.load(f)
    cache_tickers = set(matrix["confidence"].columns.tolist())

    valid = sorted(db_tickers & cache_tickers)
    print(f"[INFO] Universo valido (DB + cache): {len(valid)} tickers")
    return valid

START  = "2021-01-01"
END    = "2025-12-31"
CAPITAL = 100_000
RISK    = int(CAPITAL * float(t3.get("risk_fraction", 0.005)))

universe = get_valid_universe(START, END)

base_params = dict(
    universe=universe,
    start_date=START,
    end_date=END,
    initial_capital=CAPITAL,
    risk_dollars=RISK,
    tp1_r=float(t1["tp1_r"]),
    tp2_r=float(t1["tp2_r"]),
    tp1_pct=float(t1["tp1_pct"]),
    tp2_pct=float(t1["tp2_pct"]),
    runner_pct=float(t1["runner_pct"]),
    min_rvol=float(t2["min_rvol"]),
    min_adr=float(t2["min_adr"]),
    max_dist_sma20=float(t2["max_dist_sma20"]),
    min_consolidation_days=int(t2.get("min_consolidation_days", 5)),
    min_volume=int(t2.get("min_volume", 100000)),
    min_dollar_volume=float(t2.get("min_dollar_volume", 120000000)),
    use_rs_percentile=bool(t2.get("use_rs_percentile", True)),
    min_rs_percentile=float(t2.get("min_rs_percentile", 70.0)),
    rs_lookback_days=int(t2.get("rs_lookback_days", 60)),
    mode="production",
    offline_mode=True,
    use_adaptive_filtering=True,
    use_pattern_filter=False,
    require_spy_above_sma50=True,
    use_market_regime_filter=True,
)

# --- Correr comparacion ---
runs = [
    ("SIN_PATRON", 0.00, 0.00, 0.00),
    ("CON_PATRON", 0.30, 0.20, 0.10),
]

all_results = {}
for label, bh, bm, bl in runs:
    print(f"\n{'='*55}")
    print(f"  Corriendo: {label}")
    print(f"{'='*55}")
    engine = AdvancedVectorBTEngine(
        **base_params,
        pattern_bonus_high=bh,
        pattern_bonus_med=bm,
        pattern_bonus_low=bl,
    )
    r = engine.run_backtest()

    # FIX: metricas estan en el nivel raiz, no en r["metrics"]
    trades_df = r.get("trades_df")
    n_trades = len(trades_df) if trades_df is not None else 0

    sharpe    = r.get("sharpe_ratio", 0.0)
    win_rate  = r.get("win_rate", 0.0) * 100
    max_dd    = r.get("max_drawdown", 0.0) * 100
    tot_ret   = r.get("total_return", 0.0) * 100
    pf        = r.get("profit_factor", 0.0)

    # Trades con patron vs sin patron (si hay columna entry_score)
    pat_info = ""
    if trades_df is not None and len(trades_df) > 0:
        if "entry_score" in trades_df.columns:
            avg_score = trades_df["entry_score"].mean()
            pat_info = f" | Avg Score: {avg_score:.3f}"

    all_results[label] = {
        "sharpe": sharpe, "win_rate": win_rate, "max_dd": max_dd,
        "total_return": tot_ret, "profit_factor": pf, "trades": n_trades,
        "avg_score": trades_df["entry_score"].mean() if (trades_df is not None and "entry_score" in (trades_df.columns if trades_df is not None else [])) else 0,
    }

    print(f"  Trades    : {n_trades}")
    print(f"  Sharpe    : {sharpe:.3f}")
    print(f"  Win Rate  : {win_rate:.1f}%")
    print(f"  Max DD    : {max_dd:.1f}%")
    print(f"  Retorno   : {tot_ret:.1f}%")
    print(f"  Prof.Factor: {pf:.2f}{pat_info}")

# --- Tabla comparativa final ---
print(f"\n{'='*55}")
print(f"  COMPARACION FINAL")
print(f"{'='*55}")
print(f"{'Metrica':<18} {'SIN_PATRON':>12} {'CON_PATRON':>12} {'Delta':>10}")
print(f"{'-'*55}")

metrics_display = [
    ("Sharpe",        "sharpe",       "{:.3f}"),
    ("Win Rate %",    "win_rate",     "{:.1f}%"),
    ("Max DD %",      "max_dd",       "{:.1f}%"),
    ("Retorno %",     "total_return", "{:.1f}%"),
    ("Profit Factor", "profit_factor","{:.2f}"),
    ("N Trades",      "trades",       "{:.0f}"),
    ("Avg Entry Score","avg_score",   "{:.3f}"),
]

s = all_results.get("SIN_PATRON", {})
c = all_results.get("CON_PATRON", {})

for name, key, fmt in metrics_display:
    sv = s.get(key, 0)
    cv = c.get(key, 0)
    delta = cv - sv
    sign = "+" if delta > 0 else ""
    print(f"{name:<18} {fmt.format(sv):>12} {fmt.format(cv):>12} {sign}{fmt.format(delta):>9}")

print(f"{'='*55}")
verdict = "PATRON AYUDA" if c.get("sharpe",0) > s.get("sharpe",0) else "SIN DIFERENCIA / PATRON NO AYUDA"
print(f"\nVeredicto: {verdict}")
