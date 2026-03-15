import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import plotly.io as pio

# Set global plotly theme
pio.templates.default = "plotly_dark"
from datetime import datetime, timedelta
import json
import os
import subprocess
import time
import sys
from pathlib import Path
import calendar
import plotly.figure_factory as ff
import random
import pickle
import shutil
import quantstats as qs
import matplotlib.pyplot as plt

# Fix for Linux font issues in QuantStats/Matplotlib
try:
    plt.rcParams["font.family"] = "sans-serif"
    plt.rcParams["font.sans-serif"] = [
        "DejaVu Sans",
        "Liberation Sans",
        "Bitstream Vera Sans",
        "Arial",
    ]
except Exception:
    pass

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from src.backtest.dashboard import InteractiveDashboard
from src.backtest.visualizer import BacktestVisualizer
from src.data.openbb_data import OpenBBData
from src.data.ticker_cache import TickerCache
from config.universe_presets import LIQUID_MID_CAPS
from src.analytics.quantstats_analyzer import QuantStatsAnalyzer, TradeGrouper
from src.config.dynamic_config import (
    load_production_config,
    flatten_config,
    get_engine_params,
)
from config.defaults import (
    get_tier1_defaults,
    get_tier2_defaults,
    get_tier3_defaults,
    reload_config,
)

# --- LOAD PRODUCTION CONFIG (Single source of truth) ---
_raw_config = load_production_config()
_engine_params = flatten_config(_raw_config)

# Extract tier-level configs with defaults from centralized system
# This ensures fallbacks are ALWAYS synchronized with production_config.json
_t1 = {**get_tier1_defaults(), **_raw_config.get("tier1_strategy", {})}
_t2 = {
    **get_tier2_defaults(),
    **_raw_config.get("tier2_filters", _raw_config.get("tier2_quality", {})),
}
_t3 = {**get_tier3_defaults(), **_raw_config.get("tier3_risk", {})}
_mr = {
    **{"require_spy_above_sma50": True, "max_vix": 35.0},
    **_raw_config.get("market_regime", {}),
}
_perf = _raw_config.get("performance", {})

# --- PERFORMANCE OPTIMIZATION WRAPPERS ---


@st.cache_data(ttl=300, show_spinner=False)
def get_cached_intraday_data(symbol: str, interval: str, days: int):
    from src.data.market_data import MarketDataProvider

    provider = MarketDataProvider()
    return provider.get_intraday_data(symbol, interval=interval, days=days)


@st.cache_data(
    ttl=3600,
    show_spinner=False,
    hash_funcs={list: lambda x: hash(tuple(sorted(x)))},  # Deterministic list hashing
)
def run_cached_backtest(
    universe,
    start_date,
    end_date,
    initial_capital,
    risk_pct,
    risk_dollars,
    max_exposure_pct,
    max_dist_sma20,
    min_rvol,
    min_adr,
    min_volume,
    min_dollar_volume,
    rvol_danger,
    rvol_warning,
    rvol_danger_size,
    rvol_warning_size,
    adr_high,
    adr_med,
    max_stop_pct,
    min_consolidation_days,
    earnings_days,
    earnings_cushion,
    offline_mode,
    use_adaptive_filtering,
    tp1_r,
    tp2_r,
    require_spy_above_sma50,
    tp1_pct,
    tp2_pct,
    runner_pct,
    use_earnings_calendar=False,
    use_pit_universe=False,
    use_rs_percentile=True,
    min_rs_percentile=0,
    use_ml_filter=False,
    ml_filter_threshold=0.40,
    ml_boost_weight=0.20,
):
    from src.backtest.vectorbt_engine_advanced import AdvancedVectorBTEngine

    import time as _t
    _t0 = _t.time()
    engine = AdvancedVectorBTEngine(
        universe=universe,
        start_date=start_date,
        end_date=end_date,
        initial_capital=initial_capital,
        risk_pct=risk_pct,
        risk_dollars=risk_dollars,
        max_exposure_pct=max_exposure_pct,
        max_dist_sma20=max_dist_sma20,
        min_rvol=min_rvol,
        min_adr=min_adr,
        min_volume=min_volume,
        min_dollar_volume=min_dollar_volume,
        rvol_danger=rvol_danger,
        rvol_warning=rvol_warning,
        rvol_danger_size=rvol_danger_size,
        rvol_warning_size=rvol_warning_size,
        adr_high=adr_high,
        adr_med=adr_med,
        max_stop_pct=max_stop_pct,
        min_consolidation_days=min_consolidation_days,
        earnings_days=earnings_days,
        earnings_cushion=earnings_cushion,
        use_earnings_calendar=use_earnings_calendar,
        offline_mode=offline_mode,
        use_adaptive_filtering=use_adaptive_filtering,
        tp1_r=tp1_r,
        tp2_r=tp2_r,
        require_spy_above_sma50=require_spy_above_sma50,
        tp1_pct=tp1_pct,
        tp2_pct=tp2_pct,
        runner_pct=runner_pct,
        use_pit_universe=use_pit_universe,
        use_rs_percentile=use_rs_percentile,
        min_rs_percentile=min_rs_percentile,
        use_ml_filter=use_ml_filter,
        ml_filter_threshold=ml_filter_threshold,
        ml_boost_weight=ml_boost_weight,
    )
    _t1 = _t.time()
    results = engine.run_backtest()
    _t2 = _t.time()
    results["_perf_init_s"] = round(_t1 - _t0, 2)
    results["_perf_backtest_s"] = round(_t2 - _t1, 2)
    results["_perf_total_s"] = round(_t2 - _t0, 2)
    # BUG FIX: Get combined rejection stats from engine, not just filter_engine
    rejection_stats = (
        engine.get_rejection_stats() if hasattr(engine, "get_rejection_stats") else None
    )
    engine.cleanup()
    return results, rejection_stats


@st.cache_resource(show_spinner=False)
def _get_ticker_cache():
    return TickerCache()

# Lazy load ticker cache - only when needed
def get_ticker_cache():
    if 'ticker_cache_instance' not in st.session_state:
        st.session_state.ticker_cache_instance = _get_ticker_cache()
    return st.session_state.ticker_cache_instance


def get_cache_date_range():
    """Get date range from cache - with fast fallback"""
    try:
        cache = get_ticker_cache()
        # Use LIMIT 1 optimization for MIN/MAX
        cursor = cache.conn.execute(
            "SELECT date FROM ohlcv_cache ORDER BY date ASC LIMIT 1"
        )
        min_date = cursor.fetchone()
        cursor = cache.conn.execute(
            "SELECT date FROM ohlcv_cache ORDER BY date DESC LIMIT 1"
        )
        max_date = cursor.fetchone()
        
        if min_date and max_date:
            return (
                datetime.strptime(min_date[0], "%Y-%m-%d"),
                datetime.strptime(max_date[0], "%Y-%m-%d")
            )
    except Exception as e:
        pass
    # Fast fallback - don't block UI
    return datetime(2020, 1, 1), datetime.now()


def format_date_short(dt):
    if pd.isna(dt):
        return ""
    if isinstance(dt, str):
        dt = pd.to_datetime(dt)
    return dt.strftime("%d/%m/%y")


