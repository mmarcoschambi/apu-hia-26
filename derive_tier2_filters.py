#!/usr/bin/env python3
"""
DERIVAR TIER 2 (Filtros) - Análisis Estadístico Winners vs Losers
=================================================================

Este script analiza la base histórica de trades para derivar estadísticamente
los umbrales óptimos de los filtros (Tier 2).

Filtros a derivar:
- min_rvol: Umbral mínimo de RVOL
- min_adr: Umbral mínimo de ADR
- max_dist_sma20: Distancia máxima al SMA20
- min_consolidation_days: Días mínimos de consolidación

Metodología:
1. Cargar trades históricos (supports both complete and partial exit formats)
2. Group partial exits into complete trades if needed
3. Separar en Winners (PnL > 0) y Losers (PnL <= 0)
4. Calcular estadísticas para cada grupo
5. Encontrar umbrales óptimos que maximicen separación
6. Exportar configuración de Tier 2

Uso:
    python derive_tier2_filters.py --trades-file outputs/backtests/complete_trades_clean.csv
"""

import argparse
import json
import pandas as pd
import numpy as np
from pathlib import Path
from typing import Dict, Tuple
import warnings

warnings.filterwarnings("ignore")


def load_trades(file_path: str) -> pd.DataFrame:
    """Cargar archivo de trades."""
    df = pd.read_csv(file_path)
    print(f"Loaded {len(df)} rows from {file_path}")
    return df


def group_partial_exits(df: pd.DataFrame) -> pd.DataFrame:
    """
    Group partial exits (TP1, TP2, RUNNER, STOP) into complete trades.
    Each complete trade gets the sum of PnL and the context from the first exit.
    """
    # Detect if this is partial exit format (has exit_phase with TP1/TP2/RUNNER/STOP)
    if "exit_phase" not in df.columns:
        return df

    phases = df["exit_phase"].unique()
    has_partials = any(p in phases for p in ["TP1", "TP2", "RUNNER", "STOP"])
    if not has_partials:
        return df

    # Determine grouping columns
    symbol_col = "symbol" if "symbol" in df.columns else "ticker"
    entry_col = "entry_date" if "entry_date" in df.columns else "Entry Timestamp"

    print(f"\nGrouping {len(df)} partial exits into complete trades...")

    # Group by symbol + entry_date
    grouped = (
        df.groupby([symbol_col, entry_col])
        .agg(
            total_pnl=("pnl", "sum"),
            n_exits=("exit_phase", "count"),
            exit_phases=("exit_phase", lambda x: ",".join(sorted(x))),
            # Context: take from first row (same for all partials of same trade)
            context_rvol=("context_rvol", "first")
            if "context_rvol" in df.columns
            else ("pnl", "count"),
            context_adr=("context_adr", "first")
            if "context_adr" in df.columns
            else ("pnl", "count"),
            dist_sma20_pct=("dist_sma20_pct", "first")
            if "dist_sma20_pct" in df.columns
            else ("pnl", "count"),
            consolidation_days=("consolidation_days", "first")
            if "consolidation_days" in df.columns
            else ("pnl", "count"),
        )
        .reset_index()
    )

    # If context columns were not in original, drop the placeholder counts
    for col in ["context_rvol", "context_adr", "dist_sma20_pct", "consolidation_days"]:
        if col not in df.columns:
            if col in grouped.columns:
                grouped.drop(columns=[col], inplace=True)

    grouped.rename(
        columns={symbol_col: "symbol", entry_col: "entry_date"}, inplace=True
    )

    print(f"  -> {len(grouped)} complete trades")
    return grouped


def calculate_dist_sma20(df: pd.DataFrame) -> pd.DataFrame:
    """Calcular distancia al SMA20 si no existe."""
    if "dist_sma20" in df.columns:
        return df
    elif "dist_sma20_pct" in df.columns:
        df["dist_sma20"] = df["dist_sma20_pct"]
    elif "context_price" in df.columns and "context_sma20" in df.columns:
        df["dist_sma20"] = (
            (df["context_price"] - df["context_sma20"]) / df["context_sma20"] * 100
        )
    else:
        print("WARNING: Cannot calculate dist_sma20 - missing columns")
        df["dist_sma20"] = np.nan
    return df


def get_consolidation_days(df: pd.DataFrame) -> pd.DataFrame:
    """Obtener o estimar días de consolidación."""
    if "consolidation_days" in df.columns:
        # Check if all values are the same (placeholder)
        if df["consolidation_days"].nunique() > 1:
            return df

    # If signal_type-based heuristic is available
    if "signal_type" in df.columns:
        mapping = {
            "VCP": 15,
            "BLUE_SKY": 10,
            "BREAKOUT": 8,
            "ATH": 12,
            "VWAP_RECLAIM": 5,
        }
        mapped = df["signal_type"].map(mapping)
        if mapped.notna().any():
            df["consolidation_days"] = mapped.fillna(10)
            return df

    # Default - mark as unavailable
    df["consolidation_days"] = np.nan
    return df


