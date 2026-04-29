#!/usr/bin/env python3
"""
scripts/runbook_backtest_validation.py
=====================================
Runbook para validación backtest del pipeline Triad RTS.
Live completamente en pausa - solo backtest.

Uso:
    # Paso 1: Generar universostable
    python3 scripts/runbook_backtest_validation.py --step 1 --start 2019-01-01 --end 2025-12-31 --universe-size 200

    # Paso 2: Poblar RS rankings (por chunks de 6 meses)
    python3 scripts/runbook_backtest_validation.py --step 2 --start 2019-01-01 --end 2025-12-31 --chunk-months 6

    # Paso 3: Poblar Triad rankings (por chunks de 6 meses)
    python3 scripts/runbook_backtest_validation.py --step 3 --start 2019-01-01 --end 2025-12-31 --chunk-months 6

    # Paso 4: Build screener cache
    python3 scripts/runbook_backtest_validation.py --step 4 --universe-file data/stable_universe.csv

    # Paso 5: Run backtest IS/OOS
    python3 scripts/runbook_backtest_validation.py --step 5 --universe-file data/stable_universe.csv

"""

import sys
import os
import argparse
import logging
import sqlite3
import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Optional

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Import analytics bridge
from src.analytics.backtest_analytics_bridge import compute_backtest_analytics
from src.analytics.backtest_io import save_backtest_analytics

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

DB_PATH = PROJECT_ROOT / "data" / "ticker_cache.db"
UNIVERSE_FILE = PROJECT_ROOT / "data" / "stable_universe.csv"
SCREENER_CACHE_DIR = PROJECT_ROOT / "data" / "screener_cache"


# ============================================================================
# STEP 1: Generate Stable Universe (PIT)
# ============================================================================


def step1_generate_universe(start_date: str, end_date: str, universe_size: int = 200):
    """
    Genera universo estable por dollar volume trailing 60d.
    Rebalanceo trimestral para evitar survivorship bias.
    """
    logger.info(f"=" * 60)
    logger.info(f"STEP 1: Generando universo estable (top {universe_size})")
    logger.info(f"Rango: {start_date} a {end_date}")
    logger.info(f"=" * 60)

    conn = sqlite3.connect(DB_PATH)

    # Obtener trading dates del rango
    dates_query = f"""
        SELECT DISTINCT date FROM ohlcv_cache
        WHERE date >= '{start_date}' AND date <= '{end_date}'
        AND ticker NOT LIKE '%-KS' AND ticker NOT LIKE '%-VN' AND ticker NOT LIKE '%-T'
        AND ticker NOT LIKE '^%'
        ORDER BY date
    """
    all_dates = [r[0] for r in conn.execute(dates_query).fetchall()]

    if not all_dates:
        logger.error("No dates found in range")
        conn.close()
        return

    # Rebalanceo trimestral (4 veces por año)
    quarters = []
    current_year = int(all_dates[0][:4])
    current_quarter = (int(all_dates[0][5:7]) - 1) // 3

    for d in all_dates:
        y = int(d[:4])
        q = (int(d[5:7]) - 1) // 3
        if y > current_year or q > current_quarter:
            quarters.append(d)
            current_year = y
            current_quarter = q

    # Siempre incluir última fecha
    if all_dates[-1] not in quarters:
        quarters.append(all_dates[-1])

    logger.info(f"Trimestres a procesar: {len(quarters)}")

    universe_records = []

    for i, rebal_date in enumerate(quarters):
        # 60 días atrás para calcular dollar volume
        dv_start = (pd.to_datetime(rebal_date) - timedelta(days=90)).strftime(
            "%Y-%m-%d"
        )

        # Top tickers por dollar volume en ese período
        dv_query = f"""
            SELECT ticker, AVG(close * volume) as dv
            FROM ohlcv_cache
            WHERE date >= '{dv_start}' AND date <= '{rebal_date}'
            AND ticker NOT LIKE '%-KS' AND ticker NOT LIKE '%-VN' AND ticker NOT LIKE '%-T'
            AND ticker NOT LIKE '^%'
            GROUP BY ticker
            ORDER BY dv DESC
            LIMIT {universe_size}
        """
        top_tickers = conn.execute(dv_query).fetchall()

        for rank, (ticker, dv) in enumerate(top_tickers, 1):
            universe_records.append(
                {
                    "rebalance_date": rebal_date,
                    "ticker": ticker,
                    "rank": rank,
                    "dollar_volume": dv,
                }
            )

        logger.info(
            f"  [{i + 1}/{len(quarters)}] {rebal_date}: {len(top_tickers)} tickers"
        )

    # Guardar universo
    universe_df = pd.DataFrame(universe_records)
    universe_df.to_csv(UNIVERSE_FILE, index=False)

    conn.close()

    logger.info(f"Universo guardado en: {UNIVERSE_FILE}")
    logger.info(f"Total registros: {len(universe_df)}")
    logger.info(f"Tickers únicos: {universe_df['ticker'].nunique()}")
    logger.info(f"Paso 1 COMPLETADO")


