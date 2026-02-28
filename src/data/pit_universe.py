"""
Point-in-Time Universe Provider
================================

Provides survivorship-bias-free universe management using historical
S&P 500 composition data.

Key features:
- Returns tickers that were ACTUALLY in the S&P 500 on any given date
- Supports quarterly universe refresh (like real index rebalancing)
- Builds a tradeable_mask DataFrame to prevent signals on dates where
  a ticker wasn't in the index (pre-IPO, post-delist, not yet added)

Data source: sp500/sp500/sp500_ticker_start_end.csv
  - Contains exact entry/exit dates for every S&P 500 member since 1996
  - Empty end_date means ticker is currently active

Usage:
    from src.data.pit_universe import PointInTimeUniverse

    pit = PointInTimeUniverse()

    # Get tickers active on a specific date
    tickers_2020 = pit.get_active_tickers('2020-06-15')

    # Get the full superset across a date range (for data loading)
    all_tickers = pit.get_superset('2019-01-01', '2025-12-31')

    # Build tradeable mask (same shape as engine's self.close)
    mask = pit.build_tradeable_mask(close_df.index, close_df.columns)
"""

import pandas as pd
import numpy as np
from pathlib import Path
from typing import List, Optional, Dict, Tuple
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

# Resolve path relative to project root
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
_DEFAULT_CSV = _PROJECT_ROOT / "sp500" / "sp500" / "sp500_ticker_start_end.csv"
_UPDATED_CSV = (
    _PROJECT_ROOT
    / "sp500"
    / "sp500"
    / "S&P 500 Historical Components & Changes(11-16-2025).csv"
)


