"""
pattern_configs.py
==================
Plugin de configuracion por signal_type para optimize_3tier.py.

Cada patron define:
  - extra_fixed_params : params adicionales siempre fijos (no optimizados)
  - optuna_space       : funcion que define el espacio de busqueda Optuna
  - config_output      : nombre del archivo de config de salida
  - baseline_signal    : signal_type a usar en el baseline (Fase 1)
  - description        : descripcion del patron

Para agregar un nuevo patron:
  1. Agregar su entrada en PATTERN_CONFIGS
  2. Si tiene params de entrada propios, agregar en extra_fixed_params y optuna_space
  3. Ya. El pipeline de 3 fases se reutiliza automaticamente.
"""

from typing import Any, Dict, Optional
import optuna


def _breakout_space(trial: optuna.Trial, fixed: dict) -> dict:
    """Espacio Optuna para breakout: solo parametros de salida."""
    tp1_r = trial.suggest_float("tp1_r", 1.25, 2.25, step=0.25)
    tp2_r = trial.suggest_float("tp2_r", 2.00, 5.50, step=0.25)
    tp1_pct = trial.suggest_float("tp1_pct", 0.25, 0.50, step=0.05)
    tp2_pct = trial.suggest_float("tp2_pct", 0.20, 0.45, step=0.05)
    runner_pct = round(1.0 - tp1_pct - tp2_pct, 2)
    if runner_pct < 0.10 or runner_pct > 0.50:
        return None
    if tp2_r - tp1_r < 0.50:
        return None
    score_rs_weight = trial.suggest_float("score_rs_weight", 0.30, 1.0, step=0.10)
    return {
        "tp1_r": tp1_r,
        "tp2_r": tp2_r,
        "tp1_pct": tp1_pct,
        "tp2_pct": tp2_pct,
        "runner_pct": runner_pct,
        "score_rs_weight": score_rs_weight,
        "score_proximity_weight": round(1.0 - score_rs_weight, 2),
        "pattern_bonus_high": 0.0,
        "pattern_bonus_med": 0.0,
        "pattern_bonus_low": 0.0,
    }


def _vcp_space(trial: optuna.Trial, fixed: dict) -> dict:
    """Espacio Optuna para VCP v2: salida + 8 params de entrada Minervini."""
    tp1_r = trial.suggest_float("tp1_r", 1.25, 2.50, step=0.25)
    tp2_r = trial.suggest_float("tp2_r", 2.00, 5.25, step=0.25)
    tp1_pct = trial.suggest_float("tp1_pct", 0.30, 0.55, step=0.05)
    tp2_pct = trial.suggest_float("tp2_pct", 0.20, 0.45, step=0.05)
    runner_pct = round(1.0 - tp1_pct - tp2_pct, 2)
    if runner_pct < 0.10 or runner_pct > 0.50:
        return None
    if tp2_r - tp1_r < 0.75:
        return None
    # VCP entry signal params (v2 -- Minervini 5-condition signal)
    pivot_window = trial.suggest_int("vcp_pivot_window", 10, 25)
    atr_short = trial.suggest_int("vcp_atr_short", 5, 15)
    atr_long = trial.suggest_int("vcp_atr_long", 20, 40)
    atr_ratio = trial.suggest_float("vcp_atr_ratio", 0.60, 0.95, step=0.05)
    vol_dry_periods = trial.suggest_int("vcp_volume_dry_periods", 3, 10)
    depth_max_pct = trial.suggest_float("vcp_depth_max_pct", 8.0, 20.0, step=1.0)
    pivot_dist_max = trial.suggest_float("vcp_pivot_dist_max_pct", 2.0, 14.0, step=1.0)
    require_vol_dry = trial.suggest_categorical("vcp_require_vol_dry", [True, False])
    if atr_short >= atr_long:
        return None
    return {
        "tp1_r": tp1_r,
        "tp2_r": tp2_r,
        "tp1_pct": tp1_pct,
        "tp2_pct": tp2_pct,
        "runner_pct": runner_pct,
        "vcp_pivot_window": pivot_window,
        "vcp_atr_short": atr_short,
        "vcp_atr_long": atr_long,
        "vcp_atr_ratio": atr_ratio,
        "vcp_volume_dry_periods": vol_dry_periods,
        "vcp_depth_max_pct": depth_max_pct,
        "vcp_pivot_dist_max_pct": pivot_dist_max,
        "vcp_require_vol_dry": require_vol_dry,
    }


