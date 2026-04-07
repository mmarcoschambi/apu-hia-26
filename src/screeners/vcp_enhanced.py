"""
src/screeners/vcp_enhanced.py
VCP con Volatility Contraction Score (VCS) + criterios Minervini.
"""

import pandas as pd
import numpy as np
from typing import Optional

from .base import BaseScreener, ScreenerConfig, ScreenerResult
from .registry import ScreenerRegistry


@ScreenerRegistry.register
class VCPEnhancedScreener(BaseScreener):
    @property
    def name(self) -> str:
        return "vcp_enhanced"

    @property
    def description(self) -> str:
        return "VCP con Volatility Contraction Score (VCS 0-100) + Minervini trend"

    @property
    def compatible_patterns(self):
        return ["vcp"]

    def get_default_config(self) -> ScreenerConfig:
        return ScreenerConfig(
            name=self.name,
            min_price=5.0,
            max_price=1000.0,
            min_avg_volume=100_000,
            params={
                "min_vcs_score": 60.0,
                "min_contractions": 2,
                "require_higher_lows": True,
                "require_minervini_trend": True,
                "vcs_short_period": 13,
                "vcs_long_period": 63,
                # pesos VCS (deben sumar 1.0)
                "w_price_compression": 0.35,
                "w_price_stability": 0.30,
                "w_volume_contraction": 0.25,
                "w_structure_bonus": 0.10,
                # contraction detection
                "contraction_window": 40,  # barras a revisar
                "contraction_threshold": 0.85,  # cada rally < 85% del anterior
            },
        )

    # ------------------------------------------------------------------ #
    # VCS Score
    # ------------------------------------------------------------------ #
    def calculate_vcs_score(self, df: pd.DataFrame) -> tuple[float, dict]:
        """
        Calcula el Volatility Contraction Score (0-100).

        Componentes:
            A. Price Compression : ATR_short / ATR_long  (menor = mejor)
            B. Price Stability   : StdDev_short / StdDev_long (menor = mejor)
            C. Volume Contraction: Vol_reciente / Vol_avg (menor = mejor)
            D. Structure Bonus   : Higher lows presentes
        """
        p = self.config.params
        sp = p["vcs_short_period"]
        lp = p["vcs_long_period"]

        c = df["close"] if "close" in df.columns else df["Close"]
        v = df["volume"] if "volume" in df.columns else df["Volume"]

        atr_short = float(self.ensure_atr(df, sp).iloc[-1])
        atr_long = float(self.ensure_atr(df, lp).iloc[-1])

        # A. Price Compression
        if atr_long > 0:
            compression_ratio = (
                atr_short / atr_long
            )  # 0 < ratio <= 1 cuando hay contracción
            # Invertimos: ratio bajo → score alto
            a_score = max(0.0, min(1.0, 1.0 - compression_ratio))
        else:
            a_score = 0.0

        # B. Price Stability (StdDev rolling)
        std_short = float(c.rolling(sp).std().iloc[-1]) if len(c) >= sp else 0.0
        std_long = float(c.rolling(lp).std().iloc[-1]) if len(c) >= lp else 0.0
        if std_long > 0:
            stability_ratio = std_short / std_long
            b_score = max(0.0, min(1.0, 1.0 - stability_ratio))
        else:
            b_score = 0.0

        # C. Volume Contraction
        vol_recent = float(v.iloc[-sp:].mean()) if len(v) >= sp else float(v.mean())
        vol_avg = float(v.iloc[-lp:].mean()) if len(v) >= lp else float(v.mean())
        if vol_avg > 0:
            vol_ratio = vol_recent / vol_avg
            c_score = max(
                0.0, min(1.0, 1.0 - vol_ratio * 0.5)
            )  # 50% reducción → score=0.75
        else:
            c_score = 0.0

        # D. Structure Bonus: Higher lows en últimas n barras
        window = min(p["contraction_window"], len(df))
        lows = (
            df["low"].iloc[-window:]
            if "low" in df.columns
            else df["Low"].iloc[-window:]
        )
        # Contar cuántos mínimos locales son crecientes
        local_lows = []
        for i in range(1, len(lows) - 1):
            if lows.iloc[i] < lows.iloc[i - 1] and lows.iloc[i] < lows.iloc[i + 1]:
                local_lows.append(float(lows.iloc[i]))
        if len(local_lows) >= 2:
            higher_lows_count = sum(
                local_lows[i] > local_lows[i - 1] for i in range(1, len(local_lows))
            )
            d_score = min(1.0, higher_lows_count / max(len(local_lows) - 1, 1))
        else:
            d_score = 0.0

        # Score final ponderado → 0-100
        total = (
            p["w_price_compression"] * a_score
            + p["w_price_stability"] * b_score
            + p["w_volume_contraction"] * c_score
            + p["w_structure_bonus"] * d_score
        ) * 100

        details = {
            "price_compression": round(a_score * 100, 1),
            "price_stability": round(b_score * 100, 1),
            "volume_contraction": round(c_score * 100, 1),
            "structure_bonus": round(d_score * 100, 1),
            "atr_short": round(atr_short, 3),
            "atr_long": round(atr_long, 3),
            "vol_ratio": round(vol_ratio if vol_avg > 0 else 0, 3),
            "local_lows_found": len(local_lows),
        }
        return round(total, 1), details

    # ------------------------------------------------------------------ #
    # Contraction count
    # ------------------------------------------------------------------ #
    def count_contractions(self, df: pd.DataFrame) -> tuple[int, bool]:
        """
        Cuenta las contracciones (rallies que se vuelven menos profundos).
        Retorna (n_contractions, has_higher_lows).
        """
        p = self.config.params
        window = min(p["contraction_window"], len(df))
        h = (
            df["high"].iloc[-window:]
            if "high" in df.columns
            else df["High"].iloc[-window:]
        )
        l = (
            df["low"].iloc[-window:]
            if "low" in df.columns
            else df["Low"].iloc[-window:]
        )

        # Detectar swings: máximos y mínimos locales
        swing_highs = []
        swing_lows = []
        for i in range(1, len(h) - 1):
            if h.iloc[i] > h.iloc[i - 1] and h.iloc[i] > h.iloc[i + 1]:
                swing_highs.append(float(h.iloc[i]))
            if l.iloc[i] < l.iloc[i - 1] and l.iloc[i] < l.iloc[i + 1]:
                swing_lows.append(float(l.iloc[i]))

        # Contracciones: cada pullback es menor que el anterior
        contractions = 0
        if len(swing_highs) >= 2 and len(swing_lows) >= 2:
            # Calcular profundidad de cada retroceso entre highs consecutivos
            n = min(len(swing_highs), len(swing_lows) + 1)
            depths = []
            for i in range(min(n - 1, len(swing_lows))):
                if swing_highs[i] > 0:
                    depth = (swing_highs[i] - swing_lows[i]) / swing_highs[i]
                    depths.append(depth)
            for i in range(1, len(depths)):
                if depths[i] < depths[i - 1] * p["contraction_threshold"]:
                    contractions += 1

        # Higher lows: mínimos crecientes
        has_higher_lows = False
        if len(swing_lows) >= 2:
            has_higher_lows = all(
                swing_lows[i] > swing_lows[i - 1] for i in range(1, len(swing_lows))
            )

        return contractions, has_higher_lows

    # ------------------------------------------------------------------ #
    # Minervini trend check inline (sin importar el screener completo)
    # ------------------------------------------------------------------ #
    def _passes_minervini(self, df: pd.DataFrame) -> bool:
        if len(df) < 200:
            return False
        c = df["close"] if "close" in df.columns else df["Close"]
        price = float(c.iloc[-1])
        sma50 = float(self.ensure_ma(df, 50).iloc[-1])
        sma150 = float(self.ensure_ma(df, 150).iloc[-1])
        sma200 = float(self.ensure_ma(df, 200).iloc[-1])
        return (
            price > sma150
            and price > sma200
            and sma150 > sma200
            and sma50 > sma150
            and price > sma50
        )

    # ------------------------------------------------------------------ #
    # scan
    # ------------------------------------------------------------------ #
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

        p = self.config.params
        min_len = p["vcs_long_period"] + 10
        if len(df) < min_len:
            return ScreenerResult(
                False,
                ticker,
                self.name,
                reason=f"Historia insuficiente ({len(df)} < {min_len})",
            )

        vcs_score, vcs_details = self.calculate_vcs_score(df)
        n_contractions, has_higher_lows = self.count_contractions(df)

        minervini_ok = (
            self._passes_minervini(df) if p["require_minervini_trend"] else True
        )

        criteria = {
            "vcs_score_ok": vcs_score >= p["min_vcs_score"],
            "min_contractions_ok": n_contractions >= p["min_contractions"],
            "higher_lows_ok": has_higher_lows if p["require_higher_lows"] else True,
            "minervini_trend_ok": minervini_ok,
        }

        all_pass = all(criteria.values())
        passing = sum(criteria.values())
        score = round(vcs_score * (passing / len(criteria)), 1)

        failed = [k for k, v in criteria.items() if not v]
        reason = "VCP Enhanced OK" if all_pass else f"Falló: {', '.join(failed)}"

        return ScreenerResult(
            passed=all_pass,
            ticker=ticker,
            screener_name=self.name,
            score=score,
            metrics={
                "criteria": criteria,
                "vcs_score": vcs_score,
                "vcs_details": vcs_details,
                "n_contractions": n_contractions,
                "has_higher_lows": has_higher_lows,
                "minervini_ok": minervini_ok,
            },
            reason=reason,
        )
