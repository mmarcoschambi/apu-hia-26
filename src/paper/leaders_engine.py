"""
src/paper/leaders_engine.py
===========================
Engine para calcular líderes sectoriales, diarios y semanales para paper trading.

Uso:
    from src.paper.leaders_engine import compute_sector_leaders, compute_daily_leaders, compute_weekly_leaders

    sector_leaders = compute_sector_leaders(date="2026-04-09")
    daily_leaders = compute_daily_leaders(date="2026-04-09", signals=[...], alerts=[...])
    weekly_leaders = compute_weekly_leaders(end_date="2026-04-09", lookback_days=5)
"""

import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
CONFIG_PATH = PROJECT_ROOT / "config" / "leaders_config.json"
OUTPUTS_DIR = PROJECT_ROOT / "outputs" / "paper_trading"

# Cargar config
if CONFIG_PATH.exists():
    _cfg = json.load(open(CONFIG_PATH))
else:
    _cfg = {}

SECTOR_CFG = _cfg.get("sector_leaders", {})
DAILY_CFG = _cfg.get("daily_leaders", {})
WEEKLY_CFG = _cfg.get("weekly_leaders", {})
QUALITY_GATES = _cfg.get("quality_gates", {})


def compute_sector_leaders(date: str) -> pd.DataFrame:
    """
    Calcula líderes sectoriales para una fecha dada.

    Args:
        date: Fecha en formato YYYY-MM-DD

    Returns:
        DataFrame con columnas: date, sector_etf, rank, score, percentile,
                                classification, is_top_tier, rs_weekly, rs_monthly
    """
    from src.utils.sector_rotation import (
        SectorRotationAnalyzer,
        SECTOR_ETFS,
        SECTOR_MAP,
    )

    dt = pd.to_datetime(date)
    end_date = dt.strftime("%Y-%m-%d")
    start_date = (dt - timedelta(days=60)).strftime("%Y-%m-%d")

    lookback_weekly = SECTOR_CFG.get("lookback_weekly", 5)
    lookback_monthly = SECTOR_CFG.get("lookback_monthly", 20)
    top_percentile = SECTOR_CFG.get("top_percentile", 0.40)

    logger.info(f"🔍 Computing sector leaders for {date}...")

    analyzer = SectorRotationAnalyzer(start_date, end_date)

    if not analyzer.load_sector_data():
        logger.warning(f"Failed to load sector data for {date}, returning empty")
        return pd.DataFrame()

    analyzer.calculate_relative_strength(lookback_days=lookback_weekly)

    scores_df = analyzer.calculate_composite_score_vectorized(
        lookback_weekly=lookback_weekly,
        lookback_monthly=lookback_monthly,
    )

    if scores_df.empty:
        logger.warning("No composite scores calculated, returning empty")
        return pd.DataFrame()

    try:
        date_scores = scores_df.loc[dt]
    except KeyError:
        logger.warning(f"Date {date} not in scores, using nearest prior")
        date_scores = scores_df.iloc[-1]

    total_sectors = len(SECTOR_ETFS)
    top_n = max(1, int(total_sectors * top_percentile))

    sorted_scores = date_scores.sort_values(ascending=False)

    results = []
    for rank, (sector_etf, score) in enumerate(sorted_scores.items(), 1):
        if pd.isna(score):
            continue
        percentile = (total_sectors - rank + 1) / total_sectors
        is_top_tier = rank <= top_n

        if rank <= top_n:
            classification = "LEADER"
        elif percentile >= 0.3:
            classification = "STRONG"
        elif percentile >= 0.15:
            classification = "NEUTRAL"
        else:
            classification = "WEAK"

        rs_weekly = (
            analyzer.sector_strength.loc[dt, sector_etf]
            if analyzer.sector_strength is not None
            else None
        )

        results.append(
            {
                "date": date,
                "sector_etf": sector_etf,
                "rank": rank,
                "score": round(score, 2),
                "percentile": round(percentile, 3),
                "classification": classification,
                "is_top_tier": is_top_tier,
                "rs_weekly": round(rs_weekly, 4) if rs_weekly is not None else None,
            }
        )

    df = pd.DataFrame(results)

    out_path = OUTPUTS_DIR / f"sector_leaders_{date}.csv"
    df.to_csv(out_path, index=False)
    logger.info(f"  ✅ Sector leaders saved: {out_path} ({len(df)} sectors)")

    top_sectors = df[df["is_top_tier"]]["sector_etf"].tolist()
    logger.info(f"  📊 Top sectors ({len(top_sectors)}): {top_sectors}")

    return df


