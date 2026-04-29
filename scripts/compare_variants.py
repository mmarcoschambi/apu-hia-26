#!/usr/bin/env python3
import os
import json
import pandas as pd
from glob import glob

def compare_variants():
    outputs_dir = "outputs/backtests"
    variant_files = glob(os.path.join(outputs_dir, "variant_*_IS.json"))
    
    results = []
    for f in variant_files:
        variant_name = os.path.basename(f).replace("variant_", "").replace("_IS.json", "")
        with open(f, 'r') as j:
            data = json.load(j)
            stats = data.get("trade_stats", {})
            quality = data.get("overall_quality", {})
            
            # Find corresponding OOS file
            oos_file = f.replace("_IS.json", "_OOS.json")
            oos_pf = 0.0
            oos_trades = 0
            if os.path.exists(oos_file):
                with open(oos_file, 'r') as jo:
                    data_o = json.load(jo)
                    oos_pf = data_o.get("overall_quality", {}).get("profit_factor", 0.0)
                    oos_trades = data_o.get("trade_stats", {}).get("trades", 0)
            
            results.append({
                "Variant": variant_name,
                "IS Trades": stats.get("trades", 0),
                "IS PF": quality.get("profit_factor", 0.0),
                "IS CAGR%": stats.get("cagr_pct", 0.0),
                "OOS Trades": oos_trades,
                "OOS PF": oos_pf
            })
    
    if not results:
        print("No variants found.")
        return
        
    df = pd.DataFrame(results)
    print("\nVariant Comparison (Summary):")
    print(df.to_string(index=False))

if __name__ == "__main__":
    compare_variants()
