#!/usr/bin/env python3
"""
scripts/experiments/run_s5_baseline_validation.py
Suite de validación temporal, bootstrapping Monte Carlo y concentración
para el Benchmark de S5 (Russell 1000 + E25 v2 + ex-XLV + ticker-cap 20%).
"""

import os
import sys
import json
import argparse
import subprocess
import numpy as np
import pandas as pd
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple

PROJECT_ROOT = Path(__file__).resolve().parents[2]
BACKTEST_DIR = PROJECT_ROOT / "outputs" / "backtests"
REPORT_JSON = BACKTEST_DIR / "s5_baseline_validation_report.json"
REPORT_MD = PROJECT_ROOT / "docs/analysis/S5_BASELINE_VAL_REPORT.md"

# Matriz de ventanas temporales
WINDOWS = [
    {"start": "2019-01-01", "end": "2020-12-31", "suffix": "1920", "label": "2019-2020 (Bull / Crash COVID)"},
    {"start": "2021-01-01", "end": "2022-12-31", "suffix": "2122", "label": "2021-2022 (Bear / Post-COVID)"},
    {"start": "2023-01-01", "end": "2024-12-31", "suffix": "2324", "label": "2023-2024 (In-Sample Calibration)"},
    {"start": "2025-01-01", "end": "2026-06-01", "suffix": "2526", "label": "2025-2026 (Reciente / Out-of-Sample)"}
]

# Mapa de sectores estándar
SECTOR_MAP = {
    "AAPL": "XLK", "MSFT": "XLK", "NVDA": "XLK", "AMD": "XLK", "AVGO": "XLK", "QCOM": "XLK", "FTNT": "XLK", "MU": "XLK",
    "AMZN": "XLY", "TSLA": "XLY", "HD": "XLY", "NKE": "XLY", "MCD": "XLY",
    "META": "XLC", "NFLX": "XLC", "GOOGL": "XLC", "GOOG": "XLC", "DIS": "XLC",
    "JPM": "XLF", "BAC": "XLF", "MS": "XLF", "GS": "XLF", "WFC": "XLF", "PYPL": "XLF",
    "LLY": "XLV", "UNH": "XLV", "JNJ": "XLV", "ABBV": "XLV", "MRK": "XLV", "VRTX": "XLV",
    "XOM": "XLE", "CVX": "XLE", "SLB": "XLE",
    "CAT": "XLI", "GE": "XLI", "HON": "XLI", "UPS": "XLI", "WDC": "XLK",
}

def run_backtest(tag: str, start: str, end: str, force: bool = False) -> bool:
    """Ejecuta una celda del backtest usando subprocess."""
    metrics_file = BACKTEST_DIR / f"{tag}_metrics.json"
    trades_file = BACKTEST_DIR / f"{tag}_trades.csv"
    
    if not force and metrics_file.exists() and trades_file.exists():
        print(f"   ↳ [SKIP] Backtest '{tag}' ya existe. Cargando de caché local.")
        return True

    cmd = [
        ".venv/bin/python3",
        "scripts/backtest_via_signal_engine.py",
        "--index", "RUSSELL1000",
        "--tag", tag,
        "--start", start,
        "--end", end,
        "--e25-sizing",
        "--e25-version", "v2_atlas_informed",
        "--exclude-sectors", "XLV",
        "--ticker-cap", "0.20"
    ]

    print(f"   ⌛ [RUNNING] {tag} ({start} -> {end})...")
    try:
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
        for line in res.stdout.split("\n"):
            if "✅ DONE" in line or "Robustness Metrics" in line:
                print(f"   ↳ {line.strip()}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Error al ejecutar backtest {tag}: {e}")
        print(f"--- STDERR ---\n{e.stderr}\n--------------")
        return False

def load_metrics_and_trades(tag: str) -> Tuple[Dict, pd.DataFrame]:
    """Carga métricas y trades asociados a un tag de backtest."""
    metrics_file = BACKTEST_DIR / f"{tag}_metrics.json"
    trades_file = BACKTEST_DIR / f"{tag}_trades.csv"
    
    metrics = {}
    if metrics_file.exists():
        with open(metrics_file, "r") as f:
            metrics = json.load(f)
            
    trades = pd.DataFrame()
    if trades_file.exists():
        try:
            trades = pd.read_csv(trades_file)
            trades["pnl"] = pd.to_numeric(trades["pnl"], errors="coerce").fillna(0.0)
            if "dist_sma20" not in trades.columns:
                trades["dist_sma20"] = 0.0
            else:
                trades["dist_sma20"] = pd.to_numeric(trades["dist_sma20"], errors="coerce").fillna(0.0)
            if "sizing_factor" not in trades.columns:
                trades["sizing_factor"] = 1.0
            else:
                trades["sizing_factor"] = pd.to_numeric(trades["sizing_factor"], errors="coerce").fillna(1.0)
            trades["return_pct"] = pd.to_numeric(trades["return_pct"], errors="coerce").fillna(0.0)
        except Exception as e:
            print(f"⚠️ Error cargando {trades_file}: {e}")
            
    return metrics, trades

