#!/usr/bin/env python3
"""
VALIDATE TOP PARAMS WITH ADVANCED ENGINE
=========================================

Toma los mejores parámetros encontrados por Walk Forward (V6_PRO/THOR)
y los valida con AdvancedVectorBTEngine en período largo.

Esto garantiza que los params optimizados con motor rápido
funcionen correctamente en el motor de producción.

Usage:
    python3 validate_top_params_with_advanced.py --top 3 --period 2020-01-01:2024-12-31
"""

import sys
import json
import argparse
import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime
import logging
from typing import Dict, List

sys.path.insert(0, str(Path(__file__).resolve().parent))

from src.backtest.vectorbt_engine_advanced import AdvancedVectorBTEngine

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("ValidateTop")


def load_walk_forward_results():
    """Carga resultados del Walk Forward."""
    results_file = Path("outputs/walk_forward_results.json")

    if not results_file.exists():
        logger.error(f"❌ No results file found: {results_file}")
        logger.error("   Run Walk Forward first: python walk_forward_validation.py")
        return None

    with open(results_file, "r") as f:
        data = json.load(f)

    return data


def rank_configurations(results: Dict) -> List[Dict]:
    """Rankea configuraciones por performance OOS."""
    windows = results["windows"]

    # Agregar config_id único a cada window
    for w in windows:
        # Create hash of params for grouping
        param_str = json.dumps(w["params"], sort_keys=True)
        w["param_hash"] = hash(param_str)

    # Sort by OOS Sharpe (mejor primero)
    ranked = sorted(windows, key=lambda x: x["oos_sharpe"], reverse=True)

    return ranked


def validate_params_with_advanced(
    params: Dict, universe: List[str], start_date: str, end_date: str, config_name: str
) -> Dict:
    """Valida una configuración de params con Advanced engine."""

    logger.info(f"\n{'=' * 70}")
    logger.info(f"🔬 VALIDATING: {config_name}")
    logger.info(f"{'=' * 70}")
    logger.info(f"   Period: {start_date} → {end_date}")
    logger.info(f"   Universe: {len(universe)} tickers")

    # Mostrar params clave
    logger.info(f"\n   📋 Key Parameters:")
    key_params = [
        "min_rvol",
        "min_adr",
        "risk_dollars",
        "max_dist_sma20",
        "tp1_r",
        "tp2_r",
    ]
    for key in key_params:
        if key in params:
            logger.info(f"      • {key}: {params[key]}")

    try:
        # Crear engine con Advanced (motor de producción)
        engine = AdvancedVectorBTEngine(
            universe=universe,
            start_date=start_date,
            end_date=end_date,
            signal_type="any",  # Use 'any' for compatibility with validated params
            **params,
        )

        result = engine.run_backtest()

        logger.info(f"\n   📊 Advanced Results:")
        logger.info(f"      Sharpe: {result['sharpe_ratio']:.3f}")
        logger.info(f"      Return: {result['total_return'] * 100:.2f}%")
        logger.info(f"      Annual: {result['annualized_return'] * 100:.2f}%")
        logger.info(f"      Trades: {result['total_trades']}")
        logger.info(f"      Win Rate: {result['win_rate'] * 100:.1f}%")
        logger.info(f"      Max DD: {result['max_drawdown'] * 100:.2f}%")
        logger.info(f"      MAR Ratio: {result.get('mar_ratio', 0):.2f}")

        return {
            "config_name": config_name,
            "params": params,
            "sharpe": result["sharpe_ratio"],
            "return": result["total_return"],
            "annualized_return": result["annualized_return"],
            "trades": result["total_trades"],
            "win_rate": result["win_rate"],
            "max_dd": result["max_drawdown"],
            "mar_ratio": result.get("mar_ratio", 0),
            "status": "success",
        }

    except Exception as e:
        logger.error(f"\n   ❌ Validation failed: {e}")
        return {
            "config_name": config_name,
            "params": params,
            "status": "failed",
            "error": str(e),
        }


