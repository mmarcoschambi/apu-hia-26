"""
Purged Walk-Forward Cross-Validation
====================================

Implements expanding-window walk-forward with purge and embargo windows
to prevent data leakage in financial backtesting (per López de Prado 2018).

Per-fold:
  - Training: expanding window from fixed start to (test_start - purge_days),
    also excluding the embargo window from the previous fold's test period.
  - Test/OOS: specified OOS window (typically one year forward).

Aggregates IS/OOS Sharpe across folds and applies a degradation gate.
If degradation (IS Sharpe - OOS Sharpe) / IS Sharpe > 25%, the strategy
is rejected — it failed to generalize out-of-sample.

Usage:
    from src.validation.purged_walk_forward import PurgedWalkForwardValidator

    validator = PurgedWalkForwardValidator(n_folds=4, purge_days=10, embargo_days=5)
    folds = validator.generate_folds(train_start="2019-01-01")
    report = validator.validate(
        engine_class=AdvancedVectorBTEngine,
        params={...},
        universe=[...],
        fold_definitions=folds,
    )
    if report.gate_passed:
        print("Purged CV passed — degradation within limits")
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple, Type

import numpy as np

logger = logging.getLogger(__name__)

# === DEFAULT CONSTANTS ===

WF_N_FOLDS: int = 4
WF_PURGE_DAYS: int = 10
WF_EMBARGO_DAYS: int = 5
GATE_DEGRADATION: float = 0.25
MIN_OOS_TRADES: int = 30

# Trading day approximation (weekends + holidays ~ 1.4 cal days per trading day)
_TRADING_DAY_RATIO: float = 1.4


# === DATA CLASSES ===


@dataclass
class FoldMetrics:
    """Performance metrics for a single walk-forward fold."""

    fold: int
    is_sharpe: float
    oos_sharpe: float
    is_trades: int
    oos_trades: int


@dataclass
class PurgedWFReport:
    """Aggregated validation report from purged walk-forward CV.

    Attributes:
        folds: Per-fold metrics list
        is_sharpe_mean: Mean IS Sharpe across all folds
        oos_sharpe_mean: Mean OOS Sharpe across all folds
        degradation_pct: (IS_sharpe - OOS_sharpe) / IS_sharpe as percentage
        gate_passed: True if degradation_pct <= 25%
        trades_per_fold: List of OOS trade counts per fold
        warnings: Any warnings (e.g., insufficient trades per fold)
    """

    folds: List[FoldMetrics]
    is_sharpe_mean: float
    oos_sharpe_mean: float
    degradation_pct: float
    gate_passed: bool
    trades_per_fold: List[int]
    warnings: List[str] = field(default_factory=list)


# === VALIDATOR ===


class PurgedWalkForwardValidator:
    """
    Expanding-window walk-forward validator with purge/embargo windows.

    Prevents data leakage by removing:
    - ``purge_days`` before each test period from that fold's training data
    - ``embargo_days`` after each test period from the **next** fold's training data

    Aggregates IS/OOS Sharpe across folds and applies the degradation gate
    (rejects if (IS - OOS) / IS > 0.25).
    """

    def __init__(
        self,
        n_folds: int = WF_N_FOLDS,
        purge_days: int = WF_PURGE_DAYS,
        embargo_days: int = WF_EMBARGO_DAYS,
    ):
        if purge_days <= 0:
            raise ValueError(f"purge_days must be > 0, got {purge_days}")
        if embargo_days <= 0:
            raise ValueError(f"embargo_days must be > 0, got {embargo_days}")
        self.n_folds = n_folds
        self.purge_days = purge_days
        self.embargo_days = embargo_days

    # ------------------------------------------------------------------
    # Fold generation
    # ------------------------------------------------------------------

    def generate_folds(self, train_start: str) -> List[Dict[str, Any]]:
        """Generate expanding-window fold definitions.

        Each fold's OOS window is one calendar year forward.
        The first OOS starts 3 years after ``train_start``.

        Args:
            train_start: Fixed start date for all training windows (YYYY-MM-DD).

        Returns:
            List of dicts with keys ``fold``, ``oos_start``, ``oos_end``.
        """
        start_year = int(train_start[:4]) + 3  # first OOS starts 3yr after train
        folds: List[Dict[str, Any]] = []
        for i in range(self.n_folds):
            year = start_year + i
            folds.append(
                {
                    "fold": i + 1,
                    "oos_start": f"{year}-01-01",
                    "oos_end": f"{year}-12-31",
                }
            )
        return folds

    # ------------------------------------------------------------------
    # Purge / embargo helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _shift_date(date_str: str, trading_days: int, forward: bool = False) -> str:
        """Shift a YYYY-MM-DD string by *trading_days* (approximated).

        Uses a 1.4 calendar-day-per-trading-day heuristic.  This is a
        simplification; for production use with exact trading calendars,
        pass fold definitions with pre-computed purge/embargo dates.

        Args:
            date_str: Date in ``YYYY-MM-DD`` format.
            trading_days: Number of trading days to shift.
            forward: Shift forward (``True``) or backward (``False``).

        Returns:
            Shifted date string.
        """
        dt = datetime.strptime(date_str, "%Y-%m-%d").date()
        cal_days = int(abs(trading_days) * _TRADING_DAY_RATIO)
        if forward:
            dt += timedelta(days=cal_days)
        else:
            dt -= timedelta(days=cal_days)
        return dt.strftime("%Y-%m-%d")

    # ------------------------------------------------------------------
    # Training range computation
    # ------------------------------------------------------------------

    def get_training_range(
        self,
        train_start: str,
        fold_def: Dict[str, Any],
        previous_fold: Optional[Dict[str, Any]] = None,
    ) -> Tuple[str, str]:
        """Compute the effective training date range for a fold.

        Applies:
        1. **Purge**: training ends ``purge_days`` trading days before
           ``fold_def['oos_start']``.
        2. **Embargo**: if *previous_fold* is provided, the training end
           is further constrained to ensure it does not include data from
           the embargo window of the previous fold.

        The effective end is the **earlier** of the purge cutoff and the
        embargo cutoff (when both apply).

        Args:
            train_start: Fixed start date for all training.
            fold_def: Current fold definition with ``oos_start``.
            previous_fold: Previous fold definition (for embargo), or
                ``None`` for the first fold.

        Returns:
            Tuple of ``(effective_train_start, effective_train_end)``.
        """
        # Base purge: training ends purge_days before OOS start
        purge_end = self._shift_date(
            fold_def["oos_start"], self.purge_days, forward=False
        )

        # Embargo constraint: training must also end before the embargo
        # window of the previous fold (if any).
        if previous_fold is not None:
            embargo_end = self._shift_date(
                previous_fold["oos_end"], self.embargo_days, forward=True
            )
            # The effective end is the earlier of purge_end and embargo_end
            effective_end = min(purge_end, embargo_end)
        else:
            effective_end = purge_end

        return train_start, effective_end

    # ------------------------------------------------------------------
    # Degradation gate (pure function for testability)
    # ------------------------------------------------------------------

    @staticmethod
    def compute_degradation(
        is_sharpe: float,
        oos_sharpe: float,
        threshold: float = GATE_DEGRADATION,
    ) -> Tuple[float, bool]:
        """Compute IS-to-OOS Sharpe degradation and evaluate gate.

        Formula::

            degradation = (is_sharpe - oos_sharpe) / is_sharpe

        If ``is_sharpe <= 0``, degradation is undefined and the gate
        rejects (returns 1.0, ``False``).

        Args:
            is_sharpe: Mean in-sample Sharpe ratio.
            oos_sharpe: Mean out-of-sample Sharpe ratio.
            threshold: Maximum acceptable degradation (default ``0.25``).

        Returns:
            Tuple of ``(degradation_ratio, gate_passed)``.
        """
        if is_sharpe <= 0:
            return 1.0, False

        degradation = (is_sharpe - oos_sharpe) / is_sharpe
        gate_passed = degradation <= threshold
        return degradation, gate_passed

    # ------------------------------------------------------------------
    # Aggregate per-fold metrics into report
    # ------------------------------------------------------------------

    @staticmethod
    def aggregate_fold_metrics(
        folds_metrics: List[FoldMetrics],
        min_trades: int = MIN_OOS_TRADES,
    ) -> PurgedWFReport:
        """Aggregate per-fold metrics into a final validation report.

        Args:
            folds_metrics: List of per-fold metrics.
            min_trades: Minimum OOS trades per fold; folds below this
                trigger a warning.

        Returns:
            :class:`PurgedWFReport` with aggregated statistics.
        """
        warnings: List[str] = []

        # Flag insufficient-trade folds
        for fm in folds_metrics:
            if fm.oos_trades < min_trades:
                warnings.append(
                    f"Fold {fm.fold}: only {fm.oos_trades} OOS trades "
                    f"(< {min_trades}) — statistically insignificant"
                )

        sharpes_is = np.array([fm.is_sharpe for fm in folds_metrics])
        sharpes_oos = np.array([fm.oos_sharpe for fm in folds_metrics])

        is_sharpe_mean = float(np.mean(sharpes_is)) if len(sharpes_is) > 0 else 0.0
        oos_sharpe_mean = float(np.mean(sharpes_oos)) if len(sharpes_oos) > 0 else 0.0

        degradation, gate_passed = PurgedWalkForwardValidator.compute_degradation(
            is_sharpe_mean, oos_sharpe_mean
        )

        return PurgedWFReport(
            folds=folds_metrics,
            is_sharpe_mean=is_sharpe_mean,
            oos_sharpe_mean=oos_sharpe_mean,
            degradation_pct=round(degradation * 100, 2),
            gate_passed=gate_passed,
            trades_per_fold=[fm.oos_trades for fm in folds_metrics],
            warnings=warnings,
        )

    # ------------------------------------------------------------------
    # Main validation orchestrator
    # ------------------------------------------------------------------

    def validate(
        self,
        engine_class: Type,
        params: Dict[str, Any],
        universe: List[str],
        fold_definitions: List[Dict[str, Any]],
    ) -> PurgedWFReport:
        """Run purged walk-forward validation on a strategy.

        For each fold:
        1. Compute the effective training range (with purge/embargo).
        2. Run an IS backtest on the training range.
        3. Run an OOS backtest on the fold's test window.
        4. Collect per-fold Sharpe ratio and trade count.

        After all folds complete, aggregate and return the final report.

        Args:
            engine_class: Backtest engine class (e.g.,
                ``AdvancedVectorBTEngine``).
            params: Strategy parameters (passed to engine constructor).
            universe: List of ticker symbols.
            fold_definitions: List of fold definitions, each with keys
                ``fold``, ``oos_start``, ``oos_end``.

        Returns:
            :class:`PurgedWFReport` with aggregated results.

        Raises:
            ValueError: If *fold_definitions* is empty.
        """
        if not fold_definitions:
            raise ValueError("fold_definitions must not be empty")

        train_start = "2019-01-01"  # spec-defined fixed start
        folds_metrics: List[FoldMetrics] = []
        previous_fold: Optional[Dict[str, Any]] = None

        for fold_def in fold_definitions:
            fold_num = fold_def.get("fold", 0)
            oos_start = fold_def["oos_start"]
            oos_end = fold_def["oos_end"]

            # Training range with purge/embargo
            train_start_date, train_end_date = self.get_training_range(
                train_start, fold_def, previous_fold
            )

            # --- IS backtest ---
            try:
                is_engine = engine_class(
                    universe=universe,
                    start_date=train_start_date,
                    end_date=train_end_date,
                    **params,
                )
                is_engine.load_data()
                is_results = is_engine.run_backtest()
                is_sharpe = float(is_results.get("sharpe_ratio", 0.0))
                is_trades = int(is_results.get("total_trades", 0))
            except Exception as e:
                logger.error(f"Fold {fold_num} IS backtest failed: {e}")
                is_sharpe = 0.0
                is_trades = 0

            # --- OOS backtest ---
            try:
                oos_engine = engine_class(
                    universe=universe,
                    start_date=oos_start,
                    end_date=oos_end,
                    **params,
                )
                oos_engine.load_data()
                oos_results = oos_engine.run_backtest()
                oos_sharpe = float(oos_results.get("sharpe_ratio", 0.0))
                oos_trades = int(oos_results.get("total_trades", 0))
            except Exception as e:
                logger.error(f"Fold {fold_num} OOS backtest failed: {e}")
                oos_sharpe = 0.0
                oos_trades = 0

            folds_metrics.append(
                FoldMetrics(
                    fold=fold_num,
                    is_sharpe=is_sharpe,
                    oos_sharpe=oos_sharpe,
                    is_trades=is_trades,
                    oos_trades=oos_trades,
                )
            )
            previous_fold = fold_def

        return self.aggregate_fold_metrics(folds_metrics)
