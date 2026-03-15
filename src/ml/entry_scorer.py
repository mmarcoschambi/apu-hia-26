"""
EntryScorer - LightGBM model that predicts trade quality at entry time.

The model answers ONE question:
    "Given these conditions at entry, what is P(r_multiple >= 1.0)?"

INTEGRATION POINTS
1. As additional filter in vectorbt_engine_advanced.py (FILTRO 6.5)
2. As score component in entry score v3
3. In optimize_3tier.py to gate Optuna trials
"""
from __future__ import annotations
import logging, os, pickle
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

CORE_FEATURES = [
    "context_rvol",
    "context_adr",
    "entry_score",
    "dist_sma20_pct",
    "stop_distance_pct",
    "context_dollar_vol",
    "context_vol",
]
EXTRA_FEATURES = [
    "pattern_confidence",
    "pattern_bonus",
    "score_volume",
    "score_ema10",
    "initial_risk",
]
CAT_FEATURES = ["signal_type", "market_stage"]
ALL_FEATURES = CORE_FEATURES + EXTRA_FEATURES


def load_training_data(project_root: str = ".") -> pd.DataFrame:
    """Load and merge all available trade logs."""
    root = Path(project_root)
    sources = [
        root / "outputs/3tier_optimization/baseline_trades.csv",
        root / "outputs/backtests/complete_trades.csv",
        root / "outputs/backtests/backtest_results_enriched.csv",
        # root / "outputs/backtests/rejected_samples_ml.csv",  # DISABLED: synthetic features corrupt model
    ]
    dfs = []
    for path in sources:
        if not path.exists():
            continue
        try:
            df = pd.read_csv(path, low_memory=False)
            df["_source"] = path.stem
            dfs.append(df)
            logger.info(f"  Loaded {path.name}: {len(df)} rows")
        except Exception as e:
            logger.warning(f"  Could not load {path.name}: {e}")
    if not dfs:
        raise FileNotFoundError("No trade data found. Run optimizer first.")
    rename_maps = {"ticker": "symbol", "final_exit_date": "exit_date", "total_pnl": "pnl"}
    normalized = [df.rename(columns=rename_maps) for df in dfs]
    combined = pd.concat(normalized, ignore_index=True, sort=False)
    if "symbol" in combined.columns and "entry_date" in combined.columns:
        combined["_n_valid"] = combined.notna().sum(axis=1)
        combined = combined.sort_values("_n_valid", ascending=False)
        # rejected_samples may share (symbol, entry_date) with real trades -- keep real trade
        # real trades have r_multiple from actual exit; rejected have r_multiple=-1 (synthetic)
        # Sort so real trades (r_multiple != -1) come first, then dedup
        _has_real = combined["r_multiple"] != -1.0 if "r_multiple" in combined.columns else pd.Series(True, index=combined.index)
        combined = combined.sort_values([_has_real.name if hasattr(_has_real, "name") else "r_multiple"], ascending=False)
        combined = combined.drop_duplicates(subset=["symbol", "entry_date"], keep="first")
        combined = combined.drop(columns=["_n_valid"])
    n_rejected = (combined["r_multiple"] == -1.0).sum() if "r_multiple" in combined.columns else 0
    logger.info(f"  Combined dataset: {len(combined)} unique trades ({n_rejected} rejected samples)")
    return combined


def build_feature_matrix(
    df: pd.DataFrame,
    feature_cols: Optional[List[str]] = None,
) -> Tuple[pd.DataFrame, pd.Series, List[str]]:
    """Build X (features) and y (target=r_multiple>=1.0) from trade data."""
    if feature_cols is None:
        feature_cols = ALL_FEATURES
    if "r_multiple" not in df.columns:
        raise ValueError("r_multiple column required for training")
    # Target options:
    #   >= 1.0  -> hit 1R (very selective, ~13% positive -- too sparse)
    #   >= 0.0  -> any winner (62% positive -- better signal)
    #   >= 0.5  -> meaningful winner (good middle ground)
    # Use >= 0.5 for balanced signal: avoids predicting tiny winners
    y = (df["r_multiple"] >= 0.5).astype(int)
    available = [c for c in feature_cols if c in df.columns]
    missing = [c for c in feature_cols if c not in df.columns]
    if missing:
        logger.info(f"  Features not available (skipping): {missing}")
    X = df[available].copy()
    for cat in CAT_FEATURES:
        if cat in X.columns:
            X[cat] = X[cat].astype("category").cat.codes
    X = X.fillna(X.median(numeric_only=True))
    logger.info(f"  Feature matrix: {X.shape[0]} rows x {X.shape[1]} features | class balance: {y.mean():.1%} positive")
    return X, y, available


