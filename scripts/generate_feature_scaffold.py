#!/usr/bin/env python3
"""
FEATURE SCAFFOLD GENERATOR
===========================

Auto-genera código boilerplate para una nueva feature.

Usage:
    python3 scripts/generate_feature_scaffold.py \
        --name use_volume_surge \
        --description "Filter by volume surge" \
        --param min_volume_surge:float:3.0
"""

import argparse
from pathlib import Path

TEMPLATE = """
# ===========================================================================
# FEATURE: {feature_name}
# ===========================================================================
# Description: {description}
# Generated: AUTO
# ===========================================================================

# ---------------------------------------------------------------------------
# 1. CONFIG DEFINITION (config/feature_flags.py)
# ---------------------------------------------------------------------------

'{feature_name}': {{
    'default': False,
    'category': 'quality',  # TODO: Update category
    'description': '{description}',
    'impact': 'TBD',
    'status': 'experimental',
    'type': 'boolean',
    'ui': {{
        'label': '🔧 {display_name}',
        'help': '{description}',
        'section': 'Advanced Filters'  # TODO: Update section
    }}{params_section}
}},

# ---------------------------------------------------------------------------
# 2. THOR IMPLEMENTATION (src/backtest/optimization_engine_thor.py)
# ---------------------------------------------------------------------------

# In optimize() method, add:

# Extract feature params
{feature_name} = params.get('{feature_name}', False)
{param_extractions}

# Calculate indicator (if needed)
# TODO: Add your indicator calculation here
# Example: volume_surge = data['volume'] / data['volume'].rolling(20).mean()

# Apply filter
if {feature_name}:
    # TODO: Add your filter logic here
    # Example: base_filters &= (volume_surge >= min_volume_surge)
    pass

# ---------------------------------------------------------------------------
# 3. ADVANCED IMPLEMENTATION (src/backtest/vectorbt_engine_advanced.py)
# ---------------------------------------------------------------------------

# In __init__() method, add parameters:

{feature_name}: bool = False,
{param_definitions}

# Store as instance variables:

self.{feature_name} = {feature_name}
{param_storage}

# In calculate_entries() or apply_filters() method:

if self.{feature_name}:
    # TODO: Add your filter logic here
    # Example: 
    # volume_surge = self.volume / self.volume.rolling(20).mean()
    # entries &= (volume_surge >= self.min_volume_surge)
    pass

# ---------------------------------------------------------------------------
# 4. STREAMLIT UI (app.py)
# ---------------------------------------------------------------------------

# In sidebar, add:

with st.expander("Advanced Filters"):
    {feature_name} = st.checkbox(
        "{display_name}",
        value=False,
        help="{description}"
    )
    
{ui_params}

# Pass to engine:

engine_params['{feature_name}'] = {feature_name}
{param_passing}

# ---------------------------------------------------------------------------
# 5. TESTING (test_{feature_name}.py)
# ---------------------------------------------------------------------------

import pytest
from src.backtest.optimization_engine_thor import OptimizationEngineTHOR
from src.backtest.vectorbt_engine_advanced import AdvancedVectorBTEngine

def test_{feature_name}_thor():
    \"\"\"Test feature in THOR engine.\"\"\"
    params = {{
        '{feature_name}': True,
        {test_params}
    }}
    
    engine = OptimizationEngineTHOR(
        tickers=['AAPL', 'MSFT', 'GOOGL'],
        start_date='2023-01-01',
        end_date='2023-12-31'
    )
    
    result = engine.optimize(params)
    assert result['total_trades'] > 0

def test_{feature_name}_advanced():
    \"\"\"Test feature in Advanced engine.\"\"\"
    engine = AdvancedVectorBTEngine(
        universe=['AAPL', 'MSFT', 'GOOGL'],
        start_date='2023-01-01',
        end_date='2023-12-31',
        {feature_name}=True,
        {test_param_assignments}
    )
    
    result = engine.run_backtest()
    assert result['total_trades'] > 0

def test_{feature_name}_convergence():
    \"\"\"Test THOR/Advanced convergence with new feature.\"\"\"
    params = {{
        '{feature_name}': True,
        {test_params}
    }}
    
    # Run both engines
    thor = OptimizationEngineTHOR(
        tickers=['AAPL', 'MSFT'],
        start_date='2023-01-01',
        end_date='2023-06-30'
    )
    thor_result = thor.optimize(params)
    
    advanced = AdvancedVectorBTEngine(
        universe=['AAPL', 'MSFT'],
        start_date='2023-01-01',
        end_date='2023-06-30',
        **params
    )
    advanced_result = advanced.run_backtest()
    
    # Validate convergence
    sharpe_diff = abs(thor_result['sharpe'] - advanced_result['sharpe'])
    assert sharpe_diff < 0.3, f"Sharpe divergence too high: {{sharpe_diff}}"

# ---------------------------------------------------------------------------
# 6. VALIDATION (validation_baseline.py --test-feature)
# ---------------------------------------------------------------------------

# Run feature impact analysis:
python3 validation_baseline.py --phase 2 --feature {feature_name}

# Expected output:
# Feature: {feature_name}
#   Sharpe Delta: +X.XX
#   Verdict: ENABLE/NEUTRAL/DISABLE

"""

