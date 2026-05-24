from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, balanced_accuracy_score, classification_report, f1_score


LABEL_ORDER = ["GREEN", "YELLOW", "RED"]
EXPOSURE_MAP = {"GREEN": 1.0, "YELLOW": 0.5, "RED": 0.0}


@dataclass
class WalkForwardMLResult:
    equity_curve: pd.DataFrame
    signals: pd.DataFrame
    folds: pd.DataFrame
    feature_importance: pd.DataFrame
    oos_accuracy: float
    oos_f1_weighted: float
    oos_f1_macro: float
    oos_balanced_accuracy: float


@dataclass
class WalkForwardMLTrainer:
    train_years: int = 3
    test_months: int = 3
    step_months: int = 3
    purge_days: int = 10
    initial_capital: float = 100000.0
    random_state: int = 42
    n_estimators: int = 100
    max_depth: int = 5
    class_weight: str = "balanced"
    min_train_rows: int = 100
    folds_: list[dict] = field(default_factory=list, init=False)

    def run(
        self,
        df: pd.DataFrame,
        *,
        date_col: str = "date",
        close_col: str = "Close",
        target_col: str = "target_regime",
        feature_cols: list[str],
    ) -> WalkForwardMLResult:
        work = df.copy()
        work[date_col] = pd.to_datetime(work[date_col])
        work = work.sort_values(date_col).reset_index(drop=True)

        # Filter out feature columns that are entirely NaN in the input DataFrame
        active_features = [c for c in feature_cols if c in work.columns and work[c].notna().any()]

        fold_rows: list[dict] = []
        signal_rows: list[pd.DataFrame] = []
        equity_parts: list[pd.DataFrame] = []
        feature_importance_rows: list[pd.DataFrame] = []

        capital = self.initial_capital
        start = work[date_col].min()
        last_date = work[date_col].max()
        fold_id = 0

        while True:
            train_start = start
            train_end = train_start + pd.DateOffset(years=self.train_years)
            test_start = train_end
            test_end = test_start + pd.DateOffset(months=self.test_months)

            train = work[(work[date_col] >= train_start) & (work[date_col] < train_end)]
            test = work[(work[date_col] >= test_start) & (work[date_col] < test_end)]

            if len(train) < self.min_train_rows or test.empty:
                break

            # Purge the last H trading days from the training set to prevent look-ahead leakage into the test set
            if len(train) > self.purge_days:
                train = train.iloc[:-self.purge_days]

            X_train = train[active_features].dropna()
            y_train = train.loc[X_train.index, target_col]
            train_valid = y_train.notna()
            X_train = X_train.loc[train_valid]
            y_train = y_train.loc[train_valid]
            if X_train.empty or y_train.nunique() < 2:
                start = start + pd.DateOffset(months=self.step_months)
                if start >= last_date:
                    break
                continue

            model = RandomForestClassifier(
                n_estimators=self.n_estimators,
                max_depth=self.max_depth,
                class_weight=self.class_weight,
                random_state=self.random_state,
                n_jobs=-1,
            )
            model.fit(X_train, y_train)

            fi = pd.DataFrame(
                {
                    "feature": active_features,
                    "importance": model.feature_importances_,
                    "fold_id": fold_id,
                }
            )
            feature_importance_rows.append(fi)

            test_context = self._with_previous_row(work, test, date_col)
            test_pred = self._predict_fold(
                model=model,
                test_context=test_context,
                test=test,
                date_col=date_col,
                close_col=close_col,
                capital=capital,
                feature_cols=active_features,
            )
            test_pred["fold_id"] = fold_id
            signal_rows.append(test_pred)

            fold_metrics = self._fold_metrics(test_pred)
            fold_metrics.update(
                {
                    "fold_id": fold_id,
                    "train_start": train_start,
                    "train_end": train_end,
                    "test_start": test[date_col].min(),
                    "test_end": test[date_col].max(),
                    "train_samples": len(X_train),
                    "test_samples": len(test_pred),
                    "purge_days": self.purge_days,
                }
            )
            fold_rows.append(fold_metrics)

            equity_parts.append(
                test_pred[
                    [date_col, "equity_curve", "strategy_return", "market_return", "regime_signal"]
                ]
            )
            if not test_pred.empty:
                capital = float(test_pred["equity_curve"].iloc[-1])

            fold_id += 1
            start = start + pd.DateOffset(months=self.step_months)
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
        fi_df = (
            pd.concat(feature_importance_rows, ignore_index=True)
            if feature_importance_rows
            else pd.DataFrame()
        )
        fi_agg = (
            fi_df.groupby("feature", as_index=False)["importance"]
            .mean()
            .sort_values("importance", ascending=False)
            if not fi_df.empty
            else pd.DataFrame(columns=["feature", "importance"])
        )

        valid = (
            all_signals.dropna(subset=[target_col, "regime_signal"])
            if not all_signals.empty
            else pd.DataFrame()
        )
        if not valid.empty:
            oos_acc = accuracy_score(valid[target_col], valid["regime_signal"])
            oos_bal_acc = balanced_accuracy_score(valid[target_col], valid["regime_signal"])
            oos_f1_w = f1_score(
                valid[target_col], valid["regime_signal"], average="weighted", zero_division=0
            )
            oos_f1_m = f1_score(
                valid[target_col], valid["regime_signal"], average="macro", zero_division=0
            )
        else:
            oos_acc = oos_bal_acc = oos_f1_w = oos_f1_m = 0.0

        return WalkForwardMLResult(
            equity_curve=equity_curve,
            signals=all_signals,
            folds=folds_df,
            feature_importance=fi_agg,
            oos_accuracy=oos_acc,
            oos_f1_weighted=oos_f1_w,
            oos_f1_macro=oos_f1_m,
            oos_balanced_accuracy=oos_bal_acc,
        )

    def _with_previous_row(
        self, work: pd.DataFrame, test: pd.DataFrame, date_col: str
    ) -> pd.DataFrame:
        prev_row = work[work[date_col] < test[date_col].min()].tail(1)
        return pd.concat([prev_row, test], ignore_index=True) if not prev_row.empty else test.copy()

    def _predict_fold(
        self,
        *,
        model,
        test_context: pd.DataFrame,
        test: pd.DataFrame,
        date_col: str,
        close_col: str,
        capital: float,
        feature_cols: list[str],
    ) -> pd.DataFrame:
        X_test = test_context[feature_cols].dropna()
        pred = test_context.loc[X_test.index].copy()
        probs = model.predict_proba(X_test)
        pred_classes = model.predict(X_test)

        class_to_idx = {cls: idx for idx, cls in enumerate(model.classes_)}
        pred["regime_signal"] = pred_classes
        pred["p_green"] = self._class_probability(probs, class_to_idx, "GREEN")
        pred["p_yellow"] = self._class_probability(probs, class_to_idx, "YELLOW")
        pred["p_red"] = self._class_probability(probs, class_to_idx, "RED")
        pred["regime_proba"] = probs.max(axis=1)

        # Attach returns and compute strategy returns/equity curve on full context (including previous day)
        pred = self._attach_returns(pred, date_col, close_col, capital)
        # Then slice to keep only the test period rows OOS
        pred = pred[pred[date_col].isin(test[date_col])].copy()
        return pred

    def _class_probability(
        self,
        probs: np.ndarray,
        class_to_idx: dict,
        class_name: str,
    ) -> np.ndarray:
        idx = class_to_idx.get(class_name)
        if idx is None:
            return np.zeros(len(probs), dtype=float)
        return probs[:, idx]

    def _attach_returns(
        self,
        df: pd.DataFrame,
        date_col: str,
        close_col: str,
        initial_capital: float,
    ) -> pd.DataFrame:
        out = df.copy()
        out[date_col] = pd.to_datetime(out[date_col])
        out = out.sort_values(date_col).reset_index(drop=True)
        out["market_return"] = out[close_col].pct_change().fillna(0.0)
        out["exposure"] = out["regime_signal"].map(EXPOSURE_MAP).astype(float)
        out["strategy_return"] = out["market_return"] * out["exposure"].shift(1).fillna(0.0)
        out["equity_curve"] = initial_capital * (1.0 + out["strategy_return"]).cumprod()
        return out

    def _fold_metrics(self, scored: pd.DataFrame) -> dict:
        equity = scored["equity_curve"]
        returns = scored["strategy_return"]
        if len(equity) >= 2:
            years = len(equity) / 252
            cagr = (equity.iloc[-1] / equity.iloc[0]) ** (1 / years) - 1 if years > 0 else 0
        else:
            cagr = 0
        running_max = equity.cummax()
        drawdown = equity / running_max - 1
        max_dd = drawdown.min() if not drawdown.empty else 0
        sharpe = np.sqrt(252) * returns.mean() / returns.std() if returns.std() > 0 else 0
        return {
            "strategy_cagr": float(cagr),
            "strategy_max_drawdown": float(max_dd),
            "strategy_sharpe": float(sharpe),
            "cash_pct": float((scored["exposure"] == 0).mean()),
        }
