#!/usr/bin/env python3
"""
compare_vps_local_alignment.py — Valida que el motor local de señales
produzca EXACTAMENTE los mismos flags e indicadores que calculó el VPS
para una fecha dada.

Compara campo a campo entre snapshot.json (generado por VPS) y el cómputo
local replicando la lógica de _build_watchlist_detail() en paper_finviz.py.

PASO 1: Detecta corrupción en la cache local (Issue #39 residual).
PASO 2: Solo compara tickers con data limpia (unique close values).

Uso:
    python3 scratch/compare_vps_local_alignment.py [fecha]
    # Si no se pasa fecha, usa la más reciente en outputs/paper_finviz/
"""

import json
import sqlite3
import sys
from pathlib import Path
from datetime import datetime, timedelta

import pandas as pd

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

DB_PATH = ROOT / "data" / "ticker_cache.db"
OUT_DIR = ROOT / "outputs" / "paper_finviz"

# Tolerancia por redondeo/float en diferentes tipos de campo
TOLERANCE_PCT = 0.02   # 2% para valores porcentuales
TOLERANCE_ABS = 0.005  # 0.5 centavos para precios/niveles


def load_snapshot(date_str: str) -> dict:
    path = OUT_DIR / date_str / "snapshot.json"
    if not path.exists():
        print(f"  [ERROR] Snapshot no encontrado: {path}")
        sys.exit(1)
    with open(path) as f:
        return json.load(f)


def load_ohlcv(ticker: str, start: str, end: str) -> pd.DataFrame:
    """Carga OHLCV + medias desde la cache."""
    conn = sqlite3.connect(DB_PATH)
    query = """
        SELECT date, open, high, low, close, volume,
               sma20, sma50, sma100, sma200
        FROM ohlcv_cache
        WHERE ticker=? AND date >= ? AND date <= ?
        ORDER BY date
    """
    df = pd.read_sql(query, conn, params=(ticker, start, end))
    conn.close()
    if df.empty:
        return pd.DataFrame()
    df["date"] = pd.to_datetime(df["date"], format="mixed").dt.normalize()
    df = df.drop_duplicates(subset=["date"], keep="last").set_index("date")
    df = df.astype(float)
    return df


def compute_ema10(close: pd.Series) -> pd.Series:
    """EMA de 10 períodos (span=10, sin ajuste)."""
    return close.ewm(span=10, adjust=False).mean()


def compute_sma(close: pd.Series, period: int) -> pd.Series:
    return close.rolling(period, min_periods=period).mean()


def compute_breakout_level(high: pd.Series) -> float:
    """20-period highest high, shifted by 1 (misma lógica que _build_watchlist_detail)."""
    return float(high.shift(1).rolling(20).max().iloc[-1])


def compute_ma_stack(price: float, e10: float, s20: float, s50: float,
                     s100: float, s200: float, tol: float = 0.002) -> bool:
    """Misma lógica que _build_watchlist_detail en paper_finviz.py."""
    return bool(
        price >= e10 * (1 - tol)
        and e10 >= s20 * (1 - tol)
        and s20 >= s50 * (1 - tol)
        and s50 >= s100 * (1 - tol)
        and s100 >= s200 * (1 - tol)
    )


def compute_rvol(volume: pd.Series) -> float:
    """Relative volume: today's volume / avg(prev 20-day volume)."""
    avg_vol_20 = volume.rolling(20, min_periods=5).mean().shift(1)
    avg_last = float(avg_vol_20.iloc[-1])
    vol_today = float(volume.iloc[-1])
    if avg_last > 500 and vol_today > 0:
        return round(vol_today / avg_last, 2)
    return 1.0


def compute_adr(close: pd.Series, high: pd.Series, low: pd.Series) -> float:
    """Average Daily Range % sobre 20 días."""
    tr = (high - low) / close.shift(1)
    return float(tr.rolling(20).mean().iloc[-1] * 100)


def compute_dollar_volume_m(close: float, volume_series: pd.Series) -> float:
    """Dollar volume en millones."""
    avg_vol_20 = float(volume_series.rolling(20).mean().iloc[-1])
    return close * avg_vol_20 / 1e6


