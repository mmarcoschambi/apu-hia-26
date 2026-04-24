import math
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class EdgeMetrics:
    source_system: str
    strategy_id: str
    trades: int = 0
    wins: int = 0
    losses: int = 0
    win_rate: float = 0.0
    avg_win: float = 0.0
    avg_loss: float = 0.0
    expectancy: float = 0.0
    profit_factor: float = 0.0
    payoff_ratio: float = 0.0
    max_drawdown: float = 0.0
    sharpe: float = 0.0
    expectancy_per_100usd: float = 0.0
    metadata: dict = field(default_factory=dict)


@dataclass
class PreflightResult:
    passed: bool
    hydrated_rate_A: float = 0.0
    hydrated_rate_B: float = 0.0
    common_date_start: Optional[str] = None
    common_date_end: Optional[str] = None
    common_sessions: int = 0
    errors: list = field(default_factory=list)


def _to_float(val, default=0.0) -> float:
    if val is None:
        return default
    try:
        return float(val)
    except (ValueError, TypeError):
        return default


def compute_metrics_from_trades(trades: list[dict]) -> EdgeMetrics:
    if not trades:
        return EdgeMetrics(source_system="", strategy_id="")

    wins = [t for t in trades if _to_float(t.get("r_multiple")) > 0]
    losses = [t for t in trades if _to_float(t.get("r_multiple")) < 0]

    n = len(trades)
    n_wins = len(wins)
    n_losses = len(losses)

    win_rate = n_wins / n if n > 0 else 0.0

    avg_win = (
        sum(_to_float(t.get("r_multiple")) for t in wins) / n_wins
        if n_wins > 0
        else 0.0
    )
    avg_loss = (
        sum(_to_float(t.get("r_multiple")) for t in losses) / n_losses
        if n_losses > 0
        else 0.0
    )

    expectancy = (win_rate * avg_win) + ((1 - win_rate) * avg_loss)

    total_wins = sum(_to_float(t.get("r_multiple")) for t in wins)
    total_losses = abs(sum(_to_float(t.get("r_multiple")) for t in losses))
    profit_factor = total_wins / total_losses if total_losses > 0 else 0.0

    payoff_ratio = abs(avg_win / avg_loss) if avg_loss != 0 else 0.0

    equity = [0.0]
    for t in trades:
        equity.append(equity[-1] + _to_float(t.get("r_multiple")))
    peak = 0.0
    max_dd = 0.0
    for e in equity:
        if e > peak:
            peak = e
        dd = peak - e
        if dd > max_dd:
            max_dd = dd

    returns = [_to_float(t.get("r_multiple")) for t in trades]
    sharpe = 0.0
    if len(returns) > 1:
        mean_r = sum(returns) / len(returns)
        std_r = math.sqrt(sum((r - mean_r) ** 2 for r in returns) / len(returns))
        sharpe = mean_r / std_r if std_r > 0 else 0.0

    expectancy_per_100 = expectancy * 100.0

    return EdgeMetrics(
        source_system=trades[0].get("source_system", ""),
        strategy_id=trades[0].get("strategy_id", ""),
        trades=n,
        wins=n_wins,
        losses=n_losses,
        win_rate=win_rate,
        avg_win=avg_win,
        avg_loss=avg_loss,
        expectancy=expectancy,
        profit_factor=profit_factor,
        payoff_ratio=payoff_ratio,
        max_drawdown=max_dd,
        sharpe=sharpe,
        expectancy_per_100usd=expectancy_per_100,
    )


def compute_rolling_metrics(trades: list[dict], window: int) -> list[EdgeMetrics]:
    if len(trades) < window:
        return []
    result = []
    for i in range(len(trades) - window + 1):
        window_trades = trades[i : i + window]
        metrics = compute_metrics_from_trades(window_trades)
        if metrics.strategy_id:
            result.append(metrics)
    return result


def _is_price_source_valid(plan: dict) -> bool:
    """Evalua si la fuente de precio hidratado es aceptable para F4.

    Reglas:
    1. 'close_signal_date' es siempre valida (hidratacion real de mercado).
    2. 'input' es valida SOLO si:
       - source_system == 'B'
       - metadata.historical_plan == True
       - metadata.price_origin == 'trades_csv'
    """
    metadata = plan.get("metadata", {})
    source = plan.get("hydrated_price_source") or metadata.get("hydrated_price_source")
    if source == "close_signal_date":
        return True

    # En datasets historicos pre-F3 (F1/F2), el precio puede venir ya
    # cargado en entry_price_ref sin hydrated_price_source explicito.
    if (
        plan.get("source_system") == "B"
        and metadata.get("historical_plan") is True
        and metadata.get("price_origin") == "trades_csv"
    ):
        if source == "input":
            return True
        if _to_float(plan.get("entry_price_ref")) > 0:
            return True

    return False


def _extract_plan_date(plan: dict) -> Optional[str]:
    """Obtiene la fecha operativa desde distintos shapes de F1/F2/F3."""
    trade_date = plan.get("trade_date")
    if trade_date:
        return str(trade_date)

    signal_time = plan.get("signal_time")
    if signal_time:
        text = str(signal_time)
        try:
            return datetime.fromisoformat(text.replace("Z", "+00:00")).strftime("%Y-%m-%d")
        except ValueError:
            return text.split("T")[0]

    collision_key = plan.get("collision_key")
    if collision_key and "_" in str(collision_key):
        parts = str(collision_key).split("_")
        if len(parts) >= 3:
            return parts[1]

    return None


def compute_preflight(
    execution_plan: list[dict],
) -> PreflightResult:
    errors = []

    a_plans = [p for p in execution_plan if p.get("source_system") == "A"]
    b_plans = [p for p in execution_plan if p.get("source_system") == "B"]

    total_a = len(a_plans)
    total_b = len(b_plans)

    # Reemplazamos regla rigida por funcion de elegibilidad
    hydrated_a = [p for p in a_plans if _is_price_source_valid(p)]
    hydrated_b = [p for p in b_plans if _is_price_source_valid(p)]

    rate_a = len(hydrated_a) / total_a if total_a > 0 else 1.0
    rate_b = len(hydrated_b) / total_b if total_b > 0 else 0.0

    if rate_b < 0.80:
        errors.append(f"hydrated_rate_B={rate_b:.2%} < 80% threshold")

    all_dates_a = sorted(set(_extract_plan_date(p) for p in a_plans if _extract_plan_date(p)))
    all_dates_b = sorted(set(_extract_plan_date(p) for p in b_plans if _extract_plan_date(p)))

    common_start = None
    common_end = None
    common_sessions = 0
    if all_dates_a and all_dates_b:
        overlap_start = max(all_dates_a[0], all_dates_b[0])
        overlap_end = min(all_dates_a[-1], all_dates_b[-1])
        if overlap_end >= overlap_start:
            common_start = overlap_start
            common_end = overlap_end
            common_sessions = len(
                [d for d in all_dates_a if overlap_start <= d <= overlap_end]
            )

    if common_sessions < 60:
        errors.append(f"common_sessions={common_sessions} < 60 minimum")

    return PreflightResult(
        passed=len(errors) == 0,
        hydrated_rate_A=rate_a,
        hydrated_rate_B=rate_b,
        common_date_start=common_start,
        common_date_end=common_end,
        common_sessions=common_sessions,
        errors=errors,
    )
