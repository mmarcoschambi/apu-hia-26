"""
src/utils/market_context_live.py
================================
Helper para obtener contexto de mercado (SPY/VIX) de forma robusta.
Útil para runbook de paper trading y scanners en tiempo real.

Funcionalidades:
- Limpieza robusta de MultiIndex de yfinance
- Cadena de fallback para VIX: ^VIX -> VIXY -> cache -> PASS_WARNING
- Diagnóstico de calidad del dato (OK | LOW)
- Recomendaciones para decisiones de gate
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import pandas as pd
import yfinance as yf


PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DB_PATH = PROJECT_ROOT / "data" / "ticker_cache.db"


def _extract_close_series(df: pd.DataFrame) -> pd.Series:
    """Extrae serie de Close de DataFrame de yfinance, maneja MultiIndex."""
    if df is None or df.empty:
        return pd.Series(dtype=float)

    if isinstance(df.columns, pd.MultiIndex):
        if "Close" in df.columns.get_level_values(0):
            close_df = df.xs("Close", axis=1, level=0, drop_level=False)
            s = close_df.iloc[:, 0]
        else:
            return pd.Series(dtype=float)
    else:
        if "Close" in df.columns:
            s = df["Close"]
        elif "close" in df.columns:
            s = df["close"]
        else:
            return pd.Series(dtype=float)

    return pd.to_numeric(s, errors="coerce").dropna()


def _fetch_last_close_yf(
    ticker: str, period: str, timeout: int = 10
) -> Tuple[Optional[float], Optional[str]]:
    """Descarga último close desde Yahoo Finance."""
    try:
        df = yf.download(
            ticker, period=period, auto_adjust=True, progress=False, timeout=timeout
        )
        s = _extract_close_series(df)
        if s.empty:
            return None, f"{ticker}: close series empty"
        return float(s.iloc[-1]), None
    except Exception as e:
        return None, f"{ticker}: {e}"


def _fetch_last_close_cache(
    db_path: Path, ticker: str, days: int = 10, as_of: Optional[str | pd.Timestamp] = None
) -> Tuple[Optional[float], Optional[str]]:
    """Descarga último close desde cache local (ticker_cache.db)."""
    if not db_path or not db_path.exists() or db_path.stat().st_size == 0:
        return None, f"{ticker}: cache DB not found or empty at {db_path}"
    try:
        ref_dt = pd.Timestamp(as_of) if as_of else datetime.now()
        cutoff = (ref_dt - timedelta(days=days)).strftime("%Y-%m-%d")
        as_of_str = ref_dt.strftime("%Y-%m-%d")

        conn = sqlite3.connect(str(db_path), timeout=30)
        row = conn.execute(
            "SELECT close FROM ohlcv_cache WHERE ticker=? AND date>=? AND date<=? ORDER BY date DESC LIMIT 1",
            (ticker, cutoff, as_of_str),
        ).fetchone()
        conn.close()
        if not row:
            return None, f"{ticker}: no cache row up to {as_of_str}"
        return float(row[0]), None
    except Exception as e:
        return None, f"{ticker}: cache error {e}"


def _fetch_close_series_cache(
    db_path: Path, ticker: str, days: int = 365
) -> Tuple[pd.Series, Optional[str]]:
    """Descarga serie de close desde cache local."""
    if not db_path or not db_path.exists() or db_path.stat().st_size == 0:
        return pd.Series(dtype=float), f"{ticker}: cache DB not found or empty at {db_path}"
    try:
        conn = sqlite3.connect(str(db_path), timeout=30)
        cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
        rows = conn.execute(
            "SELECT date, close FROM ohlcv_cache WHERE ticker=? AND date>=? ORDER BY date",
            (ticker, cutoff),
        ).fetchall()
        conn.close()
        if not rows:
            return pd.Series(dtype=float), f"{ticker}: no cache rows"
        df = pd.DataFrame(rows, columns=["date", "close"])
        df["date"] = pd.to_datetime(df["date"], errors="coerce")
        df["close"] = pd.to_numeric(df["close"], errors="coerce")
        df = df.dropna(subset=["date", "close"]).drop_duplicates(subset=["date"])
        if df.empty:
            return pd.Series(dtype=float), f"{ticker}: cache series empty"
        series = df.set_index("date")["close"].astype(float).sort_index()
        return series, None
    except Exception as e:
        return pd.Series(dtype=float), f"{ticker}: cache series error {e}"


def get_market_context_live(
    require_spy_above_sma50: bool = False,
    require_spy_above_sma200: bool = False,
    spy_lookback_days: int = 300,
    max_vix: float = 35.0,
    db_path: Optional[Path] = None,
    as_of: Optional[str | pd.Timestamp] = None,
) -> Dict[str, Any]:
    """
    Obtiene contexto de mercado de forma robusta con fallback chain.

    Args:
        require_spy_above_sma50: Si True, SPY debe estar sobre SMA50 para aprobar.
        require_spy_above_sma200: Si True, SPY debe estar sobre SMA200 para aprobar.
        spy_lookback_days: Días de historia a descargar para el SPY.
        max_vix: Umbral máximo de VIX para aprobar.
        db_path: Path al DB de cache (default: PROJECT_ROOT/data/ticker_cache.db)
        as_of: Fecha de referencia para el cálculo (default: hoy).

    Returns:
        Dict con estructura:
        {
            "spy_price": float,
            "spy_sma50": float,
            "spy_sma200": float,
            "spy_ok": bool,
            "vix": float,
            "vix_ok": bool,
            "vix_source": str,  # "^VIX", "VIXY_PROXY", "CACHE:^VIX", "PASS_WARNING"
            "regime_quality": "OK" | "LOW",
            "warnings": [str],
        }
    """
    if db_path is None:
        db_path = DB_PATH

    ctx: Dict[str, Any] = {
        "spy_price": None,
        "spy_sma50": None,
        "spy_sma200": None,
        "spy_ok": True,
        "vix": None,
        "vix_ok": True,
        "vix_source": None,
        "regime_quality": "OK",
        "warnings": [],
    }

    # === SPY robusto ===
    try:
        download_kwargs = {
            "period": f"{spy_lookback_days}d",
            "auto_adjust": True,
            "progress": False,
            "timeout": 10,
        }
        if as_of:
            as_of_ts = pd.Timestamp(as_of)
            end_dt = (as_of_ts + timedelta(days=1)).strftime("%Y-%m-%d")
            start_dt = (as_of_ts - timedelta(days=int(spy_lookback_days * 1.5))).strftime(
                "%Y-%m-%d"
            )
            download_kwargs = {
                "start": start_dt,
                "end": end_dt,
                "auto_adjust": True,
                "progress": False,
                "timeout": 10,
            }

        spy_df = yf.download("SPY", **download_kwargs)
        spy_s = _extract_close_series(spy_df)
        if as_of:
            spy_s = spy_s[spy_s.index <= pd.Timestamp(as_of)]

        if not spy_s.empty:
            spy_price = float(spy_s.iloc[-1])
            ctx["spy_price"] = spy_price
            spy_ok = True

            # SMA 50
            if len(spy_s) >= 50:
                spy_sma50_val = float(spy_s.rolling(50).mean().dropna().iloc[-1])
                ctx["spy_sma50"] = spy_sma50_val
                if require_spy_above_sma50:
                    spy_ok = spy_ok and (spy_price >= spy_sma50_val)
            elif require_spy_above_sma50:
                spy_ok = False
                ctx["regime_quality"] = "LOW"
                ctx["warnings"].append("SPY insufficient data for SMA50")

            # SMA 200
            if len(spy_s) >= 200:
                spy_sma200_val = float(spy_s.rolling(200).mean().dropna().iloc[-1])
                ctx["spy_sma200"] = spy_sma200_val
                if require_spy_above_sma200:
                    spy_ok = spy_ok and (spy_price >= spy_sma200_val)
            elif require_spy_above_sma200:
                spy_ok = False
                ctx["regime_quality"] = "LOW"
                ctx["warnings"].append("SPY insufficient data for SMA200")

            ctx["spy_ok"] = spy_ok
        else:
            ctx["spy_ok"] = not (require_spy_above_sma50 or require_spy_above_sma200)
            ctx["regime_quality"] = "LOW"
            ctx["warnings"].append("SPY series empty; gate degraded")

    except Exception as e:
        ctx["spy_ok"] = not (require_spy_above_sma50 or require_spy_above_sma200)
        ctx["regime_quality"] = "LOW"
        ctx["warnings"].append(f"SPY fetch failed: {e}; gate degraded")

    if ctx["spy_price"] is None:
        spy_s, err = _fetch_close_series_cache(
            db_path, "SPY", days=max(spy_lookback_days + 30, 365)
        )
        if as_of:
            spy_s = spy_s[spy_s.index <= pd.Timestamp(as_of)]

        if not spy_s.empty:
            spy_price = float(spy_s.iloc[-1])
            ctx["spy_price"] = spy_price
            spy_ok = True

            if len(spy_s) >= 50:
                spy_sma50_val = float(spy_s.rolling(50).mean().dropna().iloc[-1])
                ctx["spy_sma50"] = spy_sma50_val
                if require_spy_above_sma50:
                    spy_ok = spy_ok and (spy_price >= spy_sma50_val)
            elif require_spy_above_sma50:
                spy_ok = False
                ctx["warnings"].append("SPY cache insufficient data for SMA50")

            if len(spy_s) >= 200:
                spy_sma200_val = float(spy_s.rolling(200).mean().dropna().iloc[-1])
                ctx["spy_sma200"] = spy_sma200_val
                if require_spy_above_sma200:
                    spy_ok = spy_ok and (spy_price >= spy_sma200_val)
            elif require_spy_above_sma200:
                spy_ok = False
                ctx["warnings"].append("SPY cache insufficient data for SMA200")

            ctx["spy_ok"] = spy_ok
            ctx["regime_quality"] = "LOW"
            ctx["warnings"].append("Using cached SPY series for regime check")
        elif err:
            ctx["warnings"].append(err)

    # === VIX chain ===
    vix_kwargs = {"period": "10d", "auto_adjust": True, "progress": False, "timeout": 10}
    if as_of:
        as_of_ts = pd.Timestamp(as_of)
        vix_kwargs = {
            "start": (as_of_ts - timedelta(days=10)).strftime("%Y-%m-%d"),
            "end": (as_of_ts + timedelta(days=1)).strftime("%Y-%m-%d"),
            "auto_adjust": True,
            "progress": False,
            "timeout": 10,
        }

    def _fetch_vix_logic(ticker: str) -> Tuple[Optional[float], Optional[str]]:
        try:
            df = yf.download(ticker, **vix_kwargs)
            s = _extract_close_series(df)
            if as_of:
                s = s[s.index <= pd.Timestamp(as_of)]
            if s.empty:
                return None, f"{ticker}: series empty"
            return float(s.iloc[-1]), None
        except Exception as e:
            return None, f"{ticker}: {e}"

    vix_val, err = _fetch_vix_logic("^VIX")
    if vix_val is not None:
        ctx["vix"] = vix_val
        ctx["vix_ok"] = vix_val < max_vix
        ctx["vix_source"] = "^VIX"
        return ctx

    if err:
        ctx["warnings"].append(err)

    proxy_val, err = _fetch_vix_logic("VIXY")
    if proxy_val is not None:
        ctx["vix"] = proxy_val
        ctx["vix_ok"] = True
        ctx["vix_source"] = "VIXY_PROXY"
        ctx["regime_quality"] = "LOW"
        ctx["warnings"].append("Using VIXY proxy; VIX gate set to warning mode")
        return ctx

    if err:
        ctx["warnings"].append(err)

    for ticker in ("^VIX", "VIXY"):
        cached, err = _fetch_last_close_cache(db_path, ticker, days=14, as_of=as_of)
        if cached is not None:
            ctx["vix"] = cached
            ctx["vix_ok"] = True
            ctx["vix_source"] = f"CACHE:{ticker}"
            ctx["regime_quality"] = "LOW"
            ctx["warnings"].append(
                f"Using cached {ticker}; VIX gate set to warning mode"
            )
            return ctx
        if err:
            ctx["warnings"].append(err)

    # Fallback final: VIX no disponible
    ctx["vix_ok"] = True
    ctx["vix_source"] = "PASS_WARNING"
    ctx["regime_quality"] = "LOW"
    ctx["warnings"].append("VIX unavailable from all sources; PASS_WARNING applied")

    return ctx


def apply_regime_override(
    ctx: Dict[str, Any],
    mode: str,
) -> Dict[str, Any]:
    """
    Aplica override al régimen calculado.

    Args:
        ctx: Output de get_market_context_live()
        mode: "none" | "spy" | "vix" | "all"

    Returns:
        Dict con raw vs effective y metadata del override
    """
    raw_spy_ok = bool(ctx.get("spy_ok", True))
    raw_vix_ok = bool(ctx.get("vix_ok", True))

    eff_spy_ok = raw_spy_ok
    eff_vix_ok = raw_vix_ok
    applied = False

    if mode == "spy":
        eff_spy_ok = True
        applied = not raw_spy_ok
    elif mode == "vix":
        eff_vix_ok = True
        applied = not raw_vix_ok
    elif mode == "all":
        eff_spy_ok = True
        eff_vix_ok = True
        applied = not (raw_spy_ok and raw_vix_ok)
    # mode == "none": no change

    return {
        "raw_spy_ok": raw_spy_ok,
        "raw_vix_ok": raw_vix_ok,
        "effective_spy_ok": eff_spy_ok,
        "effective_vix_ok": eff_vix_ok,
        "raw_regime_ok": raw_spy_ok and raw_vix_ok,
        "effective_regime_ok": eff_spy_ok and eff_vix_ok,
        "override_mode": mode,
        "override_applied": applied,
    }


def _to_bool(v: Any) -> bool:
    """Convierte valor a booleano (maneja strings 'True'/'False')."""
    if isinstance(v, bool):
        return v
    if isinstance(v, str):
        return v.strip().lower() in {"true", "1", "yes", "y"}
    return False
