import pandas as pd
df = pd.read_csv("outputs/paper_finviz/2026-05-04/rejection_audit.csv")
print(df[['ticker', 'sector_etf', 'sector_etf_dist']].head(5))
