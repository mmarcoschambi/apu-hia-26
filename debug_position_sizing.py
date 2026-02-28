#!/usr/bin/env python3
"""
DEBUG POSITION SIZING - Verifica por qué R-múltiple es 0.00
"""

import sys
import json
from pathlib import Path
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.backtest.optimization_engine_thor import OptimizationEngineTHOR


def load_validated_params():
    """Carga parámetros validados"""
    with open("config/validated_production_params.json", "r") as f:
        return json.load(f)


def debug_position_sizing():
    """Debug del cálculo de position sizing"""
    print("\n" + "=" * 80)
    print("🔬 POSITION SIZING DEBUG")
    print("=" * 80)

    params = load_validated_params()["parameters"]

    print("\n📋 Parámetros clave:")
    print(f"   risk_dollars: ${params.get('risk_dollars', 0)}")
    print(f"   max_stop_pct: {params.get('max_stop_pct', 0)}%")
    print(f"   tp1_r: {params.get('tp1_r', 0)}R")
    print(f"   tp2_r: {params.get('tp2_r', 0)}R")

    # Test con NVDA
    ticker = "NVDA"
    start_date = "2024-01-01"
    end_date = "2024-06-30"

    print(f"\n🎯 Test: {ticker} ({start_date} to {end_date})")

    try:
        engine = OptimizationEngineTHOR(
            tickers=[ticker],
            start_date=start_date,
            end_date=end_date,
            initial_capital=100000,
            offline_mode=True,
        )

        # Copiar params y añadir signal_type
        backtest_params = params.copy()
        backtest_params["signal_type"] = "any"
        result = engine.backtest(backtest_params)

        if "trades_df" in result and not result["trades_df"].empty:
            trades = result["trades_df"]

            print(f"\n📊 Total trades: {len(trades)}")

            # Análisis de position sizing
            print("\n🔬 Position Sizing Analysis:")

            if all(
                col in trades.columns for col in ["entry_price", "stop_price", "shares"]
            ):
                trades["r_multiple"] = (
                    trades["entry_price"] - trades["stop_price"]
                ) / trades["stop_price"]

                print("\n   First 5 trades:")
                print(
                    f"   {'Entry':>10} | {'Stop':>10} | {'Shares':>10} | {'R':>10} | {'Exit':>10}"
                )
                print("   " + "-" * 60)

                for _, trade in trades.head(5).iterrows():
                    entry = trade.get("entry_price", 0)
                    stop = trade.get("stop_price", 0)
                    shares = trade.get("shares", 0)
                    r_multiple = trade.get("r_multiple", 0)
                    exit_type = trade.get("exit_type", "N/A")

                    print(
                        f"   {entry:>10.2f} | {stop:>10.2f} | {shares:>10.0f} | {r_multiple:>10.3f}R | {str(exit_type)[:10]:>10}"
                    )

                # Estadísticas
                print(f"\n📊 R-Multiple Statistics:")
                print(f"   Mean R: {trades['r_multiple'].mean():.3f}R")
                print(f"   Min R: {trades['r_multiple'].min():.3f}R")
                print(f"   Max R: {trades['r_multiple'].max():.3f}R")
                print(f"   Std R: {trades['r_multiple'].std():.3f}R")
                print(f"   Zero R: {(trades['r_multiple'] == 0).sum()} trades")

                # Check if all R are zero
                if (trades["r_multiple"] == 0).all():
                    print("\n🔴 CRITICAL ISSUE: All trades have R=0!")
                    print("\n   Possible causes:")
                    print(
                        "   1. max_stop_pct is too large (current: {:.1f}%)".format(
                            params.get("max_stop_pct", 0)
                        )
                    )
                    print("   2. stop_price equals entry_price")
                    print("   3. Bug in stop calculation")
                    print("\n   Recommended fix:")
                    print("   - Reduce max_stop_pct to 2.0-3.0%")
            else:
                print("\n⚠️  Required columns not found in trades_df")
                print(f"   Available: {list(trades.columns)}")

        else:
            print("\n⚠️  No trades generated")

    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    debug_position_sizing()
