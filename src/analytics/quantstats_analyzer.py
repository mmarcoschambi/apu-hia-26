"""
QuantStats Integration for Trade Analytics
==========================================
Professional-grade performance analytics using QuantStats library.

CRITICAL: Handles partial exits correctly by grouping all exit phases
(TP1, TP2, RUNNER) into single complete trades for accurate metrics.

Key Features:
1. Trade Grouping: Merges partial exits into complete trades
2. Daily Returns: Converts trade-based results to daily equity curve
3. QuantStats Metrics: Sharpe, Sortino, drawdowns, VaR, etc.
4. Benchmark Comparison: Compare against SPY, QQQ, etc.
5. Professional Reports: HTML tearsheets and visualizations
"""

import pandas as pd
import numpy as np
import quantstats as qs
from typing import Dict, List, Tuple, Optional
from pathlib import Path
import logging
from datetime import datetime
import warnings
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages

warnings.filterwarnings("ignore")
logger = logging.getLogger(__name__)

# Configure QuantStats
qs.extend_pandas()


class TradeGrouper:
    """
    Groups partial exit trades into complete trades.

    CRITICAL: Prevents distortion from counting TP1, TP2, RUNNER as separate trades.
    All exits with same (ticker, entry_date) are grouped as ONE trade.
    """

    @staticmethod
    def group_partial_trades(trade_log: pd.DataFrame) -> pd.DataFrame:
        """
        Group partial exits (TP1, TP2, RUNNER, STOP) into complete trades.

        Args:
            trade_log: DataFrame with columns: ticker, entry_date, exit_date,
                      entry_price, exit_price, shares, pnl, exit_phase

        Returns:
            DataFrame with ONE row per complete trade containing:
            - total_pnl: Sum of all partial exit PnLs
            - total_shares: Sum of all shares exited
            - avg_exit_price: Weighted average exit price
            - final_exit_date: Last exit date
            - exit_phases: List of all exit phases (e.g., "TP1,TP2,STOP")
            - hold_days: Days from entry to final exit
            - r_multiple: Total PnL / Total Risk
        """
        if trade_log.empty:
            logger.warning("Empty trade log provided")
            return pd.DataFrame()

        logger.info(
            f"📊 Grouping {len(trade_log)} trade events into complete trades..."
        )

        # Ensure dates are datetime
        trade_log["entry_date"] = pd.to_datetime(trade_log["entry_date"])
        trade_log["exit_date"] = pd.to_datetime(trade_log["exit_date"])

        # Group by (ticker, entry_date) - this identifies a single trade
        # Build aggregation dict dynamically based on available columns
        agg_dict = {
            "exit_date": "max",  # Final exit date
            "entry_price": "first",  # Entry price (same for all partials)
            "exit_price": lambda x: np.average(
                x, weights=trade_log.loc[x.index, "shares"]
            ),  # Weighted avg
            "shares": "sum",  # Total shares
            "pnl": "sum",  # Total P&L
            "exit_phase": lambda x: ",".join(sorted(set(x))),  # All phases
        }

        # Optional columns - only include if they exist
        optional_cols = [
            "entry_signal",
            "context_adr",
            "context_rvol",
            "context_trend",
            "dist_sma20_pct",
            "consolidation_days",
            "sector",
            "sector_strength",
            "vix_regime",
            "spy_above_ema20",
            "base_risk_dollars",
            "adjusted_risk_dollars",
            "risk_reduction_factor",
            "rvol_classification",
            "volatility_regime",
            "is_vcp_pattern",
            "stop_loss",
            "tp1_target",
            "tp2_target",
            "entry_score",  # Entry Quality Score
            "pattern_type",
            "pattern_confidence",
            "pivot_price",
            "rs_percentile",
            "rs_score",
        ]

        for col in optional_cols:
            if col in trade_log.columns:
                agg_dict[col] = "first"

        grouped = (
            trade_log.groupby(["ticker", "entry_date"]).agg(agg_dict).reset_index()
        )

        # Rename columns for clarity
        grouped.rename(
            columns={
                "exit_date": "final_exit_date",
                "shares": "total_shares",
                "pnl": "total_pnl",
                "exit_phase": "exit_phases",
            },
            inplace=True,
        )

        # Calculate derived metrics
        grouped["hold_days"] = (
            grouped["final_exit_date"] - grouped["entry_date"]
        ).dt.days

        # Calculate total R-multiple (PnL / Risk)
        # Risk = adjusted_risk_dollars (this is the actual $ risked on the trade)
        if "adjusted_risk_dollars" in grouped.columns:
            grouped["r_multiple"] = grouped.apply(
                lambda row: row["total_pnl"] / row["adjusted_risk_dollars"]
                if row["adjusted_risk_dollars"] > 0
                else 0,
                axis=1,
            )
        else:
            grouped["r_multiple"] = 0.0

        # Calculate returns %
        cost_basis = grouped["entry_price"] * grouped["total_shares"]
        grouped["return_pct"] = (grouped["total_pnl"] / cost_basis * 100).fillna(0)

        # Trade outcome classification
        def classify_outcome(row):
            r = row["r_multiple"]
            if r >= 3.0:
                return "BIG_WIN"
            elif r >= 1.0:
                return "WIN"
            elif r >= 0:
                return "SMALL_WIN"
            elif r >= -0.5:
                return "SMALL_LOSS"
            else:
                return "BIG_LOSS"

        grouped["outcome_category"] = grouped.apply(classify_outcome, axis=1)

        # Win/Loss flags
        grouped["is_winner"] = grouped["total_pnl"] > 0
        grouped["was_stopped_out"] = grouped["exit_phases"].str.contains("STOP")
        grouped["hit_tp1"] = grouped["exit_phases"].str.contains("TP1")
        grouped["hit_tp2"] = grouped["exit_phases"].str.contains("TP2")
        grouped["had_runner"] = grouped["exit_phases"].str.contains("RUNNER")

        logger.info(f"✅ Grouped into {len(grouped)} complete trades")
        logger.info(f"   Winners: {grouped['is_winner'].sum()}")
        logger.info(f"   Losers: {(~grouped['is_winner']).sum()}")
        logger.info(f"   Stopped Out: {grouped['was_stopped_out'].sum()}")

        return grouped