# ============================================================================
# STEP 2: Populate RS Rankings
# ============================================================================


def step2_populate_rs(start_date: str, end_date: str, chunk_months: int = 6):
    """
    Pobla daily_rs_rankings por chunks de meses.
    """
    logger.info(f"=" * 60)
    logger.info(f"STEP 2: Poblar daily_rs_rankings")
    logger.info(f"Rango: {start_date} a {end_date}, chunks de {chunk_months} meses")
    logger.info(f"=" * 60)

    conn = sqlite3.connect(DB_PATH)

    # Asegurar tabla existe
    CREATE_TABLE_SQL = """
    CREATE TABLE IF NOT EXISTS daily_rs_rankings (
        date DATE NOT NULL,
        ticker TEXT NOT NULL,
        rs_60d_pct REAL,
        rs_20d_pct REAL,
        rs_5d_pct REAL,
        rs_composite REAL,
        universe_size INTEGER,
        computed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (date, ticker)
    )
    """
    conn.execute(CREATE_TABLE_SQL)
    conn.commit()

    # Generar chunks de fechas
    start = pd.to_datetime(start_date)
    end = pd.to_datetime(end_date)

    chunks = []
    current = start
    while current <= end:
        chunk_end = min(
            current + pd.DateOffset(months=chunk_months) - pd.Timedelta(days=1), end
        )
        chunks.append((current.strftime("%Y-%m-%d"), chunk_end.strftime("%Y-%m-%d")))
        current = chunk_end + pd.Timedelta(days=1)

    logger.info(f"Chunks a procesar: {len(chunks)}")

    for i, (chunk_start, chunk_end) in enumerate(chunks):
        logger.info(f"  [{i + 1}/{len(chunks)}] {chunk_start} a {chunk_end}")

        # Poblar mes por mes dentro del chunk
        month_start = pd.to_datetime(chunk_start)
        month_end = pd.to_datetime(chunk_end)

        months_in_chunk = []
        m = month_start
        while m <= month_end:
            months_in_chunk.append(m)
            m = m + pd.DateOffset(months=1)

        for month_dt in months_in_chunk:
            m_start = month_dt.strftime("%Y-%m-%d")
            m_end = (
                month_dt + pd.DateOffset(months=1) - pd.Timedelta(days=1)
            ).strftime("%Y-%m-%d")
            m_end = min(m_end, chunk_end)

            # Skip si ya existe
            existing = conn.execute(
                "SELECT COUNT(*) FROM daily_rs_rankings WHERE date = ?", (m_start,)
            ).fetchone()[0]

            if existing > 0:
                logger.info(f"      {m_start}: ya existe, skip")
                continue

            # Ejecutar populate para esta fecha
            sys.path.insert(0, str(PROJECT_ROOT))
            from scripts.populate_rs_rankings import compute_rs_for_date

            try:
                result = compute_rs_for_date(conn, m_start)
                if not result.empty:
                    result.to_sql(
                        "daily_rs_rankings", conn, if_exists="append", index=False
                    )
                    conn.commit()
                    logger.info(f"      {m_start}: {len(result)} tickers")
            except Exception as e:
                logger.warning(f"      {m_start}: ERROR - {str(e)[:50]}")

    conn.close()
    logger.info(f"Paso 2 COMPLETADO")


