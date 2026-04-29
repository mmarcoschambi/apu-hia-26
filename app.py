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
# matplotlib importado de forma lazy (evita 200-500ms en cold start de Streamlit)
# Se importa dentro de las funciones que lo usan (ver generate_pdf_report, etc.)


# Fix for Linux font issues — import lazy here too
def _init_matplotlib():
    """Inicializa matplotlib de forma lazy (evita overhead en cold start)."""
    import matplotlib.pyplot as plt

    plt.rcParams["font.family"] = "sans-serif"
    plt.rcParams["font.sans-serif"] = [
        "DejaVu Sans",
        "Liberation Sans",
        "Bitstream Vera Sans",
        "Arial",
    ]
    return plt


# No llamar _init_matplotlib() aqui: mantener import realmente lazy.

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

# ──────────────────────────────────────────────────────────────────────
# DASHBOARD UI LAYER — Fase 1-4: Ingesta robusta, estado aislado,
# vista filtrada y caché para multi-activo/multi-patrón
# ──────────────────────────────────────────────────────────────────────
from src.ui.dashboard_data_adapter import DashboardDataAdapter, get_adapter
from src.ui.dashboard_v2_adapter import get_dashboard_v2_adapter
from src.ui.session_state import DashboardState, ALL_LABEL
from src.ui.filtered_view import get_filtered_trades, get_scope_label, get_scope_info
from src.ui.dashboard_cache import (
    DashboardCache,
    cached_load_optimizer_config,
    cached_load_trades,
    cached_build_index,
)

# --- YAML COMBO CONFIG LOADER (Fase 2: Centralized config) ---
try:
    from config.combo_loader import (
        load_combo_configs,
        get_combo_by_name,
        get_go_combos,
        ComboConfig,
    )

    _yaml_combos = load_combo_configs()
    _yaml_go_combos = get_go_combos(_yaml_combos)
    _yaml_combos_available = True
except Exception as _yce:
    _yaml_combos = []
    _yaml_go_combos = []
    _yaml_combos_available = False

# --- LOAD COMBO RANKING (optional production selector) ---
_combo_top5_path = Path("config/combos/top5.json")
try:
    with open(_combo_top5_path, "r", encoding="utf-8") as _cf:
        _combo_top5 = json.load(_cf)
    if not isinstance(_combo_top5, list):
        _combo_top5 = []
except Exception:
    _combo_top5 = []


def _normalize_combo_config(raw: dict) -> dict:
    """Normalize combo JSON keys to match app.py expected structure."""
    cfg = dict(raw)
    # tier1_exits -> tier1_strategy
    if "tier1_exits" in cfg and "tier1_strategy" not in cfg:
        cfg["tier1_strategy"] = dict(cfg.pop("tier1_exits"))
    # tier3_fixed -> tier3_risk
    if "tier3_fixed" in cfg and "tier3_risk" not in cfg:
        cfg["tier3_risk"] = dict(cfg.pop("tier3_fixed"))
    return cfg


def _convert_yaml_to_production_dict(combo: ComboConfig) -> dict:
    """Convert ComboConfig (YAML) to nested dict structure expected by app.py."""
    # Start with production defaults as baseline
    try:
        base = load_production_config()
    except Exception:
        # Fallback to empty if file missing
        base = {}

    # Map flat YAML fields to nested JSON structure
    return {
        "combo_name": combo.name,
        "status": combo.status,
        "pbo": combo.pbo,
        "wf_sharpe_mean": combo.wf_sharpe_mean,
        "tier1_strategy": {
            **base.get("tier1_strategy", {}),
            "fee_rate": combo.fee_rate,
            "slippage_rate": combo.slippage_rate,
        },
        "tier2_filters": {
            **base.get("tier2_filters", {}),
            "min_rvol": combo.min_rvol,
            "min_adr": combo.min_adr,
            "min_consolidation_days": combo.min_consolidation_days,
            "flat_base_range_pct": combo.flat_base_range_pct,
            "vcp_contraction_threshold": combo.vcp_contraction_threshold,
        },
        "tier3_risk": {
            **base.get("tier3_risk", {}),
            "max_positions": combo.max_positions,
            "max_position_pct": combo.max_position_pct,
            "max_exposure_pct": combo.max_exposure_pct,
        },
        "market_regime": {
            **base.get("market_regime", {}),
            "require_spy_above_sma50": combo.spx_sma_period > 0,
            "max_vix": combo.vix_max,
            "regime_blocked": combo.regime_blocked,
        },
        "scanner": {"name": combo.scanner_filter, "mode": "all"},
        "pattern": {"signal_type": combo.pattern_filter},
    }


def _load_selected_strategy_config() -> dict:
    """Load active strategy config from the selected combo or production fallback."""
    # 1. PRIORITY: YAML validated combos (Fase 2 system)
    selected_yaml = st.session_state.get("active_yaml_combo")
    if _yaml_combos_available and selected_yaml:
        combo = get_combo_by_name(_yaml_combos, selected_yaml, require_go=False)
        if combo:
            return _convert_yaml_to_production_dict(combo)

    # 2. SECONDARY: top5.json (old system)
    selected_label = st.session_state.get("active_combo_label")
    if _combo_top5 and selected_label:
        for combo in _combo_top5:
            label = (
                f"{combo.get('combo', combo.get('combo_name', 'combo'))} "
                f"★ {combo.get('combo_score', combo.get('score', 0.0)):.2f}"
            )
            if label == selected_label:
                export_path = combo.get("export_path")
                if export_path and Path(export_path).exists():
                    try:
                        with open(export_path, "r", encoding="utf-8") as f:
                            raw = json.load(f)
                        return _normalize_combo_config(raw)
                    except Exception:
                        break

    # 3. FALLBACK: production_config.json
    return load_production_config()


# --- LOAD PRODUCTION CONFIG (Single source of truth) ---
_raw_config = _load_selected_strategy_config()
_engine_params = flatten_config(_raw_config)

# Track if a combo is active (for UI gating)
_combo_is_active = _raw_config.get("combo_name") is not None
_combo_source = _raw_config.get("combo_name", "production_config.json")
_combo_screener = _raw_config.get("screener", _raw_config.get("pattern", "N/A"))

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

# ── YAML COMBO PARAMETER INJECTION (Fase 3: Override with active YAML combo) ──
# When a YAML combo is active, its parameters override the defaults/production config
# This ensures the scanner live uses the exact params from the selected combo
# NOTE: _active_yaml_combo is set in sidebar below, use session_state for access here
_active_yaml_combo = None
if _yaml_combos_available and _yaml_go_combos:
    _prev_combo_name = st.session_state.get("active_yaml_combo")
    if _prev_combo_name:
        _active_yaml_combo = get_combo_by_name(_yaml_combos, _prev_combo_name)
        if _active_yaml_combo:
            _yc = _active_yaml_combo  # type: ComboConfig

            # Override tier2 (filters/quality)
            _t2.update(
                {
                    "min_rvol": _yc.min_rvol,
                    "min_adr": _yc.min_adr,
                    "min_consolidation_days": _yc.min_consolidation_days,
                }
            )

            # Override tier3 (risk)
            _t3.update(
                {
                    "max_position_pct": _yc.max_position_pct,
                    "max_exposure_pct": _yc.max_exposure_pct,
                }
            )

            # Override market regime
            _mr.update(
                {
                    "max_vix": _yc.vix_max,
                }
            )

            # Store for scanner integration
            _yaml_combo_params = {
                "fee_rate": _yc.fee_rate,
                "slippage_rate": _yc.slippage_rate,
                "regime_blocked": _yc.regime_blocked,
                "scanner_filter": _yc.scanner_filter,
                "pattern_filter": _yc.pattern_filter,
                "lookback_days": _yc.lookback_days,
                "max_setups": _yc.max_setups,
                "active_combo_name": _yc.name,
            }
        else:
            _yaml_combo_params = {}
    else:
        _yaml_combo_params = {}
else:
    _yaml_combo_params = {}

# --- LOAD VCP CONFIG (separate golden config for VCP pattern) ---
_vcp_config_path = "config/vcp_config.json"
try:
    import json as _json

    with open(_vcp_config_path) as _vf:
        _vcp_raw = _json.load(_vf)
    _vcp_t1 = _vcp_raw.get("tier1_strategy", {})
    _vcp_t2 = _vcp_raw.get("tier2_filters", {})
    _vcp_ve = _vcp_raw.get("vcp_entry", {})
    _vcp_mr = _vcp_raw.get("market_regime", {})
    _vcp_oos = _vcp_raw.get("_oos_validation", {})
    _vcp_available = True
except Exception:
    _vcp_available = False
    _vcp_t1 = _vcp_t2 = _vcp_ve = _vcp_mr = _vcp_oos = {}

# --- BREAKOUT CONFIG ---
try:
    import json as _json_bk

    with open("config/breakout_config.json") as _bkf:
        _bk_raw = _json_bk.load(_bkf)
    _bk_t1 = _bk_raw.get("tier1_strategy", {})
    _bk_t2 = _bk_raw.get("tier2_filters", {})
    _bk_oos = _bk_raw.get("_oos_validation", {})
    _breakout_available = True
except Exception:
    _breakout_available = True  # fallback to production_config
    _bk_t1 = _bk_t2 = _bk_oos = {}

# --- POCKET PIVOT CONFIG ---
try:
    import json as _json_pp

    with open("config/pocket_pivot_config.json") as _ppf:
        _pp_raw = _json_pp.load(_ppf)
    _pp_t1 = _pp_raw.get("tier1_strategy", {})
    _pp_t2 = _pp_raw.get("tier2_filters", {})
    _pp_ve = _pp_raw.get("extra_params", _pp_raw.get("vcp_entry", {}))
    _pp_oos = _pp_raw.get("_oos_validation", {})
    _pp_available = True
except Exception:
    _pp_available = False
    _pp_t1 = _pp_t2 = _pp_ve = _pp_oos = {}

# --- FLAT BASE CONFIG ---
try:
    import json as _json_fb

    with open("config/flat_base_config.json") as _fbf:
        _fb_raw = _json_fb.load(_fbf)
    _fb_t1 = _fb_raw.get("tier1_strategy", {})
    _fb_t2 = _fb_raw.get("tier2_filters", {})
    _fb_ve = _fb_raw.get("extra_params", _fb_raw.get("vcp_entry", {}))
    _fb_oos = _fb_raw.get("_oos_validation", {})
    _fb_available = True
except Exception:
    _fb_available = False
    _fb_t1 = _fb_t2 = _fb_ve = _fb_oos = {}


# ──────────────────────────────────────────────────────────────────────
# DASHBOARD DATA LAYER — Ingesta robusta + estado aislado
# ──────────────────────────────────────────────────────────────────────

# Resolve trade events path first (used by adapter + legacy code)
_TRADE_EVENTS_PATH = (
    "outputs/backtests/complete_trades_clean.csv"
    if os.path.exists("outputs/backtests/complete_trades_clean.csv")
    else "outputs/backtests/backtest_results.csv"
)


# ──────────────────────────────────────────────────────────────────────
# ML TRADE SCORER
# ──────────────────────────────────────────────────────────────────────
# ML TRADE SCORER
# ──────────────────────────────────────────────────────────────────────
@st.cache_resource
def load_trade_scorer():
    """Cargar modelo trade_scorer_lgbm.pkl si existe."""
    import pickle

    model_path = Path("models/trade_scorer_lgbm.pkl")
    if not model_path.exists():
        return None
    try:
        with open(model_path, "rb") as f:
            payload = pickle.load(f)
        return payload
    except Exception as e:
        st.warning(f"No se pudo cargar modelo ML: {e}")
        return None


def score_trades_ml(trades_df, model_payload):
    """Agregar columna ml_score a trades_df usando el modelo ML."""
    if model_payload is None:
        return trades_df
    model = model_payload.get("model")
    features = model_payload.get("features", [])
    if model is None or not features:
        return trades_df
    try:
        # MEMORY OPT: no copiar el DF entero, solo las columnas relevantes
        # Las columnas que necesitamos para scoring son pocas vs el DF completo
        score_cols = [
            c
            for c in trades_df.columns
            if c in features
            or c
            in [
                "entry_date",
                "context_rvol",
                "context_adr",
                "context_dollar_vol",
                "rs_60d",
                "rs_20d",
                "signal_type",
                "market_stage_ml",
                "vix_regime",
                "entry_stage",
                "sector_strength",
            ]
        ]
        df = trades_df[score_cols].copy()  # copy solo columnas necesarias

        # Ensure datetime for calendar-derived features
        if "entry_date" in df.columns:
            df["entry_date"] = pd.to_datetime(df["entry_date"], errors="coerce")
            if "month" not in df.columns:
                df["month"] = df["entry_date"].dt.month
            if "weekday" not in df.columns:
                df["weekday"] = df["entry_date"].dt.weekday

        # Lightweight derived numeric features (no external data)
        if (
            "rvol_adr_ratio" not in df.columns
            and "context_rvol" in df.columns
            and "context_adr" in df.columns
        ):
            df["rvol_adr_ratio"] = df["context_rvol"] / (df["context_adr"] + 0.01)

        if "log_dollar_vol" not in df.columns and "context_dollar_vol" in df.columns:
            df["log_dollar_vol"] = np.log1p(
                pd.to_numeric(df["context_dollar_vol"], errors="coerce").fillna(0)
            )

        if (
            "rs_divergence" not in df.columns
            and "rs_60d" in df.columns
            and "rs_20d" in df.columns
        ):
            df["rs_divergence"] = pd.to_numeric(
                df["rs_60d"], errors="coerce"
            ) - pd.to_numeric(df["rs_20d"], errors="coerce")

        if (
            "rs_momentum_flag" not in df.columns
            and "rs_60d" in df.columns
            and "rs_20d" in df.columns
        ):
            rs60 = pd.to_numeric(df["rs_60d"], errors="coerce")
            rs20 = pd.to_numeric(df["rs_20d"], errors="coerce")
            df["rs_momentum_flag"] = ((rs20 > rs60) & (rs60 > 60)).astype(float)

        # Encoders (optional) - if not present in payload we default to 0
        encoders = model_payload.get("encoders", {})

        def _encode_to_col(src_col: str, dst_col: str, encoder_key: str) -> None:
            if dst_col in df.columns:
                return
            mapping = encoders.get(encoder_key)
            if mapping and src_col in df.columns:
                df[dst_col] = df[src_col].astype(str).map(mapping).fillna(0).astype(int)
            else:
                df[dst_col] = 0

        if "signal_type_enc" in features:
            _encode_to_col("signal_type", "signal_type_enc", "signal_type")
        if "market_stage_ml_enc" in features:
            _encode_to_col("market_stage_ml", "market_stage_ml_enc", "market_stage_ml")
        if "vix_regime_enc" in features:
            _encode_to_col("vix_regime", "vix_regime_enc", "vix_regime")
        if "entry_stage_enc" in features:
            _encode_to_col("entry_stage", "entry_stage_enc", "entry_stage")
        if "sector_strength_enc" in features:
            _encode_to_col("sector_strength", "sector_strength_enc", "sector_strength")

        # Build feature matrix; missing cols get filled with 0
        X = df.reindex(columns=features)
        X = X.apply(pd.to_numeric, errors="ignore")
        X = X.fillna(X.median(numeric_only=True)).fillna(0)

        scores = model.predict_proba(X)[:, 1]
        result = trades_df.copy()
        result["ml_score"] = pd.to_numeric(scores, errors="coerce").clip(0, 1)
        return result
    except Exception:
        return trades_df


