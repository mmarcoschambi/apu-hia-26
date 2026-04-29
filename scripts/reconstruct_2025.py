#!/usr/bin/env python3
"""
RECONSTRUCCION 2025 - Fold OOS genuinamente nuevo
Corre combos sobre 2025-01-01/2025-12-31 con params FIJOS (sin re-optimizar).
OOS real: Optuna uso 2019-2024, 2025 nunca fue visto por ningun torneo.
Usage:
    python3 scripts/reconstruct_2025.py
    python3 scripts/reconstruct_2025.py --all
    python3 scripts/reconstruct_2025.py --universe-size 400
Outputs -> outputs/reconstruct_2025/
"""

import argparse, json, sys, logging, warnings, sqlite3
from pathlib import Path
from datetime import datetime
import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))
from src.backtest.vectorbt_engine_advanced import AdvancedVectorBTEngine
from src.integration.combo_loader import load_combo_merged

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)
RESULTS_DIR = ROOT / "outputs" / "best_combos_run"
COMBOS_DIR = ROOT / "config" / "combos"
WF_OUT_DIR = ROOT / "outputs" / "walk_forward"
OUT_DIR = ROOT / "outputs" / "reconstruct_2025"
OUT_DIR.mkdir(parents=True, exist_ok=True)
OOS_START = "2025-01-01"
OOS_END = "2025-12-31"
GATE = {"min_trades": 50, "min_sharpe": 0.75, "min_pf": 1.20, "max_dd_pct": 25.0}
DEFAULT_COMBOS = ["combo_pullback_entry", "combo_pure_momentum"]


def get_universe_from_db(start, end, limit):
    db = ROOT / "data" / "ticker_cache.db"
    try:
        conn = sqlite3.connect(str(db))
        df = pd.read_sql_query(
            "SELECT ticker, COUNT(*) as cnt FROM ohlcv_cache WHERE date >= ? AND date <= ? GROUP BY ticker ORDER BY cnt DESC LIMIT ?",
            conn,
            params=(start, end, limit),
        )
        conn.close()
        if not df.empty:
            logger.info(
                f"    DB universe: {len(df)} tickers ({df['cnt'].min()}-{df['cnt'].max()} dias de datos)"
            )
            return df["ticker"].tolist()
    except Exception as e:
        logger.error(f"    DB error: {e}")
    return ["AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA", "JPM", "V", "UNH"]


def build_engine_kwargs(combo_name):
    """
    Carga config mergeada (base + best_combos_run).
    Misma lógica que run_walkforward_hybrid.py — fuente única.
    """
    cfg, meta = load_combo_merged(combo_name)
    logger.info(
        "reconstruct: '%s' config source=%s, merged=%s",
        combo_name,
        meta.source,
        meta.sections_merged,
    )
    return cfg, meta


def extract_metrics(result):
    trades = result.get("total_trades", 0)
    sharpe = float(result.get("sharpe_ratio", 0))
    pf = float(result.get("profit_factor", 0))
    wr = float(result.get("win_rate", 0)) * 100
    tr_raw = result.get("total_return_pct", result.get("total_return", 0))
    total_return = float(tr_raw) * (100 if abs(float(tr_raw)) < 2 else 1)
    dd_raw = result.get("max_drawdown_pct", result.get("max_drawdown", 0))
    max_dd = abs(float(dd_raw)) * (100 if abs(float(dd_raw)) < 2 else 1)
    return {
        "trades": trades,
        "sharpe": round(sharpe, 3),
        "profit_factor": round(pf, 3),
        "win_rate": round(wr, 1),
        "total_return_pct": round(total_return, 2),
        "max_drawdown_pct": round(max_dd, 2),
    }


def run_reconstruction(combo_name, universe_size):
    logger.info(f"\n{'=' * 60}")
    logger.info(f"RECONSTRUCCION 2025 OOS: {combo_name}")
    logger.info(
        f"  Periodo: {OOS_START} -> {OOS_END}  |  Params: FIJOS (sin re-optimizar)"
    )
    logger.info(f"{'=' * 60}")
