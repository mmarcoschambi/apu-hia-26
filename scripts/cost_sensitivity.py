#!/usr/bin/env python3
"""
Analisis de sensibilidad a costos de transaccion.
Reutiliza build_engine_kwargs() de walk_forward_combos.py para garantizar
que los params son identicos a la optimizacion — solo varia fees+slippage.

Los campos fees y slippage si son soportados por el engine
(visibles en optimize_combo.py:objective() linea ~540).

Uso:
    python3 scripts/cost_sensitivity.py --combo combo_pure_momentum
    python3 scripts/cost_sensitivity.py --all
"""

import argparse, json, sys, logging, warnings, sqlite3
from pathlib import Path
from datetime import datetime

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

# Importar la funcion compartida de walk_forward_combos
sys.path.insert(0, str(ROOT / "scripts"))
from walk_forward_combos import (
    get_universe_from_db,
    load_combo_params,
    build_engine_kwargs,
)

from src.backtest.vectorbt_engine_advanced import AdvancedVectorBTEngine

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)

COMBOS_DIR = ROOT / "config" / "combos"
COST_OUT = ROOT / "outputs" / "cost_sensitivity"
COST_OUT.mkdir(parents=True, exist_ok=True)

# Periodo completo IS (mismo que optimizacion)
PERIOD_START = "2019-01-01"
PERIOD_END = "2024-12-31"

# Grilla de costos: fees + slippage en pct (0.001 = 10bps)
# El optimizer usa fees=0.001 slippage=0.001 como baseline (20bps round-trip)
COST_GRID = [
    {"label": "zero_cost", "fees": 0.0000, "slippage": 0.0000},  # 0 bps
    {
        "label": "optimizer_base",
        "fees": 0.0010,
        "slippage": 0.0010,
    },  # 20bps RT (baseline del optimizer)
    {"label": "light", "fees": 0.0005, "slippage": 0.0005},  # 10bps RT (IBKR pro)
    {"label": "realistic_ibkr", "fees": 0.0010, "slippage": 0.0015},  # 25bps RT
    {"label": "realistic_retail", "fees": 0.0020, "slippage": 0.0020},  # 40bps RT
    {"label": "conservative", "fees": 0.0030, "slippage": 0.0030},  # 60bps RT
    {"label": "stress", "fees": 0.0050, "slippage": 0.0050},  # 100bps RT
]


def run_with_costs(combo_name: str, params: dict, cost: dict) -> dict:
    universe = get_universe_from_db(PERIOD_START, PERIOD_END)
    kwargs = build_engine_kwargs(combo_name, params)

    # Sobreescribir fees y slippage con los del escenario
    kwargs["fees"] = cost["fees"]
    kwargs["slippage"] = cost["slippage"]

    engine = AdvancedVectorBTEngine(
        universe=universe,
        start_date=PERIOD_START,
        end_date=PERIOD_END,
        initial_capital=100_000,
        **kwargs,
    )
    try:
        result = engine.run_backtest()
        trades_df = result.get("trades_df", pd.DataFrame())
        rt_bps = int((cost["fees"] + cost["slippage"]) * 2 * 10_000)
        return {
            "label": cost["label"],
            "fees_bps": int(cost["fees"] * 10_000),
            "slippage_bps": int(cost["slippage"] * 10_000),
            "roundtrip_bps": rt_bps,
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
            "total_return": round(float(result.get("total_return_pct", 0)), 2),
            "viable": result.get("sharpe_ratio", 0) > 0
            and result.get("profit_factor", 0) > 1.0,
            "status": "ok",
        }
    except Exception as e:
        logger.error(f"    ERROR en {cost['label']}: {e}")
        return {
            "label": cost["label"],
            "fees_bps": 0,
            "slippage_bps": 0,
            "roundtrip_bps": 0,
            "trades": 0,
            "sharpe": 0,
            "pf": 0,
            "win_rate": 0,
            "max_dd": 0,
            "total_return": 0,
            "viable": False,
            "status": f"error: {str(e)[:120]}",
        }
    finally:
        engine.cleanup()