def compute_daily_leaders(
    date: str,
    signals: Optional[List[Dict]] = None,
    alerts: Optional[List[Dict]] = None,
    sector_leaders: Optional[pd.DataFrame] = None,
) -> pd.DataFrame:
    """
    Calcula líderes diarios combinando señales + alertas + fortaleza sectorial.

    Args:
        date: Fecha en formato YYYY-MM-DD
        signals: Lista de señales del scanner (de pre_report['top_signals'])
        alerts: Lista de candidatos cercanos (de watchlist_alerts)
        sector_leaders: DataFrame de compute_sector_leaders()

    Returns:
        DataFrame con columnas: ticker, combo, in_signals, n_blockers,
                                proximity_score, rs_pct, sector_etf, sector_rank,
                                daily_leader_score, reason
    """
    from src.utils.sector_rotation import SECTOR_MAP

    signals = signals or []
    alerts = alerts or []

    weights = DAILY_CFG.get("weights", {})
    w_entry = weights.get("entry_score", 0.40)
    w_sector = weights.get("sector_strength", 0.25)
    w_rs = weights.get("rs_pct", 0.20)
    w_prox = weights.get("proximity_bonus", 0.15)
    top_n = DAILY_CFG.get("top_n", 25)
    min_prox = DAILY_CFG.get("min_proximity_for_alert", 30.0)

    rs_quality_check = QUALITY_GATES.get("rs_quality_check", True)
    rs_std_min = QUALITY_GATES.get("rs_std_min_threshold", 15.0)

    logger.info(f"🔍 Computing daily leaders for {date}...")

    if sector_leaders is None:
        sector_path = OUTPUTS_DIR / f"sector_leaders_{date}.csv"
        if sector_path.exists():
            sector_leaders = pd.read_csv(sector_path)
        else:
            logger.warning("Sector leaders not found, computing...")
            sector_leaders = compute_sector_leaders(date)

    sector_map = {}
    if sector_leaders is not None and not sector_leaders.empty:
        for _, row in sector_leaders.iterrows():
            sector_map[row["sector_etf"]] = {
                "rank": row["rank"],
                "score": row["score"],
                "is_top_tier": row["is_top_tier"],
            }

    combined = []

    # Procesar signals (ya pasaron todos los filtros)
    for s in signals:
        ticker = s.get("ticker", "")
        sector_etf = SECTOR_MAP.get(ticker)
        sec_info = sector_map.get(
            sector_etf, {"rank": 99, "score": 0, "is_top_tier": False}
        )

        entry_score = s.get("entry_score", 0.5)
        rs_pct = s.get("rs_percentile", 50)

        # Normalizar scores a 0-1
        norm_entry = min(entry_score, 1.0)
        norm_rs = rs_pct / 100.0
        sector_score = (
            1.0 - (sec_info["rank"] - 1) / 11 if sec_info["rank"] <= 11 else 0
        )

        daily_score = (
            w_entry * norm_entry
            + w_sector * sector_score
            + w_rs * norm_rs
            + w_prox * 0  # signals ya pasaron
        )

        combined.append(
            {
                "ticker": ticker,
                "combo": s.get("combo", "unknown"),
                "in_signals": True,
                "n_blockers": 0,
                "proximity_score": 0.0,
                "rs_pct": rs_pct,
                "sector_etf": sector_etf,
                "sector_rank": sec_info["rank"],
                "sector_is_top_tier": sec_info["is_top_tier"],
                "entry_score": entry_score,
                "daily_leader_score": round(daily_score, 4),
                "reason": f"SIGNAL|rank={sec_info['rank']}",
            }
        )

    # Procesar alerts (no pasaron, pero están cerca)
    rs_values = [a.get("rs_pct", 50) for a in alerts]
    rs_std = np.std(rs_values) if len(rs_values) > 1 else 0
    rs_quality_low = rs_quality_check and rs_std < rs_std_min

    if rs_quality_low:
        logger.warning(
            f"  ⚠️ RS quality LOW (std={rs_std:.1f} < {rs_std_min}), reducing RS weight"
        )
        w_rs_adj = w_rs * 0.5
    else:
        w_rs_adj = w_rs

    for a in alerts:
        ticker = a.get("ticker", "")
        prox = a.get("proximity_score", 999)

        if prox > min_prox:
            continue

        sector_etf = SECTOR_MAP.get(ticker)
        sec_info = sector_map.get(
            sector_etf, {"rank": 99, "score": 0, "is_top_tier": False}
        )

        rs_pct = a.get("rs_pct", 50)
        n_block = a.get("n_blockers", 99)

        # Proximity bonus: más cerca = mayor bonus
        prox_bonus = max(0, 1.0 - prox / 50.0)

        norm_rs = rs_pct / 100.0
        sector_score = (
            1.0 - (sec_info["rank"] - 1) / 11 if sec_info["rank"] <= 11 else 0
        )

        daily_score = (
            w_entry * 0.3  # signals no pasaron filtros completos
            + w_sector * sector_score
            + w_rs_adj * norm_rs
            + w_prox * prox_bonus
        )

        blockers = a.get("blockers", "")

        combined.append(
            {
                "ticker": ticker,
                "combo": "",
                "in_signals": False,
                "n_blockers": n_block,
                "proximity_score": round(prox, 2),
                "rs_pct": rs_pct,
                "sector_etf": sector_etf,
                "sector_rank": sec_info["rank"],
                "sector_is_top_tier": sec_info["is_top_tier"],
                "entry_score": 0.0,
                "daily_leader_score": round(daily_score, 4),
                "reason": f"ALERT|prox={prox:.1f}|blks={n_block}|{blockers[:30]}",
            }
        )

    if not combined:
        logger.warning("  ℹ️ No combined candidates for daily leaders")
        return pd.DataFrame()

    df = pd.DataFrame(combined)
    df = df.sort_values("daily_leader_score", ascending=False).head(top_n)

    out_path = OUTPUTS_DIR / f"daily_leaders_{date}.csv"
    df.to_csv(out_path, index=False)
    logger.info(f"  ✅ Daily leaders saved: {out_path} ({len(df)} tickers)")

    top_5 = df.head(5)
    for _, row in top_5.iterrows():
        logger.info(
            f"    {row['ticker']:<8} score={row['daily_leader_score']:.3f} "
            f"sector={row['sector_etf'] or '?'} rank={row['sector_rank']} "
            f"{row['reason'][:40]}"
        )

    return df


