"""
FEATURE FLAGS - CENTRALIZED CONFIGURATION
==========================================

Define todas las features del sistema en un solo lugar.
Ambos engines (THOR + Advanced) importan de aquí.

Usage:
    from config.feature_flags import FEATURES, get_feature_defaults
    
    defaults = get_feature_defaults()
    params = {**defaults, **user_params}
"""

from typing import Dict, Any, List

# =============================================================================
# FEATURE DEFINITIONS
# =============================================================================

FEATURES: Dict[str, Dict[str, Any]] = {
    
    # -------------------------------------------------------------------------
    # MARKET REGIME FILTERS
    # -------------------------------------------------------------------------
    
    'require_spy_above_sma50': {
        'default': False,
        'category': 'market_regime',
        'description': 'Require SPY > SMA50 (bull market only)',
        'impact': '+0.35 Sharpe',
        'status': 'validated',
        'type': 'boolean',
        'ui': {
            'label': '📈 SPY > SMA50 Filter',
            'help': 'Only trade when market is above 50-day MA (+35% Sharpe)',
            'section': 'Market Regime'
        },
        'validation': {
            'tested': True,
            'sharpe_delta': 0.335,
            'verdict': 'ENABLE'
        }
    },
    
    'use_market_regime_filter': {
        'default': False,
        'category': 'market_regime',
        'description': 'Multi-factor market regime (SPY+VIX+breadth)',
        'impact': 'TBD',
        'status': 'experimental',
        'type': 'boolean',
        'ui': {
            'label': '🌍 Full Market Regime',
            'help': 'Advanced regime filter (SPY, VIX, breadth)',
            'section': 'Market Regime'
        }
    },
    
    # -------------------------------------------------------------------------
    # POSITION MANAGEMENT
    # -------------------------------------------------------------------------
    
    'use_trailing_stop': {
        'default': False,
        'category': 'exits',
        'description': 'Use trailing stop after TP1',
        'impact': '0.00 Sharpe',
        'status': 'validated',
        'type': 'boolean',
        'ui': {
            'label': '🔄 Trailing Stop',
            'help': 'Activate trailing stop after TP1 hit (neutral impact)',
            'section': 'Exit Strategy'
        },
        'validation': {
            'tested': True,
            'sharpe_delta': 0.000,
            'verdict': 'NEUTRAL'
        }
    },
    
    # -------------------------------------------------------------------------
    # QUALITY FILTERS
    # -------------------------------------------------------------------------
    
    'use_adaptive_filtering': {
        'default': False,
        'category': 'quality',
        'description': 'Adaptive multi-tier filter engine',
        'impact': '-1.05 Sharpe',
        'status': 'deprecated',
        'type': 'boolean',
        'ui': {
            'label': '🔧 Adaptive Filtering',
            'help': 'Multi-tier quality filter (⚠️ degrades performance)',
            'section': 'Advanced Filters'
        },
        'validation': {
            'tested': True,
            'sharpe_delta': -1.049,
            'verdict': 'DISABLE'
        }
    },
    
    'use_earnings_calendar': {
        'default': False,
        'category': 'quality',
        'description': 'Avoid trades near earnings',
        'impact': '0.00 Sharpe',
        'status': 'validated',
        'type': 'boolean',
        'ui': {
            'label': '📅 Earnings Filter',
            'help': 'Avoid entries within 3 days of earnings (neutral)',
            'section': 'Quality Filters'
        },
        'validation': {
            'tested': True,
            'sharpe_delta': 0.000,
            'verdict': 'NEUTRAL'
        },
        'params': {
            'earnings_buffer_days': {
                'default': 3,
                'range': (1, 7),
                'type': 'int',
                'description': 'Days to avoid before/after earnings'
            }
        }
    },
    
    # -------------------------------------------------------------------------
    # DYNAMIC THRESHOLDS
    # -------------------------------------------------------------------------
    
    'use_dynamic_thresholds': {
        'default': False,
        'category': 'quality',
        'description': 'Adjust RVOL/ADR thresholds by VIX',
        'impact': 'TBD',
        'status': 'experimental',
        'type': 'boolean',
        'ui': {
            'label': '📊 Dynamic Thresholds',
            'help': 'Adjust filters based on VIX regime',
            'section': 'Advanced Filters'
        }
    },
    
    # -------------------------------------------------------------------------
    # EXP-010 DYNAMIC ADR STOP
    # -------------------------------------------------------------------------
    
    'stop_mode': {
        'default': 0, # 0: fixed_pct
        'category': 'exits',
        'description': 'Stop calculation mode (0:fixed, 1:adr, 2:atr, 3:adr_floor, 4:adr_reject)',
        'status': 'experimental',
        'type': 'int',
        'ui': {
            'label': '🛑 Stop Mode',
            'help': 'Select stop calculation logic (baseline=0)',
            'section': 'Exit Strategy'
        }
    },
    
    'adr_stop_fraction': {
        'default': 0.5,
        'category': 'exits',
        'description': 'Fraction of ADR to use for stop (0.5 = 50% ADR)',
        'status': 'experimental',
        'type': 'float',
        'ui': {
            'label': '📏 ADR Stop Fraction',
            'help': 'Multiplier for ADR-based stop',
            'section': 'Exit Strategy'
        }
    },

    'sizing_mode': {
        'default': 0, # 0: fixed_risk
        'category': 'risk',
        'description': 'Position sizing mode (0:fixed_risk, 1:adaptive)',
        'status': 'experimental',
        'type': 'int',
        'ui': {
            'label': '💰 Sizing Mode',
            'help': 'Position sizing logic',
            'section': 'Risk Management'
        }
    },

    'max_position_pct': {
        'default': 0.25,
        'category': 'risk',
        'description': 'Maximum individual position size as % of equity',
        'status': 'validated',
        'type': 'float',
        'ui': {
            'label': '🛡️ Max Position %',
            'help': 'Cap for individual trade size (default 25%)',
            'section': 'Risk Management'
        }
    },
    
    # -------------------------------------------------------------------------
    # SECTOR ANALYSIS
    # -------------------------------------------------------------------------
    
    'require_positive_rs': {
        'default': False,
        'category': 'sector',
        'description': 'Require positive relative strength',
        'impact': 'TBD',
        'status': 'experimental',
        'type': 'boolean',
        'ui': {
            'label': '💪 Positive RS Only',
            'help': 'Only trade stocks with positive relative strength',
            'section': 'Sector Analysis'
        }
    },
    
    'use_rs_percentile': {
        'default': False,
        'category': 'sector',
        'description': 'Use RS percentile ranking',
        'impact': 'TBD',
        'status': 'experimental',
        'type': 'boolean',
        'ui': {
            'label': '📊 RS Percentile',
            'help': 'Rank stocks by RS percentile',
            'section': 'Sector Analysis'
        },
        'params': {
            'min_rs_percentile': {
                'default': 0.5,
                'range': (0.0, 1.0),
                'type': 'float',
                'description': 'Minimum RS percentile (0-1)'
            }
        }
    },

    # -------------------------------------------------------------------------
    # E11: THEME GROUP DIVERGENCE FILTER
    # -------------------------------------------------------------------------
    # Experiment : experiments/theme_group_etf_correlation_sandbox.py
    # Run date   : 2026-05-12
    # Verdict    : GO — Variante E (Divergence: Theme OK, Sector NO)
    #
    # Mechanism  : Entra cuando el sector ETF esta frio (S1 x) PERO el tema
    #              del ticker esta fuerte (theme_above_sma20 = True).
    #              Captura rotaciones anticipadas dentro de sectores broad.
    #
    # OOS results (2025-07-01 -> 2026-03-31):
    #   Best variant : E (Divergence)
    #   Delta Sharpe : +0.452 vs Baseline 1 (Sector ETF)  <- threshold era +0.10
    #   Win rate     : 59.4%  (threshold: > 55%)
    #   Profit factor: 3.94   (threshold: > 3.0)
    #   Avg return   : +11.5% (20d window)
    #   OOS trades   : 2875
    #
    # Taxonomy   : 97 tickers * 32 temas * src/data/theme_taxonomy.py
    #
    # WARNING: Retiene ~20% de senales del baseline. Filtro muy selectivo.
    #          NO activar en produccion sin completar shadow mode (15-20 rondas).
    #
    # Rollback triggers:
    #   - Throughput < 15 senales/mes en 4 semanas consecutivas
    #   - PF live < 3.0 sostenido
    #   - WR live < 55% sostenido
    # -------------------------------------------------------------------------

    'use_theme_group_filter': {
        'default': False,
        'category': 'sector',
        'description': 'E11: Theme divergence filter (sector cold, theme strong)',
        'impact': '+0.452 Sharpe OOS vs Sector ETF baseline',
        'status': 'shadow',        # shadow -> validated -> production
        'type': 'boolean',
        'experiment': {
            'id': 'E11',
            'file': 'experiments/theme_group_etf_correlation_sandbox.py',
            'report': 'outputs/experiments/theme_group_experiment_report.json',
            'run_date': '2026-05-12',
            'verdict': 'GO',
        },
        'ui': {
            'label': '🧩 Theme Divergence Filter (E11)',
            'help': 'Filtra senales: sector frio + tema fuerte -> rotacion anticipada. Shadow mode only.',
            'section': 'Sector Analysis'
        },
        'validation': {
            'tested': True,
            'sharpe_delta': 0.452,
            'win_rate_oos': 59.4,
            'profit_factor_oos': 3.94,
            'trades_oos': 2875,
            'verdict': 'SHADOW',       # proximo estado: ENABLE
        },
        'params': {
            'theme_filter_mode': {
                'default': 'E',
                'choices': ['A', 'B', 'C', 'D', 'E'],
                'type': 'str',
                'description': (
                    'Variante activa del filtro tematico. '
                    'E=Divergence (tema OK, sector NO) -- ganadora OOS.'
                )
            },
            'theme_filter_min_members': {
                'default': 5,
                'range': (2, 20),
                'type': 'int',
                'description': 'Minimo de tickers en el tema para que sea valido'
            },
            'theme_filter_min_pf': {
                'default': 3.0,
                'range': (1.5, 6.0),
                'type': 'float',
                'description': 'PF minimo en shadow para mantener el filtro activo'
            },
            'theme_filter_min_wr': {
                'default': 55.0,
                'range': (45.0, 70.0),
                'type': 'float',
                'description': 'Win rate minimo (%) en shadow para mantener el filtro activo'
            },
            'theme_filter_rs_lookback': {
                'default': 20,
                'range': (10, 60),
                'type': 'int',
                'description': 'Lookback en dias para calcular theme RS vs sector ETF'
            },
            'theme_filter_min_trades_per_month': {
                'default': 15,
                'range': (5, 50),
                'type': 'int',
                'description': 'Senales/mes minimas; por debajo -> trigger de rollback'
            },
            'theme_filter_rollback_weeks': {
                'default': 4,
                'range': (2, 8),
                'type': 'int',
                'description': 'Semanas consecutivas bajo el minimo antes de rollback automatico'
            },
            'theme_filter_max_throughput_drop': {
                'default': 0.50,
                'range': (0.20, 0.80),
                'type': 'float',
                'description': 'Fraccion maxima de senales retenidas (0.50 = acepta hasta 50% de drop)'
            },
        }
    },
}

# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def get_feature_defaults() -> Dict[str, Any]:
    """Get default values for all features."""
    defaults = {}
    
    for feature_name, config in FEATURES.items():
        defaults[feature_name] = config['default']
        
        # Add nested params
        if 'params' in config:
            for param_name, param_config in config['params'].items():
                defaults[param_name] = param_config['default']
    
    return defaults

def get_validated_features() -> List[str]:
    """Get list of features that have been validated."""
    return [
        name for name, config in FEATURES.items()
        if config.get('validation', {}).get('tested', False)
    ]

def get_recommended_features() -> Dict[str, bool]:
    """Get recommended feature settings based on validation."""
    recommended = {}
    
    for name, config in FEATURES.items():
        if 'validation' in config:
            verdict = config['validation'].get('verdict', 'NEUTRAL')
            recommended[name] = (verdict == 'ENABLE')
        else:
            recommended[name] = config['default']
    
    return recommended

def get_features_by_category(category: str) -> Dict[str, Dict]:
    """Get all features in a category."""
    return {
        name: config for name, config in FEATURES.items()
        if config.get('category') == category
    }

def get_ui_sections() -> Dict[str, List[str]]:
    """Get features grouped by UI section."""
    sections = {}
    
    for name, config in FEATURES.items():
        if 'ui' in config:
            section = config['ui']['section']
            if section not in sections:
                sections[section] = []
            sections[section].append(name)
    
    return sections

