"""
src/screeners/qullamaggie_momentum.py
Top 3% RS + MA Stack (estilo Kristjan Qullamaggie).
Requiere Fase 0: daily_rs_rankings poblada.
"""

import pandas as pd
import numpy as np
from typing import Optional

from .base import BaseScreener, ScreenerConfig, ScreenerResult
from .registry import ScreenerRegistry


@ScreenerRegistry.register
class QullamaggieMomentumScreener(BaseScreener):
    @property
    def name(self) -> str:
        return "qullamaggie_momentum"

    @property
    def description(self) -> str:
        return "Top 3% RS + MA Stack completo (estilo Kristjan)"

    @property
    def compatible_patterns(self):
        return ["vcp", "pocket_pivot", "breakout"]

    def get_default_config(self) -> ScreenerConfig:
        return ScreenerConfig(
            name=self.name,
            max_price=1000.0,
            min_dollar_volume=1_500_000,
            min_adr_pct=2.2,
            params={
                "min_rs_percentile": 85.0,  # 97 requiere daily_rs_rankings; 85 funciona con fallback SPY
                "min_trend_intensity": 108.0,  # (MA13 / MA65) * 100
                "require_ma_stack": True,
                "ma_stack_tolerance": 0.002,  # 0.2% tolerancia para el stack
                "rs_metric": "rs_composite",
                "rs_fallback_spy": True,  # Si no hay RS en DB, calcular vs SPY
            },
        )

    def _calc_rs_vs_spy(
        self, df: pd.DataFrame, spy_df: pd.DataFrame, period: int = 60
    ) -> float:
        """RS relativo vs SPY como percentil aproximado (fallback sin daily_rs_rankings).

        Escala calibrada: top stocks de Qullamaggie superan SPY 15-30% en 60d.
        - outperform SPY +20% -> percentil 99 (top 1%)
        - inline con SPY  0%  -> percentil 50
        - underperform   -20% -> percentil 1
        Multiplicador 500: cada 1% vs SPY = 5 puntos de percentil.
        """
        if spy_df is None or len(df) < period or len(spy_df) < period:
            return 50.0
        _c  = "close" if "close" in df.columns else "Close"
        _sc = "close" if "close" in spy_df.columns else "Close"
        ticker_ret = float(df[_c].iloc[-1] / df[_c].iloc[-period] - 1)
        spy_ret    = float(spy_df[_sc].iloc[-1] / spy_df[_sc].iloc[-period] - 1)
        relative   = ticker_ret - spy_ret
        score      = 50.0 + relative * 500.0
        return max(0.0, min(100.0, score))

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

        if len(df) < 200:
            return ScreenerResult(
                False,
                ticker,
                self.name,
                reason=f"Historia insuficiente ({len(df)} < 200)",
            )

        c = df["close"] if "close" in df.columns else df["Close"]
        price = float(c.iloc[-1])

        p = self.config.params

        # RS Percentil
        rs_pct = None
        try:
            from src.data.rs_rankings import get_rs_percentile

            rs_pct = get_rs_percentile(ticker, date=scan_date, metric=p["rs_metric"])
        except Exception:
            pass

        if rs_pct is None and p.get("rs_fallback_spy") and spy_df is not None:
            rs_pct = self._calc_rs_vs_spy(df, spy_df)

        if rs_pct is None:
            rs_pct = 50.0  # desconocido → neutral

        rs_ok = rs_pct >= p["min_rs_percentile"]

        # MA Stack: Price >= EMA10 >= SMA20 >= SMA50 >= SMA100 >= SMA200
        ema10 = self.ensure_ma(df, 10, kind="ema")
        sma20 = self.ensure_ma(df, 20)
        sma50 = self.ensure_ma(df, 50)
        sma100 = self.ensure_ma(df, 100)
        sma200 = self.ensure_ma(df, 200)

        e10 = float(ema10.iloc[-1])
        s20 = float(sma20.iloc[-1])
        s50 = float(sma50.iloc[-1])
        s100 = float(sma100.iloc[-1])
        s200 = float(sma200.iloc[-1])
        tol = p["ma_stack_tolerance"]

        stack_ok = (
            (
                price >= e10 * (1 - tol)
                and e10 >= s20 * (1 - tol)
                and s20 >= s50 * (1 - tol)
                and s50 >= s100 * (1 - tol)
                and s100 >= s200 * (1 - tol)
            )
            if p["require_ma_stack"]
            else True
        )

        # Trend Intensity: (MA13 / MA65) * 100
        ma13 = float(self.ensure_ma(df, 13).iloc[-1])
        ma65 = float(self.ensure_ma(df, 65).iloc[-1])
        trend_intensity = (ma13 / ma65 * 100) if ma65 > 0 else 0.0
        ti_ok = trend_intensity >= p["min_trend_intensity"]

        criteria = {
            "rs_top3pct": rs_ok,
            "ma_stack": stack_ok,
            "trend_intensity": ti_ok,
        }

        all_pass = all(criteria.values())
        passing = sum(criteria.values())
        score = round(
            (rs_pct * 0.5 + (trend_intensity - 100) * 2 * 0.3 + passing / 3 * 20), 1
        )
        score = max(0.0, min(100.0, score))

        failed = [k for k, v in criteria.items() if not v]
        reason = "Qullamaggie OK" if all_pass else f"Falló: {', '.join(failed)}"

        return ScreenerResult(
            passed=all_pass,
            ticker=ticker,
            screener_name=self.name,
            score=score,
            metrics={
                "criteria": criteria,
                "rs_percentile": round(rs_pct, 1),
                "trend_intensity": round(trend_intensity, 1),
                "price": price,
                "ema10": round(e10, 2),
                "sma20": round(s20, 2),
                "sma50": round(s50, 2),
                "sma100": round(s100, 2),
                "sma200": round(s200, 2),
            },
            reason=reason,
        )