# ============================================================================
# STEP 3: Populate Triad Rankings
# ============================================================================


def step3_populate_triad(start_date: str, end_date: str, chunk_months: int = 6):
    """
    Pobla daily_triad_rankings por chunks de meses.
    """
    logger.info(f"=" * 60)
    logger.info(f"STEP 3: Poblar daily_triad_rankings")
    logger.info(f"Rango: {start_date} a {end_date}, chunks de {chunk_months} meses")
    logger.info(f"=" * 60)

    conn = sqlite3.connect(DB_PATH)

    # Asegurar tabla existe
    CREATE_TABLE_SQL = """
    CREATE TABLE IF NOT EXISTS daily_triad_rankings (
        date DATE NOT NULL,
        ticker TEXT NOT NULL,
        as_5d_pct REAL,
        as_21d_pct REAL,
        trend_score_raw REAL,
        rs_composite REAL,
        rts_raw REAL,
        rts_pct REAL,
        atr14 REAL,
        atr14_universe_mean REAL,
        pivot_dist_pct REAL,
        green_candle INTEGER,
        universe_size INTEGER,
        computed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (date, ticker)
    )
    """
    conn.execute(CREATE_TABLE_SQL)
    conn.commit()

    # Cargar universo para filtrar
    if UNIVERSE_FILE.exists():
        universe_df = pd.read_csv(UNIVERSE_FILE)
        all_tickers = sorted(universe_df["ticker"].unique().tolist())
        logger.info(f"Usando universo de {len(all_tickers)} tickers")
    else:
        all_tickers = None
        logger.warning("Universo no encontrado, usando todos los tickers")

    # Generar chunks de fechas
    start = pd.to_datetime(start_date)
    end = pd.to_datetime(end_date)

    chunks = []
    current = start
    while current <= end:
        chunk_end = min(
            current + pd.DateOffset(months=chunk_months) - pd.Timedelta(days=1), end
        )
        chunks.append((current.strftime("%Y-%m-%d"), chunk_end.strftime("%Y-%m-%d")))
        current = chunk_end + pd.Timedelta(days=1)

    logger.info(f"Chunks a procesar: {len(chunks)}")

    for i, (chunk_start, chunk_end) in enumerate(chunks):
        logger.info(f"  [{i + 1}/{len(chunks)}] {chunk_start} a {chunk_end}")

        # Poblar mes por mes dentro del chunk
        month_start = pd.to_datetime(chunk_start)
        month_end = pd.to_datetime(chunk_end)

        months_in_chunk = []
        m = month_start
        while m <= month_end:
            months_in_chunk.append(m)
            m = m + pd.DateOffset(months=1)

        for month_dt in months_in_chunk:
            m_start = month_dt.strftime("%Y-%m-%d")
            m_end = (
                month_dt + pd.DateOffset(months=1) - pd.Timedelta(days=1)
            ).strftime("%Y-%m-%d")
            m_end = min(m_end, chunk_end)

            # Skip si ya existe
            existing = conn.execute(
                "SELECT COUNT(*) FROM daily_triad_rankings WHERE date = ?", (m_start,)
            ).fetchone()[0]

            if existing > 0:
                logger.info(f"      {m_start}: ya existe, skip")
                continue

            # Ejecutar populate para esta fecha
            sys.path.insert(0, str(PROJECT_ROOT))
            from scripts.populate_triad_rankings import compute_triad_for_date

            try:
                result = compute_triad_for_date(conn, m_start, max_tickers=500)
                if not result.empty:
                    # Filtrar por universo si existe
                    if all_tickers:
                        result = result[result["ticker"].isin(all_tickers)]

                    if not result.empty:
                        result.to_sql(
                            "daily_triad_rankings",
                            conn,
                            if_exists="append",
                            index=False,
                        )
                        conn.commit()
                        logger.info(f"      {m_start}: {len(result)} tickers")
            except Exception as e:
                logger.warning(f"      {m_start}: ERROR - {str(e)[:50]}")

    conn.close()
    logger.info(f"Paso 3 COMPLETADO")