def _pocket_pivot_space(trial: optuna.Trial, fixed: dict) -> dict:
    """
    Espacio Optuna para Pocket Pivot.
    Pocket Pivot: volumen del dia > max volumen bajista de los ultimos N dias,
    mientras el precio esta sobre la SMA50.
    Params de entrada:
      pp_vol_lookback : dias para calcular el max vol bajista (5-15)
      pp_vol_mult     : multiplicador minimo del volumen (1.0-2.0)
    """
    tp1_r = trial.suggest_float("tp1_r", 1.25, 3.00, step=0.25)
    tp2_r = trial.suggest_float("tp2_r", 2.00, 5.25, step=0.25)
    tp1_pct = trial.suggest_float("tp1_pct", 0.2, 0.55, step=0.05)
    tp2_pct = trial.suggest_float("tp2_pct", 0.20, 0.5, step=0.05)
    runner_pct = round(1.0 - tp1_pct - tp2_pct, 2)
    if runner_pct < 0.10 or runner_pct > 0.50:
        return None
    if tp2_r - tp1_r < 0.50:
        return None
    pp_vol_lookback = trial.suggest_int("pp_vol_lookback", 3, 15)
    pp_vol_mult = trial.suggest_float("pp_vol_mult", 0.8, 2.2, step=0.10)
    return {
        "tp1_r": tp1_r,
        "tp2_r": tp2_r,
        "tp1_pct": tp1_pct,
        "tp2_pct": tp2_pct,
        "runner_pct": runner_pct,
        "pp_vol_lookback": pp_vol_lookback,
        "pp_vol_mult": pp_vol_mult,
    }


def _flat_base_space(trial: optuna.Trial, fixed: dict) -> dict:
    """
    Espacio Optuna para Flat Base.
    Flat Base: consolidacion >= N semanas con rango < X%, luego rotura del maximo.
    Params de entrada:
      fb_min_weeks   : semanas minimas de consolidacion (4-8)
      fb_max_range   : rango maximo permitido en la base (3-10%)
    """
    tp1_r = trial.suggest_float("tp1_r", 1.25, 2.50, step=0.25)
    tp2_r = trial.suggest_float("tp2_r", 2.00, 5.00, step=0.25)
    tp1_pct = trial.suggest_float("tp1_pct", 0.30, 0.55, step=0.05)
    tp2_pct = trial.suggest_float("tp2_pct", 0.20, 0.45, step=0.05)
    runner_pct = round(1.0 - tp1_pct - tp2_pct, 2)
    if runner_pct < 0.10 or runner_pct > 0.50:
        return None
    if tp2_r - tp1_r < 0.50:
        return None
    fb_min_weeks = trial.suggest_int("fb_min_weeks", 4, 8)
    fb_max_range = trial.suggest_float("fb_max_range", 3.0, 15.0, step=0.5)
    return {
        "tp1_r": tp1_r,
        "tp2_r": tp2_r,
        "tp1_pct": tp1_pct,
        "tp2_pct": tp2_pct,
        "runner_pct": runner_pct,
        "fb_min_weeks": fb_min_weeks,
        "fb_max_range": fb_max_range,
    }


