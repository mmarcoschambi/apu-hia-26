import json
import subprocess
import sys

def read_json_message(process):
    line = process.stdout.readline()
    if not line:
        return None
    try:
        return json.loads(line)
    except Exception as e:
        print(f"Error parsing line: {line.strip()} - {e}", file=sys.stderr)
        return None

def write_json_message(process, message):
    process.stdin.write(json.dumps(message) + "\n")
    process.stdin.flush()

def main():
    print("Starting Engram MCP server...")
    process = subprocess.Popen(
        ["/home/marcos/.local/bin/engram", "mcp"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )

    # 1. Initialize MCP connection
    print("Initializing...")
    write_json_message(process, {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "mcp-client", "version": "1.0.0"}
        }
    })
    
    init_resp = read_json_message(process)
    if not init_resp or "error" in init_resp:
        print("Initialization failed:", init_resp, file=sys.stderr)
        sys.exit(1)
    
    # Send initialized notification
    write_json_message(process, {
        "jsonrpc": "2.0",
        "method": "notifications/initialized"
    })

    # 2. Call mem_session_summary
    session_summary_content = """## Goal
Audit and fix the profit_factor: 999 / win_rate: 100% / trades: 33197 optimizer anomaly. Resolve loader discrepancies, metadata export bugs, secure validation gates, and normalize committee rubric settings (ic_rubric.yaml) to enable capital_enabled trading safely.

## Instructions
- Change validation_passed default in optimize_combo.py to False to block promotion of unvalidated runs.
- Normalize config/ic_rubric.yaml combo_decisions structure and capital fields to match combo JSON configs exactly.
- Enable capital_enabled: true in combo_pure_momentum.json once validation and trade counting bugs are resolved.

## Discoveries
- Anomaly Causa Raíz: vectorbt_engine_advanced.py mapped total_trades to entries.sum().sum() (signals) instead of executed positions. The simulation calculated real PnL, resulting in PF: 999 and WR: 100% when only 1-2 trades executed successfully without loss. The inflated count bypassed Optuna's robustness filters.
- Gate Bypass: skip_validation=True left validation_passed=True by default. Taponado by changing default to False.
- Rubric Drift: ic_rubric.yaml used capital_paper_usd instead of paper_trading_capital_usd, and lacked capital_enabled. Unified.
- Submodule & Untracked Files: sp500/sp500 pointer is kept uncommitted locally to prevent data drift, while .codex/ and scratch/mock_telegram_alerts.py are local debug tools.

## Accomplished
- Mapped total_trades to unique executed trades.
- Corrected validation_passed default value to False.
- Fixed root path definitions and added optuna space fallback in optimize_combo.py.
- Formally set capital_enabled: true in config/combos/combo_pure_momentum.json.
- Normalized capital keys (capital_enabled and paper_trading_capital_usd) across all combos in config/ic_rubric.yaml.
- Recorded 6 new ADR entries in DECISIONS.md.
- Reverted staging config file to original state.
- Commited all changes up to commit 75d2d48.
- Passed 6/6 tests.

## Next Steps
- Monitor live execution under weekly framework."""

    print("Calling mem_session_summary...")
    write_json_message(process, {
        "jsonrpc": "2.0",
        "id": 2,
        "method": "tools/call",
        "params": {
            "name": "mem_session_summary",
            "arguments": {
                "content": session_summary_content
            }
        }
    })
    
    summary_resp = read_json_message(process)
    print("mem_session_summary response:")
    print(json.dumps(summary_resp, indent=2))

    # 3. Call mem_save
    memory_content = "**What**: Normalized capital keys (capital_enabled and paper_trading_capital_usd) in config/ic_rubric.yaml to match combo JSON configs exactly, resolving config metadata drift.\n**Why**: Prevent governance and staging drift.\n**Where**: config/ic_rubric.yaml, DECISIONS.md."
    
    print("Calling mem_save...")
    write_json_message(process, {
        "jsonrpc": "2.0",
        "id": 3,
        "method": "tools/call",
        "params": {
            "name": "mem_save",
            "arguments": {
                "title": "Normalized capital keys in ic_rubric.yaml to match JSON configs",
                "type": "decision",
                "scope": "project",
                "topic_key": "governance/ic-rubric-normalization",
                "content": memory_content,
                "project": "momentum-v2"
            }
        }
    })
    
    save_resp = read_json_message(process)
    print("mem_save response:")
    print(json.dumps(save_resp, indent=2))

    process.stdin.close()
    process.terminate()

if __name__ == "__main__":
    main()