def get_shadow_features() -> Dict[str, Dict]:
    """Get features currently in shadow/paper mode."""
    return {
        name: config for name, config in FEATURES.items()
        if config.get('status') == 'shadow'
    }

# =============================================================================
# DYNAMIC MODE LOGIC (Attack/Defense)
# =============================================================================

def get_active_mode(health_score: int) -> dict:
    """
    Retorna los feature flags correctos según el health del mercado.
    Ataque (health >= 6): Línea Base A+B, sin filtro temático.
    Defensa (health < 6): Variante E activa, filtro temático ON.
    """
    if health_score >= 6:
        return {
            "mode": "ATTACK",
            "use_theme_group_filter": False,   # Modo Ataque
            "risk_multiplier": 1.0,
        }
    elif health_score >= 4:
        return {
            "mode": "DEFENSE_PARTIAL",
            "use_theme_group_filter": True,    # Modo Defensa parcial
            "risk_multiplier": 0.75,           # Reducción de riesgo
        }
    else:
        return {
            "mode": "DEFENSE_TOTAL",
            "use_theme_group_filter": True,    # Modo Defensa total
            "risk_multiplier": 0.35,           # Gran reducción de riesgo
        }


# =============================================================================
# USAGE EXAMPLES
# =============================================================================

"""
# Example 1: Get defaults for engine
from config.feature_flags import get_feature_defaults

defaults = get_feature_defaults()
engine_params = {**defaults, **user_overrides}

# Example 2: Get only validated features
from config.feature_flags import get_recommended_features

recommended = get_recommended_features()
# {'require_spy_above_sma50': True, 'use_adaptive_filtering': False, ...}

# Example 3: Auto-generate Streamlit UI
from config.feature_flags import get_ui_sections, FEATURES

for section_name, feature_names in get_ui_sections().items():
    st.subheader(section_name)
    for feature in feature_names:
        config = FEATURES[feature]
        ui = config['ui']
        st.checkbox(ui['label'], value=config['default'], help=ui['help'])

# Example 4: Check what's in shadow mode
from config.feature_flags import get_shadow_features

shadow = get_shadow_features()
# {'use_theme_group_filter': {...}}  <- E11 en paper mode
"""