def compute_weekly_leaders(
    end_date: str,
    lookback_days: int = 5,
    include_current: bool = True,
) -> pd.DataFrame:
    """
    Calcula líderes semanales basándose en los últimos N días de daily_leaders.

    Args:
        end_date: Fecha final (YYYY-MM-DD), generalmente hoy
        lookback_days: Días hacia atrás a considerar (default 5)
        include_current: Incluir el día actual en el cálculo

    Returns:
        DataFrame con columnas: ticker, appearances, avg_daily_score,
                                best_rank, sector_consistency, weekly_leader_score,
                                sectors_seen, first_seen, last_seen
    """
    lookback = WEEKLY_CFG.get("lookback_days", lookback_days)
    min_app = WEEKLY_CFG.get("min_appearances", 2)
    weights = WEEKLY_CFG.get("weights", {})

    w_app = weights.get("appearances", 0.35)
    w_avg = weights.get("avg_score", 0.30)
    w_rank = weights.get("best_rank", 0.20)
    w_sector = weights.get("sector_persistence", 0.15)

    logger.info(f"🔍 Computing weekly leaders (lookback={lookback} days)...")

    dt = pd.to_datetime(end_date)

    daily_files = []
    for i in range(lookback):
        check_date = dt - timedelta(days=i)
        date_str = check_date.strftime("%Y-%m-%d")
        f = OUTPUTS_DIR / f"daily_leaders_{date_str}.csv"
        if f.exists():
            daily_files.append((date_str, f))

    if not daily_files:
        logger.warning(f"  ⚠️ No daily leader files found for last {lookback} days")
        return pd.DataFrame()

    logger.info(f"  📂 Found {len(daily_files)} daily leader files")

    all_daily = []
    for date_str, f in daily_files:
        df = pd.read_csv(f)
        df["source_date"] = date_str
        all_daily.append(df)

    combined = pd.concat(all_daily, ignore_index=True)

    if combined.empty:
        return pd.DataFrame()

    ticker_stats = {}

    for ticker, grp in combined.groupby("ticker"):
        appearances = len(grp)

        if appearances < min_app:
            continue

        avg_score = grp["daily_leader_score"].mean()
        best_rank = grp["daily_leader_score"].rank(ascending=False).min()
        best_rank = int(best_rank)

        sectors = grp["sector_etf"].dropna().unique().tolist()
        top_tier_count = (
            grp["sector_is_top_tier"].sum()
            if "sector_is_top_tier" in grp.columns
            else 0
        )

        sector_persistence = top_tier_count / appearances if appearances > 0 else 0

        dates = grp["source_date"].tolist()
        first_seen = min(dates)
        last_seen = max(dates)

        weekly_score = (
            w_app * (appearances / lookback)
            + w_avg * min(avg_score, 1.0)
            + w_rank * (1.0 - (best_rank - 1) / 25)
            + w_sector * sector_persistence
        )

        ticker_stats[ticker] = {
            "ticker": ticker,
            "appearances": appearances,
            "avg_daily_score": round(avg_score, 4),
            "best_rank": best_rank,
            "sector_consistency": round(sector_persistence, 3),
            "weekly_leader_score": round(weekly_score, 4),
            "sectors_seen": ",".join(sectors[:3]),
            "first_seen": first_seen,
            "last_seen": last_seen,
        }

    if not ticker_stats:
        logger.warning("  ℹ️ No tickers met minimum appearances threshold")
        return pd.DataFrame()

    df = pd.DataFrame(list(ticker_stats.values()))
    df = df.sort_values("weekly_leader_score", ascending=False)

    out_path = OUTPUTS_DIR / f"weekly_leaders_{end_date}.csv"
    df.to_csv(out_path, index=False)
    logger.info(f"  ✅ Weekly leaders saved: {out_path} ({len(df)} tickers)")

    top_5 = df.head(5)
    for _, row in top_5.iterrows():
        logger.info(
            f"    {row['ticker']:<8} score={row['weekly_leader_score']:.3f} "
            f"apps={row['appearances']}/{lookback} best_rank={row['best_rank']} "
            f"sectors={row['sectors_seen'][:20]}"
        )

    return df


