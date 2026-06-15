import sys
from pathlib import Path
ROOT = Path(".").resolve()
sys.path.insert(0, str(ROOT))
from scripts.paper_finviz import SECTOR_MAP

t = "EL"
s_data = {"sector_etf": None, "sector_etf_dist": None}

etf_sym = s_data.get("sector_etf")
if not etf_sym:
    etf_sym = SECTOR_MAP.get(t, "")

print("etf_sym:", etf_sym)
print("audit dict sector_etf:", etf_sym)
print("audit dict dist:", s_data.get("sector_etf_dist", ""))
