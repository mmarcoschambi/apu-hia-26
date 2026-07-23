"""
src/screeners/htf_candidate.py
High Tight Flag (HTF) — Filtro de Prioridad para el Scanner Live.

NO es una senal de entrada ciega. Es un multiplicador de conviccion:
si un breakout de 20d ademas califica como htf_candidate=True,
ese trade tiene prioridad maxima en el ranking diario.

Criterios (Qullamaggie / Minervini calibrados para S&P 500):
  POLO  : retorno >= pole_ret_pct en los ultimos pole_days dias
  CALIDAD: trend_intensity (MA13/MA65 * 100) >= min_trend_intensity
            excluye recuperaciones de value (CCL, BMY-style)
  FLAG  : precio <= flag_corr_max% por debajo del maximo reciente (bo_days)
           medido sobre close del dia ANTERIOR (evita falso-negativo en dia de BO)
  SCORE : 0-100 basado en fuerza del polo + compresion de la flag
"""

from typing import Optional
import pandas as pd
import numpy as np
import logging

from .base import BaseScreener, ScreenerConfig, ScreenerResult
from .registry import ScreenerRegistry

logger = logging.getLogger(__name__)


@ScreenerRegistry.register
class HTFCandidateScreener(BaseScreener):
    @property
    def name(self) -> str:
        return "htf_candidate"

    @property
    def description(self) -> str:
        return "High Tight Flag — prioridad en ranking live (polo 120d/50% + flag <12%)"

    @property
    def compatible_patterns(self):
        # Compatible con cualquier senal de entrada; es un filtro de prioridad
        return ["breakout", "vcp", "pocket_pivot", "flat_base"]

    def get_default_config(self) -> ScreenerConfig:
        return ScreenerConfig(
            name=self.name,
            min_price=5.0,
            max_price=2000.0,
            min_avg_volume=50_000,        # relajado: la flag baja vol por diseno
            min_dollar_volume=5_000_000,  # relajado: misma razon
            min_adr_pct=0.5,
            params={
                # POLO
                "pole_ret_pct": 0.50,     # retorno minimo del asta (50%)
                "pole_days": 120,         # ventana del asta en dias de trading
                # CALIDAD DEL POLO
                "min_trend_intensity": 108.0,  # MA13/MA65*100 — excluye value traps
                # FLAG
                "flag_corr_max": 0.12,    # correccion maxima desde el maximo (12%)
                "flag_days": 20,          # ventana para medir el maximo de la flag
                # SCORE WEIGHTS
                "pole_weight": 0.6,
                "flag_weight": 0.4,
            },
        )

    def scan(
        self,
        ticker: str,
        df: pd.DataFrame,
        spy_df: Optional[pd.DataFrame] = None,
        scan_date: Optional[str] = None,
    ) -> ScreenerResult:

        # --- Filtros base minimos (relajados vs otros screeners) ---
        passed, reason = self.apply_base_filters(df)
        if not passed:
            return ScreenerResult(False, ticker, self.name, reason=reason)

        min_rows = max(self.config.params["pole_days"] + 20, 150)
        if len(df) < min_rows:
            return ScreenerResult(
                False, ticker, self.name,
                reason=f"Historia insuficiente ({len(df)} < {min_rows} filas)"
            )

        p = self.config.params
        c_col = "close" if "close" in df.columns else "Close"
        h_col = "high"  if "high"  in df.columns else "High"

        close = df[c_col]
        high  = df[h_col]
        price = float(close.iloc[-1])

        # -- 1. POLO ----------------------------------------------------------
        pole_days = int(p["pole_days"])
        flag_days = int(p["flag_days"])  # definido aqui para usar en search_window
        if len(close) < pole_days + 1:
            return ScreenerResult(False, ticker, self.name, reason="Sin datos suficientes para polo")

        # Retorno del polo: min -> max dentro de los ultimos pole_days*2 dias
        # Usamos una ventana amplia (2x pole_days) porque:
        #   - La flag puede durar 20-90 dias adicionales al polo
        #   - El parametro flag_days=20 es la ventana del BREAKOUT, no la flag real
        # Logica: en los ultimos 2*pole_days dias, buscamos el movimiento
        # min->max mas representativo del HTF. Si el stock hizo +50% en
        # alguna sub-ventana de ese periodo, el polo esta presente.
        search_bars = pole_days * 2
        pole_window = close.iloc[-(search_bars + 1):]
        if len(pole_window) < pole_days:
            return ScreenerResult(False, ticker, self.name, reason="Ventana polo vacia")
        # Calcular el retorno max dentro de cualquier ventana de pole_days dias
        # usando rolling: para cada dia t, ret = close[t] / min(close[t-pole_days:t])
        rolling_min = pole_window.rolling(pole_days).min()
        rolling_ret = (pole_window / rolling_min - 1).fillna(0)
        pole_ret = float(rolling_ret.max())
        pole_ok  = pole_ret >= p["pole_ret_pct"]

        # -- 2. CALIDAD DEL POLO (Trend Intensity) ----------------------------
        ma13 = float(close.rolling(13).mean().iloc[-1])
        ma65 = float(close.rolling(65).mean().iloc[-1])
        trend_intensity = (ma13 / ma65 * 100) if ma65 > 0 else 0.0
        ti_ok = trend_intensity >= p["min_trend_intensity"]

        # -- 3. FLAG: correccion medida sobre close del dia ANTERIOR ----------
        # Usando close[-2] (ayer) para que el dia de breakout no produzca
        # correction negativa y bloquee la senal.
        flag_window = high.iloc[-(flag_days + 1):-1]  # excluye hoy
        if len(flag_window) == 0:
            return ScreenerResult(False, ticker, self.name, reason="Ventana de flag vacia")

        flag_high   = float(flag_window.max())
        close_prev  = float(close.iloc[-2]) if len(close) >= 2 else price
        correction  = (flag_high - close_prev) / flag_high if flag_high > 0 else 1.0
        flag_ok     = (0.0 <= correction < p["flag_corr_max"])

        # -- 4. STAGE 2: MA Stack minimo (SMA50 > SMA200) ---------------------
        sma50  = float(self.ensure_ma(df, 50).iloc[-1])
        sma200 = float(self.ensure_ma(df, 200).iloc[-1])
        stage2_ok = (price > sma50 > sma200)

        # -- Criterios y resultado --------------------------------------------
        criteria = {
            "polo_50pct_120d":      pole_ok,
            "trend_intensity_108":  ti_ok,
            "flag_tight_12pct":     flag_ok,
            "stage2_ma_stack":      stage2_ok,
        }
        all_pass = all(criteria.values())

        # Score 0-100
        # Polo: exceso sobre el umbral (max extra 50pp -> 60 puntos)
        pole_score  = min(1.0, (pole_ret - p["pole_ret_pct"]) / 0.50) * 60
        # Flag: cuanto mas ajustada, mejor (0% corr -> 40 pts; 12% -> 0 pts)
        flag_score  = max(0.0, 1.0 - correction / p["flag_corr_max"]) * 40
        score = round(pole_score + flag_score, 1) if all_pass else 0.0
        score = max(0.0, min(100.0, score))

        failed = [k for k, v in criteria.items() if not v]
        reason = (
            f"HTF candidate — polo={pole_ret:.0%}/{pole_days}d "
            f"TI={trend_intensity:.0f} corr={correction:.1%}"
            if all_pass
            else f"Falló: {', '.join(failed)} "
               f"(polo={pole_ret:.0%} TI={trend_intensity:.0f} corr={correction:.1%})"
        )

        return ScreenerResult(
            passed=all_pass,
            ticker=ticker,
            screener_name=self.name,
            score=score,
            metrics={
                "criteria":         criteria,
                "pole_ret":         round(pole_ret, 4),
                "pole_days":        pole_days,
                "trend_intensity":  round(trend_intensity, 1),
                "correction":       round(correction, 4),
                "flag_high":        round(flag_high, 2),
                "close_prev":       round(close_prev, 2),
                "price":            round(price, 2),
                "sma50":            round(sma50, 2),
                "sma200":           round(sma200, 2),
            },
            reason=reason,
        )