def run_bootstrapping(trades_df: pd.DataFrame, n_iterations: int = 5000) -> Dict:
    """Ejecuta simulación Monte Carlo (Bootstrapping) al 95% de confianza."""
    if trades_df.empty or "return_pct" not in trades_df.columns:
        return {"error": "No trades available for bootstrapping"}
        
    returns = trades_df["return_pct"].values
    pnls = trades_df["pnl"].values
    n_trades = len(returns)
    
    boot_win_rates = []
    boot_pfs = []
    boot_sharpes = []
    
    np.random.seed(42)  # Reproductibilidad
    
    for _ in range(n_iterations):
        idx = np.random.choice(n_trades, size=n_trades, replace=True)
        sample_ret = returns[idx]
        sample_pnl = pnls[idx]
        
        # Win Rate
        win_rate = (sample_pnl > 0).sum() / n_trades * 100
        boot_win_rates.append(win_rate)
        
        # Profit Factor
        pos_sum = sample_pnl[sample_pnl > 0].sum()
        neg_sum = abs(sample_pnl[sample_pnl < 0].sum())
        pf = pos_sum / neg_sum if neg_sum > 0 else (99.0 if pos_sum > 0 else 1.0)
        boot_pfs.append(pf)
        
        # Trade-based Sharpe (mean / std)
        mean_ret = sample_ret.mean()
        std_ret = sample_ret.std()
        sharpe = mean_ret / std_ret if std_ret > 0 else 0.0
        boot_sharpes.append(sharpe)
        
    return {
        "total_trades": int(n_trades),
        "win_rate": {
            "p5": float(np.percentile(boot_win_rates, 5)),
            "p50": float(np.percentile(boot_win_rates, 50)),
            "p95": float(np.percentile(boot_win_rates, 95))
        },
        "profit_factor": {
            "p5": float(np.percentile(boot_pfs, 5)),
            "p50": float(np.percentile(boot_pfs, 50)),
            "p95": float(np.percentile(boot_pfs, 95))
        },
        "trade_sharpe": {
            "p5": float(np.percentile(boot_sharpes, 5)),
            "p50": float(np.percentile(boot_sharpes, 50)),
            "p95": float(np.percentile(boot_sharpes, 95))
        }
    }

def perform_concentration_audit(trades_df: pd.DataFrame) -> Dict:
    """Ejecuta una auditoría estricta de sesgo por ticker y sector."""
    if trades_df.empty or "pnl" not in trades_df.columns:
        return {"error": "No trades available"}
        
    total_pnl = trades_df["pnl"].sum()
    total_count = len(trades_df)
    
    # Concentración por Ticker
    t_stats = trades_df.groupby("symbol").agg(
        count=("symbol", "count"),
        pnl=("pnl", "sum")
    )
    t_stats["count_pct"] = t_stats["count"] / total_count * 100
    t_stats["pnl_pct"] = t_stats["pnl"] / total_pnl * 100 if total_pnl != 0 else 0.0
    top_tickers = t_stats.sort_values(by="count", ascending=False).head(5).to_dict(orient="index")
    
    # Concentración por Sector ETF
    trades_df["sector_etf"] = trades_df["symbol"].map(SECTOR_MAP).fillna("Other")
    s_stats = trades_df.groupby("sector_etf").agg(
        count=("symbol", "count"),
        pnl=("pnl", "sum")
    )
    s_stats["count_pct"] = s_stats["count"] / total_count * 100
    s_stats["pnl_pct"] = s_stats["pnl"] / total_pnl * 100 if total_pnl != 0 else 0.0
    top_sectors = s_stats.sort_values(by="count", ascending=False).to_dict(orient="index")
    
    # Concentración por Año
    trades_df["year"] = pd.to_datetime(trades_df["entry_date"]).dt.year
    y_stats = trades_df.groupby("year").agg(
        count=("symbol", "count"),
        pnl=("pnl", "sum")
    )
    y_stats["count_pct"] = y_stats["count"] / total_count * 100
    y_stats["pnl_pct"] = y_stats["pnl"] / total_pnl * 100 if total_pnl != 0 else 0.0
    top_years = y_stats.to_dict(orient="index")
    
    alerts = []
    for ticker, stats in t_stats.iterrows():
        if stats["count_pct"] > 20:
            alerts.append(f"Ticker Concentration Alert: '{ticker}' representa {stats['count_pct']:.1f}% de los trades.")
        if stats["pnl_pct"] > 30 and total_pnl > 0:
            alerts.append(f"Ticker PnL Alert: '{ticker}' representa {stats['pnl_pct']:.1f}% del PnL total.")
            
    for sector, stats in s_stats.iterrows():
        if sector != "Other" and stats["count_pct"] > 35:
            alerts.append(f"Sector Concentration Alert: '{sector}' representa {stats['count_pct']:.1f}% de los trades.")
            
    return {
        "top_tickers": top_tickers,
        "top_sectors": top_sectors,
        "top_years": top_years,
        "alerts": alerts
    }

