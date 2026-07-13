"""
dashboard_data_adapter.py — Fase 1 + Fase 0
=============================================
Adapter de ingesta robusta para el dashboard Streamlit.

Responsabilidades:
  1. Detectar y validar el schema del JSON del optimizer_3tier
  2. Normalizar campos legacy (tier1_exits, tier3_fixed, symbol/ticker, etc.)
  3. Construir DataFrames canónicos: trades_df, metrics_df, asset_pattern_index
  4. Aplicar defaults sin lanzar KeyError
  5. Logging de warnings en lugar de crashes

Contrato de schema:
  - SCHEMA_VERSION mínimo soportado: "1.0"
  - SCHEMA_VERSION actual: "2.1"
  - Keys obligatorias del JSON: tier1_strategy | tier1_exits, tier3_risk | tier3_fixed
  - Keys opcionales: tier2_filters, validation, optimization, period

Uso:
    from src.ui.dashboard_data_adapter import DashboardDataAdapter

    adapter = DashboardDataAdapter()
    data = adapter.load_optimizer_json("outputs/3tier_optimization/FINAL_CONFIG.json")
    trades_df = adapter.load_trades_csv("outputs/backtests/complete_trades_clean.csv")
    index = adapter.build_asset_pattern_index(trades_df)
"""

from __future__ import annotations

import json
import logging
import os
import warnings
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# CONTRATO DE DATOS — Defaults y alias
# ─────────────────────────────────────────────────────────────────────────────

SCHEMA_VERSION_CURRENT = "2.1"
SCHEMA_VERSION_MIN = "1.0"

# Mapeo legacy → canónico para keys de primer nivel del JSON
_JSON_KEY_ALIASES: Dict[str, str] = {
    "tier1_exits": "tier1_strategy",
    "tier3_fixed": "tier3_risk",
    "tier2_quality": "tier2_filters",
    "filters": "tier2_filters",
    "risk": "tier3_risk",
}

# Mapeo legacy → canónico para columnas de trades DataFrame
_TRADES_COL_ALIASES: Dict[str, str] = {
    "ticker": "symbol",
    "Ticker": "symbol",
    "Symbol": "symbol",
    "entry_signal": "signal_type",
    "pattern": "pattern_type",
    "Pattern": "pattern_type",
    "exit_type": "exit_phase",
    "pnl_total": "pnl",
    "total_pnl": "pnl",           # usado en grouped_trades
    "net_pnl": "pnl",
    "entry_dt": "entry_date",
    "exit_dt": "exit_date",
    "hold": "hold_days",
    "r_mult": "r_multiple",
    "initial_size": "shares",
}

# Defaults de Tier 1
_T1_DEFAULTS: Dict[str, Any] = {
    "tp1_r": 1.5,
    "tp2_r": 3.0,
    "tp1_pct": 0.40,
    "tp2_pct": 0.35,
    "runner_pct": 0.25,
    "max_stop_pct": 0.08,
    "risk_dollars": 500,
    "signal_type": "any",
    "use_phases": True,
    "score_rs_weight": 0.5,
}

# Defaults de Tier 2
_T2_DEFAULTS: Dict[str, Any] = {
    "min_rvol": 0.8,
    "min_adr": 1.5,
    "max_dist_sma20": 15.0,
    "min_volume": 300000,
    "min_dollar_volume": 20_000_000,
    "min_consolidation_days": 10,
    "max_consolidation_range": 15.0,
    "require_positive_rs": True,
    "use_rs_percentile": True,
    "min_rs_percentile": 70.0,
    "rs_lookback_days": 60,
    "require_sector_strength": False,
    "sector_top_percentile": 0.4,
    "use_pattern_filter": False,
    "min_pattern_confidence": 0.5,
}

