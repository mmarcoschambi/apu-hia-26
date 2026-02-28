#!/usr/bin/env python3
"""
Update app.py with Professional Filters
==========================================

Adds the following to the run_vectorbt_backtest_ui function:
- require_spy_above_sma50 parameter
- min_consolidation_days parameter
- Updates the docstring to match
- Passes these parameters to the engine instantiation
"""

import re

def update_app_py():
    with open('app.py', 'r', encoding='utf-8') as f:
        content = f.read()

    # Change 1: Add require_spy_above_sma50 parameter after min_consolidation_days
    # Find: "min_consolidation_days=10,  # VCP quality (10+ days)):"
    # Replace with: "min_consolidation_days=10):  # VCP quality (10+ days)"
    content = re.sub(
        r'min_consolidation_days=10,  # VCP quality \(10\+ days\)\):',
        r'min_consolidation_days=10):  # VCP quality (10+ days)',
        content
    )

    # Change 2: Update engine instantiation to pass the new parameters
    # Find the section where engine is instantiated and add the new parameters
    # Look for: "use_dynamic_thresholds=use_dynamic_thresholds,\n             max_vix_threshold=max_vix_threshold,\n         )"
    # Replace with: "use_dynamic_thresholds=use_dynamic_thresholds,\n             max_vix_threshold=max_vix_threshold,\n             # Professional filters (NEW!)\n             require_spy_above_sma50=True,  # SPY > SMA50 required\n             min_consolidation_days=10,  # VCP quality (10+ days)\n         )"

    # First find where Dynamic Thresholds section ends
    pattern = r'(use_dynamic_thresholds=use_dynamic_thresholds,\s+max_vix_threshold=max_vix_threshold,\s+)\s*\)'
    replacement = r'\1\n             # Professional filters (NEW!)\n             require_spy_above_sma50=True,  # SPY > SMA50 required\n             min_consolidation_days=10,  # VCP quality (10+ days)\n        )'

    content = re.sub(pattern, replacement, content)

    with open('app.py', 'w', encoding='utf-8') as f:
        f.write(content)

    print("✅ app.py updated successfully")

    # Verify syntax
    import ast
    try:
        ast.parse(open('app.py').read())
        print("✅ Syntax is valid")
        return True
    except SyntaxError as e:
        print(f"❌ Syntax error: {e}")
        return False

if __name__ == '__main__':
    success = update_app_py()
    exit(0 if success else 1)