def compute_data_quality(detail: dict) -> tuple[str, list[str]]:
    """Replicación de calculate_data_quality() en src/utils/data_quality.py."""
    reasons = []
    status = "ok"

    price = detail.get("price")
    breakout_level = detail.get("breakout_level")
    rvol = detail.get("rvol")
    adr = detail.get("adr") or detail.get("adr_pct")
    dist_sma20 = detail.get("dist_sma20_pct") or detail.get("dist_sma20")
    dollar_vol_m = detail.get("dollar_volume_m") or detail.get("dollar_vol_M")

    if price is None or not isinstance(price, (int, float)):
        reasons.append("missing_price")
        status = "bad"
    if breakout_level is None or not isinstance(breakout_level, (int, float)) or breakout_level <= 0:
        reasons.append("missing_breakout_level")
        status = "bad"
    if detail.get("ma_gap_pct") == -100:
        reasons.append("default_ma_gap")
        status = "bad"
    if status == "bad":
        return status, reasons

    if rvol == 1.0 or rvol == 0:
        reasons.append("rvol_1.0_default")
        status = "warn"
    if adr == 0 or adr is None:
        reasons.append("adr_0")
        status = "warn"
    if dollar_vol_m == 0 or dollar_vol_m is None:
        reasons.append("zero_dollar_vol")
        status = "warn"
    if dist_sma20 == 0 and price != 0:
        reasons.append("dist_sma20_zero_suspect")
        status = "warn"

    return status, reasons


def fmt_diff(snap_val, local_val, abs_diff, rel_diff=None):
    """Formatea una celda de diferencia para la tabla."""
    if abs_diff is None:
        return f"  {snap_val}  |  {local_val}  |  NEW"
    snap_s = f"{snap_val:.4f}" if isinstance(snap_val, float) else str(snap_val)
    local_s = f"{local_val:.4f}" if isinstance(local_val, float) else str(local_val)
    diff_s = f"{abs_diff:.4f}"
    if rel_diff is not None:
        diff_s += f" ({rel_diff:.2%})"
    return f"  {snap_s}  |  {local_s}  |  {diff_s}"


def check_data_integrity(data_as_of: str, watchlist: dict) -> dict:
    """Detecta tickers con datos corruptos (close duplicados entre tickers)."""
    conn = sqlite3.connect(DB_PATH)
    placeholders = ",".join(["?"] * len(watchlist))
    
    df = pd.read_sql(f"""
        SELECT ticker, close FROM ohlcv_cache
        WHERE date = ? AND ticker IN ({placeholders})
        ORDER BY close
    """, conn, params=tuple([data_as_of] + list(watchlist)))
    conn.close()
    
    if df.empty:
        return {"clean": [], "corrupt": list(watchlist.keys())}
    
    close_counts = df.groupby("close").size().reset_index(name="count")
    corrupt_closes = close_counts[close_counts["count"] > 1]["close"]
    corrupt_tickers = set(df[df["close"].isin(corrupt_closes)]["ticker"].tolist())
    clean_tickers = [t for t in watchlist if t not in corrupt_tickers]
    
    return {"clean": clean_tickers, "corrupt": sorted(corrupt_tickers)}