class EquityCurveBuilder:
    """
    Converts trade-based results into daily equity curve.
    Required for QuantStats time-series analysis.
    """

    @staticmethod
    def build_daily_returns(
        complete_trades: pd.DataFrame,
        initial_capital: float = 100000,
        start_date: str = None,
        end_date: str = None,
    ) -> pd.Series:
        """
        Build daily returns series from complete trades.

        Args:
            complete_trades: DataFrame from TradeGrouper.group_partial_trades()
            initial_capital: Starting portfolio value
            start_date: Start of backtest period
            end_date: End of backtest period

        Returns:
            pd.Series: Daily returns indexed by date
        """
        if complete_trades.empty:
            logger.warning("No trades to build equity curve")
            return pd.Series(dtype=float)

        # Determine date range
        if start_date is None:
            start_date = complete_trades["entry_date"].min()
        if end_date is None:
            end_date = complete_trades["final_exit_date"].max()

        start_date = pd.to_datetime(start_date)
        end_date = pd.to_datetime(end_date)

        # Create daily date range
        date_range = pd.date_range(start=start_date, end=end_date, freq="D")

        # Initialize equity curve
        equity = pd.Series(initial_capital, index=date_range)
        daily_pnl = pd.Series(0.0, index=date_range)

        # Add PnL on exit dates
        for _, trade in complete_trades.iterrows():
            exit_date = trade["final_exit_date"]
            if exit_date in daily_pnl.index:
                daily_pnl[exit_date] += trade["total_pnl"]

        # Build cumulative equity
        for i in range(1, len(equity)):
            equity.iloc[i] = equity.iloc[i - 1] + daily_pnl.iloc[i]

        # Calculate daily returns
        daily_returns = equity.pct_change().fillna(0)

        logger.info(
            f"📈 Built equity curve: ${equity.iloc[0]:,.0f} → ${equity.iloc[-1]:,.0f}"
        )
        logger.info(
            f"   Total Return: {((equity.iloc[-1] / equity.iloc[0] - 1) * 100):.2f}%"
        )

        return daily_returns


