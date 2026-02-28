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
"""