class PointInTimeUniverse:
    """
    Point-in-time S&P 500 universe provider.

    Loads historical composition data and answers the question:
    "Which tickers were in the S&P 500 on date X?"

    This eliminates survivorship bias by ensuring:
    - You don't trade stocks that weren't in the index yet
    - You don't miss stocks that were removed (delisted/dropped)
    - Your backtest universe matches what was ACTUALLY available
    """

    def __init__(
        self,
        csv_path: Optional[str] = None,
        refresh_frequency: str = "quarterly",  # 'quarterly', 'monthly', 'annual'
    ):
        """
        Args:
            csv_path: Path to sp500_ticker_start_end.csv. Auto-detected if None.
            refresh_frequency: How often to refresh the universe during a backtest.
                'quarterly' = every 3 months (matches real index rebalancing)
                'monthly' = every month
                'annual' = once per year
        """
        self.refresh_frequency = refresh_frequency

        # Load data
        csv = Path(csv_path) if csv_path else _DEFAULT_CSV
        if not csv.exists():
            raise FileNotFoundError(
                f"Historical S&P 500 data not found at {csv}. "
                f"Expected sp500/sp500/sp500_ticker_start_end.csv in project root."
            )

        self._load_membership_data(csv)
        logger.info(
            f"PointInTimeUniverse: loaded {len(self.memberships)} ticker membership records"
        )

    def _load_membership_data(self, csv_path: Path):
        """Load and parse the ticker start/end CSV."""
        df = pd.read_csv(csv_path)

        # Parse dates
        df["start_date"] = pd.to_datetime(df["start_date"])
        # Empty end_date means currently active -> use a far future date
        df["end_date"] = pd.to_datetime(df["end_date"])
        df["end_date"] = df["end_date"].fillna(pd.Timestamp("2099-12-31"))

        # Normalize ticker names (some have dots that yfinance uses dashes for)
        df["ticker"] = df["ticker"].str.replace(".", "-", regex=False)

        self.memberships = df

        # Build a dict for fast lookup: ticker -> list of (start, end) intervals
        self._intervals: Dict[str, List[Tuple[pd.Timestamp, pd.Timestamp]]] = {}
        for _, row in df.iterrows():
            ticker = row["ticker"]
            if ticker not in self._intervals:
                self._intervals[ticker] = []
            self._intervals[ticker].append((row["start_date"], row["end_date"]))

    def get_active_tickers(self, date: str) -> List[str]:
        """
        Get tickers that were in the S&P 500 on a specific date.

        Args:
            date: Date string (YYYY-MM-DD)

        Returns:
            Sorted list of active ticker symbols
        """
        dt = pd.to_datetime(date)
        active = []

        for ticker, intervals in self._intervals.items():
            for start, end in intervals:
                if start <= dt <= end:
                    active.append(ticker)
                    break  # Found one matching interval, no need to check others

        return sorted(active)

    def get_superset(self, start_date: str, end_date: str) -> List[str]:
        """
        Get ALL tickers that were in the S&P 500 at ANY point during the date range.

        This is used for data loading — you need to download data for all tickers
        that might appear during the backtest, even if they enter/leave mid-period.

        Args:
            start_date: Start of range (YYYY-MM-DD)
            end_date: End of range (YYYY-MM-DD)

        Returns:
            Sorted list of all ticker symbols active at any point in the range
        """
        sd = pd.to_datetime(start_date)
        ed = pd.to_datetime(end_date)
        superset = set()

        for ticker, intervals in self._intervals.items():
            for start, end in intervals:
                # Ticker is relevant if its membership overlaps with [sd, ed]
                if start <= ed and end >= sd:
                    superset.add(ticker)
                    break

        return sorted(superset)

    def get_quarterly_refresh_dates(
        self, start_date: str, end_date: str
    ) -> List[pd.Timestamp]:
        """
        Generate refresh dates for the backtest period.

        Real S&P 500 rebalances happen on the 3rd Friday of March, June, Sept, Dec.
        We approximate with quarter-end dates for simplicity.

        Args:
            start_date: Backtest start
            end_date: Backtest end

        Returns:
            List of refresh timestamps
        """
        sd = pd.to_datetime(start_date)
        ed = pd.to_datetime(end_date)

        if self.refresh_frequency == "quarterly":
            # Quarter-end dates: Mar 31, Jun 30, Sep 30, Dec 31
            dates = pd.date_range(start=sd, end=ed, freq="QE")
        elif self.refresh_frequency == "monthly":
            dates = pd.date_range(start=sd, end=ed, freq="ME")
        elif self.refresh_frequency == "annual":
            dates = pd.date_range(start=sd, end=ed, freq="YE")
        else:
            dates = pd.date_range(start=sd, end=ed, freq="QE")

        # Always include start date as first refresh
        all_dates = [sd] + list(dates)
        # Remove duplicates and sort
        all_dates = sorted(set(all_dates))

        return all_dates

    def build_tradeable_mask(
        self,
        dates_index: pd.DatetimeIndex,
        ticker_columns: List[str],
        close_df: Optional[pd.DataFrame] = None,
        lookback_years: int = 1,
    ) -> pd.DataFrame:
        """
        Build a boolean DataFrame (same shape as price data) indicating
        whether each ticker was tradeable on each date.

        For S&P 500 members:
            True = ticker was in the S&P 500 on that date (membership-based)
            False = not in the index (pre-IPO, post-delist, removed)

        For non-S&P tickers (when close_df is provided):
            Uses data-availability with lag: a ticker is tradeable at a quarterly
            rebalance date if it had at least `lookback_years` of price data
            available before that date. Tradeable status persists until the next
            rebalance. Delisted tickers (data stops) become non-tradeable after
            their last data point. This eliminates look-ahead bias without
            requiring index membership data.

        For non-S&P tickers (when close_df is NOT provided):
            Marked as always tradeable (legacy permissive fallback).

        Args:
            dates_index: DatetimeIndex from the price DataFrame
            ticker_columns: List of ticker symbols (columns of price DataFrame)
            close_df: Optional close price DataFrame for data-availability checks
                on non-S&P tickers. Should have same index/columns as the mask.
            lookback_years: Years of prior data required for non-S&P tickers
                to be considered tradeable at each rebalance (default: 1)

        Returns:
            Boolean DataFrame with same shape as price data
        """
        mask = pd.DataFrame(
            False, index=dates_index, columns=ticker_columns, dtype=bool
        )

        non_sp500_tickers = []
        sp500_count = 0

        for ticker in ticker_columns:
            if ticker in self._intervals:
                sp500_count += 1
                for start, end in self._intervals[ticker]:
                    # Set True for dates within this membership interval
                    mask.loc[(dates_index >= start) & (dates_index <= end), ticker] = (
                        True
                    )
            else:
                non_sp500_tickers.append(ticker)

        # Handle non-S&P tickers
        if non_sp500_tickers:
            if close_df is not None:
                self._apply_data_availability_mask(
                    mask, close_df, non_sp500_tickers, dates_index, lookback_years
                )
                logger.info(
                    f"Non-S&P tickers: {len(non_sp500_tickers)} tickers use "
                    f"data-availability mask (1-year lag, quarterly rebalance)"
                )
            else:
                # Legacy fallback: mark as always tradeable
                for ticker in non_sp500_tickers:
                    mask[ticker] = True
                logger.warning(
                    f"Non-S&P tickers: {len(non_sp500_tickers)} tickers marked as "
                    f"always-tradeable (no close_df provided for availability check)"
                )

        # Count for logging
        total_cells = mask.shape[0] * mask.shape[1]
        tradeable_cells = mask.sum().sum()
        pct = tradeable_cells / total_cells * 100 if total_cells > 0 else 0

        logger.info(
            f"Tradeable mask: {tradeable_cells:,}/{total_cells:,} cells ({pct:.1f}%) "
            f"across {sp500_count} S&P 500 + {len(non_sp500_tickers)} non-S&P tickers, "
            f"{len(dates_index)} trading days"
        )

        return mask

    def _apply_data_availability_mask(
        self,
        mask: pd.DataFrame,
        close_df: pd.DataFrame,
        tickers: List[str],
        dates_index: pd.DatetimeIndex,
        lookback_years: int = 1,
    ):
        """
        For non-S&P tickers, determine tradeability using data-availability
        with a 1-year lag and quarterly rebalance.

        Logic at each quarterly rebalance date:
          - Look at data available UP TO the previous year-end (1-year lag)
          - A ticker is tradeable for the next quarter if:
            (a) It had at least `lookback_years` of price data at that point
            (b) It was still actively trading (has data near the cutoff date)

        Between rebalances, tradeable status is frozen (no look-ahead).
        After a ticker's last data point, it becomes non-tradeable (delisting).

        Args:
            mask: The tradeable mask DataFrame (modified in place)
            close_df: Close price DataFrame
            tickers: List of non-S&P tickers to evaluate
            dates_index: DatetimeIndex
            lookback_years: Minimum years of data required
        """
        if dates_index.empty or not tickers:
            return

        start_date = dates_index[0]
        end_date = dates_index[-1]

        # Generate quarterly rebalance dates (first trading day of each quarter)
        rebalance_dates = self.get_quarterly_refresh_dates(
            start_date.strftime("%Y-%m-%d"), end_date.strftime("%Y-%m-%d")
        )

        # For each rebalance, the "cutoff" is 1 year before — we only look at
        # data that was available up to that point (no look-ahead)
        lookback_delta = pd.DateOffset(years=lookback_years)
        # Minimum trading days required (~252 trading days per year)
        min_data_points = lookback_years * 200  # conservative: 200 instead of 252

        for ticker in tickers:
            if ticker not in close_df.columns:
                # No data at all — leave as False (non-tradeable)
                continue

            ticker_prices = close_df[ticker]
            # Where does this ticker actually have data?
            has_data = ticker_prices.notna()
            # What's the last date with real data? (detects delistings)
            last_data_date = ticker_prices.last_valid_index()

            if last_data_date is None:
                # No valid data at all
                continue

            # Process each rebalance window
            for i, rebalance_date in enumerate(rebalance_dates):
                # Cutoff: data available up to 1 year before this rebalance
                cutoff_date = rebalance_date - lookback_delta

                # Check: does the ticker have enough history before rebalance?
                data_before_rebalance = has_data.loc[has_data.index <= rebalance_date]
                data_count = data_before_rebalance.sum()

                # First data point for this ticker
                first_data_date = ticker_prices.first_valid_index()
                if first_data_date is None:
                    continue

                # Ticker must:
                # 1. Have data starting at least lookback_years before rebalance
                # 2. Have minimum number of data points
                # 3. Still be actively trading (last data >= cutoff)
                has_enough_history = first_data_date <= cutoff_date
                has_enough_points = data_count >= min_data_points
                still_trading = last_data_date >= cutoff_date

                if has_enough_history and has_enough_points and still_trading:
                    # Determine the window this rebalance covers
                    if i + 1 < len(rebalance_dates):
                        window_end = rebalance_dates[i + 1]
                    else:
                        window_end = end_date

                    # Tradeable for this quarter, but NOT beyond last data point
                    # (handles mid-quarter delistings)
                    effective_end = min(window_end, last_data_date)

                    mask.loc[
                        (dates_index >= rebalance_date)
                        & (dates_index <= effective_end),
                        ticker,
                    ] = True

    def build_tradeable_mask_with_data_awareness(
        self,
        close_df: pd.DataFrame,
    ) -> pd.DataFrame:
        """
        Enhanced tradeable mask that also checks for actual data availability.

        A ticker is tradeable on date X if:
        1. It was in the S&P 500 on that date (membership check), AND
        2. It has non-NaN price data on that date (data availability check)

        This catches cases where the membership data says a ticker is active
        but we don't actually have price data for it (gaps, missing downloads).

        Args:
            close_df: Close price DataFrame (dates × tickers)

        Returns:
            Boolean DataFrame
        """
        membership_mask = self.build_tradeable_mask(
            close_df.index, list(close_df.columns), close_df=close_df
        )

        # Also require that price data actually exists (not NaN from pre-IPO ffill)
        has_data = close_df.notna()

        combined = membership_mask & has_data

        logger.info(
            f"Data-aware tradeable mask: {combined.sum().sum():,} tradeable "
            f"(membership: {membership_mask.sum().sum():,}, "
            f"has_data: {has_data.sum().sum():,})"
        )

        return combined

    def get_universe_for_period(
        self, as_of_date: str, lookback_buffer_days: int = 200
    ) -> List[str]:
        """
        Get the universe as it would have been known on a specific date.

        This is the "point-in-time" function: returns tickers that were
        in the S&P 500 on `as_of_date` AND had been trading for at least
        `lookback_buffer_days` (to ensure sufficient pre-history for
        indicators like SMA200).

        Args:
            as_of_date: The date from which perspective we're looking
            lookback_buffer_days: Min trading days the ticker must have existed

        Returns:
            List of tickers that pass both membership and maturity checks
        """
        dt = pd.to_datetime(as_of_date)
        buffer = pd.Timedelta(days=int(lookback_buffer_days * 1.5))  # ~calendar days
        cutoff = dt - buffer

        qualified = []
        for ticker, intervals in self._intervals.items():
            for start, end in intervals:
                if start <= dt <= end and start <= cutoff:
                    qualified.append(ticker)
                    break

        return sorted(qualified)

    def summary(self, start_date: str, end_date: str) -> Dict:
        """Get summary statistics for a backtest period."""
        sd = pd.to_datetime(start_date)
        ed = pd.to_datetime(end_date)

        active_start = self.get_active_tickers(start_date)
        active_end = self.get_active_tickers(end_date)
        superset = self.get_superset(start_date, end_date)

        # Count entries and exits during the period
        entries = self.memberships[
            (self.memberships["start_date"] >= sd)
            & (self.memberships["start_date"] <= ed)
        ]
        exits = self.memberships[
            (self.memberships["end_date"] >= sd)
            & (self.memberships["end_date"] <= ed)
            & (self.memberships["end_date"] < pd.Timestamp("2099-01-01"))
        ]

        return {
            "period": f"{start_date} to {end_date}",
            "active_at_start": len(active_start),
            "active_at_end": len(active_end),
            "superset_total": len(superset),
            "entries_during_period": len(entries),
            "exits_during_period": len(exits),
            "turnover_pct": (len(entries) + len(exits))
            / (2 * max(len(active_start), 1))
            * 100,
        }