cfg, meta = build_engine_kwargs(combo_name)
    universe = get_universe_from_db(OOS_START, OOS_END, universe_size)
    kwargs   = cfg  # ahora cfg ya es la config mergeada completa
    logger.info(f"  Universe: {len(universe)} tickers")
    logger.info(f"  Corriendo backtest 2025... (puede tardar unos minutos)")
    engine = AdvancedVectorBTEngine(
        universe=universe,
        start_date=OOS_START,
        end_date=OOS_END,
        initial_capital=100_000,
        **kwargs,
    )
    try:
        result = engine.run_backtest()
        m = extract_metrics(result)
        gate_ok = (
            m["trades"] >= GATE["min_trades"]
            and m["sharpe"] >= GATE["min_sharpe"]
            and m["profit_factor"] >= GATE["min_pf"]
            and m["max_drawdown_pct"] <= GATE["max_dd_pct"]
        )
        verdict = "GO" if gate_ok else "NO-GO"
        logger.info(f"\n  RESULTADOS 2025 OOS:")
        logger.info(f"    Trades:        {m['trades']}  (gate >= {GATE['min_trades']})")
        logger.info(
            f"    Sharpe:        {m['sharpe']:.3f}  (gate >= {GATE['min_sharpe']})"
        )
        logger.info(
            f"    Profit Factor: {m['profit_factor']:.3f}  (gate >= {GATE['min_pf']})"
        )
        logger.info(f"    Win Rate:      {m['win_rate']:.1f}%")
        logger.info(f"    Total Return:  {m['total_return_pct']:.2f}%")
        logger.info(
            f"    Max Drawdown:  {m['max_drawdown_pct']:.2f}%  (gate <= {GATE['max_dd_pct']})"
        )
        logger.info(f"\n    VEREDICTO: [{verdict}]")
        out = {
            "combo": combo_name,
            "oos_start": OOS_START,
            "oos_end": OOS_END,
            "universe_size": len(universe),
            "params_source": "best_combos_run (fixed, no re-opt)",
            "run_at": datetime.now().isoformat(),
            "metrics": m,
            "gate": {"rules": GATE, "passed": gate_ok, "verdict": verdict},
            "status": "ok",
        }
        trades_df = result.get("trades_df", pd.DataFrame())
        if not trades_df.empty:
            tp = OUT_DIR / f"{combo_name}_trades_2025.csv"
            trades_df.to_csv(tp)
            out["trades_csv"] = str(tp)
            logger.info(f"    Trades CSV: {tp}")
        rp = OUT_DIR / f"{combo_name}_result_2025.json"
        with open(rp, "w") as f:
            json.dump(out, f, indent=2)
        logger.info(f"    Resultado JSON: {rp}")
        return out
    except Exception as e:
        logger.error(f"  ERROR: {e}")
        import traceback

        traceback.print_exc()
        err = {
            "combo": combo_name,
            "status": f"error: {e}",
            "metrics": {},
            "gate": {"verdict": "ERROR"},
        }
        with open(OUT_DIR / f"{combo_name}_result_2025.json", "w") as f:
            json.dump(err, f, indent=2)
        return err
    finally:
        engine.cleanup()


def print_comparison_vs_wf(results):
    logger.info(f"\n{'=' * 60}")
    logger.info("COMPARACION: 2025 OOS vs Walk-Forward historico")
    logger.info(f"{'=' * 60}")
    for r in results:
        combo = r["combo"]
        logger.info(f"\n  {combo}")
        logger.info(
            f"  {'Fold':<10} {'Anio':<6} {'Trades':>7} {'Sharpe':>7} {'PF':>6} {'WR%':>6} {'Ret%':>7} Verdict"
        )
        logger.info(f"  {'-' * 60}")
        wf_file = WF_OUT_DIR / f"{combo}_wf_results.json"
        if wf_file.exists():
            wf = json.load(open(wf_file))
            for fold in wf.get("folds", []):
                if fold.get("status") != "ok":
                    continue
                tag = "(low sample)" if fold["trades"] < 50 else ""
                logger.info(
                    f"  {'Fold ' + str(fold['fold']):<10} {fold['oos_start'][:4]:<6} "
                    f"{fold['trades']:>7} {fold['sharpe']:>7.3f} {fold['pf']:>6.3f} "
                    f"{fold['win_rate']:>6.1f} {fold['total_return']:>7.1f}  {tag}"
                )
        else:
            logger.info(f"  (sin WF historico en {wf_file})")
        m = r.get("metrics", {})
        v = r.get("gate", {}).get("verdict", "?")
        logger.info(
            f"  {'2025 OOS':<10} {'2025':<6} "
            f"{m.get('trades', 0):>7} {m.get('sharpe', 0):>7.3f} "
            f"{m.get('profit_factor', 0):>6.3f} {m.get('win_rate', 0):>6.1f} "
            f"{m.get('total_return_pct', 0):>7.1f}  [{v}] <- NUEVO OOS"
        )


def main():
    parser = argparse.ArgumentParser(description="Reconstruccion 2025 OOS")
    parser.add_argument("--combo", default="combo_pullback_entry")
    parser.add_argument("--all", action="store_true")
    parser.add_argument(
        "--universe-size",
        type=int,
        default=200,
        help="Tickers desde DB (default 200 = igual que WF/Optuna)",
    )
    args = parser.parse_args()
    combos = DEFAULT_COMBOS if args.all else [args.combo]
    results = []
    for c in combos:
        try:
            results.append(run_reconstruction(c, args.universe_size))
        except Exception as e:
            logger.error(f"  SKIP {c}: {e}")
    if results:
        print_comparison_vs_wf(results)
    logger.info(f"\n{'=' * 60}")
    logger.info("RESUMEN FINAL")
    logger.info(f"{'=' * 60}")
    for r in results:
        m = r.get("metrics", {})
        v = r.get("gate", {}).get("verdict", r.get("status", "?"))
        logger.info(
            f"  {r['combo']:40s} [{v}]  "
            f"Sharpe={m.get('sharpe', 0):.3f}  "
            f"PF={m.get('profit_factor', 0):.3f}  "
            f"Trades={m.get('trades', 0)}"
        )
    logger.info(f"\nOutputs: {OUT_DIR}")


if __name__ == "__main__":
    main()
