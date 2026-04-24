from datetime import datetime, timezone, timedelta
from typing import Optional

try:
    from zoneinfo import ZoneInfo

    BUENOS_AIRES_TZ = ZoneInfo("America/Buenos_Aires")
except Exception:
    BUENOS_AIRES_TZ = timezone(timedelta(hours=-3))
    import logging

    logging.warning("tzdata not available, using fixed UTC-03:00 fallback")

from src.integration.conflict_policy import (
    resolve_opposite_side,
    resolve_same_side,
)
from src.integration.routed_signal import RoutedSignal
from src.integration.unified_signal import UnifiedSignal


def parse_signal_time(signal_time: str) -> datetime:
    dt = datetime.fromisoformat(signal_time.replace("Z", "+00:00"))
    return dt.astimezone(BUENOS_AIRES_TZ)


def get_trade_date(signal_time: str) -> str:
    dt = parse_signal_time(signal_time)
    return dt.strftime("%Y-%m-%d")


def get_timeframe_bucket(timeframe: str) -> str:
    tf = timeframe.lower()
    if tf == "1d" or tf == "1D":
        return "daily"
    if tf in ("5m", "15m", "30m", "1h", "4h"):
        return "intraday"
    return "swing"


def make_collision_key(signal: UnifiedSignal) -> str:
    trade_date = get_trade_date(signal.signal_time)
    bucket = get_timeframe_bucket(signal.timeframe)
    return f"{signal.ticker}_{trade_date}_{bucket}"


class SignalRouter:
    def __init__(self, cooldown_enabled: bool = True):
        self.cooldown_enabled = cooldown_enabled
        self.cooldown_tickers: set[str] = set()

    def reset_cooldown(self):
        self.cooldown_tickers = set()

    def is_in_cooldown(self, ticker: str) -> bool:
        return self.cooldown_enabled and ticker in self.cooldown_tickers

    def add_cooldown(self, ticker: str):
        if self.cooldown_enabled:
            self.cooldown_tickers.add(ticker)

    def route_signals(
        self, signals: list[UnifiedSignal]
    ) -> tuple[list[RoutedSignal], list[RoutedSignal], list[RoutedSignal]]:
        collision_groups: dict[str, list[UnifiedSignal]] = {}
        for signal in signals:
            key = make_collision_key(signal)
            if key not in collision_groups:
                collision_groups[key] = []
            collision_groups[key].append(signal)

        accepted = []
        dropped = []
        blocked = []

        for key, group in collision_groups.items():
            ticker = group[0].ticker

            if self.is_in_cooldown(ticker):
                for signal in group:
                    routed = RoutedSignal(
                        signal=signal,
                        router_decision="blocked",
                        router_reason="cooldown",
                        collision_key=key,
                    )
                    blocked.append(routed)
                continue

            sides = set(s.side for s in group)
            has_opposite = len(sides) > 1 and ("long" in sides and "short" in sides)

            if has_opposite:
                decisions = resolve_opposite_side(group)
            else:
                decisions = resolve_same_side(group)

            for signal, decision in zip(group, decisions):
                routed = RoutedSignal(
                    signal=signal,
                    router_decision=decision.decision,
                    router_reason=decision.reason,
                    collision_key=key,
                )

                if decision.decision == "accepted":
                    accepted.append(routed)
                elif decision.decision == "dropped":
                    dropped.append(routed)
                else:
                    blocked.append(routed)

                if decision.reason == "opposite_balanced":
                    self.add_cooldown(ticker)

        return accepted, dropped, blocked

    def get_summary(
        self,
        accepted: list[RoutedSignal],
        dropped: list[RoutedSignal],
        blocked: list[RoutedSignal],
    ) -> dict:
        dropped_by_score = sum(
            1 for r in dropped if r.router_reason in ("won_by_score", "tie_stability_A")
        )
        dropped_opposite = sum(
            1 for r in dropped if r.router_reason == "opposite_resolved"
        )
        blocked_opposite = sum(
            1 for r in blocked if r.router_reason == "opposite_balanced"
        )
        blocked_cooldown = sum(1 for r in blocked if r.router_reason == "cooldown")

        return {
            "total_input": len(accepted) + len(dropped) + len(blocked),
            "accepted": len(accepted),
            "dropped": len(dropped),
            "blocked": len(blocked),
            "dropped_by_score": dropped_by_score,
            "dropped_opposite_resolved": dropped_opposite,
            "blocked_opposite_balanced": blocked_opposite,
            "blocked_cooldown": blocked_cooldown,
        }
