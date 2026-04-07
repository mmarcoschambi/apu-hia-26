"""
src/screeners/base.py
BaseScreener, ScreenerResult y ScreenerConfig.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
import pandas as pd
import numpy as np


@dataclass
class ScreenerResult:
    """Resultado de la evaluación de un screener sobre un ticker."""

    passed: bool
    ticker: str
    screener_name: str
    score: float = 0.0  # 0-100, para ranking
    metrics: Dict = field(default_factory=dict)
    reason: str = ""  # Descripción de por qué pasó/falló


@dataclass
class ScreenerConfig:
    """Configuración portable y serializable de un screener."""

    name: str
    enabled: bool = True
    # Filtros base comunes
    min_price: float = 5.0
    max_price: float = 500.0
    min_avg_volume: int = 300_000
    min_dollar_volume: float = 15_000_000
    min_adr_pct: float = 1.5
    max_adr_pct: float = 15.0
    # Parámetros específicos del screener
    params: Dict = field(default_factory=dict)


class BaseScreener(ABC):
    """Interface común para todos los screeners del sistema."""

    def __init__(self, config: Optional[ScreenerConfig] = None):
        self.config = config or self.get_default_config()

    @property
    @abstractmethod
    def name(self) -> str:
        """Identificador único del screener."""

    @property
    @abstractmethod
    def description(self) -> str:
        """Descripción breve del screener."""

    @property
    def compatible_patterns(self) -> List[str]:
        """Patrones de entrada con los que funciona bien este screener."""
        return ["any"]

    @abstractmethod
    def scan(
        self,
        ticker: str,
        df: pd.DataFrame,
        spy_df: Optional[pd.DataFrame] = None,
        scan_date: Optional[str] = None,
    ) -> ScreenerResult:
        """
        Evalúa un ticker.

        Args:
            ticker: Símbolo bursátil.
            df:     DataFrame con columnas OHLCV + indicadores precalculados.
            spy_df: DataFrame de SPY para RS relativo (opcional).
            scan_date: Fecha point-in-time usada por screeners con dependencia temporal.

        Returns:
            ScreenerResult con passed, score y métricas detalladas.
        """

    @abstractmethod
    def get_default_config(self) -> ScreenerConfig:
        """Retorna la configuración por defecto del screener."""

    # ------------------------------------------------------------------ #
    # Helpers comunes
    # ------------------------------------------------------------------ #

    def apply_base_filters(self, df: pd.DataFrame) -> Tuple[bool, str]:
        """
        Filtros básicos compartidos por todos los screeners.
        Retorna (passed, reason).
        """
        if len(df) < 50:
            return False, f"Historia insuficiente ({len(df)} barras < 50)"

        row = df.iloc[-1]
        price = float(row.get("close", row.get("Close", 0)))

        if price <= 0:
            return False, "Precio inválido"
        if price < self.config.min_price:
            return False, f"Precio ${price:.2f} < mínimo ${self.config.min_price}"
        if price > self.config.max_price:
            return False, f"Precio ${price:.2f} > máximo ${self.config.max_price}"

        # ADR
        adr_col = next(
            (c for c in ("adr_pct", "adr_pct_20", "adr_14") if c in df.columns), None
        )
        if adr_col:
            adr = float(row[adr_col])
            if adr < self.config.min_adr_pct:
                return False, f"ADR {adr:.2f}% < {self.config.min_adr_pct}%"
            if adr > self.config.max_adr_pct:
                return False, f"ADR {adr:.2f}% > {self.config.max_adr_pct}%"

        return True, "OK"

    @staticmethod
    def ensure_ma(
        df: pd.DataFrame, period: int, col: str = "close", kind: str = "sma"
    ) -> pd.Series:
        """
        Calcula una MA si no está presente en el DataFrame.
        kind: 'sma' | 'ema'
        """
        col_name = f"{'ema' if kind == 'ema' else 'sma'}{period}"
        if col_name in df.columns:
            return df[col_name]
        src = df[col] if col in df.columns else df[col.capitalize()]
        if kind == "ema":
            return src.ewm(span=period, adjust=False).mean()
        return src.rolling(period).mean()

    @staticmethod
    def ensure_atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
        """Calcula ATR si no está presente."""
        if f"atr{period}" in df.columns:
            return df[f"atr{period}"]
        h = df["high"] if "high" in df.columns else df["High"]
        l = df["low"] if "low" in df.columns else df["Low"]
        c = df["close"] if "close" in df.columns else df["Close"]
        c_prev = c.shift(1)
        tr = pd.concat([h - l, (h - c_prev).abs(), (l - c_prev).abs()], axis=1).max(
            axis=1
        )
        return tr.rolling(period).mean()