class EntryScorer:
    """LightGBM classifier predicting P(r_multiple >= 1.0) at entry time."""

    MODEL_PATH = "models/entry_scorer.pkl"

    def __init__(self, n_estimators=200, max_depth=4, learning_rate=0.05,
                 feature_cols=None, project_root="."):
        self.n_estimators = n_estimators
        self.max_depth = max_depth
        self.learning_rate = learning_rate
        self.feature_cols = feature_cols or ALL_FEATURES
        self.project_root = project_root
        self.model = None
        self.used_features: List[str] = []
        self.threshold = 0.50
        self._trained = False

    def train(self, df=None, eval_split=0.2, verbose=True) -> Dict:
        try:
            import lightgbm as lgb
        except ImportError:
            raise ImportError("Run: pip install lightgbm --break-system-packages")
        from sklearn.metrics import roc_auc_score, classification_report
        from sklearn.model_selection import train_test_split

        if df is None:
            df = load_training_data(self.project_root)

        X, y, used = build_feature_matrix(df, self.feature_cols)
        self.used_features = used

        if "entry_date" in df.columns:
            sort_idx = df["entry_date"].argsort().values
            X = X.iloc[sort_idx].reset_index(drop=True)
            y = y.iloc[sort_idx].reset_index(drop=True)
            split_pt = int(len(X) * (1 - eval_split))
            X_train, X_val = X.iloc[:split_pt], X.iloc[split_pt:]
            y_train, y_val = y.iloc[:split_pt], y.iloc[split_pt:]
            if verbose:
                logger.info(f"  Temporal split: {len(X_train)} train / {len(X_val)} val")
        else:
            X_train, X_val, y_train, y_val = train_test_split(
                X, y, test_size=eval_split, random_state=42, stratify=y)

        neg = (y_train == 0).sum()
        pos = (y_train == 1).sum()
        scale = neg / pos if pos > 0 else 1.0

        # Sample weights: rejected_samples (synthetic negatives) get lower weight
        # df is sorted + reset_index was NOT called, so sort_idx aligns with df
        if "r_multiple" in df.columns:
            df_sorted = df.iloc[sort_idx].reset_index(drop=True) if "entry_date" in df.columns else df
            is_rej_sorted = (df_sorted["r_multiple"] == -1.0).values
            # train portion = first split_pt rows after sort
            is_rej_train = is_rej_sorted[:split_pt] if "entry_date" in df.columns else is_rej_sorted[:len(X_train)]
            sample_weight = np.where(is_rej_train, 0.30, 1.0)
            n_real = int((sample_weight == 1.0).sum())
            n_syn  = int((sample_weight < 1.0).sum())
            logger.info(f"  Sample weights: {n_real} real trades (w=1.0) | {n_syn} rejected (w=0.3)")
        else:
            sample_weight = None

        self.model = lgb.LGBMClassifier(
            n_estimators=self.n_estimators, max_depth=self.max_depth,
            learning_rate=self.learning_rate, num_leaves=15,
            min_child_samples=5, scale_pos_weight=scale,
            random_state=42, verbose=-1,
        )
        fit_kwargs = dict(
            eval_set=[(X_val, y_val)],
            callbacks=[lgb.early_stopping(20, verbose=False), lgb.log_evaluation(0)],
        )
        if sample_weight is not None:
            fit_kwargs["sample_weight"] = sample_weight
        self.model.fit(X_train, y_train, **fit_kwargs,
        )

        proba_val = self.model.predict_proba(X_val)[:, 1]
        pred_val = (proba_val >= self.threshold).astype(int)
        auc = roc_auc_score(y_val, proba_val) if len(y_val.unique()) > 1 else 0.5
        report = classification_report(y_val, pred_val, output_dict=True, zero_division=0)
        importances = dict(sorted(
            zip(self.used_features, self.model.feature_importances_),
            key=lambda x: x[1], reverse=True))

        self._trained = True

        if verbose:
            logger.info(f"\n  === EntryScorer Training Results ===")
            logger.info(f"  Train size: {len(X_train)} | Val size: {len(X_val)}")
            logger.info(f"  Class balance (train): {y_train.mean():.1%} positive")
            logger.info(f"  ROC-AUC:   {auc:.3f}")
            logger.info(f"  Precision: {report['1']['precision']:.3f}")
            logger.info(f"  Recall:    {report['1']['recall']:.3f}")
            logger.info(f"  F1:        {report['1']['f1-score']:.3f}")
            logger.info(f"\n  Top features by importance:")
            for feat, imp in list(importances.items())[:8]:
                logger.info(f"    {feat:<30} {imp}")

        return {"roc_auc": auc, "precision": report['1']['precision'],
                "recall": report['1']['recall'], "f1": report['1']['f1-score'],
                "n_train": len(X_train), "n_val": len(X_val),
                "feature_importances": importances}

    def predict_proba(self, features) -> float:
        if not self._trained or self.model is None:
            raise RuntimeError("Model not trained. Call .train() first.")
        if isinstance(features, dict):
            row = {f: features.get(f, np.nan) for f in self.used_features}
            X = pd.DataFrame([row])
            return float(self.model.predict_proba(X)[0, 1])
        else:
            X = features.reindex(columns=self.used_features).fillna(0)
            return self.model.predict_proba(X)[:, 1]

    def predict_series(self, df: pd.DataFrame) -> pd.Series:
        proba = self.predict_proba(df)
        return pd.Series(proba, index=df.index, name="ml_entry_prob")

    def score_distribution(self, df=None) -> Dict:
        if df is None:
            df = load_training_data(self.project_root)
        X, y, _ = build_feature_matrix(df, self.used_features)
        proba = self.model.predict_proba(X)[:, 1]
        report = {}
        for t in [0.40, 0.45, 0.50, 0.55, 0.60, 0.65]:
            mask = proba >= t
            n = mask.sum()
            if n > 0:
                precision = y[mask].mean()
                report[f"threshold_{t:.2f}"] = {
                    "n_trades": int(n),
                    "pct_selected": f"{n/len(proba):.1%}",
                    "win_rate_if_selected": f"{precision:.1%}",
                }
        return report

    def save(self, path=None) -> str:
        save_path = Path(path or self.MODEL_PATH)
        save_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"model": self.model, "used_features": self.used_features,
                   "threshold": self.threshold, "n_estimators": self.n_estimators,
                   "max_depth": self.max_depth}
        with open(save_path, "wb") as f:
            pickle.dump(payload, f)
        logger.info(f"  Model saved to {save_path}")
        return str(save_path)

    @classmethod
    def load(cls, path=None, project_root=".") -> "EntryScorer":
        load_path = Path(path or cls.MODEL_PATH)
        if not load_path.exists():
            raise FileNotFoundError(f"Model not found: {load_path}")
        with open(load_path, "rb") as f:
            payload = pickle.load(f)
        scorer = cls(project_root=project_root)
        scorer.model = payload["model"]
        scorer.used_features = payload["used_features"]
        scorer.threshold = payload["threshold"]
        scorer._trained = True
        logger.info(f"  Model loaded from {load_path}")
        return scorer

    def feature_importance_report(self) -> pd.DataFrame:
        if not self._trained:
            raise RuntimeError("Train model first.")
        fi = dict(zip(self.used_features, self.model.feature_importances_))
        return (pd.DataFrame.from_dict(fi, orient="index", columns=["importance"])
                .sort_values("importance", ascending=False))