class QuantStatsAnalyzer:
    """
    Professional analytics using QuantStats with proper trade grouping.
    """

    def __init__(
        self,
        trade_log: pd.DataFrame,
        initial_capital: float = 100000,
        benchmark_ticker: str = "SPY",
    ):
        """
        Initialize analyzer with raw trade log (including partial exits).

        Args:
            trade_log: Raw trade log DataFrame (may contain partial exits)
            initial_capital: Starting capital
            benchmark_ticker: Benchmark symbol for comparison (default: SPY)
        """
        self.raw_trade_log = trade_log
        self.initial_capital = initial_capital
        self.benchmark_ticker = benchmark_ticker

        # Group partial trades into complete trades
        self.complete_trades = TradeGrouper.group_partial_trades(trade_log)
        self.grouped_trades = self.complete_trades  # Alias for backward compatibility

        # Build daily returns
        if not self.complete_trades.empty:
            self.daily_returns = EquityCurveBuilder.build_daily_returns(
                self.complete_trades, initial_capital=initial_capital
            )
        else:
            self.daily_returns = pd.Series(dtype=float)

    def get_trade_metrics(self) -> Dict:
        """
        Calculate trade-based metrics (not time-series based).
        These are accurate because we use complete trades.
        """
        if self.complete_trades.empty:
            return {}

        trades = self.complete_trades

        # Basic counts
        total_trades = len(trades)
        winners = trades["is_winner"].sum()
        losers = total_trades - winners

        # Win rate
        win_rate = (winners / total_trades * 100) if total_trades > 0 else 0

        # P&L metrics
        total_pnl = trades["total_pnl"].sum()
        avg_win = trades[trades["is_winner"]]["total_pnl"].mean() if winners > 0 else 0
        avg_loss = trades[~trades["is_winner"]]["total_pnl"].mean() if losers > 0 else 0

        # Profit factor
        gross_profit = trades[trades["is_winner"]]["total_pnl"].sum()
        gross_loss = abs(trades[~trades["is_winner"]]["total_pnl"].sum())
        profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else np.inf

        # R-Multiple metrics
        avg_r = trades["r_multiple"].mean()
        median_r = trades["r_multiple"].median()
        best_r = trades["r_multiple"].max()
        worst_r = trades["r_multiple"].min()

        # Hold time
        avg_hold_days = trades["hold_days"].mean()

        # Exit analysis
        stopped_out = trades["was_stopped_out"].sum()
        hit_tp1 = trades["hit_tp1"].sum()
        hit_tp2 = trades["hit_tp2"].sum()
        had_runner = trades["had_runner"].sum()

        return {
            "total_trades": total_trades,
            "winners": winners,
            "losers": losers,
            "win_rate_pct": win_rate,
            "total_pnl": total_pnl,
            "avg_win": avg_win,
            "avg_loss": avg_loss,
            "profit_factor": profit_factor,
            "avg_r_multiple": avg_r,
            "median_r_multiple": median_r,
            "best_r_multiple": best_r,
            "worst_r_multiple": worst_r,
            "avg_hold_days": avg_hold_days,
            "stopped_out": stopped_out,
            "hit_tp1": hit_tp1,
            "hit_tp2": hit_tp2,
            "had_runner": had_runner,
        }

    def get_quantstats_metrics(self, benchmark_data: pd.Series = None) -> Dict:
        """
        Calculate QuantStats time-series metrics.

        Args:
            benchmark_data: Optional benchmark returns series

        Returns:
            Dictionary of QuantStats metrics
        """
        if self.daily_returns.empty:
            logger.warning("No daily returns available")
            return {}

        returns = self.daily_returns

        metrics = {
            # Risk-adjusted returns
            "sharpe_ratio": qs.stats.sharpe(returns),
            "sortino_ratio": qs.stats.sortino(returns),
            "calmar_ratio": qs.stats.calmar(returns),
            "omega_ratio": qs.stats.omega(returns),
            # Returns
            "total_return": qs.stats.comp(returns),
            "cagr": qs.stats.cagr(returns),
            "avg_return": returns.mean(),
            "avg_return_annual": returns.mean() * 252,
            # Volatility
            "volatility_annual": qs.stats.volatility(returns),
            "downside_volatility": returns[returns < 0].std() * np.sqrt(252),
            # Drawdown
            "max_drawdown": qs.stats.max_drawdown(returns),
            "avg_drawdown": self._calculate_avg_drawdown(returns),
            "avg_drawdown_days": self._calculate_avg_drawdown_days(returns),
            # Risk metrics
            "var_95": qs.stats.value_at_risk(returns, sigma=2),  # 95% VaR
            "cvar_95": qs.stats.conditional_value_at_risk(
                returns, sigma=2
            ),  # Expected Shortfall
            # Distribution
            "skewness": qs.stats.skew(returns),
            "kurtosis": qs.stats.kurtosis(returns),
            # Streaks
            "best_day": returns.max(),
            "worst_day": returns.min(),
            "win_days": (returns > 0).sum(),
            "loss_days": (returns < 0).sum(),
        }

        # Add trade-specific metrics if trade log exists
        if hasattr(self, "grouped_trades") and not self.grouped_trades.empty:
            trades = self.grouped_trades

            # Win/Loss statistics
            winning_trades = trades[trades["total_pnl"] > 0]
            losing_trades = trades[trades["total_pnl"] < 0]

            metrics["total_trades"] = len(trades)
            metrics["winning_trades"] = len(winning_trades)
            metrics["losing_trades"] = len(losing_trades)
            metrics["win_rate"] = (
                len(winning_trades) / len(trades) if len(trades) > 0 else 0
            )

            # Profit metrics
            total_wins = (
                winning_trades["total_pnl"].sum() if len(winning_trades) > 0 else 0
            )
            total_losses = (
                abs(losing_trades["total_pnl"].sum()) if len(losing_trades) > 0 else 1
            )
            metrics["profit_factor"] = (
                total_wins / total_losses if total_losses > 0 else 0
            )

            metrics["avg_win"] = (
                winning_trades["total_pnl"].mean() if len(winning_trades) > 0 else 0
            )
            metrics["avg_loss"] = (
                losing_trades["total_pnl"].mean() if len(losing_trades) > 0 else 0
            )
            metrics["avg_win_loss_ratio"] = (
                abs(metrics["avg_win"] / metrics["avg_loss"])
                if metrics["avg_loss"] != 0
                else 0
            )

            metrics["largest_win"] = (
                winning_trades["total_pnl"].max() if len(winning_trades) > 0 else 0
            )
            metrics["largest_loss"] = (
                losing_trades["total_pnl"].min() if len(losing_trades) > 0 else 0
            )

            # Holding periods
            if "hold_days" in trades.columns:
                metrics["avg_holding_period"] = trades["hold_days"].mean()
                metrics["max_holding_period"] = trades["hold_days"].max()

            # Consecutive streaks
            pnl_series = trades.sort_values("final_exit_date")["total_pnl"]
            wins = (pnl_series > 0).astype(int)
            losses = (pnl_series < 0).astype(int)

            def max_consecutive(series):
                if len(series) == 0:
                    return 0
                max_streak = 0
                current_streak = 0
                for val in series:
                    if val == 1:
                        current_streak += 1
                        max_streak = max(max_streak, current_streak)
                    else:
                        current_streak = 0
                return max_streak

            metrics["max_consecutive_wins"] = max_consecutive(wins.values)
            metrics["max_consecutive_losses"] = max_consecutive(losses.values)

        # Exposure time (% of time in market)
        if not returns.empty:
            # Count days with non-zero returns as market exposure
            exposure_days = (returns != 0).sum()
            total_days = len(returns)
            metrics["exposure_time_pct"] = (
                (exposure_days / total_days * 100) if total_days > 0 else 0
            )

        # Benchmark comparison if provided
        if benchmark_data is not None:
            # Align dates
            aligned_returns, aligned_benchmark = returns.align(
                benchmark_data, join="inner"
            )

            if len(aligned_returns) > 0:
                try:
                    greeks = qs.stats.greeks(aligned_returns, aligned_benchmark)
                    metrics["alpha"] = greeks["alpha"]
                    metrics["beta"] = greeks["beta"]
                except Exception as e:
                    logger.warning(f"Could not calculate greeks: {e}")
                    metrics["alpha"] = 0
                    metrics["beta"] = 0

                metrics["correlation"] = aligned_returns.corr(aligned_benchmark)
                metrics["information_ratio"] = qs.stats.information_ratio(
                    aligned_returns, aligned_benchmark
                )

                # Tracking error
                tracking_diff = aligned_returns - aligned_benchmark
                metrics["tracking_error"] = tracking_diff.std() * np.sqrt(252)

                metrics["benchmark_total_return"] = qs.stats.comp(aligned_benchmark)
                metrics["benchmark_cagr"] = qs.stats.cagr(aligned_benchmark)
                metrics["excess_return"] = (
                    metrics["total_return"] - metrics["benchmark_total_return"]
                )

        return metrics

    def generate_report(
        self, output_dir: str = "outputs/quantstats", benchmark_ticker: str = None
    ) -> str:
        """
        Generate complete QuantStats HTML report.

        Args:
            output_dir: Directory to save report
            benchmark_ticker: Benchmark ticker (default: self.benchmark_ticker)

        Returns:
            Path to generated HTML report
        """
        if self.daily_returns.empty:
            logger.error("Cannot generate report: No returns data")
            return None

        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_file = output_path / f"tearsheet_{timestamp}.html"

        # Download benchmark if specified
        benchmark = None
        if benchmark_ticker:
            try:
                import yfinance as yf

                start = self.daily_returns.index.min()
                end = self.daily_returns.index.max()
                bench_data = yf.download(
                    benchmark_ticker, start=start, end=end, progress=False
                )

                if not bench_data.empty:
                    if isinstance(bench_data.columns, pd.MultiIndex):
                        benchmark = (
                            bench_data["Close"].iloc[:, 0].pct_change().fillna(0)
                        )
                    else:
                        benchmark = bench_data["Close"].pct_change().fillna(0)

                    logger.info(f"✅ Loaded benchmark: {benchmark_ticker}")
            except Exception as e:
                logger.warning(f"Could not load benchmark {benchmark_ticker}: {e}")

        # Generate report
        logger.info(f"📊 Generating QuantStats tearsheet...")

        # Ensure alignment between strategy returns and benchmark
        if benchmark is not None:
            # Reindex benchmark to match strategy returns index, filling with 0
            # This ensures they have exactly the same dates for rolling calculations
            benchmark = benchmark.reindex(self.daily_returns.index).fillna(0)

        import matplotlib.pyplot as plt

        try:
            plt.rcParams["font.sans-serif"] = [
                "DejaVu Sans",
                "Liberation Sans",
                "Arial",
            ]
        except Exception:
            pass

        qs.reports.html(
            self.daily_returns,
            benchmark=benchmark,
            output=str(report_file),
            title=f"Trading Strategy Performance Report - {timestamp}",
        )

        logger.info(f"✅ Report saved: {report_file}")
        return str(report_file)

    def generate_pdf_report(
        self,
        output_dir: str = "outputs/quantstats",
        benchmark_ticker: str = None,
        skip_snapshot: bool = False,
    ) -> str:
        """
        Generate complete QuantStats PDF report by stitching together multiple plots.

        Args:
            output_dir: Directory to save report
            benchmark_ticker: Benchmark ticker
            skip_snapshot: Skip the snapshot page if it has quantiles rendering issues

        Returns:
            Path to generated PDF report
        """
        if self.daily_returns.empty:
            logger.error("Cannot generate PDF: No returns data")
            return None

        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_file = output_path / f"tearsheet_{timestamp}.pdf"

        # Download benchmark if specified
        benchmark = None
        if benchmark_ticker:
            try:
                import yfinance as yf

                start = self.daily_returns.index.min()
                end = self.daily_returns.index.max()
                bench_data = yf.download(
                    benchmark_ticker, start=start, end=end, progress=False
                )

                if not bench_data.empty:
                    if isinstance(bench_data.columns, pd.MultiIndex):
                        benchmark = (
                            bench_data["Close"].iloc[:, 0].pct_change().fillna(0)
                        )
                    else:
                        benchmark = bench_data["Close"].pct_change().fillna(0)
                    # Align benchmark
                    benchmark = benchmark.reindex(self.daily_returns.index).fillna(0)
            except Exception as e:
                logger.warning(f"Could not load benchmark {benchmark_ticker}: {e}")

        # Get comprehensive metrics
        metrics = self.get_quantstats_metrics(benchmark_data=benchmark)

        logger.info(f"📊 Generating QuantStats PDF tearsheet...")

        try:
            with PdfPages(report_file) as pdf:
                # Page 1: Key Metrics Summary Table
                try:
                    fig = self._create_metrics_summary_page(metrics, benchmark_ticker)
                    pdf.savefig(fig, bbox_inches="tight")
                    plt.close(fig)
                    logger.info("✅ Page 1: Metrics Summary")
                except Exception as e:
                    logger.warning(f"⚠️  Skipped Metrics Summary page: {e}")

                # Page 2: Snapshot (Summary) - SKIP IF PROBLEMATIC
                if not skip_snapshot:
                    try:
                        fig = qs.plots.snapshot(
                            self.daily_returns,
                            benchmark=benchmark,
                            show=False,
                            title="Strategy Performance Summary",
                        )
                        pdf.savefig(fig)
                        plt.close(fig)
                        logger.info("✅ Page 2: Snapshot")
                    except Exception as e:
                        logger.warning(
                            f"⚠️  Skipped Snapshot page (known quantiles issue): {e}"
                        )
                        logger.info(
                            "   💡 Tip: Use skip_snapshot=True to avoid this warning"
                        )

                # Page 3: Returns and Drawdown
                try:
                    fig = qs.plots.returns(
                        self.daily_returns, benchmark=benchmark, show=False
                    )
                    pdf.savefig(fig)
                    plt.close(fig)
                    logger.info("✅ Page 3: Returns")
                except Exception as e:
                    logger.warning(f"⚠️  Skipped Returns plot: {e}")

                try:
                    fig = qs.plots.drawdown(self.daily_returns, show=False)
                    pdf.savefig(fig)
                    plt.close(fig)
                    logger.info("✅ Page 4: Drawdown")
                except Exception as e:
                    logger.warning(f"⚠️  Skipped Drawdown plot: {e}")

                # Page 4: Heatmap and Annual Returns
                try:
                    fig = qs.plots.monthly_heatmap(self.daily_returns, show=False)
                    pdf.savefig(fig)
                    plt.close(fig)
                    logger.info("✅ Page 5: Monthly Heatmap")
                except Exception as e:
                    logger.warning(f"⚠️  Skipped Monthly Heatmap: {e}")

                try:
                    fig = qs.plots.yearly_returns(self.daily_returns, show=False)
                    pdf.savefig(fig)
                    plt.close(fig)
                    logger.info("✅ Page 6: Yearly Returns")
                except Exception as e:
                    logger.warning(f"⚠️  Skipped Yearly Returns: {e}")

                # Page 5: Risk Metrics
                if len(self.daily_returns) > 30:
                    try:
                        fig = qs.plots.rolling_sharpe(self.daily_returns, show=False)
                        pdf.savefig(fig)
                        plt.close(fig)
                        logger.info("✅ Page 7: Rolling Sharpe")
                    except Exception as e:
                        logger.warning(f"⚠️  Skipped Rolling Sharpe: {e}")

                    try:
                        fig = qs.plots.rolling_volatility(
                            self.daily_returns, show=False
                        )
                        pdf.savefig(fig)
                        plt.close(fig)
                        logger.info("✅ Page 8: Rolling Volatility")
                    except Exception as e:
                        logger.warning(f"⚠️  Skipped Rolling Volatility: {e}")

                if benchmark is not None and len(self.daily_returns) > 60:
                    try:
                        fig = qs.plots.rolling_beta(
                            self.daily_returns, benchmark, show=False
                        )
                        pdf.savefig(fig)
                        plt.close(fig)
                        logger.info("✅ Page 9: Rolling Beta")
                    except Exception as e:
                        logger.warning(f"⚠️  Skipped Rolling Beta: {e}")

                # Page 6: Distributions - WITH FALLBACK
                try:
                    fig = qs.plots.distribution(self.daily_returns, show=False)
                    pdf.savefig(fig)
                    plt.close(fig)
                    logger.info("✅ Page 10: Distribution (QuantStats)")
                except Exception as e:
                    logger.warning(f"⚠️  QuantStats distribution failed: {e}")
                    logger.info("📊 Generating simple distribution plot...")
                    try:
                        fig = self._create_simple_distribution_plot()
                        pdf.savefig(fig)
                        plt.close(fig)
                        logger.info("✅ Page 10: Distribution (Simple Fallback)")
                    except Exception as e2:
                        logger.error(f"❌ Both distribution plots failed: {e2}")

                # Page 11: Trade Analytics (Entry Score, RS, Position Sizing)
                try:
                    from src.analytics.trade_analytics import (
                        generate_full_trade_analysis,
                    )

                    if hasattr(self, "trade_log") and not self.trade_log.empty:
                        analysis = generate_full_trade_analysis(self.trade_log)

                        fig = self._create_trade_analysis_page(analysis)
                        pdf.savefig(fig, bbox_inches="tight")
                        plt.close(fig)
                        logger.info(
                            "✅ Page 11: Trade Analytics (Entry Score, RS, Position Sizing)"
                        )
                except Exception as e:
                    logger.warning(f"⚠️ Skipped Trade Analytics page: {e}")

            logger.info(f"✅ PDF Report saved: {report_file}")
            return str(report_file)
        except Exception as e:
            logger.error(f"Error generating PDF report: {e}")
            import traceback

            logger.error(traceback.format_exc())
            return None

    def _create_metrics_summary_page(
        self, metrics: Dict, benchmark_ticker: str = None
    ) -> plt.Figure:
        """Create a comprehensive metrics summary page for PDF report."""
        fig, axes = plt.subplots(3, 2, figsize=(11, 14))
        fig.suptitle(
            "Performance Metrics Summary", fontsize=16, fontweight="bold", y=0.995
        )

        # Helper function to format metrics
        def fmt_pct(val, decimals=2):
            return (
                f"{val * 100:.{decimals}f}%"
                if val is not None and not np.isnan(val)
                else "N/A"
            )

        def fmt_num(val, decimals=2):
            return (
                f"{val:.{decimals}f}"
                if val is not None and not np.isnan(val)
                else "N/A"
            )

        def fmt_int(val):
            return f"{int(val)}" if val is not None and not np.isnan(val) else "N/A"

        # Section 1: Risk-Adjusted Returns
        ax1 = axes[0, 0]
        ax1.axis("off")
        risk_adj_data = [
            ["CAGR", fmt_pct(metrics.get("cagr", 0))],
            ["Sharpe Ratio", fmt_num(metrics.get("sharpe_ratio", 0))],
            ["Sortino Ratio", fmt_num(metrics.get("sortino_ratio", 0))],
            ["Calmar Ratio", fmt_num(metrics.get("calmar_ratio", 0))],
            ["Omega Ratio", fmt_num(metrics.get("omega_ratio", 0))],
        ]
        table1 = ax1.table(
            cellText=risk_adj_data,
            colLabels=["Risk-Adjusted Returns", "Value"],
            cellLoc="left",
            loc="center",
            colWidths=[0.6, 0.4],
        )
        table1.auto_set_font_size(False)
        table1.set_fontsize(9)
        table1.scale(1, 2)
        self._style_table(table1)

        # Section 2: Trade Statistics
        ax2 = axes[0, 1]
        ax2.axis("off")
        trade_data = [
            ["Total Trades", fmt_int(metrics.get("total_trades", 0))],
            ["Win Rate", fmt_pct(metrics.get("win_rate", 0))],
            ["Profit Factor", fmt_num(metrics.get("profit_factor", 0))],
            ["Avg Win/Avg Loss", fmt_num(metrics.get("avg_win_loss_ratio", 0))],
            [
                "Avg Holding Period",
                fmt_num(metrics.get("avg_holding_period", 0), 1) + " days",
            ],
        ]
        table2 = ax2.table(
            cellText=trade_data,
            colLabels=["Trade Statistics", "Value"],
            cellLoc="left",
            loc="center",
            colWidths=[0.6, 0.4],
        )
        table2.auto_set_font_size(False)
        table2.set_fontsize(9)
        table2.scale(1, 2)
        self._style_table(table2)

        # Section 3: Risk Metrics
        ax3 = axes[1, 0]
        ax3.axis("off")
        risk_data = [
            ["Max Drawdown", fmt_pct(metrics.get("max_drawdown", 0))],
            ["Avg Drawdown", fmt_pct(metrics.get("avg_drawdown", 0))],
            ["VaR (95%)", fmt_pct(metrics.get("var_95", 0))],
            ["CVaR (95%)", fmt_pct(metrics.get("cvar_95", 0))],
            ["Volatility (Annual)", fmt_pct(metrics.get("volatility_annual", 0))],
        ]
        table3 = ax3.table(
            cellText=risk_data,
            colLabels=["Risk Metrics", "Value"],
            cellLoc="left",
            loc="center",
            colWidths=[0.6, 0.4],
        )
        table3.auto_set_font_size(False)
        table3.set_fontsize(9)
        table3.scale(1, 2)
        self._style_table(table3)

        # Section 4: Distribution & Streaks
        ax4 = axes[1, 1]
        ax4.axis("off")
        dist_data = [
            ["Skewness", fmt_num(metrics.get("skewness", 0), 3)],
            ["Kurtosis", fmt_num(metrics.get("kurtosis", 0), 3)],
            ["Max Consecutive Wins", fmt_int(metrics.get("max_consecutive_wins", 0))],
            [
                "Max Consecutive Losses",
                fmt_int(metrics.get("max_consecutive_losses", 0)),
            ],
            ["Exposure Time", fmt_pct(metrics.get("exposure_time_pct", 0) / 100)],
        ]
        table4 = ax4.table(
            cellText=dist_data,
            colLabels=["Distribution & Exposure", "Value"],
            cellLoc="left",
            loc="center",
            colWidths=[0.6, 0.4],
        )
        table4.auto_set_font_size(False)
        table4.set_fontsize(9)
        table4.scale(1, 2)
        self._style_table(table4)

        # Section 5: Benchmark Comparison (if available)
        ax5 = axes[2, 0]
        ax5.axis("off")
        if benchmark_ticker and metrics.get("alpha") is not None:
            bench_data = [
                [f"Alpha vs {benchmark_ticker}", fmt_num(metrics.get("alpha", 0))],
                [f"Beta vs {benchmark_ticker}", fmt_num(metrics.get("beta", 0))],
                ["Information Ratio", fmt_num(metrics.get("information_ratio", 0))],
                ["Tracking Error", fmt_pct(metrics.get("tracking_error", 0))],
                ["Excess Return", fmt_pct(metrics.get("excess_return", 0))],
            ]
            table5 = ax5.table(
                cellText=bench_data,
                colLabels=["Benchmark Comparison", "Value"],
                cellLoc="left",
                loc="center",
                colWidths=[0.6, 0.4],
            )
            table5.auto_set_font_size(False)
            table5.set_fontsize(9)
            table5.scale(1, 2)
            self._style_table(table5)
        else:
            ax5.text(
                0.5, 0.5, "No Benchmark Data", ha="center", va="center", fontsize=12
            )

        # Section 6: Win/Loss Details
        ax6 = axes[2, 1]
        ax6.axis("off")
        wl_data = [
            ["Winning Trades", fmt_int(metrics.get("winning_trades", 0))],
            ["Losing Trades", fmt_int(metrics.get("losing_trades", 0))],
            ["Avg Win", f"${fmt_num(metrics.get('avg_win', 0), 0)}"],
            ["Avg Loss", f"${fmt_num(metrics.get('avg_loss', 0), 0)}"],
            ["Largest Win", f"${fmt_num(metrics.get('largest_win', 0), 0)}"],
        ]
        table6 = ax6.table(
            cellText=wl_data,
            colLabels=["Win/Loss Details", "Value"],
            cellLoc="left",
            loc="center",
            colWidths=[0.6, 0.4],
        )
        table6.auto_set_font_size(False)
        table6.set_fontsize(9)
        table6.scale(1, 2)
        self._style_table(table6)

        plt.tight_layout(rect=[0, 0, 1, 0.99])
        return fig

    def _style_table(self, table):
        """Apply consistent styling to tables."""
        for (i, j), cell in table.get_celld().items():
            if i == 0:  # Header row
                cell.set_facecolor("#2c3e50")
                cell.set_text_props(weight="bold", color="white")
            else:
                cell.set_facecolor("#34495e" if i % 2 == 0 else "#2c3e50")
                cell.set_text_props(color="white")
            cell.set_edgecolor("white")

    def _create_simple_distribution_plot(self) -> plt.Figure:
        """Simple distribution plot as fallback when QuantStats fails."""
        fig, axes = plt.subplots(2, 2, figsize=(12, 10))
        fig.suptitle("Returns Distribution Analysis", fontsize=14, fontweight="bold")

        # 1. Daily returns histogram
        axes[0, 0].hist(
            self.daily_returns.dropna(),
            bins=50,
            color="steelblue",
            edgecolor="black",
            alpha=0.7,
        )
        axes[0, 0].set_title("Daily Returns Distribution")
        axes[0, 0].set_xlabel("Return (%)")
        axes[0, 0].set_ylabel("Frequency")
        axes[0, 0].axvline(0, color="red", linestyle="--", linewidth=2, alpha=0.5)
        axes[0, 0].grid(alpha=0.3)

        # 2. Weekly returns histogram
        if len(self.daily_returns) > 30:
            weekly = self.daily_returns.resample("W").sum()
            axes[0, 1].hist(
                weekly.dropna(),
                bins=min(30, len(weekly) // 2),
                color="orange",
                edgecolor="black",
                alpha=0.7,
            )
            axes[0, 1].set_title("Weekly Returns Distribution")
            axes[0, 1].set_xlabel("Return (%)")
            axes[0, 1].set_ylabel("Frequency")
            axes[0, 1].axvline(0, color="red", linestyle="--", linewidth=2, alpha=0.5)
            axes[0, 1].grid(alpha=0.3)
        else:
            axes[0, 1].text(
                0.5,
                0.5,
                "Insufficient data\nfor weekly returns",
                ha="center",
                va="center",
                fontsize=12,
            )
            axes[0, 1].axis("off")

        # 3. Box plot
        try:
            bp = axes[1, 0].boxplot(
                [self.daily_returns.dropna()], vert=True, patch_artist=True
            )
            bp["boxes"][0].set_facecolor("lightblue")
            bp["medians"][0].set_color("red")
            bp["medians"][0].set_linewidth(2)
            axes[1, 0].set_title("Daily Returns Box Plot")
            axes[1, 0].set_ylabel("Return (%)")
            axes[1, 0].axhline(0, color="red", linestyle="--", linewidth=2, alpha=0.5)
            axes[1, 0].grid(alpha=0.3)
        except Exception as e:
            logger.warning(f"Box plot failed: {e}")
            axes[1, 0].text(
                0.5, 0.5, "Box plot unavailable", ha="center", va="center", fontsize=12
            )
            axes[1, 0].axis("off")

        # 4. Cumulative returns
        cumulative = (1 + self.daily_returns).cumprod() - 1
        axes[1, 1].plot(
            cumulative.index, cumulative.values * 100, color="green", linewidth=2
        )
        axes[1, 1].set_title("Cumulative Returns")
        axes[1, 1].set_xlabel("Date")
        axes[1, 1].set_ylabel("Return (%)")
        axes[1, 1].axhline(0, color="red", linestyle="--", linewidth=2, alpha=0.5)
        axes[1, 1].grid(alpha=0.3)
        axes[1, 1].tick_params(axis="x", rotation=45)

        plt.tight_layout()
        return fig

    def print_summary(self):
        """Print comprehensive summary to console."""
        print("\n" + "=" * 80)
        print("QUANTSTATS PERFORMANCE ANALYSIS")
        print("=" * 80 + "\n")

        # Trade-based metrics
        print("📊 TRADE METRICS (Complete Trades)")
        print("-" * 80)
        trade_metrics = self.get_trade_metrics()

        if trade_metrics:
            print(f"Total Trades:        {trade_metrics['total_trades']}")
            print(
                f"Winners:             {trade_metrics['winners']} ({trade_metrics['win_rate_pct']:.1f}%)"
            )
            print(f"Losers:              {trade_metrics['losers']}")
            print(f"Stopped Out:         {trade_metrics['stopped_out']}")
            print(f"\nP&L Metrics:")
            print(f"Total P&L:           ${trade_metrics['total_pnl']:,.2f}")
            print(f"Avg Win:             ${trade_metrics['avg_win']:,.2f}")
            print(f"Avg Loss:            ${trade_metrics['avg_loss']:,.2f}")
            print(f"Profit Factor:       {trade_metrics['profit_factor']:.2f}")
            print(f"\nR-Multiple Analysis:")
            print(f"Average R:           {trade_metrics['avg_r_multiple']:+.2f}R")
            print(f"Median R:            {trade_metrics['median_r_multiple']:+.2f}R")
            print(f"Best R:              {trade_metrics['best_r_multiple']:+.2f}R")
            print(f"Worst R:             {trade_metrics['worst_r_multiple']:+.2f}R")
            print(f"\nExit Analysis:")
            print(
                f"Hit TP1:             {trade_metrics['hit_tp1']} ({trade_metrics['hit_tp1'] / trade_metrics['total_trades'] * 100:.1f}%)"
            )
            print(
                f"Hit TP2:             {trade_metrics['hit_tp2']} ({trade_metrics['hit_tp2'] / trade_metrics['total_trades'] * 100:.1f}%)"
            )
            print(
                f"Had Runner:          {trade_metrics['had_runner']} ({trade_metrics['had_runner'] / trade_metrics['total_trades'] * 100:.1f}%)"
            )
            print(f"Avg Hold Time:       {trade_metrics['avg_hold_days']:.1f} days")

        # QuantStats metrics
        print("\n" + "-" * 80)
        print("📈 QUANTSTATS METRICS (Time-Series)")
        print("-" * 80)
        qs_metrics = self.get_quantstats_metrics()

        if qs_metrics:
            print(f"\nRisk-Adjusted Returns:")
            print(f"Sharpe Ratio:        {qs_metrics.get('sharpe_ratio', 0):.2f}")
            print(f"Sortino Ratio:       {qs_metrics.get('sortino_ratio', 0):.2f}")
            print(f"Calmar Ratio:        {qs_metrics.get('calmar_ratio', 0):.2f}")
            print(f"Omega Ratio:         {qs_metrics.get('omega_ratio', 0):.2f}")

            print(f"\nReturns:")
            print(
                f"Total Return:        {qs_metrics.get('total_return', 0) * 100:+.2f}%"
            )
            print(f"CAGR:                {qs_metrics.get('cagr', 0) * 100:+.2f}%")
            print(f"Avg Daily Return:    {qs_metrics.get('avg_return', 0) * 100:+.4f}%")
            print(
                f"Annualized Return:   {qs_metrics.get('avg_return_annual', 0) * 100:+.2f}%"
            )

            print(f"\nVolatility:")
            print(
                f"Annual Volatility:   {qs_metrics.get('volatility_annual', 0) * 100:.2f}%"
            )
            print(
                f"Downside Volatility: {qs_metrics.get('downside_volatility', 0) * 100:.2f}%"
            )

            print(f"\nDrawdown:")
            print(
                f"Max Drawdown:        {qs_metrics.get('max_drawdown', 0) * 100:.2f}%"
            )
            print(
                f"Avg Drawdown:        {qs_metrics.get('avg_drawdown', 0) * 100:.2f}%"
            )
            print(
                f"Avg DD Days:         {qs_metrics.get('avg_drawdown_days', 0):.0f} days"
            )

            print(f"\nRisk Metrics:")
            print(f"VaR (95%):           {qs_metrics.get('var_95', 0) * 100:.2f}%")
            print(f"CVaR (95%):          {qs_metrics.get('cvar_95', 0) * 100:.2f}%")

            print(f"\nDistribution:")
            print(f"Skewness:            {qs_metrics.get('skewness', 0):.2f}")
            print(f"Kurtosis:            {qs_metrics.get('kurtosis', 0):.2f}")
            print(f"Best Day:            {qs_metrics.get('best_day', 0) * 100:+.2f}%")
            print(f"Worst Day:           {qs_metrics.get('worst_day', 0) * 100:+.2f}%")

            # Benchmark comparison if available
            if "alpha" in qs_metrics:
                print(f"\nBenchmark Comparison:")
                print(f"Alpha:               {qs_metrics['alpha']:.4f}")
                print(f"Beta:                {qs_metrics['beta']:.2f}")
                print(f"Correlation:         {qs_metrics['correlation']:.2f}")
                print(f"Information Ratio:   {qs_metrics['information_ratio']:.2f}")
                print(f"Excess Return:       {qs_metrics['excess_return'] * 100:+.2f}%")

        print("\n" + "=" * 80 + "\n")

    def export_complete_trades(
        self, output_path: str = "outputs/quantstats/complete_trades.csv"
    ):
        """Export complete trades (grouped) to CSV for further analysis."""
        if self.complete_trades.empty:
            logger.warning("No complete trades to export")
            return

        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)

        self.complete_trades.to_csv(output_file, index=False)
        logger.info(
            f"✅ Exported {len(self.complete_trades)} complete trades to: {output_file}"
        )

    def _calculate_avg_drawdown(self, returns):
        """
        Calculate average drawdown.

        QuantStats doesn't have avg_drawdown, so we calculate it from drawdown series.
        """
        try:
            dd_series = qs.stats.to_drawdown_series(returns)
            # Only consider negative drawdowns (exclude 0s which are peaks)
            negative_dd = dd_series[dd_series < 0]
            if len(negative_dd) > 0:
                return negative_dd.mean()
            return 0.0
        except Exception as e:
            logger.warning(f"Could not calculate avg_drawdown: {e}")
            return 0.0

    def _calculate_avg_drawdown_days(self, returns):
        """
        Calculate average drawdown duration in days.

        Uses drawdown_details to get individual drawdown durations.
        """
        try:
            dd_details = qs.stats.drawdown_details(returns)
            if not dd_details.empty and "days" in dd_details.columns:
                return dd_details["days"].mean()
            return 0.0
        except Exception as e:
            logger.warning(f"Could not calculate avg_drawdown_days: {e}")
            return 0.0