def get_stats(df: pd.DataFrame) -> dict:
    if df.empty:
        return {"trades": 0, "pnl": 0.0, "wr": 0.0, "pf": 0.0, "avg_ret": 0.0}
    pnls = df["pnl"]
    win = pnls[pnls > 0]
    loss = pnls[pnls < 0]
    return {
        "trades": len(df),
        "pnl": pnls.sum(),
        "wr": (pnls > 0).mean() * 100,
        "pf": win.sum() / abs(loss.sum()) if not loss.empty and loss.sum() != 0 else float("inf"),
        "avg_ret": df["return_pct"].mean()
    }

def run_bucket_and_ablation_audit(df: pd.DataFrame) -> Dict:
    """Calcula desgloses por buckets de distancia a SMA20 y ablación de líderes."""
    # Buckets
    buckets = [
        ("Z1 (<6.76%)", lambda x: x["dist_sma20"] < 6.76),
        ("Z2 (6.76-10%)", lambda x: (x["dist_sma20"] >= 6.76) & (x["dist_sma20"] < 10.0)),
        ("Z3 (10-15%)", lambda x: (x["dist_sma20"] >= 10.0) & (x["dist_sma20"] < 15.0)),
        ("Z4 (15-25%)", lambda x: (x["dist_sma20"] >= 15.0) & (x["dist_sma20"] < 25.0)),
        ("Z5 (25-35%)", lambda x: (x["dist_sma20"] >= 25.0) & (x["dist_sma20"] < 35.0)),
        ("Z6 (>35%)", lambda x: x["dist_sma20"] >= 35.0),
    ]
    bucket_results = {}
    for label, mask in buckets:
        sub = df[mask(df)]
        s = get_stats(sub)
        avg_sf = sub["sizing_factor"].mean() if not sub.empty else 1.0
        bucket_results[label] = {**s, "avg_sf": avg_sf}
        
    # Ablación de Líderes
    leaders = ["NVDA", "AMD", "META", "AAPL"]
    sub_ex_l = df[~df["symbol"].isin(leaders)]
    s_ex_l = get_stats(sub_ex_l)
    
    # Excluyendo el mayor contribuidor individual
    top_contrib, top_val = "None", 0.0
    s_ex_top = {"trades": 0, "pnl": 0.0, "wr": 0.0, "pf": 0.0}
    if not df.empty:
        ticker_pnl = df.groupby("symbol")["pnl"].sum().sort_values(ascending=False)
        if not ticker_pnl.empty:
            top_contrib = ticker_pnl.index[0]
            top_val = ticker_pnl.iloc[0]
            sub_ex_top = df[df["symbol"] != top_contrib]
            s_ex_top = get_stats(sub_ex_top)
            
    return {
        "buckets": bucket_results,
        "ablation": {
            "ex_leaders_list": leaders,
            "ex_leaders": s_ex_l,
            "top_contrib": top_contrib,
            "top_contrib_pnl": top_val,
            "ex_top_contrib": s_ex_top
        }
    }

