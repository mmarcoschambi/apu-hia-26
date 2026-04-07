"""
src/screeners/minervini_trend.py
Stage 2 Trend Template de Mark Minervini (7 criterios).
"""

import pandas as pd
import numpy as np
from typing import Optional

from .base import BaseScreener, ScreenerConfig, ScreenerResult
from .registry import ScreenerRegistry


@ScreenerRegistry.register
class MinerviniTrendScreener(BaseScreener):
    @property
    def name(self) -> str:
        return "minervini_trend"

    @property
    def description(self) -> str:
        return "Mark Minervini Stage 2 Trend Template (7 criterios)"

    @property
    def compatible_patterns(self):
        return ["vcp", "cup_and_handle", "flat_base", "pocket_pivot", "breakout"]

    def get_default_config(self) -> ScreenerConfig:
        return ScreenerConfig(
            name=self.name,
            min_price=5.0,
            max_price=1000.0,
            min_avg_volume=100_000,
            params={
                "max_dist_from_52wk_high_pct": 25.0,
                "min_above_52wk_low_pct": 30.0,
                "sma200_uptrend_days": 22,
            },
        )

    def scan(
        self,
        ticker: str,
        df: pd.DataFrame,
        spy_df: Optional[pd.DataFrame] = None,
        scan_date: Optional[str] = None,
    ) -> ScreenerResult:
        # 1. Filtros base
        passed, reason = self.apply_base_filters(df)
        if not passed:
            return ScreenerResult(False, ticker, self.name, reason=reason)

        if len(df) < 200:
            return ScreenerResult(
                False,
                ticker,
                self.name,
                reason=f"Historia insuficiente para SMA200 ({len(df)} barras)",
            )

        c = df["close"] if "close" in df.columns else df["Close"]

        sma50 = self.ensure_ma(df, 50)
        sma150 = self.ensure_ma(df, 150)
        sma200 = self.ensure_ma(df, 200)

        price = float(c.iloc[-1])
        s50 = float(sma50.iloc[-1])
        s150 = float(sma150.iloc[-1])
        s200 = float(sma200.iloc[-1])
        s200_ago = float(sma200.iloc[-(self.config.params["sma200_uptrend_days"] + 1)])

        # 52-week lookback (252 barras o las disponibles)
        lookback = min(252, len(df))
        high_52w = float(c.iloc[-lookback:].max())
        low_52w = float(c.iloc[-lookback:].min())

        params = self.config.params
        max_dist_high = params["max_dist_from_52wk_high_pct"] / 100
        min_above_low = params["min_above_52wk_low_pct"] / 100

        # 7 criterios
        criteria = {
            "price_above_sma150_sma200": price > s150 and price > s200,
            "sma150_above_sma200": s150 > s200,
            "sma200_uptrend": s200 > s200_ago,
            "sma50_stack": s50 > s150 > s200,
            "price_above_sma50": price > s50,
            "near_52wk_high": price >= high_52w * (1 - max_dist_high),
            "above_52wk_low": price >= low_52w * (1 + min_above_low),
        }

        passing = sum(criteria.values())
        score = round(passing / 7 * 100, 1)
        all_pass = passing == 7

        failed = [k for k, v in criteria.items() if not v]
        reason = "Stage 2 OK" if all_pass else f"Falló: {', '.join(failed)}"

        return ScreenerResult(
            passed=all_pass,
            ticker=ticker,
            screener_name=self.name,
            score=score,
            metrics={
                "criteria": criteria,
                "price": price,
                "sma50": round(s50, 2),
                "sma150": round(s150, 2),
                "sma200": round(s200, 2),
                "high_52w": round(high_52w, 2),
                "low_52w": round(low_52w, 2),
                "dist_from_high_pct": round((1 - price / high_52w) * 100, 1),
                "above_low_pct": round((price / low_52w - 1) * 100, 1),
                "passing_criteria": passing,
            },
            reason=reason,
        )
