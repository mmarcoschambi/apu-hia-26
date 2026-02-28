#!/usr/bin/env python3
"""
USE VALIDATED PARAMS IN PRODUCTION
===================================

Aplica los parámetros validados de config/validated_production_params.json
al motor Advanced para backtesting o live trading.

Usage:
    # Full backtest con params validados
    python3 use_validated_params.py --start 2020-01-01 --end 2024-12-31

    # Quick test
    python3 use_validated_params.py --start 2024-01-01 --end 2024-06-30

    # Con toda la data disponible
    python3 use_validated_params.py --all

    # Con features opcionales
    python3 use_validated_params.py --start 2023-01-01 --use-sector-rotation --use-market-regime
"""

import sys
import json
import argparse
from pathlib import Path
import logging
import sqlite3
from datetime import datetime

sys.path.insert(0, str(Path(__file__).resolve().parent))

from src.backtest.vectorbt_engine_advanced import AdvancedVectorBTEngine

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("ValidatedParams")


def load_validated_params():
    """Carga params validados."""
    config_file = Path("config/validated_production_params.json")

    if not config_file.exists():
        logger.error(f"❌ No validated params found: {config_file}")
        logger.error("   Run dual validation first:")
        logger.error("   bash run_dual_validation.sh --quick")
        return None

    with open(config_file, "r") as f:
        data = json.load(f)

    return data


def get_earliest_date_from_db():
    """Obtiene la fecha más antigua disponible en la base de datos."""
    db_path = Path("data/ticker_cache.db")

    if not db_path.exists():
        logger.warning("⚠️  Database not found, defaulting to 2015-01-01")
        return "2015-01-01"

    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Try ticker_cache table first (most common)
        cursor.execute("""
            SELECT MIN(date(timestamp)) 
            FROM ticker_cache 
            WHERE timestamp IS NOT NULL
        """)

        result = cursor.fetchone()
        conn.close()

        if result and result[0]:
            logger.info(f"   📊 Found data starting from: {result[0]}")
            return result[0]
        else:
            logger.warning("⚠️  No data found in database, defaulting to 2015-01-01")
            return "2015-01-01"

    except Exception as e:
        logger.warning(f"⚠️  Error reading database: {e}, defaulting to 2015-01-01")
        return "2015-01-01"


