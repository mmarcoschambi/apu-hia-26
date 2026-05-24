from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.linear_model import ElasticNet, Ridge
from sklearn.metrics import mean_squared_error, r2_score

try:
    from lightgbm import LGBMRegressor
except Exception:  # pragma: no cover
    LGBMRegressor = None


@dataclass
class SignalWalkForwardResult:
    predictions: pd.DataFrame
    folds: pd.DataFrame
    feature_importance: pd.DataFrame
    corr_oos: float
    rmse_oos: float
    model_name: str


@dataclass
class SignalWalkForwardTrainer:
    train_years: int = 3
    test_months: int = 3
    step_months: int = 3
    min_rows: int = 200
    initial_capital: float = 100000.0
    model_name: str = "ridge"
    random_state: int = 42
    folds_: list[dict] = field(default_factory=list, init=False)

    def run(
        self,
        df: pd.DataFrame,
        *,
        date_col: str = "entry_date",
        symbol_col: str = "symbol",
        target_col: str = "r_multiple",
        feature_cols: list[str],
    ) -> SignalWalkForwardResult:
        work = df.copy()
        work[date_col] = pd.to_datetime(work[date_col], errors="coerce")
        work = work.sort_values(date_col).reset_index(drop=True)

        preds: list[pd.DataFrame] = []
        fold_rows: list[dict] = []
        fi_rows: list[pd.DataFrame] = []

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

            if len(train) < self.min_rows or test.empty:
                break

            X_train = train[feature_cols].copy()
            y_train = pd.to_numeric(train[target_col], errors="coerce")
            X_train = self._encode_features(X_train)
            mask = X_train.notna().all(axis=1) & y_train.notna()
            X_train = X_train.loc[mask]
            y_train = y_train.loc[mask]
            if len(X_train) < self.min_rows:
                start = start + pd.DateOffset(months=self.step_months)
                if start >= last_date:
                    break
                continue

            model = self._make_model()
            model.fit(X_train, y_train)

            if hasattr(model, "feature_importances_"):
                fi_rows.append(
                    pd.DataFrame(
                        {
                            "feature": feature_cols,
                            "importance": model.feature_importances_,
                            "fold_id": fold_id,
                        }
                    )
                )

            X_test = self._encode_features(test[feature_cols].copy())
            pred_mask = X_test.notna().all(axis=1)
            test_pred = test.loc[pred_mask].copy()
            X_test = X_test.loc[pred_mask]
            if X_test.empty:
                start = start + pd.DateOffset(months=self.step_months)
                if start >= last_date:
                    break
                continue

            raw_pred = pd.Series(model.predict(X_test), index=X_test.index)
            train_pred = pd.Series(model.predict(X_train), index=X_train.index)
            test_pred["pred_return"] = raw_pred
            test_pred["pred_score"] = self._percentile_from_train(train_pred, raw_pred)
            test_pred["fold_id"] = fold_id

            best_threshold = self._find_best_threshold(train_pred, y_train)
            test_pred["best_threshold"] = best_threshold
            test_pred["take_trade"] = test_pred["pred_score"] >= best_threshold
            test_pred["risk_multiplier"] = np.select(
                [
                    test_pred["pred_score"] >= (best_threshold + 10.0),
                    test_pred["pred_score"] >= best_threshold,
                    test_pred["pred_score"] >= (best_threshold - 20.0),
                ],
                [2.0, 1.0, 0.5],
                default=0.0,
            )
            preds.append(test_pred)

            fold_rows.append(
                {
                    "fold_id": fold_id,
                    "train_start": train_start,
                    "train_end": train_end,
                    "test_start": test[date_col].min(),
                    "test_end": test[date_col].max(),
                    "train_rows": len(X_train),
                    "test_rows": len(test_pred),
                    "best_threshold": float(best_threshold),
                    "rmse": float(
                        np.sqrt(mean_squared_error(
                            test_pred[target_col], test_pred["pred_return"]
                        ))
                    ),
                    "corr": float(test_pred[[target_col, "pred_return"]].corr().iloc[0, 1])
                    if len(test_pred) > 1
                    else 0.0,
                    "r2": float(r2_score(test_pred[target_col], test_pred["pred_return"]))
                    if len(test_pred) > 1
                    else 0.0,
                }
            )

            fold_id += 1
            start = start + pd.DateOffset(months=self.step_months)
            if start >= last_date:
                break

        pred_df = pd.concat(preds, ignore_index=True) if preds else pd.DataFrame()
        folds_df = pd.DataFrame(fold_rows)
        fi_df = (
            pd.concat(fi_rows, ignore_index=True)
            if fi_rows
            else pd.DataFrame(columns=["feature", "importance"])
        )
        fi_agg = (
            fi_df.groupby("feature", as_index=False)["importance"]
            .mean()
            .sort_values("importance", ascending=False)
            if not fi_df.empty
            else pd.DataFrame(columns=["feature", "importance"])
        )

        corr_oos = (
            float(pred_df[[target_col, "pred_return"]].corr().iloc[0, 1])
            if len(pred_df) > 1
            else 0.0
        )
        rmse_oos = (
            float(np.sqrt(mean_squared_error(pred_df[target_col], pred_df["pred_return"])))
            if len(pred_df)
            else 0.0
        )

        return SignalWalkForwardResult(
            predictions=pred_df,
            folds=folds_df,
            feature_importance=fi_agg,
            corr_oos=corr_oos,
            rmse_oos=rmse_oos,
            model_name=self.model_name,
        )

    def _make_model(self):
        if self.model_name == "lightgbm" and LGBMRegressor is not None:
            return LGBMRegressor(
                n_estimators=300,
                max_depth=4,
                learning_rate=0.05,
                subsample=0.8,
                colsample_bytree=0.8,
                random_state=self.random_state,
            )
        if self.model_name == "elasticnet":
            return ElasticNet(alpha=0.001, l1_ratio=0.3, random_state=self.random_state)
        return Ridge(alpha=1.0, random_state=self.random_state)

    def _encode_features(self, X: pd.DataFrame) -> pd.DataFrame:
        out = X.copy()
        for col in out.columns:
            if pd.api.types.is_bool_dtype(out[col]):
                out[col] = out[col].astype(float)
            elif pd.api.types.is_object_dtype(out[col]) or pd.api.types.is_categorical_dtype(
                out[col]
            ):
                out[col] = out[col].astype("category").cat.codes.replace(-1, np.nan)
        return out.apply(pd.to_numeric, errors="coerce")

    def _percentile_from_train(self, train_pred: pd.Series, test_pred: pd.Series) -> pd.Series:
        train = pd.Series(train_pred).dropna().values
        if len(train) == 0:
            return pd.Series(np.zeros(len(test_pred)), index=test_pred.index)
        return pd.Series(
            [100.0 * (train <= v).mean() for v in test_pred.values], index=test_pred.index
        )

    def _find_best_threshold(self, train_pred: pd.Series, y_train: pd.Series) -> float:
        train_score = self._percentile_from_train(train_pred, train_pred)
        best_threshold = 70.0  # Default fallback
        best_sharpe = -np.inf
        
        # Test percentile thresholds from 50 to 80
        for threshold in [50.0, 60.0, 70.0, 80.0]:
            selected_y = y_train[train_score >= threshold]
            if len(selected_y) < 15 or len(selected_y) < 0.1 * len(y_train):
                continue
            
            mean_y = selected_y.mean()
            std_y = selected_y.std(ddof=1)
            sharpe = (mean_y / std_y) if (std_y > 0 and not pd.isna(std_y)) else 0.0
            
            # We want to maximize the Sharpe ratio OOS
            if sharpe > best_sharpe:
                best_sharpe = sharpe
                best_threshold = threshold
                
        return best_threshold
