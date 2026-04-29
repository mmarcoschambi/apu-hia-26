"""
src/analytics/backtest_analytics_bridge.py
===========================================
Bridge entre backtest engines y el schema canónico de analytics S1.

Convierte el output de run_backtest() (vectorbt_engine_advanced, daily_engine)
al schema canónico con régimen cards y system vs actual.

API principal:
    compute_backtest_analytics(results, trades_df, equity_curve, ...) -> dict
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

# === CONSTANTS ===

DEFAULT_CAPITAL = 100_000
RISK_PER_TRADE_PCT = 0.02  # 2% default


# === REGIME CLASSIFICATION (reused from S1) ===


def classify_regime_bin(market_score: float) -> str:
    """Clasifica market_score en bins."""
    if market_score is None or pd.isna(market_score):
        return "UNKNOWN"
    if market_score < 25:
        return "BEAR"
    elif market_score < 50:
        return "NEUTRAL_WEAK"
    elif market_score <= 80:
        return "FAVORABLE"
    else:
        return "STRONG"


def classify_kelly_tier(
    market_score: float, regime_quality: str = "OK"
) -> Tuple[str, float]:
    """Calcula Kelly tier y fracción."""
    if market_score is None or pd.isna(market_score):
        return "UNKNOWN", 0.25
    if 50 <= market_score <= 80 and regime_quality == "OK":
        return "HALF", 0.5
    else:
        return "QUARTER", 0.25


# === TRADES CONVERSION ===


def backtest_trades_to_r(
    trades_df: pd.DataFrame,
    initial_capital: float = DEFAULT_CAPITAL,
    risk_per_trade_pct: float = RISK_PER_TRADE_PCT,
) -> List[Dict]:
    """
    Convierte trades del backtest (pnl en $) a pnl_r (R-múltiplos).

    Args:
        trades_df: DataFrame con columnas pnl, return_pct (del engine)
        initial_capital: Capital inicial del backtest
        risk_per_trade_pct: Porcentaje de riesgo por trade (default 2%)

    Returns:
        Lista de dicts con pnl_r normalizado
    """
    if trades_df is None or trades_df.empty:
        return []

    risk_per_trade = initial_capital * risk_per_trade_pct

    trades_r = []
    for _, row in trades_df.iterrows():
        pnl = row.get("pnl", 0)
        pnl_r = pnl / risk_per_trade if risk_per_trade > 0 else 0.0

        trades_r.append(
            {
                "ticker": row.get("symbol", row.get("ticker", "UNKNOWN")),
                "combo": row.get("combo", row.get("strategy", "UNKNOWN")),
                "entry_date": row.get("entry_date"),
                "exit_date": row.get("exit_date"),
                "pnl": pnl,
                "pnl_r": round(pnl_r, 4),
                "return_pct": row.get("return_pct", 0),
                "exit_phase": row.get("exit_phase"),
            }
        )

    return trades_r


# === REGIME CARDS ===


def get_regime_from_classifier(entry_date, classifier) -> Optional[str]:
    """Obtiene régimen del clasificador para una fecha."""
    if classifier is None:
        return None
    try:
        stage = classifier.get_market_stage(entry_date)
        return stage
    except Exception:
        return None


def get_regime_estimated(equity_series: pd.Series, entry_date) -> str:
    """Fallback: estima régimen desde posición del equity en la fecha."""
    if equity_series is None or equity_series.empty:
        return "UNKNOWN"

    try:
        entry_idx = equity_series.index.get_loc(pd.to_datetime(entry_date))
        window_before = equity_series.iloc[max(0, entry_idx - 20) : entry_idx]

        if len(window_before) < 5:
            return "NEUTRAL"

        # Simple heuristic: equity trend over last 20 days
        slope = (window_before.iloc[-1] - window_before.iloc[0]) / window_before.iloc[0]
        if slope > 0.03:
            return "BULL"
        elif slope < -0.03:
            return "BEAR"
        else:
            return "NEUTRAL"
    except Exception:
        return "UNKNOWN"


def build_regime_cards(
    trades: List[Dict],
    equity_curve: pd.Series,
    regime_classifier=None,
    initial_capital: float = DEFAULT_CAPITAL,
) -> List[Dict]:
    """
    Construye las 4 regime cards: <25, 25-50, 50-80, >80.

    Mapea BULL/NEUTRAL/BEAR del clasificador a los bins numéricos.
    Si no hay clasificador, usa estimación y marca régimen como estimated.
    """
    # Map classifier stages to bins
    stage_to_bin = {
        "BULL": ">80",
        "NEUTRAL": "50-80",
        "NEUTRAL_WEAK": "25-50",
        "BEAR": "<25",
    }

    bin_labels = {
        "<25": "BEAR",
        "25-50": "NEUTRAL_WEAK",
        "50-80": "FAVORABLE",
        ">80": "STRONG",
    }

    # Group trades by regime bin
    bins = {"<25": [], "25-50": [], "50-80": [], ">80": []}

    for trade in trades:
        entry_date = trade.get("entry_date")
        if entry_date is None:
            continue

        # Try classifier first
        regime_stage = get_regime_from_classifier(entry_date, regime_classifier)

        if regime_stage is None:
            # Fallback to estimated
            regime_stage = get_regime_estimated(equity_curve, entry_date)
            source = "estimated"
        else:
            source = "classifier"

        bin_name = stage_to_bin.get(regime_stage, "50-80")
        bins[bin_name].append((trade, source))

    cards = []

    for bin_name in ["<25", "25-50", "50-80", ">80"]:
        trades_in_bin, sources = zip(*bins[bin_name]) if bins[bin_name] else ([], [])

        n_trades = len(trades_in_bin)

        if n_trades == 0:
            cards.append(
                {
                    "regime_bin": bin_name,
                    "label": bin_labels[bin_name],
                    "trade_count": 0,
                    "win_rate": 0.0,
                    "avg_pnl_pct": 0.0,
                    "avg_pnl_r": 0.0,
                    "kelly_tier": "QUARTER",
                    "cash_ratio": 0.25,
                    "regime_source": "classifier" if sources else "none",
                }
            )
            continue

        wins = sum(1 for t in trades_in_bin if t.get("pnl", 0) > 0)
        win_rate = (wins / n_trades * 100) if n_trades > 0 else 0.0

        avg_pnl_pct = sum(t.get("return_pct", 0) for t in trades_in_bin) / n_trades
        avg_pnl_r = sum(t.get("pnl_r", 0) for t in trades_in_bin) / n_trades

        # Kelly tier based on regime
        if bin_name == "50-80":
            kelly_tier, kelly_frac = "HALF", 0.5
        else:
            kelly_tier, kelly_frac = "QUARTER", 0.25

        cash_ratio = 0.25 if bin_name in ["<25", "25-50"] else 0.15

        # Regime source majority
        source_counts = {"classifier": 0, "estimated": 0}
        for s in sources:
            if s in source_counts:
                source_counts[s] += 1
        regime_source = (
            "estimated"
            if source_counts["estimated"] > source_counts["classifier"]
            else "classifier"
        )

        cards.append(
            {
                "regime_bin": bin_name,
                "label": bin_labels[bin_name],
                "trade_count": n_trades,
                "win_rate": round(win_rate, 2),
                "avg_pnl_pct": round(avg_pnl_pct, 2),
                "avg_pnl_r": round(avg_pnl_r, 3),
                "kelly_tier": kelly_tier,
                "cash_ratio": cash_ratio,
                "regime_source": regime_source,
            }
        )

    return cards


# === SYSTEM VS ACTUAL ===


def compute_system_edge_vs_actual(
    system_equity_final: float,
    actual_portfolio_value: Optional[float] = None,
) -> Dict[str, Any]:
    """Calcula system edge vs actual portfolio."""
    if actual_portfolio_value is None:
        return {
            "system_value": round(system_equity_final, 2),
            "actual_value": None,
            "system_edge": None,
            "system_return": None,
            "actual_return": None,
            "has_actual": False,
        }

    system_return = 0.0
    actual_return = (
        (actual_portfolio_value - system_equity_final) / system_equity_final
        if system_equity_final > 0
        else 0.0
    )

    return {
        "system_value": round(system_equity_final, 2),
        "actual_value": round(actual_portfolio_value, 2),
        "system_edge": round(actual_return, 4),
        "system_return": round(system_return * 100, 2),
        "actual_return": round(actual_return * 100, 2),
        "has_actual": True,
    }


# === COMPUTE BACKTEST ANALYTICS (MAIN API) ===


def compute_backtest_analytics(
    results: Dict[str, Any],
    trades_df: pd.DataFrame,
    equity_curve: pd.Series,
    start_date: str,
    end_date: str,
    run_id: str,
    initial_capital: float = DEFAULT_CAPITAL,
    risk_per_trade_pct: float = RISK_PER_TRADE_PCT,
    regime_classifier=None,
    actual_portfolio_value: Optional[float] = None,
    engine_name: str = "vectorbt_advanced",
) -> Dict[str, Any]:
    """
    Convierte output del backtest al schema canónico S1 con regime cards.

    Args:
        results: Dict con keys del engine (total_return, sharpe_ratio, etc.)
        trades_df: DataFrame de trades del backtest
        equity_curve: Serie temporal de equity
        start_date, end_date: Período del backtest
        run_id: Identificador único del run
        initial_capital: Capital inicial
        risk_per_trade_pct: % de riesgo por trade
        regime_classifier: Instancia de MarketRegimeClassifier (opcional)
        actual_portfolio_value: Valor real del portfolio si hay (para system edge)
        engine_name: Nombre del engine ("vectorbt_advanced", "daily_engine")

    Returns:
        Dict con schema canónico extendido con regime_cards
    """
    logger.info(f"📊 Computing backtest analytics for run {run_id}...")

    # Convert trades to R-múltiplos
    trades_r = backtest_trades_to_r(
        trades_df,
        initial_capital=initial_capital,
        risk_per_trade_pct=risk_per_trade_pct,
    )

    # Extract metrics from results (engine provides authoritative values)
    total_return = results.get("total_return", 0)
    annualized_return = results.get("annualized_return", results.get("cagr", 0))
    sharpe = results.get("sharpe_ratio", results.get("sharpe", 0))
    max_dd = results.get("max_drawdown", 0)
    calmar = results.get("calmar_ratio", results.get("calmar", 0))
    win_rate = results.get("win_rate", 0)
    profit_factor = results.get("profit_factor", 0)

    # Trade stats
    n_trades = len(trades_r)
    wins = [t for t in trades_r if t.get("pnl", 0) > 0]
    losses = [t for t in trades_r if t.get("pnl", 0) < 0]

    avg_win = sum(t.get("pnl_r", 0) for t in wins) / len(wins) if wins else 0.0
    avg_loss = (
        abs(sum(t.get("pnl_r", 0) for t in losses) / len(losses)) if losses else 0.0
    )
    rr = avg_win / avg_loss if avg_loss > 0 else 0.0

    trade_stats = {
        "trades": n_trades,
        "cagr_pct": round(annualized_return * 100, 2)
        if isinstance(annualized_return, float)
        else 0.0,
        "cagr_source": engine_name,
        "win_rate": round(win_rate, 2),
        "rr": round(rr, 2),
        "avg_win": round(avg_win, 3),
        "avg_loss": round(avg_loss, 3),
        "gross_profit": round(sum(t.get("pnl_r", 0) for t in wins), 3),
        "gross_loss": round(abs(sum(t.get("pnl_r", 0) for t in losses)), 3),
    }

    # Overall quality (reuse S1 functions with R-converted trades)
    from src.analytics.paper_analytics_engine import compute_overall_quality

    oq = compute_overall_quality(trades_r, equity_curve, initial_capital)
    oq["profit_factor"] = round(profit_factor, 2)
    oq["max_drawdown_90d"] = round(max_dd * 100, 2) if max_dd else 0.0
    oq["calmar"] = round(calmar, 2) if calmar else 0.0
    oq["sharpe"] = round(sharpe, 2) if sharpe else 0.0
    oq["cagr_pct"] = (
        round(annualized_return * 100, 2)
        if isinstance(annualized_return, float)
        else None
    )
    oq["cagr_source"] = engine_name

    # Position sizing (from engine results)
    market_score = 50.0  # default for backtest
    kelly_tier, kelly_frac = classify_kelly_tier(market_score, "OK")

    from src.analytics.paper_analytics_engine import compute_position_sizing

    pos_sizing = compute_position_sizing(
        capital=initial_capital,
        kelly_tier=kelly_tier,
        kelly_fraction=kelly_frac,
    )

    # Risk checks (simplified for backtest)
    from src.analytics.paper_analytics_engine import compute_risk_checks

    risk_checks = compute_risk_checks(
        capital=initial_capital,
        equity_series=equity_curve,
        market_score=market_score,
        deployed_pct=pos_sizing["deployed_pct"],
        cash_reserve_usd=pos_sizing["cash_reserve_usd"],
    )

    # Simulation (use equity curve)
    from src.analytics.paper_analytics_engine import run_mc_summary

    simulation = run_mc_summary(
        equity_curve, n_sims=1000, initial_capital=initial_capital
    )
    if equity_curve is not None and len(equity_curve) < 30:
        simulation["confidence_low"] = True
    else:
        simulation["confidence_low"] = False

    # Market info
    regime_bin = classify_regime_bin(market_score)

    # System vs actual
    system_final = (
        equity_curve.iloc[-1]
        if equity_curve is not None and len(equity_curve) > 0
        else initial_capital
    )
    system_edge = compute_system_edge_vs_actual(system_final, actual_portfolio_value)

    # Regime cards
    regime_cards = build_regime_cards(
        trades_r, equity_curve, regime_classifier, initial_capital
    )

    # Quality flags
    quality_flags = []
    if equity_curve is None or len(equity_curve) < 10:
        quality_flags.append("NO_EQUITY_HISTORY")
    if n_trades == 0:
        quality_flags.append("NO_TRADES")
    if actual_portfolio_value is None:
        quality_flags.append("NO_ACTUAL_SNAPSHOT")

    # Check regime cards source
    if any(c.get("regime_source") == "estimated" for c in regime_cards):
        quality_flags.append("REGIME_ESTIMATED")

    # Verify total trades match
    total_in_cards = sum(c["trade_count"] for c in regime_cards)
    if total_in_cards != n_trades:
        quality_flags.append(f"TRADES_MISMATCH_CARDS:{total_in_cards}/{n_trades}")

    # Build final payload
    payload = {
        "meta": {
            "date": end_date,
            "generated_at": datetime.now().isoformat(),
            "version": "1.0",
            "schema_version": "S1+regime_cards",
            "source_engine": engine_name,
            "run_type": "backtest",
            "run_id": run_id,
            "period": {
                "start": start_date,
                "end": end_date,
            },
            "initial_capital": initial_capital,
            "risk_per_trade_pct": risk_per_trade_pct,
            "data_quality_flags": quality_flags,
        },
        "position_sizing": pos_sizing,
        "risk_checks": risk_checks,
        "trade_stats": trade_stats,
        "overall_quality": oq,
        "simulation": simulation,
        "market": {
            "market_score": market_score,
            "regime_bin": regime_bin,
        },
        "system_vs_actual": system_edge,
        "regime_cards": regime_cards,
    }

    logger.info(
        f"  ✅ Backtest analytics computed: {n_trades} trades, WR={win_rate * 100:.1f}%, PF={profit_factor:.2f}"
    )
    logger.info(
        f"  📊 Regime cards: {len(regime_cards)} bins, total_trades={total_in_cards}"
    )

    return payload


# === CLI TEST ===

if __name__ == "__main__":
    print("Testing backtest analytics bridge...")

    # Create dummy data
    n = 50
    equity = pd.Series([100000 * (1 + i * 0.005) for i in range(n)])
    equity.index = pd.date_range("2025-01-01", periods=n, freq="D")

    trades_df = pd.DataFrame(
        {
            "symbol": ["AAPL"] * 10 + ["NVDA"] * 10,
            "entry_date": pd.date_range("2025-01-01", periods=20, freq="D").strftime(
                "%Y-%m-%d"
            ),
            "exit_date": pd.date_range("2025-01-05", periods=20, freq="D").strftime(
                "%Y-%m-%d"
            ),
            "pnl": [100, -50, 200, -30, 150, -20, 80, -40, 120, -60] * 2,
            "return_pct": [1.0, -0.5, 2.0, -0.3, 1.5, -0.2, 0.8, -0.4, 1.2, -0.6] * 2,
        }
    )

    results = {
        "total_return": 0.15,
        "annualized_return": 0.25,
        "sharpe_ratio": 1.8,
        "max_drawdown": 0.08,
        "calmar_ratio": 3.1,
        "win_rate": 55.0,
        "profit_factor": 2.2,
    }

    payload = compute_backtest_analytics(
        results=results,
        trades_df=trades_df,
        equity_curve=equity,
        start_date="2025-01-01",
        end_date="2025-04-09",
        run_id="test_run_001",
        initial_capital=100000,
    )

    print(f"  Trades: {payload['trade_stats']['trades']}")
    print(f"  CAGR: {payload['trade_stats']['cagr_pct']}%")
    print(f"  PF: {payload['overall_quality']['profit_factor']}")
    print(f"  Regime cards: {len(payload['regime_cards'])}")
    for card in payload["regime_cards"]:
        print(
            f"    {card['regime_bin']}: {card['trade_count']} trades, WR={card['win_rate']}%"
        )
