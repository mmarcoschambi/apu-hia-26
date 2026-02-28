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


@st.cache_data(ttl=3600, show_spinner=False)
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
):
    from src.backtest.vectorbt_engine_advanced import AdvancedVectorBTEngine

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
    )
    results = engine.run_backtest()
    # BUG FIX: Get combined rejection stats from engine, not just filter_engine
    rejection_stats = (
        engine.get_rejection_stats() if hasattr(engine, "get_rejection_stats") else None
    )
    engine.cleanup()
    return results, rejection_stats


ticker_cache = TickerCache()


def get_cache_date_range():
    try:
        cursor = ticker_cache.conn.execute(
            "SELECT MIN(date), MAX(date) FROM ohlcv_cache"
        )
        sqlite_min, sqlite_max = cursor.fetchone()
        if sqlite_min and sqlite_max:
            return datetime.strptime(sqlite_min, "%Y-%m-%d"), datetime.strptime(
                sqlite_max, "%Y-%m-%d"
            )
    except:
        pass
    return datetime(2020, 1, 1), datetime.now()


def paginate_dataframe(df, page_size=20, key_prefix="df", **kwargs):
    use_container_width = kwargs.pop("use_container_width", True)
    if len(df) <= page_size:
        return st.dataframe(df, use_container_width=use_container_width, **kwargs)
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
        df.iloc[start_idx:end_idx], use_container_width=use_container_width, **kwargs
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
):
    progress_bar = st.progress(0)
    status_text = st.empty()
    status_text.markdown("**Running VectorBT Engine**...")
    try:
        if tickers_list:
            universe = tickers_list
        else:
            import sqlite3

            conn = sqlite3.connect("./data/ticker_cache.db")
            selection_start, selection_end = str(start_date), str(end_date)
            min_required_days = 100
            if max_symbols == 0:
                query = "SELECT ticker FROM ohlcv_cache WHERE date BETWEEN ? AND ? GROUP BY ticker HAVING COUNT(*) >= ? ORDER BY ticker"
                cursor = conn.execute(
                    query, (selection_start, selection_end, min_required_days)
                )
            else:
                query = "SELECT ticker, AVG(dollar_volume) as avg_dv FROM ohlcv_cache WHERE date BETWEEN ? AND ? GROUP BY ticker HAVING COUNT(*) >= ? ORDER BY avg_dv DESC LIMIT ?"
                cursor = conn.execute(
                    query,
                    (selection_start, selection_end, min_required_days, max_symbols),
                )
            universe = [row[0] for row in cursor.fetchall()]
            conn.close()
        if not universe:
            raise ValueError("No tickers found.")
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
        )
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
                }
            )
            output_df.to_csv("outputs/backtests/backtest_results.csv", index=False)
            # Also save full enriched trades for derive_tier2_filters.py
            trades.to_csv("outputs/backtests/complete_trades_clean.csv", index=False)
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
    win_rate = (
        metrics_dict.get("win_rate", 0) * 100
        if metrics_dict.get("win_rate", 0) < 1
        else metrics_dict.get("win_rate", 0)
    )
    pf = metrics_dict.get("profit_factor", 0)
    max_dd = (
        abs(metrics_dict.get("max_drawdown", 0)) * 100
        if abs(metrics_dict.get("max_drawdown", 0)) < 1
        else abs(metrics_dict.get("max_drawdown", 0))
    )
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

    t1, t2, t3, t4, t5 = st.tabs(
        ["Performance", "Trade Log", "QuantStats", "Diagnostics", "Insights"]
    )

    # --- Fetch Benchmark Data ---
    @st.cache_data(ttl=3600)
    def get_benchmark_returns(ticker, start, end):
        try:
            from src.data.market_data import MarketDataProvider

            provider = MarketDataProvider()
            # Convert dates to string for provider
            s_str = (
                start.strftime("%Y-%m-%d")
                if isinstance(start, datetime)
                else str(start)
            )
            e_str = end.strftime("%Y-%m-%d") if isinstance(end, datetime) else str(end)

            # Try to get from provider
            df = provider.get_daily_data(ticker, start_date=s_str, end_date=e_str)
            if df.empty:
                # Fallback to yfinance directly
                import yfinance as yf

                df = yf.download(ticker, start=s_str, end=e_str, progress=False)

            if not df.empty:
                if "Close" in df.columns:
                    return df["Close"].pct_change().fillna(0)
                elif "close" in df.columns:
                    return df["close"].pct_change().fillna(0)
        except Exception as e:
            st.error(f"Error fetching benchmark: {e}")
        return pd.Series()

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
                qs_col1, qs_col2, qs_col3, qs_col4 = st.columns(4)

                with qs_col1:
                    st.markdown("**Risk-Adjusted**")
                    sharpe = qs_metrics.get("sharpe_ratio", 0)
                    sortino = qs_metrics.get("sortino_ratio", 0)
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
                        ]
                    )

                with qs_col2:
                    st.markdown("**Returns**")
                    total_ret = qs_metrics.get("total_return", 0)
                    max_dd = qs_metrics.get("max_drawdown", 0)
                    render_metric_cards(
                        [
                            {
                                "label": "Return",
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
                    st.markdown("**Benchmark Alpha**")
                    alpha = qs_metrics.get("alpha", 0)
                    beta = qs_metrics.get("beta", 0)
                    render_metric_cards(
                        [
                            {
                                "label": f"Alpha vs {benchmark_ticker}",
                                "value": f"{alpha:.2f}" if alpha is not None else "N/A",
                            },
                            {
                                "label": f"Beta vs {benchmark_ticker}",
                                "value": f"{beta:.2f}" if beta is not None else "N/A",
                            },
                        ]
                    )

                with qs_col4:
                    st.markdown("**Outperformance**")
                    excess = qs_metrics.get("excess_return", 0)
                    info_ratio = qs_metrics.get("information_ratio", 0)
                    render_metric_cards(
                        [
                            {
                                "label": "Excess Return",
                                "value": f"{excess * 100:+.2f}%"
                                if excess is not None
                                else "N/A",
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
            ]
            if has_r:
                show_cols.append("r_multiple")
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
            else:
                display_df = display_source[show_cols].sort_values(
                    "final_exit_date", ascending=False
                )
        else:
            # Partial exits view
            if quick_sort == "Latest First":
                display_df = df.sort_values("exit_date", ascending=False)
            elif quick_sort == "Oldest First":
                display_df = df.sort_values("exit_date", ascending=True)
            elif quick_sort == "Top Winners ($)":
                display_df = df.sort_values("pnl", ascending=False)
            elif quick_sort == "Top Losers ($)":
                display_df = df.sort_values("pnl", ascending=True)
            else:
                display_df = df.sort_values("exit_date", ascending=False)

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

        # Display dataframe
        if show_all:
            st.dataframe(display_df, use_container_width=True, height=600)
        else:
            paginate_dataframe(display_df, key_prefix="trades_log")

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

        if not grouped_trades.empty and not benchmark_returns.empty:
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
            monthly_ret = qs.stats.monthly_returns(strat_returns) * 100
            # Format for display
            st.dataframe(
                monthly_ret.style.background_gradient(cmap="RdYlGn", axis=None).format(
                    "{:.2f}%"
                ),
                use_container_width=True,
            )

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
        else:
            st.info(
                "Run backtest and ensure benchmark data is available for comparison."
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
    with t5:
        st.header("Trading System Configuration")

        col_i1, col_i2 = st.columns(2)

        with col_i1:
            st.markdown("**Tier 1: Strategy (THOR Optimized)**")
            st.info(
                f"TP1: Sell {_t1.get('tp1_pct', 0) * 100:.0f}% at {_t1.get('tp1_r', 0)}R"
            )
            st.info(
                f"TP2: Sell {_t1.get('tp2_pct', 0) * 100:.0f}% at {_t1.get('tp2_r', 0)}R"
            )
            st.info(
                f"Runner: Hold {_t1.get('runner_pct', 0) * 100:.0f}% with trailing SMA20"
            )
            st.info(
                f"Max Stop: {_t1.get('max_stop_pct', 0) * 100:.1f}% | Risk: ${_t1.get('risk_dollars', 0)}/trade"
            )

            st.markdown("**Tier 2: Filters (Statistically Derived)**")
            st.info(
                f"Min RVOL: {_t2.get('min_rvol', 0)}x | Max Dist SMA20: {_t2.get('max_dist_sma20', 0)}%"
            )
            st.info(
                f"Min ADR: {_t2.get('min_adr', 0)}% | Min $Volume: ${_t2.get('min_dollar_volume', 0):,.0f}"
            )

        with col_i2:
            st.markdown("**Tier 3: Risk Management (Fixed)**")
            st.info(
                f"RVOL Danger ({_t3.get('rvol_danger', 0)}x): Size to {_t3.get('rvol_danger_size', 0) * 100:.0f}%"
            )
            st.info(
                f"RVOL Warning ({_t3.get('rvol_warning', 0)}x): Size to {_t3.get('rvol_warning_size', 0) * 100:.0f}%"
            )
            st.info(
                f"Max Exposure: {_t3.get('max_exposure_pct', 0) * 100:.0f}% | Max Position: {_t3.get('max_position_pct', 0) * 100:.0f}%"
            )

            st.markdown("**Market Regime**")
            st.info(
                f"SPY > SMA50: {'Required' if _mr.get('require_spy_above_sma50') else 'Not Required'}"
            )
            st.info(f"Max VIX: {_mr.get('max_vix', 40)}")

            st.markdown("**THOR Optimization Results**")
            st.success(
                f"Validation Sharpe: {_perf.get('sharpe_ratio', 0):.2f} | "
                f"Win Rate: {_perf.get('win_rate_pct', 0):.2f}% | "
                f"Trades: {_perf.get('total_trades', 0)} | "
                f"Return: {_perf.get('total_return_pct', 0):.2f}%"
            )
else:
    st.info("No backtest results found. Run a backtest to see analytics.")
