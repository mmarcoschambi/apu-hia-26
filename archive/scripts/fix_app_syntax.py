#!/usr/bin/env python3
"""
Fix app.py syntax errors
==============================
Fixes duplicate docstrings and parameter formatting issues in app.py
"""

import re

with open('app.py', 'r') as f:
    content = f.read()

# Fix 1: Remove duplicate docstring (lines 178-179)
# Look for pattern: """Execute...""" followed immediately by another """Execute..."""
content = re.sub(
    r'"""Execute backtest using VectorBT engine \(40-600x faster\)\s*"""\s*"""Execute backtest using VectorBT engine \(40-600x faster\)"""',
    '"""Execute backtest using VectorBT engine (40-600x faster)"""',
    content
)

# Fix 2: Remove extra closing parenthesis on line 177
content = re.sub(
    r'(min_consolidation_days=10,  # VCP quality \(10\+ days\)):\s*"""',
    r'(min_consolidation_days=10,  # VCP quality (10+ days)):"\n    """',
    content
)

with open('app.py', 'w') as f:
    f.write(content)

print("✅ Fixes applied successfully")

# Verify syntax
try:
    import ast
    ast.parse(content)
    print("✅ Syntax is valid")
except SyntaxError as e:
    print(f"❌ Syntax error: {e}")
    print(f"Line {e.lineno}: {e.text}")