if __name__ == "__main__":
    print("=" * 70)
    print("Point-in-Time Universe Provider")
    print("=" * 70)

    pit = PointInTimeUniverse()

    # Test: What was in the S&P on Jan 1, 2020?
    active_2020 = pit.get_active_tickers("2020-01-02")
    print(f"\nS&P 500 on 2020-01-02: {len(active_2020)} tickers")
    print(f"  First 10: {active_2020[:10]}")

    # Test: What was in the S&P on Jan 1, 2025?
    active_2025 = pit.get_active_tickers("2025-01-02")
    print(f"\nS&P 500 on 2025-01-02: {len(active_2025)} tickers")

    # Test: Full superset 2019-2025
    superset = pit.get_superset("2019-01-01", "2025-12-31")
    print(f"\nSuperset 2019-2025: {len(superset)} unique tickers")

    # Test: Summary
    summary = pit.summary("2019-01-01", "2025-12-31")
    print(f"\nSummary:")
    for k, v in summary.items():
        print(f"  {k}: {v}")

    # Test: Quarterly refresh dates
    refresh = pit.get_quarterly_refresh_dates("2019-01-01", "2025-12-31")
    print(f"\nQuarterly refresh dates: {len(refresh)}")
    for d in refresh[:8]:
        active = pit.get_active_tickers(d.strftime("%Y-%m-%d"))
        print(f"  {d.date()}: {len(active)} tickers")

    # Test: Universe for period (with maturity check)
    qualified = pit.get_universe_for_period("2020-01-02", lookback_buffer_days=200)
    print(f"\nQualified (200-day maturity) on 2020-01-02: {len(qualified)} tickers")
