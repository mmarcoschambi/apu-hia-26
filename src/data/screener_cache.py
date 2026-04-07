"""
Point-in-time screener cache.

Builds and queries historical screener results keyed by (screener, ticker, date)
to avoid look-ahead bias in combo optimization and backtests.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

import pandas as pd

from src.data.market_data import MarketDataProvider
from src.screeners import ScreenerRegistry

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_CACHE_DIR = PROJECT_ROOT / "data" / "screener_cache"


@dataclass
class ScreenerCacheRecord:
    screener_name: str
    ticker: str
    date: str
    passed: bool
    score: float
    reason: str
    metrics: Dict[str, Any]


class ScreenerCacheManager:
    """Builds and queries point-in-time screener caches."""

    def __init__(self, cache_dir: Optional[Path] = None):
        self.cache_dir = cache_dir or DEFAULT_CACHE_DIR
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._memory_cache: Dict[str, pd.DataFrame] = {}
        self._market_data = MarketDataProvider()

    def cache_path(self, screener_name: str) -> Path:
        return self.cache_dir / f"{screener_name}.parquet"

    def metadata_path(self, screener_name: str) -> Path:
        return self.cache_dir / f"{screener_name}.meta.json"

    def build_for_combo(
        self,
        screener_name: str,
        tickers: Iterable[str],
        start_date: str,
        end_date: str,
        *,
        spy_ticker: str = "SPY",
        lookback_buffer_days: int = 365,
    ) -> pd.DataFrame:
        """Build a point-in-time cache for a single screener.

        Args:
            screener_name: Screener registry name.
            tickers: Universe of symbols to evaluate.
            start_date: Backtest start date.
            end_date: Backtest end date.
            spy_ticker: Benchmark ticker for screeners that use SPY.
            lookback_buffer_days: Extra history buffer for indicators.

        Returns:
            DataFrame with historical screener results.
        """
        screener = ScreenerRegistry.get(screener_name)
        spy_df = self._load_symbol_data(
            spy_ticker,
            start_date,
            end_date,
            lookback_buffer_days=lookback_buffer_days,
        )

        records: List[Dict[str, Any]] = []
        for ticker in tickers:
            df = self._load_symbol_data(
                ticker,
                start_date,
                end_date,
                lookback_buffer_days=lookback_buffer_days,
            )
            if df.empty:
                continue

            for date in df.index[df.index >= pd.to_datetime(start_date)]:
                hist = df.loc[:date]
                if len(hist) < 50:
                    continue
                scan_date = date.strftime("%Y-%m-%d")
                spy_slice = spy_df.loc[:date] if not spy_df.empty else spy_df
                try:
                    result = screener.scan(
                        ticker, hist, spy_df=spy_slice, scan_date=scan_date
                    )
                    records.append(
                        {
                            "screener_name": screener_name,
                            "ticker": ticker,
                            "date": scan_date,
                            "passed": bool(result.passed),
                            "score": float(result.score),
                            "reason": result.reason,
                            "metrics_json": json.dumps(result.metrics, default=str),
                        }
                    )
                except Exception as exc:
                    logger.debug(
                        "Screener cache failed for %s %s %s: %s",
                        screener_name,
                        ticker,
                        scan_date,
                        exc,
                    )

        cache_df = pd.DataFrame(records)
        if not cache_df.empty:
            cache_df["date"] = pd.to_datetime(cache_df["date"])
            cache_df.sort_values(["screener_name", "ticker", "date"], inplace=True)
            cache_df.to_parquet(self.cache_path(screener_name), index=False)
            metadata = {
                "screener_name": screener_name,
                "start_date": str(pd.to_datetime(start_date).date()),
                "end_date": str(pd.to_datetime(end_date).date()),
                "tickers": sorted({str(t) for t in tickers}),
                "rows": int(len(cache_df)),
            }
            self.metadata_path(screener_name).write_text(
                json.dumps(metadata, indent=2), encoding="utf-8"
            )
            self._memory_cache[screener_name] = cache_df
        return cache_df

    def load(self, screener_name: str) -> pd.DataFrame:
        if screener_name in self._memory_cache:
            return self._memory_cache[screener_name]
        path = self.cache_path(screener_name)
        if not path.exists():
            return pd.DataFrame()
        df = pd.read_parquet(path)
        if "date" in df.columns:
            df["date"] = pd.to_datetime(df["date"])
        self._memory_cache[screener_name] = df
        return df

    def load_metadata(self, screener_name: str) -> Dict[str, Any]:
        path = self.metadata_path(screener_name)
        if not path.exists():
            return {}
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return {}

    def get_snapshot(self, screener_name: str, scan_date: str) -> pd.DataFrame:
        df = self.load(screener_name)
        if df.empty:
            return df
        target = pd.to_datetime(scan_date)
        return df[df["date"] == target]

    def passed_tickers(self, screener_name: str, scan_date: str) -> List[str]:
        snapshot = self.get_snapshot(screener_name, scan_date)
        if snapshot.empty:
            return []
        passed = snapshot[snapshot["passed"]]
        return sorted(passed["ticker"].unique().tolist())

    def build_mask(
        self,
        screener_name: str,
        dates_index: pd.DatetimeIndex,
        ticker_columns: List[str],
    ) -> Optional[pd.DataFrame]:
        """Build a boolean mask aligned to an entries matrix."""
        df = self.load(screener_name)
        if df.empty:
            return None

        meta = self.load_metadata(screener_name)
        if not meta:
            logger.warning(
                "Screener cache metadata missing for %s; skipping filter",
                screener_name,
            )
            return None

        cache_start = pd.to_datetime(meta.get("start_date"))
        cache_end = pd.to_datetime(meta.get("end_date"))
        requested_start = pd.to_datetime(dates_index.min())
        requested_end = pd.to_datetime(dates_index.max())
        if requested_start < cache_start or requested_end > cache_end:
            logger.warning(
                "Screener cache range mismatch for %s (cache %s..%s, requested %s..%s); skipping filter",
                screener_name,
                cache_start.date(),
                cache_end.date(),
                requested_start.date(),
                requested_end.date(),
            )
            return None
        cached_tickers = set(meta.get("tickers", []))
        requested_tickers = set(ticker_columns)
        if not requested_tickers.issubset(cached_tickers):
            logger.warning(
                "Screener cache universe mismatch for %s; skipping filter",
                screener_name,
            )
            return None

        passed = df[df["passed"]].copy()
        if passed.empty:
            return None

        passed["value"] = True
        pivot = passed.pivot_table(
            index="date",
            columns="ticker",
            values="value",
            aggfunc="max",
            fill_value=False,
        )
        pivot.index = pd.to_datetime(pivot.index)
        return (
            pivot.reindex(index=dates_index, columns=ticker_columns, fill_value=False)
            .fillna(False)
            .astype(bool)
        )

    def _load_symbol_data(
        self,
        ticker: str,
        start_date: str,
        end_date: str,
        *,
        lookback_buffer_days: int = 365,
    ) -> pd.DataFrame:
        buffer_start = (
            pd.to_datetime(start_date) - pd.Timedelta(days=lookback_buffer_days)
        ).strftime("%Y-%m-%d")
        # offline=True: usar solo DB/cache local, sin llamadas a red
        # El rebuild del screener cache debe trabajar con datos ya descargados
        df = self._market_data.get_daily_data(
            ticker,
            start_date=buffer_start,
            end_date=end_date,
            offline=True,
        )
        if df is None or df.empty:
            return pd.DataFrame()

        df = df.copy()
        if not isinstance(df.index, pd.DatetimeIndex):
            df.index = pd.to_datetime(df.index)
        df = df.sort_index()
        return df


def load_or_build_screener_cache(
    screener_name: str,
    tickers: Iterable[str],
    start_date: str,
    end_date: str,
    *,
    force_rebuild: bool = False,
) -> pd.DataFrame:
    """Load a cache if available or build it otherwise."""
    manager = ScreenerCacheManager()
    if not force_rebuild:
        cached = manager.load(screener_name)
        if not cached.empty:
            return cached
    return manager.build_for_combo(screener_name, tickers, start_date, end_date)
