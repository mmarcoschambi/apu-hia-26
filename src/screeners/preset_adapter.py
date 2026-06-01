"""
src/screeners/preset_adapter.py
===============================
Adapta las funciones heredadas de preset_filter_library a la interfaz BaseScreener.
Cada clase se registra en ScreenerRegistry para ser cargada de forma dinámica.
"""

from typing import Optional, Dict
import pandas as pd

from .base import BaseScreener, ScreenerConfig, ScreenerResult
from .registry import ScreenerRegistry
import src.strategies.preset_filter_library as pfl


@ScreenerRegistry.register
class LLHLConfirmedScreener(BaseScreener):
    @property
    def name(self) -> str:
        return "ll_hl_confirmed"

    @property
    def description(self) -> str:
        return "Detecta estructura LL -> HL con pivotes confirmados"

    def get_default_config(self) -> ScreenerConfig:
        return ScreenerConfig(
            name=self.name,
            params={"pivot_left": 3, "pivot_right": 3}
        )

    def scan(self, ticker: str, df: pd.DataFrame, spy_df: Optional[pd.DataFrame] = None, scan_date: Optional[str] = None) -> ScreenerResult:
        passed_base, reason_base = self.apply_base_filters(df)
        if not passed_base:
            return ScreenerResult(False, ticker, self.name, reason=reason_base)

        try:
            mask = pfl.ll_hl_confirmed(
                df,
                pivot_left=self.config.params.get("pivot_left", 3),
                pivot_right=self.config.params.get("pivot_right", 3)
            )
            passed = bool(mask.iloc[-1]) if len(mask) else False
            return ScreenerResult(
                passed=passed,
                ticker=ticker,
                screener_name=self.name,
                reason="LL-HL structure confirmed" if passed else "No confirmed LL-HL structure"
            )
        except Exception as e:
            return ScreenerResult(False, ticker, self.name, reason=f"Error: {e}")


@ScreenerRegistry.register
class Fib0618BreakScreener(BaseScreener):
    @property
    def name(self) -> str:
        return "fib_0618_break_between_hl_and_swing_high"

    @property
    def description(self) -> str:
        return "Ruptura del nivel 61.8% de Fibonacci entre HL y Swing High"

    def get_default_config(self) -> ScreenerConfig:
        return ScreenerConfig(
            name=self.name,
            params={"threshold": 0.10}
        )

    def scan(self, ticker: str, df: pd.DataFrame, spy_df: Optional[pd.DataFrame] = None, scan_date: Optional[str] = None) -> ScreenerResult:
        passed_base, reason_base = self.apply_base_filters(df)
        if not passed_base:
            return ScreenerResult(False, ticker, self.name, reason=reason_base)

        try:
            mask = pfl.fib_0618_break_between_hl_and_swing_high(
                df,
                threshold=self.config.params.get("threshold", 0.10)
            )
            passed = bool(mask.iloc[-1]) if len(mask) else False
            return ScreenerResult(
                passed=passed,
                ticker=ticker,
                screener_name=self.name,
                reason="Fibonacci 61.8% breakout confirmed" if passed else "No Fibonacci 61.8% breakout"
            )
        except Exception as e:
            return ScreenerResult(False, ticker, self.name, reason=f"Error: {e}")


@ScreenerRegistry.register
class SecondPivotBreakScreener(BaseScreener):
    @property
    def name(self) -> str:
        return "second_pivot_break_swing_high"

    @property
    def description(self) -> str:
        return "Ruptura de confirmación del segundo pivote high"

    def get_default_config(self) -> ScreenerConfig:
        return ScreenerConfig(
            name=self.name,
            params={"threshold": 0.10}
        )

    def scan(self, ticker: str, df: pd.DataFrame, spy_df: Optional[pd.DataFrame] = None, scan_date: Optional[str] = None) -> ScreenerResult:
        passed_base, reason_base = self.apply_base_filters(df)
        if not passed_base:
            return ScreenerResult(False, ticker, self.name, reason=reason_base)

        try:
            mask = pfl.second_pivot_break_swing_high(
                df,
                threshold=self.config.params.get("threshold", 0.10)
            )
            passed = bool(mask.iloc[-1]) if len(mask) else False
            return ScreenerResult(
                passed=passed,
                ticker=ticker,
                screener_name=self.name,
                reason="Second pivot breakout confirmed" if passed else "No second pivot breakout"
            )
        except Exception as e:
            return ScreenerResult(False, ticker, self.name, reason=f"Error: {e}")


