"""
src/signals/backtest_adapter.py
Adapter que conecta el motor canónico con daily_engine.

Permite que daily_engine use SignalDecision para generar señales
manteniendo intacta toda la lógica de exits/position sizing/risk management.
"""

from __future__ import annotations

from typing import Optional
import pandas as pd

from src.signals.signal_engine import (
    SignalDecision,
    evaluate_ticker,
    SignalMode,
)


def ticker_to_signal_decision(
    symbol: str,
    df: pd.DataFrame,
    spy_df: pd.DataFrame | None,
    combo_cfg: dict,
    mode: SignalMode = "A",
    rs_percentile: Optional[float] = None,
) -> SignalDecision:
    """
    Wrapper para que daily_engine genere una SignalDecision
    a partir del mismo flujo que live.

    Si df < 65 filas o falla el screener/tier2 → decision.passed=False.
    """
    return evaluate_ticker(
        ticker=symbol,
        df=df,
        spy_df=spy_df,
        combo_cfg=combo_cfg,
        mode=mode,
        skip_tier2=False,
        rs_percentile=rs_percentile,
    )


def decisions_to_screener_format(
    decisions: list[SignalDecision],
) -> list[dict]:
    """
    Convierte SignalDecision al formato que _run_daily_screener()
    espera en raw_candidates (diccionario plano con símbolos candidatos).

    Formato de salida compatible con la interfaz interna de daily_engine.
    """
    candidates = []
    for d in decisions:
        if not d.passed:
            continue
        cand = {
            "symbol": d.ticker,
            "score": d.entry_score,
            "screener_score": d.screener_score,
            "screener_reason": d.screener_reason,
            "signal_type": d.signal_type,
            "rvol": d.tier2_metrics.rvol,
            "adr_pct": d.tier2_metrics.adr_pct,
            "dist_sma20": d.tier2_metrics.dist_sma20,
            "consol_days": d.tier2_metrics.consol_days,
            "volume": d.tier2_metrics.volume,
            "dollar_vol": d.tier2_metrics.dollar_vol_M * 1e6,
            "close": d.tier2_metrics.close,
            "rs_ret": d.tier2_metrics.rs_ret,
            "rs_percentile": d.tier2_metrics.rs_percentile,
            "mode": d.mode,
            "reject_reason": d.reject_reason,
            "cost_model": d.cost_model,
        }
        candidates.append(cand)
    return candidates