def analyze_backtest_with_quantstats(
    trade_log_path: str,
    initial_capital: float = 100000,
    benchmark: str = "SPY",
    generate_html: bool = True,
    output_dir: str = "outputs/quantstats",
) -> QuantStatsAnalyzer:
    """
    Convenience function to analyze backtest results with QuantStats.

    Args:
        trade_log_path: Path to trade log CSV file
        initial_capital: Starting capital
        benchmark: Benchmark ticker symbol
        generate_html: Whether to generate HTML tearsheet
        output_dir: Output directory for reports

    Returns:
        QuantStatsAnalyzer instance
    """
    # Load trade log
    trade_log = pd.read_csv(trade_log_path)
    logger.info(f"📂 Loaded {len(trade_log)} trade events from {trade_log_path}")

    # Create analyzer
    analyzer = QuantStatsAnalyzer(
        trade_log=trade_log, initial_capital=initial_capital, benchmark_ticker=benchmark
    )

    # Print summary
    analyzer.print_summary()

    # Export complete trades
    analyzer.export_complete_trades(f"{output_dir}/complete_trades.csv")

    # Generate HTML report
    if generate_html:
        report_path = analyzer.generate_report(
            output_dir=output_dir, benchmark_ticker=benchmark
        )
        if report_path:
            print(f"📊 Full report available at: {report_path}")

    return analyzer