# ============================================================================
# STEP 4: Build Screener Cache
# ============================================================================


def step4_build_screener_cache(universe_file: str):
    """
    Construye screener cache para triad_rts.
    """
    logger.info(f"=" * 60)
    logger.info(f"STEP 4: Build screener cache")
    logger.info(f"=" * 60)

    # Cargar universo
    universe_df = pd.read_csv(universe_file)
    all_tickers = sorted(universe_df["ticker"].unique().tolist())

    logger.info(f"Universe: {len(all_tickers)} tickers")

    # Limpiar cache viejo
    cache_file = SCREENER_CACHE_DIR / "triad_rts.parquet"
    meta_file = SCREENER_CACHE_DIR / "triad_rts.meta.json"

    if cache_file.exists():
        cache_file.unlink()
        logger.info("Cache antiguo eliminado")
    if meta_file.exists():
        meta_file.unlink()
        logger.info("Meta antiguo eliminado")

    # Build nuevo cache
    from src.data.screener_cache import ScreenerCacheManager
    from src.screeners import ScreenerRegistry

    SCREENER_CACHE = ScreenerCacheManager()
    screener = ScreenerRegistry.get("triad_rts")

    # Rango completo del universo
    min_date = universe_df["rebalance_date"].min()
    max_date = universe_df["rebalance_date"].max()

    logger.info(f"Building cache from {min_date} to {max_date}...")
    logger.info("NOTE: This may take several minutes per 100 tickers. Check progress bar below.")

    result = SCREENER_CACHE.build_for_combo(
        screener_name="triad_rts",
        tickers=all_tickers,
        start_date=min_date,
        end_date=max_date,
    )

    logger.info(f"Cache construido: {len(result)} rows")
    logger.info(f"Passed: {result['passed'].sum()}")
    logger.info(f"Paso 4 COMPLETADO")


# ============================================================================
# STEP 5: Run Backtest
# ============================================================================


