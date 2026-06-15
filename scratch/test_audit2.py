import json
import sys
from pathlib import Path
import pandas as pd
ROOT = Path(".").resolve()
sys.path.insert(0, str(ROOT))
from scripts.paper_finviz import SECTOR_MAP

df = pd.read_csv("outputs/paper_finviz/2026-05-04/rejection_audit.csv")
for t in df['ticker'].head(5):
    print(f"'{t}' -> map says: '{SECTOR_MAP.get(t, 'MISSING')}'")
