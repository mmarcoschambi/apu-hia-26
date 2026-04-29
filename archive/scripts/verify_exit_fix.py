#!/usr/bin/env python3
"""
Simple verification that the fix was applied correctly
"""

import sys
from pathlib import Path

print("=" * 80)
print("🔍 EXIT LOGIC FIX - CODE VERIFICATION")
print("=" * 80)

# Check numba_core.py
numba_file = Path("src/backtest/numba_core.py")

if not numba_file.exists():
    print("❌ numba_core.py not found")
    sys.exit(1)

content = numba_file.read_text()
lines = content.split('\n')

print("\n✅ Checking priority order in exit logic...")

# Find the exit logic section
tp1_line = None
tp2_line = None
stop_line = None

for i, line in enumerate(lines):
    if 'TAKE PROFIT 1' in line and 'Prioridad máxima' in line:
        tp1_line = i
    if 'TAKE PROFIT 2' in line and 'Segunda prioridad' in line:
        tp2_line = i
    if 'STOP LOSS' in line and 'Tercera prioridad' in line:
        stop_line = i

if tp1_line and tp2_line and stop_line:
    print(f"\n  Found exit checks:")
    print(f"    Line {tp1_line}: TP1 (Prioridad máxima)")
    print(f"    Line {tp2_line}: TP2 (Segunda prioridad)")  
    print(f"    Line {stop_line}: STOP (Tercera prioridad)")
    
    if tp1_line < tp2_line < stop_line:
        print(f"\n  ✅ CORRECT ORDER: TP1 → TP2 → STOP")
        print(f"     Targets are checked BEFORE stops")
    else:
        print(f"\n  ❌ WRONG ORDER")
        sys.exit(1)
else:
    print(f"\n  ⚠️ Could not find all exit check sections")
    print(f"     TP1: {'Found' if tp1_line else 'Not found'}")
    print(f"     TP2: {'Found' if tp2_line else 'Not found'}")
    print(f"     STOP: {'Found' if stop_line else 'Not found'}")

# Check if elif is used
print("\n✅ Checking that elif is used (not separate ifs)...")

exit_section_start = tp1_line if tp1_line else 0
exit_section_end = stop_line + 20 if stop_line else len(lines)
exit_section = '\n'.join(lines[exit_section_start:exit_section_end])

if 'elif not pos_tp2_done' in exit_section and 'elif curr_low <= pos_stop_price' in exit_section:
    print("  ✅ Using elif correctly (mutually exclusive exits)")
else:
    print("  ⚠️ Not using elif - may have issues")

# Check breakeven logic
print("\n✅ Checking breakeven stop logic...")

breakeven_found = False
for i, line in enumerate(lines):
    if 'pos_stop_price[i] = max(pos_stop_price[i], pos_entry_price[i])' in line:
        breakeven_found = True
        print(f"  ✅ Breakeven update found at line {i}")
        break

if not breakeven_found:
    print("  ⚠️ Breakeven update not found")

# Summary
print("\n" + "=" * 80)
print("SUMMARY")
print("=" * 80)

checks_passed = 0
checks_total = 3

if tp1_line and tp2_line and stop_line and tp1_line < tp2_line < stop_line:
    checks_passed += 1
    print("✅ Exit priority order: CORRECT")
else:
    print("❌ Exit priority order: INCORRECT")

if 'elif not pos_tp2_done' in exit_section:
    checks_passed += 1
    print("✅ Using elif: CORRECT")
else:
    print("❌ Using elif: INCORRECT")

if breakeven_found:
    checks_passed += 1
    print("✅ Breakeven logic: FOUND")
else:
    print("❌ Breakeven logic: NOT FOUND")

print(f"\nScore: {checks_passed}/{checks_total}")

if checks_passed == checks_total:
    print("\n🎯 ALL FIXES APPLIED CORRECTLY")
    print("\nNOTE: The fix changes exit priority to:")
    print("  1. TP1 checked first (highest priority)")
    print("  2. TP2 checked second")
    print("  3. STOP checked last (only if targets not hit)")
    print("\nThis allows trades to capture partial profits")
    print("even on days with high volatility.")
    sys.exit(0)
else:
    print("\n⚠️  SOME FIXES MISSING OR INCORRECT")
    sys.exit(1)

