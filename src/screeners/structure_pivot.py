"""
src/screeners/structure_pivot.py
Screener de estructura de pivotes LL->HL / HH->LH.
"""

from typing import Optional

import pandas as pd

from src.indicators.structure_pivot import scan_structures

from .base import BaseScreener, ScreenerConfig, ScreenerResult
from .registry import ScreenerRegistry


@ScreenerRegistry.register
class StructurePivotScreener(BaseScreener):
    @property
    def name(self) -> str:
        return "structure_pivot"

    @property
    def description(self) -> str:
        return "Swing structure pivots (LL->HL / HH->LH) with confirmed-pivot breakout line"

    @property
    def compatible_patterns(self):
        return ["any", "breakout", "vcp", "pocket_pivot"]

    def get_default_config(self) -> ScreenerConfig:
        return ScreenerConfig(
            name=self.name,
            min_price=5.0,
            max_price=1000.0,
            min_avg_volume=100_000,
            min_dollar_volume=10_000_000,
            min_adr_pct=1.0,
            max_adr_pct=20.0,
            params={
                "min_len": 2,
                "max_len": 10,
                "priority_mode": "tightest",  # tightest|longest|shortest
                "direction": "long",  # long|short|both
                "max_distance_pct": 2.0,  # distancia max a break line para considerar setup cercano
            },
        )

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
        min_len = int(p.get("min_len", 2))
        max_len = int(p.get("max_len", 10))
        required_bars = max(2 * max_len + 1, 60)
        if len(df) < required_bars:
            return ScreenerResult(
                False,
                ticker,
                self.name,
                reason=f"Historia insuficiente ({len(df)} < {required_bars})",
            )

        winners = scan_structures(
            df=df,
            min_len=min_len,
            max_len=max_len,
            priority_mode=str(p.get("priority_mode", "tightest")),
        )
        long_w = winners["long"]
        short_w = winners["short"]

        direction = str(p.get("direction", "long")).lower()
        max_dist = float(p.get("max_distance_pct", 2.0))

        long_ok = bool(
            long_w
            and long_w.distance_to_break_pct is not None
            and 0.0 <= long_w.distance_to_break_pct <= max_dist
        )
        short_ok = bool(
            short_w
            and short_w.distance_to_break_pct is not None
            and 0.0 <= short_w.distance_to_break_pct <= max_dist
        )

        if direction == "long":
            selected_ok = long_ok
        elif direction == "short":
            selected_ok = short_ok
        else:
            selected_ok = long_ok or short_ok

        score = 0.0
        if selected_ok:
            distances = []
            if long_ok and long_w and long_w.distance_to_break_pct is not None:
                distances.append(long_w.distance_to_break_pct)
            if short_ok and short_w and short_w.distance_to_break_pct is not None:
                distances.append(short_w.distance_to_break_pct)
            if distances:
                best_dist = min(distances)
                score = round(max(0.0, 100.0 * (1.0 - (best_dist / max_dist))), 1)

        if selected_ok:
            reason = "Structure Pivot setup activo cerca de ruptura"
        else:
            reason = "Sin setup Structure Pivot activo dentro de distancia configurada"

        return ScreenerResult(
            passed=selected_ok,
            ticker=ticker,
            screener_name=self.name,
            score=score,
            metrics={
                "direction": direction,
                "min_len": min_len,
                "max_len": max_len,
                "priority_mode": p.get("priority_mode", "tightest"),
                "max_distance_pct": max_dist,
                "long_setup": bool(long_w),
                "long_break_val": long_w.break_val if long_w else None,
                "long_curr_pivot": long_w.curr_p if long_w else None,
                "long_length": long_w.length if long_w else None,
                "long_distance_pct": long_w.distance_to_break_pct if long_w else None,
                "short_setup": bool(short_w),
                "short_break_val": short_w.break_val if short_w else None,
                "short_curr_pivot": short_w.curr_p if short_w else None,
                "short_length": short_w.length if short_w else None,
                "short_distance_pct": short_w.distance_to_break_pct if short_w else None,
            },
            reason=reason,
        )