def main():
    parser = argparse.ArgumentParser(
        description="Use validated params with Advanced engine"
    )
    parser.add_argument(
        "--start", type=str, default=None, help="Start date (YYYY-MM-DD)"
    )
    parser.add_argument(
        "--end", type=str, default=None, help="End date (YYYY-MM-DD), default=today"
    )
    parser.add_argument(
        "--all", action="store_true", help="Use all available data (overrides --start)"
    )
    parser.add_argument(
        "--tickers",
        nargs="+",
        default=None,
        help="Override universe (default: use validated universe)",
    )
    parser.add_argument(
        "--use-sector-rotation",
        action="store_true",
        help="Enable sector rotation filter",
    )
    parser.add_argument(
        "--use-market-regime", action="store_true", help="Enable market regime filter"
    )
    parser.add_argument(
        "--use-trailing-stop", action="store_true", help="Enable trailing stop"
    )
    parser.add_argument(
        "--capital", type=float, default=100000, help="Initial capital (default: $100k)"
    )

    args = parser.parse_args()

    # Determine start date
    if args.all:
        start_date = get_earliest_date_from_db()
        logger.info(f"🗄️  Using all available data from: {start_date}")
    elif args.start:
        start_date = args.start
    else:
        parser.error("Either --start or --all must be specified")
        return

    # Load validated params
    config = load_validated_params()
    if not config:
        return

    params = config["parameters"]

    # Override universe if specified
    if args.tickers:
        universe = args.tickers
    elif "universe" in config:
        # Use universe from validated config
        universe = config["universe"]
        logger.info(f"   Using universe from validated config: {len(universe)} tickers")
    else:
        # Use default good tickers (matches validation)
        universe = [
            "AAPL",
            "MSFT",
            "GOOGL",
            "NVDA",
            "TSLA",
            "META",
            "AMZN",
            "NFLX",
            "AMD",
            "AVGO",
        ]
        logger.info(f"   Using default universe: {len(universe)} tickers")

    logger.info("=" * 70)
    logger.info("🏭 PRODUCTION BACKTEST WITH VALIDATED PARAMS")
    logger.info("=" * 70)
    logger.info(f"\n📋 Config Info:")
    logger.info(f"   Source: {config.get('config_name', 'N/A')}")
    logger.info(f"   Validated: {config.get('validated_date', 'N/A')}")
    logger.info(
        f"   Original validation period: {config.get('validation_period', 'N/A')}"
    )

    if "performance" in config:
        perf = config["performance"]
        logger.info(f"\n   📊 Validation Performance:")
        logger.info(f"      • Sharpe: {perf.get('sharpe_ratio', 0):.3f}")
        logger.info(
            f"      • Annual Return: {perf.get('annualized_return_pct', 0):.2f}%"
        )
        logger.info(f"      • Win Rate: {perf.get('win_rate_pct', 0):.1f}%")
        logger.info(f"      • Max DD: {perf.get('max_drawdown_pct', 0):.2f}%")

    logger.info(f"\n🎯 Running backtest:")
    logger.info(f"   Period: {start_date} → {args.end or 'today'}")
    logger.info(f"   Universe: {len(universe)} tickers")
    logger.info(f"   Capital: ${args.capital:,.0f}")

    # Build engine params
    engine_params = params.copy()

    # Override filters that may block all trades in validation
    # User can re-enable via command line flags
    engine_params["require_spy_above_sma50"] = False  # Override to allow entries

    # Add optional features if requested
    if args.use_sector_rotation:
        engine_params["use_composite_sector_scoring"] = True
        logger.info("   🔧 Sector rotation: ENABLED")

    if args.use_market_regime:
        engine_params["use_market_regime_filter"] = True
        engine_params["require_spy_above_sma50"] = (
            True  # Re-enable if using market regime
        )
        logger.info("   🔧 Market regime: ENABLED")

    if args.use_trailing_stop:
        engine_params["use_trailing_stop"] = True
        logger.info("   🔧 Trailing stop: ENABLED")

    # Set signal_type for convergence
    engine_params["signal_type"] = "breakout"

    # Create engine
    engine = AdvancedVectorBTEngine(
        universe=universe,
        start_date=start_date,
        end_date=args.end,
        initial_capital=args.capital,
        **engine_params,
    )

    # Run backtest
    result = engine.run_backtest()

    # Display results
    logger.info("\n" + "=" * 70)
    logger.info("📊 RESULTS WITH VALIDATED PARAMS")
    logger.info("=" * 70)

    logger.info(f"\n   💰 Returns:")
    logger.info(f"      Total Return: {result['total_return'] * 100:.2f}%")
    if "annualized_return" in result:
        logger.info(f"      Annualized: {result['annualized_return'] * 100:.2f}%")

    logger.info(f"\n   📊 Performance:")
    logger.info(f"      Sharpe Ratio: {result['sharpe_ratio']:.3f}")
    if "mar_ratio" in result:
        logger.info(f"      MAR Ratio: {result['mar_ratio']:.2f}")
    if "calmar_ratio" in result:
        logger.info(f"      Calmar Ratio: {result['calmar_ratio']:.2f}")

    logger.info(f"\n   🎯 Trading:")
    logger.info(f"      Total Trades: {result['total_trades']}")
    logger.info(f"      Win Rate: {result['win_rate'] * 100:.1f}%")

    logger.info(f"\n   📉 Risk:")
    logger.info(f"      Max Drawdown: {result['max_drawdown'] * 100:.2f}%")

    logger.info("\n✅ Backtest complete!")
    logger.info("\n💡 Next Steps:")
    logger.info("   • If satisfied, use these params in app.py")
    logger.info("   • Or run live_scanner.py with validated params")
    logger.info("   • Or paper trade to verify results")


if __name__ == "__main__":
    main()