# Defaults de Tier 3
_T3_DEFAULTS: Dict[str, Any] = {
    "rvol_danger": 3.0,
    "rvol_warning": 2.0,
    "rvol_danger_size": 0.5,
    "rvol_warning_size": 0.75,
    "adr_high": 6.0,
    "adr_med": 5.0,
    "adr_high_size": 0.75,
    "adr_med_size": 0.85,
    "max_exposure_pct": 0.65,
    "max_position_pct": 0.25,
    "earnings_days": 5,
    "earnings_cushion": 2,
    "max_stop_pct_hard": 0.08,
    "risk_fraction": 0.005,
    "compounding_enabled": False,
}

# Defaults de validación
_VALIDATION_DEFAULTS: Dict[str, Any] = {
    "approved": False,
    "pbo_score": 0.0,
    "sharpe_ratio": 0.0,
    "max_drawdown_pct": 0.0,
    "bootstrap_p5": 0.0,
    "bootstrap_p10": 0.0,
    "rejection_reasons": [],
    "discovery_passed": False,
    "validation_passed": False,
    "production_passed": False,
}

# Defaults de métricas de optimización
_OPTIM_DEFAULTS: Dict[str, Any] = {
    "trials": 0,
    "best_score": 0.0,
    "best_trial_metrics": {
        "total_return": 0.0,
        "sharpe": 0.0,
        "max_dd": 0.0,
        "win_rate": 0.0,
        "trades": 0,
        "profit_factor": 0.0,
    },
}

# Valores permitidos para signal_type / pattern_type
VALID_SIGNAL_TYPES = {"any", "breakout", "vcp", "pocket_pivot", "flat_base", "NONE"}


# ─────────────────────────────────────────────────────────────────────────────
# ADAPTER PRINCIPAL
# ─────────────────────────────────────────────────────────────────────────────


