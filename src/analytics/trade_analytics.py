"""
Trade Analytics - RS, Entry Score, Position Sizing Analysis
============================================================

Este módulo proporciona análisis estadístico detallado de trades para
identificar correlaciones entre:
- Entry Quality Score vs PnL
- RS Percentile vs Win Rate
- Position Sizing vs Outcome
- Context metrics (RVOL, ADR) vs Trade Quality

Usado por:
  - Dashboard de Streamlit (app.py)
  - PDF Tearsheet (quantstats_analyzer.py)
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple
import logging

logger = logging.getLogger(__name__)


def analyze_entry_score_correlation(trades_df: pd.DataFrame) -> Dict:
    """
    Analiza la correlación entre Entry Quality Score y resultados de trades.

    Args:
        trades_df: DataFrame con trades (debe tener columnas: entry_score, pnl, r_multiple)

    Returns:
        Dict con estadísticas de correlación
    """
    if trades_df.empty or "entry_score" not in trades_df.columns:
        return {}

    df = trades_df.copy()

    # Convertir entry_score a numérico
    df["entry_score"] = pd.to_numeric(df["entry_score"], errors="coerce")
    df["r_multiple"] = pd.to_numeric(df.get("r_multiple", 0), errors="coerce")
    df["pnl"] = pd.to_numeric(df["pnl"], errors="coerce")

    # Remover NaN
    df_clean = df.dropna(subset=["entry_score", "pnl"])

    if len(df_clean) < 10:
        return {"error": "Insufficient trades for correlation analysis (min 10)"}

    results = {}

    # 1. Correlación Entry Score vs PnL
    corr_score_pnl = df_clean["entry_score"].corr(df_clean["pnl"])
    results["corr_entry_score_vs_pnl"] = round(corr_score_pnl, 4)

    # 2. Correlación Entry Score vs R-Multiple
    if "r_multiple" in df_clean.columns:
        corr_score_r = df_clean["entry_score"].corr(df_clean["r_multiple"])
        results["corr_entry_score_vs_r"] = round(corr_score_r, 4)

    # 3. Win Rate por cuartil de Entry Score
    df_clean["score_quartile"] = pd.qcut(
        df_clean["entry_score"], q=4, labels=["Q1", "Q2", "Q3", "Q4"], duplicates="drop"
    )

    win_rate_by_quartile = {}
    for quartile in ["Q1", "Q2", "Q3", "Q4"]:
        q_df = df_clean[df_clean["score_quartile"] == quartile]
        if len(q_df) > 0:
            wins = (q_df["pnl"] > 0).sum()
            win_rate_by_quartile[quartile] = {
                "win_rate": round(wins / len(q_df) * 100, 1),
                "count": len(q_df),
                "avg_pnl": round(q_df["pnl"].mean(), 2),
                "avg_r": round(q_df.get("r_multiple", 0).mean(), 2)
                if "r_multiple" in q_df.columns
                else None,
            }

    results["win_rate_by_score_quartile"] = win_rate_by_quartile

    # 4. Estadísticas por nivel de Entry Score
    high_score = df_clean[df_clean["entry_score"] >= 0.7]
    med_score = df_clean[
        (df_clean["entry_score"] >= 0.4) & (df_clean["entry_score"] < 0.7)
    ]
    low_score = df_clean[df_clean["entry_score"] < 0.4]

    results["high_score_trades"] = {
        "count": len(high_score),
        "win_rate": round((high_score["pnl"] > 0).sum() / len(high_score) * 100, 1)
        if len(high_score) > 0
        else 0,
        "avg_pnl": round(high_score["pnl"].mean(), 2) if len(high_score) > 0 else 0,
        "total_pnl": round(high_score["pnl"].sum(), 2) if len(high_score) > 0 else 0,
    }

    results["med_score_trades"] = {
        "count": len(med_score),
        "win_rate": round((med_score["pnl"] > 0).sum() / len(med_score) * 100, 1)
        if len(med_score) > 0
        else 0,
        "avg_pnl": round(med_score["pnl"].mean(), 2) if len(med_score) > 0 else 0,
        "total_pnl": round(med_score["pnl"].sum(), 2) if len(med_score) > 0 else 0,
    }

    results["low_score_trades"] = {
        "count": len(low_score),
        "win_rate": round((low_score["pnl"] > 0).sum() / len(low_score) * 100, 1)
        if len(low_score) > 0
        else 0,
        "avg_pnl": round(low_score["pnl"].mean(), 2) if len(low_score) > 0 else 0,
        "total_pnl": round(low_score["pnl"].sum(), 2) if len(low_score) > 0 else 0,
    }

    # 5. Top Winners Analysis
    top_winners = df_clean.nlargest(10, "pnl")
    results["top_10_winners"] = {
        "avg_entry_score": round(top_winners["entry_score"].mean(), 3),
        "avg_r_multiple": round(top_winners.get("r_multiple", 0).mean(), 2)
        if "r_multiple" in top_winners.columns
        else None,
        "total_pnl": round(top_winners["pnl"].sum(), 2),
    }

    # 6. Bottom Losers Analysis
    top_losers = df_clean.nsmallest(10, "pnl")
    results["top_10_losers"] = {
        "avg_entry_score": round(top_losers["entry_score"].mean(), 3),
        "avg_r_multiple": round(top_losers.get("r_multiple", 0).mean(), 2)
        if "r_multiple" in top_losers.columns
        else None,
        "total_loss": round(top_losers["pnl"].sum(), 2),
    }

    return results


def analyze_rs_percentile_performance(trades_df: pd.DataFrame) -> Dict:
    """
    Analiza la performance de trades basado en RS Percentile.

    Args:
        trades_df: DataFrame con trades (debe tener columna rs_percentile)

    Returns:
        Dict con análisis de RS
    """
    if trades_df.empty or "rs_percentile" not in trades_df.columns:
        return {}

    df = trades_df.copy()
    df["rs_percentile"] = pd.to_numeric(df["rs_percentile"], errors="coerce")
    df["pnl"] = pd.to_numeric(df["pnl"], errors="coerce")

    df_clean = df.dropna(subset=["rs_percentile", "pnl"])

    if len(df_clean) < 10:
        return {"error": "Insufficient trades with RS data"}

    results = {}

    # 1. Correlación RS vs PnL
    corr_rs_pnl = df_clean["rs_percentile"].corr(df_clean["pnl"])
    results["corr_rs_vs_pnl"] = round(corr_rs_pnl, 4)

    # 2. Win Rate por cuartil de RS
    df_clean["rs_quartile"] = pd.qcut(
        df_clean["rs_percentile"],
        q=4,
        labels=["Q1", "Q2", "Q3", "Q4"],
        duplicates="drop",
    )

    win_rate_by_rs = {}
    for quartile in ["Q1", "Q2", "Q3", "Q4"]:
        q_df = df_clean[df_clean["rs_quartile"] == quartile]
        if len(q_df) > 0:
            wins = (q_df["pnl"] > 0).sum()
            win_rate_by_rs[quartile] = {
                "win_rate": round(wins / len(q_df) * 100, 1),
                "count": len(q_df),
                "avg_pnl": round(q_df["pnl"].mean(), 2),
                "rs_range": f"{q_df['rs_percentile'].min():.0f}-{q_df['rs_percentile'].max():.0f}",
            }

    results["win_rate_by_rs_quartile"] = win_rate_by_rs

    # 3. Performance por nivel de RS
    high_rs = df_clean[df_clean["rs_percentile"] >= 80]
    med_rs = df_clean[
        (df_clean["rs_percentile"] >= 50) & (df_clean["rs_percentile"] < 80)
    ]
    low_rs = df_clean[df_clean["rs_percentile"] < 50]

    results["high_rs_trades"] = {
        "label": "RS≥80 (Top 20%)",
        "count": len(high_rs),
        "win_rate": round((high_rs["pnl"] > 0).sum() / len(high_rs) * 100, 1)
        if len(high_rs) > 0
        else 0,
        "avg_pnl": round(high_rs["pnl"].mean(), 2) if len(high_rs) > 0 else 0,
        "total_pnl": round(high_rs["pnl"].sum(), 2) if len(high_rs) > 0 else 0,
    }

    results["med_rs_trades"] = {
        "label": "RS 50-80",
        "count": len(med_rs),
        "win_rate": round((med_rs["pnl"] > 0).sum() / len(med_rs) * 100, 1)
        if len(med_rs) > 0
        else 0,
        "avg_pnl": round(med_rs["pnl"].mean(), 2) if len(med_rs) > 0 else 0,
        "total_pnl": round(med_rs["pnl"].sum(), 2) if len(med_rs) > 0 else 0,
    }

    results["low_rs_trades"] = {
        "label": "RS<50 (Bottom 50%)",
        "count": len(low_rs),
        "win_rate": round((low_rs["pnl"] > 0).sum() / len(low_rs) * 100, 1)
        if len(low_rs) > 0
        else 0,
        "avg_pnl": round(low_rs["pnl"].mean(), 2) if len(low_rs) > 0 else 0,
        "total_pnl": round(low_rs["pnl"].sum(), 2) if len(low_rs) > 0 else 0,
    }

    # 4. RS Percentile Distribution
    results["rs_distribution"] = {
        "mean": round(df_clean["rs_percentile"].mean(), 1),
        "median": round(df_clean["rs_percentile"].median(), 1),
        "std": round(df_clean["rs_percentile"].std(), 1),
        "min": round(df_clean["rs_percentile"].min(), 1),
        "max": round(df_clean["rs_percentile"].max(), 1),
    }

    return results


def analyze_position_sizing(trades_df: pd.DataFrame) -> Dict:
    """
    Analiza la relación entre Position Sizing y resultados.

    Args:
        trades_df: DataFrame con trades

    Returns:
        Dict con análisis de position sizing
    """
    if trades_df.empty:
        return {}

    df = trades_df.copy()
    df["pnl"] = pd.to_numeric(df["pnl"], errors="coerce")
    df["initial_risk"] = pd.to_numeric(df.get("initial_risk", 0), errors="coerce")
    df["shares"] = pd.to_numeric(df.get("shares", 0), errors="coerce")

    df_clean = df.dropna(subset=["pnl"])

    if len(df_clean) < 10:
        return {"error": "Insufficient trades"}

    results = {}

    # 1. Risk Distribution
    if "initial_risk" in df_clean.columns and df_clean["initial_risk"].notna().any():
        results["risk_distribution"] = {
            "mean_risk": round(df_clean["initial_risk"].mean(), 2),
            "median_risk": round(df_clean["initial_risk"].median(), 2),
            "std_risk": round(df_clean["initial_risk"].std(), 2),
            "min_risk": round(df_clean["initial_risk"].min(), 2),
            "max_risk": round(df_clean["initial_risk"].max(), 2),
        }

    # 2. R-Multiple Distribution
    if "r_multiple" in df_clean.columns:
        r_clean = df_clean.dropna(subset=["r_multiple"])
        if len(r_clean) > 0:
            results["r_distribution"] = {
                "mean_r": round(r_clean["r_multiple"].mean(), 2),
                "median_r": round(r_clean["r_multiple"].median(), 2),
                "std_r": round(r_clean["r_multiple"].std(), 2),
                "positive_r_pct": round(
                    (r_clean["r_multiple"] > 0).sum() / len(r_clean) * 100, 1
                ),
                "big_wins_pct": round(
                    (r_clean["r_multiple"] >= 2.0).sum() / len(r_clean) * 100, 1
                ),
                "big_losses_pct": round(
                    (r_clean["r_multiple"] <= -1.0).sum() / len(r_clean) * 100, 1
                ),
            }

    # 3. Stop Distance Analysis
    if "stop_distance_pct" in df_clean.columns:
        stop_clean = df_clean.dropna(subset=["stop_distance_pct"])
        if len(stop_clean) > 0:
            results["stop_distance_distribution"] = {
                "mean_stop_pct": round(stop_clean["stop_distance_pct"].mean(), 2),
                "median_stop_pct": round(stop_clean["stop_distance_pct"].median(), 2),
                "tight_stops_pct": round(
                    (stop_clean["stop_distance_pct"] < 3.0).sum()
                    / len(stop_clean)
                    * 100,
                    1,
                ),
                "wide_stops_pct": round(
                    (stop_clean["stop_distance_pct"] > 6.0).sum()
                    / len(stop_clean)
                    * 100,
                    1,
                ),
            }

    # 4. Performance by Stop Distance
    if "stop_distance_pct" in df_clean.columns:
        stop_clean = df_clean.dropna(subset=["stop_distance_pct"])
        if len(stop_clean) >= 10:
            tight = stop_clean[stop_clean["stop_distance_pct"] < 3.0]
            normal = stop_clean[
                (stop_clean["stop_distance_pct"] >= 3.0)
                & (stop_clean["stop_distance_pct"] <= 6.0)
            ]
            wide = stop_clean[stop_clean["stop_distance_pct"] > 6.0]

            results["performance_by_stop"] = {
                "tight_stops": {
                    "count": len(tight),
                    "win_rate": round((tight["pnl"] > 0).sum() / len(tight) * 100, 1)
                    if len(tight) > 0
                    else 0,
                    "avg_r": round(tight.get("r_multiple", 0).mean(), 2)
                    if "r_multiple" in tight.columns and len(tight) > 0
                    else 0,
                },
                "normal_stops": {
                    "count": len(normal),
                    "win_rate": round((normal["pnl"] > 0).sum() / len(normal) * 100, 1)
                    if len(normal) > 0
                    else 0,
                    "avg_r": round(normal.get("r_multiple", 0).mean(), 2)
                    if "r_multiple" in normal.columns and len(normal) > 0
                    else 0,
                },
                "wide_stops": {
                    "count": len(wide),
                    "win_rate": round((wide["pnl"] > 0).sum() / len(wide) * 100, 1)
                    if len(wide) > 0
                    else 0,
                    "avg_r": round(wide.get("r_multiple", 0).mean(), 2)
                    if "r_multiple" in wide.columns and len(wide) > 0
                    else 0,
                },
            }

    return results


def analyze_context_correlations(trades_df: pd.DataFrame) -> Dict:
    """
    Analiza correlaciones entre contexto de mercado y resultados.

    Args:
        trades_df: DataFrame con trades

    Returns:
        Dict con análisis de contexto
    """
    if trades_df.empty:
        return {}

    df = trades_df.copy()
    numeric_cols = ["pnl", "context_rvol", "context_adr", "dist_sma20_pct"]

    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    df_clean = df.dropna(subset=["pnl"])

    if len(df_clean) < 10:
        return {"error": "Insufficient trades"}

    results = {}

    # 1. RVOL vs PnL Correlation
    if "context_rvol" in df_clean.columns:
        rvol_clean = df_clean.dropna(subset=["context_rvol"])
        if len(rvol_clean) > 10:
            results["rvol_correlation"] = {
                "corr_vs_pnl": round(
                    rvol_clean["context_rvol"].corr(rvol_clean["pnl"]), 4
                ),
                "mean_rvol": round(rvol_clean["context_rvol"].mean(), 2),
                "median_rvol": round(rvol_clean["context_rvol"].median(), 2),
            }

            # Win Rate por RVOL
            low_rvol = rvol_clean[rvol_clean["context_rvol"] < 1.5]
            med_rvol = rvol_clean[
                (rvol_clean["context_rvol"] >= 1.5) & (rvol_clean["context_rvol"] < 3.0)
            ]
            high_rvol = rvol_clean[rvol_clean["context_rvol"] >= 3.0]

            results["performance_by_rvol"] = {
                "low_rvol": {
                    "count": len(low_rvol),
                    "win_rate": round(
                        (low_rvol["pnl"] > 0).sum() / len(low_rvol) * 100, 1
                    )
                    if len(low_rvol) > 0
                    else 0,
                    "avg_pnl": round(low_rvol["pnl"].mean(), 2)
                    if len(low_rvol) > 0
                    else 0,
                },
                "med_rvol": {
                    "count": len(med_rvol),
                    "win_rate": round(
                        (med_rvol["pnl"] > 0).sum() / len(med_rvol) * 100, 1
                    )
                    if len(med_rvol) > 0
                    else 0,
                    "avg_pnl": round(med_rvol["pnl"].mean(), 2)
                    if len(med_rvol) > 0
                    else 0,
                },
                "high_rvol": {
                    "count": len(high_rvol),
                    "win_rate": round(
                        (high_rvol["pnl"] > 0).sum() / len(high_rvol) * 100, 1
                    )
                    if len(high_rvol) > 0
                    else 0,
                    "avg_pnl": round(high_rvol["pnl"].mean(), 2)
                    if len(high_rvol) > 0
                    else 0,
                },
            }

    # 2. ADR vs PnL Correlation
    if "context_adr" in df_clean.columns:
        adr_clean = df_clean.dropna(subset=["context_adr"])
        if len(adr_clean) > 10:
            results["adr_correlation"] = {
                "corr_vs_pnl": round(
                    adr_clean["context_adr"].corr(adr_clean["pnl"]), 4
                ),
                "mean_adr": round(adr_clean["context_adr"].mean(), 2),
                "median_adr": round(adr_clean["context_adr"].median(), 2),
            }

    # 3. Distance from SMA20 vs PnL
    if "dist_sma20_pct" in df_clean.columns:
        dist_clean = df_clean.dropna(subset=["dist_sma20_pct"])
        if len(dist_clean) > 10:
            results["dist_sma20_correlation"] = {
                "corr_vs_pnl": round(
                    dist_clean["dist_sma20_pct"].corr(dist_clean["pnl"]), 4
                ),
                "mean_dist": round(dist_clean["dist_sma20_pct"].mean(), 2),
                "median_dist": round(dist_clean["dist_sma20_pct"].median(), 2),
            }

            # Performance por distancia
            near_sma = dist_clean[dist_clean["dist_sma20_pct"] < 5.0]
            far_sma = dist_clean[dist_clean["dist_sma20_pct"] >= 5.0]

            results["performance_by_dist_sma"] = {
                "near_sma": {
                    "count": len(near_sma),
                    "win_rate": round(
                        (near_sma["pnl"] > 0).sum() / len(near_sma) * 100, 1
                    )
                    if len(near_sma) > 0
                    else 0,
                    "avg_pnl": round(near_sma["pnl"].mean(), 2)
                    if len(near_sma) > 0
                    else 0,
                },
                "far_sma": {
                    "count": len(far_sma),
                    "win_rate": round(
                        (far_sma["pnl"] > 0).sum() / len(far_sma) * 100, 1
                    )
                    if len(far_sma) > 0
                    else 0,
                    "avg_pnl": round(far_sma["pnl"].mean(), 2)
                    if len(far_sma) > 0
                    else 0,
                },
            }

    return results


def generate_full_trade_analysis(trades_df: pd.DataFrame) -> Dict:
    """
    Genera análisis completo de trades para dashboard y PDF.

    Args:
        trades_df: DataFrame con todos los trades

    Returns:
        Dict con análisis completo
    """
    logger.info("📊 Generando análisis completo de trades...")

    analysis = {
        "entry_score": analyze_entry_score_correlation(trades_df),
        "rs_percentile": analyze_rs_percentile_performance(trades_df),
        "position_sizing": analyze_position_sizing(trades_df),
        "context": analyze_context_correlations(trades_df),
        "pattern_performance": analyze_pattern_performance(trades_df),
        "generated_at": pd.Timestamp.now().isoformat(),
        "total_trades": len(trades_df),
    }

    # Summary Insights
    insights = []

    # Entry Score Insights
    if "corr_entry_score_vs_pnl" in analysis.get("entry_score", {}):
        corr = analysis["entry_score"]["corr_entry_score_vs_pnl"]
        if corr > 0.2:
            insights.append(
                f"✅ Entry Score correlaciona positivamente con PnL (r={corr:.2f})"
            )
        elif corr < -0.1:
            insights.append(
                f"⚠️ Entry Score correlaciona negativamente con PnL (r={corr:.2f}) - revisar lógica"
            )

    # RS Insights
    if "corr_rs_vs_pnl" in analysis.get("rs_percentile", {}):
        corr_rs = analysis["rs_percentile"]["corr_rs_vs_pnl"]
        if corr_rs > 0.15:
            insights.append(f"✅ RS Percentile correlaciona con PnL (r={corr_rs:.2f})")

    # Win Rate Comparison
    if "high_score_trades" in analysis.get(
        "entry_score", {}
    ) and "low_score_trades" in analysis.get("entry_score", {}):
        high_wr = analysis["entry_score"]["high_score_trades"].get("win_rate", 0)
        low_wr = analysis["entry_score"]["low_score_trades"].get("win_rate", 0)
        if high_wr > low_wr + 10:
            insights.append(
                f"✅ High Score trades tienen Win Rate {high_wr:.0f}% vs {low_wr:.0f}% Low Score"
            )

    analysis["insights"] = insights

    logger.info(f"   ✅ Análisis completado: {len(insights)} insights generados")

    return analysis


def analyze_pattern_performance(trades_df: pd.DataFrame) -> Dict:
    """
    Analiza performance por tipo de patrón detectado.

    Args:
        trades_df: DataFrame con trades (debe tener columnas:
                   pattern_type, pattern_confidence, pattern_bonus, pnl, r_multiple)

    Returns:
        Dict con estadísticas por tipo de patrón
    """
    if trades_df.empty:
        return {"error": "Empty trades_df"}

    # Check for pattern columns
    has_pattern = (
        "pattern_type" in trades_df.columns
        and "pattern_confidence" in trades_df.columns
    )
    if not has_pattern:
        return {"error": "Pattern columns not found in trades_df"}

    df = trades_df.copy()

    # Convert to numeric
    df["pattern_confidence"] = pd.to_numeric(
        df["pattern_confidence"], errors="coerce"
    ).fillna(0)
    df["pnl"] = pd.to_numeric(df["pnl"], errors="coerce").fillna(0)
    df["r_multiple"] = pd.to_numeric(
        df.get("r_multiple", df["pnl"] / 100), errors="coerce"
    ).fillna(0)

    # Fill missing pattern_type
    df["pattern_type"] = df["pattern_type"].fillna("NONE")

    result = {
        "summary": {},
        "by_pattern": {},
        "pattern_vs_none": {},
        "confidence_buckets": {},
    }

    # Summary stats
    total_trades = len(df)
    trades_with_pattern = len(df[df["pattern_confidence"] > 0])
    trades_no_pattern = len(df[df["pattern_confidence"] == 0])

    result["summary"] = {
        "total_trades": total_trades,
        "trades_with_pattern": trades_with_pattern,
        "trades_without_pattern": trades_no_pattern,
        "pattern_detection_rate": trades_with_pattern / total_trades
        if total_trades > 0
        else 0,
    }

    # Performance by pattern type
    pattern_types = df["pattern_type"].unique()

    for ptype in pattern_types:
        pattern_trades = df[df["pattern_type"] == ptype]
        if len(pattern_trades) == 0:
            continue

        winners = pattern_trades[pattern_trades["pnl"] > 0]
        losers = pattern_trades[pattern_trades["pnl"] <= 0]

        result["by_pattern"][ptype] = {
            "count": len(pattern_trades),
            "win_rate": len(winners) / len(pattern_trades)
            if len(pattern_trades) > 0
            else 0,
            "avg_pnl": pattern_trades["pnl"].mean(),
            "avg_r": pattern_trades["r_multiple"].mean(),
            "median_r": pattern_trades["r_multiple"].median(),
            "total_pnl": pattern_trades["pnl"].sum(),
            "avg_confidence": pattern_trades["pattern_confidence"].mean(),
        }

    # Pattern vs No Pattern comparison
    with_pattern = df[df["pattern_confidence"] > 0]
    without_pattern = df[df["pattern_confidence"] == 0]

    if len(with_pattern) > 0:
        result["pattern_vs_none"]["with_pattern"] = {
            "count": len(with_pattern),
            "win_rate": len(with_pattern[with_pattern["pnl"] > 0]) / len(with_pattern),
            "avg_r": with_pattern["r_multiple"].mean(),
            "avg_pnl": with_pattern["pnl"].mean(),
        }

    if len(without_pattern) > 0:
        result["pattern_vs_none"]["no_pattern"] = {
            "count": len(without_pattern),
            "win_rate": len(without_pattern[without_pattern["pnl"] > 0])
            / len(without_pattern),
            "avg_r": without_pattern["r_multiple"].mean(),
            "avg_pnl": without_pattern["pnl"].mean(),
        }

    # Confidence buckets analysis
    df["conf_bucket"] = pd.cut(
        df["pattern_confidence"],
        bins=[-0.01, 0.3, 0.5, 0.7, 1.01],
        labels=["<0.3", "0.3-0.5", "0.5-0.7", "0.7+"],
    )

    for bucket in df["conf_bucket"].unique():
        if pd.isna(bucket):
            continue
        bucket_trades = df[df["conf_bucket"] == bucket]
        if len(bucket_trades) == 0:
            continue

        winners = bucket_trades[bucket_trades["pnl"] > 0]
        result["confidence_buckets"][str(bucket)] = {
            "count": len(bucket_trades),
            "win_rate": len(winners) / len(bucket_trades),
            "avg_r": bucket_trades["r_multiple"].mean(),
            "avg_pnl": bucket_trades["pnl"].mean(),
        }

    # Pattern bonus effectiveness
    if "pattern_bonus" in df.columns:
        df["pattern_bonus"] = pd.to_numeric(
            df["pattern_bonus"], errors="coerce"
        ).fillna(0)

        with_bonus = df[df["pattern_bonus"] > 0]
        without_bonus = df[df["pattern_bonus"] == 0]

        result["bonus_effectiveness"] = {
            "trades_with_bonus": len(with_bonus),
            "bonus_avg_r": with_bonus["r_multiple"].mean()
            if len(with_bonus) > 0
            else 0,
            "trades_without_bonus": len(without_bonus),
            "no_bonus_avg_r": without_bonus["r_multiple"].mean()
            if len(without_bonus) > 0
            else 0,
            "improvement": (
                with_bonus["r_multiple"].mean() - without_bonus["r_multiple"].mean()
            )
            if len(with_bonus) > 0 and len(without_bonus) > 0
            else 0,
        }

    logger.info(
        f"   ✅ Pattern analysis: {trades_with_pattern}/{total_trades} trades with pattern"
    )

    return result
