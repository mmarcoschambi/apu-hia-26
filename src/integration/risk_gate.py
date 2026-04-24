import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from src.integration.execution_plan import ExecutionPlanRow
from src.integration.routed_signal import RoutedSignal


@dataclass
class RiskGateConfig:
    capital_total_usd: float = 100000.0
    risk_per_trade_usd: float = 1000.0
    budget_split: dict[str, float] = field(default_factory=lambda: {"A": 0.7, "B": 0.3})
    max_exposure_total_pct: float = 0.65
    max_exposure_per_ticker_pct: float = 0.12
    max_positions_total: int = 8
    max_positions_per_source: dict[str, int] = field(
        default_factory=lambda: {"A": 6, "B": 4}
    )
    default_stop_pct: float = 0.05
    min_shares: int = 1
    min_price: float = 1.0


def load_config(config_path: Path) -> RiskGateConfig:
    with open(config_path, "r") as f:
        data = json.load(f)
    return RiskGateConfig(
        capital_total_usd=data.get("capital_total_usd", 100000.0),
        risk_per_trade_usd=data.get("risk_per_trade_usd", 1000.0),
        budget_split=data.get("budget_split", {"A": 0.7, "B": 0.3}),
        max_exposure_total_pct=data.get("max_exposure_total_pct", 0.65),
        max_exposure_per_ticker_pct=data.get("max_exposure_per_ticker_pct", 0.12),
        max_positions_total=data.get("max_positions_total", 8),
        max_positions_per_source=data.get("max_positions_per_source", {"A": 6, "B": 4}),
        default_stop_pct=data.get("default_stop_pct", 0.05),
        min_shares=data.get("min_shares", 1),
        min_price=data.get("min_price", 1.0),
    )


def apply_risk_gate(
    signals: list[RoutedSignal],
    config: RiskGateConfig,
) -> tuple[list[ExecutionPlanRow], list[dict]]:
    sorted_signals = sorted(
        signals,
        key=lambda s: s.normalized_score,
        reverse=True,
    )

    budget_used = {"A": 0.0, "B": 0.0}
    positions_by_source = {"A": 0, "B": 0}
    exposure_by_ticker: dict[str, float] = {}
    total_exposure = 0.0

    planned = []
    rejected = []

    for routed in sorted_signals:
        signal = routed.signal
        source = signal.source_system

        if positions_by_source[source] >= config.max_positions_per_source[source]:
            rejected.append(
                {
                    "signal": routed,
                    "reason": "max_positions_per_source",
                    "source": source,
                    "current": positions_by_source[source],
                }
            )
            continue

        if total_exposure >= config.capital_total_usd * config.max_exposure_total_pct:
            rejected.append(
                {
                    "signal": routed,
                    "reason": "max_exposure_total",
                    "exposure": total_exposure,
                }
            )
            continue

        ticker_exposure = exposure_by_ticker.get(signal.ticker, 0.0)
        if (
            ticker_exposure
            >= config.capital_total_usd * config.max_exposure_per_ticker_pct
        ):
            rejected.append(
                {
                    "signal": routed,
                    "reason": "max_exposure_per_ticker",
                    "ticker": signal.ticker,
                    "exposure": ticker_exposure,
                }
            )
            continue

        budget_source = config.budget_split.get(source, 0.7 if source == "A" else 0.3)
        budget_limit = config.capital_total_usd * budget_source
        if budget_used[source] >= budget_limit:
            rejected.append(
                {
                    "signal": routed,
                    "reason": "budget_exhausted",
                    "source": source,
                }
            )
            continue

        entry_price = signal.entry_price_ref
        if entry_price <= 0 or entry_price < config.min_price:
            rejected.append(
                {
                    "signal": routed,
                    "reason": "invalid_entry_price",
                    "price": entry_price,
                }
            )
            continue

        stop_price = signal.stop_price
        if stop_price and stop_price > 0:
            per_share_risk = abs(entry_price - stop_price)
        else:
            per_share_risk = entry_price * config.default_stop_pct

        if per_share_risk <= 0:
            rejected.append(
                {
                    "signal": routed,
                    "reason": "invalid_stop",
                }
            )
            continue

        shares = int(config.risk_per_trade_usd / per_share_risk)
        if shares < config.min_shares:
            rejected.append(
                {
                    "signal": routed,
                    "reason": "min_shares",
                    "shares": shares,
                }
            )
            continue

        notional = shares * entry_price

        trade_date = (
            routed.collision_key.split("_")[1]
            if "_" in routed.collision_key
            else "unknown"
        )

        plan_row = ExecutionPlanRow(
            source_system=source,
            strategy_id=signal.strategy_id,
            ticker=signal.ticker,
            trade_date=trade_date,
            side=signal.side,
            entry_type=signal.entry_type,
            entry_price_ref=entry_price,
            hydrated_price_source=signal.metadata.get("hydrated_price_source", "input"),
            stop_price=stop_price,
            target_price=signal.target_price,
            risk_budget_usd=budget_limit,
            risk_per_trade_usd=config.risk_per_trade_usd,
            per_share_risk=per_share_risk,
            shares=shares,
            notional_usd=notional,
            router_reason=routed.router_reason,
            collision_key=routed.collision_key,
            metadata=signal.metadata,
        )

        planned.append(plan_row)
        budget_used[source] += config.risk_per_trade_usd
        positions_by_source[source] += 1
        total_exposure += notional
        exposure_by_ticker[signal.ticker] = ticker_exposure + notional

    return planned, rejected