def main():
    import json, sys
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    project_root = sys.argv[1] if len(sys.argv) > 1 else "."

    logger.info("=" * 60)
    logger.info("  EntryScorer -- LightGBM Training")
    logger.info("=" * 60)

    try:
        import lightgbm
        logger.info(f"  LightGBM version: {lightgbm.__version__}")
    except ImportError:
        logger.error("LightGBM not installed. Run: pip install lightgbm --break-system-packages")
        sys.exit(1)

    scorer = EntryScorer(project_root=project_root)
    metrics = scorer.train(verbose=True)

    logger.info("\n  === Score Distribution ===")
    dist = scorer.score_distribution()
    for k, v in dist.items():
        logger.info(f"  {k}: {v}")

    save_path = scorer.save(os.path.join(project_root, "models/entry_scorer.pkl"))

    summary = {
        "status": "trained",
        "roc_auc": round(metrics["roc_auc"], 4),
        "precision": round(metrics["precision"], 4),
        "recall": round(metrics["recall"], 4),
        "f1": round(metrics["f1"], 4),
        "n_train": metrics["n_train"],
        "n_val": metrics["n_val"],
        "model_path": save_path,
        "top_features": list(metrics["feature_importances"].keys())[:5],
    }
    summary_path = os.path.join(project_root, "models/entry_scorer_summary.json")
    Path(summary_path).parent.mkdir(parents=True, exist_ok=True)
    with open(summary_path, "w") as f:
        json.dump(summary, f, indent=2)

    logger.info(f"\n  Summary: {summary_path}")
    logger.info("=" * 60)
    logger.info("  NEXT STEPS:")
    logger.info("  1. Use as filter: block entries with prob < 0.50")
    logger.info("  2. Use as score boost: entry_score += 0.2 * prob")
    logger.info("  3. Collect MORE data: run optimizer to generate more trades")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
