"""
src/signals/signal_engine.py
Canonical Signal Engine — único motor usado por live y backtest.

Contrato: (ticker, df, spy_df, combo_cfg, mode) -> SignalDecision

Modes:
    A        → combo_pure_momentum (qullamaggie + breakout)
    B        → combo_stage2_breakout (minervini + breakout)
    A_BOTH   → Union de A y B, ranking por score

El engine ES EL MISMO para live y backtest. Si diverge, el test de paridad falla.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Literal, Optional

import numpy as np
import pandas as pd

from src.screeners.pipeline import ScreenerPipeline
from src.screeners.registry import ScreenerRegistry

logger = logging.getLogger(__name__)


SignalMode = Literal["A", "B", "A_BOTH"]


class RejectReason(str):
    pass


@dataclass
class Tier2Metrics:
    rvol: float = 0.0
    adr_pct: float = 0.0
    dist_sma20: float = 0.0
    consol_days: int = 0
    volume: float = 0.0
    dollar_vol_M: float = 0.0
    rs_ret: Optional[float] = None
    rs_percentile: Optional[float] = None
    close: float = 0.0
    spy_above_sma50: bool = True
    spy_above_sma200: bool = True

    def to_dict(self) -> dict:
        return {
            "rvol": self.rvol,
            "adr_pct": self.adr_pct,
            "dist_sma20": self.dist_sma20,
            "consol_days": self.consol_days,
            "volume": self.volume,
            "dollar_vol_M": self.dollar_vol_M,
            "rs_ret": self.rs_ret,
            "rs_percentile": self.rs_percentile,
            "close": self.close,
            "spy_above_sma50": self.spy_above_sma50,
            "spy_above_sma200": self.spy_above_sma200,
        }


@dataclass
class SignalDecision:
    """Output canónico del motor de señal."""

    ticker: str
    mode: SignalMode
    passed: bool
    entry_score: float = 0.0
    screener_score: float = 0.0
    tier2_score: float = 0.0
    reject_reason: str = ""
    tier2_metrics: Tier2Metrics = field(default_factory=Tier2Metrics)
    screener_reason: str = ""
    signal_type: str = "breakout"
    cost_model: dict = field(default_factory=dict)

    @property
    def composite_score(self) -> float:
        return self.entry_score

    @property
    def reject_contract(self) -> str:
        if self.passed:
            return "APPROVED"
        return self.reject_reason

    def to_dict(self) -> dict:
        return {
            "ticker": self.ticker,
            "mode": self.mode,
            "passed": self.passed,
            "entry_score": self.entry_score,
            "screener_score": self.screener_score,
            "tier2_score": self.tier2_score,
            "reject_reason": self.reject_reason,
            "screener_reason": self.screener_reason,
            "signal_type": self.signal_type,
            "cost_model": self.cost_model,
            "tier2_metrics": self.tier2_metrics.to_dict(),
        }

    @classmethod
    def from_dict(cls, d: dict) -> SignalDecision:
        m = d.get("tier2_metrics", {})
        t2m = Tier2Metrics(**m) if isinstance(m, dict) else Tier2Metrics()
        return cls(
            ticker=d["ticker"],
            mode=d["mode"],
            passed=d["passed"],
            entry_score=d.get("entry_score", 0.0),
            screener_score=d.get("screener_score", 0.0),
            tier2_score=d.get("tier2_score", 0.0),
            reject_reason=d.get("reject_reason", ""),
            screener_reason=d.get("screener_reason", ""),
            signal_type=d.get("signal_type", "breakout"),
            cost_model=d.get("cost_model", {}),
            tier2_metrics=t2m,
        )


def compute_tier2_metrics(
    df: pd.DataFrame,
    spy_df: Optional[pd.DataFrame] = None,
    rs_lookback: int = 60,
) -> Tier2Metrics:
    """Calcula métricas Tier2 desde OHLCV. Mismo cálculo en live y backtest."""
    if len(df) < 20:
        return Tier2Metrics()

    close = df["close"]
    high = df["high"]
    low = df["low"]
    volume = df["volume"]

    sma20 = close.rolling(20).mean()
    avg_vol = volume.rolling(20).mean().replace(0, np.nan)
    rvol = (
        (volume / avg_vol).iloc[-1]
        if not np.isnan(volume.iloc[-1] / avg_vol.iloc[-1])
        else 0.0
    )
    adr = (((high - low) / close.replace(0, np.nan)) * 100).rolling(20).mean().iloc[-1]
    adr = 0.0 if np.isnan(adr) else adr
    dist_sma20_val = (
        (close - sma20.replace(0, np.nan)) / sma20.replace(0, np.nan) * 100
    ).iloc[-1]
    dist_sma20_val = 0.0 if np.isnan(dist_sma20_val) else dist_sma20_val
    bb_std = close.rolling(20).std()
    inside_bb = (close >= sma20 - bb_std * 2) & (close <= sma20 + bb_std * 2)
    consol_days = int(inside_bb.rolling(20).sum().iloc[-1])
    dollar_vol = (
        (close * avg_vol).iloc[-1] if not np.isnan((close * avg_vol).iloc[-1]) else 0.0
    )

    rs_ret: Optional[float] = None
    if (
        spy_df is not None
        and len(df) >= rs_lookback + 5
        and len(spy_df) >= rs_lookback + 5
    ):
        try:
            period = min(rs_lookback, len(df) - 1, len(spy_df) - 1)
            if period > 10:
                ticker_ret = float(close.iloc[-1] / close.iloc[-period - 1] - 1)
                spy_close = (
                    spy_df["close"] if "close" in spy_df.columns else spy_df["Close"]
                )
                spy_ret = float(spy_close.iloc[-1] / spy_close.iloc[-period - 1] - 1)
                rs_ret = ticker_ret - spy_ret
        except Exception:
            pass

    # Market Regime checks
    spy_above_sma50 = True
    spy_above_sma200 = True
    if spy_df is not None:
        spy_close = spy_df["close"] if "close" in spy_df.columns else spy_df["Close"]
        if len(spy_df) >= 50:
            spy_sma50 = spy_close.rolling(50).mean().iloc[-1]
            spy_above_sma50 = float(spy_close.iloc[-1]) > float(spy_sma50)
        if len(spy_df) >= 200:
            spy_sma200 = spy_close.rolling(200).mean().iloc[-1]
            spy_above_sma200 = float(spy_close.iloc[-1]) > float(spy_sma200)

    return Tier2Metrics(
        rvol=float(rvol) if not np.isnan(rvol) else 0.0,
        adr_pct=adr,
        dist_sma20=dist_sma20_val,
        consol_days=consol_days,
        volume=float(volume.iloc[-1]),
        dollar_vol_M=float(dollar_vol) / 1e6,
        rs_ret=rs_ret,
        rs_percentile=None,
        close=float(close.iloc[-1]),
        spy_above_sma50=spy_above_sma50,
        spy_above_sma200=spy_above_sma200,
    )


def apply_tier2_filters(metrics: Tier2Metrics, t2_cfg: dict) -> tuple[bool, str]:
    """Evalúa métricas contra umbrales Tier2. Mismo en live y backtest."""
    if metrics.rvol < t2_cfg.get("min_rvol", 0):
        return (
            False,
            f"tier2_fail:rvol:{metrics.rvol:.2f}<{t2_cfg.get('min_rvol', 0):.2f}",
        )
    if metrics.adr_pct < t2_cfg.get("min_adr", 0):
        return (
            False,
            f"tier2_fail:adr_pct:{metrics.adr_pct:.2f}<{t2_cfg.get('min_adr', 0):.2f}",
        )
    if metrics.dist_sma20 > t2_cfg.get("max_dist_sma20", 999):
        return (
            False,
            f"tier2_fail:dist_sma20:{metrics.dist_sma20:.2f}>{t2_cfg.get('max_dist_sma20', 999):.2f}",
        )
    if metrics.dollar_vol_M * 1e6 < t2_cfg.get("min_dollar_volume", 0):
        return (
            False,
            f"tier2_fail:dollar_vol:{metrics.dollar_vol_M:.1f}M<{t2_cfg.get('min_dollar_volume', 0) / 1e6:.1f}M",
        )
    if metrics.consol_days < t2_cfg.get("min_consolidation_days", 0):
        return (
            False,
            f"tier2_fail:consol_days:{metrics.consol_days}<{t2_cfg.get('min_consolidation_days', 0)}",
        )
    if metrics.volume < t2_cfg.get("min_volume", 0):
        return (
            False,
            f"tier2_fail:volume:{metrics.volume:.0f}<{t2_cfg.get('min_volume', 0)}",
        )
    if t2_cfg.get("require_positive_rs", False):
        if metrics.rs_ret is None or metrics.rs_ret <= 0:
            rs_display = (
                f"{metrics.rs_ret:.4f}" if metrics.rs_ret is not None else "None"
            )
            return False, f"tier2_fail:rs_ret:{rs_display}<=0"
    if t2_cfg.get("use_rs_percentile", False):
        rs_pct = metrics.rs_percentile
        min_rs_pct = float(t2_cfg.get("min_rs_percentile", 0.0))
        if rs_pct is None or rs_pct < min_rs_pct:
            return False, f"tier2_fail:rs_percentile:{rs_pct}<{min_rs_pct:.1f}"
    
    if t2_cfg.get("require_spy_above_sma50", False):
        if not metrics.spy_above_sma50:
            return False, "tier2_fail:market_regime:spy_below_sma50"

    if t2_cfg.get("require_spy_above_sma200", False):
        if not metrics.spy_above_sma200:
            return False, "tier2_fail:market_regime:spy_below_sma200"

    return True, "passed"


def evaluate_ticker(
    ticker: str,
    df: pd.DataFrame,
    spy_df: Optional[pd.DataFrame],
    combo_cfg: dict,
    mode: SignalMode = "A",
    skip_tier2: bool = False,
    rs_percentile: Optional[float] = None,
    scan_date: Optional[str] = None,
) -> SignalDecision:
    """
    Evaluación canónica de un ticker contra un combo.

    Esta función es EL PUNTO DE VERDAD para la lógica de señal.
    Live y backtest DEBEN llamar esta función — si producen resultados
    distintos, el test de paridad detecta el bug.

    Args:
        ticker:        Símbolo.
        df:            DataFrame OHLCV (índice es fecha, columnas lowercase).
        spy_df:        SPY OHLCV para RS.
        combo_cfg:     Config JSON del combo (screener, tier2_filters, pattern).
        mode:          A | B | A_BOTH (actúa como filtro de cuál combo se evalúa).
        skip_tier2:    Para debugging — saltar filtros Tier2.
        rs_percentile: Precalculado (None = calcular inline).

    Returns:
        SignalDecision con passed, scores, rechazo, y métricas.
    """
    if len(df) < 65:
        return SignalDecision(
            ticker=ticker,
            mode=mode,
            passed=False,
            reject_reason="insufficient_data",
        )

    screener_cfg = combo_cfg.get("screener", {})
    t2_cfg = combo_cfg.get("tier2_filters", {})
    pattern_cfg = combo_cfg.get("pattern", {})

    screener_name = screener_cfg.get("name")
    pipeline: Optional[ScreenerPipeline] = None
    if screener_name:
        try:
            # 1. Cargar config base de disco o default
            config = ScreenerRegistry.load_config(screener_name)
            
            # 2. Aplicar overrides desde combo_cfg (que pueden venir de la memoria/argumentos)
            # Esto es CRÍTICO para que los experimentos funcionen
            if "min_adr_pct" in screener_cfg:
                config.min_adr_pct = screener_cfg["min_adr_pct"]
            if "params" in screener_cfg:
                config.params.update(screener_cfg["params"])
            
            logger.debug(f"Screener {screener_name} FINAL PARAMS: {config.params}")

            screener = ScreenerRegistry.get(screener_name, config)
            pipeline = ScreenerPipeline(
                [screener], mode=screener_cfg.get("mode", "all")
            )
        except Exception as e:
            logger.debug(f"Screener init error {screener_name}: {e}")

    screener_passed = True
    screener_score = 0.0
    screener_reason = ""
    screener_metrics = {}

    if pipeline:
        try:
            result = pipeline.scan(ticker, df, spy_df, scan_date=scan_date)
            screener_passed = result.passed
            screener_score = result.score
            screener_reason = result.reason
            screener_metrics = result.metrics or {}
        except Exception as e:
            logger.debug(f"Screener scan error {ticker}: {e}")
            screener_passed = False
            screener_reason = f"screener_fail:error:{e}"

    if not screener_passed:
        return SignalDecision(
            ticker=ticker,
            mode=mode,
            passed=False,
            reject_reason=f"screener_fail:{screener_reason}",
            screener_score=screener_score,
            screener_reason=screener_reason,
            signal_type=pattern_cfg.get("signal_type", "breakout"),
        )

    metrics = compute_tier2_metrics(df, spy_df)
    
    # Intentar obtener RS Percentile si no se proporcionó uno
    if rs_percentile is not None:
        metrics.rs_percentile = rs_percentile
    elif scan_date and t2_cfg.get("use_rs_percentile", False):
        try:
            from src.data.rs_rankings import get_rs_percentile
            metrics.rs_percentile = get_rs_percentile(
                ticker, date=scan_date, metric=t2_cfg.get("rs_metric", "rs_composite")
            )
        except Exception as e:
            logger.debug(f"Tier2 RS lookup error {ticker}: {e}")

    if not skip_tier2:
        tier2_ok, tier2_reason = apply_tier2_filters(metrics, t2_cfg)
        if not tier2_ok:
            return SignalDecision(
                ticker=ticker,
                mode=mode,
                passed=False,
                reject_reason=tier2_reason,
                screener_score=screener_score,
                screener_reason=screener_reason,
                tier2_metrics=metrics,
                signal_type=pattern_cfg.get("signal_type", "breakout"),
            )

    entry_score = round(screener_score / 100.0, 3)
    cost_model = {
        "fee_rate": combo_cfg.get("tier3_fixed", {}).get("fee_rate", 0.001),
        "slippage_rate": combo_cfg.get("tier3_fixed", {}).get("slippage_rate", 0.0005),
    }

    return SignalDecision(
        ticker=ticker,
        mode=mode,
        passed=True,
        entry_score=entry_score,
        screener_score=round(screener_score, 1),
        tier2_score=1.0,
        reject_reason="",
        tier2_metrics=metrics,
        screener_reason=screener_reason,
        signal_type=pattern_cfg.get("signal_type", "breakout"),
        cost_model=cost_model,
    )


def scan_universe(
    universe: list[str],
    df_map: dict[str, pd.DataFrame],
    spy_df: Optional[pd.DataFrame],
    combo_cfg: dict,
    mode: SignalMode = "A",
    skip_tier2: bool = False,
) -> list[SignalDecision]:
    """
    Escanea un universo completo con el motor canónico.

    Args:
        universe:   Lista de tickers.
        df_map:     Pre-cargado: {ticker: df_ohlcv}. Mismo df para live y backtest.
        spy_df:     SPY OHLCV.
        combo_cfg:  Config del combo.
        mode:       A | B | A_BOTH.
        skip_tier2: Para tests y dry-runs.

    Returns:
        Lista de SignalDecision (solo los passed=True, ordenados por entry_score desc).
    """
    results: list[SignalDecision] = []

    for ticker in universe:
        df = df_map.get(ticker)
        if df is None or len(df) < 65:
            continue

        decision = evaluate_ticker(ticker, df, spy_df, combo_cfg, mode, skip_tier2)
        if decision.passed:
            results.append(decision)

    results.sort(key=lambda x: x.entry_score, reverse=True)
    return results


def merge_ab_signals(
    signals_a: list[SignalDecision],
    signals_b: list[SignalDecision],
) -> list[SignalDecision]:
    """
    Combina señales de A y B en ranking unificado por composite_score.

    Si un ticker aparece en ambos (A+B overlap), se prioriza por:
    1. Mayor entry_score
    2. Tie-break: modo del score más alto

    Args:
        signals_a: Lista de SignalDecision A (passed=True).
        signals_b: Lista de SignalDecision B (passed=True).

    Returns:
        Lista combinada ordenada por score desc.
    """
    seen: dict[str, SignalDecision] = {}

    for sig in signals_a:
        sig.mode = "A"
        seen[sig.ticker] = sig

    for sig in signals_b:
        sig.mode = "B"
        existing = seen.get(sig.ticker)
        if existing is None:
            sig.mode = "A_BOTH"
            seen[sig.ticker] = sig
        else:
            if sig.entry_score > existing.entry_score:
                existing.mode = "A_BOTH"
                existing.entry_score = sig.entry_score
                existing.screener_score = sig.screener_score
                existing.tier2_metrics = sig.tier2_metrics
                existing.screener_reason = sig.screener_reason
                existing.tier2_score = sig.tier2_score
            else:
                existing.mode = "A_BOTH"

    merged = list(seen.values())
    merged.sort(key=lambda x: x.entry_score, reverse=True)
    return merged


def decision_to_dict(d: SignalDecision) -> dict:
    """Serialización estándar para archivos CSV/JSON."""
    return d.to_dict()


def decisions_to_df(decisions: list[SignalDecision]) -> pd.DataFrame:
    """Convierte lista de decisiones a DataFrame."""
    rows = []
    for dec in decisions:
        row = {
            "ticker": dec.ticker,
            "mode": dec.mode,
            "passed": dec.passed,
            "entry_score": dec.entry_score,
            "screener_score": dec.screener_score,
            "tier2_score": dec.tier2_score,
            "reject_reason": dec.reject_reason,
            "screener_reason": dec.screener_reason,
            "signal_type": dec.signal_type,
            "rvol": dec.tier2_metrics.rvol,
            "adr_pct": dec.tier2_metrics.adr_pct,
            "dist_sma20": dec.tier2_metrics.dist_sma20,
            "consol_days": dec.tier2_metrics.consol_days,
            "volume": dec.tier2_metrics.volume,
            "dollar_vol_M": dec.tier2_metrics.dollar_vol_M,
            "rs_ret": dec.tier2_metrics.rs_ret,
            "rs_percentile": dec.tier2_metrics.rs_percentile,
            "close": dec.tier2_metrics.close,
        }
        rows.append(row)
    return pd.DataFrame(rows)
