from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd

from src.regime_detection.baseline_rules import (
    BaselineThresholds,
    LABEL_GREEN,
    LABEL_RED,
    LABEL_YELLOW,
    classify_regime_baseline,
)


@dataclass(frozen=True)
class BacktestConfig:
    train_years: int = 3
    test_months: int = 3
    step_months: int = 3
    initial_capital: float = 100000.0
    annualization_factor: int = 252
    vix_grid: tuple[float, ...] = (20.0, 22.0, 25.0, 28.0)
    breadth_red_grid: tuple[float, ...] = (-30.0, -25.0, -20.0, -15.0)
    dix_red_grid: tuple[float, ...] = (30.0, 35.0, 40.0, 45.0)
    yellow_vix_low: float = 15.0
    yellow_vix_high: float = 25.0
    yellow_breadth_low: float = -10.0
    yellow_breadth_high: float = 10.0


@dataclass
class WalkForwardBacktestResult:
    equity_curve: pd.DataFrame
    signals: pd.DataFrame
    folds: pd.DataFrame
    best_thresholds: list[BaselineThresholds] = field(default_factory=list)


class WalkForwardRegimeBacktester:
    def __init__(self, config: BacktestConfig | None = None):
        self.config = config or BacktestConfig()

    def run(
        self,
        df: pd.DataFrame,
        *,
        date_col: str = "date",
        close_col: str = "Close",
    ) -> WalkForwardBacktestResult:
        required = {date_col, close_col, "vix", "breadth_pct", "dix"}
        missing = required.difference(df.columns)
        if missing:
            raise ValueError(f"Missing required columns: {sorted(missing)}")

        work = df.copy()
        work[date_col] = pd.to_datetime(work[date_col])
        work = work.sort_values(date_col).drop_duplicates(subset=[date_col]).reset_index(drop=True)

        fold_rows: list[dict] = []
        signal_rows: list[pd.DataFrame] = []
        equity_parts: list[pd.DataFrame] = []
        best_thresholds: list[BaselineThresholds] = []
        capital = self.config.initial_capital

        start = work[date_col].min()
        last_date = work[date_col].max()
        fold_id = 0

        while True:
            train_start = start
            train_end = train_start + pd.DateOffset(years=self.config.train_years)
            test_end = train_end + pd.DateOffset(months=self.config.test_months)

            train = work[(work[date_col] >= train_start) & (work[date_col] < train_end)]
            test = work[(work[date_col] >= train_end) & (work[date_col] < test_end)]

            if len(train) < 100 or test.empty:
                break

            best_thresholds_fold, train_summary = self._optimize_thresholds(
                train, date_col, close_col
            )
            best_thresholds.append(best_thresholds_fold)

            prev_row = work[work[date_col] < test[date_col].min()].tail(1)
            test_context = (
                pd.concat([prev_row, test], ignore_index=True)
                if not prev_row.empty
                else test.copy()
            )
            test_signals = classify_regime_baseline(test_context, best_thresholds_fold)
            test_signals = self._attach_backtest_returns(
                test_signals,
                date_col,
                close_col,
                initial_capital=capital,
            )
            if not prev_row.empty:
                test_signals = test_signals.iloc[1:].reset_index(drop=True)
            test_signals["fold_id"] = fold_id
            signal_rows.append(test_signals)

            fold_metrics = self._fold_metrics(test_signals)
            fold_metrics.update(
                {
                    "fold_id": fold_id,
                    "train_start": train_start,
                    "train_end": train_end,
                    "test_start": test[date_col].min(),
                    "test_end": test[date_col].max(),
                    **train_summary,
                    **self._thresholds_as_dict(best_thresholds_fold),
                }
            )
            fold_rows.append(fold_metrics)

            equity_parts.append(
                test_signals[
                    [date_col, "equity_curve", "strategy_return", "market_return", "regime_signal"]
                ]
            )
            if not test_signals.empty:
                capital = float(test_signals["equity_curve"].iloc[-1])

            fold_id += 1
            start = start + pd.DateOffset(months=self.config.step_months)
            if start >= last_date:
                break

        all_signals = pd.concat(signal_rows, ignore_index=True) if signal_rows else pd.DataFrame()
        if not all_signals.empty:
            all_signals = all_signals.sort_values(date_col).reset_index(drop=True)

        equity_curve = (
            pd.concat(equity_parts, ignore_index=True) if equity_parts else pd.DataFrame()
        )
        if not equity_curve.empty:
            equity_curve = equity_curve.sort_values(date_col).reset_index(drop=True)

        folds_df = pd.DataFrame(fold_rows)
        return WalkForwardBacktestResult(
            equity_curve=equity_curve,
            signals=all_signals,
            folds=folds_df,
            best_thresholds=best_thresholds,
        )

    def _optimize_thresholds(
        self,
        train: pd.DataFrame,
        date_col: str,
        close_col: str,
    ) -> tuple[BaselineThresholds, dict]:
        best_score = -np.inf
        best_thresholds = BaselineThresholds()
        best_summary: dict = {}

        for vix in self.config.vix_grid:
            for breadth_red in self.config.breadth_red_grid:
                for dix_red in self.config.dix_red_grid:
                    thresholds = BaselineThresholds(
                        red_vix=vix,
                        red_breadth_pct=breadth_red,
                        red_dix=dix_red,
                        yellow_vix_low=self.config.yellow_vix_low,
                        yellow_vix_high=self.config.yellow_vix_high,
                        yellow_breadth_low=self.config.yellow_breadth_low,
                        yellow_breadth_high=self.config.yellow_breadth_high,
                    )
                    scored = classify_regime_baseline(train, thresholds)
                    scored = self._attach_backtest_returns(scored, date_col, close_col)
                    score = self._objective_score(scored)
                    if score > best_score:
                        best_score = score
                        best_thresholds = thresholds
                        best_summary = {
                            "train_objective": score,
                            "train_sharpe": self._sharpe_ratio(scored["strategy_return"]),
                            "train_max_drawdown": self._max_drawdown(scored["equity_curve"]),
                            "train_cash_pct": float((scored["exposure"] == 0).mean()),
                        }

        return best_thresholds, best_summary

    def _objective_score(self, scored: pd.DataFrame) -> float:
        sharpe = self._sharpe_ratio(scored["strategy_return"])
        max_dd = self._max_drawdown(scored["equity_curve"])
        cash_pct = float((scored["exposure"] == 0).mean())
        return sharpe - abs(max_dd) * 0.5 + cash_pct * 0.1

    def _attach_backtest_returns(
        self,
        df: pd.DataFrame,
        date_col: str,
        close_col: str,
        *,
        initial_capital: float | None = None,
    ) -> pd.DataFrame:
        out = df.copy()
        out[date_col] = pd.to_datetime(out[date_col])
        out["market_return"] = out[close_col].pct_change().fillna(0.0)
        out["exposure"] = (
            out["regime_signal"]
            .map({LABEL_GREEN: 1.0, LABEL_YELLOW: 0.5, LABEL_RED: 0.0})
            .astype(float)
        )
        out["strategy_return"] = out["market_return"] * out["exposure"].shift(1).fillna(0.0)
        base_capital = self.config.initial_capital if initial_capital is None else initial_capital
        out["equity_curve"] = base_capital * (1.0 + out["strategy_return"]).cumprod()
        return out

    def _fold_metrics(self, scored: pd.DataFrame) -> dict:
        return {
            "strategy_cagr": self._cagr(scored["equity_curve"]),
            "strategy_max_drawdown": self._max_drawdown(scored["equity_curve"]),
            "strategy_sharpe": self._sharpe_ratio(scored["strategy_return"]),
            "cash_pct": float((scored["exposure"] == 0).mean()),
        }

    def _sharpe_ratio(self, returns: pd.Series) -> float:
        returns = pd.Series(returns).dropna()
        if returns.empty or returns.std(ddof=0) == 0:
            return 0.0
        return float(
            np.sqrt(self.config.annualization_factor) * returns.mean() / returns.std(ddof=0)
        )

    def _max_drawdown(self, equity: pd.Series) -> float:
        equity = pd.Series(equity).dropna()
        if equity.empty:
            return 0.0
        running_max = equity.cummax()
        drawdown = equity / running_max - 1.0
        return float(drawdown.min())

    def _cagr(self, equity: pd.Series) -> float:
        equity = pd.Series(equity).dropna()
        if equity.empty or len(equity) < 2:
            return 0.0
        start, end = equity.iloc[0], equity.iloc[-1]
        days = max(len(equity) - 1, 1)
        years = days / self.config.annualization_factor
        if start <= 0 or years <= 0:
            return 0.0
        return float((end / start) ** (1.0 / years) - 1.0)

    def _thresholds_as_dict(self, thresholds: BaselineThresholds) -> dict:
        return {
            "red_vix": thresholds.red_vix,
            "red_breadth_pct": thresholds.red_breadth_pct,
            "red_dix": thresholds.red_dix,
            "yellow_vix_low": thresholds.yellow_vix_low,
            "yellow_vix_high": thresholds.yellow_vix_high,
            "yellow_breadth_low": thresholds.yellow_breadth_low,
            "yellow_breadth_high": thresholds.yellow_breadth_high,
        }
