"""Diagnóstico de problemas del sistema Momentum Trading"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import pandas as pd
import numpy as np


def analyze_entry_score_components(trades_df: pd.DataFrame):
    """Analiza correlación de cada componente del entry_score con PnL"""
    print("\n" + "=" * 60)
    print("📊 ANÁLISIS DE COMPONENTES DEL ENTRY SCORE")
    print("=" * 60)

    if trades_df.empty:
        print("❌ No hay trades para analizar")
        return

    if "entry_score" not in trades_df.columns or "pnl" not in trades_df.columns:
        print("❌ Faltan columnas necesarias")
        return

    df = trades_df.copy()
    df["entry_score"] = pd.to_numeric(df["entry_score"], errors="coerce")
    df["pnl"] = pd.to_numeric(df["pnl"], errors="coerce")
    df_clean = df.dropna(subset=["entry_score", "pnl"])

    print(f"\n📈 Total trades analizados: {len(df_clean)}")

    # Calcular R múltiple - intentar con stop_loss o con adjusted_risk_dollars
    if "r_multiple" in df_clean.columns:
        has_r = True
    elif "adjusted_risk_dollars" in df_clean.columns and "pnl" in df_clean.columns:
        # Calcular R desde risk dollars
        df_clean["r_multiple"] = df_clean["pnl"] / df_clean["adjusted_risk_dollars"]
        has_r = True
    elif "stop_loss" in df_clean.columns and "entry_price" in df_clean.columns:
        # Intentar calcular desde stop_loss (puedefallar si stop_loss == entry_price)
        df_clean["r_multiple"] = df_clean.apply(
            lambda r: (r["pnl"] / abs(r["entry_price"] - r["stop_loss"]) / r["shares"])
            if pd.notna(r["stop_loss"])
            and r["entry_price"] != r["stop_loss"]
            and r["shares"] > 0
            else 0,
            axis=1,
        )
        has_r = True
    else:
        has_r = False

    # Correlación general
    corr_pnl = df_clean["entry_score"].corr(df_clean["pnl"])
    print(f"\n🔗 Correlación entry_score vs PnL: {corr_pnl:.4f}")

    if has_r:
        corr_r = df_clean["entry_score"].corr(df_clean["r_multiple"])
        print(f"🔗 Correlación entry_score vs R: {corr_r:.4f}")

    return df_clean

    # Distribución por rangos de score
    print("\n📊 DISTRIBUCIÓN POR RANGOS DE SCORE:")
    print("-" * 50)

    ranges = [
        ("High (≥0.7)", df_clean["entry_score"] >= 0.7),
        (
            "Med (0.4-0.7)",
            (df_clean["entry_score"] >= 0.4) & (df_clean["entry_score"] < 0.7),
        ),
        ("Low (<0.4)", df_clean["entry_score"] < 0.4),
    ]

    for label, mask in ranges:
        subset = df_clean[mask]
        if len(subset) > 0:
            wins = (subset["pnl"] > 0).sum()
            total = len(subset)
            wr = wins / total * 100
            avg_pnl = subset["pnl"].mean()
            avg_r = subset["r_multiple"].mean()
            print(
                f"  {label:12s}: {total:4d} trades | WR: {wr:5.1f}% | Avg PnL: ${avg_pnl:7.2f} | Avg R: {avg_r:+.3f}"
            )

    # Verificar si pattern_bonus está distorsionando
    if "pattern_confidence" in df_clean.columns:
        print("\n🎯 IMPACTO DEL PATTERN BONUS:")
        print("-" * 50)
        df_clean["pattern_confidence"] = pd.to_numeric(
            df_clean["pattern_confidence"], errors="coerce"
        )

        with_bonus = df_clean[df_clean["pattern_confidence"] > 0]
        without_bonus = df_clean[
            df_clean["pattern_confidence"].isna()
            | (df_clean["pattern_confidence"] == 0)
        ]

        print(
            f"  Con pattern:   {len(with_bonus):4d} trades | WR: {(with_bonus['pnl'] > 0).mean() * 100:5.1f}% | Avg Score: {with_bonus['entry_score'].mean():.3f}"
        )
        print(
            f"  Sin pattern:   {len(without_bonus):4d} trades | WR: {(without_bonus['pnl'] > 0).mean() * 100:5.1f}% | Avg Score: {without_bonus['entry_score'].mean():.3f}"
        )

        # Verificar si el bonus está inflando scores
        if len(with_bonus) > 0:
            base_score_no_bonus = with_bonus["entry_score"] - 0.3  # Quitar bonus aprox
            print(
                f"\n  ⚠️  Score promedio CON bonus: {with_bonus['entry_score'].mean():.3f}"
            )
            print(
                f"  ⚠️  Score promedio SIN bonus (estimado): {base_score_no_bonus.mean():.3f}"
            )


def analyze_r_reached(trades_df: pd.DataFrame):
    """Analiza distribución de R múltiples alcanzados"""
    print("\n" + "=" * 60)
    print("📉 ANÁLISIS DE R MÚLTIPLES ALCANZADOS")
    print("=" * 60)

    if "r_multiple" not in trades_df.columns:
        print("❌ No hay datos de R múltiples")
        return

    df = trades_df.copy()
    df["r_multiple"] = pd.to_numeric(df["r_multiple"], errors="coerce")
    df_clean = df.dropna(subset=["r_multiple"])

    # R múltiples alcanzados en trades winners
    if df_clean.empty:
        print("   ⚠️ No hay datos de R múltiples")
        return

    winners = df_clean[df_clean["r_multiple"] > 0]
    losers = df_clean[df_clean["r_multiple"] <= 0]

    print(f"\n🏆 Winners: {len(winners)} trades")
    print(f"   Promedio R: {winners['r_multiple'].mean():.3f}")
    print(f"   Mediana R: {np.median(winners['r_multiple']):.3f}")
    print(f"   Max R: {winners['r_multiple'].max():.3f}")

    print(f"\n❌ Losers: {len(losers)} trades")
    print(f"   Promedio R: {losers['r_multiple'].mean():.3f}")
    print(f"   Min R: {losers['r_multiple'].min():.3f}")

    # Distribución de R en winners
    print("\n📊 Distribución de R en winners:")
    r_bins = [0, 0.5, 1, 1.5, 2, 2.5, 3, 5, 10, float("inf")]
    r_labels = [
        "0-0.5R",
        "0.5-1R",
        "1-1.5R",
        "1.5-2R",
        "2-2.5R",
        "2.5-3R",
        "3-5R",
        "5-10R",
        "10R+",
    ]

    for i, label in enumerate(r_labels):
        count = (
            (winners["r_multiple"] >= r_bins[i])
            & (winners["r_multiple"] < r_bins[i + 1])
        ).sum()
        pct = count / len(winners) * 100 if len(winners) > 0 else 0
        print(f"   {label:10s}: {count:4d} ({pct:5.1f}%)")


def main():
    """Ejecutar análisis completo"""
    print("\n" + "=" * 60)
    print("🚀 DIAGNÓSTICO COMPLETO DEL SISTEMA MOMENTUM")
    print("=" * 60)

    # Buscar archivos - usar backtest_results.csv como principal
    main_file = Path("outputs/backtests/backtest_results.csv")
    test_file = Path("outputs/backtests/test_trades.csv")

    if main_file.exists():
        trades_file = main_file
    elif test_file.exists():
        trades_file = test_file
    else:
        trades_file = None

    if trades_file:
        print(f"\n📂 Cargando: {trades_file}")
        trades_df = pd.read_csv(trades_file)
        print(f"   Trades cargados: {len(trades_df)}")

        # Ejecutar análisis
        df_with_r = analyze_entry_score_components(trades_df)
        analyze_r_reached(df_with_r if df_with_r is not None else trades_df)
    else:
        print("\n❌ No se encontraron archivos de trades")
        print("   Ejecuta un backtest primero:")
        print(
            "   python3 backtest_dynamic_universe.py --start 2024-01-01 --end 2024-12-31"
        )


if __name__ == "__main__":
    main()
