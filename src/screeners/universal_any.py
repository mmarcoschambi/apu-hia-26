"""
src/screeners/universal_any.py
Universal benchmark screener used as the explicit "any" comparator.
"""

from typing import Optional

import pandas as pd

from .base import BaseScreener, ScreenerConfig, ScreenerResult
from .registry import ScreenerRegistry


@ScreenerRegistry.register
class UniversalAnyScreener(BaseScreener):
    @property
    def name(self) -> str:
        return "universal_any"

    @property
    def description(self) -> str:
        return "Universal benchmark screener (legacy any)"

    @property
    def compatible_patterns(self):
        return ["any", "breakout", "vcp", "pocket_pivot", "flat_base"]

    def get_default_config(self) -> ScreenerConfig:
        return ScreenerConfig(
            name=self.name,
            min_price=5.0,
            max_price=1000.0,
            min_avg_volume=100_000,
            min_dollar_volume=10_000_000,
            min_adr_pct=1.0,
            max_adr_pct=20.0,
            params={
                "benchmark_mode": True,
            },
        )

    def scan(
        self,
        ticker: str,
        df: pd.DataFrame,
        spy_df: Optional[pd.DataFrame] = None,
        scan_date: Optional[str] = None,
    ) -> ScreenerResult:
        passed, reason = self.apply_base_filters(df)
        if not passed:
            return ScreenerResult(False, ticker, self.name, reason=reason)

        row = df.iloc[-1]
        price = float(row.get("close", row.get("Close", 0.0)))
        avg_volume = float(
            row.get("avg_volume_20", row.get("volume", row.get("Volume", 0.0)))
        )
        dollar_volume = float(row.get("dollar_volume", price * avg_volume))

        return ScreenerResult(
            passed=True,
            ticker=ticker,
            screener_name=self.name,
            score=50.0,
            metrics={
                "benchmark_mode": True,
                "price": price,
                "avg_volume": avg_volume,
                "dollar_volume": dollar_volume,
            },
            reason="Universal benchmark passed",
        )