# -- Registro central de patrones ----------------------------------------------
PATTERN_CONFIGS: Dict[str, Dict[str, Any]] = {
    "breakout": {
        "description": "Breakout clasico: close > 20d high. Señal pura de ruptura de pivote.",
        "config_output": "config/breakout_config.json",
        "baseline_signal": "any",
        "optuna_space": _breakout_space,
        "extra_fixed_params": {},
        "min_tp_separation": 0.50,
        "export_to_streamlit": True,
    },
    "any": {
        "description": "Benchmark universal: signal_type any con el baseline historico. Compite sin privilegios.",
        "config_output": "config/any_config.json",
        "baseline_signal": "any",
        "optuna_space": _breakout_space,
        "extra_fixed_params": {
            "signal_type": "any",
            "use_adaptive_filtering": True,
            "require_spy_above_sma50": True,
            "use_market_regime_filter": True,
            "block_trades_in_stage3": True,
            "block_trades_in_stage4": True,
        },
        "min_tp_separation": 0.50,
        "export_to_streamlit": True,
    },
    "vcp": {
        "description": "VCP v2 (Minervini 5-condition): pivot_break + atr_contracting + vol_dry + near_pivot + tight_base.",
        "config_output": "config/vcp_config.json",
        "baseline_signal": "vcp",
        "optuna_space": _vcp_space,
        "extra_fixed_params": {
            "signal_type": "vcp",
            # v2 defaults (Optuna will override these per trial)
            "vcp_pivot_window": 15,
            "vcp_atr_short": 10,
            "vcp_atr_long": 30,
            "vcp_atr_ratio": 0.85,
            "vcp_volume_dry_periods": 5,
            "vcp_depth_max_pct": 15.0,
            "vcp_pivot_dist_max_pct": 8.0,
            "vcp_require_vol_dry": True,
            "use_adaptive_filtering": False,
            "require_spy_above_sma50": False,
            "use_market_regime_filter": False,
            "block_trades_in_stage3": False,
            "block_trades_in_stage4": False,
        },
        "min_tp_separation": 0.75,
        "export_to_streamlit": False,
        "golden_config_key": "_oos_sharpe",  # key to read from vcp_config.json for guard
    },
    "pocket_pivot": {
        "description": "Pocket Pivot: vol spike sobre max vol bajista de N dias.",
        "config_output": "config/pocket_pivot_config.json",
        "baseline_signal": "pocket_pivot",
        "optuna_space": _pocket_pivot_space,
        "extra_fixed_params": {
            "signal_type": "pocket_pivot",
            "pp_vol_lookback": 10,
            "pp_vol_mult": 1.0,
            "use_adaptive_filtering": False,
            "require_spy_above_sma50": False,
            "use_market_regime_filter": False,
            "block_trades_in_stage3": False,
            "block_trades_in_stage4": False,
        },
        "min_tp_separation": 0.50,
        "export_to_streamlit": False,
    },
    "flat_base": {
        "description": "Flat Base: consolidacion N semanas con rango < X%, luego rotura.",
        "config_output": "config/flat_base_config.json",
        "baseline_signal": "flat_base",
        "optuna_space": _flat_base_space,
        "extra_fixed_params": {
            "signal_type": "flat_base",
            "fb_min_weeks": 5,
            "fb_max_range": 7.0,
            "use_adaptive_filtering": False,
            "require_spy_above_sma50": False,
            "use_market_regime_filter": False,
            "block_trades_in_stage3": False,
            "block_trades_in_stage4": False,
        },
        "min_tp_separation": 0.50,
        "export_to_streamlit": False,
    },
}


def get_pattern_config(signal_type: str) -> Dict[str, Any]:
    """Retorna la config del patron. Falla claro si no existe."""
    if signal_type not in PATTERN_CONFIGS:
        valid = list(PATTERN_CONFIGS.keys())
        raise ValueError(
            f"Unknown signal_type '{signal_type}'. Valid options: {valid}\n"
            f"To add a new pattern, edit src/config/pattern_configs.py"
        )
    return PATTERN_CONFIGS[signal_type]


def list_patterns() -> str:
    """Retorna string formateado con todos los patrones disponibles."""
    lines = ["Available signal types:"]
    for k, v in PATTERN_CONFIGS.items():
        output = v["config_output"].replace("config/", "")
        lines.append(f"  {k:<15} -> {output:<35} {v['description']}")
    return "\n".join(lines)