# --- CARGAR MODELO ML AL INICIO ---
_ML_MODEL = load_trade_scorer()


# --- PERFORMANCE OPTIMIZATION WRAPPERS ---


@st.cache_data(ttl=300, show_spinner=False)
def get_cached_intraday_data(symbol: str, interval: str, days: int):
    from src.data.market_data import MarketDataProvider

    provider = MarketDataProvider()
    return provider.get_intraday_data(symbol, interval=interval, days=days)


@st.cache_data(show_spinner=False)
def _cached_group_trades(df_json: str) -> "pd.DataFrame":
    """Cache del TradeGrouper — evita reagrupar trades en cada rerun de Streamlit."""
    from io import StringIO

    df = pd.read_json(
        StringIO(df_json),
        convert_dates=["entry_date", "exit_date", "final_exit_date"],
    )
    trade_df = df.rename(columns={"symbol": "ticker"})
    return TradeGrouper.group_partial_trades(trade_df)


# ──────────────────────────────────────────────────────────────────────
# DASHBOARD DATA LAYER — Ingesta robusta + estado aislado
# (must be after _cached_group_trades definition)
# ──────────────────────────────────────────────────────────────────────


# 1) Adapter: carga trades CSV con normalización canónica
# MEMORY OPT: cachear usando mtime del CSV como key — se invalida cuando el backtest
# escribe un CSV nuevo, sin necesidad de TTL fijo que cause lag en el dashboard.
def _get_csv_mtime(path: str) -> float:
    """Retorna mtime del CSV para usar como cache key."""
    import os as _os

    try:
        return _os.path.getmtime(path)
    except Exception:
        return 0.0


@st.cache_data(show_spinner=False)
def _load_trades_cached(path: str, _mtime: float = 0.0) -> pd.DataFrame:
    """Carga y normaliza el CSV de trades. Cache se invalida al cambiar el archivo."""
    adapter = get_adapter()
    return adapter.load_trades_csv(path)


@st.cache_data(show_spinner=False)
def _build_index_cached(path: str, _mtime: float = 0.0) -> dict:
    """Construye índice asset→patrones. Cache se invalida al cambiar el archivo."""
    adapter = get_adapter()
    trades = _load_trades_cached(path, _mtime)
    if trades.empty:
        return {"ALL": ["any"]}
    return adapter.build_asset_pattern_index(trades)


_adapter = get_adapter()
_trades_csv_mtime = _get_csv_mtime(_TRADE_EVENTS_PATH)
_trades_df = (
    _load_trades_cached(_TRADE_EVENTS_PATH, _trades_csv_mtime)
    if os.path.exists(_TRADE_EVENTS_PATH)
    else pd.DataFrame()
)

# 2) Índice activo → patrones (para selectores dependientes)
_asset_pattern_index = (
    _build_index_cached(_TRADE_EVENTS_PATH, _trades_csv_mtime)
    if os.path.exists(_TRADE_EVENTS_PATH) and not _trades_df.empty
    else {"ALL": ["any"]}
)

# 3) Session state: árbol de estado con selectores dependientes
_dash_state = DashboardState(st.session_state)
_dash_state.init()

# 4) Vista filtrada: TODAS las visualizaciones consumen esta vista
_selected_asset = _dash_state.selected_asset
_selected_pattern = _dash_state.selected_pattern
_view_df, _scope_label, _n_view_trades = get_scope_info(
    _trades_df, _selected_asset, _selected_pattern
)

# 5) Grouped trades (legacy TradeGrouper) sobre la vista filtrada
if not _view_df.empty:
    # MEMORY OPT: evitar copias dobles del view DF en cada rerun
    # _view_for_grouper: renombrar sin copy si ya tiene 'ticker', sino rename crea copia mínima
    if "symbol" in _view_df.columns and "ticker" not in _view_df.columns:
        _view_for_grouper = _view_df.rename(columns={"symbol": "ticker"})
    else:
        _view_for_grouper = _view_df
    grouped_trades = _cached_group_trades(_view_for_grouper.to_json())
    if not grouped_trades.empty:
        g_numeric_cols = grouped_trades.select_dtypes(include=[np.number]).columns
        grouped_trades[g_numeric_cols] = grouped_trades[g_numeric_cols].round(2)
    # MEMORY OPT: df = alias de _view_df con tipos de fecha corregidos (sin copy completo)
    df = _view_df
    if "entry_date" in df.columns:
        # Solo convertir si no es datetime ya (evita operacion innecesaria)
        if not pd.api.types.is_datetime64_any_dtype(df["entry_date"]):
            df = df.copy()  # copy lazy: solo si realmente necesitamos mutar
            df["entry_date"] = pd.to_datetime(df["entry_date"])
    if "exit_date" in df.columns:
        if not pd.api.types.is_datetime64_any_dtype(df["exit_date"]):
            if df is _view_df:  # no hicimos copy aun
                df = df.copy()
            df["exit_date"] = pd.to_datetime(df["exit_date"])
    trade_df_for_grouper = _view_for_grouper
else:
    grouped_trades = pd.DataFrame()
    df = pd.DataFrame()
    trade_df_for_grouper = pd.DataFrame()

has_r = (
    (
        "r_multiple" in grouped_trades.columns
        and grouped_trades["r_multiple"].abs().sum() > 0
    )
    if not grouped_trades.empty
    else False
)

_dash_cache = DashboardCache()
_dashboard_v2_adapter = get_dashboard_v2_adapter()


@st.cache_data(show_spinner=False)
def _load_integration_run_v2(mode: str, date: str | None = None) -> dict:
    return _dashboard_v2_adapter.load_integration_run(mode=mode, date=date)


@st.cache_data(show_spinner=False)
def _load_combo_run_v2(date: str | None = None) -> dict:
    return _dashboard_v2_adapter.load_combo_scan_run(date=date)


@st.cache_data(show_spinner=False)
def _load_universe_snapshot_v2() -> dict:
    return _dashboard_v2_adapter.load_universe_snapshot()


def _filter_by_system(df: pd.DataFrame, system_view: str) -> pd.DataFrame:
    if df.empty or system_view == "Combined" or "source_system" not in df.columns:
        return df
    target = "A" if system_view == "A only" else "B"
    return df[df["source_system"] == target]


def _filter_combo_df(df: pd.DataFrame, selected_agent: str) -> pd.DataFrame:
    if df.empty or selected_agent == "All agents" or "agent_name" not in df.columns:
        return df
    return df[df["agent_name"] == selected_agent]


def _render_kpi_row(items: list[tuple[str, str, str | None]]) -> None:
    cols = st.columns(len(items))
    for col, (label, value, delta) in zip(cols, items):
        col.metric(label, value, delta=delta)


