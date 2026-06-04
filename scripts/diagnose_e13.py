#!/usr/bin/env python3
import argparse
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parent.parent
BACKTEST_DIR = ROOT / "outputs" / "backtests"


def resolve_gold_path() -> Path:
    candidates = [
        BACKTEST_DIR / "gold_standard_is_2023_2024_trades.csv",
        BACKTEST_DIR / "gold_standard_variant_e_trades.csv",
        BACKTEST_DIR / "gold_standard_dynamic_trades.csv",
        BACKTEST_DIR / "gold_standard_parity_trades.csv",
        BACKTEST_DIR / "gold_standard_parity_oos_trades.csv",
    ]
    for path in candidates:
        if path.exists():
            return path
    raise FileNotFoundError(
        "No se encontró un CSV Gold Standard en outputs/backtests/. "
        "Pasá --gold-path explícitamente."
    )


def load_trades(path: Path, require_health: bool = False) -> pd.DataFrame:
    df = pd.read_csv(path)
    if require_health and "health_at_entry" not in df.columns:
        raise ValueError(f"{path.name} no tiene la columna health_at_entry")
    if "exit_phase" not in df.columns:
        raise ValueError(f"{path.name} no tiene la columna exit_phase")
    return df


def regime_label(health: float) -> str:
    if health < 4:
        return "DEFENSE"
    if health < 6:
        return "PARTIAL"
    return "ATTACK"


def print_query_1(e13: pd.DataFrame) -> None:
    print("QUERY 1 — Distribución de exits por régimen en E13 IS")
    q1 = (
        e13.assign(regime=e13["health_at_entry"].apply(regime_label))
        .groupby(["regime", "exit_phase"], as_index=False)
        .agg(
            trades=("return_pct", "size"),
            avg_ret=("return_pct", "mean"),
            worst=("return_pct", "min"),
        )
        .sort_values(["regime", "trades"], ascending=[True, False])
    )
    print(q1.round(2).to_string(index=False))


def print_query_2(e13: pd.DataFrame, gold: pd.DataFrame, gold_label: str) -> None:
    print("\nQUERY 2 — Comparar mismo período Gold Standard vs E13")
    combined = pd.concat(
        [
            e13.assign(tag="e13_is_2023_2024"),
            gold.assign(tag=gold_label),
        ],
        ignore_index=True,
    )
    q2 = (
        combined.groupby("tag", as_index=False)
        .agg(
            trades=("return_pct", "size"),
            avg_ret=("return_pct", "mean"),
            worst_trade=("return_pct", "min"),
            best_trade=("return_pct", "max"),
            win_rate=("return_pct", lambda s: (s > 0).mean() * 100),
        )
        .sort_values("tag")
    )
    print(q2.round(2).to_string(index=False))


def main() -> None:
    parser = argparse.ArgumentParser(description="Diagnóstico E13 vs Gold Standard")
    parser.add_argument(
        "--e13-path",
        default=str(BACKTEST_DIR / "e13_is_2023_2024_trades.csv"),
        help="CSV de trades de E13 IS",
    )
    parser.add_argument(
        "--gold-path",
        default=None,
        help="CSV de trades del Gold Standard. Si no se pasa, se autodetecta.",
    )
    args = parser.parse_args()

    e13_path = Path(args.e13_path)
    gold_path = Path(args.gold_path) if args.gold_path else resolve_gold_path()

    e13 = load_trades(e13_path, require_health=True)
    gold = load_trades(gold_path, require_health=False)

    print(f"Usando E13: {e13_path.name}")
    print(f"Usando Gold: {gold_path.name}\n")
    print_query_1(e13)
    print_query_2(e13, gold, gold_path.stem.replace("_trades", ""))


if __name__ == "__main__":
    main()
