import subprocess
r = subprocess.run(["grep", "-n", "backtest_results\|trades_df\|to_csv\|pattern_confidence\|pattern_type", 
    "/home/marcos/trade/momentum-v2/src/backtest/vectorbt_engine_advanced.py"], capture_output=True, text=True)
for line in r.stdout.split("\n")[:40]:
    print(line)