"""
src/screeners/triad_rts.py
Screener Triad RTS (Minervini + AS + RTS + Filtros Estructurales).

Implementa el pipeline completo del design doc:
  - Fase 1: Filtros base (precio, dollar volume, market cap)
  - Fase 2: Absolute Strength gate (AS 5d >= 50 Y AS 21d >= 50)
  - Fase 3: Minervini Trend Template (8 criterios + RS > 70)
  - Fase 4: RTS Gate (RTS percentile >= 90)
  - Fase 5: Dark Green Cells (ATR, extensión SMA50, proximidad pivote, green candle)

Backtest-only: Usa daily_triad_rankings para métricas PIT.
"""

import pandas as pd
from typing import Optional
import logging

logger = logging.getLogger(__name__)

from .base import BaseScreener, ScreenerConfig, ScreenerResult
from .registry import ScreenerRegistry


@ScreenerRegistry.register
class TriadRTSScreener(BaseScreener):
    @property
    def name(self) -> str:
        return "triad_rts"

    @property
    def description(self) -> str:
        return "Triad RTS: Minervini + AS + RTS + Filtros Estructurales (Pipeline Completo)"

    @property
    def compatible_patterns(self):
        return ["breakout", "vcp", "cup_and_handle", "flat_base", "pocket_pivot"]

    def get_default_config(self) -> ScreenerConfig:
        return ScreenerConfig(
            name=self.name,
            min_price=5.0,
            max_price=1000.0,
            min_avg_volume=100_000,
            min_dollar_volume=20_000_000,
            min_adr_pct=1.5,
            params={
                # Fase 1: Filtros base
                "min_market_cap": 1_000_000_000,  # $1B
                "require_market_cap": False,  # OFF por defecto (datos no siempre disponibles)
                # Fase 2: AS gates
                "min_as_5d_pct": 50.0,
                "min_as_21d_pct": 50.0,
                # Fase 3: Minervini params
                "max_dist_from_52wk_high_pct": 25.0,
                "min_above_52wk_low_pct": 30.0,
                "sma200_uptrend_days": 22,
                "min_rs_percentile": 70.0,  # RS > 70
                # Fase 4: RTS gate
                "min_rts_pct": 70.0,
                # Fase 5: Dark green cells
                "require_atr_above_universe": True,
                "max_sma50_atr_extension": 5.0,  # Max 5x ATR desde SMA50
                "pivot_tolerance_pct": 2.0,  # +-2% de máximo 20 días
                "require_green_candle": False,
            },
        )

    def _load_triad_metrics(self, ticker: str, date: str) -> Optional[dict]:
        """Carga métricas desde daily_triad_rankings."""
        try:
            from src.data.triad_rankings import get_triad_metrics

            return get_triad_metrics(ticker, date=date)
        except Exception as e:
            logger.error(f"{ticker}: _load_triad_metrics({date}) exception: {e}")
            return None

    def _load_rs_percentile(self, ticker: str, date: str) -> float:
        """Carga RS percentile desde daily_rs_rankings."""
        try:
            from src.data.rs_rankings import get_rs_percentile

            rs = get_rs_percentile(ticker, date=date, metric="rs_composite")
            return rs if rs is not None else 50.0
        except Exception:
            return 50.0

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
                reason=f"Historia insuficiente ({len(df)} < 200 barras)",
            )

        p = self.config.params

        c = df["close"] if "close" in df.columns else df["Close"]
        o = df["open"] if "open" in df.columns else df["Open"]
        h = df["high"] if "high" in df.columns else df["High"]
        l = df["low"] if "low" in df.columns else df["Low"]
        v = df["volume"] if "volume" in df.columns else df["Volume"]

        price = float(c.iloc[-1])
        prev_close = float(c.iloc[-2]) if len(c) >= 2 else price

        # ============================================================
        # FASE 1: FILTROS BASE
        # ============================================================
        dollar_vol = price * v.iloc[-20:].mean()
        base_filters = {
            "price_ok": price >= self.config.min_price,
            "dollar_vol_ok": dollar_vol >= p.get("min_dollar_volume", 20_000_000),
        }

        # Market cap check (opcional)
        if p.get("require_market_cap", False) and "market_cap" in df.columns:
            mcap = df["market_cap"].iloc[-1]
            base_filters["market_cap_ok"] = mcap >= p.get(
                "min_market_cap", 1_000_000_000
            )

        if not all(base_filters.values()):
            failed = [k for k, v in base_filters.items() if not v]
            return ScreenerResult(
                False, ticker, self.name, reason=f"Base: {', '.join(failed)}"
            )

        # ============================================================
        # FASE 2: ABSOLUTE STRENGTH GATE
        # ============================================================
        triad_metrics = None
        as_5d_pct = 50.0
        as_21d_pct = 50.0

        if scan_date:
            triad_metrics = self._load_triad_metrics(ticker, scan_date)
            if triad_metrics:
                as_5d_pct = triad_metrics.get("as_5d_pct", 50.0)
                as_21d_pct = triad_metrics.get("as_21d_pct", 50.0)
            else:
                logger.warning(
                    f"{ticker}: scan_date={scan_date} pero no hay triad_metrics - usando fallback 50.0"
                )
        else:
            logger.warning(
                f"{ticker}: scan_date=None - usando fallback 50.0 para AS/RTS (esto diluye el gate!)"
            )

        as_filters = {
            "as_5d_ok": as_5d_pct >= p.get("min_as_5d_pct", 50.0),
            "as_21d_ok": as_21d_pct >= p.get("min_as_21d_pct", 50.0),
        }

        if not all(as_filters.values()):
            return ScreenerResult(
                False,
                ticker,
                self.name,
                reason=f"AS: 5d={as_5d_pct:.0f} < {p.get('min_as_5d_pct')} OR 21d={as_21d_pct:.0f} < {p.get('min_as_21d_pct')}",
            )

        # ============================================================
        # FASE 3: MINERVINI TREND TEMPLATE (8 CRITERIOS + RS > 70)
        # ============================================================
        sma50 = self.ensure_ma(df, 50)
        sma150 = self.ensure_ma(df, 150)
        sma200 = self.ensure_ma(df, 200)

        s50 = float(sma50.iloc[-1])
        s150 = float(sma150.iloc[-1])
        s200 = float(sma200.iloc[-1])
        s200_ago = float(sma200.iloc[-(p.get("sma200_uptrend_days", 22) + 1)])

        # 52-week lookback
        lookback = min(252, len(df))
        high_52w = float(c.iloc[-lookback:].max())
        low_52w = float(c.iloc[-lookback:].min())

        max_dist_high = p.get("max_dist_from_52wk_high_pct", 25.0) / 100
        min_above_low = p.get("min_above_52wk_low_pct", 30.0) / 100

        # RS Percentile check
        rs_pct = 50.0
        if scan_date:
            rs_pct = self._load_rs_percentile(ticker, scan_date)

        minervini_criteria = {
            "price_above_sma150_sma200": price > s150 and price > s200,
            "sma150_above_sma200": s150 > s200,
            "sma200_uptrend": s200 > s200_ago,
            "sma50_stack": s50 > s150 > s200,
            "price_above_sma50": price > s50,
            "near_52wk_high": price >= high_52w * (1 - max_dist_high),
            "above_52wk_low": price >= low_52w * (1 + min_above_low),
            "rs_ok": rs_pct >= p.get("min_rs_percentile", 70.0),
        }

        passing_minervini = sum(minervini_criteria.values())

        if passing_minervini < 8:
            failed = [k for k, v in minervini_criteria.items() if not v]
            return ScreenerResult(
                False,
                ticker,
                self.name,
                reason=f"Minervini ({passing_minervini}/8): {', '.join(failed[:3])}",
            )

        # ============================================================
        # FASE 4: RTS GATE
        # ============================================================
        rts_pct = 50.0
        trend_score = 0.0

        if triad_metrics:
            rts_pct = triad_metrics.get("rts_pct", 50.0)
            trend_score = triad_metrics.get("trend_score_raw", 0.0)

        if rts_pct < p.get("min_rts_pct", 90.0):
            return ScreenerResult(
                False,
                ticker,
                self.name,
                reason=f"RTS: {rts_pct:.0f} < {p.get('min_rts_pct')}",
            )

        # ============================================================
        # FASE 5: DARK GREEN CELLS (FILTROS ESTRUCTURALES)
        # ============================================================
        # ATR
        atr = self.ensure_atr(df, 14)
        atr14 = float(atr.iloc[-1])

        atr_universe_mean = atr14
        if triad_metrics:
            atr_universe_mean = triad_metrics.get("atr14_universe_mean", atr14)

        atr_filter = True
        if p.get("require_atr_above_universe", True):
            atr_filter = atr14 > atr_universe_mean  # Debe ser >= promedio del universo

        # Extensión SMA50
        dist_sma50_pct = ((price - s50) / s50 * 100) if s50 > 0 else 999.0
        max_ext = p.get("max_sma50_atr_extension", 5.0)
        ext_filter = dist_sma50_pct < (max_ext * atr14 / price * 100)

        # Proximidad a pivote (20d high)
        high_20d = h.iloc[-20:].max()
        pivot_dist = ((price - high_20d) / high_20d * 100) if high_20d > 0 else 0.0
        pivot_tol = p.get("pivot_tolerance_pct", 2.0)
        pivot_filter = (
            abs(pivot_dist) <= pivot_tol or pivot_dist > 0
        )  # En pivote o haciendo nuevo high

        # Green candle
        green_ok = True
        if p.get("require_green_candle", True):
            if triad_metrics:
                green_ok = triad_metrics.get("green_candle", False)
            else:
                green_ok = (price >= float(o.iloc[-1])) and (price >= prev_close)

        dark_green_filters = {
            "atr_ok": atr_filter,
            "ext_ok": ext_filter,
            "pivot_ok": pivot_filter,
            "green_ok": green_ok,
        }

        if not all(dark_green_filters.values()):
            failed = [k for k, v in dark_green_filters.items() if not v]
            return ScreenerResult(
                False, ticker, self.name, reason=f"DarkGreen: {', '.join(failed)}"
            )

        # ============================================================
        # PASSED: Return result con score
        # ============================================================
        # Score compuesto
        score = min(100.0, (rts_pct + rs_pct + passing_minervini * 10) / 3)

        return ScreenerResult(
            passed=True,
            ticker=ticker,
            screener_name=self.name,
            score=score,
            metrics={
                "criteria": {
                    **base_filters,
                    **as_filters,
                    **minervini_criteria,
                    **dark_green_filters,
                },
                "as_5d_pct": as_5d_pct,
                "as_21d_pct": as_21d_pct,
                "trend_score_raw": trend_score,
                "rts_pct": rts_pct,
                "rs_percentile": rs_pct,
                "price": price,
                "sma50": round(s50, 2),
                "sma150": round(s150, 2),
                "sma200": round(s200, 2),
                "high_52w": round(high_52w, 2),
                "low_52w": round(low_52w, 2),
                "atr14": round(atr14, 3),
                "dist_sma50_pct": round(dist_sma50_pct, 2),
                "pivot_dist_pct": round(pivot_dist, 2),
                "green_candle": green_ok,
                "passing_minervini": passing_minervini,
            },
            reason="Triad RTS PASSED - All phases",
        )
