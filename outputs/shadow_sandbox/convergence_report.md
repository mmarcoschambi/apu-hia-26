# Shadow Convergence Report: Backtest vs. Paper Trader VPS (May 2026)

**Verdict:** **NO CONVERGE**

## Executive Summary
A convergence test was executed comparing the local backtester (`backtest_via_signal_engine.py`) using setups generated from Finviz snapshots against the trades executed by the live paper trader on the VPS during May 2026. 

The live paper trader on the VPS registered 2 trades:
1. **ADM** (Entry: May 18, Exit: May 19)
2. **NXPI** (Entry: May 18/19, Exit: May 19)

However, the local backtester under the new snapshot-based setups source did not execute these trades. Instead, the local backtest generated 3 different trades:
- **ADEA** (Entry: 2026-05-06)
- **LRCX** (Entry: 2026-05-11)
- **EQNR** (Entry: 2026-05-19)

## Root Cause Analysis
The discrepancy is caused by a data mismatch between the VPS cron logs (`logs/vps/cron_finviz_monitor.log`) and the Finviz snapshots (`outputs/paper_finviz/*/snapshot.json`) that were synchronized to the local environment:

1. **Log Presence:** The VPS logs explicitly outputted `ADM` (May 18) and `NXPI` (May 19) under the `🏆 HIGH QUALITY SETUPS` table printed to stdout. This is why the legacy log-based ETL previously captured them.
2. **Snapshot Absence:** A deep inspection of the local Finviz snapshots (`outputs/paper_finviz/2026-05-18/snapshot.json` and `outputs/paper_finviz/2026-05-19/snapshot.json`) shows that **neither ADM nor NXPI exist** in the `watchlist_detail` dictionary. For example, on May 19, the snapshot contains 185 tickers in its watchlist, but `NXPI` is entirely missing.
3. **Implication:** Since the local setups directory (`outputs/shadow_sandbox/finviz_runs/`) is rebuilt purely from the snapshot JSONs (as implemented in issue #36), `ADM` and `NXPI` were not present in the backtester's universe for those dates, preventing their replication.
4. **Partial Universe Limitation (Watchlist Detail vs. Crudos):** A critical structural limitation is that the `watchlist_detail` dictionary in the snapshots contains only a filtered subset of 331 unique watchlist tickers, whereas the raw scanned universe ("crudos") contains 591 tickers. This represents a significant coverage gap (where ~44% of the raw universe is omitted from `watchlist_detail`), directly contributing to missing valid signals in the simulation.

## Local Backtest Execution Details
- **Command Run:** `python3 scripts/backtest_via_signal_engine.py --universe-source shadow_finviz --start 2026-05-01 --end 2026-05-29 --tag shadow_may_2026 --exclude-sectors XLV`
- **Universe Source:** `shadow_finviz` (reads setups from `outputs/shadow_sandbox/finviz_runs/`)
- **Metrics Summary:**
  - **Total Return:** 0.06%
  - **Max Drawdown (MDD):** -7.25%
  - **Total Trades:** 3

### Generated Trades List
| Symbol | Entry Date | Exit Date | Entry Price | Exit Price | PnL | Sizing | Exit Phase |
|--------|------------|------------|-------------|------------|-----|--------|------------|
| **ADEA** | 2026-05-06 | 2026-05-18 | $27.98 | $27.35 | $1,398.07 | 1206 shares | TP1+STOP |
| **LRCX** | 2026-05-11 | 2026-05-19 | $292.66 | $273.38 | -$3,533.13 | 134 shares | STOP |
| **EQNR** | 2026-05-19 | 2026-05-27 | $40.90 | $36.50 | -$5,131.29 | 1225 shares | STOP_GAP |

## Recommended Action / Next Steps
The convergence failed due to an incomplete synchronization or a generation bug on the VPS side that caused the snapshots to miss tickers that were printed in the logs.
- **Next Issue Goal:** Investigate why the VPS `snapshot.json` generation logic differs from the watchlist printed in the VPS log. 
- Ensure that the VPS script `run_finviz_monitor.py` or equivalent updates and serializes the exact same watchlist to `snapshot.json` that it prints to the logs.