def analyze_winners_losers(df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Separar trades en Winners y Losers."""
    pnl_col = "total_pnl" if "total_pnl" in df.columns else "pnl"
    winners = df[df[pnl_col] > 0].copy()
    losers = df[df[pnl_col] <= 0].copy()

    print(f"\nDISTRIBUTION:")
    print(f"   Winners: {len(winners)} ({len(winners) / len(df) * 100:.1f}%)")
    print(f"   Losers:  {len(losers)} ({len(losers) / len(df) * 100:.1f}%)")

    return winners, losers


def calculate_statistics(series: pd.Series, name: str) -> Dict:
    """Calcular estadísticas descriptivas."""
    series_clean = series.dropna()

    if len(series_clean) == 0:
        return {
            "count": 0,
            "mean": np.nan,
            "median": np.nan,
            "std": np.nan,
            "p25": np.nan,
            "p50": np.nan,
            "p75": np.nan,
            "p10": np.nan,
            "p90": np.nan,
            "min": np.nan,
            "max": np.nan,
        }

    return {
        "count": len(series_clean),
        "mean": series_clean.mean(),
        "median": series_clean.median(),
        "std": series_clean.std(),
        "p25": series_clean.quantile(0.25),
        "p50": series_clean.quantile(0.50),
        "p75": series_clean.quantile(0.75),
        "p10": series_clean.quantile(0.10),
        "p90": series_clean.quantile(0.90),
        "min": series_clean.min(),
        "max": series_clean.max(),
    }


def find_optimal_threshold(
    winners: pd.Series,
    losers: pd.Series,
    metric_name: str,
    higher_is_better: bool = True,
) -> Dict:
    """
    Encontrar umbral óptimo que maximice separación entre winners y losers.
    """
    w_stats = calculate_statistics(winners, "winners")
    l_stats = calculate_statistics(losers, "losers")

    print(f"\n{'=' * 60}")
    print(f"ANALYSIS: {metric_name}")
    print(f"{'=' * 60}")

    print(f"\n  WINNERS (n={w_stats['count']}):")
    print(f"   Mean:   {w_stats['mean']:.2f}")
    print(f"   Median: {w_stats['median']:.2f}")
    print(f"   Std:    {w_stats['std']:.2f}")
    print(f"   P10-P90: [{w_stats['p10']:.2f}, {w_stats['p90']:.2f}]")

    print(f"\n  LOSERS (n={l_stats['count']}):")
    print(f"   Mean:   {l_stats['mean']:.2f}")
    print(f"   Median: {l_stats['median']:.2f}")
    print(f"   Std:    {l_stats['std']:.2f}")
    print(f"   P10-P90: [{l_stats['p10']:.2f}, {l_stats['p90']:.2f}]")

    if higher_is_better:
        threshold_conservative = w_stats["p25"]
        threshold_aggressive = (w_stats["mean"] + l_stats["mean"]) / 2
        threshold_balanced = w_stats["p10"]
    else:
        threshold_conservative = w_stats["p75"]
        threshold_aggressive = (w_stats["mean"] + l_stats["mean"]) / 2
        threshold_balanced = w_stats["p90"]

    print(f"\n  PROPOSED THRESHOLDS:")
    print(f"   Conservative (P25 winners): {threshold_conservative:.2f}")
    print(f"   Balanced (P10/P90 winners): {threshold_balanced:.2f}")
    print(f"   Aggressive (intersection):  {threshold_aggressive:.2f}")

    return {
        "winners": w_stats,
        "losers": l_stats,
        "threshold_conservative": threshold_conservative,
        "threshold_balanced": threshold_balanced,
        "threshold_aggressive": threshold_aggressive,
    }


def calculate_filter_impact(
    df: pd.DataFrame, column: str, threshold: float, direction: str = "above"
) -> Dict:
    """Calcular impacto de aplicar un filtro."""
    pnl_col = "total_pnl" if "total_pnl" in df.columns else "pnl"

    if direction == "above":
        filtered = df[df[column] >= threshold]
    else:
        filtered = df[df[column] <= threshold]

    original_win_rate = (df[pnl_col] > 0).mean() * 100
    filtered_win_rate = (filtered[pnl_col] > 0).mean() * 100 if len(filtered) > 0 else 0

    original_trades = len(df)
    filtered_trades = len(filtered)

    original_pnl = df[pnl_col].sum()
    filtered_pnl = filtered[pnl_col].sum() if len(filtered) > 0 else 0

    return {
        "threshold": threshold,
        "trades_passed": filtered_trades,
        "trades_filtered": original_trades - filtered_trades,
        "filter_rate": (original_trades - filtered_trades) / original_trades * 100,
        "original_win_rate": original_win_rate,
        "filtered_win_rate": filtered_win_rate,
        "win_rate_improvement": filtered_win_rate - original_win_rate,
        "avg_pnl_original": df[pnl_col].mean(),
        "avg_pnl_filtered": filtered[pnl_col].mean() if len(filtered) > 0 else 0,
        "total_pnl_original": original_pnl,
        "total_pnl_filtered": filtered_pnl,
    }


def derive_tier2_config(trades_file: str, output_file: str = None) -> Dict:
    """
    Derivar configuración completa de Tier 2 desde análisis estadístico.
    """
    print("=" * 70)
    print("DERIVING TIER 2 (Filters) - Winners vs Losers Analysis")
    print("=" * 70)

    # Load data
    df = load_trades(trades_file)

    # Group partial exits into complete trades
    df = group_partial_exits(df)

    # Prepare derived columns
    df = calculate_dist_sma20(df)
    df = get_consolidation_days(df)

    # Detect PnL column
    pnl_col = "total_pnl" if "total_pnl" in df.columns else "pnl"

    # Separate winners and losers
    winners, losers = analyze_winners_losers(df)

    # ====================================================================
    # Analysis 1: RVOL
    # ====================================================================
    rvol_analysis = None
    if "context_rvol" in df.columns and df["context_rvol"].notna().sum() > 10:
        print("\n" + "=" * 70)
        print("1. RVOL ANALYSIS")
        print("=" * 70)
        rvol_analysis = find_optimal_threshold(
            winners["context_rvol"],
            losers["context_rvol"],
            "Relative Volume (RVOL)",
            higher_is_better=True,
        )

        print("\n  RVOL Impact Analysis:")
        for threshold in [1.0, 1.25, 1.5, 1.75, 2.0, 2.25, 2.5]:
            impact = calculate_filter_impact(df, "context_rvol", threshold, "above")
            print(
                f"   RVOL >= {threshold}: {impact['trades_passed']}/{len(df)} trades, "
                f"WR: {impact['original_win_rate']:.1f}% -> {impact['filtered_win_rate']:.1f}%, "
                f"PnL: ${impact['total_pnl_filtered']:,.0f}"
            )
    else:
        print("\n  RVOL data not available, skipping")

    # ====================================================================
    # Analysis 2: ADR
    # ====================================================================
    adr_analysis = None
    if "context_adr" in df.columns and df["context_adr"].notna().sum() > 10:
        print("\n" + "=" * 70)
        print("2. ADR ANALYSIS")
        print("=" * 70)
        adr_analysis = find_optimal_threshold(
            winners["context_adr"],
            losers["context_adr"],
            "Average Daily Range (ADR %)",
            higher_is_better=True,
        )

        print("\n  ADR Impact Analysis:")
        for threshold in [1.0, 1.5, 2.0, 2.5, 3.0, 3.5]:
            impact = calculate_filter_impact(df, "context_adr", threshold, "above")
            print(
                f"   ADR >= {threshold}%: {impact['trades_passed']}/{len(df)} trades, "
                f"WR: {impact['original_win_rate']:.1f}% -> {impact['filtered_win_rate']:.1f}%, "
                f"PnL: ${impact['total_pnl_filtered']:,.0f}"
            )
    else:
        print("\n  ADR data not available, skipping")

    # ====================================================================
    # Analysis 3: Distance SMA20
    # ====================================================================
    dist_analysis = None
    if "dist_sma20" in df.columns and df["dist_sma20"].notna().sum() > 10:
        print("\n" + "=" * 70)
        print("3. DISTANCE SMA20 ANALYSIS")
        print("=" * 70)
        dist_analysis = find_optimal_threshold(
            winners["dist_sma20"],
            losers["dist_sma20"],
            "Distance to SMA20 (%)",
            higher_is_better=False,
        )

        print("\n  Dist SMA20 Impact Analysis:")
        for threshold in [3.0, 5.0, 7.5, 10.0, 12.5, 15.0]:
            impact = calculate_filter_impact(df, "dist_sma20", threshold, "below")
            print(
                f"   Dist <= {threshold}%: {impact['trades_passed']}/{len(df)} trades, "
                f"WR: {impact['original_win_rate']:.1f}% -> {impact['filtered_win_rate']:.1f}%, "
                f"PnL: ${impact['total_pnl_filtered']:,.0f}"
            )
    else:
        print("\n  dist_sma20 data not available, skipping")

    # ====================================================================
    # Analysis 4: Consolidation Days
    # ====================================================================
    consol_analysis = None
    if (
        "consolidation_days" in df.columns
        and df["consolidation_days"].notna().sum() > 10
    ):
        if df["consolidation_days"].nunique() > 1:  # Not all same value
            print("\n" + "=" * 70)
            print("4. CONSOLIDATION DAYS ANALYSIS")
            print("=" * 70)
            consol_analysis = find_optimal_threshold(
                winners["consolidation_days"],
                losers["consolidation_days"],
                "Consolidation Days",
                higher_is_better=True,
            )

            print("\n  Consolidation Impact Analysis:")
            for threshold in [5, 8, 10, 12, 15]:
                impact = calculate_filter_impact(
                    df, "consolidation_days", threshold, "above"
                )
                print(
                    f"   Consol >= {threshold}d: {impact['trades_passed']}/{len(df)} trades, "
                    f"WR: {impact['original_win_rate']:.1f}% -> {impact['filtered_win_rate']:.1f}%, "
                    f"PnL: ${impact['total_pnl_filtered']:,.0f}"
                )
    else:
        print("\n  consolidation_days data not available, skipping")

    # ====================================================================
    # FINAL RECOMMENDATION
    # ====================================================================
    print("\n" + "=" * 70)
    print("FINAL RECOMMENDATION - TIER 2 FILTERS")
    print("=" * 70)

    tier2_config = {
        "min_rvol": round(rvol_analysis["threshold_balanced"], 2)
        if rvol_analysis
        else 1.5,
        "min_adr": round(adr_analysis["threshold_balanced"], 1)
        if adr_analysis
        else 2.5,
        "max_dist_sma20": round(dist_analysis["threshold_balanced"], 1)
        if dist_analysis
        else 15.0,
        "min_consolidation_days": int(consol_analysis["threshold_balanced"])
        if consol_analysis
        else 10,
        "min_volume": 200000,
        "min_dollar_volume": 3_000_000,
        "max_consolidation_range": 15.0,
        "require_sector_strength": True,
        "sector_top_percentile": 0.40,
        "require_positive_rs": False,
        "analysis_metadata": {
            "trades_analyzed": len(df),
            "winners": len(winners),
            "losers": len(losers),
            "original_win_rate": (df[pnl_col] > 0).mean() * 100,
        },
    }

    # Add analysis details to metadata
    if rvol_analysis:
        tier2_config["analysis_metadata"]["rvol_winners_avg"] = rvol_analysis[
            "winners"
        ]["mean"]
        tier2_config["analysis_metadata"]["rvol_losers_avg"] = rvol_analysis["losers"][
            "mean"
        ]
    if adr_analysis:
        tier2_config["analysis_metadata"]["adr_winners_avg"] = adr_analysis["winners"][
            "mean"
        ]
        tier2_config["analysis_metadata"]["adr_losers_avg"] = adr_analysis["losers"][
            "mean"
        ]
    if dist_analysis:
        tier2_config["analysis_metadata"]["dist_sma20_winners_avg"] = dist_analysis[
            "winners"
        ]["mean"]
        tier2_config["analysis_metadata"]["dist_sma20_losers_avg"] = dist_analysis[
            "losers"
        ]["mean"]

    print(f"\n  Recommended Tier 2 Parameters:")
    print(f"   min_rvol:              {tier2_config['min_rvol']}x")
    print(f"   min_adr:               {tier2_config['min_adr']}%")
    print(f"   max_dist_sma20:        {tier2_config['max_dist_sma20']}%")
    print(f"   min_consolidation_days: {tier2_config['min_consolidation_days']}d")
    print(f"   min_dollar_volume:     ${tier2_config['min_dollar_volume'] / 1e6:.1f}M")

    # Save configuration
    if output_file is None:
        output_file = "config/tier2_filters_derived.json"

    output_path = Path(output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w") as f:
        json.dump(tier2_config, f, indent=2)

    print(f"\n  Saved to: {output_path}")

    return tier2_config


def main():
    parser = argparse.ArgumentParser(
        description="Derive Tier 2 Filters statistically from Winners vs Losers"
    )
    parser.add_argument(
        "--trades-file",
        type=str,
        default="outputs/backtests/complete_trades_clean.csv",
        help="CSV file with trade history (supports partial exits format)",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="config/tier2_filters_derived.json",
        help="Output file for Tier 2 configuration",
    )

    args = parser.parse_args()

    derive_tier2_config(args.trades_file, args.output)

    print("\n" + "=" * 70)
    print("Analysis complete!")
    print("=" * 70)


if __name__ == "__main__":
    main()
