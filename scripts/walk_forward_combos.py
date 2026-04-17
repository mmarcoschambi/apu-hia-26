#!/usr/bin/env python3
"""
Walk-Forward externo para combos optimizados.
Replica exactamente como optimize_combo.py construye el engine:
  - Universe desde DB (top N por disponibilidad de datos, igual que optimizacion)
  - Params planos: **tier2_filters + **tier3_fixed + **tier1_strategy
  - risk_dollars derivado de risk_fraction * capital

Uso:
    python3 scripts/walk_forward_combos.py --combo combo_pure_momentum
    python3 scripts/walk_forward_combos.py --all
    python3 scripts/walk_forward_combos.py --all --save-baseline
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

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)

# Expanding window: train siempre desde 2019, OOS avanza 1 anio
WF_FOLDS = [
    {"fold": 1, "oos_start": "2022-01-01", "oos_end": "2022-12-31"},
    {"fold": 2, "oos_start": "2023-01-01", "oos_end": "2023-12-31"},
    {"fold": 3, "oos_start": "2024-01-01", "oos_end": "2024-12-31"},
    {"fold": 4, "oos_start": "2025-01-01", "oos_end": "2025-12-31"},
]

# Gate mas estricto para evitar falsos GO por 1 anio excepcional.
GATE_RULES = {
    "min_valid_folds": 2,
    "min_positive_folds": 2,
    "min_sharpe_mean": 0.75,
    "min_sharpe_min": 0.25,
    "min_pf_mean": 1.20,
    "min_pf_min": 1.00,
    "min_trades_per_fold": 50,
}

COMBOS_DIR = ROOT / "config" / "combos"
RESULTS_DIR = ROOT / "outputs" / "best_combos_run"
WF_OUT_DIR = ROOT / "outputs" / "walk_forward"
WF_OUT_DIR.mkdir(parents=True, exist_ok=True)

UNIVERSE_SIZE = 200  # igual que optimizacion


def get_universe_from_db(start_date: str, end_date: str, limit: int = UNIVERSE_SIZE):
    """Replica get_universe_from_db() de optimize_combo.py."""
    db_path = ROOT / "data" / "ticker_cache.db"
    try:
        conn = sqlite3.connect(str(db_path))
        df = pd.read_sql_query(
            """
            SELECT ticker, COUNT(*) as cnt
            FROM ohlcv_cache
            WHERE date >= ? AND date <= ?
            GROUP BY ticker
            ORDER BY cnt DESC
            LIMIT ?
        """,
            conn,
            params=(start_date, end_date, limit),
        )
        conn.close()
        if not df.empty:
            return df["ticker"].tolist()
    except Exception as e:
        logger.error(f"Error DB: {e}")
    # fallback minimo
    return ["AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA", "JPM", "V", "UNH"]


def load_combo_params(combo_name: str) -> dict:
    f = RESULTS_DIR / f"{combo_name}_config.json"
    if not f.exists():
        raise FileNotFoundError(f"No hay config optimizada para {combo_name}: {f}")
    return json.load(open(f))


def build_engine_kwargs(combo_name: str, params: dict) -> dict:
    """
    Traduce la config guardada en best_combos_run/*_config.json
    a los kwargs planos que acepta AdvancedVectorBTEngine.
    Replica la logica del objective() de optimize_combo.py.
    """
    combo_cfg = json.load(open(COMBOS_DIR / f"{combo_name}.json"))

    tier2 = params.get("tier2_filters", {})
    tier1 = params.get("tier1_strategy", {})
    tier3 = params.get("tier3_risk", {})

    signal_type = combo_cfg.get("pattern", {}).get("signal_type", "any")
    screener_name = combo_cfg.get("screener", {}).get("name", "minervini_trend")

    # risk_dollars: replica la derivacion del optimizer
    risk_fraction = tier3.get("risk_fraction", 0.005)
    risk_dollars = int(100_000 * risk_fraction)

    # tier3_fixed tiene algunos nombres distintos al engine — normalizar
    tier3_engine = {}
    TIER3_RENAMES = {
        "max_stop_pct_hard": "max_stop_pct",
        # rvol_danger_size / rvol_warning_size en config son 0-1 (fraccion),
        # en el engine son int (porcentaje). Detectar y convertir.
    }
    for k, v in tier3.items():
        k_engine = TIER3_RENAMES.get(k, k)
        # rvol_*_size: si viene como decimal (<= 1.0) convertir a int pct
        if (
            k_engine in ("rvol_danger_size", "rvol_warning_size")
            and isinstance(v, float)
            and v <= 1.0
        ):
            v = int(v * 100)
        # max_stop_pct_hard: config tiene 0.08 (8%), engine espera 8.0 (divide por 100 internamente)
        if k_engine == "max_stop_pct" and isinstance(v, float) and v <= 1.0:
            v = round(v * 100, 1)  # 0.08 -> 8.0
        tier3_engine[k_engine] = v

    # tier2 keys que el engine no conoce -> descartar silenciosamente
    ENGINE_TIER2_KEYS = {
        "min_rvol",
        "min_adr",
        "max_dist_sma20",
        "min_dollar_volume",
        "min_volume",
        "min_consolidation_days",
        "use_rs_percentile",
        "min_rs_percentile",
        "rs_lookback_days",
        "require_positive_rs",
        "use_pattern_filter",
        "min_pattern_confidence",
        "pattern_cache_path",
    }
    tier2_clean = {k: v for k, v in tier2.items() if k in ENGINE_TIER2_KEYS}

    kwargs = {
        **tier2_clean,
        **tier3_engine,
        **tier1,
        "signal_type": signal_type,
        "screener_name": screener_name,
        "screener_cache_path": str(ROOT / "data" / "screener_cache"),
        "mode": "production",
        "risk_dollars": risk_dollars,
        "fees": 0.001,  # mismo que optimizer: 10bps
        "slippage": 0.001,  # mismo que optimizer: 10bps
    }
    return kwargs


def run_oos_fold(combo_name: str, params: dict, fold: dict) -> dict:
    universe = get_universe_from_db(fold["oos_start"], fold["oos_end"])
    logger.info(f"    universe: {len(universe)} tickers")

    kwargs = build_engine_kwargs(combo_name, params)

    engine = AdvancedVectorBTEngine(
        universe=universe,
        start_date=fold["oos_start"],
        end_date=fold["oos_end"],
        initial_capital=100_000,
        **kwargs,
    )
    try:
        result = engine.run_backtest()
        trades_df = result.get("trades_df", pd.DataFrame())
        return {
            "fold": fold["fold"],
            "oos_start": fold["oos_start"],
            "oos_end": fold["oos_end"],
            "trades": result.get("total_trades", 0),
            "sharpe": round(float(result.get("sharpe_ratio", 0)), 3),
            "pf": round(float(result.get("profit_factor", 0)), 3),
            "win_rate": round(float(result.get("win_rate", 0)) * 100, 1),
            "max_dd": round(
                float(result.get("max_drawdown_pct", 0))
                if result.get("max_drawdown_pct") is not None
                else abs(float(result.get("max_drawdown", 0))) * 100,
                2,
            ),
            "total_return": round(
                float(result.get("total_return_pct", result.get("total_return", 0)))
                * (
                    100
                    if abs(
                        result.get("total_return_pct", result.get("total_return", 1))
                    )
                    < 2
                    else 1
                ),
                2,
            ),
            "status": "ok",
        }
    except Exception as e:
        logger.error(f"    Fold {fold['fold']} ERROR: {e}")
        return {
            "fold": fold["fold"],
            "oos_start": fold["oos_start"],
            "oos_end": fold["oos_end"],
            "trades": 0,
            "sharpe": 0,
            "pf": 0,
            "win_rate": 0,
            "max_dd": 0,
            "total_return": 0,
            "status": f"error: {str(e)[:120]}",
        }
    finally:
        engine.cleanup()


def evaluate_combo_wf(combo_name: str) -> dict:
    logger.info(f"\n{'=' * 60}")
    logger.info(f"WALK-FORWARD: {combo_name}")
    logger.info(f"{'=' * 60}")

    params = load_combo_params(combo_name)
    fold_results = []

    for fold in WF_FOLDS:
        logger.info(
            f"  Fold {fold['fold']}: OOS {fold['oos_start']} -> {fold['oos_end']}"
        )
        r = run_oos_fold(combo_name, params, fold)
        fold_results.append(r)
        logger.info(
            f"    trades={r['trades']}  sharpe={r['sharpe']}  pf={r['pf']}  wr={r['win_rate']}%  dd={r['max_dd']}%  [{r['status']}]"
        )

    # Folds con <30 trades: estadisticamente invalidos
    # (bear market + SPY<SMA50 filter -> pocos trades por diseno, no falla del sistema)
    MIN_FOLD_TRADES = GATE_RULES["min_trades_per_fold"]
    valid = [
        f
        for f in fold_results
        if f["status"] == "ok" and f["trades"] >= MIN_FOLD_TRADES
    ]
    low_sample = [
        f for f in fold_results if f["status"] == "ok" and f["trades"] < MIN_FOLD_TRADES
    ]
    if not valid:
        agg = {
            "sharpe_mean": 0,
            "sharpe_min": 0,
            "pf_mean": 0,
            "pf_consistent": False,
            "trades_total": 0,
            "trades_per_fold": 0,
            "verdict": "INSUFFICIENT_DATA",
        }
    else:
        sharpes = [f["sharpe"] for f in valid]
        pfs = [f["pf"] for f in valid]
        agg = {
            "sharpe_mean": round(float(np.mean(sharpes)), 3),
            "sharpe_min": round(float(np.min(sharpes)), 3),
            "sharpe_positive_folds": int(sum(s > 0 for s in sharpes)),
            "pf_mean": round(float(np.mean(pfs)), 3),
            "pf_consistent": bool(all(p > 1.0 for p in pfs)),
            "trades_total": int(sum(f["trades"] for f in valid)),
            "trades_per_fold": round(float(np.mean([f["trades"] for f in valid])), 1),
            "folds_valid": len(valid),
            "folds_ignored_low_sample": len(low_sample),
        }
        positive_folds = agg["sharpe_positive_folds"]
        n_valid = len(valid)
        if n_valid >= GATE_RULES["min_valid_folds"]:
            go = (
                positive_folds >= GATE_RULES["min_positive_folds"]
                and agg["sharpe_mean"] >= GATE_RULES["min_sharpe_mean"]
                and agg["sharpe_min"] >= GATE_RULES["min_sharpe_min"]
                and agg["pf_mean"] >= GATE_RULES["min_pf_mean"]
                and min(pfs) >= GATE_RULES["min_pf_min"]
                and agg["trades_per_fold"] >= GATE_RULES["min_trades_per_fold"]
            )
        else:
            go = False
        agg["verdict"] = "GO" if go else "NO-GO"
        agg["gate_rules"] = GATE_RULES

    if low_sample:
        for ls in low_sample:
            logger.info(
                f"    Fold {ls['fold']} IGNORADO: {ls['trades']} trades "
                f"(bear/regime filter activo, muestra insuficiente)"
            )
    logger.info(f"\n  AGREGADO:")
    logger.info(f"    Sharpe medio:    {agg.get('sharpe_mean', 0):.3f}")
    logger.info(f"    Sharpe minimo:   {agg.get('sharpe_min', 0):.3f}")
    logger.info(f"    PF consistente:  {agg.get('pf_consistent', False)}")
    logger.info(f"    Trades por fold: {agg.get('trades_per_fold', 0):.1f}")
    logger.info(
        f"    Folds validos:   {agg.get('folds_valid', 0)}/{len(WF_FOLDS)}  "
        f"(ignorados por muestra baja: {agg.get('folds_ignored_low_sample', 0)})"
    )
    verdict = agg.get("verdict", "?")
    logger.info(f"    {'[GO]' if verdict == 'GO' else '[NO-GO]'} VEREDICTO: {verdict}")

    result = {
        "combo": combo_name,
        "run_at": datetime.now().isoformat(),
        "folds": fold_results,
        "aggregate": agg,
    }
    out_f = WF_OUT_DIR / f"{combo_name}_wf.json"
    json.dump(result, open(out_f, "w"), indent=2)
    logger.info(f"  Guardado: {out_f}")
    return result


def main():
    parser = argparse.ArgumentParser(description="Walk-Forward externo para combos")
    parser.add_argument("--combo", type=str)
    parser.add_argument("--all", action="store_true")
    parser.add_argument(
        "--save-baseline",
        action="store_true",
        help="Agrega resultados WF al baseline_metrics.json canonico",
    )
    args = parser.parse_args()

    if args.all:
        combos = [
            f.stem
            for f in sorted(COMBOS_DIR.glob("combo_*.json"))
            if "triad_rts" not in f.stem and "ideal_setup" not in f.stem
        ]
    elif args.combo:
        combos = [args.combo]
    else:
        parser.print_help()
        return

    all_results = []
    for combo in combos:
        try:
            r = evaluate_combo_wf(combo)
            all_results.append(r)
        except FileNotFoundError as e:
            logger.warning(f"  Saltando {combo}: {e}")

    logger.info(f"\n{'=' * 60}")
    logger.info("RESUMEN WALK-FORWARD")
    logger.info(f"{'=' * 60}")
    for r in all_results:
        agg = r["aggregate"]
        v = agg.get("verdict", "?")
        tag = "[GO ]" if v == "GO" else "[NOG]"
        logger.info(
            f"  {tag} {r['combo']:<35} sharpe={agg.get('sharpe_mean', 0):>5.2f}  pf={agg.get('pf_mean', 0):>4.2f}  trades={agg.get('trades_total', 0):>5}"
        )

    if args.save_baseline:
        bl_f = (
            ROOT
            / "baseline_snapshots"
            / "2026-03-29_week1_real"
            / "baseline_metrics.json"
        )
        if bl_f.exists():
            bl = json.load(open(bl_f))
            for r in all_results:
                for c in bl["combos"]:
                    if c["name"] == r["combo"]:
                        c["wf_sharpe_mean"] = r["aggregate"].get("sharpe_mean")
                        c["wf_pf_mean"] = r["aggregate"].get("pf_mean")
                        c["wf_verdict"] = r["aggregate"].get("verdict")
            json.dump(bl, open(bl_f, "w"), indent=2)
            logger.info(f"\nBaseline actualizado con WF: {bl_f}")


if __name__ == "__main__":
    main()
