from src.utils.sector_rotation import SECTOR_MAP
import pandas as pd

df = pd.read_csv("outputs/paper_finviz/2026-05-04/rejection_audit.csv")
for t in df['ticker'].head(5):
    print(f"Ticker: {t}, SECTOR_MAP: {SECTOR_MAP.get(t, 'NONE')}")