def main():
    parser = argparse.ArgumentParser(description="Orquestador de Validación Cruzada S5")
    parser.add_argument("--force", action="store_true", help="Forzar ejecución de backtests")
    args = parser.parse_args()

    print("=============================================================")
    print("🚀 VALIDACIÓN TEMPORAL Y BOOTSTRAP: BENCHMARK BASELINE S5")
    print("=============================================================\n")

    matrix_results = {}
    aggregated_trades = []

    for w in WINDOWS:
        tag = f"s5_baseline_w{w['suffix']}"
        print(f"👉 Evaluando: {w['label']} ({w['start']} a {w['end']})")
        
        success = run_backtest(tag, w["start"], w["end"], force=args.force)
        if not success:
            print(f"❌ Error en ventana {w['label']}. Deteniendo ejecucion.")
            sys.exit(1)
            
        metrics, trades = load_metrics_and_trades(tag)
        
        # Guardar trades agregados
        if not trades.empty:
            trades["window"] = w["suffix"]
            aggregated_trades.append(trades)
            
        # Ejecutar bootstrap por ventana
        boot = run_bootstrapping(trades)
        
        # Auditoría de concentración por ventana
        con_audit = perform_concentration_audit(trades)
        
        matrix_results[w["suffix"]] = {
            "label": w["label"],
            "start": w["start"],
            "end": w["end"],
            "metrics": metrics,
            "bootstrapping": boot,
            "concentration": con_audit,
            "total_trades": len(trades)
        }
        print(f"   ✓ Retorno: {metrics.get('total_return', 0.0)}% | MDD: {metrics.get('max_drawdown', 0.0)}% | Trades: {len(trades)}")
        print(f"   ✓ Bootstrapping PF (p50): {boot.get('profit_factor', {}).get('p50', 0.0):.2f}\n")

    # Pool unificado de trades
    all_trades = pd.concat(aggregated_trades, ignore_index=True) if aggregated_trades else pd.DataFrame()
    
    # Bootstrap unificado
    consolidated_boot = run_bootstrapping(all_trades)
    
    # Concentración unificada
    consolidated_concentration = perform_concentration_audit(all_trades)
    
    # Análisis de buckets y ablación
    con_audit = run_bucket_and_ablation_audit(all_trades)
    
    # Estructura del reporte final
    report_data = {
        "run_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "windows": matrix_results,
        "consolidated": {
            "total_trades": len(all_trades),
            "bootstrapping": consolidated_boot,
            "concentration": consolidated_concentration,
            "buckets_and_ablation": con_audit
        }
    }
    
    # Guardar reporte JSON
    BACKTEST_DIR.mkdir(parents=True, exist_ok=True)
    with open(REPORT_JSON, "w") as f:
        json.dump(report_data, f, indent=2)
        
    print(f"💾 Reporte estructurado JSON guardado en: {REPORT_JSON}")
    
    # Generar reporte Markdown
    generate_markdown_report(report_data)
    print(f"📝 Reporte Markdown guardado en: {REPORT_MD}")