@ScreenerRegistry.register
class DowntrendLineBreakScreener(BaseScreener):
    @property
    def name(self) -> str:
        return "downtrend_line_break"

    @property
    def description(self) -> str:
        return "Ruptura de línea de tendencia bajista"

    def get_default_config(self) -> ScreenerConfig:
        return ScreenerConfig(
            name=self.name,
            params={"max_lookback": 40}
        )

    def scan(self, ticker: str, df: pd.DataFrame, spy_df: Optional[pd.DataFrame] = None, scan_date: Optional[str] = None) -> ScreenerResult:
        passed_base, reason_base = self.apply_base_filters(df)
        if not passed_base:
            return ScreenerResult(False, ticker, self.name, reason=reason_base)

        try:
            mask = pfl.downtrend_line_break(
                df,
                max_lookback=self.config.params.get("max_lookback", 40)
            )
            passed = bool(mask.iloc[-1]) if len(mask) else False
            return ScreenerResult(
                passed=passed,
                ticker=ticker,
                screener_name=self.name,
                reason="Downtrend line break confirmed" if passed else "No downtrend line break"
            )
        except Exception as e:
            return ScreenerResult(False, ticker, self.name, reason=f"Error: {e}")


@ScreenerRegistry.register
class PowerPlayScreener(BaseScreener):
    @property
    def name(self) -> str:
        return "power_play"

    @property
    def description(self) -> str:
        return "Minervini Power Play: Ruptura violenta reciente con alta velocidad"

    def get_default_config(self) -> ScreenerConfig:
        return ScreenerConfig(
            name=self.name,
            params={"window": 10}
        )

    def scan(self, ticker: str, df: pd.DataFrame, spy_df: Optional[pd.DataFrame] = None, scan_date: Optional[str] = None) -> ScreenerResult:
        passed_base, reason_base = self.apply_base_filters(df)
        if not passed_base:
            return ScreenerResult(False, ticker, self.name, reason=reason_base)

        try:
            mask = pfl.power_play(
                df,
                window=self.config.params.get("window", 10)
            )
            passed = bool(mask.iloc[-1]) if len(mask) else False
            return ScreenerResult(
                passed=passed,
                ticker=ticker,
                screener_name=self.name,
                reason="Power Play pattern confirmed" if passed else "No Power Play pattern"
            )
        except Exception as e:
            return ScreenerResult(False, ticker, self.name, reason=f"Error: {e}")


@ScreenerRegistry.register
class WeeklyReturnMinScreener(BaseScreener):
    @property
    def name(self) -> str:
        return "weekly_return_min"

    @property
    def description(self) -> str:
        return "Retorno mínimo en 5 días (ej. +20% en 1 semana)"

    def get_default_config(self) -> ScreenerConfig:
        return ScreenerConfig(
            name=self.name,
            params={"minimum_pct": 20.0}
        )

    def scan(self, ticker: str, df: pd.DataFrame, spy_df: Optional[pd.DataFrame] = None, scan_date: Optional[str] = None) -> ScreenerResult:
        passed_base, reason_base = self.apply_base_filters(df)
        if not passed_base:
            return ScreenerResult(False, ticker, self.name, reason=reason_base)

        try:
            mask = pfl.weekly_return_min(
                df,
                minimum_pct=self.config.params.get("minimum_pct", 20.0)
            )
            passed = bool(mask.iloc[-1]) if len(mask) else False
            return ScreenerResult(
                passed=passed,
                ticker=ticker,
                screener_name=self.name,
                reason="Weekly return threshold exceeded" if passed else "Weekly return below threshold"
            )
        except Exception as e:
            return ScreenerResult(False, ticker, self.name, reason=f"Error: {e}")