def paginate_dataframe(df, page_size=20, key_prefix="df", column_config=None, **kwargs):
    use_container_width = kwargs.pop("use_container_width", True)
    if len(df) <= page_size:
        return st.dataframe(
            df,
            use_container_width=use_container_width,
            column_config=column_config,
            **kwargs,
        )
    total_pages = (len(df) // page_size) + 1
    page_number = st.number_input(
        f"Page (1-{total_pages})",
        min_value=1,
        max_value=total_pages,
        value=1,
        step=1,
        key=f"{key_prefix}_page_input",
    )
    start_idx = (page_number - 1) * page_size
    end_idx = min(start_idx + page_size, len(df))
    st.caption(f"Showing {start_idx + 1} to {end_idx} of {len(df)}")
    return st.dataframe(
        df.iloc[start_idx:end_idx],
        use_container_width=use_container_width,
        column_config=column_config,
        **kwargs,
    )


def run_vectorbt_backtest_ui(
    start_date,
    end_date,
    equity,
    risk_pct,
    max_exp_pct,
    risk_dollars,
    tickers_list,
    max_symbols,
    offline_mode,
    max_dist_sma20,
    min_rvol,
    min_adr,
    min_volume,
    min_dollar_volume,
    rvol_danger,
    rvol_warning,
    rvol_danger_size,
    rvol_warning_size,
    adr_high,
    adr_med,
    max_stop_pct,
    min_consolidation_days,
    earnings_days,
    earnings_cushion,
    tp1_r,
    tp2_r,
    require_spy_above_sma50,
    tp1_pct,
    tp2_pct,
    runner_pct,
    use_adaptive_filtering=True,
    use_earnings_calendar=False,
    use_pit_universe=False,
    use_rs_percentile=True,
    min_rs_percentile=0,
    use_ml_filter=False,
    ml_filter_threshold=0.40,
    ml_boost_weight=0.20,
):
    progress_bar = st.progress(0)
    status_text = st.empty()
    status_text.markdown("**Running VectorBT Engine**...")
    try:
        if tickers_list:
            universe = tickers_list
            status_text.markdown(f"✅ Using manual list: {len(tickers_list)} tickers")
        else:
            import sqlite3

            # Show database query progress
            status_text.markdown("🔍 **Cargando universo desde base de datos...**")
            progress_bar.progress(0.1)
            
            conn = sqlite3.connect("./data/ticker_cache.db")
            selection_start, selection_end = str(start_date), str(end_date)
            # Adapt minimum required days to the backtest period length
            import math as _math
            _period_days = (pd.to_datetime(str(end_date)) - pd.to_datetime(str(start_date))).days
            _trading_days_est = int(_period_days * 5 / 7)  # rough estimate
            min_required_days = max(10, min(100, int(_trading_days_est * 0.5)))
            
            if max_symbols == 0:
                # DETERMINISTIC: Order by ticker AND first date to ensure consistency
                query = """
                    SELECT ticker 
                    FROM ohlcv_cache 
                    WHERE date BETWEEN ? AND ? 
                    GROUP BY ticker 
                    HAVING COUNT(*) >= ? 
                    ORDER BY ticker ASC
                """
                cursor = conn.execute(
                    query, (selection_start, selection_end, min_required_days)
                )
            else:
                # OPTIMIZED: Use pre-computed rolling_dollar_vol_20 instead of AVG()
                # This is MUCH faster since it avoids GROUP BY aggregation
                query = """
                    SELECT DISTINCT ticker
                    FROM ohlcv_cache 
                    WHERE date BETWEEN ? AND ? 
                    AND rolling_dollar_vol_20 IS NOT NULL
                    GROUP BY ticker
                    HAVING COUNT(*) >= ?
                    ORDER BY MAX(rolling_dollar_vol_20) DESC, ticker ASC
                    LIMIT ?
                """
                cursor = conn.execute(
                    query,
                    (selection_start, selection_end, min_required_days, max_symbols),
                )
            
            status_text.markdown(f"📥 **Extrayendo tickers** (límite: {'SIN LÍMITE' if max_symbols == 0 else max_symbols})...")
            progress_bar.progress(0.15)
            
            universe = [row[0] for row in cursor.fetchall()]
            conn.close()

            # DETERMINISTIC: Sort universe to ensure consistency
            universe = sorted(list(set(universe)))
            
            status_text.markdown(f"✅ **Universo cargado:** {len(universe)} tickers")
            progress_bar.progress(0.2)

            # Log universe for debugging
            import logging

            logger = logging.getLogger(__name__)
            universe_hash = hash(tuple(universe))
            logger.info(f"🎯 Universe hash: {universe_hash} ({len(universe)} tickers)")

        if not universe:
            raise ValueError("No tickers found.")

        # Sort universe one more time before caching (belt and suspenders)
        universe = sorted(list(set(universe)))
        
        status_text.markdown(f"🚀 **Iniciando backtest:** {len(universe)} tickers de {start_date} a {end_date}")
        progress_bar.progress(0.25)

        results, rejection_stats = run_cached_backtest(
            universe,
            str(start_date),
            str(end_date),
            equity,
            risk_pct / 100.0,
            risk_dollars,
            max_exp_pct / 100.0,
            max_dist_sma20,
            min_rvol,
            min_adr,
            min_volume,
            min_dollar_volume,
            rvol_danger,
            rvol_warning,
            rvol_danger_size,
            rvol_warning_size,
            adr_high,
            adr_med,
            max_stop_pct,
            min_consolidation_days,
            earnings_days,
            earnings_cushion,
            offline_mode,
            use_adaptive_filtering,
            tp1_r,
            tp2_r,
            require_spy_above_sma50,
            tp1_pct,
            tp2_pct,
            runner_pct,
            use_earnings_calendar,
            use_pit_universe,
            use_rs_percentile,
            min_rs_percentile,
            use_ml_filter,
            ml_filter_threshold,
            ml_boost_weight,
        )
        
        # Update progress after backtest completes
        status_text.markdown("✅ **Backtest completado - generando visualizaciones...**")
        progress_bar.progress(0.9)
        
        # Performance timers display
        _pi = results.get("_perf_init_s", 0)
        _pb = results.get("_perf_backtest_s", 0)
        _pt = results.get("_perf_total_s", 0)
        if _pt > 0:
            st.info(f"⏱ Performance | Engine init: **{_pi}s** | Backtest: **{_pb}s** | Total: **{_pt}s**")
            st.sidebar.caption(f"⏱ init:{_pi}s bt:{_pb}s total:{_pt}s")

        # BUG FIX: Always update session state and persistence to avoid stale data
        st.session_state["adaptive_filter_rejections"] = (
            rejection_stats if rejection_stats else {}
        )

        # Also persist to disk so diagnostics tab works after rerun
        with open("outputs/backtests/rejection_stats.json", "w") as f:
            json.dump(st.session_state["adaptive_filter_rejections"], f)

        # Clear stale legacy file if it exists to prevent UI from falling back to it
        stale_csv = "outputs/backtests/adaptive_filter_rejections.csv"
        if os.path.exists(stale_csv):
            try:
                os.remove(stale_csv)
            except:
                pass

        # Persist summary metrics for Scorecard in Tab 4
        metrics_summary = {
            "sharpe_ratio": results.get("sharpe_ratio", 0),
            "win_rate": results.get("win_rate", 0),
            "profit_factor": results.get("profit_factor", 0),
            "max_drawdown": results.get("max_drawdown", 0),
            "annualized_return": results.get("annualized_return", 0),
        }
        with open("outputs/backtests/backtest_metrics.json", "w") as f:
            json.dump(metrics_summary, f)

        trades = results["trades"]
        if not trades.empty:
            symbol_col = "symbol" if "symbol" in trades.columns else "ticker"
            entry_date_col = (
                "entry_date" if "entry_date" in trades.columns else "Entry Timestamp"
            )
            exit_date_col = (
                "exit_date" if "exit_date" in trades.columns else "Exit Timestamp"
            )
            entry_price_col = (
                "entry_price" if "entry_price" in trades.columns else "Avg Entry Price"
            )
            exit_price_col = (
                "exit_price" if "exit_price" in trades.columns else "Avg Exit Price"
            )
            output_df = pd.DataFrame(
                {
                    "symbol": trades[symbol_col],
                    "entry_date": pd.to_datetime(trades[entry_date_col]),
                    "exit_date": pd.to_datetime(trades[exit_date_col]),
                    "entry_price": trades[entry_price_col],
                    "exit_price": trades[exit_price_col],
                    "shares": trades["shares"],
                    "pnl": trades["pnl"],
                    "exit_phase": trades.get("exit_phase", "FULL"),
                    "signal_type": trades.get("entry_signal", "MOMENTUM"),
                    "stop_loss": trades.get("stop_loss", np.nan),
                    "tp1_target": trades.get("tp1_target", np.nan),
                    "tp2_target": trades.get("tp2_target", np.nan),
                    "adjusted_risk_dollars": trades.get("adjusted_risk_dollars", 0),
                    "entry_score": trades.get("entry_score", np.nan),
                }
            )
            output_df.to_csv("outputs/backtests/backtest_results.csv", index=False)
            # Also save full enriched trades for derive_tier2_filters.py
            trades.to_csv("outputs/backtests/complete_trades_clean.csv", index=False)

            # RECALCULATE scorecard metrics from actual post-ML trades
            # This fixes the bug where ML post-filter changes trades but metrics stay pre-ML
            try:
                _pnl = trades["pnl"]
                _wins = _pnl[_pnl > 0]
                _loss = _pnl[_pnl < 0]
                _wр = len(_wins) / len(_pnl) if len(_pnl) > 0 else 0
                _pf = (_wins.sum() / abs(_loss.sum())) if len(_loss) > 0 and abs(_loss.sum()) > 0 else float("inf")
                _r = trades["r_multiple"].mean() if "r_multiple" in trades.columns else 0
                # Equity curve for Sharpe/DD
                _eq = results.get("equity_curve")
                if _eq is not None and len(_eq) > 1:
                    _ret = _eq.pct_change().dropna()
                    _sharpe = (_ret.mean() / _ret.std() * (252**0.5)) if _ret.std() > 0 else 0
                    _peak = _eq.cummax()
                    _dd = ((_eq - _peak) / _peak).min()
                else:
                    _sharpe = results.get("sharpe_ratio", 0)
                    _dd = results.get("max_drawdown", 0)
                metrics_summary_real = {
                    "sharpe_ratio": float(_sharpe),
                    "win_rate": float(_wр),
                    "profit_factor": float(_pf) if _pf != float("inf") else 9999.0,
                    "max_drawdown": float(_dd),
                    "annualized_return": results.get("annualized_return", 0),
                    "avg_r": float(_r),
                }
                with open("outputs/backtests/backtest_metrics.json", "w") as _mf:
                    json.dump(metrics_summary_real, _mf)
            except Exception as _me:
                pass  # Keep original metrics if recalc fails
            if "equity_curve" in results and results["equity_curve"] is not None:
                results["equity_curve"].to_csv("outputs/backtests/equity_curve.csv")
        st.balloons()
        return True
    except Exception as e:
        st.error(f"Error: {e}")
        import traceback

        st.error(traceback.format_exc())
        return False


# --- CUSTOM CSS ---
st.set_page_config(page_title="Momentum V2 Dashboard", page_icon="📈", layout="wide")
st.markdown(
    """
<style>
    .stApp { background-color: var(--background-color); color: var(--text-color); }
    .metric-container { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 16px; margin-bottom: 24px; }
    .metric-card { 
        background-color: var(--secondary-background-color); 
        padding: 20px 16px; 
        border-radius: 12px; 
        border: 1px solid rgba(255,255,255,0.1); 
        border-left: 4px solid var(--primary-color); 
        transition: 0.3s; 
    }
    .metric-card:hover { transform: translateY(-4px); border-color: var(--primary-color); box-shadow: 0 4px 20px rgba(0,0,0,0.4); }
    .metric-label { color: #8899a6; font-size: 0.75rem; text-transform: uppercase; font-weight: 600; margin-bottom: 6px; }
    .metric-value { color: var(--text-color); font-size: 1.5rem; font-weight: 700; }
    .metric-value.positive { color: #00ffa3; }
    .metric-value.negative { color: #ff4b4b; }
    [data-testid="stSidebar"] { background-color: var(--secondary-background-color); border-right: 1px solid rgba(255,255,255,0.1); }
    
    /* Better Scrollbars */
    ::-webkit-scrollbar { width: 8px; height: 8px; }
    ::-webkit-scrollbar-track { background: rgba(0,0,0,0); }
    ::-webkit-scrollbar-thumb { background: #30363d; border-radius: 4px; }
    ::-webkit-scrollbar-thumb:hover { background: #484f58; }
    
    /* Scorecard / Semáforo Styles */
    .scorecard-container { display: flex; gap: 12px; margin-bottom: 24px; flex-wrap: wrap; }
    .scorecard-item { 
        padding: 12px 16px; 
        border-radius: 8px; 
        flex: 1; 
        min-width: 140px; 
        text-align: center;
        border: 1px solid rgba(255,255,255,0.1);
        display: flex;
        flex-direction: column;
        justify-content: center;
        transition: 0.3s;
    }
    .score-green { background-color: rgba(0, 255, 163, 0.1); border-color: #00ffa3; color: #00ffa3; box-shadow: 0 0 10px rgba(0, 255, 163, 0.1); }
    .score-yellow { background-color: rgba(255, 165, 0, 0.1); border-color: #ffa500; color: #ffa500; box-shadow: 0 0 10px rgba(255, 165, 0, 0.1); }
    .score-red { background-color: rgba(255, 75, 75, 0.1); border-color: #ff4b4b; color: #ff4b4b; box-shadow: 0 0 10px rgba(255, 75, 75, 0.1); }
    .score-label { font-size: 0.7rem; text-transform: uppercase; font-weight: 700; opacity: 0.9; margin-bottom: 4px; }
    .score-value { font-size: 1.2rem; font-weight: 800; }
</style>
""",
    unsafe_allow_html=True,
)


def render_metric_cards(metrics):
    html = '<div class="metric-container">'
    for m in metrics:
        v_class = (
            "positive"
            if "+" in str(m["value"])
            or (isinstance(m["value"], (int, float)) and m["value"] > 0)
            else ("negative" if "-" in str(m["value"]) else "")
        )
        html += f'<div class="metric-card"><div class="metric-label">{m["label"]}</div><div class="metric-value {v_class}">{m["value"]}</div>'
        if "sub" in m:
            html += f'<div style="color:#64748b;font-size:0.8rem;">{m["sub"]}</div>'
        html += "</div>"
    html += "</div>"
    st.markdown(html, unsafe_allow_html=True)


def render_scorecard(metrics_dict):
    """
    Renders a 'Semáforo' (Traffic Light) scorecard for backtest results.
     thresholds:
     - Sharpe: G>1.2, Y>0.7, R<0.7
     - WinRate: G>55%, Y>45%, R<45%
     - PF: G>1.5, Y>1.1, R<1.1
     - MaxDD: G<10%, Y<20%, R>20%
     - AvgR: G>1.5, Y>1.0, R<1.0
    """
    sharpe = metrics_dict.get("sharpe_ratio", 0)
    _wr_raw = metrics_dict.get("win_rate", 0)
    # win_rate stored as decimal (0.0-1.0) or percentage (0-100)
    # If <= 1.0, treat as decimal and multiply by 100
    win_rate = _wr_raw * 100 if _wr_raw <= 1.0 else _wr_raw
    _pf_raw = metrics_dict.get("profit_factor", 0)
    pf = float("inf") if _pf_raw >= 9999 else _pf_raw
    _dd_raw = abs(metrics_dict.get("max_drawdown", 0))
    max_dd = _dd_raw * 100 if _dd_raw <= 1.0 else _dd_raw
    avg_r = metrics_dict.get("avg_r", 0)

    def get_color(val, metric_type):
        if metric_type == "sharpe":
            return (
                "score-green"
                if val > 1.2
                else ("score-yellow" if val > 0.7 else "score-red")
            )
        if metric_type == "win_rate":
            return (
                "score-green"
                if val > 55
                else ("score-yellow" if val > 45 else "score-red")
            )
        if metric_type == "pf":
            return (
                "score-green"
                if val > 1.5
                else ("score-yellow" if val > 1.1 else "score-red")
            )
        if metric_type == "dd":
            return (
                "score-green"
                if val < 10
                else ("score-yellow" if val < 20 else "score-red")
            )
        if metric_type == "avg_r":
            return (
                "score-green"
                if val > 1.5
                else ("score-yellow" if val > 1.0 else "score-red")
            )
        return ""

    html = '<div class="scorecard-container">'

    # Sharpe
    color = get_color(sharpe, "sharpe")
    html += f'<div class="scorecard-item {color}"><div class="score-label">Sharpe Ratio</div><div class="score-value">{sharpe:.2f}</div></div>'

    # Profit Factor
    color = get_color(pf, "pf")
    pf_str = f"{pf:.2f}" if pf != float("inf") else "INF"
    html += f'<div class="scorecard-item {color}"><div class="score-label">Profit Factor</div><div class="score-value">{pf_str}</div></div>'

    # Win Rate
    color = get_color(win_rate, "win_rate")
    html += f'<div class="scorecard-item {color}"><div class="score-label">Win Rate</div><div class="score-value">{win_rate:.1f}%</div></div>'

    # Max DD
    color = get_color(max_dd, "dd")
    html += f'<div class="scorecard-item {color}"><div class="score-label">Max Drawdown</div><div class="score-value">{max_dd:.1f}%</div></div>'

    # Avg R
    color = get_color(avg_r, "avg_r")
    html += f'<div class="scorecard-item {color}"><div class="score-label">Avg R-Mult</div><div class="score-value">{avg_r:.2f}R</div></div>'

    html += "</div>"
    st.markdown(html, unsafe_allow_html=True)


# --- SIDEBAR (Wired to production_config.json) ---
with st.sidebar:
    st.title("Momentum V2")
    st.caption("Institutional Trading Engine")

    # Show loaded config version
    st.caption(f"Config: THOR-Optimized | Sharpe: {_perf.get('sharpe_ratio', 0):.2f}")

    if st.button("Clear Cache", use_container_width=True):
        st.cache_data.clear()
        st.cache_resource.clear()
        st.toast("Cache Cleared")
    st.markdown("---")

    with st.expander("Market & Universe", expanded=True):
        cache_min, cache_max = get_cache_date_range()
        start_date = st.date_input("Start", value=cache_max - timedelta(days=365))
        end_date = st.date_input("End", value=cache_max)
        scan_mode = st.radio(
            "Source", ["Manual", "All Market", "Sector"], horizontal=True
        )
        tickers_input = st.text_area("Tickers (CSV)", "APP, PLTR", height=70)

    with st.expander("Risk Management", expanded=False):
        equity = st.number_input(
            "Equity ($)",
            value=int(
                _raw_config.get("ui_defaults", {}).get("initial_capital", 100000)
            ),
        )

        # Compounding toggle
        use_compounding = st.checkbox(
            "Enable Compounding",
            value=_t3.get("compounding_enabled", False),
            help="When enabled, risk amount scales with account equity (recommended). When disabled, fixed dollar risk is used.",
        )

        if use_compounding:
            risk_pct = st.slider(
                "Risk per Trade (%)",
                0.1,
                3.0,
                float(_t3.get("risk_fraction", 0.01) * 100),
                step=0.1,
                help="Percentage of equity to risk per trade (compounding mode)",
            )
            risk_dollars = 0  # Not used in compounding mode
            st.info(
                f"Risk: ${equity * (risk_pct / 100):,.0f} per trade (1.0% of equity)"
            )
        else:
            risk_dollars = st.number_input(
                "Risk per Trade ($)",
                value=int(_t1.get("risk_dollars", 1000)),
                min_value=50,
                max_value=2000,
                step=50,
                help="Fixed dollar risk per trade (no compounding)",
            )
            risk_pct = 0.0  # Not used in fixed dollar mode

        max_exp = st.slider(
            "Max Exposure (%)",
            5,
            100,
            int(_t3.get("max_exposure_pct", 0.65) * 100),
        )

    with st.expander("Strategy & Targets", expanded=False):
        tp1_r = st.number_input(
            "TP1 (R)",
            value=float(_t1.get("tp1_r", 1.5)),
            min_value=0.5,
            max_value=5.0,
            step=0.25,
        )
        tp2_r = st.number_input(
            "TP2 (R)",
            value=float(_t1.get("tp2_r", 6.0)),
            min_value=1.0,
            max_value=10.0,
            step=0.5,
        )
        # Show actual optimized distribution from config
        tp1_p = float(_t1.get("tp1_pct", 0.45))
        tp2_p = float(_t1.get("tp2_pct", 0.25))
        run_p = float(_t1.get("runner_pct", 0.30))
        st.info(
            f"Distribution: TP1={tp1_p * 100:.0f}% / TP2={tp2_p * 100:.0f}% / Runner={run_p * 100:.0f}%"
        )

        max_stop_pct_raw = float(_t1.get("max_stop_pct", 0.08))
        st.info(f"Max Stop: {max_stop_pct_raw * 100:.1f}% (Tier 1 optimized)")

    with st.expander("Tier 2 Filters (Derived)", expanded=False):
        use_adaptive = st.checkbox("Adaptive Engine (Tiered Filters)", value=True)
        use_earnings_filter = st.checkbox(
            "Earnings Filter",
            value=False,
            help=f"Avoid entries within {_t3.get('earnings_days', 5)} days of earnings announcements. Requires earnings calendar data in cache.",
        )
        use_pit = st.checkbox(
            "Point-in-Time Universe (S&P 500)",
            value=False,
            help="Use historical S&P 500 composition to eliminate survivorship bias. "
            "Only trades tickers that were ACTUALLY in the index on each date.",
        )
        use_ml = st.checkbox(
            "🤖 ML Entry Filter (LightGBM)",
            value=False,
            help="Aplica el modelo EntryScorer: bloquea entradas con prob<0.40 y boost entry_score en las que pasan. ROC-AUC: 0.807",
        )
        if use_ml:
            ml_threshold = st.slider("ML threshold", 0.30, 0.60, 0.40, step=0.05,
                help="Entradas con prob ML por debajo de este valor son bloqueadas")
            ml_boost = st.slider("ML boost weight", 0.0, 0.40, 0.20, step=0.05,
                help="entry_score += boost * ml_prob para entradas que pasan el filtro")
        else:
            ml_threshold = 0.40
            ml_boost = 0.20
        min_rvol = st.slider(
            "Min RVOL",
            0.5,
            3.0,
            float(_t2.get("min_rvol", 0.91)),
            step=0.1,
        )
        max_dist = st.slider(
            "Max Dist SMA20%",
            1.0,
            30.0,
            float(_t2.get("max_dist_sma20", 8.94)),
            step=0.1,
        )
        st.caption(
            f"Min ADR: {_t2.get('min_adr', 1.97)}% | Min $Vol: ${_t2.get('min_dollar_volume', 20000000):,.0f}"
        )

    with st.expander("Tier 3 Risk (Fixed)", expanded=False):
        st.caption("Institutional risk parameters - not editable")
        st.text(
            f"RVOL Danger: {_t3.get('rvol_danger', 3.0)}x -> {_t3.get('rvol_danger_size', 0.5) * 100:.0f}% size"
        )
        st.text(
            f"RVOL Warning: {_t3.get('rvol_warning', 2.0)}x -> {_t3.get('rvol_warning_size', 0.75) * 100:.0f}% size"
        )
        st.text(
            f"ADR High: {_t3.get('adr_high', 6.0)}% | ADR Med: {_t3.get('adr_med', 5.0)}%"
        )
        st.text(
            f"SPY > SMA50: {'ON' if _mr.get('require_spy_above_sma50', True) else 'OFF'}"
        )

    st.markdown("---")
    benchmark_ticker = st.selectbox("Benchmark", ["SPY", "QQQ", "IWM", "DIA"], index=0)

    if st.button("RUN BACKTEST", use_container_width=True, type="primary"):
        manual_list = [s.strip().upper() for s in tickers_input.split(",") if s.strip()]
        if run_vectorbt_backtest_ui(
            start_date,
            end_date,
            equity,
            risk_pct
            if use_compounding
            else 0.5,  # risk_pct as percentage (e.g. 1.0 = 1%), run_vectorbt_backtest_ui divides by 100
            max_exp,
            risk_dollars if not use_compounding else 0,
            manual_list if scan_mode == "Manual" else None,
            0 if scan_mode == "All Market" else 500,
            True,  # offline_mode
            max_dist,
            min_rvol,
            float(_t2.get("min_adr", 2.48)),
            int(_t2.get("min_volume", 300000)),
            int(_t2.get("min_dollar_volume", 20000000)),
            float(_t3.get("rvol_danger", 3.0)),
            float(_t3.get("rvol_warning", 2.0)),
            # Engine expects integer units for rvol sizes (divides by 100 internally)
            int(round(_t3.get("rvol_danger_size", 0.5) * 100)),
            int(round(_t3.get("rvol_warning_size", 0.75) * 100)),
            float(_t3.get("adr_high", 6.0)),
            float(_t3.get("adr_med", 5.0)),
            # Engine expects percentage unit for max_stop_pct (divides by 100 internally)
            float(_t1.get("max_stop_pct", 0.08) * 100),
            int(_t2.get("min_consolidation_days", 10)),
            int(_t3.get("earnings_days", 5)),
            float(_t3.get("earnings_cushion", 2)),
            tp1_r,
            tp2_r,
            bool(_mr.get("require_spy_above_sma50", True)),
            tp1_p,
            tp2_p,
            run_p,
            use_adaptive,
            use_earnings_filter,
            use_pit,
            True,  # use_rs_percentile
            0,  # min_rs_percentile
            use_ml,
            ml_threshold,
            ml_boost,
        ):
            st.rerun()

# --- MAIN PAGE ---
st.title("Institutional Dashboard")

# Calculate results summary if they exist for the top bar
top_net_pnl = 0
if os.path.exists("outputs/backtests/backtest_results.csv"):
    try:
        _temp_df = pd.read_csv("outputs/backtests/backtest_results.csv")
        top_net_pnl = _temp_df["pnl"].sum()
    except:
        pass

# Config summary bar
cc1, cc2, cc3, cc4, cc5, cc6 = st.columns(6)
cc1.metric("TP1/TP2", f"{_t1.get('tp1_r', 0):.2f}R / {_t1.get('tp2_r', 0):.2f}R")
cc2.metric("Max Stop", f"{_t1.get('max_stop_pct', 0) * 100:.2f}%")
cc3.metric("Risk", f"${_t1.get('risk_dollars', 0):.2f}")
cc4.metric("SPY>SMA50", "ON" if _mr.get("require_spy_above_sma50") else "OFF")
cc5.metric("Val Sharpe", f"{_perf.get('sharpe_ratio', 0):.2f}")
cc6.metric("Final Equity", f"${(equity + top_net_pnl):,.2f}", f"{top_net_pnl:+,.2f}")
st.markdown("---")

if os.path.exists("outputs/backtests/backtest_results.csv"):
    df = pd.read_csv("outputs/backtests/backtest_results.csv")
    df["entry_date"] = pd.to_datetime(df["entry_date"])
    df["exit_date"] = pd.to_datetime(df["exit_date"])

    # Round numeric columns for cleaner UI
    numeric_cols = df.select_dtypes(include=[np.number]).columns
    df[numeric_cols] = df[numeric_cols].round(2)

    # --- GROUP PARTIAL EXITS INTO COMPLETE TRADES ---
    # The CSV has one row per partial exit (TP1, TP2, RUNNER, STOP).
    # TradeGrouper merges them into single complete trades.
    trade_df_for_grouper = df.rename(columns={"symbol": "ticker"})
    grouped_trades = TradeGrouper.group_partial_trades(trade_df_for_grouper)

    # Round grouped trades as well
    if not grouped_trades.empty:
        g_numeric_cols = grouped_trades.select_dtypes(include=[np.number]).columns
        grouped_trades[g_numeric_cols] = grouped_trades[g_numeric_cols].round(2)

    # R-multiples availability check (shared across tabs)
    has_r = (
        "r_multiple" in grouped_trades.columns
        and grouped_trades["r_multiple"].abs().sum() > 0
    )

    t1, t2, t3, t4, t5, t6, t7 = st.tabs(
        [
            "Performance",
            "Trade Log",
            "QuantStats",
            "Diagnostics",
            "Insights",
            "Market Regime",
            "🎓 Anatomía del Trade",
        ]
    )

    # --- Fetch Benchmark Data ---
    @st.cache_data(ttl=3600)
    @st.cache_data(ttl=3600, show_spinner=False)
    def get_benchmark_returns(ticker, start, end):
        """Fetch benchmark returns - tries cache first, then yfinance direct, then SQLite."""
        import yfinance as yf
        s_str = start.strftime("%Y-%m-%d") if isinstance(start, datetime) else str(start)[:10]
        e_str = end.strftime("%Y-%m-%d") if isinstance(end, datetime) else str(end)[:10]

        # 1. Try yfinance direct (most reliable, always fresh)
        try:
            df = yf.download(ticker, start=s_str, end=e_str,
                             auto_adjust=True, progress=False, timeout=10)
            if df is not None and not df.empty:
                close = df["Close"] if "Close" in df.columns else df.iloc[:, 0]
                if isinstance(close, pd.DataFrame):
                    close = close.iloc[:, 0]
                return close.pct_change().fillna(0)
        except Exception:
            pass

        # 2. Try SQLite cache
        try:
            import sqlite3
            conn_bm = sqlite3.connect("data/ticker_cache.db")
            rows = conn_bm.execute(
                "SELECT date, close FROM ohlcv_cache WHERE ticker=? AND date BETWEEN ? AND ? ORDER BY date",
                (ticker, s_str, e_str)
            ).fetchall()
            conn_bm.close()
            if rows:
                bm_df = pd.DataFrame(rows, columns=["date", "close"])
                bm_df["date"] = pd.to_datetime(bm_df["date"])
                bm_df = bm_df.set_index("date")
                return bm_df["close"].pct_change().fillna(0)
        except Exception:
            pass

        # 3. Try MarketDataProvider
        try:
            from src.data.market_data import MarketDataProvider
            provider = MarketDataProvider()
            df = provider.get_daily_data(ticker, start_date=s_str, end_date=e_str)
            if not df.empty:
                close_col = "Close" if "Close" in df.columns else "close"
                return df[close_col].pct_change().fillna(0)
        except Exception:
            pass

        return pd.Series(dtype=float)

    benchmark_returns = get_benchmark_returns(benchmark_ticker, start_date, end_date)

    # =========================================================================
    # TAB 1: PERFORMANCE (Full QuantStats integration)
    # =========================================================================
    with t1:
        # --- Trade-based metrics (from grouped complete trades) ---
        total_trades = len(grouped_trades)
        winners = (
            int(grouped_trades["is_winner"].sum()) if not grouped_trades.empty else 0
        )
        losers = total_trades - winners
        net_pnl = grouped_trades["total_pnl"].sum() if not grouped_trades.empty else 0
        win_rate = (winners / total_trades * 100) if total_trades > 0 else 0

        # Profit factor
        gross_profit = (
            grouped_trades[grouped_trades["is_winner"]]["total_pnl"].sum()
            if winners > 0
            else 0
        )
        gross_loss = (
            abs(grouped_trades[~grouped_trades["is_winner"]]["total_pnl"].sum())
            if losers > 0
            else 0
        )
        profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else float("inf")

        # Avg win/loss
        avg_win = (
            grouped_trades[grouped_trades["is_winner"]]["total_pnl"].mean()
            if winners > 0
            else 0
        )
        avg_loss = (
            grouped_trades[~grouped_trades["is_winner"]]["total_pnl"].mean()
            if losers > 0
            else 0
        )

        # R-multiples (already calculated above)
        avg_r = grouped_trades["r_multiple"].mean() if has_r else 0

        # Exit analysis
        hit_tp1 = (
            int(grouped_trades["hit_tp1"].sum())
            if "hit_tp1" in grouped_trades.columns
            else 0
        )
        hit_tp2 = (
            int(grouped_trades["hit_tp2"].sum())
            if "hit_tp2" in grouped_trades.columns
            else 0
        )
        had_runner = (
            int(grouped_trades["had_runner"].sum())
            if "had_runner" in grouped_trades.columns
            else 0
        )
        was_stopped = (
            int(grouped_trades["was_stopped_out"].sum())
            if "was_stopped_out" in grouped_trades.columns
            else 0
        )

        # Avg hold days
        avg_hold = (
            grouped_trades["hold_days"].mean()
            if "hold_days" in grouped_trades.columns
            else 0
        )

        # Entry Score statistics
        has_entry_score = "entry_score" in grouped_trades.columns
        avg_entry_score = grouped_trades["entry_score"].mean() if has_entry_score else 0
        high_score_trades = (
            int((grouped_trades["entry_score"] >= 0.5).sum()) if has_entry_score else 0
        )
        low_score_trades = (
            int((grouped_trades["entry_score"] < 0.3).sum()) if has_entry_score else 0
        )

        # --- Row 1: Core metrics ---
        render_metric_cards(
            [
                {"label": "Net Profit", "value": f"${net_pnl:,.2f}"},
                {
                    "label": "Win Rate",
                    "value": f"{win_rate:.2f}%",
                    "sub": f"{winners}W / {losers}L",
                },
                {
                    "label": "Total Trades",
                    "value": str(total_trades),
                    "sub": f"({len(df)} partial exits)",
                },
                {
                    "label": "Profit Factor",
                    "value": f"{profit_factor:.2f}"
                    if profit_factor != float("inf")
                    else "INF",
                },
                {
                    "label": "Avg Win / Loss",
                    "value": f"${avg_win:,.2f} / ${avg_loss:,.2f}",
                },
            ]
        )

        # --- Row 2: Exit analysis ---
        render_metric_cards(
            [
                {
                    "label": "Hit TP1",
                    "value": str(hit_tp1),
                    "sub": f"{hit_tp1 / total_trades * 100:.2f}% of trades"
                    if total_trades > 0
                    else "",
                },
                {
                    "label": "Hit TP2",
                    "value": str(hit_tp2),
                    "sub": f"{hit_tp2 / total_trades * 100:.2f}% of trades"
                    if total_trades > 0
                    else "",
                },
                {
                    "label": "Runners",
                    "value": str(had_runner),
                    "sub": f"{had_runner / total_trades * 100:.2f}% of trades"
                    if total_trades > 0
                    else "",
                },
                {
                    "label": "Stopped Out",
                    "value": str(was_stopped),
                    "sub": f"{was_stopped / total_trades * 100:.2f}% of trades"
                    if total_trades > 0
                    else "",
                },
                {"label": "Avg Hold", "value": f"{avg_hold:.2f}d"},
            ]
        )

        # --- Row 3: Entry Score Analysis ---
        if has_entry_score:
            st.markdown("### Entry Quality Score v2 Analysis")
            st.caption(
                "Metodología: 70% RS Rank (60d Relative Strength) + 30% Proximidad a Máximo 52-Semanas."
            )
            col_es1, col_es2, col_es3, col_es4 = st.columns(4)
            with col_es1:
                st.metric("Avg Entry Score", f"{avg_entry_score:.3f}")
            with col_es2:
                st.metric(
                    "High Score (≥0.5)",
                    f"{high_score_trades}",
                    delta=f"{high_score_trades / total_trades * 100:.1f}%",
                    help="Trades con RS dominante y cercanía a máximos (Menor resistencia)",
                )
            with col_es3:
                st.metric(
                    "Low Score (<0.3)",
                    f"{low_score_trades}",
                    delta=f"-{low_score_trades / total_trades * 100:.1f}%"
                    if low_score_trades > 0
                    else "0%",
                    delta_color="inverse",
                    help="Trades con RS débil o lejos de máximos",
                )
            with col_es4:
                corr = (
                    grouped_trades["entry_score"].corr(grouped_trades["total_pnl"])
                    if total_trades > 5
                    else 0
                )
                st.metric(
                    "Score-PnL Corr",
                    f"{corr:.3f}",
                    help="Correlación entre Calidad de Entrada y PnL Final",
                )

        # --- QuantStats Time-Series Metrics ---
        st.markdown("### Time-Series Analytics")

        try:
            # Filter trades by date range
            if start_date and end_date:
                filter_start = pd.to_datetime(start_date)
                filter_end = pd.to_datetime(end_date)
                filtered_trades_t1 = trade_df_for_grouper[
                    (pd.to_datetime(trade_df_for_grouper["entry_date"]) >= filter_start)
                    & (pd.to_datetime(trade_df_for_grouper["entry_date"]) <= filter_end)
                ]
            else:
                filtered_trades_t1 = trade_df_for_grouper

            analyzer = QuantStatsAnalyzer(
                trade_log=filtered_trades_t1,
                initial_capital=equity if "equity" in dir() else 100000,
                benchmark_ticker=benchmark_ticker,
            )
            # Pass benchmark returns if available
            qs_metrics = analyzer.get_quantstats_metrics(
                benchmark_data=benchmark_returns
                if not benchmark_returns.empty
                else None
            )

            if qs_metrics:
                # First row: Primary metrics
                qs_col1, qs_col2, qs_col3, qs_col4 = st.columns(4)

                with qs_col1:
                    st.markdown("**Risk-Adjusted Returns**")
                    sharpe = qs_metrics.get("sharpe_ratio", 0)
                    sortino = qs_metrics.get("sortino_ratio", 0)
                    calmar = qs_metrics.get("calmar_ratio", 0)
                    render_metric_cards(
                        [
                            {
                                "label": "Sharpe",
                                "value": f"{sharpe:.2f}" if sharpe else "N/A",
                            },
                            {
                                "label": "Sortino",
                                "value": f"{sortino:.2f}" if sortino else "N/A",
                            },
                            {
                                "label": "Calmar",
                                "value": f"{calmar:.2f}" if calmar else "N/A",
                            },
                        ]
                    )

                with qs_col2:
                    st.markdown("**Returns & Drawdown**")
                    cagr = qs_metrics.get("cagr", 0)
                    total_ret = qs_metrics.get("total_return", 0)
                    max_dd = qs_metrics.get("max_drawdown", 0)
                    render_metric_cards(
                        [
                            {
                                "label": "CAGR",
                                "value": f"{cagr * 100:+.2f}%" if cagr else "N/A",
                            },
                            {
                                "label": "Total Return",
                                "value": f"{total_ret * 100:+.2f}%"
                                if total_ret
                                else "N/A",
                            },
                            {
                                "label": "Max DD",
                                "value": f"{max_dd * 100:.2f}%" if max_dd else "N/A",
                            },
                        ]
                    )

                with qs_col3:
                    st.markdown("**Trade Statistics**")
                    total_trades = qs_metrics.get("total_trades", 0)
                    win_rate = qs_metrics.get("win_rate", 0)
                    profit_factor = qs_metrics.get("profit_factor", 0)
                    render_metric_cards(
                        [
                            {
                                "label": "Total Trades",
                                "value": f"{int(total_trades)}"
                                if total_trades
                                else "N/A",
                            },
                            {
                                "label": "Win Rate",
                                "value": f"{win_rate * 100:.1f}%"
                                if win_rate
                                else "N/A",
                            },
                            {
                                "label": "Profit Factor",
                                "value": f"{profit_factor:.2f}"
                                if profit_factor
                                else "N/A",
                            },
                        ]
                    )

                with qs_col4:
                    st.markdown("**Risk Metrics**")
                    var_95 = qs_metrics.get("var_95", 0)
                    cvar_95 = qs_metrics.get("cvar_95", 0)
                    vol = qs_metrics.get("volatility_annual", 0)
                    render_metric_cards(
                        [
                            {
                                "label": "VaR (95%)",
                                "value": f"{var_95 * 100:.2f}%" if var_95 else "N/A",
                            },
                            {
                                "label": "CVaR (95%)",
                                "value": f"{cvar_95 * 100:.2f}%" if cvar_95 else "N/A",
                            },
                            {
                                "label": "Volatility",
                                "value": f"{vol * 100:.2f}%" if vol else "N/A",
                            },
                        ]
                    )

                # Second row: Additional metrics
                st.markdown("---")
                qs_col5, qs_col6, qs_col7, qs_col8 = st.columns(4)

                with qs_col5:
                    st.markdown("**Win/Loss Analysis**")
                    avg_win = qs_metrics.get("avg_win", 0)
                    avg_loss = qs_metrics.get("avg_loss", 0)
                    avg_wl_ratio = qs_metrics.get("avg_win_loss_ratio", 0)
                    render_metric_cards(
                        [
                            {
                                "label": "Avg Win",
                                "value": f"${avg_win:.0f}" if avg_win else "N/A",
                            },
                            {
                                "label": "Avg Loss",
                                "value": f"${avg_loss:.0f}" if avg_loss else "N/A",
                            },
                            {
                                "label": "Win/Loss Ratio",
                                "value": f"{avg_wl_ratio:.2f}"
                                if avg_wl_ratio
                                else "N/A",
                            },
                        ]
                    )

                with qs_col6:
                    st.markdown("**Exposure & Streaks**")
                    exposure = qs_metrics.get("exposure_time_pct", 0)
                    max_cons_wins = qs_metrics.get("max_consecutive_wins", 0)
                    max_cons_losses = qs_metrics.get("max_consecutive_losses", 0)
                    render_metric_cards(
                        [
                            {
                                "label": "Exposure Time",
                                "value": f"{exposure:.1f}%" if exposure else "N/A",
                            },
                            {
                                "label": "Max Consec. Wins",
                                "value": f"{int(max_cons_wins)}"
                                if max_cons_wins
                                else "N/A",
                            },
                            {
                                "label": "Max Consec. Losses",
                                "value": f"{int(max_cons_losses)}"
                                if max_cons_losses
                                else "N/A",
                            },
                        ]
                    )

                with qs_col7:
                    st.markdown("**Distribution**")
                    skewness = qs_metrics.get("skewness", 0)
                    kurtosis = qs_metrics.get("kurtosis", 0)
                    avg_hold = qs_metrics.get("avg_holding_period", 0)
                    render_metric_cards(
                        [
                            {
                                "label": "Skewness",
                                "value": f"{skewness:.3f}"
                                if skewness is not None
                                else "N/A",
                            },
                            {
                                "label": "Kurtosis",
                                "value": f"{kurtosis:.3f}"
                                if kurtosis is not None
                                else "N/A",
                            },
                            {
                                "label": "Avg Hold Days",
                                "value": f"{avg_hold:.1f}" if avg_hold else "N/A",
                            },
                        ]
                    )

                with qs_col8:
                    st.markdown(f"**Benchmark vs {benchmark_ticker}**")
                    alpha = qs_metrics.get("alpha", 0)
                    beta = qs_metrics.get("beta", 0)
                    info_ratio = qs_metrics.get("information_ratio", 0)
                    render_metric_cards(
                        [
                            {
                                "label": "Alpha",
                                "value": f"{alpha:.2f}" if alpha is not None else "N/A",
                            },
                            {
                                "label": "Beta",
                                "value": f"{beta:.2f}" if beta is not None else "N/A",
                            },
                            {
                                "label": "Info Ratio",
                                "value": f"{info_ratio:.2f}"
                                if info_ratio is not None
                                else "N/A",
                            },
                        ]
                    )
        except Exception as e:
            st.warning(f"QuantStats metrics unavailable: {e}")

        # ═══════════════════════════════════════════════════════════════════════
        # ANÁLISIS DE ENTRY SCORE, RS Y POSITION SIZING
        # ═══════════════════════════════════════════════════════════════════════
        try:
            from src.analytics.trade_analytics import generate_full_trade_analysis

            if "trade_df_for_grouper" in dir() and not trade_df_for_grouper.empty:
                analysis = generate_full_trade_analysis(trade_df_for_grouper)

                st.markdown("---")
                st.markdown("### 📊 Entry Score v2, RS & Position Sizing Analysis")
                st.info(
                    "Entry Score v2 = 70% RS Rank (Cross-sectional) + 30% 52wk High Proximity. Prioriza ganadores de momentum con poca resistencia superior."
                )

                # Insights
                if "insights" in analysis and analysis["insights"]:
                    for insight in analysis["insights"]:
                        st.markdown(f"- {insight}")

                # Entry Score Analysis
                es = analysis.get("entry_score", {})
                if es and "high_score_trades" in es:
                    st.markdown("#### Entry Quality Score Performance")
                    col1, col2, col3, col4 = st.columns(4)

                    with col1:
                        st.metric(
                            "Score-PnL Corr",
                            f"{es.get('corr_entry_score_vs_pnl', 'N/A')}",
                        )
                    with col2:
                        hs = es.get("high_score_trades", {})
                        st.metric(
                            "High Score (≥0.7)",
                            f"{hs.get('count', 0)}",
                            f"{hs.get('win_rate', 0)}% WR",
                        )
                    with col3:
                        ms = es.get("med_score_trades", {})
                        st.metric(
                            "Med Score (0.4-0.7)",
                            f"{ms.get('count', 0)}",
                            f"{ms.get('win_rate', 0)}% WR",
                        )
                    with col4:
                        ls = es.get("low_score_trades", {})
                        st.metric(
                            "Low Score (<0.4)",
                            f"{ls.get('count', 0)}",
                            f"{ls.get('win_rate', 0)}% WR",
                        )

                # RS Percentile Analysis
                rs = analysis.get("rs_percentile", {})
                if rs and "high_rs_trades" in rs:
                    st.markdown("#### RS Percentile Performance (IBD-Style)")
                    col1, col2, col3, col4 = st.columns(4)

                    with col1:
                        st.metric("RS-PnL Corr", f"{rs.get('corr_rs_vs_pnl', 'N/A')}")
                    with col2:
                        hrs = rs.get("high_rs_trades", {})
                        st.metric(
                            "RS≥80 (Top 20%)",
                            f"{hrs.get('count', 0)}",
                            f"{hrs.get('win_rate', 0)}% WR",
                        )
                    with col3:
                        mrs = rs.get("med_rs_trades", {})
                        st.metric(
                            "RS 50-80",
                            f"{mrs.get('count', 0)}",
                            f"{mrs.get('win_rate', 0)}% WR",
                        )
                    with col4:
                        lrs = rs.get("low_rs_trades", {})
                        st.metric(
                            "RS<50 (Bottom 50%)",
                            f"{lrs.get('count', 0)}",
                            f"{lrs.get('win_rate', 0)}% WR",
                        )

                # Position Sizing Analysis
                ps = analysis.get("position_sizing", {})
                if ps and "r_distribution" in ps:
                    st.markdown("#### Position Sizing & R-Multiple")
                    col1, col2, col3, col4 = st.columns(4)

                    rd = ps.get("r_distribution", {})
                    with col1:
                        st.metric("Mean R", f"{rd.get('mean_r', 'N/A')}")
                    with col2:
                        st.metric("Median R", f"{rd.get('median_r', 'N/A')}")
                    with col3:
                        st.metric("Big Wins (≥2R)", f"{rd.get('big_wins_pct', 'N/A')}%")
                    with col4:
                        st.metric(
                            "Big Losses (≤-1R)", f"{rd.get('big_losses_pct', 'N/A')}%"
                        )

                # Context Analysis
                ctx = analysis.get("context", {})
                if ctx and "rvol_correlation" in ctx:
                    st.markdown("#### Context Correlations")
                    col1, col2 = st.columns(2)

                    rvol_corr = ctx.get("rvol_correlation", {})
                    with col1:
                        st.metric(
                            "RVOL-PnL Corr", f"{rvol_corr.get('corr_vs_pnl', 'N/A')}"
                        )

                    adr_corr = ctx.get("adr_correlation", {})
                    with col2:
                        st.metric(
                            "ADR-PnL Corr", f"{adr_corr.get('corr_vs_pnl', 'N/A')}"
                        )

                # Pattern Analysis
                pat = analysis.get("pattern_performance", {})
                if (
                    pat
                    and "summary" in pat
                    and "total_trades" in pat.get("summary", {})
                ):
                    st.markdown("#### Pattern Detection Performance")

                    # Summary
                    ps = pat.get("summary", {})
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric("Total Trades", f"{ps.get('total_trades', 0)}")
                    with col2:
                        st.metric("With Pattern", f"{ps.get('trades_with_pattern', 0)}")
                    with col3:
                        st.metric(
                            "Detection Rate",
                            f"{ps.get('pattern_detection_rate', 0):.1%}",
                        )

                    # Pattern vs None
                    pvn = pat.get("pattern_vs_none", {})
                    if pvn:
                        col1, col2 = st.columns(2)
                        with col1:
                            wp = pvn.get("with_pattern", {})
                            st.metric(
                                "With Pattern: Win Rate",
                                f"{wp.get('win_rate', 0):.1%}",
                                f"Avg R: {wp.get('avg_r', 0):.2f}",
                            )
                        with col2:
                            wop = pvn.get("no_pattern", {})
                            st.metric(
                                "No Pattern: Win Rate",
                                f"{wop.get('win_rate', 0):.1%}",
                                f"Avg R: {wop.get('avg_r', 0):.2f}",
                            )

                    # By Pattern Type
                    by_pat = pat.get("by_pattern", {})
                    if by_pat:
                        st.markdown("##### Performance by Pattern Type")
                        pattern_data = []
                        for ptype, stats in by_pat.items():
                            pattern_data.append(
                                {
                                    "Pattern": ptype,
                                    "Count": stats.get("count", 0),
                                    "Win Rate": f"{stats.get('win_rate', 0):.1%}",
                                    "Avg R": f"{stats.get('avg_r', 0):.2f}",
                                    "Avg PnL": f"${stats.get('avg_pnl', 0):.2f}",
                                }
                            )
                        if pattern_data:
                            st.dataframe(
                                pd.DataFrame(pattern_data),
                                hide_index=True,
                                use_container_width=True,
                            )

                    # Confidence Buckets
                    conf_buckets = pat.get("confidence_buckets", {})
                    if conf_buckets:
                        st.markdown("##### Performance by Confidence")
                        bucket_data = []
                        for bucket, stats in conf_buckets.items():
                            bucket_data.append(
                                {
                                    "Confidence": bucket,
                                    "Count": stats.get("count", 0),
                                    "Win Rate": f"{stats.get('win_rate', 0):.1%}",
                                    "Avg R": f"{stats.get('avg_r', 0):.2f}",
                                }
                            )
                        if bucket_data:
                            st.dataframe(
                                pd.DataFrame(bucket_data),
                                hide_index=True,
                                use_container_width=True,
                            )

                # Store analysis for PDF export
                if "analysis" not in dir():
                    analysis_data = analysis

        except Exception as e:
            st.warning(f"Advanced trade analysis unavailable: {e}")

        # --- Cumulative PnL Chart ---
        st.markdown("### Equity Curve")

        # Build equity curve from grouped trades (by exit date)
        if not grouped_trades.empty:
            eq_data = grouped_trades[["final_exit_date", "total_pnl"]].copy()
            eq_data = eq_data.sort_values("final_exit_date")
            eq_data["cumulative_pnl"] = eq_data["total_pnl"].cumsum()

            fig = go.Figure()
            fig.add_trace(
                go.Scatter(
                    x=eq_data["final_exit_date"],
                    y=eq_data["cumulative_pnl"],
                    mode="lines",
                    fill="tozeroy",
                    line=dict(color="#00ffa3", width=2),
                    fillcolor="rgba(0, 255, 163, 0.1)",
                    name="Cumulative PnL",
                )
            )
            fig.update_layout(
                title="Cumulative PnL (Complete Trades)",
                xaxis_title="Date",
                yaxis_title="PnL ($)",
                template="plotly_dark",
                height=400,
            )
            st.plotly_chart(fig, use_container_width=True)

        # --- Monthly Returns Heatmap ---
        if not grouped_trades.empty:
            st.markdown("### Monthly Returns")
            monthly = grouped_trades.copy()
            monthly["month"] = monthly["final_exit_date"].dt.to_period("M")
            monthly_pnl = monthly.groupby("month")["total_pnl"].sum()

            if len(monthly_pnl) > 1:
                monthly_df = monthly_pnl.reset_index()
                monthly_df["month"] = monthly_df["month"].dt.to_timestamp()
                monthly_df["year"] = monthly_df["month"].dt.year
                monthly_df["mo"] = monthly_df["month"].dt.month

                pivot = monthly_df.pivot_table(
                    values="total_pnl", index="year", columns="mo", aggfunc="sum"
                ).fillna(0)
                pivot.columns = [calendar.month_abbr[m] for m in pivot.columns]

                fig_hm = px.imshow(
                    pivot.values,
                    x=pivot.columns.tolist(),
                    y=[str(y) for y in pivot.index.tolist()],
                    color_continuous_scale="RdYlGn",
                    aspect="auto",
                    labels=dict(color="PnL ($)"),
                )
                fig_hm.update_layout(
                    title="Monthly PnL Heatmap",
                    template="plotly_dark",
                    height=300,
                )
                st.plotly_chart(fig_hm, use_container_width=True)

        # --- R-Multiple Distribution ---
        if has_r and not grouped_trades.empty:
            st.markdown("### R-Multiple Distribution")
            fig_r = px.histogram(
                grouped_trades,
                x="r_multiple",
                nbins=30,
                color_discrete_sequence=["#00ffa3"],
                labels={"r_multiple": "R-Multiple"},
            )
            fig_r.update_layout(
                title=f"R-Multiple Distribution (Avg: {avg_r:+.2f}R)",
                template="plotly_dark",
                height=300,
            )
            st.plotly_chart(fig_r, use_container_width=True)

    # =========================================================================
    # TAB 2: TRADE LOG
    # =========================================================================
    with t2:
        # Quick Sort / Filter Options
        st.markdown("### 🔍 Filter & Sort")
        q_col1, q_col2, q_col3 = st.columns(3)

        with q_col1:
            view_mode = st.radio(
                "View Mode", ["Complete Trades", "All Partial Exits"], horizontal=True
            )

        with q_col2:
            quick_sort = st.selectbox(
                "Quick Sort (Entire Dataset)",
                [
                    "Latest First",
                    "Oldest First",
                    "Top Winners ($)",
                    "Top Losers ($)",
                    "High R-Multiple",
                    "High Entry Score",
                    "Low Entry Score",
                ],
                index=0,
            )

        with q_col3:
            show_all = st.checkbox(
                "Show All (Disable Pagination)",
                value=False,
                help="May be slow for >1000 trades",
            )

        if view_mode == "Complete Trades":
            display_source = grouped_trades.copy()
            display_source = display_source.rename(columns={"ticker": "symbol"})
            # Select most useful columns
            show_cols = [
                "symbol",
                "entry_date",
                "final_exit_date",
                "entry_price",
                "total_pnl",
                "total_shares",
                "exit_phases",
                "hold_days",
                "entry_score",
                "pattern_type",
                "rs_percentile",
            ]
            if has_r:
                show_cols.append("r_multiple")

            # Ensure RS percentile exists, fallback to 0 if missing
            if "rs_percentile" not in display_source.columns:
                display_source["rs_percentile"] = 0

            show_cols = [c for c in show_cols if c in display_source.columns]

            # Apply sorting before pagination
            if quick_sort == "Latest First":
                display_df = display_source[show_cols].sort_values(
                    "final_exit_date", ascending=False
                )
            elif quick_sort == "Oldest First":
                display_df = display_source[show_cols].sort_values(
                    "final_exit_date", ascending=True
                )
            elif quick_sort == "Top Winners ($)":
                display_df = display_source[show_cols].sort_values(
                    "total_pnl", ascending=False
                )
            elif quick_sort == "Top Losers ($)":
                display_df = display_source[show_cols].sort_values(
                    "total_pnl", ascending=True
                )
            elif quick_sort == "High R-Multiple" and "r_multiple" in show_cols:
                display_df = display_source[show_cols].sort_values(
                    "r_multiple", ascending=False
                )
            elif quick_sort == "High Entry Score" and "entry_score" in show_cols:
                display_df = display_source[show_cols].sort_values(
                    "entry_score", ascending=False
                )
            elif quick_sort == "Low Entry Score" and "entry_score" in show_cols:
                display_df = display_source[show_cols].sort_values(
                    "entry_score", ascending=True
                )
            else:
                display_df = display_source[show_cols].sort_values(
                    "final_exit_date", ascending=False
                )
        else:
            # Partial exits view - ensure entry_score column is visible
            partial_cols = [
                "symbol",
                "entry_date",
                "exit_date",
                "exit_phase",
                "entry_price",
                "exit_price",
                "shares",
                "pnl",
                "entry_score",
                "pattern_type",
                "rs_percentile",
            ]

            # Fallback for RS in partials
            if "rs_percentile" not in df.columns:
                df["rs_percentile"] = 0

            partial_cols = [c for c in partial_cols if c in df.columns]

            if quick_sort == "Latest First":
                display_df = df[partial_cols].sort_values("exit_date", ascending=False)
            elif quick_sort == "Oldest First":
                display_df = df[partial_cols].sort_values("exit_date", ascending=True)
            elif quick_sort == "Top Winners ($)":
                display_df = df[partial_cols].sort_values("pnl", ascending=False)
            elif quick_sort == "Top Losers ($)":
                display_df = df[partial_cols].sort_values("pnl", ascending=True)
            elif quick_sort == "High Entry Score" and "entry_score" in partial_cols:
                display_df = df[partial_cols].sort_values(
                    "entry_score", ascending=False
                )
            elif quick_sort == "Low Entry Score" and "entry_score" in partial_cols:
                display_df = df[partial_cols].sort_values("exit_date", ascending=True)
            else:
                display_df = df[partial_cols].sort_values("exit_date", ascending=False)

        selected_symbol = st.selectbox(
            "Filter Symbol", ["All"] + sorted(df["symbol"].unique().tolist())
        )
        if selected_symbol != "All":
            sym_col = "symbol" if "symbol" in display_df.columns else "ticker"
            display_df = display_df[display_df[sym_col] == selected_symbol]

        # Filter by date range (start_date / end_date from backtest config)
        if start_date and end_date:
            filter_start = pd.to_datetime(start_date)
            filter_end = pd.to_datetime(end_date)
            date_col = (
                "entry_date"
                if "entry_date" in display_df.columns
                else "final_exit_date"
            )
            display_df = display_df[
                (display_df[date_col] >= filter_start)
                & (display_df[date_col] <= filter_end)
            ]

        if not display_df.empty:
            display_df_display = display_df.copy()
            date_cols = [c for c in display_df_display.columns if "date" in c.lower()]
            for col in date_cols:
                if col in display_df_display.columns:
                    display_df_display[col] = display_df_display[col].apply(
                        format_date_short
                    )

            has_score = "entry_score" in display_df_display.columns
        else:
            display_df_display = display_df
            has_score = False

        # Build column configuration
        log_column_config = {
            "entry_score": st.column_config.ProgressColumn(
                "Score",
                help="Entry Quality v2: 70% RS Rank + 30% 52wk High Proximity",
                format="%.3f",
                min_value=0.0,
                max_value=1.0,
            ),
            "rs_percentile": st.column_config.ProgressColumn(
                "RS Percentile",
                help="Relative Strength Percentile (0-100)",
                format="%d",
                min_value=0,
                max_value=100,
            ),
            "pattern_type": st.column_config.TextColumn(
                "Pattern", help="Detected Chart Pattern"
            ),
        }

        if show_all:
            st.dataframe(
                display_df_display,
                use_container_width=True,
                height=600,
                column_config=log_column_config,
            )
        else:
            paginate_dataframe(
                display_df_display,
                key_prefix="trades_log",
                column_config=log_column_config,
            )

        st.markdown("---")
        st.subheader("Trade Chart Viewer")
        if not display_df.empty:
            # Synchronize with the filtered and sorted display_df
            trade_options = display_df.index.tolist()

            if view_mode == "Complete Trades":

                def format_fn(i):
                    row = display_source.loc[i]
                    return f"{row['symbol']} - {row['entry_date'].date()} (${row['total_pnl']:,.2f})"

                source_df = display_source
            else:

                def format_fn(i):
                    row = df.loc[i]
                    return f"{row['symbol']} - {row['entry_date'].date()} ({row['exit_phase']} - ${row['pnl']:,.2f})"

                source_df = df

            trade_idx = st.selectbox(
                "Select Trade to Visualize (Follows filters/sort above)",
                trade_options,
                format_func=format_fn,
            )

            if st.button("Show Detailed Chart"):
                dash = InteractiveDashboard("outputs/backtests/backtest_results.csv")

                # If it's a grouped trade, we need all partials
                if view_mode == "Complete Trades":
                    main_trade = grouped_trades.loc[trade_idx]
                    # Find all partial exits for this trade
                    partials = df[
                        (df["symbol"] == main_trade["ticker"])
                        & (df["entry_date"] == main_trade["entry_date"])
                    ]

                    exits = []
                    for _, p in partials.iterrows():
                        exits.append(
                            {
                                "date": p["exit_date"],
                                "price": p["exit_price"],
                                "type": p["exit_phase"],
                                "qty_pct": (
                                    p["shares"] / main_trade["total_shares"] * 100
                                )
                                if main_trade["total_shares"] > 0
                                else 0,
                            }
                        )

                    signal_data = {
                        "camino": main_trade.get("signal_type", "MOMENTUM"),
                        "entry_price": main_trade["entry_price"],
                        "stop_loss": main_trade.get("stop_loss"),
                        "exits": exits,
                        "outcome": "WIN" if main_trade["total_pnl"] > 0 else "LOSS",
                        "return_pct": (
                            main_trade["total_pnl"]
                            / (main_trade["entry_price"] * main_trade["total_shares"])
                            * 100
                        )
                        if (main_trade["entry_price"] * main_trade["total_shares"]) > 0
                        else 0,
                        "hold_days": main_trade["hold_days"],
                        "pattern_type": main_trade.get("pattern_type", "NONE"),
                        "pivot_price": main_trade.get("pivot_price"),
                        "pattern_confidence": main_trade.get("pattern_confidence", 0),
                    }
                    symbol = main_trade["ticker"]
                    entry_date = main_trade["entry_date"]
                else:
                    # Single partial exit view
                    trade = df.loc[trade_idx]
                    signal_data = {
                        "camino": trade.get("signal_type", "MOMENTUM"),
                        "entry_price": trade["entry_price"],
                        "stop_loss": trade.get("stop_loss"),
                        "exit_price": trade["exit_price"],
                        "outcome": "WIN" if trade["pnl"] > 0 else "LOSS",
                        "return_pct": (trade["exit_price"] - trade["entry_price"])
                        / trade["entry_price"]
                        * 100,
                        "hold_days": (trade["exit_date"] - trade["entry_date"]).days,
                        "pattern_type": trade.get("pattern_type", "NONE"),
                        "pivot_price": trade.get("pivot_price"),
                        "pattern_confidence": trade.get("pattern_confidence", 0),
                    }
                    symbol = trade["symbol"]
                    entry_date = trade["entry_date"]

                st.plotly_chart(
                    dash.create_trade_chart(
                        symbol,
                        entry_date.strftime("%Y-%m-%d"),
                        signal_data,
                    ),
                    use_container_width=True,
                )

    # =========================================================================
    # TAB 3: QUANTSTATS (Professional Analytics)
    # =========================================================================
    with t3:
        st.header(f"Performance vs {benchmark_ticker}")

        if grouped_trades.empty:
            st.warning("No trades to analyze. Run a backtest first.")
        elif benchmark_returns.empty:
            st.warning(
                f"Could not load {benchmark_ticker} benchmark data for this period. "
                "This can happen in offline mode or when the date range has no cached SPY data. "
                "Try running the backtest in online mode or with a longer date range."
            )
            # Still show strategy metrics without benchmark
            st.markdown("### Strategy Metrics (no benchmark)")
            try:
                from src.analytics.quantstats_analyzer import QuantStatsAnalyzer
                _analyzer_solo = QuantStatsAnalyzer(
                    trade_log=trade_df_for_grouper,
                    initial_capital=equity,
                    benchmark_ticker=None,
                )
                _qs_m = _analyzer_solo.get_quantstats_metrics()
                if _qs_m:
                    _c1, _c2, _c3 = st.columns(3)
                    _c1.metric("Sharpe", f"{_qs_m.get('sharpe', 0):.2f}")
                    _c2.metric("Max DD", f"{_qs_m.get('max_drawdown', 0)*100:.2f}%")
                    _c3.metric("CAGR", f"{_qs_m.get('cagr', 0)*100:.2f}%")
            except Exception as _qe:
                st.info(f"Metrics unavailable: {_qe}")
        else:
            # Filter trades by date range
            if start_date and end_date:
                filter_start = pd.to_datetime(start_date)
                filter_end = pd.to_datetime(end_date)
                filtered_trades = trade_df_for_grouper[
                    (pd.to_datetime(trade_df_for_grouper["entry_date"]) >= filter_start)
                    & (pd.to_datetime(trade_df_for_grouper["entry_date"]) <= filter_end)
                ]
            else:
                filtered_trades = trade_df_for_grouper

            # Re-initialize analyzer for report generation
            analyzer = QuantStatsAnalyzer(
                trade_log=filtered_trades,
                initial_capital=equity,
                benchmark_ticker=benchmark_ticker,
            )

            # --- Returns Comparison Chart ---
            st.markdown("### Cumulative Returns vs Benchmark")

            strat_returns = analyzer.daily_returns
            aligned_bench = benchmark_returns.reindex(strat_returns.index).fillna(0)

            cum_strat = (1 + strat_returns).cumprod() - 1
            cum_bench = (1 + aligned_bench).cumprod() - 1

            fig_comp = go.Figure()
            fig_comp.add_trace(
                go.Scatter(
                    x=cum_strat.index,
                    y=cum_strat * 100,
                    mode="lines",
                    name="Strategy",
                    line=dict(color="#00ffa3", width=3),
                )
            )
            fig_comp.add_trace(
                go.Scatter(
                    x=cum_bench.index,
                    y=cum_bench * 100,
                    mode="lines",
                    name=benchmark_ticker,
                    line=dict(color="#8899a6", width=2, dash="dash"),
                )
            )

            fig_comp.update_layout(
                title=f"Strategy vs {benchmark_ticker} Cumulative Returns",
                yaxis_title="Return (%)",
                template="plotly_dark",
                height=500,
                hovermode="x unified",
            )
            st.plotly_chart(fig_comp, use_container_width=True)

            # --- QuantStats Detailed Plots ---
            st.markdown("### Advanced Analytics")

            col_q1, col_q2 = st.columns(2)

            with col_q1:
                # Underwater Plot
                st.markdown("**Underwater Plot (Drawdowns)**")
                if len(strat_returns) > 0:
                    dd = qs.stats.to_drawdown_series(strat_returns)
                    fig_dd = px.area(
                        x=dd.index, y=dd * 100, color_discrete_sequence=["#ff4b4b"]
                    )
                    fig_dd.update_layout(
                        template="plotly_dark",
                        height=300,
                        yaxis_title="Drawdown (%)",
                        showlegend=False,
                    )
                    st.plotly_chart(fig_dd, use_container_width=True)
                else:
                    st.info("Not enough data for drawdown analysis.")

            with col_q2:
                # Rolling Beta
                st.markdown(f"**Rolling Beta vs {benchmark_ticker}**")
                try:
                    # Align benchmark exactly to strategy returns
                    aligned_bench_local = aligned_bench.reindex(
                        strat_returns.index
                    ).fillna(0)

                    # Determine best window (min between 126 and 1/3 of total data)
                    available_days = len(strat_returns)
                    adaptive_window = min(126, max(10, available_days // 3))

                    if available_days > 20:
                        # Use rolling_greeks and extract beta (rolling_beta is deprecated/missing in some qs versions)
                        greeks = qs.stats.rolling_greeks(
                            strat_returns, aligned_bench_local, periods=adaptive_window
                        )
                        rolling_beta = greeks["beta"]

                        fig_beta = px.line(
                            x=rolling_beta.index,
                            y=rolling_beta.values,
                            color_discrete_sequence=["#00d1ff"],
                        )
                        fig_beta.update_layout(
                            title=f"Rolling Beta ({adaptive_window}d)",
                            template="plotly_dark",
                            height=300,
                            yaxis_title="Beta",
                            showlegend=False,
                        )
                        st.plotly_chart(fig_beta, use_container_width=True)
                    else:
                        st.info(f"Need > 20 days for beta (current: {available_days})")
                except Exception as e:
                    st.error(f"Beta error: {e}")

            # --- Monthly Returns ---
            st.markdown("### Monthly Returns (%)")
            import pandas as pd
            if len(strat_returns) > 0 and isinstance(strat_returns.index, pd.DatetimeIndex):
                monthly_ret = qs.stats.monthly_returns(strat_returns) * 100
                # Format for display
                st.dataframe(
                    monthly_ret.style.background_gradient(cmap="RdYlGn", axis=None).format(
                        "{:.2f}%"
                    ),
                    use_container_width=True,
                )
            else:
                st.info("Not enough valid date-indexed data for monthly returns.")

            # --- Report Generation ---
            st.markdown("---")
            if st.button("Generate Full PDF Tearsheet"):
                with st.spinner("Generating professional PDF report..."):
                    report_path = analyzer.generate_pdf_report(
                        benchmark_ticker=benchmark_ticker
                    )
                    if report_path:
                        st.success(f"PDF Report generated successfully!")
                        with open(report_path, "rb") as f:
                            st.download_button(
                                label="Download PDF Tearsheet",
                                data=f,
                                file_name=os.path.basename(report_path),
                                mime="application/pdf",
                            )
    # =========================================================================
    # TAB 4: DIAGNOSTICS (Rejection funnel + filter analysis)
    # =========================================================================
    with t4:
        # --- Backtest Scorecard (Semáforo) ---
        scorecard_metrics = {}
        if os.path.exists("outputs/backtests/backtest_metrics.json"):
            try:
                with open("outputs/backtests/backtest_metrics.json", "r") as f:
                    scorecard_metrics = json.load(f)

                # Add Avg R if available from grouped_trades
                if not grouped_trades.empty and "r_multiple" in grouped_trades.columns:
                    scorecard_metrics["avg_r"] = grouped_trades["r_multiple"].mean()

                st.subheader("Performance Scorecard")
                render_scorecard(scorecard_metrics)
                st.markdown("---")
            except Exception as e:
                st.warning(f"Error loading scorecard metrics: {e}")

        # Try session state first, then persisted file
        rejections = None
        if "adaptive_filter_rejections" in st.session_state:
            rejections = st.session_state["adaptive_filter_rejections"]
        elif os.path.exists("outputs/backtests/rejection_stats.json"):
            try:
                with open("outputs/backtests/rejection_stats.json", "r") as f:
                    rejections = json.load(f)
            except:
                pass
        elif os.path.exists("outputs/backtests/adaptive_filter_rejections.csv"):
            try:
                rej_csv = pd.read_csv(
                    "outputs/backtests/adaptive_filter_rejections.csv"
                )
                rejections = dict(zip(rej_csv.iloc[:, 0], rej_csv.iloc[:, 1]))
            except Exception as e:
                st.error(f"Error loading rejection data: {e}")

        if rejections:
            st.subheader("Filter Rejection Funnel")
            st.caption(
                "Motivos por los cuales se descartaron candidatos durante el escaneo (Tier 1 & Tier 2)."
            )

            try:
                # Convert rejections to a clean DataFrame for plotting with AGGREGATION
                rej_items_raw = []
                for k, v in rejections.items():
                    if v > 0:
                        # AGGREGATION LOGIC: Simplify complex reasons
                        reason = k
                        if "LowRVOL" in k:
                            reason = "Low RVOL (Tier 2)"
                        elif "LowADR" in k:
                            reason = "Low ADR (Tier 2)"
                        elif "Overextended" in k:
                            reason = "Overextended (Tier 2)"
                        elif "ShortConsolidation" in k:
                            reason = "Short Consolidation (Tier 3)"
                        elif "WeakSector" in k:
                            reason = "Weak Sector (Tier 3)"
                        elif "Earnings" in k:
                            reason = "Earnings Risk"
                        elif "MarketRegime" in k or "Regime" in k:
                            reason = "Market Regime Risk"
                        elif "TIER1" in k:
                            reason = "Tier 1: Market Safety"
                        elif "TIER2" in k:
                            reason = "Tier 2: Dynamic Quality"
                        elif "TIER3" in k:
                            reason = "Tier 3: Secondary Filters"
                        else:
                            # Default cleaning
                            reason = (
                                k.replace("blocked_by_", "").replace("_", " ").title()
                            )

                        rej_items_raw.append({"Reason": reason, "Count": int(v)})

                if rej_items_raw:
                    # Group by the simplified reason to aggregate counts
                    rej_df_raw = pd.DataFrame(rej_items_raw)
                    rej_df = rej_df_raw.groupby("Reason")["Count"].sum().reset_index()
                    rej_df = rej_df.sort_values("Count", ascending=True)

                    fig_funnel = px.bar(
                        rej_df,
                        x="Count",
                        y="Reason",
                        orientation="h",
                        title="Trade Rejection Distribution (Aggregated)",
                        color="Count",
                        color_continuous_scale="Reds",
                        template="plotly_dark",
                        text="Count",  # Show numbers on bars
                    )
                    fig_funnel.update_traces(textposition="outside")
                    fig_funnel.update_layout(
                        height=max(350, len(rej_df) * 40),
                        margin=dict(l=20, r=40, t=60, b=20),
                        xaxis_title="Number of Rejected Entries",
                        yaxis_title="",
                    )
                    st.plotly_chart(fig_funnel, use_container_width=True)
                else:
                    st.info("No rejection data to display for this period.")
            except Exception as e:
                st.warning(f"Could not render funnel: {e}")

            # --- NEW: Market Regime & Exposure Analysis ---
            st.markdown("---")
            st.subheader("📊 Market Regime & Exposure Analysis")

            try:
                from src.utils.market_regime import (
                    MarketRegimeClassifier,
                    load_spy_vix_data,
                )

                # Load SPY data for the backtest period
                # First try offline for speed, then online if missing
                spy_data, vix_data = load_spy_vix_data(
                    str(start_date), str(end_date), cache=get_ticker_cache(), offline=True
                )

                if spy_data is None or spy_data.empty:
                    with st.spinner("Downloading SPY/VIX data for market analysis..."):
                        spy_data, vix_data = load_spy_vix_data(
                            str(start_date),
                            str(end_date),
                            cache=get_ticker_cache(),
                            offline=False,
                        )

                if spy_data is not None and not spy_data.empty:
                    classifier = MarketRegimeClassifier(spy_data, vix_data)
                    context_df = classifier.get_context_series()

                    col_m1, col_m2 = st.columns(2)

                    with col_m1:
                        st.markdown("**Market Regime Timeline**")
                        # Map stages to colors
                        stage_colors = {
                            "STAGE_1": "#00ffa3",  # Bull - Green
                            "STAGE_2": "#ffa500",  # Consolidation - Orange
                            "STAGE_3": "#ff7f00",  # Distribution - Dark Orange
                            "STAGE_4": "#ff4b4b",  # Bear - Red
                        }

                        fig_regime = go.Figure()

                        # Add SPY Price
                        fig_regime.add_trace(
                            go.Scatter(
                                x=spy_data.index,
                                y=spy_data["close"],
                                name="SPY Price",
                                line=dict(color="white", width=1.5),
                            )
                        )

                        # Add background colors for stages
                        for stage, color in stage_colors.items():
                            mask = context_df["market_stage"] == stage
                            if mask.any():
                                # Find contiguous blocks
                                diff = mask.astype(int).diff().fillna(0)
                                starts = spy_data.index[diff == 1].tolist()
                                if mask.iloc[0]:
                                    starts.insert(0, spy_data.index[0])
                                ends = spy_data.index[diff == -1].tolist()
                                if mask.iloc[-1]:
                                    ends.append(spy_data.index[-1])

                                for s, e in zip(starts, ends):
                                    fig_regime.add_vrect(
                                        x0=s,
                                        x1=e,
                                        fillcolor=color,
                                        opacity=0.15,
                                        layer="below",
                                        line_width=0,
                                        name=stage,
                                    )

                        fig_regime.update_layout(
                            template="plotly_dark",
                            height=400,
                            margin=dict(l=20, r=20, t=30, b=20),
                            yaxis_title="SPY Price",
                            showlegend=True,
                        )
                        st.plotly_chart(fig_regime, use_container_width=True)
                        st.caption(
                            "Background colors indicate Market Stage (Green=Bull, Red=Bear). Your system filters entries in Red/Orange stages."
                        )

                    with col_m2:
                        st.markdown("**Portfolio Exposure Density**")
                        if not grouped_trades.empty:
                            # Calculate daily exposure
                            dates = pd.date_range(start_date, end_date)
                            exposure_series = pd.Series(0, index=dates)

                            for _, trade in grouped_trades.iterrows():
                                mask = (
                                    exposure_series.index >= trade["entry_date"]
                                ) & (exposure_series.index <= trade["final_exit_date"])
                                exposure_series[mask] += 1

                            fig_exp = px.area(
                                x=exposure_series.index,
                                y=exposure_series.values,
                                title="Active Trades Over Time",
                                labels={"x": "Date", "y": "Open Positions"},
                                color_discrete_sequence=["#00ffa3"],
                            )
                            fig_exp.update_layout(template="plotly_dark", height=400)
                            st.plotly_chart(fig_exp, use_container_width=True)

                            avg_exp = exposure_series.mean()
                            st.caption(
                                f"Average open positions: {avg_exp:.2f}. Periods with 0 positions explain the low Exposure Time."
                            )
                else:
                    st.warning(
                        "Could not load SPY data for regime analysis. Ensure SPY is in cache."
                    )
            except Exception as e:
                st.error(f"Error generating regime analysis: {e}")

            # --- NEW: Expert Metric Analysis (Dynamic) ---
            st.markdown("#### 💡 Análisis Experto de Métricas")
            exp_col1, exp_col2 = st.columns(2)

            # Get actual values from metrics
            exposure = qs_metrics.get("exposure_time_pct", 0) if qs_metrics else 0
            beta_val = qs_metrics.get("beta", 0) if qs_metrics else 0
            
            with exp_col1:
                # Dynamic interpretation based on actual exposure
                if exposure > 0:
                    exposure_quality = "excelente" if exposure < 15 else "moderado" if exposure < 30 else "alto"
                    in_market_pct = exposure
                    in_cash_pct = 100 - exposure
                    
                    st.info(f"**Exposure Time ({exposure:.1f}%)**")
                    st.write(f"""
                    Este valor es **{exposure_quality}** para una estrategia de momentum quirúrgica:
                    * **Eficiencia:** Capital en riesgo solo el {in_market_pct:.1f}% del tiempo.
                    * **Selectividad:** Sistema estricto, opera solo en condiciones óptimas.
                    * **Protección:** El {in_cash_pct:.1f}% del tiempo estás en cash, evitando drawdowns innecesarios.
                    """)
                else:
                    st.info("**Exposure Time**")
                    st.write("Métrica no disponible para este período.")

            with exp_col2:
                # Dynamic interpretation based on actual beta
                if beta_val is not None and abs(beta_val) > 0.01:
                    if beta_val < -0.1:
                        beta_desc = "**fuertemente descorrelacionado negativo**"
                        benefit = "Alta protección cuando el mercado cae"
                    elif beta_val < 0:
                        beta_desc = "**ligeramente descorrelacionado negativo**"
                        benefit = "Cierta protección en caídas del mercado"
                    elif beta_val < 0.5:
                        beta_desc = "**baja correlación positiva**"
                        benefit = "Independencia moderada del mercado"
                    elif beta_val < 1.0:
                        beta_desc = "**correlación positiva moderada**"
                        benefit = "Se mueve con el mercado, pero con menor volatilidad"
                    else:
                        beta_desc = "**alta correlación con el mercado**"
                        benefit = "Sigue de cerca los movimientos del SPY"
                    
                    st.info(f"**Beta ({beta_val:+.2f})**")
                    st.write(f"""
                    Tu estrategia está {beta_desc} del SPY:
                    * **Carácter:** {benefit}.
                    * **Alpha Puro:** Retornos generados por selección de activos, no por el mercado.
                    * **Valor Institucional:** {'Alta resiliencia buscada por fondos' if beta_val < 0 else 'Diversificación moderada'}.
                    """)
                else:
                    st.info("**Beta**")
                    st.write("Métrica no disponible o beta cercano a cero (estrategia neutral).")
            # --- END EXPERT ANALYSIS ---

            st.markdown("---")
            # --- END NEW SECTION ---

            rej_df = pd.DataFrame(
                [{"filter": k, "rejections": v} for k, v in rejections.items()]
            ).sort_values("rejections", ascending=False)

            # Categorize by tier
            def categorize_tier(filter_name):
                fn = filter_name.lower()
                if any(
                    x in fn
                    for x in ["tier1", "spy", "market", "regime", "vix", "warmup"]
                ):
                    return "Tier 1 (Market Safety)"
                elif any(
                    x in fn
                    for x in [
                        "tier2",
                        "tier3",
                        "rvol",
                        "adr",
                        "sma20",
                        "consolidat",
                        "volume",
                        "sector",
                        "overextended",
                    ]
                ):
                    return "Tier 2 (Quality Filter)"
                else:
                    return "Other"

            rej_df["tier"] = rej_df["filter"].apply(categorize_tier)

            # Summary by tier
            tier_summary = rej_df.groupby("tier")["rejections"].sum().reset_index()

            col_d1, col_d2 = st.columns([1, 2])

            with col_d1:
                st.markdown("**Rejections by Tier**")
                for _, row in tier_summary.iterrows():
                    st.metric(row["tier"], f"{row['rejections']:,}")
                st.metric("Total Rejections", f"{rej_df['rejections'].sum():,}")

            with col_d2:
                fig_rej = px.bar(
                    rej_df.head(15),
                    x="filter",
                    y="rejections",
                    color="tier",
                    title="Top 15 Rejection Reasons",
                    color_discrete_map={
                        "Tier 1 (Market Safety)": "#ff4b4b",
                        "Tier 2 (Quality Filter)": "#ffa500",
                        "Other": "#64748b",
                    },
                )
                fig_rej.update_layout(
                    template="plotly_dark",
                    xaxis_tickangle=-45,
                    height=450,
                )
                st.plotly_chart(fig_rej, use_container_width=True)

            # Detailed table
            with st.expander("Full Rejection Detail"):
                st.dataframe(rej_df, use_container_width=True)
        else:
            st.info(
                "No rejection data available. Run a backtest to see filter diagnostics."
            )

        # --- Trade Distribution Analysis ---
        if not grouped_trades.empty:
            st.markdown("---")
            st.subheader("Trade Distribution Analysis")

            col_da, col_db = st.columns(2)

            with col_da:
                # Outcome breakdown
                if "outcome_category" in grouped_trades.columns:
                    outcome_counts = grouped_trades["outcome_category"].value_counts()
                    fig_out = px.pie(
                        values=outcome_counts.values,
                        names=outcome_counts.index,
                        title="Trade Outcome Distribution",
                        color_discrete_sequence=px.colors.qualitative.Set2,
                    )
                    fig_out.update_layout(template="plotly_dark", height=350)
                    st.plotly_chart(fig_out, use_container_width=True)

            with col_db:
                # Exit phase breakdown
                exit_counts = grouped_trades["exit_phases"].value_counts().head(10)
                fig_exit = px.bar(
                    x=exit_counts.index,
                    y=exit_counts.values,
                    title="Exit Phase Combinations",
                    labels={"x": "Exit Phases", "y": "Count"},
                    color_discrete_sequence=["#00ffa3"],
                )
                fig_exit.update_layout(template="plotly_dark", height=350)
                st.plotly_chart(fig_exit, use_container_width=True)

    # =========================================================================
    # TAB 5: INSIGHTS (Dynamic from config)
    # =========================================================================
    # TAB 5: INSIGHTS (Configuration Display - Dynamic)
    # =========================================================================
    with t5:
        st.header("⚙️ Configuración del Sistema")
        st.caption(f"Parámetros activos cargados desde: `config/production_config.json`")

        col_i1, col_i2 = st.columns(2)

        with col_i1:
            st.markdown("### 🎯 Tier 1: Estrategia Core")
            st.markdown(f"**Take Profit Multi-Fase:**")
            
            tp1_pct = _t1.get('tp1_pct', 0) * 100
            tp2_pct = _t1.get('tp2_pct', 0) * 100
            runner_pct = _t1.get('runner_pct', 0) * 100
            tp1_r = _t1.get('tp1_r', 0)
            tp2_r = _t1.get('tp2_r', 0)
            
            st.info(f"**TP1:** {tp1_pct:.0f}% de posición @ {tp1_r:.1f}R")
            st.info(f"**TP2:** {tp2_pct:.0f}% de posición @ {tp2_r:.1f}R")
            st.info(f"**Runner:** {runner_pct:.0f}% con EMA8/EMA21 crossover + ATR trailing")
            
            st.markdown("**Gestión de Riesgo:**")
            max_stop = _t1.get('max_stop_pct', 0) * 100
            risk_dollars = _t1.get('risk_dollars', 0)
            st.info(f"Stop Loss Máximo: {max_stop:.1f}%")
            st.info(f"Riesgo por Trade: ${risk_dollars:.0f}")

            st.markdown("---")
            st.markdown("### 🔬 Tier 2: Filtros de Calidad")
            
            min_rvol = _t2.get('min_rvol', 0)
            max_dist_sma20 = _t2.get('max_dist_sma20', 0)
            min_adr = _t2.get('min_adr', 0)
            min_dollar_vol = _t2.get('min_dollar_volume', 0)
            
            st.info(f"**RVOL Mínimo:** {min_rvol:.1f}x (volumen relativo)")
            st.info(f"**Distancia Max SMA20:** {max_dist_sma20:.1f}% (evita sobreextensión)")
            st.info(f"**ADR Mínimo:** {min_adr:.2f}% (rango promedio diario)")
            st.info(f"**Volumen Mínimo:** ${min_dollar_vol:,.0f} (liquidez)")

        with col_i2:
            st.markdown("### 🛡️ Tier 3: Gestión de Riesgo")
            
            rvol_danger = _t3.get('rvol_danger', 0)
            rvol_danger_size = _t3.get('rvol_danger_size', 0) * 100
            rvol_warning = _t3.get('rvol_warning', 0)
            rvol_warning_size = _t3.get('rvol_warning_size', 0) * 100
            max_exposure = _t3.get('max_exposure_pct', 0) * 100
            max_position = _t3.get('max_position_pct', 0) * 100
            
            st.markdown("**Ajustes por Volatilidad:**")
            st.warning(f"**RVOL Peligro (≥{rvol_danger:.1f}x):** Reduce size a {rvol_danger_size:.0f}%")
            st.warning(f"**RVOL Alerta (≥{rvol_warning:.1f}x):** Reduce size a {rvol_warning_size:.0f}%")
            
            st.markdown("**Límites de Cartera:**")
            st.info(f"**Max Exposure Total:** {max_exposure:.0f}% del capital")
            st.info(f"**Max Posición Individual:** {max_position:.0f}% del capital")

            st.markdown("---")
            st.markdown("### 🌊 Market Regime Filter")
            
            require_spy_sma50 = _mr.get('require_spy_above_sma50', False)
            max_vix = _mr.get('max_vix', 40)
            
            st.info(f"**SPY > SMA50:** {'✅ Requerido' if require_spy_sma50 else '❌ No requerido'}")
            st.info(f"**VIX Máximo:** {max_vix:.0f} (por encima = BLOCKED)")
            
            st.markdown("**Reglas de Stage:**")
            st.success("Stage 1 (Bull): 100% size")
            st.warning("Stage 2 (Consolidation): 75% size")
            st.error("Stage 3/4 (Distribution/Bear): BLOCKED")

            if _perf:
                st.markdown("---")
                st.markdown("### 📈 Performance de Validación")
                st.caption("Resultados del último proceso de optimización")
                
                val_sharpe = _perf.get('sharpe_ratio', 0)
                val_wr = _perf.get('win_rate_pct', 0)
                val_trades = _perf.get('total_trades', 0)
                val_return = _perf.get('total_return_pct', 0)
                
                perf_col1, perf_col2 = st.columns(2)
                with perf_col1:
                    st.metric("Sharpe Ratio", f"{val_sharpe:.2f}")
                    st.metric("Win Rate", f"{val_wr:.1f}%")
                with perf_col2:
                    st.metric("Total Trades", f"{val_trades}")
                    st.metric("Return", f"{val_return:+.2f}%")
    with t6:
        st.header("🌊 Market Regime — Cómo Funciona el Filtro")
        st.caption(
            "Esta pestaña explica cómo el sistema clasifica las condiciones del mercado día a día "
            "y muestra qué días se permitieron trades o se bloquearon durante tu backtest."
        )

        with st.expander("¿Cómo funciona el Market Regime filter?", expanded=True):
            col_edu1, col_edu2 = st.columns([1, 1])
            with col_edu1:
                st.markdown("""
**El sistema clasifica cada día en uno de 4 Stages:**

| Stage | Nombre | Condición | Acción |
|-------|--------|-----------|--------|
| Stage 1 | Bull Trend | SPY > SMA50 & SMA200, momentum > 3%, VIX < 20 | Tamaño completo |
| Stage 2 | Consolidación | SPY saludable pero sin momentum claro | 75% size |
| Stage 3 | Distribución | **2 de 3:** SPY < SMA50 · vol > 1.5 · VIX > 20 | BLOQUEADO |
| Stage 4 | Bear Trend | SPY < SMA200 & SMA50, momentum < -5% | BLOQUEADO |

**¿Por qué 2-de-3 para Stage 3?** Los mercados distribuyen *antes* de que el VIX explote.
Si SPY está bajo SMA50 Y la volatilidad está elevada, es suficiente para parar el trading
aunque el VIX no haya llegado a 25. El sistema viejo requería las 3 condiciones (AND),
lo que significaba que el filtro actuaba demasiado tarde.
""")
            with col_edu2:
                st.markdown("""
**Las 3 señales monitoreadas diariamente:**

**Price Action** — SPY vs SMA50 y SMA200
Cuando el precio rompe bajo su promedio de 50 días, el dinero institucional está reduciendo exposición.

**Volatility** — Promedio de 20 días del rango diario %
Rangos intraday elevados destruyen setups de swing. Umbral: > 1.5% (reducido de 2.0).

**VIX** — Volatilidad implícita de opciones del S&P 500
VIX > 20 = mercado pagando prima por protección a corto plazo.
Hard cap en 25: por encima de esto, no hay entradas sin importar otras señales.
Sistema viejo usaba 35 como cap — eso es nivel pandemia/guerra, demasiado tarde.

**VIX Term Structure:** Cuando VIX spot > VIX 3-meses (backwardation),
el pánico institucional está confirmado — la señal de peligro más fuerte a corto plazo.
""")

        st.markdown("---")
        st.subheader("Regime Timeline")

        try:
            from src.utils.market_regime import (
                MarketRegimeClassifier,
                load_spy_vix_data,
            )
            import plotly.graph_objects as go
            from plotly.subplots import make_subplots

            spy_r, vix_r = load_spy_vix_data(
                str(start_date), str(end_date), cache=get_ticker_cache(), offline=True
            )
            if spy_r is None or spy_r.empty:
                with st.spinner("Downloading SPY/VIX..."):
                    spy_r, vix_r = load_spy_vix_data(
                        str(start_date),
                        str(end_date),
                        cache=get_ticker_cache(),
                        offline=False,
                    )

            if spy_r is not None and not spy_r.empty:
                clf = MarketRegimeClassifier(spy_r, vix_r)
                ctx = clf.get_context_series()

                STAGE_COLOR = {
                    "STAGE_1": "#00c853",
                    "STAGE_2": "#ffd600",
                    "STAGE_3": "#ff6d00",
                    "STAGE_4": "#d50000",
                }
                STAGE_LABEL = {
                    "STAGE_1": "Stage 1 - Bull (trades permitidos)",
                    "STAGE_2": "Stage 2 - Consolidación (trades permitidos)",
                    "STAGE_3": "Stage 3 - Distribución (BLOQUEADO)",
                    "STAGE_4": "Stage 4 - Bear (BLOQUEADO)",
                }

                total_days = len(ctx)
                sc = ctx["market_stage"].value_counts()
                tradeable = sc.get("STAGE_1", 0) + sc.get("STAGE_2", 0)
                blocked = sc.get("STAGE_3", 0) + sc.get("STAGE_4", 0)

                sm1, sm2, sm3, sm4, sm5 = st.columns(5)
                sm1.metric("Total days", total_days)
                sm2.metric(
                    "Stage 1 Bull",
                    sc.get("STAGE_1", 0),
                    f"{sc.get('STAGE_1', 0) / total_days * 100:.0f}%",
                )
                sm3.metric(
                    "Stage 2 Neutral",
                    sc.get("STAGE_2", 0),
                    f"{sc.get('STAGE_2', 0) / total_days * 100:.0f}%",
                )
                sm4.metric(
                    "Stage 3 Dist.",
                    sc.get("STAGE_3", 0),
                    f"{sc.get('STAGE_3', 0) / total_days * 100:.0f}%",
                )
                sm5.metric(
                    "Stage 4 Bear",
                    sc.get("STAGE_4", 0),
                    f"{sc.get('STAGE_4', 0) / total_days * 100:.0f}%",
                )

                tradeable_pct = tradeable / total_days * 100 if total_days else 0
                st.progress(
                    int(tradeable_pct),
                    text=f"Días operables: {tradeable_pct:.0f}%  ({tradeable} abiertos / {blocked} bloqueados)",
                )
                
                # Dynamic interpretation
                st.markdown("#### 📊 Interpretación del Período")
                if tradeable_pct >= 70:
                    st.success(f"""
                    ✅ **Período muy favorable** ({tradeable_pct:.0f}% días operables)
                    
                    El mercado estuvo en condiciones óptimas la mayoría del tiempo.
                    Stage 1 dominante indica tendencia alcista sostenida.
                    Excelente ambiente para estrategias de momentum.
                    """)
                elif tradeable_pct >= 50:
                    st.info(f"""
                    ⚖️ **Período mixto** ({tradeable_pct:.0f}% días operables)
                    
                    Mercado alternó entre fases operables y bloqueadas.
                    Requiere selectividad — el sistema filtró días riesgosos.
                    Ambiente normal para swing trading.
                    """)
                else:
                    st.warning(f"""
                    ⚠️ **Período desafiante** ({tradeable_pct:.0f}% días operables)
                    
                    El mercado estuvo en Stage 3/4 más de la mitad del tiempo.
                    Alta volatilidad o tendencia bajista dominante.
                    El filtro protegió capital evitando entradas peligrosas.
                    """)

                st.markdown("---")

                fig = make_subplots(
                    rows=3,
                    cols=1,
                    shared_xaxes=True,
                    row_heights=[0.55, 0.25, 0.20],
                    vertical_spacing=0.04,
                    subplot_titles=(
                        "Precio SPY + Stage de Mercado",
                        "VIX (Volatilidad Implícita)",
                        "Volatilidad (promedio 20d del rango %)",
                    ),
                )

                fig.add_trace(
                    go.Scatter(
                        x=spy_r.index,
                        y=spy_r["close"],
                        name="SPY",
                        line=dict(color="white", width=1.5),
                    ),
                    row=1,
                    col=1,
                )
                fig.add_trace(
                    go.Scatter(
                        x=clf.spy.index,
                        y=clf.spy["sma50"],
                        name="SMA50",
                        line=dict(color="#42a5f5", width=1, dash="dot"),
                    ),
                    row=1,
                    col=1,
                )
                fig.add_trace(
                    go.Scatter(
                        x=clf.spy.index,
                        y=clf.spy["sma200"],
                        name="SMA200",
                        line=dict(color="#ef5350", width=1, dash="dot"),
                    ),
                    row=1,
                    col=1,
                )

                for stage, color in STAGE_COLOR.items():
                    mask = ctx["market_stage"] == stage
                    if not mask.any():
                        continue
                    diff = mask.astype(int).diff().fillna(0)
                    starts = spy_r.index[diff == 1].tolist()
                    if mask.iloc[0]:
                        starts.insert(0, spy_r.index[0])
                    ends = spy_r.index[diff == -1].tolist()
                    if mask.iloc[-1]:
                        ends.append(spy_r.index[-1])
                    for s, e in zip(starts, ends):
                        fig.add_vrect(
                            x0=s,
                            x1=e,
                            fillcolor=color,
                            opacity=0.13,
                            layer="below",
                            line_width=0,
                            row=1,
                            col=1,
                        )

                if vix_r is not None and not vix_r.empty:
                    vx = vix_r.reindex(spy_r.index, method="ffill")
                    fig.add_trace(
                        go.Scatter(
                            x=vx.index,
                            y=vx["close"],
                            name="VIX",
                            line=dict(color="#ff9800", width=1.5),
                            fill="tozeroy",
                            fillcolor="rgba(255,152,0,0.08)",
                        ),
                        row=2,
                        col=1,
                    )
                    fig.add_hline(
                        y=20,
                        line_dash="dash",
                        line_color="#ffd600",
                        annotation_text="VIX 20 (trigger Stage 3)",
                        annotation_position="top left",
                        row=2,
                        col=1,
                    )
                    fig.add_hline(
                        y=25,
                        line_dash="dash",
                        line_color="#ef5350",
                        annotation_text="VIX 25 (límite absoluto)",
                        annotation_position="top left",
                        row=2,
                        col=1,
                    )

                fig.add_trace(
                    go.Scatter(
                        x=clf.spy.index,
                        y=clf.spy["volatility_20"],
                        name="Vol 20d",
                        line=dict(color="#ce93d8", width=1.2),
                        fill="tozeroy",
                        fillcolor="rgba(206,147,216,0.08)",
                    ),
                    row=3,
                    col=1,
                )
                fig.add_hline(
                    y=1.5,
                    line_dash="dash",
                    line_color="#ffd600",
                    annotation_text="Umbral 1.5%",
                    annotation_position="top left",
                    row=3,
                    col=1,
                )

                fig.update_layout(
                    template="plotly_dark",
                    height=700,
                    margin=dict(l=20, r=20, t=60, b=20),
                    legend=dict(
                        orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1
                    ),
                    hovermode="x unified",
                )
                fig.update_yaxes(title_text="Precio ($)", row=1, col=1)
                fig.update_yaxes(title_text="VIX", row=2, col=1)
                fig.update_yaxes(title_text="Rango (%)", row=3, col=1)
                st.plotly_chart(fig, use_container_width=True)

                lc1, lc2, lc3, lc4 = st.columns(4)
                lc1.success("Stage 1 - Bull: entradas completas")
                lc2.warning("Stage 2 - Consolidación: selectivo (75% size)")
                lc3.error("Stage 3 - Distribución: BLOQUEADO (2-de-3)")
                lc4.error("Stage 4 - Bear: BLOQUEADO")

                st.markdown("---")
                st.subheader("Transiciones de Stage")
                st.caption(
                    "Cada vez que el régimen de mercado cambió durante el período del backtest."
                )
                transitions = []
                prev = None
                for date, row_ctx in ctx.iterrows():
                    curr = row_ctx["market_stage"]
                    if curr != prev:
                        transitions.append(
                            {
                                "Fecha": date.strftime("%Y-%m-%d"),
                                "Nuevo Stage": STAGE_LABEL.get(curr, curr),
                                "SPY": f"${row_ctx['spy_price']:.2f}",
                                "VIX": f"{row_ctx['vix_value']:.1f}",
                                "Vol 20d": f"{row_ctx['market_volatility']:.2f}%",
                                "Trades Permitidos": "✅ Sí"
                                if curr in ["STAGE_1", "STAGE_2"]
                                else "🚫 No",
                            }
                        )
                        prev = curr
                if transitions:
                    trans_df = pd.DataFrame(transitions)
                    st.dataframe(trans_df, use_container_width=True)
                    
                    # Add educational context based on actual transitions
                    st.markdown("#### 💡 Análisis de Transiciones")
                    
                    num_transitions = len(transitions)
                    blocked_transitions = len([t for t in transitions if "STAGE_3" in t["Nuevo Stage"] or "STAGE_4" in t["Nuevo Stage"]])
                    
                    if num_transitions <= 5:
                        st.success(f"""
                        ✅ **Mercado estable** ({num_transitions} cambios de regime)
                        
                        Pocas transiciones indican un mercado con tendencia clara y sostenida.
                        Ideal para estrategias direccionales como momentum.
                        """)
                    elif num_transitions <= 15:
                        st.info(f"""
                        ⚖️ **Mercado normal** ({num_transitions} cambios de regime)
                        
                        Alternancia típica entre fases alcistas y consolidación.
                        El sistema se adapta automáticamente al cambio de condiciones.
                        """)
                    else:
                        st.warning(f"""
                        ⚠️ **Mercado volátil** ({num_transitions} cambios de regime)
                        
                        Muchas transiciones indican inestabilidad y cambios bruscos.
                        El filtro de regime es crítico en estos períodos.
                        """)
                    
                    if blocked_transitions > 0:
                        st.error(f"""
                        🛡️ **Protección activa:** {blocked_transitions} transiciones a Stage 3/4 bloqueadas
                        
                        El sistema detectó condiciones peligrosas y bloqueó nuevas entradas,
                        protegiendo tu capital de drawdowns evitables.
                        """)
            else:
                st.warning(
                    "No se pudo cargar datos de SPY. Ejecuta un backtest primero para poblar el cache."
                )
        except Exception as e:
            st.error(f"Market Regime tab error: {e}")
            import traceback

            st.code(traceback.format_exc())

    # =========================================================================
    # TAB 7: TRADE ANATOMY - EDUCATIONAL MODE
    # =========================================================================
    with t7:
        st.markdown("## 🎓 Anatomía del Trade - Modo Educativo")
        st.caption("Aprende cómo funciona el sistema analizando trades reales paso a paso")
        
        if not grouped_trades.empty:
            # Trade selector
            st.markdown("### 📍 Selecciona un Trade para Analizar")
            
            # Create dropdown with most interesting trades
            interesting_trades = grouped_trades.copy()
            interesting_trades['description'] = (
                interesting_trades['ticker'] + " | " +
                interesting_trades['entry_date'].astype(str) + " → " +
                interesting_trades['final_exit_date'].astype(str) + " | PnL: $" +
                interesting_trades['total_pnl'].round(2).astype(str)
            )
            
            # Sort by absolute PnL to show most impactful trades
            interesting_trades['abs_pnl'] = interesting_trades['total_pnl'].abs()
            interesting_trades = interesting_trades.sort_values('abs_pnl', ascending=False)
            
            selected_trade_desc = st.selectbox(
                "Trade:",
                interesting_trades['description'].tolist(),
                help="Ordenados por impacto (PnL absoluto)"
            )
            
            # Get the selected trade
            selected_idx = interesting_trades[
                interesting_trades['description'] == selected_trade_desc
            ].index[0]
            trade = interesting_trades.loc[selected_idx]
            
            # Display trade overview
            st.markdown("---")
            outcome_emoji = "✅" if trade['total_pnl'] > 0 else "❌"
            st.markdown(f"## {outcome_emoji} {trade['ticker']} - Análisis Completo")
            
            # Key metrics in columns
            m1, m2, m3, m4, m5 = st.columns(5)
            m1.metric("Entrada", f"${trade['entry_price']:.2f}")
            m2.metric("PnL Total", f"${trade['total_pnl']:.2f}")
            m3.metric("Días en Trade", f"{int(trade['hold_days'])}")
            m4.metric("Entry Score", f"{trade.get('entry_score', 0):.2f}")
            m5.metric("R-Multiple", f"{trade.get('r_multiple', 0):+.2f}R" if 'r_multiple' in trade else "N/A")
            
            # PHASE 1: PRE-ENTRADA
            st.markdown("---")
            st.markdown("### 🔍 FASE 1: Pre-Entrada (Screening)")
            
            col_pre1, col_pre2 = st.columns(2)
            
            with col_pre1:
                st.markdown("#### ¿Qué buscaba el sistema?")
                st.info(f"""
                **Patrón:** {trade.get('pattern_type', 'N/A')}
                
                **Criterios de selección:**
                1. **Base consolidada** - Precio entre soporte y resistencia
                2. **AVWAP por debajo** - Precio no sobreextendido
                3. **Volumen institucional** - Detecta acumulación
                4. **Momentum relativo** - RS Percentile: {trade.get('rs_percentile', 0):.0f}
                """)
                
            with col_pre2:
                st.markdown("#### Filtros que Pasó")
                # Show that this trade passed all filters
                st.success(f"""
                ✅ **Tier 1 (Market Safety)** - Régimen de mercado favorable
                ✅ **Tier 2 (Quality)** - Calidad técnica suficiente
                ✅ **Tier 3 (Risk)** - Risk/Reward aceptable
                
                **Entry Score:** {trade.get('entry_score', 0):.2f}/1.0
                """)
                
                if trade.get('entry_score', 0) >= 0.7:
                    st.write("🔥 **Score alto** - Setup de muy alta calidad")
                elif trade.get('entry_score', 0) >= 0.4:
                    st.write("⚠️ **Score medio** - Setup aceptable pero no ideal")
                else:
                    st.write("⚡ **Score bajo** - Setup marginal, riesgo elevado")
            
            # PHASE 2: ENTRADA
            st.markdown("---")
            st.markdown("### 🚀 FASE 2: Entrada (Trigger)")
            
            col_ent1, col_ent2 = st.columns(2)
            
            with col_ent1:
                st.markdown("#### El Momento de Entrada")
                entry_date_str = trade['entry_date'].strftime('%Y-%m-%d') if hasattr(trade['entry_date'], 'strftime') else str(trade['entry_date'])
                st.write(f"""
                **Fecha:** {entry_date_str}
                **Precio:** ${trade['entry_price']:.2f}
                **Shares:** {int(trade.get('total_shares', 0))}
                **Capital Arriesgado:** ${int(trade.get('total_shares', 0) * trade['entry_price']):.0f}
                
                **Trigger:**
                El precio rompió por encima del nivel de resistencia de la base consolidada,
                confirmando que hay compradores institucionales entrando.
                """)
                
            with col_ent2:
                st.markdown("#### Position Sizing Dinámico")
                shares = int(trade.get('total_shares', 0))
                entry_price = trade['entry_price']
                position_value = shares * entry_price
                
                st.write(f"""
                **Cálculo de posición:**
                * Shares: {shares}
                * Precio entrada: ${entry_price:.2f}
                * Valor posición: ${position_value:.2f}
                
                El sistema ajusta el tamaño basado en:
                1. **Riesgo fijo ($)** - Define cuánto perder si salta el stop
                2. **Distancia al stop** - Más lejos = menos shares
                3. **Régimen de mercado** - Stage 2 = 75% size
                """)
            
            # PHASE 3: GESTIÓN
            st.markdown("---")
            st.markdown("### 📊 FASE 3: Gestión del Trade")
            
            col_gest1, col_gest2 = st.columns(2)
            
            with col_gest1:
                st.markdown("#### Sistema de Salidas Escalonadas")
                
                # Parse exit phases if available
                exit_info = trade.get('exit_phases', 'N/A')
                st.write(f"""
                **Fases de salida:** {exit_info}
                
                El sistema usa **Take Profit dinámico** en 3 fases:
                * **TP1 (33%)** - Toma ganancias tempranas, asegura capital
                * **TP2 (33%)** - Captura el movimiento medio
                * **TP3 (34%)** - Permite correr ganadores
                
                Cada fase tiene su propio trailing stop para proteger ganancias.
                """)
                
            with col_gest2:
                st.markdown("#### ¿Qué Pasó en Este Trade?")
                
                if trade['total_pnl'] > 0:
                    st.success(f"""
                    ✅ **Trade Ganador** (+${trade['total_pnl']:.2f})
                    
                    El precio continuó en la dirección esperada y el sistema
                    ejecutó las salidas según el plan. Las múltiples fases
                    permitieron capturar diferentes partes del movimiento.
                    """)
                else:
                    st.error(f"""
                    ❌ **Trade Perdedor** (${trade['total_pnl']:.2f})
                    
                    El precio no se movió como se esperaba. El stop loss
                    protegió el capital al limitar la pérdida a un nivel
                    predefinido. Es parte normal del trading.
                    """)
            
            # PHASE 4: POST-MORTEM
            st.markdown("---")
            st.markdown("### 🔬 FASE 4: Post-Mortem (Aprendizaje)")
            
            col_pm1, col_pm2 = st.columns(2)
            
            with col_pm1:
                st.markdown("#### Métricas de Performance")
                
                win_rate_pct = (grouped_trades['total_pnl'] > 0).sum() / len(grouped_trades) * 100
                avg_win = grouped_trades[grouped_trades['total_pnl'] > 0]['total_pnl'].mean() if (grouped_trades['total_pnl'] > 0).any() else 0
                avg_loss = grouped_trades[grouped_trades['total_pnl'] < 0]['total_pnl'].mean() if (grouped_trades['total_pnl'] < 0).any() else 0
                
                st.info(f"""
                **Contexto del sistema completo:**
                * Win Rate: {win_rate_pct:.1f}%
                * Avg Win: ${avg_win:.2f}
                * Avg Loss: ${avg_loss:.2f}
                * Total Trades: {len(grouped_trades)}
                
                Este trade {'contribuyó positivamente' if trade['total_pnl'] > 0 else 'fue parte del costo de hacer negocios'}.
                """)
                
            with col_pm2:
                st.markdown("#### Lecciones Clave")
                
                # Dynamic lessons based on trade characteristics
                lessons = []
                
                if trade.get('entry_score', 0) >= 0.7 and trade['total_pnl'] > 0:
                    lessons.append("✅ **Score alto + ganador** - Sistema funcionó como esperado")
                elif trade.get('entry_score', 0) < 0.4 and trade['total_pnl'] < 0:
                    lessons.append("⚠️ **Score bajo + perdedor** - Confirmación de que scores bajos son más riesgosos")
                elif trade.get('entry_score', 0) >= 0.7 and trade['total_pnl'] < 0:
                    lessons.append("📚 **Score alto pero perdió** - Incluso buenos setups fallan (probabilidades)")
                elif trade.get('entry_score', 0) < 0.4 and trade['total_pnl'] > 0:
                    lessons.append("🎲 **Score bajo pero ganó** - Caso fortuito, no replicable")
                
                if trade['hold_days'] < 3:
                    lessons.append("⚡ **Trade corto** - Sistema detectó debilidad y cortó rápido")
                elif trade['hold_days'] > 10:
                    lessons.append("🏃 **Trade extendido** - El momentum se mantuvo varios días")
                
                if trade.get('rs_percentile', 0) >= 80:
                    lessons.append("🚀 **RS alto** - Líder relativo del mercado (IBD style)")
                
                for lesson in lessons:
                    st.write(lesson)
                
                if not lessons:
                    st.write("📊 Trade con características estándar del sistema")
            
            # EDUCATIONAL CONCEPTS
            st.markdown("---")
            st.markdown("### 📚 Conceptos Clave del Sistema")
            
            edu_tabs = st.tabs([
                "Triad Protocol",
                "Entry Score",
                "R-Multiple",
                "Market Regime",
                "Position Sizing"
            ])
            
            with edu_tabs[0]:
                st.markdown("""
                #### 🔱 Triad Protocol
                
                El sistema busca la confluencia de **3 niveles técnicos**:
                
                **1. Base (Consolidación)**
                * Zona de precio donde la acción se consolida
                * Identifica soporte/resistencia
                * Mínimo 5 días de formación
                
                **2. AVWAP (Anchored VWAP)**
                * Precio promedio ponderado desde el último pivot
                * Muestra dónde están posicionados los institucionales
                * Entrada ideal: precio cerca pero no muy por encima
                
                **3. VWAP (Daily)**
                * Precio justo del día actual
                * Referencia intraday para entradas precisas
                
                **¿Por qué funciona?**
                Cuando precio rompe la base Y está cerca de AVWAP Y supera VWAP,
                es señal de que institucionales están comprando activamente.
                """)
                
            with edu_tabs[1]:
                st.markdown("""
                #### 🎯 Entry Score v2
                
                Califica la **calidad del setup** de 0.0 a 1.0 combinando:
                
                **Componentes (ponderados):**
                * **Triad quality** (30%) - ¿Qué tan limpia está la estructura?
                * **Volume confirmation** (25%) - ¿Hay volumen institucional?
                * **RS Percentile** (25%) - ¿Es líder relativo?
                * **Volatility & momentum** (20%) - ¿Tiene fuerza el movimiento?
                
                **Interpretación:**
                * **≥0.7** - Setup de alta calidad, mayor probabilidad de éxito
                * **0.4-0.7** - Setup aceptable, riesgo moderado
                * **<0.4** - Setup marginal, alta probabilidad de fallo
                
                **Uso en producción:**
                Puedes filtrar trades por score mínimo para mejorar consistencia.
                """)
                
            with edu_tabs[2]:
                st.markdown("""
                #### 📏 R-Multiple (Risk Units)
                
                Mide **cuántas veces tu riesgo inicial ganaste o perdiste**.
                
                **Ejemplo:**
                * Entrada: $100, Stop: $95 → Riesgo = $5
                * Si sales en $110 → Ganaste $10 → **+2R**
                * Si salta stop en $95 → Perdiste $5 → **-1R**
                
                **¿Por qué es importante?**
                * **Normaliza trades** - Compara manzanas con manzanas
                * **Win Rate ≠ Profit** - Puedes ganar 40% de trades y ser rentable con +3R avg
                * **Objetivo:** Avg R-Multiple > +0.5R para rentabilidad sostenida
                
                **Estrategias ganadoras:**
                * Corta perdedores rápido (-1R)
                * Deja correr ganadores (+2R, +3R, +5R)
                """)
                
            with edu_tabs[3]:
                st.markdown("""
                #### 🌊 Market Regime Filter
                
                El sistema **adapta su agresividad** según el estado del mercado (SPY):
                
                **Stage 1 - Bull Trend** 🟢
                * SPY > SMA50 & SMA200
                * Momentum fuerte
                * **Acción:** Entradas completas (100% size)
                
                **Stage 2 - Consolidation** 🟡
                * SPY saludable pero sin momentum claro
                * **Acción:** Entradas reducidas (75% size)
                
                **Stage 3 - Distribution** 🔴
                * 2 de 3: SPY < SMA50, Vol > 1.5%, VIX > 20
                * Dinero institucional saliendo
                * **Acción:** BLOQUEADO - No nuevas entradas
                
                **Stage 4 - Bear Trend** ⛔
                * SPY < SMA200 & SMA50
                * Tendencia bajista confirmada
                * **Acción:** BLOQUEADO
                
                **Filosofía:**
                No luches contra la marea. El mejor trade es el que no haces en mal ambiente.
                """)
                
            with edu_tabs[4]:
                st.markdown("""
                #### 💰 Position Sizing Dinámico
                
                Cada trade tiene tamaño calculado para **riesgo fijo en dólares**.
                
                **Fórmula:**
                ```
                Shares = Risk_$ / (Entry - Stop_Loss)
                ```
                
                **Ejemplo práctico:**
                * Riesgo fijo: $100 por trade
                * Entry: $50, Stop: $48
                * Distancia: $2
                * Shares = $100 / $2 = **50 shares**
                
                **Ventajas:**
                1. **Riesgo consistente** - Cada trade arriesga lo mismo
                2. **Adaptativo** - Stops más anchos = menos shares
                3. **Protección de cuenta** - No apuestas todo en un trade
                
                **Ajustes por régimen:**
                * Stage 1 (Bull): 100% del tamaño calculado
                * Stage 2 (Consolidation): 75% del tamaño
                * Stage 3/4: No entries
                """)
            
            # LIVE EXECUTION TIMELINE
            st.markdown("---")
            st.markdown("### 📅 Timeline de Ejecución")
            
            # Get individual exits from original trade_df if available
            if 'trade_df_for_grouper' in dir() and not trade_df_for_grouper.empty:
                # Find all partial exits for this trade
                partial_exits = trade_df_for_grouper[
                    (trade_df_for_grouper['ticker'] == trade['ticker']) &
                    (trade_df_for_grouper['entry_date'] == trade['entry_date'])
                ].copy()
                
                if not partial_exits.empty:
                    partial_exits = partial_exits.sort_values('exit_date')
                    
                    timeline_data = []
                    timeline_data.append({
                        "Evento": "🟢 ENTRADA",
                        "Fecha": entry_date_str,
                        "Precio": f"${trade['entry_price']:.2f}",
                        "Shares": f"{int(trade['total_shares'])}",
                        "PnL": "-",
                        "Notas": "Apertura de posición completa"
                    })
                    
                    for idx, exit_row in partial_exits.iterrows():
                        exit_date_str = exit_row['exit_date'].strftime('%Y-%m-%d') if hasattr(exit_row['exit_date'], 'strftime') else str(exit_row['exit_date'])
                        exit_price = exit_row.get('exit_price', 0)
                        pnl = exit_row.get('pnl', 0)
                        shares_exited = exit_row.get('shares', 0)
                        exit_reason = exit_row.get('exit_reason', 'N/A')
                        
                        emoji = "🎯" if "TP" in str(exit_reason) else "🛑" if pnl < 0 else "📤"
                        
                        timeline_data.append({
                            "Evento": f"{emoji} SALIDA",
                            "Fecha": exit_date_str,
                            "Precio": f"${exit_price:.2f}",
                            "Shares": f"{int(shares_exited)}",
                            "PnL": f"${pnl:.2f}",
                            "Notas": str(exit_reason)
                        })
                    
                    timeline_df = pd.DataFrame(timeline_data)
                    st.dataframe(timeline_df, use_container_width=True, hide_index=True)
                else:
                    st.info("Timeline detallado no disponible para este trade")
            
            # KEY TAKEAWAYS
            st.markdown("---")
            st.markdown("### 💡 Conclusiones & Takeaways")
            
            final_col1, final_col2 = st.columns(2)
            
            with final_col1:
                st.markdown("#### ¿Qué hizo bien el sistema?")
                positives = []
                
                if trade.get('entry_score', 0) >= 0.6:
                    positives.append("✅ Identificó setup de calidad")
                if trade.get('rs_percentile', 0) >= 70:
                    positives.append("✅ Seleccionó líder relativo fuerte")
                if trade['hold_days'] >= 2:
                    positives.append("✅ Dio espacio al trade para desarrollarse")
                if trade['total_pnl'] > 0:
                    positives.append("✅ Ejecutó plan de salida correctamente")
                else:
                    positives.append("✅ Cortó pérdida según plan (gestión de riesgo)")
                
                for p in positives:
                    st.write(p)
            
            with final_col2:
                st.markdown("#### Puntos de Mejora")
                improvements = []
                
                if trade.get('entry_score', 0) < 0.4:
                    improvements.append("⚠️ Entry score bajo - considerar umbral más alto")
                if trade.get('rs_percentile', 0) < 50:
                    improvements.append("⚠️ RS bajo - no era líder de mercado")
                if trade['total_pnl'] < 0 and trade['hold_days'] < 2:
                    improvements.append("⚠️ Stop muy ajustado o entrada prematura")
                if abs(trade['total_pnl']) < 50:
                    improvements.append("⚠️ PnL pequeño - ajustar risk/size o skip setups débiles")
                
                if improvements:
                    for imp in improvements:
                        st.write(imp)
                else:
                    st.success("✨ Ejecución sólida sin puntos críticos de mejora")
            
            # COMPARISON WITH PEERS
            st.markdown("---")
            st.markdown("### 📊 Comparación con Otros Trades")
            
            comp_col1, comp_col2, comp_col3 = st.columns(3)
            
            with comp_col1:
                st.markdown("#### Por PnL")
                rank_pnl = (grouped_trades['total_pnl'] >= trade['total_pnl']).sum()
                st.metric(
                    "Ranking",
                    f"{rank_pnl} / {len(grouped_trades)}",
                    f"Top {rank_pnl/len(grouped_trades)*100:.0f}%"
                )
                
            with comp_col2:
                st.markdown("#### Por Entry Score")
                if 'entry_score' in grouped_trades.columns:
                    rank_score = (grouped_trades['entry_score'] >= trade.get('entry_score', 0)).sum()
                    st.metric(
                        "Ranking",
                        f"{rank_score} / {len(grouped_trades)}",
                        f"Top {rank_score/len(grouped_trades)*100:.0f}%"
                    )
                else:
                    st.write("N/A")
                    
            with comp_col3:
                st.markdown("#### Por Días en Hold")
                rank_hold = (grouped_trades['hold_days'] >= trade['hold_days']).sum()
                st.metric(
                    "Ranking",
                    f"{rank_hold} / {len(grouped_trades)}",
                    f"Top {rank_hold/len(grouped_trades)*100:.0f}%"
                )
            
        else:
            st.info("No hay trades disponibles. Ejecuta un backtest primero.")


else:
    st.info("No backtest results found. Run a backtest to see analytics.")