def run_full_leaders_pipeline(
    date: str, lookback_days: int = 5
) -> Dict[str, pd.DataFrame]:
    """
    Ejecuta el pipeline completo de leaders para un día.

    Args:
        date: Fecha objetivo (YYYY-MM-DD)
        lookback_days: Días para weekly

    Returns:
        Dict con 'sector', 'daily', 'weekly' DataFrames
    """
    logger.info("=" * 60)
    logger.info("LEADERS PIPELINE")
    logger.info("=" * 60)

    sector_df = compute_sector_leaders(date)

    pre_report_path = OUTPUTS_DIR / f"pre_report_{date}.json"
    signals = []
    alerts = []

    if pre_report_path.exists():
        pre_data = json.load(open(pre_report_path))
        signals = pre_data.get("top_signals", [])
        alerts_data = pre_data.get("alerts", {})
        alerts = alerts_data.get("top_near_threshold", [])

    alerts_path = OUTPUTS_DIR / f"watchlist_alerts_{date}.csv"
    if alerts_path.exists() and not alerts:
        alerts_df = pd.read_csv(alerts_path)
        alerts = alerts_df.to_dict("records")

    daily_df = compute_daily_leaders(date, signals, alerts, sector_df)

    weekly_df = compute_weekly_leaders(date, lookback_days)

    manifest = {
        "generated_at": datetime.now().isoformat(),
        "date": date,
        "lookback_days": lookback_days,
        "sector_count": len(sector_df) if not sector_df.empty else 0,
        "daily_count": len(daily_df) if not daily_df.empty else 0,
        "weekly_count": len(weekly_df) if not weekly_df.empty else 0,
    }

    manifest_path = OUTPUTS_DIR / f"leaders_manifest_{date}.json"
    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2)
    logger.info(f"  ✅ Manifest saved: {manifest_path}")

    return {
        "sector": sector_df,
        "daily": daily_df,
        "weekly": weekly_df,
    }


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Leaders Engine CLI")
    parser.add_argument("--date", type=str, default=None, help="Date (YYYY-MM-DD)")
    parser.add_argument("--lookback", type=int, default=5, help="Weekly lookback days")
    parser.add_argument(
        "--phase", type=str, choices=["sector", "daily", "weekly", "all"], default="all"
    )
    args = parser.parse_args()

    date = args.date or datetime.now().strftime("%Y-%m-%d")

    if args.phase in ["sector", "all"]:
        compute_sector_leaders(date)

    if args.phase in ["daily", "all"]:
        pre_path = OUTPUTS_DIR / f"pre_report_{date}.json"
        signals = []
        if pre_path.exists():
            signals = json.load(open(pre_path)).get("top_signals", [])
        alerts_path = OUTPUTS_DIR / f"watchlist_alerts_{date}.csv"
        alerts = []
        if alerts_path.exists():
            alerts = pd.read_csv(alerts_path).to_dict("records")

        sector_path = OUTPUTS_DIR / f"sector_leaders_{date}.csv"
        sector_df = pd.read_csv(sector_path) if sector_path.exists() else None

        compute_daily_leaders(date, signals, alerts, sector_df)

    if args.phase in ["weekly", "all"]:
        compute_weekly_leaders(date, args.lookback)