@ScreenerRegistry.register
class Near52wHighBandScreener(BaseScreener):
    @property
    def name(self) -> str:
        return "near_52w_high_band"

    @property
    def description(self) -> str:
        return "Precio se encuentra dentro del rango porcentual del máximo de 52 semanas"

    def get_default_config(self) -> ScreenerConfig:
        return ScreenerConfig(
            name=self.name,
            params={"min_pct": 0.0, "max_pct": 15.0}
        )

    def scan(self, ticker: str, df: pd.DataFrame, spy_df: Optional[pd.DataFrame] = None, scan_date: Optional[str] = None) -> ScreenerResult:
        passed_base, reason_base = self.apply_base_filters(df)
        if not passed_base:
            return ScreenerResult(False, ticker, self.name, reason=reason_base)

        try:
            mask = pfl.near_52w_high_band(
                df,
                min_pct=self.config.params.get("min_pct", 0.0),
                max_pct=self.config.params.get("max_pct", 15.0)
            )
            passed = bool(mask.iloc[-1]) if len(mask) else False
            return ScreenerResult(
                passed=passed,
                ticker=ticker,
                screener_name=self.name,
                reason="Inside 52w high band" if passed else "Outside 52w high band"
            )
        except Exception as e:
            return ScreenerResult(False, ticker, self.name, reason=f"Error: {e}")


@ScreenerRegistry.register
class VCSScoreMinScreener(BaseScreener):
    @property
    def name(self) -> str:
        return "vcs_score_min"

    @property
    def description(self) -> str:
        return "VCS Score de VCP de Mark Minervini superior al mínimo"

    def get_default_config(self) -> ScreenerConfig:
        return ScreenerConfig(
            name=self.name,
            params={"minimum": 55.0}
        )

    def scan(self, ticker: str, df: pd.DataFrame, spy_df: Optional[pd.DataFrame] = None, scan_date: Optional[str] = None) -> ScreenerResult:
        passed_base, reason_base = self.apply_base_filters(df)
        if not passed_base:
            return ScreenerResult(False, ticker, self.name, reason=reason_base)

        try:
            mask = pfl.vcs_score_min(
                df,
                minimum=self.config.params.get("minimum", 55.0)
            )
            passed = bool(mask.iloc[-1]) if len(mask) else False
            return ScreenerResult(
                passed=passed,
                ticker=ticker,
                screener_name=self.name,
                reason="VCS score threshold exceeded" if passed else "VCS score below threshold"
            )
        except Exception as e:
            return ScreenerResult(False, ticker, self.name, reason=f"Error: {e}")


@ScreenerRegistry.register
class TrendBaseScreener(BaseScreener):
    @property
    def name(self) -> str:
        return "trend_base"

    @property
    def description(self) -> str:
        return "Filtro estructural de tendencia"

    def get_default_config(self) -> ScreenerConfig:
        return ScreenerConfig(
            name=self.name,
            params={"min_above_sma200": 0.0}
        )

    def scan(self, ticker: str, df: pd.DataFrame, spy_df: Optional[pd.DataFrame] = None, scan_date: Optional[str] = None) -> ScreenerResult:
        passed_base, reason_base = self.apply_base_filters(df)
        if not passed_base:
            return ScreenerResult(False, ticker, self.name, reason=reason_base)

        try:
            mask = pfl.trend_base(
                df,
                min_above_sma200=self.config.params.get("min_above_sma200", 0.0)
            )
            passed = bool(mask.iloc[-1]) if len(mask) else False
            return ScreenerResult(
                passed=passed,
                ticker=ticker,
                screener_name=self.name,
                reason="Trend base criteria met" if passed else "Trend base criteria failed"
            )
        except Exception as e:
            return ScreenerResult(False, ticker, self.name, reason=f"Error: {e}")


@ScreenerRegistry.register
class RelVolumeMinScreener(BaseScreener):
    @property
    def name(self) -> str:
        return "rel_volume_min"

    @property
    def description(self) -> str:
        return "Volumen relativo superior al mínimo"

    def get_default_config(self) -> ScreenerConfig:
        return ScreenerConfig(
            name=self.name,
            params={"minimum": 1.5, "period": 50}
        )

    def scan(self, ticker: str, df: pd.DataFrame, spy_df: Optional[pd.DataFrame] = None, scan_date: Optional[str] = None) -> ScreenerResult:
        passed_base, reason_base = self.apply_base_filters(df)
        if not passed_base:
            return ScreenerResult(False, ticker, self.name, reason=reason_base)

        try:
            mask = pfl.rel_volume_min(
                df,
                minimum=self.config.params.get("minimum", 1.5),
                period=self.config.params.get("period", 50)
            )
            passed = bool(mask.iloc[-1]) if len(mask) else False
            return ScreenerResult(
                passed=passed,
                ticker=ticker,
                screener_name=self.name,
                reason="Relative volume above minimum" if passed else "Relative volume below minimum"
            )
        except Exception as e:
            return ScreenerResult(False, ticker, self.name, reason=f"Error: {e}")