def generate_scaffold(feature_name: str, description: str, params: list):
    """Generate feature scaffold code."""
    
    # Parse params
    param_defs = []
    param_extractions = []
    param_storage = []
    param_passing = []
    test_params = []
    test_param_assignments = []
    ui_params = []
    params_section = ""
    
    if params:
        params_dict = []
        for param in params:
            parts = param.split(':')
            if len(parts) != 3:
                print(f"⚠️  Invalid param format: {param}")
                continue
            
            param_name, param_type, default_val = parts
            
            params_dict.append(f"""
            '{param_name}': {{
                'default': {default_val},
                'range': (0.0, 10.0),  # TODO: Update range
                'type': '{param_type}',
                'description': 'TODO: Add description'
            }}""")
            
            param_extractions.append(f"{param_name} = params.get('{param_name}', {default_val})")
            param_defs.append(f"{param_name}: {param_type} = {default_val},")
            param_storage.append(f"self.{param_name} = {param_name}")
            param_passing.append(f"engine_params['{param_name}'] = {param_name}")
            test_params.append(f"'{param_name}': {default_val}")
            test_param_assignments.append(f"{param_name}={default_val}")
            
            # UI slider/input
            if param_type == 'float':
                ui_params.append(f"""    if {feature_name}:
        {param_name} = st.slider(
            "{param_name.replace('_', ' ').title()}",
            min_value=0.0,
            max_value=10.0,
            value={default_val},
            step=0.1
        )""")
            elif param_type == 'int':
                ui_params.append(f"""    if {feature_name}:
        {param_name} = st.number_input(
            "{param_name.replace('_', ' ').title()}",
            min_value=0,
            max_value=100,
            value={default_val}
        )""")
        
        params_section = f",\n    'params': {{{','.join(params_dict)}\n    }}"
    
    # Format template
    display_name = feature_name.replace('_', ' ').replace('use ', '').title()
    
    code = TEMPLATE.format(
        feature_name=feature_name,
        display_name=display_name,
        description=description,
        params_section=params_section,
        param_extractions='\n'.join(param_extractions) if param_extractions else '# No params',
        param_definitions='\n'.join(param_defs) if param_defs else '',
        param_storage='\n'.join(param_storage) if param_storage else '# No params',
        param_passing='\n'.join(param_passing) if param_passing else '# No params',
        test_params=',\n        '.join(test_params) if test_params else '# No params',
        test_param_assignments=',\n        '.join(test_param_assignments) if test_param_assignments else '',
        ui_params='\n\n'.join(ui_params) if ui_params else '    # No params'
    )
    
    return code

def main():
    parser = argparse.ArgumentParser(description='Generate feature scaffold')
    parser.add_argument('--name', required=True, help='Feature name (e.g., use_volume_surge)')
    parser.add_argument('--description', required=True, help='Feature description')
    parser.add_argument('--param', action='append', help='Param in format name:type:default')
    
    args = parser.parse_args()
    
    # Generate scaffold
    code = generate_scaffold(args.name, args.description, args.param or [])
    
    # Save to file
    output_file = Path(f'templates/feature_{args.name}.txt')
    output_file.write_text(code)
    
    print(f"✅ Scaffold generated: {output_file}")
    print(f"\n📋 Next steps:")
    print(f"   1. Copy sections to respective files")
    print(f"   2. Implement TODO sections")
    print(f"   3. Run: python3 test_{args.name}.py")
    print(f"   4. Run: python3 validation_baseline.py --phase 2")

if __name__ == '__main__':
    main()
