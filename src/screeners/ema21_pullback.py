"""
src/screeners/ema21_pullback.py
Pullback a 21EMA en zona ATR válida (estilo IBD/O'Neil).
"""

import pandas as pd
import numpy as np
from typing import Optional

from .base import BaseScreener, ScreenerConfig, ScreenerResult
from .registry import ScreenerRegistry


@ScreenerRegistry.register
class EMA21PullbackScreener(BaseScreener):
    @property
    def name(self) -> str:
        return "ema21_pullback"

    @property
    def description(self) -> str:
        return "Pullback a 21EMA en zona ATR válida (-0.5R a +1R)"

    @property
    def compatible_patterns(self):
        return ["pocket_pivot", "breakout"]

    def get_default_config(self) -> ScreenerConfig:
        return ScreenerConfig(
            name=self.name,
            min_avg_volume=1_000_000,
            min_adr_pct=3.5,
            max_adr_pct=10.0,
            params={
                "ema21_zone_min_r": -0.5,  # Permite hasta 0.5 ATR debajo del EMA21
                "ema21_zone_max_r": 1.0,  # No más de 1 ATR arriba del EMA21
                "sma50_zone_min_r": 0.0,  # Precio sobre SMA50
                "sma50_zone_max_r": 3.0,  # No demasiado extendido sobre SMA50
                "atr_period": 14,
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

        if len(df) < 60:
            return ScreenerResult(
                False, ticker, self.name, reason="Historia insuficiente (< 60 barras)"
            )

        c = df["close"] if "close" in df.columns else df["Close"]
        price = float(c.iloc[-1])

        atr_period = self.config.params.get("atr_period", 14)
        atr = float(self.ensure_atr(df, atr_period).iloc[-1])
        ema21 = float(self.ensure_ma(df, 21, kind="ema").iloc[-1])
        sma50 = float(self.ensure_ma(df, 50).iloc[-1])

        if atr <= 0:
            return ScreenerResult(False, ticker, self.name, reason="ATR inválido")

        p = self.config.params
        # R-multiples: positivo = precio por encima de la MA
        r_from_ema21 = (price - ema21) / atr
        r_from_sma50 = (price - sma50) / atr

        criteria = {
            "in_ema21_zone": p["ema21_zone_min_r"]
            <= r_from_ema21
            <= p["ema21_zone_max_r"],
            "in_sma50_zone": p["sma50_zone_min_r"]
            <= r_from_sma50
            <= p["sma50_zone_max_r"],
            "price_above_ema21_low": price >= ema21 * 0.995,  # tolerancia 0.5%
        }

        passing = sum(criteria.values())
        all_pass = passing == len(criteria)

        # Score: más alto mientras más cerca del centro de la zona EMA21
        ideal_r = (p["ema21_zone_min_r"] + p["ema21_zone_max_r"]) / 2
        proximity = max(0, 1 - abs(r_from_ema21 - ideal_r))
        score = (
            round(proximity * 100, 1)
            if all_pass
            else round(passing / len(criteria) * 50, 1)
        )

        failed = [k for k, v in criteria.items() if not v]
        reason = "EMA21 pullback OK" if all_pass else f"Falló: {', '.join(failed)}"

        return ScreenerResult(
            passed=all_pass,
            ticker=ticker,
            screener_name=self.name,
            score=score,
            metrics={
                "criteria": criteria,
                "price": price,
                "ema21": round(ema21, 2),
                "sma50": round(sma50, 2),
                "atr": round(atr, 2),
                "r_from_ema21": round(r_from_ema21, 2),
                "r_from_sma50": round(r_from_sma50, 2),
            },
            reason=reason,
        )