class DashboardDataAdapter:
    """
    Adapter de ingesta robusto para el dashboard Streamlit.

    Convierte JSON del optimizer_3tier y CSV de trades en DataFrames
    canónicos listos para consumir por las visualizaciones.
    """

    def __init__(self) -> None:
        self._last_json_mtime: Optional[float] = None
        self._last_json_path: Optional[str] = None
        self._last_csv_mtime: Optional[float] = None
        self._last_csv_path: Optional[str] = None

    # ──────────────────────────────────────────────────────────────────────────
    # JSON del optimizer
    # ──────────────────────────────────────────────────────────────────────────

    def load_optimizer_json(self, path: str) -> Dict[str, Any]:
        """
        Carga y normaliza el JSON del optimizer_3tier.

        - Aplica alias de keys legacy
        - Rellena defaults para keys faltantes
        - Nunca lanza KeyError: siempre devuelve dict completo
        - Loguea warnings para keys faltantes o schema desconocido

        Returns:
            dict con keys: tier1_strategy, tier2_filters, tier3_risk,
                           validation, optimization, period, metadata
        """
        path_obj = Path(path)
        if not path_obj.exists():
            logger.warning(f"[Adapter] JSON no encontrado: {path} — usando defaults")
            return self._build_default_config()

        try:
            with open(path_obj, "r", encoding="utf-8") as f:
                raw = json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            logger.error(f"[Adapter] Error leyendo JSON {path}: {e} — usando defaults")
            return self._build_default_config()

        # Validar schema version
        schema_ver = raw.get("_schema_version", "1.0")
        self._check_schema_version(schema_ver, path)

        # Aplicar aliases de keys legacy
        normalized = self._apply_key_aliases(raw)

        # Construir config canónica con defaults
        config = self._build_canonical_config(normalized, raw)

        logger.debug(f"[Adapter] JSON cargado OK: {path} (schema {schema_ver})")
        return config

    def _check_schema_version(self, version: str, path: str) -> None:
        try:
            v_major = float(version.split(".")[0])
            min_major = float(SCHEMA_VERSION_MIN.split(".")[0])
            if v_major < min_major:
                logger.warning(
                    f"[Adapter] Schema version {version} < mínimo {SCHEMA_VERSION_MIN} "
                    f"en {path}. Compatibilidad no garantizada."
                )
        except Exception:
            logger.warning(f"[Adapter] Schema version desconocida: '{version}' en {path}")

    def _apply_key_aliases(self, raw: Dict[str, Any]) -> Dict[str, Any]:
        """Renombra keys legacy al nombre canónico."""
        normalized = dict(raw)
        for legacy_key, canonical_key in _JSON_KEY_ALIASES.items():
            if legacy_key in normalized and canonical_key not in normalized:
                logger.debug(f"[Adapter] Renombrando key: '{legacy_key}' → '{canonical_key}'")
                normalized[canonical_key] = normalized.pop(legacy_key)
        return normalized

    def _build_canonical_config(
        self, normalized: Dict[str, Any], raw: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Construye config canónica aplicando defaults para keys faltantes."""
        # Tier 1
        t1_raw = normalized.get("tier1_strategy", {})
        if not t1_raw:
            logger.warning("[Adapter] 'tier1_strategy' faltante — usando defaults")
        t1 = {**_T1_DEFAULTS, **t1_raw}

        # Tier 2
        t2_raw = normalized.get("tier2_filters", {})
        t2 = {**_T2_DEFAULTS, **t2_raw}

        # Tier 3
        t3_raw = normalized.get("tier3_risk", {})
        if not t3_raw:
            logger.warning("[Adapter] 'tier3_risk' faltante — usando defaults")
        t3 = {**_T3_DEFAULTS, **t3_raw}

        # Validation
        val_raw = normalized.get("validation", {})
        validation = {**_VALIDATION_DEFAULTS, **val_raw}

        # Optimization
        optim_raw = normalized.get("optimization", {})
        # Merge best_trial_metrics con defaults
        best_metrics_raw = optim_raw.pop("best_trial_metrics", {}) if isinstance(optim_raw, dict) else {}
        optim = {**_OPTIM_DEFAULTS, **optim_raw}
        optim["best_trial_metrics"] = {
            **_OPTIM_DEFAULTS["best_trial_metrics"],
            **best_metrics_raw,
        }

        # Period
        period = normalized.get("period", {
            "start": "2019-01-01",
            "end": "2025-12-31",
            "initial_capital": 100_000,
        })

        # Market regime
        market_regime = normalized.get("market_regime", {
            "require_spy_above_sma50": True,
            "max_vix": 35.0,
            "use_market_regime_filter": True,
        })

        # Performance
        performance = normalized.get("performance", {})

        return {
            "_schema_version": normalized.get("_schema_version", SCHEMA_VERSION_CURRENT),
            "_last_updated": normalized.get("_last_updated", normalized.get("timestamp", "")),
            "_pipeline": normalized.get("pipeline", normalized.get("_optimization_method", "unknown")),
            "tier1_strategy": t1,
            "tier2_filters": t2,
            "tier3_risk": t3,
            "validation": validation,
            "optimization": optim,
            "period": period,
            "market_regime": market_regime,
            "performance": performance,
            "universe_size": normalized.get("universe_size", 0),
            # Acceso directo a campos de ui_defaults (backward compat)
            "ui_defaults": normalized.get("ui_defaults", {
                "initial_capital": period.get("initial_capital", 100_000),
                "risk_type": "fixed_dollar",
                "default_universe_size": 50,
                "lookback_days": 365,
            }),
        }

    def _build_default_config(self) -> Dict[str, Any]:
        """Config vacía con todos los defaults."""
        return self._build_canonical_config({}, {})

    # ──────────────────────────────────────────────────────────────────────────
    # CSV de trades
    # ──────────────────────────────────────────────────────────────────────────

    def load_trades_csv(self, path: str) -> pd.DataFrame:
        """
        Carga y normaliza el CSV de trades.

        - Renombra columnas legacy a nombres canónicos
        - Parsea fechas
        - Rellena valores faltantes con defaults seguros
        - Normaliza signal_type y pattern_type a minúsculas

        Returns:
            DataFrame canónico o DataFrame vacío si el archivo no existe.
        """
        path_obj = Path(path)

        # Buscar archivo alternativo si el principal no existe
        if not path_obj.exists():
            fallback = Path("outputs/backtests/backtest_results.csv")
            if fallback.exists():
                logger.warning(
                    f"[Adapter] CSV principal no encontrado ({path}), "
                    f"usando fallback: {fallback}"
                )
                path_obj = fallback
            else:
                logger.warning(f"[Adapter] No se encontró CSV de trades en {path}")
                return pd.DataFrame()

        try:
            df = pd.read_csv(path_obj, low_memory=False)
        except Exception as e:
            logger.error(f"[Adapter] Error leyendo CSV {path_obj}: {e}")
            return pd.DataFrame()

        if df.empty:
            logger.warning(f"[Adapter] CSV vacío: {path_obj}")
            return df

        df = self._normalize_trades_columns(df)
        df = self._parse_trade_dates(df)
        df = self._fill_trade_defaults(df)

        logger.debug(
            f"[Adapter] CSV cargado: {len(df)} filas, "
            f"{df['symbol'].nunique() if 'symbol' in df.columns else '?'} activos, "
            f"path={path_obj}"
        )
        return df

    def _normalize_trades_columns(self, df: pd.DataFrame) -> pd.DataFrame:
        """Renombra columnas legacy a nombres canónicos."""
        rename_map = {}
        for legacy, canonical in _TRADES_COL_ALIASES.items():
            if legacy in df.columns and canonical not in df.columns:
                rename_map[legacy] = canonical
        if rename_map:
            logger.debug(f"[Adapter] Renombrando columnas trades: {rename_map}")
            df = df.rename(columns=rename_map)
        return df

    def _parse_trade_dates(self, df: pd.DataFrame) -> pd.DataFrame:
        """Convierte columnas de fecha a datetime."""
        for col in ["entry_date", "exit_date", "final_exit_date"]:
            if col in df.columns:
                try:
                    df[col] = pd.to_datetime(df[col], errors="coerce")
                except Exception as e:
                    logger.warning(f"[Adapter] Error parseando columna fecha '{col}': {e}")
        return df

    def _fill_trade_defaults(self, df: pd.DataFrame) -> pd.DataFrame:
        """Rellena columnas faltantes con defaults seguros."""
        # Columna symbol/ticker
        if "symbol" not in df.columns:
            logger.warning("[Adapter] Columna 'symbol' no encontrada en trades CSV")
            df["symbol"] = "UNKNOWN"

        # signal_type → normalizar a minúsculas, default "any"
        if "signal_type" not in df.columns:
            if "pattern_type" in df.columns:
                df["signal_type"] = df["pattern_type"].str.lower().fillna("any")
            else:
                df["signal_type"] = "any"
        else:
            df["signal_type"] = (
                df["signal_type"]
                .astype(str)
                .str.lower()
                .replace("none", "any")
                .fillna("any")
            )

        # pattern_type — normalizar
        if "pattern_type" not in df.columns:
            df["pattern_type"] = df["signal_type"]
        else:
            df["pattern_type"] = (
                df["pattern_type"]
                .astype(str)
                .str.upper()
                .replace("NAN", "NONE")
                .fillna("NONE")
            )

        # shares, entry_price, exit_price defaults to prevent crashes (Fix Issue #10)
        if "shares" not in df.columns:
            logger.warning("[Adapter] Columna 'shares' no encontrada — se asumirá 1")
            df["shares"] = 1.0
        else:
            df["shares"] = pd.to_numeric(df["shares"], errors="coerce").fillna(1.0)

        if "entry_price" not in df.columns:
            df["entry_price"] = 1.0
        else:
            df["entry_price"] = pd.to_numeric(df["entry_price"], errors="coerce").fillna(1.0)

        if "exit_price" not in df.columns:
            df["exit_price"] = df["entry_price"] if "entry_price" in df.columns else 1.0
        else:
            df["exit_price"] = pd.to_numeric(df["exit_price"], errors="coerce").fillna(1.0)

        # pnl numérico
        if "pnl" not in df.columns:
            logger.warning("[Adapter] Columna 'pnl' no encontrada — se asumirá 0")
            df["pnl"] = 0.0
        else:
            df["pnl"] = pd.to_numeric(df["pnl"], errors="coerce").fillna(0.0)


        # r_multiple
        if "r_multiple" not in df.columns:
            df["r_multiple"] = np.nan
        else:
            df["r_multiple"] = pd.to_numeric(df["r_multiple"], errors="coerce")

        # outcome / is_winner
        if "outcome" in df.columns and "is_winner" not in df.columns:
            df["is_winner"] = df["outcome"].str.upper().isin(["WIN", "TP1", "TP2", "RUNNER"])
        elif "is_winner" not in df.columns:
            df["is_winner"] = df["pnl"] > 0

        # exit_phase
        if "exit_phase" not in df.columns and "outcome" in df.columns:
            df["exit_phase"] = df["outcome"]

        # hold_days
        if "hold_days" not in df.columns:
            if "entry_date" in df.columns and "exit_date" in df.columns:
                try:
                    df["hold_days"] = (
                        df["exit_date"] - df["entry_date"]
                    ).dt.days.fillna(0)
                except Exception:
                    df["hold_days"] = 0
            else:
                df["hold_days"] = 0

        return df

    # ──────────────────────────────────────────────────────────────────────────
    # Índice activo → patrones
    # ──────────────────────────────────────────────────────────────────────────

    def build_asset_pattern_index(
        self, trades_df: pd.DataFrame
    ) -> Dict[str, List[str]]:
        """
        Construye índice {asset → [patterns]} desde el DataFrame de trades.

        Returns:
            Dict con key "ALL" para todos los activos y keys individuales
            por símbolo. Ejemplo:
            {
                "ALL": ["any", "vcp", "breakout"],
                "AAPL": ["any", "breakout"],
                "TSLA": ["vcp"],
            }
        """
        if trades_df.empty or "symbol" not in trades_df.columns:
            return {"ALL": ["any"]}

        index: Dict[str, List[str]] = {}

        # Patrones globales
        all_patterns = sorted(trades_df["signal_type"].dropna().unique().tolist())
        index["ALL"] = all_patterns if all_patterns else ["any"]

        # Patrones por activo
        for asset in sorted(trades_df["symbol"].dropna().unique()):
            asset_df = trades_df[trades_df["symbol"] == asset]
            patterns = sorted(asset_df["signal_type"].dropna().unique().tolist())
            index[asset] = patterns if patterns else ["any"]

        return index

    # ──────────────────────────────────────────────────────────────────────────
    # Multi-run: cargar todos los JSONs de una carpeta de optimizaciones
    # ──────────────────────────────────────────────────────────────────────────

    def load_optimization_runs(
        self, folder: str = "outputs/3tier_optimization"
    ) -> List[Dict[str, Any]]:
        """
        Carga todos los FINAL_CONFIG.json de una carpeta de optimizaciones.

        Útil para la tab de comparación multi-run / multi-patrón.
        Cada run incluye un campo '_source_path' con su ruta de origen.

        Returns:
            Lista de configs canónicas, ordenadas por timestamp desc.
        """
        folder_path = Path(folder)
        if not folder_path.exists():
            logger.warning(f"[Adapter] Carpeta de optimizaciones no encontrada: {folder}")
            return []

        runs = []
        # Buscar FINAL_CONFIG.json y archivos config de patrones
        json_candidates = list(folder_path.glob("FINAL_CONFIG.json"))
        json_candidates += list(folder_path.glob("**/FINAL_CONFIG.json"))
        json_candidates += list(Path("config").glob("*_config.json"))

        seen = set()
        for json_path in json_candidates:
            if str(json_path) in seen:
                continue
            seen.add(str(json_path))
            try:
                config = self.load_optimizer_json(str(json_path))
                config["_source_path"] = str(json_path)
                # Inferir patrón desde el path si no está en el JSON
                if config.get("_pipeline") == "unknown":
                    stem = json_path.stem
                    for pat in ["vcp", "breakout", "pocket_pivot", "flat_base"]:
                        if pat in str(json_path).lower():
                            config["_inferred_pattern"] = pat
                            break
                runs.append(config)
            except Exception as e:
                logger.warning(f"[Adapter] Skipping {json_path}: {e}")

        # Ordenar por timestamp descendente
        runs.sort(key=lambda r: r.get("_last_updated", ""), reverse=True)
        return runs

    # ──────────────────────────────────────────────────────────────────────────
    # Helper: métricas por activo/patrón desde trades_df
    # ──────────────────────────────────────────────────────────────────────────

    @staticmethod
    def compute_segment_metrics(
        trades_df: pd.DataFrame,
        group_by: List[str] = None,
    ) -> pd.DataFrame:
        """
        Calcula KPIs por segmento (activo, patrón o combinación).

        Args:
            trades_df: DataFrame canónico de trades
            group_by: columnas para agrupar, e.g. ["symbol"] o ["symbol", "signal_type"]
                      Si None, calcula métricas globales como 1 fila.

        Returns:
            DataFrame con columnas: trades, win_rate, net_pnl, avg_r,
                                    profit_factor, avg_hold, sharpe_approx
        """
        if trades_df.empty:
            return pd.DataFrame()

        if group_by is None:
            df_work = trades_df.copy()
            df_work["_group"] = "ALL"
            group_by = ["_group"]
        else:
            df_work = trades_df.copy()

        def _segment_kpis(g: pd.DataFrame) -> pd.Series:
            n = len(g)
            winners = g["is_winner"].sum() if "is_winner" in g.columns else (g["pnl"] > 0).sum()
            losers = n - winners
            win_rate = winners / n * 100 if n > 0 else 0.0

            net_pnl = g["pnl"].sum()
            gross_profit = g.loc[g["pnl"] > 0, "pnl"].sum()
            gross_loss = abs(g.loc[g["pnl"] < 0, "pnl"].sum())
            profit_factor = gross_profit / gross_loss if gross_loss > 0 else float("inf")

            avg_r = g["r_multiple"].mean() if "r_multiple" in g.columns else np.nan
            avg_hold = g["hold_days"].mean() if "hold_days" in g.columns else np.nan

            # Sharpe aproximado por trade (no anualizado)
            if "r_multiple" in g.columns and g["r_multiple"].notna().sum() > 2:
                r = g["r_multiple"].dropna()
                sharpe_approx = r.mean() / r.std() if r.std() > 0 else 0.0
            else:
                sharpe_approx = np.nan

            return pd.Series({
                "trades": n,
                "winners": int(winners),
                "losers": int(losers),
                "win_rate_pct": round(win_rate, 2),
                "net_pnl": round(net_pnl, 2),
                "gross_profit": round(gross_profit, 2),
                "gross_loss": round(gross_loss, 2),
                "profit_factor": round(profit_factor, 4) if profit_factor != float("inf") else 9999.0,
                "avg_r": round(avg_r, 4) if not np.isnan(avg_r) else None,
                "avg_hold_days": round(avg_hold, 1) if not np.isnan(avg_hold) else None,
                "sharpe_approx": round(sharpe_approx, 4) if not np.isnan(sharpe_approx) else None,
            })

        try:
            result = df_work.groupby(group_by).apply(_segment_kpis).reset_index()
            return result
        except Exception as e:
            logger.error(f"[Adapter] Error calculando métricas por segmento: {e}")
            return pd.DataFrame()


# ─────────────────────────────────────────────────────────────────────────────
# Instancia singleton (lazy) para uso desde app.py
# ─────────────────────────────────────────────────────────────────────────────

_adapter_instance: Optional[DashboardDataAdapter] = None


def get_adapter() -> DashboardDataAdapter:
    """Retorna instancia singleton del adapter."""
    global _adapter_instance
    if _adapter_instance is None:
        _adapter_instance = DashboardDataAdapter()
    return _adapter_instance
