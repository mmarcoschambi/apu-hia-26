"""
src/screeners/pipeline.py
ScreenerPipeline para combinar múltiples screeners.
"""
from typing import List, Optional

import pandas as pd

from .base import BaseScreener, ScreenerResult


class ScreenerPipeline:
    """
    Combina múltiples screeners en secuencia o paralelo.

    Modos:
        'all'        – Debe pasar TODOS los screeners.
        'any'        – Debe pasar AL MENOS UNO.
        'sequential' – Pipeline en orden; se detiene al primer fallo.
    """

    def __init__(self, screeners: List[BaseScreener], mode: str = "all"):
        if mode not in ("all", "any", "sequential"):
            raise ValueError(f"mode debe ser 'all', 'any' o 'sequential', no '{mode}'")
        self.screeners = screeners
        self.mode = mode

    @property
    def name(self) -> str:
        names = "+".join(s.name for s in self.screeners)
        return f"pipeline_{self.mode}[{names}]"

    def scan(
        self,
        ticker: str,
        df: pd.DataFrame,
        spy_df: Optional[pd.DataFrame] = None,
    ) -> ScreenerResult:
        results: List[ScreenerResult] = []

        for screener in self.screeners:
            result = screener.scan(ticker, df, spy_df)
            results.append(result)

            if self.mode == "sequential" and not result.passed:
                return ScreenerResult(
                    passed=False,
                    ticker=ticker,
                    screener_name=self.name,
                    score=0.0,
                    reason=f"Falló en {screener.name}: {result.reason}",
                    metrics={"failed_at": screener.name, "individual": [r.__dict__ for r in results]},
                )

        if not results:
            return ScreenerResult(passed=False, ticker=ticker, screener_name=self.name,
                                  reason="Pipeline vacío")

        if self.mode == "all":
            passed = all(r.passed for r in results)
        elif self.mode == "any":
            passed = any(r.passed for r in results)
        else:  # sequential completó sin fallos
            passed = results[-1].passed

        avg_score = sum(r.score for r in results) / len(results)
        reasons = [f"{r.screener_name}={'PASS' if r.passed else 'FAIL'}" for r in results]

        return ScreenerResult(
            passed=passed,
            ticker=ticker,
            screener_name=self.name,
            score=avg_score,
            reason=" | ".join(reasons),
            metrics={"individual": [r.__dict__ for r in results]},
        )

    def __repr__(self):
        return f"ScreenerPipeline(mode={self.mode!r}, screeners={[s.name for s in self.screeners]})"