def _render_phase_status(run: dict) -> None:
    status = run.get("status", {})
    labels = [("F1", "Unified"), ("F2", "Router"), ("F3", "Risk"), ("F4", "Edge")]
    cols = st.columns(len(labels))
    for col, (phase, subtitle) in zip(cols, labels):
        ok = bool(status.get(phase.lower()))
        col.markdown(
            f"""
            <div style="padding:14px 16px;border:1px solid {"#204b32" if ok else "#5b2f2f"};
            border-radius:14px;background:{"#0f1e17" if ok else "#221516"};">
              <div style="font-size:12px;color:#9eb1c9;text-transform:uppercase;letter-spacing:0.08em;">{phase}</div>
              <div style="font-size:20px;font-weight:700;margin-top:4px;">{"OK" if ok else "Missing"}</div>
              <div style="font-size:12px;color:#9eb1c9;margin-top:2px;">{subtitle}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )


def _render_warnings(warnings: list[str], title: str = "Artifacts") -> None:
    if warnings:
        with st.expander(f"Warnings: {title}", expanded=False):
            for warning in warnings:
                st.warning(warning)


def _render_pipeline_summary(run: dict, system_view: str) -> None:
    unified_df = _filter_by_system(
        run.get("unified_signals_df", pd.DataFrame()), system_view
    )
    routed_df = _filter_by_system(
        run.get("routed_signals_df", pd.DataFrame()), system_view
    )
    execution_df = _filter_by_system(
        run.get("execution_plan_df", pd.DataFrame()), system_view
    )
    phase3 = run.get("phase3_summary", {})
    router = run.get("router_summary", {})
    edge = run.get("edge_report", {})
    preflight = edge.get("preflight", {})

    exposure_value = (
        phase3.get("exposure_total", 0.0)
        if system_view == "Combined"
        else phase3.get("exposure_A", 0.0)
        if system_view == "A only"
        else phase3.get("exposure_B", 0.0)
    )
    positions_value = (
        phase3.get("positions_total", 0)
        if system_view == "Combined"
        else phase3.get("positions_A", 0)
        if system_view == "A only"
        else phase3.get("positions_B", 0)
    )

    _render_kpi_row(
        [
            ("Signals F1", f"{len(unified_df):,}", None),
            ("Accepted F2", f"{len(routed_df):,}", None),
            ("Planned F3", f"{len(execution_df):,}", None),
            ("Exposure", f"${exposure_value:,.0f}", None),
            ("Positions", f"{positions_value}", None),
            ("Edge Status", edge.get("status", "N/A"), None),
        ]
    )

    subcols = st.columns(3)
    with subcols[0]:
        st.caption("Router breakdown")
        _render_kpi_row(
            [
                ("Accepted", str(router.get("accepted", "—")), None),
                ("Dropped", str(router.get("dropped", "—")), None),
                ("Blocked", str(router.get("blocked", "—")), None),
            ]
        )
    with subcols[1]:
        st.caption("Hydration rates")
        rate_a = preflight.get("hydrated_rate_A")
        rate_b = preflight.get("hydrated_rate_B")
        _render_kpi_row(
            [
                ("Rate A", f"{rate_a:.0%}" if rate_a is not None else "—", None),
                ("Rate B", f"{rate_b:.0%}" if rate_b is not None else "—", None),
                ("Sessions", str(preflight.get("common_sessions", "—")), None),
            ]
        )
    with subcols[2]:
        st.caption("Edge preflight")
        if preflight.get("passed"):
            st.success("✓ Preflight passed")
        else:
            st.error("✗ Preflight blocked")
            for error in preflight.get("errors") or []:
                st.caption(f"⚠ {error}")


def _render_execution_table(run: dict, system_view: str) -> None:
    execution_df = _filter_by_system(
        run.get("execution_plan_df", pd.DataFrame()), system_view
    )
    rejected_df = _filter_by_system(
        run.get("risk_rejected_df", pd.DataFrame()), system_view
    )
    if execution_df.empty:
        st.info("No execution plan rows found for this view.")
    else:
        columns = [
            column
            for column in [
                "source_system",
                "strategy_id",
                "ticker",
                "trade_date",
                "entry_price_ref",
                "hydrated_price_source",
                "shares",
                "notional_usd",
                "router_reason",
                "meta_historical_plan",
                "meta_price_origin",
                "meta_price_validation_mode",
            ]
            if column in execution_df.columns
        ]
        st.dataframe(
            execution_df[columns].sort_values(
                by=[
                    c for c in ["trade_date", "source_system", "ticker"] if c in columns
                ]
            ),
            use_container_width=True,
            height=360,
        )
    if not rejected_df.empty:
        with st.expander("Risk rejects", expanded=False):
            st.dataframe(rejected_df.head(100), use_container_width=True, height=280)


def _render_edge_panel(run: dict, system_view: str) -> None:
    edge_report = run.get("edge_report", {})
    preflight = edge_report.get("preflight", {})
    metrics_df = _filter_by_system(
        run.get("edge_metrics_df", pd.DataFrame()), system_view
    )
    promotions_df = _filter_by_system(
        run.get("promotion_decisions_df", pd.DataFrame()), system_view
    )

    header_cols = st.columns(5)
    header_cols[0].metric(
        "Preflight", "PASS ✓" if preflight.get("passed") else "BLOCKED ✗"
    )
    header_cols[1].metric("Common Sessions", f"{preflight.get('common_sessions', 0):,}")
    header_cols[2].metric("PROMOTE", f"{edge_report.get('promote_count', 0)}")
    header_cols[3].metric("HOLD", f"{edge_report.get('hold_count', 0)}")
    header_cols[4].metric("REJECT", f"{edge_report.get('reject_count', 0)}")

    # Degradation warning
    if edge_report.get("rolling_degradation_detected"):
        pct = edge_report.get("rolling_degradation_pct", 0)
        st.warning(
            f"⚠ Rolling degradation detected: {pct:.0%} of rolling windows below threshold."
        )

    if preflight.get("errors"):
        for error in preflight.get("errors") or []:
            st.error(f"✗ {error}")
    elif edge_report.get("message"):
        st.info(edge_report["message"])

    # Inline promotions from edge_report (historical mode has them embedded)
    inline_promotions = edge_report.get("promotions", [])
    if inline_promotions and promotions_df.empty:
        promotions_df = pd.DataFrame(inline_promotions)

    # Inline metrics from edge_report
    inline_metrics = edge_report.get("edge_metrics", [])
    if inline_metrics and metrics_df.empty:
        metrics_df = pd.DataFrame(inline_metrics)

    if not metrics_df.empty:
        st.subheader("Edge Metrics by Strategy")
        vis_cols = [
            c
            for c in [
                "source_system",
                "strategy_id",
                "ticker",
                "promote_decision",
                "sharpe",
                "win_rate",
                "profit_factor",
                "trade_count",
                "edge_score",
                "promote_reason",
            ]
            if c in metrics_df.columns
        ]
        st.dataframe(
            metrics_df[vis_cols] if vis_cols else metrics_df,
            use_container_width=True,
            height=300,
        )
    if not promotions_df.empty:
        st.subheader("Promotion Decisions")
        vis_cols = [
            c
            for c in [
                "strategy_id",
                "ticker",
                "source_system",
                "decision",
                "reason",
                "edge_score",
                "promote_count",
            ]
            if c in promotions_df.columns
        ]
        st.dataframe(
            promotions_df[vis_cols] if vis_cols else promotions_df,
            use_container_width=True,
            height=240,
        )


def _render_universe_panel(universe_run: dict) -> None:
    meta = universe_run.get("stable_universe_meta", {})
    universe_df = universe_run.get("stable_universe_df", pd.DataFrame())
    _render_kpi_row(
        [
            ("Provider", str(meta.get("provider", "N/A")), None),
            ("Tickers", f"{meta.get('tickers_count', len(universe_df)):,}", None),
            ("Scan Date", str(meta.get("scan_date", "N/A")), None),
            ("Pages OK", str(meta.get("pages_ok", "N/A")), None),
        ]
    )
    left, right = st.columns([1.4, 1])
    with left:
        st.subheader("Universe Metadata")
        st.json(meta)
    with right:
        st.subheader("Stable Universe")
        if universe_df.empty:
            st.warning("stable_universe.csv is missing or empty.")
        else:
            st.dataframe(universe_df.head(250), use_container_width=True, height=360)
    if universe_run.get("latest_snapshot_date"):
        st.caption(f"Latest snapshot: {universe_run['latest_snapshot_date']}")


def _render_combo_panel(combo_run: dict, selected_agent: str) -> None:
    summary = combo_run.get("combo_scan_summary", {})
    combo_df = _filter_combo_df(
        combo_run.get("combo_signals_df", pd.DataFrame()), selected_agent
    )
    agent_tables = combo_run.get("agent_tables", {})
    agents = summary.get("agents", {})

    _render_kpi_row(
        [
            ("Combo Run", str(combo_run.get("run_date", "N/A")), None),
            ("Universe Source", str(summary.get("universe_source", "N/A")), None),
            ("Universe Count", f"{summary.get('universe_count', 0):,}", None),
            ("Signals", f"{len(combo_df):,}", None),
        ]
    )

    top_left, top_right = st.columns([1.1, 1.4])
    with top_left:
        st.subheader("Run Summary")
        st.json(summary)
    with top_right:
        st.subheader("Combined Signals")
        if combo_df.empty:
            st.info("No combo signals found for the selected filter.")
        else:
            visible = [
                column
                for column in [
                    "agent_name",
                    "combo_name",
                    "ticker",
                    "signal_date",
                    "entry_score",
                    "screener_score",
                    "screener_reason",
                    "pattern_signal",
                    "tier2_filter",
                    "rvol",
                    "adr_pct",
                    "dist_sma20",
                    "dollar_vol_M",
                    "rs_percentile",
                    "rs_ret",
                ]
                if column in combo_df.columns
            ]
            st.dataframe(
                combo_df[visible].head(250), use_container_width=True, height=360
            )

    if agents:
        with st.expander("Agent breakdown", expanded=False):
            st.json(agents)
    if selected_agent != "All agents" and selected_agent in agent_tables:
        with st.expander(f"Raw file: {selected_agent}", expanded=False):
            st.dataframe(
                agent_tables[selected_agent].head(250),
                use_container_width=True,
                height=280,
            )


def _render_ab_comparison(live_run: dict, historical_run: dict) -> None:
    """Render A vs B signal count and exposure comparison as bar charts."""
    phase3_live = live_run.get("phase3_summary", {})
    unified_live = live_run.get("unified_signals_df", pd.DataFrame())

    f1_a_live = (
        int((unified_live.get("source_system", pd.Series()) == "A").sum())
        if not unified_live.empty
        else 0
    )
    f1_b_live = (
        int((unified_live.get("source_system", pd.Series()) == "B").sum())
        if not unified_live.empty
        else 0
    )

    st.markdown("#### A vs B Signal Breakdown")
    chart_cols = st.columns(2)
    with chart_cols[0]:
        bar_data = pd.DataFrame(
            {
                "System": ["A", "B"],
                "F1 Signals": [f1_a_live, f1_b_live],
            }
        )
        if bar_data["F1 Signals"].sum() > 0:
            fig = px.bar(
                bar_data,
                x="System",
                y="F1 Signals",
                color="System",
                color_discrete_map={"A": "#3b82f6", "B": "#f59e0b"},
                title="Live F1 Signals by System",
                height=240,
            )
            fig.update_layout(showlegend=False, margin=dict(t=36, b=16, l=16, r=16))
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No F1 signal data for A/B breakdown.")
    with chart_cols[1]:
        exp_data = pd.DataFrame(
            {
                "System": ["A", "B"],
                "Exposure USD": [
                    float(phase3_live.get("exposure_A", 0) or 0),
                    float(phase3_live.get("exposure_B", 0) or 0),
                ],
            }
        )
        if exp_data["Exposure USD"].sum() > 0:
            fig2 = px.bar(
                exp_data,
                x="System",
                y="Exposure USD",
                color="System",
                color_discrete_map={"A": "#3b82f6", "B": "#f59e0b"},
                title="Live Planned Exposure by System",
                height=240,
            )
            fig2.update_layout(showlegend=False, margin=dict(t=36, b=16, l=16, r=16))
            st.plotly_chart(fig2, use_container_width=True)
        else:
            st.info("No exposure data for A/B breakdown.")


def _render_dashboard_v2(
    mode: str, system_view: str, selected_combo_run: str | None, selected_agent: str
) -> None:
    run = _load_integration_run_v2(mode)
    historical_run = _load_integration_run_v2("historical")
    combo_run = _load_combo_run_v2(selected_combo_run)
    universe_run = _load_universe_snapshot_v2()

    st.title("Momentum Control Tower 2.0")
    st.caption(
        f"Mode: {mode.title()}  |  System view: {system_view}  |  Integration run: {run.get('run_date') or 'latest'}"
    )
    _render_warnings(run.get("warnings", []), f"integration/{mode}")
    _render_warnings(combo_run.get("warnings", []), "combo scanner")
    _render_warnings(universe_run.get("warnings", []), "stable universe")

    overview_tab, pipeline_tab, universe_tab, research_tab, legacy_tab = st.tabs(
        [
            "Overview",
            "Live Pipeline",
            "Universe + Combos",
            "Research / Historical",
            "Legacy",
        ]
    )

    with overview_tab:
        _render_phase_status(run)
        st.markdown("")
        _render_pipeline_summary(run, system_view)

        # A vs B comparison chart
        _render_ab_comparison(run, historical_run)

        if mode == "live":
            edge_report = run.get("edge_report", {})
            preflight = edge_report.get("preflight", {})
            if preflight.get("errors") and any(
                "hydrated_rate_B" in err for err in (preflight.get("errors") or [])
            ):
                st.warning(
                    "⚠ System B is currently blocked in live due to input pricing without historical authorization."
                )

    with pipeline_tab:
        pipe_tab, exec_tab, edge_tab = st.tabs(["Pipeline", "Execution", "Edge"])
        with pipe_tab:
            st.subheader("Unified Signals (F1)")
            f1 = _filter_by_system(
                run.get("unified_signals_df", pd.DataFrame()), system_view
            )
            if f1.empty:
                st.info("No F1 signals found.")
            else:
                cols = [
                    c
                    for c in [
                        "source_system",
                        "strategy_id",
                        "ticker",
                        "signal_time",
                        "entry_price_ref",
                        "meta_historical_plan",
                        "meta_price_origin",
                    ]
                    if c in f1.columns
                ]
                st.dataframe(f1[cols].head(250), use_container_width=True, height=260)
            st.subheader("Routed Signals (F2)")
            f2 = _filter_by_system(
                run.get("routed_signals_df", pd.DataFrame()), system_view
            )
            if not f2.empty:
                cols = [
                    c
                    for c in [
                        "source_system",
                        "strategy_id",
                        "ticker",
                        "signal_time",
                        "entry_price_ref",
                        "router_reason",
                        "meta_historical_plan",
                    ]
                    if c in f2.columns
                ]
                st.dataframe(f2[cols].head(250), use_container_width=True, height=260)
        with exec_tab:
            _render_execution_table(run, system_view)
        with edge_tab:
            _render_edge_panel(run, system_view)

    with universe_tab:
        top_tab, combo_tab = st.tabs(["Universe", "Combos"])
        with top_tab:
            _render_universe_panel(universe_run)
        with combo_tab:
            _render_combo_panel(combo_run, selected_agent)

    with research_tab:
        st.subheader("Historical Calibration")
        _render_phase_status(historical_run)
        _render_pipeline_summary(historical_run, system_view)
        hist_edge_tab, hist_exec_tab = st.tabs(
            ["Historical Edge", "Historical Execution"]
        )
        with hist_edge_tab:
            _render_edge_panel(historical_run, system_view)
        with hist_exec_tab:
            _render_execution_table(historical_run, system_view)

    with legacy_tab:
        st.info(
            "The legacy backtest dashboard is still available. Switch the sidebar selector to `Legacy` to open the full legacy workspace."
        )
        if not _trades_df.empty:
            st.caption(f"Legacy trade log loaded: {len(_trades_df):,} rows")


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
    # VCP / pattern params
    signal_type="breakout",
    vcp_pivot_window=15,
    vcp_atr_short=10,
    vcp_atr_long=30,
    vcp_atr_ratio=0.85,
    vcp_volume_dry_periods=5,
    vcp_depth_max_pct=15.0,
    vcp_pivot_dist_max_pct=8.0,
    vcp_require_vol_dry=True,
    # Pocket Pivot params
    pp_vol_lookback=10,
    pp_vol_mult=1.0,
    # Flat Base params
    fb_min_weeks=5,
    fb_max_range=7.0,
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
        signal_type=signal_type,
        vcp_pivot_window=vcp_pivot_window,
        vcp_atr_short=vcp_atr_short,
        vcp_atr_long=vcp_atr_long,
        vcp_atr_ratio=vcp_atr_ratio,
        vcp_volume_dry_periods=vcp_volume_dry_periods,
        vcp_depth_max_pct=vcp_depth_max_pct,
        vcp_pivot_dist_max_pct=vcp_pivot_dist_max_pct,
        vcp_require_vol_dry=vcp_require_vol_dry,
        pp_vol_lookback=pp_vol_lookback,
        pp_vol_mult=pp_vol_mult,
        fb_min_weeks=fb_min_weeks,
        fb_max_range=fb_max_range,
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
    if "ticker_cache_instance" not in st.session_state:
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
                datetime.strptime(max_date[0], "%Y-%m-%d"),
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
    tp1_p,
    tp2_p,
    run_p,
    use_adaptive,
    use_earnings_filter,
    _use_pit,
    use_rs_percentile,
    min_rs_percentile,
    _use_ml,
    _ml_threshold,
    _ml_boost,
    # Signal type routing
    signal_type,
    vcp_pivot_window,
    vcp_atr_short,
    vcp_atr_long,
    vcp_atr_ratio,
    vcp_volume_dry_periods,
    vcp_depth_max_pct,
    vcp_pivot_dist_max_pct,
    vcp_require_vol_dry,
    pp_vol_lookback,
    pp_vol_mult,
    fb_min_weeks,
    fb_max_range,
    min_required_days_override=None,
    universe_selection_method="static",
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

            _period_days = (
                pd.to_datetime(str(end_date)) - pd.to_datetime(str(start_date))
            ).days
            _trading_days_est = int(_period_days * 5 / 7)  # rough estimate
            _auto_min_days = max(10, min(100, int(_trading_days_est * 0.5)))
            min_required_days = (
                int(min_required_days_override)
                if min_required_days_override is not None
                else _auto_min_days
            )

            # ── US-ONLY FILTER: exclude tickers with exchange suffix ─────
            # Tickers US no tienen sufijo: AAPL, MSFT, SPY
            # Tickers internacionales tienen sufijo: 005930-KS, 300750-SZ, 0981-HK
            # Esto se hace en SQL para no cargar datos innecesarios a RAM
            us_filter_clause = " AND ticker NOT LIKE '%-%' " if us_only else ""

            if max_symbols == 0:
                if universe_selection_method == "static":
                    # Universo estático: solo tickers presentes al inicio del período
                    query = f"""
                        SELECT ticker 
                        FROM ohlcv_cache 
                        WHERE date BETWEEN ? AND ? 
                        {us_filter_clause}
                        GROUP BY ticker 
                        HAVING COUNT(*) >= ? 
                        ORDER BY ticker ASC
                    """
                    cursor = conn.execute(
                        query, (selection_start, selection_end, min_required_days)
                    )
                else:
                    # Rebalance mensual: universo rotado cada mes
                    # Nota: usamos umbral mensual de 15 días (no min_required_days)
                    query = f"""
                        WITH monthly_universe AS (
                            SELECT 
                                ticker,
                                AVG(rolling_dollar_vol_20) as avg_adv
                            FROM ohlcv_cache 
                            WHERE date BETWEEN ? AND ? 
                            AND rolling_dollar_vol_20 IS NOT NULL
                            {us_filter_clause}
                            GROUP BY ticker, strftime('%Y-%m', date)
                            HAVING COUNT(*) >= 15
                        )
                        SELECT DISTINCT ticker 
                        FROM monthly_universe 
                        ORDER BY avg_adv DESC, ticker ASC
                    """
                    cursor = conn.execute(query, (selection_start, selection_end))
            else:
                if universe_selection_method == "static":
                    # Universo estático con límite: ranking por liquidez inicial
                    query = f"""
                        WITH universe_rank AS (
                            SELECT 
                                ticker,
                                AVG(rolling_dollar_vol_20) as initial_adv,
                                COUNT(*) as day_count
                            FROM ohlcv_cache 
                            WHERE date BETWEEN ? AND date(date, '+63 days') 
                            AND rolling_dollar_vol_20 IS NOT NULL
                            {us_filter_clause}
                            GROUP BY ticker
                            HAVING day_count >= ?
                        )
                        SELECT ticker 
                        FROM universe_rank 
                        ORDER BY initial_adv DESC, ticker ASC 
                        LIMIT ?
                    """
                    cursor = conn.execute(
                        query, (selection_start, min_required_days, max_symbols)
                    )
                else:
                    # Rebalance mensual con límite
                    query = f"""
                        WITH monthly_universe AS (
                            SELECT 
                                ticker,
                                AVG(rolling_dollar_vol_20) as avg_adv
                            FROM ohlcv_cache 
                            WHERE date BETWEEN ? AND ? 
                            AND rolling_dollar_vol_20 IS NOT NULL
                            {us_filter_clause}
                            GROUP BY ticker, strftime('%Y-%m', date)
                            HAVING COUNT(*) >= 15
                        ),
                        ticker_rank AS (
                            SELECT 
                                ticker,
                                AVG(avg_adv) as overall_adv
                            FROM monthly_universe 
                            GROUP BY ticker
                            ORDER BY overall_adv DESC
                            LIMIT ?
                        )
                        SELECT DISTINCT ticker 
                        FROM ticker_rank 
                        ORDER BY overall_adv DESC, ticker ASC
                    """
                    cursor = conn.execute(
                        query,
                        (selection_start, selection_end, max_symbols),
                    )

            status_text.markdown(
                f"📥 **Extrayendo tickers** (límite: {'SIN LÍMITE' if max_symbols == 0 else max_symbols})..."
            )
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

        status_text.markdown(
            f"🚀 **Iniciando backtest:** {len(universe)} tickers de {start_date} a {end_date}"
        )
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
            use_adaptive,
            tp1_r,
            tp2_r,
            require_spy_above_sma50,
            tp1_p,
            tp2_p,
            run_p,
            use_earnings_filter,
            _use_pit,
            use_rs_percentile,
            min_rs_percentile,
            _use_ml,
            _ml_threshold,
            _ml_boost,
            # Signal params (passed through function signature)
            signal_type,
            vcp_pivot_window,
            vcp_atr_short,
            vcp_atr_long,
            vcp_atr_ratio,
            vcp_volume_dry_periods,
            vcp_depth_max_pct,
            vcp_pivot_dist_max_pct,
            vcp_require_vol_dry,
            pp_vol_lookback,
            pp_vol_mult,
            fb_min_weeks,
            fb_max_range,
        )

        # Update progress after backtest completes
        status_text.markdown(
            "✅ **Backtest completado - generando visualizaciones...**"
        )
        progress_bar.progress(0.9)

        # Universe funnel display
        st.info(
            f"📊 **Universo** | Elegibles SQL: **{len(universe)}** | "
            f"Cargados engine: **{results.get('n_loaded', '?')}** | "
            f"Con trades: **{results.get('n_with_trades', '?')}**"
        )

        # Performance timers display
        _pi = results.get("_perf_init_s", 0)
        _pb = results.get("_perf_backtest_s", 0)
        _pt = results.get("_perf_total_s", 0)
        if _pt > 0:
            st.info(
                f"⏱ Performance | Engine init: **{_pi}s** | Backtest: **{_pb}s** | Total: **{_pt}s**"
            )
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

            # Robust column extraction -- handles ticker/symbol and datetime formats
            def _get_col(df, *names, default=None):
                for n in names:
                    if n in df.columns:
                        return df[n]
                return pd.Series([default] * len(df), index=df.index)

            _sym = _get_col(trades, "ticker", "symbol", "Ticker", "Symbol")
            _sym = _sym.astype(str)  # ensure string, not int index

            def _parse_dates(s):
                """Handle both string dates and nanosecond timestamps."""
                try:
                    parsed = pd.to_datetime(s)
                    # If dates look like epoch (year < 2000), treat as nanoseconds
                    if parsed.dt.year.min() < 2000:
                        parsed = pd.to_datetime(s.astype("int64") // 10**9, unit="s")
                    return parsed
                except Exception:
                    return pd.to_datetime(s, errors="coerce")

            _entry_dates = _parse_dates(trades[entry_date_col])
            _exit_dates = _parse_dates(trades[exit_date_col])

            output_df = pd.DataFrame(
                {
                    "symbol": _sym,
                    "entry_date": _entry_dates,
                    "exit_date": _exit_dates,
                    "entry_price": trades[entry_price_col],
                    "exit_price": trades[exit_price_col],
                    "shares": trades["shares"],
                    "pnl": trades["pnl"],
                    "exit_phase": trades["exit_phase"]
                    if "exit_phase" in trades.columns
                    else "FULL",
                    "signal_type": trades["entry_signal"]
                    if "entry_signal" in trades.columns
                    else signal_type,
                    "stop_loss": trades["stop_loss"]
                    if "stop_loss" in trades.columns
                    else np.nan,
                    "tp1_target": trades["tp1_target"]
                    if "tp1_target" in trades.columns
                    else np.nan,
                    "tp2_target": trades["tp2_target"]
                    if "tp2_target" in trades.columns
                    else np.nan,
                    "adjusted_risk_dollars": trades["adjusted_risk_dollars"]
                    if "adjusted_risk_dollars" in trades.columns
                    else 0,
                    "entry_score": trades["entry_score"]
                    if "entry_score" in trades.columns
                    else np.nan,
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
                _pf = (
                    (_wins.sum() / abs(_loss.sum()))
                    if len(_loss) > 0 and abs(_loss.sum()) > 0
                    else float("inf")
                )
                _r = (
                    trades["r_multiple"].mean() if "r_multiple" in trades.columns else 0
                )
                # Equity curve for Sharpe/DD
                _eq = results.get("equity_curve")
                if _eq is not None and len(_eq) > 1:
                    _ret = _eq.pct_change().dropna()
                    _sharpe = (
                        (_ret.mean() / _ret.std() * (252**0.5)) if _ret.std() > 0 else 0
                    )
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

        # FIX: Clear cached data loaders so dashboard picks up new CSV files
        _load_trades_cached.clear()
        _build_index_cached.clear()
        _cached_group_trades.clear()

        # Force rerun to reload dashboard with fresh trade data
        st.rerun()
        return True
    except Exception as e:
        st.error(f"Error: {e}")
        import traceback

        st.error(traceback.format_exc())

        # Clean up stale output files to avoid showing old results
        stale_files = [
            "outputs/backtests/backtest_results.csv",
            "outputs/backtests/complete_trades_clean.csv",
            "outputs/backtests/equity_curve.csv",
            "outputs/backtests/backtest_metrics.json",
        ]
        for stale_file in stale_files:
            if os.path.exists(stale_file):
                try:
                    os.remove(stale_file)
                except:
                    pass

        return False


# --- CUSTOM CSS ---
st.set_page_config(page_title="Momentum V2 Dashboard", page_icon="📈", layout="wide")
CSS_FILE = Path(__file__).parent / "assets" / "custom.css"
if CSS_FILE.exists():
    st.markdown(f"<style>{CSS_FILE.read_text()}</style>", unsafe_allow_html=True)
else:
    st.warning("⚠️ CSS file not found: assets/custom.css")


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


# --- SIDEBAR (Wired to production_config.json / combo ranking) ---
with st.sidebar:
    st.title("Momentum V2")
    st.caption("Institutional Trading Engine")

    st.subheader("Dashboard")
    dashboard_view = st.radio(
        "Workspace",
        ["Integrated 2.0", "Legacy"],
        index=0,
        help="Integrated 2.0 reads live/historical pipeline artifacts. Legacy keeps the backtest-centric workspace.",
    )
    dashboard_mode = st.radio(
        "Mode",
        ["Live", "Historical"],
        index=0,
        horizontal=True,
        help="Select which integration artifacts to inspect in Dashboard 2.0.",
    )
    system_view = st.selectbox(
        "System View",
        ["Combined", "A only", "B only"],
        index=0,
        help="Filter Dashboard 2.0 views by source system.",
    )
    _combo_run_options = _dashboard_v2_adapter.list_combo_scan_runs() or ["latest"]
    selected_combo_run = st.selectbox(
        "Combo Run Date",
        _combo_run_options,
        index=0,
        help="Reads outputs/live_signals/<date>/ generated by the multi-combo scanner.",
    )
    _combo_run_data = _load_combo_run_v2(
        None if selected_combo_run == "latest" else selected_combo_run
    )
    _agent_series = _combo_run_data.get("combo_signals_df", pd.DataFrame()).get(
        "agent_name", pd.Series(dtype=str)
    )
    _agent_names = sorted({str(agent) for agent in _agent_series.dropna().tolist()})
    selected_agent = st.selectbox(
        "Combo / Agent",
        ["All agents", *_agent_names],
        index=0,
        help="Filters Universe + Combos tables in Dashboard 2.0.",
    )
    if dashboard_view == "Integrated 2.0":
        st.caption(
            "Legacy controls remain available below but are ignored by Dashboard 2.0."
        )
    st.divider()

    # ── RUN SCRIPTS (opt-in, Dashboard 2.0 only) ────────────────────
    if dashboard_view == "Integrated 2.0":
        with st.expander("⚡ Run Scripts (opt-in)", expanded=False):
            st.caption(
                "These trigger external scripts. Dashboard reads their outputs automatically."
            )
            _base = "/home/marcos/trade/momentum-v2"

            def _run_script_streaming(label: str, cmd: list, cwd: str) -> None:
                """Run a script showing live output line by line via Popen."""
                import subprocess as _sp
                import time as _time
                log_placeholder = st.empty()
                status_placeholder = st.empty()
                log_lines: list = []
                try:
                    proc = _sp.Popen(
                        cmd, stdout=_sp.PIPE, stderr=_sp.STDOUT,
                        text=True, cwd=cwd, bufsize=1,
                    )
                    status_placeholder.info(f"⏳ Running {label}...")
                    while True:
                        line = proc.stdout.readline()
                        if line == "" and proc.poll() is not None:
                            break
                        if line:
                            log_lines.append(line.rstrip())
                            # Show last 30 lines rolling
                            log_placeholder.code(
                                "\n".join(log_lines[-30:]), language=None
                            )
                    rc = proc.wait()
                    if rc == 0:
                        status_placeholder.success(f"✓ {label} completed successfully")
                    else:
                        status_placeholder.error(f"✗ {label} failed (rc={rc})")
                except FileNotFoundError:
                    status_placeholder.error(f"✗ Script not found: {cmd[1]}")
                except Exception as _e:
                    status_placeholder.error(f"✗ Unexpected error: {_e}")

            if st.button("🔄 Sync Universe", use_container_width=True, key="btn_sync_universe"):
                _run_script_streaming(
                    "sync_universe.py",
                    ["python3", f"{_base}/scripts/sync_universe.py"],
                    _base,
                )

            if st.button("📡 Run Combo Scanner", use_container_width=True, key="btn_combo_scanner"):
                st.caption("Reads ~400 tickers from DB — typically 1-3 min. Output streams below.")
                _run_script_streaming(
                    "run_combo_scanner.py",
                    ["python3", f"{_base}/scripts/run_combo_scanner.py",
                     "--universe-source", "stable"],
                    _base,
                )

            st.caption("💡 For background runs: python3 scripts/run_combo_scanner.py")
    st.divider()

    # ── YAML COMBO SELECTOR (Fase 3: Centralized config UI) ──────────
    if _yaml_combos_available and _yaml_go_combos:
        st.divider()
        st.subheader("🎯 Combo Activo (YAML)")

        _yaml_combo_names = [c.name for c in _yaml_go_combos]
        _yaml_labels = [
            f"{c.name} (Sharpe WF: {c.wf_sharpe_mean:.2f})" for c in _yaml_go_combos
        ]

        # Restore previous selection or default to first
        _prev_yaml_combo = st.session_state.get("active_yaml_combo")
        _default_idx = 0
        if _prev_yaml_combo and _prev_yaml_combo in _yaml_combo_names:
            _default_idx = _yaml_combo_names.index(_prev_yaml_combo)

        _yaml_selected_label = st.selectbox(
            "Combo activo",
            options=_yaml_labels,
            index=_default_idx,
            help="Selecciona un combo GO validado por walk-forward",
        )

        # Update session state and global reference
        _selected_combo_name = _yaml_combo_names[
            _yaml_labels.index(_yaml_selected_label)
        ]
        st.session_state["active_yaml_combo"] = _selected_combo_name
        _active_yaml_combo = get_combo_by_name(_yaml_combos, _selected_combo_name)

        # Panel de estado del combo seleccionado
        with st.expander("📊 Estado del Combo", expanded=True):
            st.metric("Status", _active_yaml_combo.status)
            st.metric("Sharpe WF Mean", f"{_active_yaml_combo.wf_sharpe_mean:.2f}")
            st.caption(f"Min: {_active_yaml_combo.wf_sharpe_min:.2f}")
            st.metric("PBO", f"{_active_yaml_combo.pbo:.0%}")
            st.caption(f"Costos: {_active_yaml_combo.cost_robustness}")

            # Alerts
            if _active_yaml_combo.alerts:
                for alert in _active_yaml_combo.alerts:
                    if "⚠" in alert:
                        st.warning(alert)
                    else:
                        st.info(alert)

        # Scanner parameters preview
        with st.expander("⚙️ Parámetros del Scanner", expanded=False):
            st.caption(f"Filter: {_active_yaml_combo.scanner_filter}")
            st.caption(f"Patterns: {_active_yaml_combo.pattern_filter}")
            st.caption(
                f"Fee: {_active_yaml_combo.fee_rate * 10000:.0f}bps | Slippage: {_active_yaml_combo.slippage_rate * 10000:.0f}bps"
            )
            st.caption(f"Max positions: {_active_yaml_combo.max_positions}")
            st.caption(f"Regime blocked: {_active_yaml_combo.regime_blocked}")
    else:
        _active_yaml_combo = None

    # ── EXECUTION MODE ───────────────────────────────────────────────
    _exec_mode = st.radio(
        "Execution Mode",
        ["Combo", "Pattern"],
        horizontal=True,
        help="Combo: screener×pattern optimized | Pattern: production_config + pattern override",
    )

    if _exec_mode == "Combo":
        # ── COMBO MODE ───────────────────────────────────────────────
        if _combo_top5:
            _combo_options = []
            for combo in _combo_top5:
                label = (
                    f"{combo.get('combo', combo.get('combo_name', 'combo'))} "
                    f"★ {combo.get('combo_score', combo.get('score', 0.0)):.2f}"
                )
                _combo_options.append(label)
            current_combo = st.session_state.get(
                "active_combo_label", _combo_options[0]
            )
            if current_combo not in _combo_options:
                current_combo = _combo_options[0]
            _combo_sel = st.selectbox(
                "Active Combo",
                _combo_options,
                index=_combo_options.index(current_combo),
                key="active_combo_label",
            )
            st.caption("Combo config loaded — Strategy selector disabled")

            # Show combo metadata
            st.info(f"Source: {_combo_source}")
            if _combo_screener:
                st.caption(f"Screener/Pattern: {_combo_screener}")

            # Force _use_any so Strategy overrides are skipped
            _strategy_sel = "Any (producción)"
            _use_vcp = _use_pp = _use_fb = _use_breakout = False
            _use_any = True
        else:
            st.warning("No combos available in top5.json")
            _combo_sel = None
            _strategy_sel = "Any (producción)"
            _use_vcp = _use_pp = _use_fb = _use_breakout = False
            _use_any = True
    else:
        # ── PATTERN MODE ─────────────────────────────────────────────
        _combo_sel = None
        st.session_state["active_combo_label"] = None

        # ── STRATEGY SELECTOR ────────────────────────────────────────
        _strategy_options = ["Any (producción)", "Breakout"]
        if _vcp_available:
            _v_sh = _vcp_oos.get("oos_sharpe", 0)
            _v_ok = str(_vcp_oos.get("passed", "False")) == "True"
            _strategy_options.append(
                f"VCP {'✅' if _v_ok else '⚠'}  Sharpe {_v_sh:.2f} OOS"
            )
        if _pp_available:
            _p_sh = _pp_oos.get("oos_sharpe", 0)
            _p_ok = str(_pp_oos.get("passed", "False")) == "True"
            _strategy_options.append(
                f"Pocket Pivot {'✅' if _p_ok else '⚠'}  Sharpe {_p_sh:.2f} OOS"
                if _p_sh
                else "Pocket Pivot (sin validar)"
            )
        if _fb_available:
            _f_sh = _fb_oos.get("oos_sharpe", 0)
            _f_ok = str(_fb_oos.get("passed", "False")) == "True"
            _strategy_options.append(
                f"Flat Base {'✅' if _f_ok else '⚠'}  Sharpe {_f_sh:.2f} OOS"
                if _f_sh
                else "Flat Base (sin validar)"
            )
        _strategy_sel = st.selectbox(
            "Strategy",
            _strategy_options,
            index=0,
            help="Any: señal permisiva | Breakout: close>20d_high | VCP: Minervini | Pocket Pivot | Flat Base",
        )
        _use_vcp = _strategy_sel.startswith("VCP") and _vcp_available
        _use_pp = _strategy_sel.startswith("Pocket") and _pp_available
        _use_fb = _strategy_sel.startswith("Flat") and _fb_available
        _use_breakout = _strategy_sel.startswith("Breakout")
        _use_any = _strategy_sel.startswith("Any")

    if _use_vcp:
        _t1 = {**_t1, **_vcp_t1}
        _t2 = {**_t2, **_vcp_t2}
        st.success("VCP config loaded")
    elif _use_pp:
        _t1 = {**_t1, **_pp_t1}
        _t2 = {**_t2, **_pp_t2}
        st.success("Pocket Pivot config loaded")
    elif _use_fb:
        _t1 = {**_t1, **_fb_t1}
        _t2 = {**_t2, **_fb_t2}
        st.success("Flat Base config loaded")
    elif _use_breakout:
        if _bk_t1:
            _t1 = {**_t1, **_bk_t1}
            _t2 = {**_t2, **_bk_t2}
        st.info("Breakout: close > 20d high — config independiente de Any")

    if _use_vcp:
        _vcp_is = _vcp_oos.get("is_sharpe_comparable", 0)
        st.caption(
            f"VCP | IS: {_vcp_is:.2f} -> OOS: {_vcp_oos.get('oos_sharpe', 0):.2f}"
        )
    elif _use_pp:
        st.caption(f"Pocket Pivot | OOS: {_pp_oos.get('oos_sharpe', 'sin validar')}")
    elif _use_fb:
        st.caption(f"Flat Base | OOS: {_fb_oos.get('oos_sharpe', 'sin validar')}")
    elif _use_breakout:
        _bk_oos_sh = _bk_oos.get("oos_sharpe", 0)
        _bk_cap = f"OOS: {_bk_oos_sh:.2f}" if _bk_oos_sh else "sin validar"
        st.caption(f"Breakout | {_bk_cap}")
    else:
        st.caption(f"Any | Sharpe: {_perf.get('sharpe_ratio', 0):.2f}")

    # Strategy-specific params (shown only when that strategy is active)
    if _use_vcp and _vcp_available:
        with st.expander("VCP Entry Params", expanded=False):
            _ve = _vcp_ve
            st.caption(f"pivot_window: {_ve.get('vcp_pivot_window', 10)} bars")
            st.caption(f"atr_ratio: < {_ve.get('vcp_atr_ratio', 0.8)}")
            st.caption(f"depth_max: {_ve.get('vcp_depth_max_pct', 18)}%")
            st.caption(f"pivot_dist: {_ve.get('vcp_pivot_dist_max_pct', 5)}%")
            st.caption(f"vol_dry: {_ve.get('vcp_require_vol_dry', True)}")
            _vv = _vcp_oos
            if _vv.get("oos_sharpe"):
                st.metric(
                    "OOS Sharpe",
                    f"{_vv.get('oos_sharpe', 0):.2f}",
                    f"WR {_vv.get('oos_win_rate', 0):.0f}%",
                )
    elif _use_pp and _pp_available:
        with st.expander("Pocket Pivot Params", expanded=False):
            st.caption(f"vol_lookback: {_pp_ve.get('pp_vol_lookback', 10)} bars")
            st.caption(f"vol_mult: {_pp_ve.get('pp_vol_mult', 1.0)}x")
            if _pp_oos.get("oos_sharpe"):
                st.metric("OOS Sharpe", f"{_pp_oos.get('oos_sharpe', 0):.2f}")
    elif _use_fb and _fb_available:
        with st.expander("Flat Base Params", expanded=False):
            st.caption(f"min_weeks: {_fb_ve.get('fb_min_weeks', 5)}")
            st.caption(f"max_range: {_fb_ve.get('fb_max_range', 7.0)}%")
            if _fb_oos.get("oos_sharpe"):
                st.metric("OOS Sharpe", f"{_fb_oos.get('oos_sharpe', 0):.2f}")

    if st.button("Clear Cache", use_container_width=True):
        st.cache_data.clear()
        st.cache_resource.clear()
        _dash_cache.invalidate()
        st.toast("Cache Cleared")
    st.markdown("---")

    # ── MULTI-ASSET / MULTI-PATTERN SELECTORS ────────────────────────
    if not _trades_df.empty:
        with st.expander("🔍 Segmentar por Activo / Patrón", expanded=True):
            _dash_state.render_asset_selector(
                asset_list=sorted(_trades_df["symbol"].dropna().unique().tolist())
                if "symbol" in _trades_df.columns
                else [],
                pattern_index=_asset_pattern_index,
            )
            _dash_state.render_pattern_selector(pattern_index=_asset_pattern_index)
            _dash_state.render_scope_badge()
            st.caption(f"{_n_view_trades} trades en vista actual")
        st.markdown("---")

    with st.expander("Market & Universe", expanded=True):
        cache_min, cache_max = get_cache_date_range()
        start_date = st.date_input("Start", value=cache_max - timedelta(days=365))
        end_date = st.date_input("End", value=cache_max)
        scan_mode = st.radio(
            "Source", ["Manual", "All Market", "Sector"], horizontal=True
        )
        tickers_input = st.text_area("Tickers (CSV)", "APP, PLTR", height=70)

        # ── MEMORY SAVER: US-only filter ─────────────────────────────────
        # Tickers US no tienen sufijo de exchange (ej: AAPL vs 005930-KS)
        # Filtrar en query SQL reduce RAM cargando menos columnas en DataFrames
        us_only = st.checkbox(
            "US Market Only",
            value=True,
            help="Solo tickers de exchanges US (NYSE/NASDAQ). "
            "Reduce RAM significativamente al excluir Asia/Europa/Latam.",
        )

        # ── MEMORY SAVER: Cap de universo ────────────────────────────────
        if scan_mode == "All Market":
            max_symbols_ui = st.slider(
                "Max Tickers",
                min_value=50,
                max_value=3000,
                value=200,
                step=50,
                help="Limite superior de tickers. Menos = menos RAM.",
            )
        else:
            max_symbols_ui = 0  # Manual o Sector: sin limite forzado

        # ── UNIVERSE SELECTION (Look-ahead bias fix) ─────────────────────────
        st.write("🔍 **Selección de Universo (sin look-ahead):**")
        universe_selection = st.selectbox(
            "Método de selección",
            ["Estático (inicio período)", "Rebalance Mensual"],
            index=0,
            help="Estático: universo fijo desde inicio. Rebalance: universo rotado cada mes.",
        )

        # ── MIN DAYS OVERRIDE ────────────────────────────────────────────
        min_days_ui = st.slider(
            "Min días en rango",
            min_value=10,
            max_value=300,
            value=100,
            step=10,
            help="Días mínimos que debe tener el ticker en el rango. Bajar amplía IPOs tardíos.",
        )
        # ── MEMORY SAVER: Low-memory mode ────────────────────────────────
        low_memory_mode = st.checkbox(
            "Low Memory Mode",
            value=False,
            help="Reduce RAM: limita a 150 tickers, desactiva PIT universe y ML filter.",
        )

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
                max_value=10000,
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
            ml_threshold = st.slider(
                "ML threshold",
                0.30,
                0.60,
                0.40,
                step=0.05,
                help="Entradas con prob ML por debajo de este valor son bloqueadas",
            )
            ml_boost = st.slider(
                "ML boost weight",
                0.0,
                0.40,
                0.20,
                step=0.05,
                help="entry_score += boost * ml_prob para entradas que pasan el filtro",
            )
        else:
            ml_threshold = 0.40
            ml_boost = 0.20
        # PERF Item 5: st.form agrupa los sliders Tier 2.
        # Los cambios se acumulan y solo se aplican al presionar "Apply".
        # Esto evita un rerun completo por cada movimiento de slider.
        with st.form("tier2_params_form"):
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
            st.form_submit_button("Apply Tier 2 Params", use_container_width=True)

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
        # ── LOW MEMORY MODE overrides ────────────────────────────────────
        if low_memory_mode:
            _max_sym = 150
            _use_pit = False
            _use_ml = False
            _ml_threshold = 0.40
            _ml_boost = 0.20
        else:
            _max_sym = (
                max_symbols_ui
                if scan_mode == "All Market"
                else (3000 if scan_mode == "Sector" else 0)
            )
            _use_pit = use_pit
            _use_ml = use_ml
            _ml_threshold = ml_threshold
            _ml_boost = ml_boost

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
            _max_sym,
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
            _use_pit,
            True,  # use_rs_percentile
            0,  # min_rs_percentile
            _use_ml,
            _ml_threshold,
            _ml_boost,
            # Signal type routing
            (
                "vcp"
                if _use_vcp
                else "pocket_pivot"
                if _use_pp
                else "flat_base"
                if _use_fb
                else "breakout"
                if _use_breakout
                else "any"
            ),
            # VCP params
            int(_vcp_ve.get("vcp_pivot_window", 15)) if _use_vcp else 15,
            int(_vcp_ve.get("vcp_atr_short", 10)) if _use_vcp else 10,
            int(_vcp_ve.get("vcp_atr_long", 30)) if _use_vcp else 30,
            float(_vcp_ve.get("vcp_atr_ratio", 0.85)) if _use_vcp else 0.85,
            int(_vcp_ve.get("vcp_volume_dry_periods", 5)) if _use_vcp else 5,
            float(_vcp_ve.get("vcp_depth_max_pct", 15.0)) if _use_vcp else 15.0,
            float(_vcp_ve.get("vcp_pivot_dist_max_pct", 8.0)) if _use_vcp else 8.0,
            bool(_vcp_ve.get("vcp_require_vol_dry", True)) if _use_vcp else True,
            # PP params
            int(_pp_ve.get("pp_vol_lookback", 10)) if _use_pp else 10,
            float(_pp_ve.get("pp_vol_mult", 1.0)) if _use_pp else 1.0,
            # FB params
            int(_fb_ve.get("fb_min_weeks", 5)) if _use_fb else 5,
            float(_fb_ve.get("fb_max_range", 7.0)) if _use_fb else 7.0,
            min_required_days_override=min_days_ui,
            universe_selection_method=universe_selection,
        ):
            st.rerun()

    # ── CACHE TIMINGS (debug) ────────────────────────────────────────
    _dash_cache.render_timing_sidebar()

# --- MAIN PAGE ---
if dashboard_view == "Integrated 2.0":
    _render_dashboard_v2(
        mode=dashboard_mode.lower(),
        system_view=system_view,
        selected_combo_run=None
        if selected_combo_run == "latest"
        else selected_combo_run,
        selected_agent=selected_agent,
    )
else:
    st.title("Institutional Dashboard")

# Calculate results summary if they exist for the top bar
top_net_pnl = 0
_TRADE_EVENTS_PATH = (
    "outputs/backtests/complete_trades_clean.csv"
    if os.path.exists("outputs/backtests/complete_trades_clean.csv")
    else "outputs/backtests/backtest_results.csv"
)
if dashboard_view == "Legacy" and not _trades_df.empty:
    t1, t2, t3, t4, t5, t6, t7, t8 = st.tabs(
        [
            "Performance",
            "Trade Log",
            "QuantStats",
            "Diagnostics",
            "Insights",
            "Market Regime",
            "🎓 Anatomía del Trade",
            "📊 Estrategias",
        ]
    )

    # Scope badge — muestra qué activo/patrón se está visualizando
    if _scope_label != "🌐 Global":
        st.caption(f"Segmento activo: **{_scope_label}** ({_n_view_trades} trades)")

    # --- Fetch Benchmark Data ---
    @st.cache_data(ttl=3600, show_spinner=False)
    def get_benchmark_returns(ticker, start, end):
        """Fetch benchmark returns - tries cache first, then yfinance direct, then SQLite."""
        import yfinance as yf

        s_str = (
            start.strftime("%Y-%m-%d")
            if isinstance(start, datetime)
            else str(start)[:10]
        )
        e_str = end.strftime("%Y-%m-%d") if isinstance(end, datetime) else str(end)[:10]

        # 1. Try yfinance direct (most reliable, always fresh)
        try:
            df = yf.download(
                ticker,
                start=s_str,
                end=e_str,
                auto_adjust=True,
                progress=False,
                timeout=10,
            )
            if df is not None and not df.empty:
                close = df["Close"] if "Close" in df.columns else df.iloc[:, 0]
                if isinstance(close, pd.DataFrame):
                    close = close.iloc[:, 0]
                return close.pct_change().fillna(0)
        except Exception:
            pass

        # 2. Try SQLite cache (reusa conexion existente de _get_ticker_cache)
        try:
            _tc = _get_ticker_cache()
            rows = _tc.conn.execute(
                "SELECT date, close FROM ohlcv_cache WHERE ticker=? AND date BETWEEN ? AND ? ORDER BY date",
                (ticker, s_str, e_str),
            ).fetchall()
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
        # Strategy context banner
        _cur_sig_label = (
            "VCP"
            if _use_vcp
            else "Pocket Pivot"
            if _use_pp
            else "Flat Base"
            if _use_fb
            else "Breakout"
            if _use_breakout
            else "Any"
        )
        _oos_ref = (
            _vcp_oos.get("oos_sharpe")
            if _use_vcp
            else _pp_oos.get("oos_sharpe")
            if _use_pp
            else _fb_oos.get("oos_sharpe")
            if _use_fb
            else None
        )
        _oos_badge = f" | OOS ref: {_oos_ref:.2f}" if _oos_ref else ""
        st.caption(f"Strategy activa: **{_cur_sig_label}**{_oos_badge}")
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

        # --- ML TradeScorer Summary ---
        if _ML_MODEL is not None:
            st.markdown("### 🤖 ML TradeScorer")
            oof_auc = _ML_MODEL.get("oof_auc", 0)
            oof_std = _ML_MODEL.get("oof_auc_std", 0)
            n_trades = _ML_MODEL.get("n_trades", 0)
            positive_rate = _ML_MODEL.get("positive_rate", 0)
            threshold_top30 = _ML_MODEL.get("threshold_top30", 0)
            features = _ML_MODEL.get("features", [])
            feat_imp = _ML_MODEL.get("feature_importance", {})

            col_ml1, col_ml2, col_ml3, col_ml4 = st.columns(4)
            with col_ml1:
                st.metric(
                    "OOF AUC",
                    f"{oof_auc:.3f}",
                    delta=f"±{oof_std:.3f}" if oof_std else None,
                    help="ROC-AUC out-of-fold - >0.55 útil, >0.60 sólido",
                )
            with col_ml2:
                st.metric("Training Trades", f"{n_trades:,}")
            with col_ml3:
                st.metric("Win Rate (train)", f"{positive_rate:.1%}")
            with col_ml4:
                st.metric("Threshold P70", f"{threshold_top30:.2f}")

            # Top features
            if feat_imp:
                top_feats = sorted(feat_imp.items(), key=lambda x: x[1], reverse=True)[
                    :5
                ]
                feat_str = " | ".join([f"{f}: {v:.1f}" for f, v in top_feats])
                st.caption(f"Top features: {feat_str}")
            st.caption(f"Features usadas: {len(features)}")

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

            # Session state cache para QuantStats — evita recalcular en cada rerun.
            # Usa key estable: (min_date, max_date, n_rows, date_sum) para evitar ordenar listas largas.
            _ed = pd.to_datetime(filtered_trades_t1["entry_date"], errors="coerce")
            _ed_num = _ed.view("int64")
            _ed_num = pd.Series(_ed_num).dropna().astype("int64")
            _qs_key = (
                "qs_"
                f"{int(_ed_num.min()) if len(_ed_num) else 0}_"
                f"{int(_ed_num.max()) if len(_ed_num) else 0}_"
                f"{len(filtered_trades_t1)}_"
                f"{int(_ed_num.sum()) if len(_ed_num) else 0}"
            )
            if _qs_key not in st.session_state:
                _analyzer = QuantStatsAnalyzer(
                    trade_log=filtered_trades_t1,
                    initial_capital=equity if "equity" in dir() else 100000,
                    benchmark_ticker=benchmark_ticker,
                )
                st.session_state[_qs_key] = _analyzer.get_quantstats_metrics(
                    benchmark_data=benchmark_returns
                    if not benchmark_returns.empty
                    else None
                )
            qs_metrics = st.session_state[_qs_key]
            analyzer = QuantStatsAnalyzer(
                trade_log=filtered_trades_t1,
                initial_capital=equity if "equity" in dir() else 100000,
                benchmark_ticker=benchmark_ticker,
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
        # MONTE CARLO SIMULATION (Random Draw)
        # ═══════════════════════════════════════════════════════════════════════
        st.markdown("---")
        st.markdown("### 🎲 Monte Carlo Simulation")

        try:
            # Build daily returns series from grouped trades
            if not grouped_trades.empty and "final_exit_date" in grouped_trades.columns:
                # Create daily equity curve from trades
                mc_df = grouped_trades[["final_exit_date", "total_pnl"]].copy()
                mc_df = mc_df.sort_values("final_exit_date")
                mc_df["cumulative_pnl"] = mc_df["total_pnl"].cumsum()

                # Get daily returns (simplified: use trade returns as daily returns)
                # For more accuracy, we'd map to calendar days
                trade_returns = (
                    mc_df["total_pnl"].values / equity
                    if equity > 0
                    else np.zeros(len(mc_df))
                )

                def run_monte_carlo(
                    returns: np.ndarray, n_simulations: int = 1000, n_trades: int = None
                ) -> dict:
                    """Run Monte Carlo simulation using bootstrap resampling."""
                    if len(returns) == 0:
                        return {}

                    n_trades = n_trades or len(returns)

                    # Initialize results arrays
                    final_capitals = np.zeros(n_simulations)
                    total_returns = np.zeros(n_simulations)
                    max_drawdowns = np.zeros(n_simulations)
                    sharpe_ratios = np.zeros(n_simulations)
                    win_rates = np.zeros(n_simulations)

                    np.random.seed(42)  # For reproducibility

                    for i in range(n_simulations):
                        # Random draw with replacement (bootstrap)
                        sampled_indices = np.random.choice(
                            len(returns), size=n_trades, replace=True
                        )
                        sampled_returns = returns[sampled_indices]

                        # Calculate cumulative equity
                        equity_curve = np.cumsum(sampled_returns) + 1.0
                        final_capitals[i] = equity_curve[-1] * equity
                        total_returns[i] = (equity_curve[-1] - 1.0) * 100

                        # Calculate max drawdown
                        peak = np.maximum.accumulate(equity_curve)
                        drawdown = (equity_curve - peak) / peak
                        max_drawdowns[i] = drawdown.min() * 100

                        # Calculate Sharpe ratio (annualized)
                        if sampled_returns.std() > 0:
                            sharpe_ratios[i] = (
                                sampled_returns.mean() / sampled_returns.std()
                            ) * np.sqrt(252)
                        else:
                            sharpe_ratios[i] = 0

                        # Calculate win rate
                        win_rates[i] = (
                            (sampled_returns > 0).sum() / len(sampled_returns) * 100
                        )

                    return {
                        "final_capital": final_capitals,
                        "total_return": total_returns,
                        "max_drawdown": max_drawdowns,
                        "sharpe_ratio": sharpe_ratios,
                        "win_rate": win_rates,
                    }

                # UI for Monte Carlo parameters
                mc_col1, mc_col2, mc_col3 = st.columns(3)

                with mc_col1:
                    mc_simulations = st.slider(
                        "Simulations",
                        min_value=100,
                        max_value=5000,
                        value=1000,
                        step=100,
                        help="Number of Monte Carlo iterations",
                    )

                with mc_col2:
                    mc_resample = st.checkbox(
                        "Resample N trades",
                        value=False,
                        help="If enabled, resample same number of trades as original",
                    )

                with mc_col3:
                    if st.button("Run Monte Carlo", type="primary"):
                        mc_key = f"mc_results_{mc_simulations}_{mc_resample}"
                        if mc_key not in st.session_state:
                            with st.spinner("Running Monte Carlo simulations..."):
                                n_trades_val = (
                                    len(trade_returns) if mc_resample else None
                                )
                                mc_results = run_monte_carlo(
                                    trade_returns,
                                    n_simulations=mc_simulations,
                                    n_trades=n_trades_val,
                                )
                                st.session_state[mc_key] = mc_results

                # Display results if available
                mc_results = st.session_state.get(
                    f"mc_results_{mc_simulations}_{mc_resample}"
                )

                if mc_results and len(mc_results.get("final_capital", [])) > 0:
                    st.success(f"Completed {mc_simulations:,} simulations")

                    # Calculate percentiles
                    p10 = np.percentile(mc_results["total_return"], 10)
                    p50 = np.percentile(mc_results["total_return"], 50)
                    p90 = np.percentile(mc_results["total_return"], 90)

                    dd_p10 = np.percentile(mc_results["max_drawdown"], 10)
                    dd_p50 = np.percentile(mc_results["max_drawdown"], 50)
                    dd_p90 = np.percentile(mc_results["max_drawdown"], 90)

                    sharpe_p10 = np.percentile(mc_results["sharpe_ratio"], 10)
                    sharpe_p50 = np.percentile(mc_results["sharpe_ratio"], 50)
                    sharpe_p90 = np.percentile(mc_results["sharpe_ratio"], 90)

                    wr_p10 = np.percentile(mc_results["win_rate"], 10)
                    wr_p50 = np.percentile(mc_results["win_rate"], 50)
                    wr_p90 = np.percentile(mc_results["win_rate"], 90)

                    # Display summary metrics with color rules
                    st.markdown("#### Monte Carlo Results Summary")

                    mc_summary_cols = st.columns(4)

                    with mc_summary_cols[0]:
                        st.markdown("**Return Distribution (%)**")
                        # Color based on P10/P90
                        p10_color = "green" if p10 > 0 else "red"
                        p90_color = "green" if p90 > 0 else "red"
                        st.markdown(
                            f"<span style='color:#ff6b6b'>P10: {p10:+.1f}%</span> | "
                            f"P50: <span style='color:#00ffa3'>{p50:+.1f}%</span> | "
                            f"<span style='color:{p90_color}'>P90: {p90:+.1f}%</span>",
                            unsafe_allow_html=True,
                        )

                    with mc_summary_cols[1]:
                        st.markdown("**Max Drawdown Distribution (%)**")
                        dd_color_p10 = (
                            "green"
                            if abs(dd_p10) < 20
                            else ("orange" if abs(dd_p10) < 30 else "red")
                        )
                        dd_color_p90 = (
                            "green"
                            if abs(dd_p90) < 20
                            else ("orange" if abs(dd_p90) < 30 else "red")
                        )
                        st.markdown(
                            f"P10: <span style='color:{dd_color_p10}'>{dd_p10:.1f}%</span> | "
                            f"P50: <span style='color:#00ffa3'>{dd_p50:.1f}%</span> | "
                            f"P90: <span style='color:{dd_color_p90}'>{dd_p90:.1f}%</span>",
                            unsafe_allow_html=True,
                        )

                    with mc_summary_cols[2]:
                        st.markdown("**Sharpe Ratio Distribution**")
                        sharpe_color_p10 = (
                            "green"
                            if sharpe_p10 > 1.0
                            else ("orange" if sharpe_p10 > 0.5 else "red")
                        )
                        sharpe_color_p90 = (
                            "green"
                            if sharpe_p90 > 1.0
                            else ("orange" if sharpe_p90 > 0.5 else "red")
                        )
                        st.markdown(
                            f"P10: <span style='color:{sharpe_color_p10}'>{sharpe_p10:.2f}</span> | "
                            f"P50: <span style='color:#00ffa3'>{sharpe_p50:.2f}</span> | "
                            f"P90: <span style='color:{sharpe_color_p90}'>{sharpe_p90:.2f}</span>",
                            unsafe_allow_html=True,
                        )

                    with mc_summary_cols[3]:
                        st.markdown("**Win Rate Distribution (%)**")
                        wr_color_p10 = (
                            "green"
                            if wr_p10 > 50
                            else ("orange" if wr_p10 > 40 else "red")
                        )
                        wr_color_p90 = (
                            "green"
                            if wr_p90 > 50
                            else ("orange" if wr_p90 > 40 else "red")
                        )
                        st.markdown(
                            f"P10: <span style='color:{wr_color_p10}'>{wr_p10:.1f}%</span> | "
                            f"P50: <span style='color:#00ffa3'>{wr_p50:.1f}%</span> | "
                            f"P90: <span style='color:{wr_color_p90}'>{wr_p90:.1f}%</span>",
                            unsafe_allow_html=True,
                        )

                    # Histograms
                    st.markdown("#### Distribution Histograms")

                    hist_col1, hist_col2 = st.columns(2)

                    with hist_col1:
                        fig_ret = go.Figure()
                        fig_ret.add_trace(
                            go.Histogram(
                                x=mc_results["total_return"],
                                nbinsx=30,
                                marker_color="#00ffa3",
                                name="Return %",
                            )
                        )
                        # Add vertical lines for percentiles
                        fig_ret.add_vline(
                            x=p10,
                            line_dash="dash",
                            line_color="#ff6b6b",
                            annotation_text="P10",
                        )
                        fig_ret.add_vline(
                            x=p50,
                            line_dash="solid",
                            line_color="#00ffa3",
                            annotation_text="P50",
                        )
                        fig_ret.add_vline(
                            x=p90,
                            line_dash="dash",
                            line_color="#ff6b6b",
                            annotation_text="P90",
                        )
                        fig_ret.update_layout(
                            title="Return Distribution (%)",
                            template="plotly_dark",
                            height=300,
                            xaxis_title="Return (%)",
                            yaxis_title="Frequency",
                        )
                        st.plotly_chart(fig_ret, use_container_width=True)

                    with hist_col2:
                        fig_dd = go.Figure()
                        fig_dd.add_trace(
                            go.Histogram(
                                x=mc_results["max_drawdown"],
                                nbinsx=30,
                                marker_color="#ff6b6b",
                                name="Max DD %",
                            )
                        )
                        fig_dd.add_vline(
                            x=dd_p10,
                            line_dash="dash",
                            line_color="#ffa500",
                            annotation_text="P10",
                        )
                        fig_dd.add_vline(
                            x=dd_p50,
                            line_dash="solid",
                            line_color="#00ffa3",
                            annotation_text="P50",
                        )
                        fig_dd.add_vline(
                            x=dd_p90,
                            line_dash="dash",
                            line_color="#d50000",
                            annotation_text="P90",
                        )
                        fig_dd.update_layout(
                            title="Max Drawdown Distribution (%)",
                            template="plotly_dark",
                            height=300,
                            xaxis_title="Max Drawdown (%)",
                            yaxis_title="Frequency",
                        )
                        st.plotly_chart(fig_dd, use_container_width=True)

                    hist_col3, hist_col4 = st.columns(2)

                    with hist_col3:
                        fig_sharpe = go.Figure()
                        fig_sharpe.add_trace(
                            go.Histogram(
                                x=mc_results["sharpe_ratio"],
                                nbinsx=30,
                                marker_color="#00d1ff",
                                name="Sharpe",
                            )
                        )
                        fig_sharpe.add_vline(
                            x=sharpe_p10,
                            line_dash="dash",
                            line_color="#ffa500",
                            annotation_text="P10",
                        )
                        fig_sharpe.add_vline(
                            x=sharpe_p50,
                            line_dash="solid",
                            line_color="#00ffa3",
                            annotation_text="P50",
                        )
                        fig_sharpe.add_vline(
                            x=sharpe_p90,
                            line_dash="dash",
                            line_color="#00ffa3",
                            annotation_text="P90",
                        )
                        fig_sharpe.update_layout(
                            title="Sharpe Ratio Distribution",
                            template="plotly_dark",
                            height=300,
                            xaxis_title="Sharpe Ratio",
                            yaxis_title="Frequency",
                        )
                        st.plotly_chart(fig_sharpe, use_container_width=True)

                    with hist_col4:
                        fig_wr = go.Figure()
                        fig_wr.add_trace(
                            go.Histogram(
                                x=mc_results["win_rate"],
                                nbinsx=30,
                                marker_color="#ffa500",
                                name="Win Rate %",
                            )
                        )
                        fig_wr.add_vline(
                            x=wr_p10,
                            line_dash="dash",
                            line_color="#ff6b6b",
                            annotation_text="P10",
                        )
                        fig_wr.add_vline(
                            x=wr_p50,
                            line_dash="solid",
                            line_color="#00ffa3",
                            annotation_text="P50",
                        )
                        fig_wr.add_vline(
                            x=wr_p90,
                            line_dash="dash",
                            line_color="#00ffa3",
                            annotation_text="P90",
                        )
                        fig_wr.update_layout(
                            title="Win Rate Distribution (%)",
                            template="plotly_dark",
                            height=300,
                            xaxis_title="Win Rate (%)",
                            yaxis_title="Frequency",
                        )
                        st.plotly_chart(fig_wr, use_container_width=True)

                    # Interpretation
                    st.markdown("#### Monte Carlo Interpretation")
                    if p10 > 0 and p90 > 0:
                        st.success(
                            f"✅ **Resultado robusto:** El P10 ({p10:+.1f}%) es positivo, "
                            f"indicando que incluso en el escenario pesimista la estrategia genera retornos."
                        )
                    elif p90 < 0:
                        st.error(
                            f"⚠️ **Resultado frágil:** El P90 ({p90:+.1f}%) es negativo, "
                            f"la estrategia puede perder en cualquier escenario."
                        )
                    else:
                        st.warning(
                            f"⚠️ **Resultado mixto:** P10 ({p10:+.1f}%) negativo, P90 ({p90:+.1f}%) positivo. "
                            f"La estrategia tiene variabilidad significativa."
                        )

                    if abs(dd_p90) > 30:
                        st.warning(
                            f"⚠️ **Drawdown riesgo:** El P90 del drawdown es {dd_p90:.1f}%, "
                            f"indicando potencial de pérdidas significativas en escenarios adversos."
                        )
                    else:
                        st.success(
                            f"✅ **Control de riesgo:** El P90 del drawdown ({dd_p90:.1f}%) está controlado."
                        )
                else:
                    st.info("Click 'Run Monte Carlo' to execute simulations")

            else:
                st.info("No grouped trades available for Monte Carlo simulation")

        except Exception as e:
            st.warning(f"Monte Carlo simulation unavailable: {e}")

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
        # ML Model Info
        if _ML_MODEL is not None:
            oof_auc = _ML_MODEL.get("oof_auc", 0)
            n_trades = _ML_MODEL.get("n_trades", 0)
            st.info(
                f"🤖 **TradeScorer ML**: OOF AUC={oof_auc:.3f} | Trained on {n_trades:,} trades | Ordena por 'High ML Score' para ver predicciones"
            )
        else:
            st.caption(
                "💡 Ejecuta `python3 train_trade_scorer.py` para entrenar el modelo ML"
            )

        # Quick Sort / Filter Options
        st.markdown("### 🔍 Filter & Sort")
        q_col1, q_col2, q_col3 = st.columns(3)

        with q_col1:
            view_mode = st.radio(
                "View Mode", ["Complete Trades", "All Partial Exits"], horizontal=True
            )

        with q_col2:
            sort_options = [
                "Latest First",
                "Oldest First",
                "Top Winners ($)",
                "Top Losers ($)",
                "High R-Multiple",
                "High Entry Score",
                "Low Entry Score",
            ]
            if _ML_MODEL is not None:
                sort_options.append("High ML Score")
            quick_sort = st.selectbox(
                "Quick Sort (Entire Dataset)",
                sort_options,
                index=0,
            )

        with q_col3:
            show_all = st.checkbox(
                "Show All (Disable Pagination)",
                value=False,
                help="May be slow for >1000 trades",
            )

        if view_mode == "Complete Trades":
            if grouped_trades.empty:
                st.info("No hay trades agrupados. Corré un backtest primero.")
                display_df = pd.DataFrame()
            else:
                display_source = grouped_trades.copy()
                display_source = display_source.rename(columns={"ticker": "symbol"})

                # Apply ML scoring if model available
                if _ML_MODEL is not None:
                    display_source = score_trades_ml(display_source, _ML_MODEL)

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
                if _ML_MODEL is not None and "ml_score" in display_source.columns:
                    show_cols.append("ml_score")

                # Ensure RS percentile exists, fallback to 0 if missing
                if "rs_percentile" not in display_source.columns:
                    display_source["rs_percentile"] = 0

                # Filtrar solo columnas que existen
                show_cols = [c for c in show_cols if c in display_source.columns]

                # Sortear sobre display_source completo antes de filtrar cols
                _has_exit_date = "final_exit_date" in display_source.columns
                _has_pnl = "total_pnl" in display_source.columns
                _sort_col_date = "final_exit_date" if _has_exit_date else None

                if quick_sort == "Latest First" and _sort_col_date:
                    display_df = display_source.sort_values(
                        _sort_col_date, ascending=False
                    )[show_cols]
                elif quick_sort == "Oldest First" and _sort_col_date:
                    display_df = display_source.sort_values(
                        _sort_col_date, ascending=True
                    )[show_cols]
                elif quick_sort == "Top Winners ($)" and _has_pnl:
                    display_df = display_source.sort_values(
                        "total_pnl", ascending=False
                    )[show_cols]
                elif quick_sort == "Top Losers ($)" and _has_pnl:
                    display_df = display_source.sort_values(
                        "total_pnl", ascending=True
                    )[show_cols]
                elif (
                    quick_sort == "High R-Multiple"
                    and "r_multiple" in display_source.columns
                ):
                    display_df = display_source.sort_values(
                        "r_multiple", ascending=False
                    )[show_cols]
                elif (
                    quick_sort == "High Entry Score"
                    and "entry_score" in display_source.columns
                ):
                    display_df = display_source.sort_values(
                        "entry_score", ascending=False
                    )[show_cols]
                elif (
                    quick_sort == "Low Entry Score"
                    and "entry_score" in display_source.columns
                ):
                    display_df = display_source.sort_values(
                        "entry_score", ascending=True
                    )[show_cols]
                elif (
                    quick_sort == "High ML Score"
                    and "ml_score" in display_source.columns
                ):
                    display_df = display_source.sort_values(
                        "ml_score", ascending=False
                    )[show_cols]
                else:
                    if _sort_col_date:
                        display_df = display_source.sort_values(
                            _sort_col_date, ascending=False
                        )[show_cols]
                    else:
                        display_df = display_source[show_cols]
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

        _sym_col_name = (
            "symbol"
            if "symbol" in df.columns
            else ("ticker" if "ticker" in df.columns else None)
        )
        _symbol_list = (
            sorted(df[_sym_col_name].dropna().unique().tolist())
            if _sym_col_name
            else []
        )
        selected_symbol = st.selectbox("Filter Symbol", ["All"] + _symbol_list)
        if selected_symbol != "All" and _sym_col_name:
            display_df = display_df[display_df[_sym_col_name] == selected_symbol]

        # Debug badge: show row count before date filter
        _pre_filter_count = len(display_df)

        # Optional date range filter - disabled by default to avoid silently hiding trades
        apply_date_filter = st.checkbox(
            "Apply Date Range Filter",
            value=False,
            help="Filter trades by the Start/End dates from sidebar. "
            "When disabled, shows all available trades.",
        )
        if apply_date_filter and start_date and end_date:
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

        # Show debug badge if filtering changed row count
        _post_filter_count = len(display_df)
        if _pre_filter_count > 0:
            if _post_filter_count == 0:
                st.warning(
                    f"⚠️ **0 trades after filtering** ({_pre_filter_count} available). "
                    f"Enable 'Apply Date Range Filter' to see all trades, or adjust the sidebar dates."
                )
                # Show available date range for diagnosis
                _avail_dates = []
                for _dc in ["entry_date", "exit_date", "final_exit_date"]:
                    if _dc in df.columns:
                        _avail_dates.append(_dc)
                if _avail_dates:
                    _dcol = _avail_dates[0]
                    _dmin = pd.to_datetime(df[_dcol]).min().strftime("%Y-%m-%d")
                    _dmax = pd.to_datetime(df[_dcol]).max().strftime("%Y-%m-%d")
                    st.caption(f"Available trade dates: {_dmin} to {_dmax}")
            elif _post_filter_count < _pre_filter_count:
                st.caption(
                    f"Showing {_post_filter_count}/{_pre_filter_count} trades "
                    f"(date filter applied)"
                )

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
        # Add ML score column config if present
        if "ml_score" in display_df_display.columns:
            _ml_oof_auc = _ML_MODEL.get("oof_auc", 0) if _ML_MODEL is not None else 0
            log_column_config["ml_score"] = st.column_config.ProgressColumn(
                "ML Score",
                help=f"P(winner) segun LightGBM - OOF AUC: {_ml_oof_auc:.3f}",
                format=".0%",
                min_value=0.0,
                max_value=1.0,
            )

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
                    sym = row.get("symbol", row.get("ticker", "Unknown"))
                    entry_dt = row.get("entry_date", row.get("final_exit_date", ""))
                    if hasattr(entry_dt, "date"):
                        entry_dt = entry_dt.date()
                    pnl = row.get("total_pnl", 0)
                    return f"{sym} - {entry_dt} (${pnl:,.2f})"

                source_df = display_source
            else:

                def format_fn(i):
                    row = df.loc[i]
                    sym = row.get("symbol", row.get("ticker", "Unknown"))
                    entry_dt = row.get("entry_date", "")
                    if hasattr(entry_dt, "date"):
                        entry_dt = entry_dt.date()
                    phase = row.get("exit_phase", "")
                    pnl = row.get("pnl", 0)
                    return f"{sym} - {entry_dt} ({phase} - ${pnl:,.2f})"

                source_df = df

            trade_idx = st.selectbox(
                "Select Trade to Visualize (Follows filters/sort above)",
                trade_options,
                format_func=format_fn,
            )

            if st.button("Show Detailed Chart"):
                dash = InteractiveDashboard(
                    df=df
                )  # PERF Item 6: evita re-leer CSV desde disco

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
                    _c2.metric("Max DD", f"{_qs_m.get('max_drawdown', 0) * 100:.2f}%")
                    _c3.metric("CAGR", f"{_qs_m.get('cagr', 0) * 100:.2f}%")
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

            if len(strat_returns) > 0 and isinstance(
                strat_returns.index, pd.DatetimeIndex
            ):
                monthly_ret = qs.stats.monthly_returns(strat_returns) * 100
                # Format for display
                st.dataframe(
                    monthly_ret.style.background_gradient(
                        cmap="RdYlGn", axis=None
                    ).format("{:.2f}%"),
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
                    str(start_date),
                    str(end_date),
                    cache=get_ticker_cache(),
                    offline=True,
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
                    exposure_quality = (
                        "excelente"
                        if exposure < 15
                        else "moderado"
                        if exposure < 30
                        else "alto"
                    )
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
                    * **Valor Institucional:** {"Alta resiliencia buscada por fondos" if beta_val < 0 else "Diversificación moderada"}.
                    """)
                else:
                    st.info("**Beta**")
                    st.write(
                        "Métrica no disponible o beta cercano a cero (estrategia neutral)."
                    )
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
        st.caption(
            f"Parámetros activos cargados desde: `config/production_config.json`"
        )

        col_i1, col_i2 = st.columns(2)

        with col_i1:
            st.markdown("### 🎯 Tier 1: Estrategia Core")
            st.markdown(f"**Take Profit Multi-Fase:**")

            tp1_pct = _t1.get("tp1_pct", 0) * 100
            tp2_pct = _t1.get("tp2_pct", 0) * 100
            runner_pct = _t1.get("runner_pct", 0) * 100
            tp1_r = _t1.get("tp1_r", 0)
            tp2_r = _t1.get("tp2_r", 0)

            st.info(f"**TP1:** {tp1_pct:.0f}% de posición @ {tp1_r:.1f}R")
            st.info(f"**TP2:** {tp2_pct:.0f}% de posición @ {tp2_r:.1f}R")
            st.info(
                f"**Runner:** {runner_pct:.0f}% con EMA8/EMA21 crossover + ATR trailing"
            )

            st.markdown("**Gestión de Riesgo:**")
            max_stop = _t1.get("max_stop_pct", 0) * 100
            risk_dollars = _t1.get("risk_dollars", 0)
            st.info(f"Stop Loss Máximo: {max_stop:.1f}%")
            st.info(f"Riesgo por Trade: ${risk_dollars:.0f}")

            st.markdown("---")
            st.markdown("### 🔬 Tier 2: Filtros de Calidad")

            min_rvol = _t2.get("min_rvol", 0)
            max_dist_sma20 = _t2.get("max_dist_sma20", 0)
            min_adr = _t2.get("min_adr", 0)
            min_dollar_vol = _t2.get("min_dollar_volume", 0)

            st.info(f"**RVOL Mínimo:** {min_rvol:.1f}x (volumen relativo)")
            st.info(
                f"**Distancia Max SMA20:** {max_dist_sma20:.1f}% (evita sobreextensión)"
            )
            st.info(f"**ADR Mínimo:** {min_adr:.2f}% (rango promedio diario)")
            st.info(f"**Volumen Mínimo:** ${min_dollar_vol:,.0f} (liquidez)")

        with col_i2:
            st.markdown("### 🛡️ Tier 3: Gestión de Riesgo")

            rvol_danger = _t3.get("rvol_danger", 0)
            rvol_danger_size = _t3.get("rvol_danger_size", 0) * 100
            rvol_warning = _t3.get("rvol_warning", 0)
            rvol_warning_size = _t3.get("rvol_warning_size", 0) * 100
            max_exposure = _t3.get("max_exposure_pct", 0) * 100
            max_position = _t3.get("max_position_pct", 0) * 100

            st.markdown("**Ajustes por Volatilidad:**")
            st.warning(
                f"**RVOL Peligro (≥{rvol_danger:.1f}x):** Reduce size a {rvol_danger_size:.0f}%"
            )
            st.warning(
                f"**RVOL Alerta (≥{rvol_warning:.1f}x):** Reduce size a {rvol_warning_size:.0f}%"
            )

            st.markdown("**Límites de Cartera:**")
            st.info(f"**Max Exposure Total:** {max_exposure:.0f}% del capital")
            st.info(f"**Max Posición Individual:** {max_position:.0f}% del capital")

            st.markdown("---")
            st.markdown("### 🌊 Market Regime Filter")

            require_spy_sma50 = _mr.get("require_spy_above_sma50", False)
            max_vix = _mr.get("max_vix", 40)

            st.info(
                f"**SPY > SMA50:** {'✅ Requerido' if require_spy_sma50 else '❌ No requerido'}"
            )
            st.info(f"**VIX Máximo:** {max_vix:.0f} (por encima = BLOCKED)")

            st.markdown("**Reglas de Stage:**")
            st.success("Stage 1 (Bull): 100% size")
            st.warning("Stage 2 (Consolidation): 75% size")
            st.error("Stage 3/4 (Distribution/Bear): BLOCKED")

            if _perf:
                st.markdown("---")
                st.markdown("### 📈 Performance de Validación")
                st.caption("Resultados del último proceso de optimización")

                val_sharpe = _perf.get("sharpe_ratio", 0)
                val_wr = _perf.get("win_rate_pct", 0)
                val_trades = _perf.get("total_trades", 0)
                val_return = _perf.get("total_return_pct", 0)

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
                    blocked_transitions = len(
                        [
                            t
                            for t in transitions
                            if "STAGE_3" in t["Nuevo Stage"]
                            or "STAGE_4" in t["Nuevo Stage"]
                        ]
                    )

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
        st.caption(
            "Aprende cómo funciona el sistema analizando trades reales paso a paso"
        )

        if not grouped_trades.empty:
            # Trade selector
            st.markdown("### 📍 Selecciona un Trade para Analizar")

            # Create dropdown with most interesting trades
            interesting_trades = grouped_trades.copy()
            interesting_trades["description"] = (
                interesting_trades["ticker"].astype(str)
                + " | "
                + interesting_trades["entry_date"].astype(str)
                + " → "
                + interesting_trades["final_exit_date"].astype(str)
                + " | PnL: $"
                + interesting_trades["total_pnl"].round(2).astype(str)
            )

            # Sort by absolute PnL to show most impactful trades
            interesting_trades["abs_pnl"] = interesting_trades["total_pnl"].abs()
            interesting_trades = interesting_trades.sort_values(
                "abs_pnl", ascending=False
            )

            selected_trade_desc = st.selectbox(
                "Trade:",
                interesting_trades["description"].tolist(),
                help="Ordenados por impacto (PnL absoluto)",
            )

            # Get the selected trade
            selected_idx = interesting_trades[
                interesting_trades["description"] == selected_trade_desc
            ].index[0]
            trade = interesting_trades.loc[selected_idx]

            # Display trade overview
            st.markdown("---")
            outcome_emoji = "✅" if trade["total_pnl"] > 0 else "❌"
            st.markdown(f"## {outcome_emoji} {trade['ticker']} - Análisis Completo")

            # Key metrics in columns
            m1, m2, m3, m4, m5 = st.columns(5)
            m1.metric("Entrada", f"${trade['entry_price']:.2f}")
            m2.metric("PnL Total", f"${trade['total_pnl']:.2f}")
            m3.metric("Días en Trade", f"{int(trade['hold_days'])}")
            m4.metric("Entry Score", f"{trade.get('entry_score', 0):.2f}")
            m5.metric(
                "R-Multiple",
                f"{trade.get('r_multiple', 0):+.2f}R"
                if "r_multiple" in trade
                else "N/A",
            )

            # PHASE 1: PRE-ENTRADA
            st.markdown("---")
            st.markdown("### 🔍 FASE 1: Pre-Entrada (Screening)")

            col_pre1, col_pre2 = st.columns(2)

            with col_pre1:
                st.markdown("#### ¿Qué buscaba el sistema?")
                st.info(f"""
                **Patrón:** {trade.get("pattern_type", "N/A")}
                
                **Criterios de selección:**
                1. **Base consolidada** - Precio entre soporte y resistencia
                2. **AVWAP por debajo** - Precio no sobreextendido
                3. **Volumen institucional** - Detecta acumulación
                4. **Momentum relativo** - RS Percentile: {trade.get("rs_percentile", 0):.0f}
                """)

            with col_pre2:
                st.markdown("#### Filtros que Pasó")
                # Show that this trade passed all filters
                st.success(f"""
                ✅ **Tier 1 (Market Safety)** - Régimen de mercado favorable
                ✅ **Tier 2 (Quality)** - Calidad técnica suficiente
                ✅ **Tier 3 (Risk)** - Risk/Reward aceptable
                
                **Entry Score:** {trade.get("entry_score", 0):.2f}/1.0
                """)

                if trade.get("entry_score", 0) >= 0.7:
                    st.write("🔥 **Score alto** - Setup de muy alta calidad")
                elif trade.get("entry_score", 0) >= 0.4:
                    st.write("⚠️ **Score medio** - Setup aceptable pero no ideal")
                else:
                    st.write("⚡ **Score bajo** - Setup marginal, riesgo elevado")

            # PHASE 2: ENTRADA
            st.markdown("---")
            st.markdown("### 🚀 FASE 2: Entrada (Trigger)")

            col_ent1, col_ent2 = st.columns(2)

            with col_ent1:
                st.markdown("#### El Momento de Entrada")
                entry_date_str = (
                    trade["entry_date"].strftime("%Y-%m-%d")
                    if hasattr(trade["entry_date"], "strftime")
                    else str(trade["entry_date"])
                )
                st.write(f"""
                **Fecha:** {entry_date_str}
                **Precio:** ${trade["entry_price"]:.2f}
                **Shares:** {int(trade.get("total_shares", 0))}
                **Capital Arriesgado:** ${int(trade.get("total_shares", 0) * trade["entry_price"]):.0f}
                
                **Trigger:**
                El precio rompió por encima del nivel de resistencia de la base consolidada,
                confirmando que hay compradores institucionales entrando.
                """)

            with col_ent2:
                st.markdown("#### Position Sizing Dinámico")
                shares = int(trade.get("total_shares", 0))
                entry_price = trade["entry_price"]
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
                exit_info = trade.get("exit_phases", "N/A")
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

                if trade["total_pnl"] > 0:
                    st.success(f"""
                    ✅ **Trade Ganador** (+${trade["total_pnl"]:.2f})
                    
                    El precio continuó en la dirección esperada y el sistema
                    ejecutó las salidas según el plan. Las múltiples fases
                    permitieron capturar diferentes partes del movimiento.
                    """)
                else:
                    st.error(f"""
                    ❌ **Trade Perdedor** (${trade["total_pnl"]:.2f})
                    
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

                win_rate_pct = (
                    (grouped_trades["total_pnl"] > 0).sum() / len(grouped_trades) * 100
                )
                avg_win = (
                    grouped_trades[grouped_trades["total_pnl"] > 0]["total_pnl"].mean()
                    if (grouped_trades["total_pnl"] > 0).any()
                    else 0
                )
                avg_loss = (
                    grouped_trades[grouped_trades["total_pnl"] < 0]["total_pnl"].mean()
                    if (grouped_trades["total_pnl"] < 0).any()
                    else 0
                )

                st.info(f"""
                **Contexto del sistema completo:**
                * Win Rate: {win_rate_pct:.1f}%
                * Avg Win: ${avg_win:.2f}
                * Avg Loss: ${avg_loss:.2f}
                * Total Trades: {len(grouped_trades)}
                
                Este trade {"contribuyó positivamente" if trade["total_pnl"] > 0 else "fue parte del costo de hacer negocios"}.
                """)

            with col_pm2:
                st.markdown("#### Lecciones Clave")

                # Dynamic lessons based on trade characteristics
                lessons = []

                if trade.get("entry_score", 0) >= 0.7 and trade["total_pnl"] > 0:
                    lessons.append(
                        "✅ **Score alto + ganador** - Sistema funcionó como esperado"
                    )
                elif trade.get("entry_score", 0) < 0.4 and trade["total_pnl"] < 0:
                    lessons.append(
                        "⚠️ **Score bajo + perdedor** - Confirmación de que scores bajos son más riesgosos"
                    )
                elif trade.get("entry_score", 0) >= 0.7 and trade["total_pnl"] < 0:
                    lessons.append(
                        "📚 **Score alto pero perdió** - Incluso buenos setups fallan (probabilidades)"
                    )
                elif trade.get("entry_score", 0) < 0.4 and trade["total_pnl"] > 0:
                    lessons.append(
                        "🎲 **Score bajo pero ganó** - Caso fortuito, no replicable"
                    )

                if trade["hold_days"] < 3:
                    lessons.append(
                        "⚡ **Trade corto** - Sistema detectó debilidad y cortó rápido"
                    )
                elif trade["hold_days"] > 10:
                    lessons.append(
                        "🏃 **Trade extendido** - El momentum se mantuvo varios días"
                    )

                if trade.get("rs_percentile", 0) >= 80:
                    lessons.append(
                        "🚀 **RS alto** - Líder relativo del mercado (IBD style)"
                    )

                for lesson in lessons:
                    st.write(lesson)

                if not lessons:
                    st.write("📊 Trade con características estándar del sistema")

            # EDUCATIONAL CONCEPTS
            st.markdown("---")
            st.markdown("### 📚 Conceptos Clave del Sistema")

            edu_tabs = st.tabs(
                [
                    "Triad Protocol",
                    "Entry Score",
                    "R-Multiple",
                    "Market Regime",
                    "Position Sizing",
                ]
            )

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
            if "trade_df_for_grouper" in dir() and not trade_df_for_grouper.empty:
                # Find all partial exits for this trade
                partial_exits = trade_df_for_grouper[
                    (trade_df_for_grouper["ticker"] == trade["ticker"])
                    & (trade_df_for_grouper["entry_date"] == trade["entry_date"])
                ].copy()

                if not partial_exits.empty:
                    partial_exits = partial_exits.sort_values("exit_date")

                    timeline_data = []
                    timeline_data.append(
                        {
                            "Evento": "🟢 ENTRADA",
                            "Fecha": entry_date_str,
                            "Precio": f"${trade['entry_price']:.2f}",
                            "Shares": f"{int(trade['total_shares'])}",
                            "PnL": "-",
                            "Notas": "Apertura de posición completa",
                        }
                    )

                    for idx, exit_row in partial_exits.iterrows():
                        exit_date_str = (
                            exit_row["exit_date"].strftime("%Y-%m-%d")
                            if hasattr(exit_row["exit_date"], "strftime")
                            else str(exit_row["exit_date"])
                        )
                        exit_price = exit_row.get("exit_price", 0)
                        pnl = exit_row.get("pnl", 0)
                        shares_exited = exit_row.get("shares", 0)
                        exit_reason = exit_row.get("exit_reason", "N/A")

                        emoji = (
                            "🎯"
                            if "TP" in str(exit_reason)
                            else "🛑"
                            if pnl < 0
                            else "📤"
                        )

                        timeline_data.append(
                            {
                                "Evento": f"{emoji} SALIDA",
                                "Fecha": exit_date_str,
                                "Precio": f"${exit_price:.2f}",
                                "Shares": f"{int(shares_exited)}",
                                "PnL": f"${pnl:.2f}",
                                "Notas": str(exit_reason),
                            }
                        )

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

                if trade.get("entry_score", 0) >= 0.6:
                    positives.append("✅ Identificó setup de calidad")
                if trade.get("rs_percentile", 0) >= 70:
                    positives.append("✅ Seleccionó líder relativo fuerte")
                if trade["hold_days"] >= 2:
                    positives.append("✅ Dio espacio al trade para desarrollarse")
                if trade["total_pnl"] > 0:
                    positives.append("✅ Ejecutó plan de salida correctamente")
                else:
                    positives.append("✅ Cortó pérdida según plan (gestión de riesgo)")

                for p in positives:
                    st.write(p)

            with final_col2:
                st.markdown("#### Puntos de Mejora")
                improvements = []

                if trade.get("entry_score", 0) < 0.4:
                    improvements.append(
                        "⚠️ Entry score bajo - considerar umbral más alto"
                    )
                if trade.get("rs_percentile", 0) < 50:
                    improvements.append("⚠️ RS bajo - no era líder de mercado")
                if trade["total_pnl"] < 0 and trade["hold_days"] < 2:
                    improvements.append("⚠️ Stop muy ajustado o entrada prematura")
                if abs(trade["total_pnl"]) < 50:
                    improvements.append(
                        "⚠️ PnL pequeño - ajustar risk/size o skip setups débiles"
                    )

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
                rank_pnl = (grouped_trades["total_pnl"] >= trade["total_pnl"]).sum()
                st.metric(
                    "Ranking",
                    f"{rank_pnl} / {len(grouped_trades)}",
                    f"Top {rank_pnl / len(grouped_trades) * 100:.0f}%",
                )

            with comp_col2:
                st.markdown("#### Por Entry Score")
                if "entry_score" in grouped_trades.columns:
                    rank_score = (
                        grouped_trades["entry_score"] >= trade.get("entry_score", 0)
                    ).sum()
                    st.metric(
                        "Ranking",
                        f"{rank_score} / {len(grouped_trades)}",
                        f"Top {rank_score / len(grouped_trades) * 100:.0f}%",
                    )
                else:
                    st.write("N/A")

            with comp_col3:
                st.markdown("#### Por Días en Hold")
                rank_hold = (grouped_trades["hold_days"] >= trade["hold_days"]).sum()
                st.metric(
                    "Ranking",
                    f"{rank_hold} / {len(grouped_trades)}",
                    f"Top {rank_hold / len(grouped_trades) * 100:.0f}%",
                )

        else:
            st.info("No hay trades disponibles. Ejecuta un backtest primero.")

    with t8:
        st.markdown("### Estrategias disponibles")
        st.caption(
            "Comparativa de configs optimizadas. Los parámetros son los golden config actuales."
        )

        import json as _json_t8
        import pandas as _pd_t8

        def _load_cfg(path, signal):
            try:
                c = _json_t8.load(open(path))
                t1_ = c.get("tier1_strategy", {})
                t2_ = c.get("tier2_filters", {})
                oos = c.get("_oos_validation", {})
                ve = c.get("vcp_entry", c.get("extra_params", {}))
                return {
                    "Signal": signal,
                    "TP1 (R)": t1_.get("tp1_r", "-"),
                    "TP2 (R)": t1_.get("tp2_r", "-"),
                    "TP1 %": f"{t1_.get('tp1_pct', 0) * 100:.0f}%",
                    "Runner %": f"{t1_.get('runner_pct', 0) * 100:.0f}%",
                    "Max Stop": f"{t1_.get('max_stop_pct', 0) * 100:.1f}%",
                    "Min RVOL": t2_.get("min_rvol", "-"),
                    "Max Dist SMA20": f"{t2_.get('max_dist_sma20', '-')}%",
                    "RS Filter": "ON" if t2_.get("use_rs_percentile") else "OFF",
                    "OOS Sharpe": oos.get("oos_sharpe", "sin validar"),
                    "OOS WR": f"{oos.get('oos_win_rate', 0):.0f}%"
                    if oos.get("oos_win_rate")
                    else "-",
                    "OOS DD": f"{oos.get('oos_max_dd', 0):.1f}%"
                    if oos.get("oos_max_dd")
                    else "-",
                    "OOS Period": oos.get("period", "-"),
                    "Passed": "✅"
                    if str(oos.get("passed", "False")) == "True"
                    else "⚠",
                }
            except Exception as _e:
                return {"Signal": signal, "Error": str(_e)}

        configs_to_show = [
            ("config/production_config.json", "Any / Breakout"),
        ]
        if _vcp_available:
            configs_to_show.append(("config/vcp_config.json", "VCP"))
        if _pp_available:
            configs_to_show.append(("config/pocket_pivot_config.json", "Pocket Pivot"))
        if _fb_available:
            configs_to_show.append(("config/flat_base_config.json", "Flat Base"))

        rows = [_load_cfg(p, s) for p, s in configs_to_show]
        df_strats = _pd_t8.DataFrame(rows)

        # Cast all columns to str to avoid PyArrow type errors
        # (mixed float/str columns like OOS Sharpe break Arrow serialization)
        df_display = df_strats.set_index("Signal").astype(str)
        st.dataframe(
            df_display,
            use_container_width=True,
            height=200,
        )

        st.markdown("---")
        st.markdown("#### Cómo optimizar un patrón nuevo")
        st.code(
            "# Cualquier patrón registrado en pattern_configs.py:\n"
            "python3 optimize_3tier.py --signal-type vcp --trials 200 --tickers 80\n"
            "python3 optimize_3tier.py --signal-type pocket_pivot --trials 200 --tickers 80\n"
            "python3 optimize_3tier.py --signal-type flat_base --trials 200 --tickers 80\n"
            "\n"
            "# Validar VCP OOS:\n"
            "python3 validate_vcp_oos.py --start 2023-01-01 --end 2024-12-31 --tickers 120\n"
            "\n"
            "# Forzar export si el golden guard bloquea (e.g. tras fix de bug):\n"
            "python3 optimize_3tier.py --signal-type breakout --trials 300 --force-export",
            language="bash",
        )

        st.markdown("---")
        st.markdown("#### Señal activa en este backtest")
        _sig_info = {
            "any": "close > SMA20 (sin filtro adicional). Tier2 calibrado para este universo.",
            "breakout": "close > rolling 20d high. Breakout clásico de pivote.",
            "vcp": "5 condiciones: atr_contracting + pivot_break + vol_dry + near_pivot + tight_base.",
            "pocket_pivot": "Día verde + volumen > max(vol down-days últimos N bars). Entrada dentro de la base.",
            "flat_base": "Base tight (<fb_max_range%) + plana (no cup) + breakout del borde superior.",
        }
        _cur_sig = (
            "vcp"
            if _use_vcp
            else "pocket_pivot"
            if _use_pp
            else "flat_base"
            if _use_fb
            else "breakout"
            if _use_breakout
            else "any"
        )
        st.info(f"**{_cur_sig.upper()}** — {_sig_info.get(_cur_sig, '')}")

else:
    st.info("No backtest results found. Run a backtest to see analytics.")