if __name__ == "__main__":
    import sys

    print("Run analysis from command line or import QuantStatsAnalyzer")

    def _create_trade_analysis_page(self, analysis: Dict) -> plt.Figure:
        """Create trade analytics page for PDF report."""
        fig, axes = plt.subplots(2, 2, figsize=(11, 14))
        fig.suptitle(
            "Trade Analytics: Entry Score, RS & Position Sizing",
            fontsize=16,
            fontweight="bold",
            y=0.995,
        )

        # Helper functions
        def fmt(val, suffix=""):
            if val is None or (isinstance(val, float) and np.isnan(val)):
                return "N/A"
            return f"{val}{suffix}"

        # Section 1: Entry Score Analysis
        ax1 = axes[0, 0]
        ax1.axis("off")

        es = analysis.get("entry_score", {})
        if es and "high_score_trades" in es:
            es_data = [
                ["Entry Score - PnL Corr", fmt(es.get("corr_entry_score_vs_pnl"))],
                [
                    "High Score (≥0.7)",
                    f"{es['high_score_trades'].get('count', 0)} trades, {es['high_score_trades'].get('win_rate', 0)}% WR",
                ],
                [
                    "Med Score (0.4-0.7)",
                    f"{es['med_score_trades'].get('count', 0)} trades, {es['med_score_trades'].get('win_rate', 0)}% WR",
                ],
                [
                    "Low Score (<0.4)",
                    f"{es['low_score_trades'].get('count', 0)} trades, {es['low_score_trades'].get('win_rate', 0)}% WR",
                ],
                [
                    "Top 10 Winners Avg Score",
                    fmt(
                        es.get("top_10_winners", {}).get("avg_entry_score"),
                        " (R={})".format(
                            es.get("top_10_winners", {}).get("avg_r_multiple")
                        ),
                    )
                    if es.get("top_10_winners")
                    else "N/A",
                ],
            ]
            table1 = ax1.table(
                cellText=es_data,
                colLabels=["Entry Quality Score", "Value"],
                cellLoc="left",
                loc="center",
                colWidths=[0.5, 0.5],
            )
            table1.auto_set_font_size(False)
            table1.set_fontsize(9)
            table1.scale(1, 2)
            for (i, j), cell in table1.get_celld().items():
                cell.set_facecolor("#2c3e50" if i == 0 else "#34495e")
                cell.set_text_props(color="white")
        else:
            ax1.text(
                0.5, 0.5, "No Entry Score Data", ha="center", va="center", fontsize=12
            )

        # Section 2: RS Percentile Analysis
        ax2 = axes[0, 1]
        ax2.axis("off")

        rs = analysis.get("rs_percentile", {})
        if rs and "high_rs_trades" in rs:
            rs_data = [
                ["RS Percentile - PnL Corr", fmt(rs.get("corr_rs_vs_pnl"))],
                [
                    "RS ≥80 (Top 20%)",
                    f"{rs['high_rs_trades'].get('count', 0)} trades, {rs['high_rs_trades'].get('win_rate', 0)}% WR",
                ],
                [
                    "RS 50-80",
                    f"{rs['med_rs_trades'].get('count', 0)} trades, {rs['med_rs_trades'].get('win_rate', 0)}% WR",
                ],
                [
                    "RS <50 (Bottom 50%)",
                    f"{rs['low_rs_trades'].get('count', 0)} trades, {rs['low_rs_trades'].get('win_rate', 0)}% WR",
                ],
                ["Mean RS", fmt(rs.get("rs_distribution", {}).get("mean"))],
            ]
            table2 = ax2.table(
                cellText=rs_data,
                colLabels=["RS Percentile (IBD-Style)", "Value"],
                cellLoc="left",
                loc="center",
                colWidths=[0.5, 0.5],
            )
            table2.auto_set_font_size(False)
            table2.set_fontsize(9)
            table2.scale(1, 2)
            for (i, j), cell in table2.get_celld().items():
                cell.set_facecolor("#2c3e50" if i == 0 else "#34495e")
                cell.set_text_props(color="white")
        else:
            ax2.text(0.5, 0.5, "No RS Data", ha="center", va="center", fontsize=12)

        # Section 3: Position Sizing & R-Multiple
        ax3 = axes[1, 0]
        ax3.axis("off")

        ps = analysis.get("position_sizing", {})
        if ps and "r_distribution" in ps:
            rd = ps.get("r_distribution", {})
            ps_data = [
                ["Mean R-Multiple", fmt(rd.get("mean_r"))],
                ["Median R-Multiple", fmt(rd.get("median_r"))],
                ["Positive R Trades", fmt(rd.get("positive_r_pct"), "%")],
                ["Big Wins (≥2R)", fmt(rd.get("big_wins_pct"), "%")],
                ["Big Losses (≤-1R)", fmt(rd.get("big_losses_pct"), "%")],
            ]
            table3 = ax3.table(
                cellText=ps_data,
                colLabels=["Position Sizing", "Value"],
                cellLoc="left",
                loc="center",
                colWidths=[0.5, 0.5],
            )
            table3.auto_set_font_size(False)
            table3.set_fontsize(9)
            table3.scale(1, 2)
            for (i, j), cell in table3.get_celld().items():
                cell.set_facecolor("#2c3e50" if i == 0 else "#34495e")
                cell.set_text_props(color="white")
        else:
            ax3.text(
                0.5,
                0.5,
                "No Position Sizing Data",
                ha="center",
                va="center",
                fontsize=12,
            )

        # Section 4: Context Correlations
        ax4 = axes[1, 1]
        ax4.axis("off")

        ctx = analysis.get("context", {})
        if ctx:
            rvol = ctx.get("rvol_correlation", {})
            adr = ctx.get("adr_correlation", {})
            dist = ctx.get("dist_sma20_correlation", {})
            ctx_data = [
                ["RVOL - PnL Corr", fmt(rvol.get("corr_vs_pnl"))],
                ["ADR - PnL Corr", fmt(adr.get("corr_vs_pnl"))],
                ["Dist SMA20 - PnL Corr", fmt(dist.get("corr_vs_pnl"))],
                ["Mean RVOL", fmt(rvol.get("mean_rvol"))],
                ["Mean ADR", fmt(adr.get("mean_adr"), "%")],
            ]
            table4 = ax4.table(
                cellText=ctx_data,
                colLabels=["Context Correlations", "Value"],
                cellLoc="left",
                loc="center",
                colWidths=[0.5, 0.5],
            )
            table4.auto_set_font_size(False)
            table4.set_fontsize(9)
            table4.scale(1, 2)
            for (i, j), cell in table4.get_celld().items():
                cell.set_facecolor("#2c3e50" if i == 0 else "#34495e")
                cell.set_text_props(color="white")
        else:
            ax4.text(0.5, 0.5, "No Context Data", ha="center", va="center", fontsize=12)

        plt.tight_layout(rect=[0, 0, 1, 0.98])
        return fig

    # Example usage
    if len(sys.argv) > 1:
        trade_log_file = sys.argv[1]
    else:
        # Default: look for latest trade log
        from pathlib import Path

        trade_logs = list(Path("outputs/backtests").glob("trade_log_*.csv"))
        if trade_logs:
            trade_log_file = str(max(trade_logs, key=lambda p: p.stat().st_mtime))
            print(f"Using latest trade log: {trade_log_file}")
        else:
            print(
                "No trade log found. Usage: python quantstats_analyzer.py <trade_log.csv>"
            )
            sys.exit(1)

    # Run analysis
    analyzer = analyze_backtest_with_quantstats(
        trade_log_path=trade_log_file,
        initial_capital=100000,
        benchmark="SPY",
        generate_html=True,
    )
