from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd


@dataclass(frozen=True)
class SignalDatasetAudit:
    rows: int
    unique_symbols: int
    start_date: str | None
    end_date: str | None
    target_name: str
    recommended_model: str
    notes: list[str]


def count_rows(path: str | Path) -> int:
    df = pd.read_csv(path)
    return int(len(df))


def audit_signal_dataset(
    df: pd.DataFrame,
    *,
    date_col: str = "entry_date",
    symbol_col: str = "symbol",
    target_col: str = "r_multiple",
) -> SignalDatasetAudit:
    rows = int(len(df))
    unique_symbols = int(df[symbol_col].nunique()) if symbol_col in df.columns else 0
    start_date = None
    end_date = None
    if date_col in df.columns and not df.empty:
        dates = pd.to_datetime(df[date_col], errors="coerce")
        start_date = str(dates.min().date()) if dates.notna().any() else None
        end_date = str(dates.max().date()) if dates.notna().any() else None

    notes: list[str] = []
    if rows < 200:
        recommended_model = "Ridge/ElasticNet"
        notes.append("<200 trades: use baseline linear ranking, not boosters")
    elif rows < 500:
        recommended_model = "Regularized tree or linear"
        notes.append("200-500 trades: keep model simple")
    else:
        recommended_model = "LightGBM optional"
        notes.append(">500 trades: booster can be considered, but only with strict walk-forward")

    if target_col not in df.columns:
        if target_col == "r_multiple" and "return_pct" in df.columns:
            notes.append("using return_pct as fallback for missing r_multiple")
        else:
            notes.append(f"missing target column: {target_col}")

    return SignalDatasetAudit(
        rows=rows,
        unique_symbols=unique_symbols,
        start_date=start_date,
        end_date=end_date,
        target_name=target_col,
        recommended_model=recommended_model,
        notes=notes,
    )
