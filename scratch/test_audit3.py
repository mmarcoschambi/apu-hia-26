import json
import sys
from pathlib import Path
import pandas as pd
ROOT = Path(".").resolve()
sys.path.insert(0, str(ROOT))
from scripts.paper_finviz import SECTOR_MAP, get_etf_dists

dists_cache = get_etf_dists("2026-05-04")
print("dists_cache:", dists_cache)

for t in ["EL", "MU", "MO", "FANG"]:
    etf_sym = SECTOR_MAP.get(t, "")
    etf_dist = dists_cache.get(etf_sym, "") if etf_sym else ""
    print(f"{t}: sym={etf_sym}, dist={etf_dist}")