def step5_run_backtest(universe_file: str):
    """
    Ejecuta backtest de validación.
    """
    logger.info(f"=" * 60)
    logger.info(f"STEP 5: Run Backtest Validation")
    logger.info(f"=" * 60)

    # Cargar universo
    universe_df = pd.read_csv(universe_file)
    all_tickers = sorted(universe_df["ticker"].unique().tolist())

    logger.info(f"Universe: {len(all_tickers)} tickers")

    # Split IS/OOS
    is_end = "2022-12-31"
    oos_start = "2023-01-01"
    oos_end = "2024-12-31"

    logger.info(f"IS: 2019-01-01 to {is_end}")
    logger.info(f"OOS: {oos_start} to {oos_end}")

    def _extract_metrics(result: dict) -> dict:
        """
        Normaliza métricas de salida del engine.
        Soporta:
        - result["metrics"] (estructura anidada)
        - métricas en raíz (vectorbt_engine_advanced)
        """
        if not isinstance(result, dict):
            return {}

        if isinstance(result.get("metrics"), dict) and result.get("metrics"):
            m = result["metrics"].copy()
        else:
            m = {
                "sharpe_ratio": result.get("sharpe_ratio", result.get("sharpe", 0)),
                "win_rate": result.get("win_rate", result.get("win_rate_pct", 0)),
                "profit_factor": result.get("profit_factor", 0),
                "max_drawdown": result.get("max_drawdown", 0),
                "annualized_return": result.get(
                    "annualized_return", result.get("cagr", 0)
                ),
                "total_return": result.get("total_return", 0),
            }

        # Normalize win_rate to fraction [0,1] if comes in percent [0,100]
        wr = m.get("win_rate", 0)
        try:
            wr = float(wr)
            if wr > 1.0:
                wr = wr / 100.0
            m["win_rate"] = wr
        except Exception:
            m["win_rate"] = 0.0

        return m

    # Run IS
    logger.info(f"\n--- Running IS Backtest ---")
    sys.path.insert(0, str(PROJECT_ROOT))
    from src.backtest.vectorbt_engine_advanced import AdvancedVectorBTEngine

    engine_is = AdvancedVectorBTEngine(
        universe=all_tickers,
        start_date="2019-01-01",
        end_date=is_end,
        initial_capital=100_000,
        risk_dollars=150,
        screener_name="triad_rts",
        screener_cache_path=str(SCREENER_CACHE_DIR),
    )

    result_is = engine_is.run_backtest()
    trades_is = result_is.get("trades_df", pd.DataFrame())
    metrics_is = _extract_metrics(result_is)

    logger.info(f"IS Results:")
    logger.info(f"  Trades: {len(trades_is)}")
    logger.info(f"  Sharpe: {metrics_is.get('sharpe_ratio', 0):.2f}")
    logger.info(f"  Win Rate: {metrics_is.get('win_rate', 0) * 100:.1f}%")
    logger.info(f"  Profit Factor: {metrics_is.get('profit_factor', 0):.2f}")
    logger.info(f"  Max DD: {metrics_is.get('max_drawdown', 0) * 100:.1f}%")

    engine_is.cleanup()

    # Run OOS
    logger.info(f"\n--- Running OOS Backtest ---")

    engine_oos = AdvancedVectorBTEngine(
        universe=all_tickers,
        start_date=oos_start,
        end_date=oos_end,
        initial_capital=100_000,
        risk_dollars=150,
        screener_name="triad_rts",
        screener_cache_path=str(SCREENER_CACHE_DIR),
    )

    result_oos = engine_oos.run_backtest()
    trades_oos = result_oos.get("trades_df", pd.DataFrame())
    metrics_oos = _extract_metrics(result_oos)

    logger.info(f"OOS Results:")
    logger.info(f"  Trades: {len(trades_oos)}")
    logger.info(f"  Sharpe: {metrics_oos.get('sharpe_ratio', 0):.2f}")
    logger.info(f"  Win Rate: {metrics_oos.get('win_rate', 0) * 100:.1f}%")
    logger.info(f"  Profit Factor: {metrics_oos.get('profit_factor', 0):.2f}")
    logger.info(f"  Max DD: {metrics_oos.get('max_drawdown', 0) * 100:.1f}%")

    engine_oos.cleanup()

    # Validación Go/No-Go
    logger.info(f"\n{'=' * 60}")
    logger.info(f"VALIDATION SUMMARY")
    logger.info(f"{'=' * 60}")

    is_ok = (
        len(trades_is) >= 50
        and metrics_is.get("profit_factor", 0) > 1.0
        and metrics_is.get("sharpe_ratio", 0) > 0
    )

    oos_ok = (
        len(trades_oos) >= 20
        and metrics_oos.get("profit_factor", 0) > 0.8  # Menos exigente en OOS
        and metrics_oos.get("win_rate", 0) > 0.30
    )

    if is_ok and oos_ok:
        logger.info(f"✅ GO - Pipeline validado para pasar a fase pre-live")
    else:
        logger.info(f"❌ NO-GO - Revisar métricas antes de proceder")

    logger.info(f"Paso 5 COMPLETADO")

    # === Save backtest analytics ===
    logger.info(f"\n--- Saving Backtest Analytics ---")

    # Generate run_id
    run_id = f"bt_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    # Build equity curve from trades (approximation)
    # For a more accurate equity curve, the engine provides it
    equity_curve = pd.Series()
    if result_is.get("equity_curve") is not None:
        equity_curve = result_is["equity_curve"]
    elif not trades_is.empty:
        # Fallback: reconstruct from trades
        equity = 100_000
        equity_curve = pd.Series([equity])
        for _, trade in trades_is.iterrows():
            equity += trade.get("pnl", 0)
            equity_curve = pd.concat([equity_curve, pd.Series([equity])])

    # Compute and save IS analytics
    if not trades_is.empty:
        is_analytics = compute_backtest_analytics(
            results=metrics_is,
            trades_df=trades_is,
            equity_curve=equity_curve,
            start_date="2019-01-01",
            end_date=is_end,
            run_id=f"{run_id}_IS",
            initial_capital=100_000,
            risk_per_trade_pct=0.02,
            engine_name="vectorbt_advanced",
        )
        save_backtest_analytics(f"{run_id}_IS", is_analytics)

        logger.info(f"  IS Analytics saved: {len(trades_is)} trades")
        logger.info(f"    CAGR: {is_analytics['trade_stats']['cagr_pct']}%")
        logger.info(f"    PF: {is_analytics['overall_quality']['profit_factor']}")
        logger.info(f"    Regime cards: {len(is_analytics['regime_cards'])}")

    # Compute and save OOS analytics
    if not trades_oos.empty:
        equity_curve_oos = pd.Series()
        if result_oos.get("equity_curve") is not None:
            equity_curve_oos = result_oos["equity_curve"]

        oos_analytics = compute_backtest_analytics(
            results=metrics_oos,
            trades_df=trades_oos,
            equity_curve=equity_curve_oos,
            start_date=oos_start,
            end_date=oos_end,
            run_id=f"{run_id}_OOS",
            initial_capital=100_000,
            risk_per_trade_pct=0.02,
            engine_name="vectorbt_advanced",
        )
        save_backtest_analytics(f"{run_id}_OOS", oos_analytics)

        logger.info(f"  OOS Analytics saved: {len(trades_oos)} trades")
        logger.info(f"    CAGR: {oos_analytics['trade_stats']['cagr_pct']}%")
        logger.info(f"    PF: {oos_analytics['overall_quality']['profit_factor']}")
        logger.info(f"    Regime cards: {len(oos_analytics['regime_cards'])}")

    logger.info(f"✅ Backtest analytics saved to outputs/backtests/")

    return {
        "is_metrics": metrics_is,
        "oos_metrics": metrics_oos,
        "is_ok": is_ok,
        "oos_ok": oos_ok,
    }