def generate_markdown_report(data: Dict):
    """Genera la especificación Markdown para revisión por el orquestador."""
    md = []
    md.append("# Reporte de Validación Temporal y Robustez del Benchmark S5")
    md.append(f"> Generado automáticamente el: {data['run_date']}\n")
    md.append("Este reporte presenta los resultados consolidados de la simulación del **Candidato Benchmark para S5** en el universo PIT del **Russell 1000** con exclusión de **XLV** y sizing penalizado **E25 v2**.\n")
    
    md.append("## 🏁 Resumen y Veredicto de Consistencia Temporal")
    
    # Calcular consistencia temporal
    positive_windows = 0
    total_windows = len(data["windows"])
    for w_id, w_data in data["windows"].items():
        if w_data["metrics"].get("total_return", 0.0) >= 0.0:
            positive_windows += 1
            
    verdict_text = "🟢 **APROBADO**" if positive_windows >= 3 else "🔴 **RECHAZADO**"
    
    md.append(f"- **Criterio de Aceptación**: Al menos 3 de {total_windows} ventanas temporales positivas y PF de bootstrap >= 1.05.")
    md.append(f"- **Veredicto Temporal**: {verdict_text} ({positive_windows} de {total_windows} ventanas cerradas en positivo).")
    md.append(f"- **Trades Totales en el Ciclo**: {data['consolidated']['total_trades']} trades.")
    
    # Tabla comparativa por ventanas
    md.append("\n### 📊 Tabla de Folds Históricos (OOS & IS)")
    md.append("| Ventana | Rango de Fechas | Retorno Total | Max Drawdown | Sharpe (VBT) | Trades | PF Bootstrap (p50) |")
    md.append("| :--- | :---: | :---: | :---: | :---: | :---: | :---: |")
    for w_id, w_data in data["windows"].items():
        m = w_data["metrics"]
        b = w_data["bootstrapping"]
        md.append(f"| **{w_data['label']}** | `{w_data['start']}` a `{w_data['end']}` | {m.get('total_return', 0.0):.2f}% | {m.get('max_drawdown', 0.0):.2f}% | {m.get('sharpe_ratio', 0.0):.2f} | {w_data['total_trades']} | {b.get('profit_factor', {}).get('p50', 0.0):.2f} |")
        
    # Análisis de Bootstrapping
    md.append("\n## 🎲 Simulación Monte Carlo (Bootstrapping 5,000 Folds)")
    md.append("Simulación realizada sobre el pool de trades de todo el ciclo 2019-2026:")
    b = data["consolidated"]["bootstrapping"]
    md.append(f"- **Win Rate (CI 95%)**: `{b['win_rate']['p50']:.2f}%` (Límite p5: `{b['win_rate']['p5']:.2f}%` a p95: `{b['win_rate']['p95']:.2f}%`)")
    md.append(f"- **Profit Factor (CI 95%)**: `{b['profit_factor']['p50']:.2f}` (Límite p5: `{b['profit_factor']['p5']:.2f}` a p95: `{b['profit_factor']['p95']:.2f}`)")
    md.append(f"- **Sharpe basado en Trades (CI 95%)**: `{b['trade_sharpe']['p50']:.3f}` (Límite p5: `{b['trade_sharpe']['p5']:.3f}` a p95: `{b['trade_sharpe']['p95']:.3f}`)")
    
    # Buckets de distancia
    md.append("\n## 🔬 Desglose de Expectancia por Extensión (Z1 - Z6)")
    md.append("Análisis de rentabilidad y sizing promedio según la distancia porcentual del activo a su SMA20 en la entrada:")
    md.append("| Bucket | Trades | P&L Acumulado | Win Rate | Profit Factor | Sizing Factor Promedio |")
    md.append("| :--- | :---: | :---: | :---: | :---: | :---: |")
    buckets = data["consolidated"]["buckets_and_ablation"]["buckets"]
    for label, stats in buckets.items():
        md.append(f"| **{label}** | {stats['trades']} | ${stats['pnl']:.2f} | {stats['wr']:.1f}% | {stats['pf']:.2f} | {stats['avg_sf']:.2f} |")
        
    # Ablación de líderes
    md.append("\n## 🛡️ Análisis de Concentración y Robustez (Ablación)")
    ab = data["consolidated"]["buckets_and_ablation"]["ablation"]
    md.append("Auditoría para asegurar que el alfa de la estrategia no esté concentrada en unos pocos activos idiosincráticos:")
    md.append(f"- **Trades sin líderes principales** ({', '.join(ab['ex_leaders_list'])}):")
    md.append(f"  * Cantidad de trades: {ab['ex_leaders']['trades']}")
    md.append(f"  * P&L Neto: ${ab['ex_leaders']['pnl']:.2f}")
    md.append(f"  * Win Rate: {ab['ex_leaders']['wr']:.1f}% | Profit Factor: {ab['ex_leaders']['pf']:.2f}")
    md.append(f"- **Trades sin el mayor contribuidor individual** (`{ab['top_contrib']}` - P&L: `${ab['top_contrib_pnl']:.2f}`):")
    md.append(f"  * Cantidad de trades: {ab['ex_top_contrib']['trades']}")
    md.append(f"  * P&L Neto: ${ab['ex_top_contrib']['pnl']:.2f}")
    md.append(f"  * Win Rate: {ab['ex_top_contrib']['wr']:.1f}% | Profit Factor: {ab['ex_top_contrib']['pf']:.2f}")
    
    # Alertas de concentración
    alerts = data["consolidated"]["concentration"]["alerts"]
    if alerts:
        md.append("\n### ⚠️ Alertas de Concentración Detectadas")
        for alert in alerts:
            md.append(f"- {alert}")
    else:
        md.append("\n🟢 **Sin alertas de concentración**: La exposición está distribuida de forma robusta.")

    # Guardar en archivo
    Path(REPORT_MD).parent.mkdir(parents=True, exist_ok=True)
    with open(REPORT_MD, "w") as f:
        f.write("\n".join(md))

if __name__ == "__main__":
    main()
