import json
import os
from pathlib import Path

JOURNAL_PATH = Path("outputs/paper_finviz/journal.json")
INITIAL_CAPITAL = 100_000
RISK_FRACTION = 0.005
RISK_DOLLARS = INITIAL_CAPITAL * RISK_FRACTION

def fix_journal():
    if not JOURNAL_PATH.exists():
        print(f"No journal found at {JOURNAL_PATH}")
        return

    with open(JOURNAL_PATH, "r") as f:
        journal = json.load(f)

    cleaned_journal = []
    total_removed_combo = 0
    total_removed_broadcast = 0
    total_fixed_size = 0

    for day in journal:
        signals = day.get("signals", [])
        
        # Bug 3: Remove inactive combos
        active_signals = [s for s in signals if s.get("combo") == "combo_pure_momentum"]
        total_removed_combo += len(signals) - len(active_signals)
        
        # Bug 2: Check for broadcast bug (duplicate prices)
        prices = [s["entry_price"] for s in active_signals]
        if len(prices) != len(set(prices)) and len(active_signals) > 1:
            # Engine now discards all setups if there's a broadcast bug
            total_removed_broadcast += len(active_signals)
            active_signals = []
            print(f"Found broadcast bug on {day['date']} - removed all setups for that day.")

        # Bug 1: Fix position_size: 0
        for s in active_signals:
            if s.get("position_size", 0) == 0:
                price = float(s["entry_price"])
                stop = float(s["stop_loss"])
                risk_per_share = price - stop
                if risk_per_share <= 0:
                    risk_per_share = price * 0.01
                
                size = int(RISK_DOLLARS / risk_per_share)
                max_size = int((INITIAL_CAPITAL * 0.25) / price)
                size = min(max(size, 1), max_size)
                
                s["position_size"] = size
                total_fixed_size += 1

        day["signals"] = active_signals
        cleaned_journal.append(day)

    # Save backup just in case
    backup_path = JOURNAL_PATH.with_suffix(".json.bak")
    os.system(f"cp {JOURNAL_PATH} {backup_path}")

    with open(JOURNAL_PATH, "w") as f:
        json.dump(cleaned_journal, f, indent=2)

    print(f"Journal Cleaned:")
    print(f" - Removed {total_removed_combo} signals from old inactive combos.")
    print(f" - Removed {total_removed_broadcast} signals due to broadcast bug (duplicate prices).")
    print(f" - Fixed position_size=0 for {total_fixed_size} setups.")
    print(f" - Original backed up to {backup_path}")

if __name__ == "__main__":
    fix_journal()