def main():
    parser = argparse.ArgumentParser(description="Validate top params with Advanced")
    parser.add_argument(
        "--top", type=int, default=3, help="Number of top configs to validate"
    )
    parser.add_argument(
        "--period",
        type=str,
        default="2020-01-01:2024-12-31",
        help="Validation period (start:end)",
    )
    parser.add_argument(
        "--min-trades",
        type=int,
        default=10,
        help="Minimum trades required for valid config",
    )

    args = parser.parse_args()

    # Parse period
    start_date, end_date = args.period.split(":")

    logger.info("=" * 70)
    logger.info("🔬 TOP PARAMS VALIDATION WITH ADVANCED ENGINE")
    logger.info("=" * 70)
    logger.info(f"📅 Validation Period: {start_date} → {end_date}")
    logger.info(f"🏆 Top configs to test: {args.top}")
    logger.info(f"🎯 Min trades required: {args.min_trades}\n")

    # Load Walk Forward results
    wf_results = load_walk_forward_results()
    if not wf_results:
        return

    universe = wf_results["universe"]

    # Rank configurations
    logger.info("📊 Ranking configurations by OOS performance...")
    ranked = rank_configurations(wf_results)

    logger.info(f"\n🏆 Top {args.top} configurations from Walk Forward:")
    for i, window in enumerate(ranked[: args.top], 1):
        logger.info(
            f"   {i}. Window {window['window_id']}: "
            f"Sharpe={window['oos_sharpe']:.2f}, "
            f"Return={window['oos_return'] * 100:.2f}%, "
            f"Trades={window['oos_trades']}"
        )

    # Validate each top config with Advanced
    validation_results = []

    for i, window in enumerate(ranked[: args.top], 1):
        config_name = f"Config_{i}_Window_{window['window_id']}"
        params = window["params"]

        result = validate_params_with_advanced(
            params=params,
            universe=universe,
            start_date=start_date,
            end_date=end_date,
            config_name=config_name,
        )

        validation_results.append(result)

    # Summary and recommendation
    logger.info("\n" + "=" * 70)
    logger.info("📊 VALIDATION SUMMARY")
    logger.info("=" * 70)

    logger.info(
        f"\n{'Config':<15} | {'Sharpe':<8} | {'Return':<10} | {'Trades':<8} | {'WR':<8} | {'Status'}"
    )
    logger.info("-" * 70)

    valid_results = [r for r in validation_results if r["status"] == "success"]

    for result in valid_results:
        logger.info(
            f"{result['config_name']:<15} | "
            f"{result['sharpe']:<8.2f} | "
            f"{result['return'] * 100:<10.2f}% | "
            f"{result['trades']:<8} | "
            f"{result['win_rate'] * 100:<7.1f}% | "
            f"{result['status']}"
        )

    # Filter by min_trades and select best
    qualified = [
        r for r in valid_results if r["trades"] >= args.min_trades and r["sharpe"] > 0
    ]

    if qualified:
        best = max(qualified, key=lambda x: x["sharpe"])

        logger.info("\n" + "=" * 70)
        logger.info("🏆 RECOMMENDED CONFIGURATION FOR PRODUCTION")
        logger.info("=" * 70)

        logger.info(f"\n   Config: {best['config_name']}")
        logger.info(f"   ✅ Validated with Advanced (production engine)")
        logger.info(f"\n   📊 Performance:")
        logger.info(f"      • Sharpe: {best['sharpe']:.3f}")
        logger.info(
            f"      • Annualized Return: {best['annualized_return'] * 100:.2f}%"
        )
        logger.info(f"      • Total Return: {best['return'] * 100:.2f}%")
        logger.info(f"      • Trades: {best['trades']}")
        logger.info(f"      • Win Rate: {best['win_rate'] * 100:.1f}%")
        logger.info(f"      • Max DD: {best['max_dd'] * 100:.2f}%")
        logger.info(f"      • MAR Ratio: {best['mar_ratio']:.2f}")

        # Save recommended params
        output_file = Path("config/validated_production_params.json")
        output_file.parent.mkdir(exist_ok=True)

        output = {
            "validated_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "validation_period": f"{start_date} to {end_date}",
            "source": "walk_forward + advanced_validation",
            "config_name": best["config_name"],
            "universe": universe,  # Agregar universo usado en validación
            "performance": {
                "sharpe_ratio": best["sharpe"],
                "annualized_return_pct": best["annualized_return"] * 100,
                "total_return_pct": best["return"] * 100,
                "total_trades": best["trades"],
                "win_rate_pct": best["win_rate"] * 100,
                "max_drawdown_pct": best["max_dd"] * 100,
                "mar_ratio": best["mar_ratio"],
            },
            "parameters": best["params"],
        }

        with open(output_file, "w") as f:
            json.dump(output, f, indent=2)

        logger.info(f"\n   💾 Saved to: {output_file}")

    else:
        logger.warning("\n⚠️  NO configurations met criteria!")
        logger.warning(f"   Min trades required: {args.min_trades}")
        logger.warning(f"   Min Sharpe: > 0")
        logger.warning("\n   💡 Suggestions:")
        logger.warning("      • Lower --min-trades threshold")
        logger.warning("      • Run Walk Forward with more data")
        logger.warning("      • Relax optimization constraints")

    logger.info("\n✅ Validation complete!")


if __name__ == "__main__":
    main()