def analyze_combo_costs(combo_name: str) -> dict:
    logger.info(f"\n{'=' * 60}")
    logger.info(f"COST SENSITIVITY: {combo_name}")
    logger.info(f"{'=' * 60}")

    params = load_combo_params(combo_name)
    scenarios = []

    for cost in COST_GRID:
        rt = int((cost["fees"] + cost["slippage"]) * 2 * 10_000)
        logger.info(f"  [{cost['label']}] round-trip={rt}bps")
        r = run_with_costs(combo_name, params, cost)
        scenarios.append(r)
        logger.info(
            f"    sharpe={r['sharpe']}  pf={r['pf']}  return={r['total_return']}%  viable={r['viable']}"
        )

    # Referencia: degradacion vs zero_cost
    zero = next((s for s in scenarios if s["label"] == "zero_cost"), None)
    base = next((s for s in scenarios if s["label"] == "optimizer_base"), None)

    if zero and zero["sharpe"] != 0:
        for s in scenarios:
            s["sharpe_vs_zero"] = round(s["sharpe"] - zero["sharpe"], 3)
            s["pct_sharpe_decay"] = (
                round((s["sharpe"] - zero["sharpe"]) / abs(zero["sharpe"]) * 100, 1)
                if zero["sharpe"]
                else 0
            )

    # Breakeven: ultimo escenario viable
    viable = [s for s in scenarios if s["viable"]]
    breakeven_bps = viable[-1]["roundtrip_bps"] if viable else 0

    assessment = (
        "ROBUSTO"
        if breakeven_bps >= 60
        else "MODERADO"
        if breakeven_bps >= 25
        else "FRAGIL"
    )

    # Tabla resumen
    logger.info(
        f"\n  {'Escenario':<22} {'RT-bps':>7} {'Sharpe':>8} {'PF':>6} {'Ret%':>7} {'Viable':>7}"
    )
    logger.info(f"  {'-' * 57}")
    for s in scenarios:
        v = "SI" if s["viable"] else "NO"
        logger.info(
            f"  {s['label']:<22} {s['roundtrip_bps']:>7} {s['sharpe']:>8.3f} "
            f"{s['pf']:>6.3f} {s['total_return']:>7.1f} {v:>7}"
        )

    logger.info(f"\n  Breakeven round-trip: {breakeven_bps}bps  ->  {assessment}")
    if base:
        logger.info(
            f"  Optimizer usó 20bps RT — sharpe en ese escenario: {base['sharpe']:.3f}"
        )

    result = {
        "combo": combo_name,
        "run_at": datetime.now().isoformat(),
        "period": {"start": PERIOD_START, "end": PERIOD_END},
        "scenarios": scenarios,
        "breakeven_bps": breakeven_bps,
        "assessment": assessment,
        "optimizer_baseline_bps": 20,
    }
    out_f = COST_OUT / f"{combo_name}_costs.json"
    import numpy as np

    def _to_native(obj):
        if isinstance(obj, dict): return {k: _to_native(v) for k, v in obj.items()}
        if isinstance(obj, list): return [_to_native(v) for v in obj]
        if isinstance(obj, (bool,)): return bool(obj)
        if hasattr(obj, "item"): return obj.item()  # numpy scalar
        return obj

    json.dump(_to_native(result), open(out_f, "w"), indent=2)
    logger.info(f"  Guardado: {out_f}")
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--combo", type=str)
    parser.add_argument("--all", action="store_true")
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
            r = analyze_combo_costs(combo)
            all_results.append(r)
        except FileNotFoundError as e:
            logger.warning(f"  Saltando {combo}: {e}")

    logger.info(f"\n{'=' * 60}")
    logger.info("RESUMEN SENSIBILIDAD A COSTOS")
    logger.info(f"{'=' * 60}")
    icons = {"ROBUSTO": "[OK]", "MODERADO": "[~~]", "FRAGIL": "[XX]"}
    for r in all_results:
        a = r["assessment"]
        logger.info(
            f"  {icons.get(a, '[?]')} {r['combo']:<35} breakeven={r['breakeven_bps']:>4}bps  {a}"
        )


if __name__ == "__main__":
    main()