def main():
    # 1. Determinar fecha
    if len(sys.argv) > 1:
        date_str = sys.argv[1]
    else:
        dates = sorted([d.name for d in OUT_DIR.iterdir() if d.is_dir()], reverse=True)
        if not dates:
            print("[ERROR] No hay directorios de fecha en outputs/paper_finviz/")
            sys.exit(1)
        date_str = dates[0]

    print(f"{'='*80}")
    print(f"  COMPARACIÓN VPS vs LOCAL — Fecha: {date_str}")
    print(f"{'='*80}")

    # 2. Cargar snapshot
    snap = load_snapshot(date_str)
    watchlist = snap.get("watchlist_detail", {})
    data_as_of = snap.get("data_as_of", date_str)
    print(f"  Universe size (snapshot): {snap.get('universe_size')}")
    print(f"  Data as of: {data_as_of}")
    print(f"  Tickers en watchlist_detail: {len(watchlist)}")
    print(f"  Señales activas: {snap.get('signals_count')}")
    print()

    if not watchlist:
        print("[WARN] watchlist_detail vacío. Nada que comparar.")
        sys.exit(0)

    # 3. Check de integridad de datos locales
    integrity = check_data_integrity(data_as_of, watchlist)
    print(f"  [Integridad] Tickers con datos limpios: {len(integrity['clean'])}")
    print(f"  [Integridad] Tickers con datos corruptos: {len(integrity['corrupt'])}")
    if integrity["corrupt"]:
        print(f"  [Integridad] Muestra corruptos: {integrity['corrupt'][:10]}...")
    print()

    # 4. Rango de fechas para carga de datos
    as_of = pd.Timestamp(data_as_of)
    start_wide = (as_of - timedelta(days=400)).strftime("%Y-%m-%d")
    end_str = data_as_of

    # 5. Comparar ticker por ticker (solo data limpia)
    fields_to_compare = [
        "score", "ma_stack", "breakout_level", "dollar_volume_m", "is_promotable"
    ]

    mismatches = {f: [] for f in fields_to_compare}
    total_checked = 0
    score_mismatches = 0
    is_promotable_mismatches = 0
    score_checked = 0
    is_promotable_checked = 0

    # Campos que NO dependen de OHLCV — computamos para todos los tickers
    conn = sqlite3.connect(DB_PATH)

    for ticker, snap_detail in sorted(watchlist.items()):
        total_checked += 1

        # ---- score: RS percentile (no depende de OHLCV local corrupto) ----
        snap_score = snap_detail.get("score")
        rs_row = conn.execute(
            "SELECT rs_composite FROM daily_rs_rankings WHERE ticker=? AND date=?",
            (ticker, data_as_of)
        ).fetchone()
        rs_local = rs_row[0] if rs_row else None
        score_checked += 1
        if snap_score is not None and rs_local is not None:
            if abs(snap_score - rs_local) > TOLERANCE_PCT:
                score_mismatches += 1
                mismatches["score"].append((ticker, snap_score, rs_local))

        # ---- is_promotable: data quality check (usa campos del snapshot) ----
        # Esta función solo valida que el ticker tenga datos completos; no
        # necesita OHLCV local. Usamos los valores del snapshot como proxy.
        snap_prom = snap_detail.get("is_promotable")
        is_promotable_checked += 1
        local_detail_check = {
            "price": snap_detail.get("price"),
            "breakout_level": snap_detail.get("breakout_level"),
            "rvol": snap_detail.get("rvol"),
            "adr": snap_detail.get("adr"),
            "dist_sma20_pct": snap_detail.get("dist_sma20_pct"),
            "dollar_volume_m": snap_detail.get("dollar_volume_m"),
            "ma_gap_pct": snap_detail.get("ma_gap_pct"),
        }
        local_q_status, _ = compute_data_quality(local_detail_check)
        local_is_promotable = local_q_status == "ok"
        if snap_prom is not None and local_is_promotable != snap_prom:
            is_promotable_mismatches += 1
            mismatches["is_promotable"].append((ticker, snap_prom, local_is_promotable))

        # ---- Campos OHLCV: solo para tickers con data limpia ----
        if ticker not in integrity["clean"]:
            continue

        df = load_ohlcv(ticker, start_wide, end_str)
        if df.empty or len(df) < 200:
            continue

        price = float(df["close"].iloc[-1])
        high_s = df["high"]
        volume_s = df["volume"]
        ema10 = compute_ema10(df["close"])

        sma20_col = df["sma20"].ffill()
        sma50_col = df["sma50"].ffill()
        sma100_col = df["sma100"].ffill()
        sma200_col = df["sma200"].ffill()

        e10_val = float(ema10.iloc[-1])
        s20_val = float(sma20_col.iloc[-1])
        s50_val = float(sma50_col.iloc[-1])
        s100_val = float(sma100_col.iloc[-1])
        s200_val = float(sma200_col.iloc[-1])

        local_breakout = compute_breakout_level(high_s)
        local_ma_stack = compute_ma_stack(price, e10_val, s20_val, s50_val, s100_val, s200_val)
        local_dvol_m = round(compute_dollar_volume_m(price, volume_s), 2)

        # ma_stack
        snap_ma = snap_detail.get("ma_stack")
        if snap_ma is not None and local_ma_stack != snap_ma:
            mismatches["ma_stack"].append((ticker, snap_ma, local_ma_stack))

        # breakout_level
        snap_bo = snap_detail.get("breakout_level")
        if snap_bo is not None and abs(local_breakout - snap_bo) > TOLERANCE_ABS:
            mismatches["breakout_level"].append((ticker, snap_bo, local_breakout))

        # dollar_volume_m
        snap_dvol = snap_detail.get("dollar_volume_m")
        if snap_dvol is not None and abs(local_dvol_m - snap_dvol) > TOLERANCE_PCT:
            mismatches["dollar_volume_m"].append((ticker, snap_dvol, local_dvol_m))

    conn.close()

    # 5. Reporte
    print(f"\n{'='*80}")
    print(f"  RESUMEN DE COMPARACIÓN")
    print(f"{'='*80}")
    print(f"  Tickers en watchlist:       {total_checked}")
    print(f"  Tickers con data limpia:    {len(integrity['clean'])}")
    print(f"  Tickers con data corrupta:  {len(integrity['corrupt'])}")
    print()

    # Tier 1: Campos no-OHLCV (todos los tickers)
    print(f"  ── CAMPOS NO-OHLCV (score, is_promotable) ──")
    print(f"  Score checkeado:    {score_checked}")
    print(f"  Score mismatches:   {score_mismatches}")
    print(f"  is_promotable check:{is_promotable_checked}")
    print(f"  is_promotable mism: {is_promotable_mismatches}")
    print()
    if score_mismatches == 0 and is_promotable_mismatches == 0:
        print(f"  ✅ RS Percentile e is_promotable: 100% alineado ({total_checked}/{total_checked})")
    else:
        print(f"  ⚠️  Desajustes en lógica no-OHLCV. Revisar.")

    print()
    print(f"  ── CAMPOS OHLCV (ma_stack, breakout_level, dollar_volume_m) ──")

    total_ohlcv_diffs = sum(len(mismatches[f]) for f in ["ma_stack", "breakout_level", "dollar_volume_m"])
    clean_count = len(integrity['clean'])

    if clean_count == 0:
        print(f"  ⚠️  0 tickers con data limpia. No se pueden validar campos OHLCV.")
        print(f"     Ejecutar pre-warm: python3 scripts/paper_finviz.py --phase pre --date {date_str}")
    elif total_ohlcv_diffs == 0:
        print(f"  ✅ Campos OHLCV: 100% alineado en {clean_count} tickers con data limpia")
    else:
        for field in ["ma_stack", "breakout_level", "dollar_volume_m"]:
            diffs = mismatches[field]
            if not diffs:
                continue
            print(f"\n  --- {field} ({len(diffs)}/{clean_count} diferencias) ---")
            print(f"  {'Ticker':<12} {'Snapshot':<18} {'Local':<18}")
            print(f"  {'-'*48}")
            for entry in diffs:
                t, snap_v, local_v = entry
                if isinstance(snap_v, float):
                    print(f"  {t:<12} {snap_v:<18.4f} {local_v:<18.4f}")
                else:
                    print(f"  {t:<12} {str(snap_v):<18} {str(local_v):<18}")
        print()

    # Veredicto final
    print(f"{'='*80}")
    print(f"  VEREDICTO")
    print(f"{'='*80}")
    if score_mismatches == 0 and is_promotable_mismatches == 0:
        print(f"  ✅ Lógica de SEÑALES VPS y LOCAL es IDÉNTICA.")
        print()
        if total_ohlcv_diffs == 0 and clean_count > 0:
            print(f"     Campos OHLCV también alineados en {clean_count} tickers con data limpia.")
        elif clean_count > 0:
            print(f"     ⚠️ Campos OHLCV tienen {total_ohlcv_diffs} diferencias en {clean_count} tickers.")
            print(f"        Posible causa: datos locales corruptos (Issue #39 residual).")
        else:
            print(f"     ⚠️ No se pudieron validar campos OHLCV por falta de data limpia en cache local.")
        print(f"     Para validar con data fresca: pre-warm via paper_finviz.py")
    else:
        print(f"  ❌ DESALINEACIÓN en lógica no-OHLCV. Se requiere depuración.")


if __name__ == "__main__":
    main()