# ============================================================================
# MAIN
# ============================================================================


def main():
    parser = argparse.ArgumentParser(description="Runbook Backtest Validation")
    parser.add_argument(
        "--step",
        type=int,
        required=True,
        help="1=Universe, 2=RS, 3=Triad, 4=Cache, 5=Backtest",
    )
    parser.add_argument("--start", type=str, default="2019-01-01")
    parser.add_argument("--end", type=str, default="2025-12-31")
    parser.add_argument("--universe-size", type=int, default=200)
    parser.add_argument("--chunk-months", type=int, default=6)
    parser.add_argument("--universe-file", type=str, default=str(UNIVERSE_FILE))

    args = parser.parse_args()

    logger.info(f"Iniciando Step {args.step}")

    if args.step == 1:
        step1_generate_universe(args.start, args.end, args.universe_size)
    elif args.step == 2:
        step2_populate_rs(args.start, args.end, args.chunk_months)
    elif args.step == 3:
        step3_populate_triad(args.start, args.end, args.chunk_months)
    elif args.step == 4:
        step4_build_screener_cache(args.universe_file)
    elif args.step == 5:
        step5_run_backtest(args.universe_file)
    else:
        logger.error(f"Step inválido: {args.step}")

    logger.info(f"Runbook completado")


if __name__ == "__main__":
    main()
