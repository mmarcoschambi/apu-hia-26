import json, sqlite3, time, warnings
import pandas as pd
import yfinance as yf

warnings.filterwarnings("ignore")

audit = json.load(open("outputs/paper_trading/universe_audit.json"))
missing = audit["combined_missing"]
print(f"Downloading {len(missing)} missing SP500+R1000 tickers...")

conn = sqlite3.connect("data/ticker_cache.db")
success, skip, errors = 0, 0, 0

for i in range(0, len(missing), 20):
    batch = missing[i:i+20]
    try:
        import io, contextlib
        with contextlib.redirect_stderr(io.StringIO()):
            df = yf.download(" ".join(batch), period="2y",
                             auto_adjust=True, progress=False, timeout=30)
        if df is None or df.empty:
            skip += len(batch); time.sleep(1); continue

        if isinstance(df.columns, pd.MultiIndex):
            for ticker in batch:
                try:
                    if ticker not in df.columns.get_level_values(1):
                        skip += 1; continue
                    t_df = df.xs(ticker, axis=1, level=1).dropna(subset=["Close"]).reset_index()
                    if t_df.empty: skip += 1; continue
                    t_df["Date"] = pd.to_datetime(t_df["Date"]).dt.strftime("%Y-%m-%d")
                    n = 0
                    for _, row in t_df.iterrows():
                        try:
                            conn.execute(
                                "INSERT OR REPLACE INTO ohlcv_cache (ticker,date,open,high,low,close,volume) VALUES (?,?,?,?,?,?,?)",
                                (ticker, row["Date"],
                                 float(row.get("Open") or 0), float(row.get("High") or 0),
                                 float(row.get("Low") or 0), float(row.get("Close") or 0),
                                 float(row.get("Volume") or 0))
                            ); n += 1
                        except: pass
                    conn.commit()
                    if n > 0: success += 1
                    else: skip += 1
                except: skip += 1
        else:
            ticker = batch[0]
            t_df = df.reset_index()
            t_df.columns = [c[0] if isinstance(c,tuple) else c for c in t_df.columns]
            t_df = t_df.dropna(subset=["Close"])
            t_df["Date"] = pd.to_datetime(t_df["Date"]).dt.strftime("%Y-%m-%d")
            n = 0
            for _, row in t_df.iterrows():
                try:
                    conn.execute("INSERT OR REPLACE INTO ohlcv_cache (ticker,date,open,high,low,close,volume) VALUES (?,?,?,?,?,?,?)",
                        (ticker, row["Date"], float(row.get("Open") or 0), float(row.get("High") or 0),
                         float(row.get("Low") or 0), float(row.get("Close") or 0), float(row.get("Volume") or 0))); n+=1
                except: pass
            conn.commit()
            if n > 0: success += 1
            else: skip += 1
        pct = (i+len(batch)) / len(missing) * 100
        print(f"  [{i+len(batch)}/{len(missing)} {pct:.0f}%] ok={success} skip={skip}")
        time.sleep(0.5)
    except Exception as e:
        errors += len(batch); print(f"  ERR batch {i}: {e}"); time.sleep(2)

conn.close()
print(f"\nDone: {success} added | {skip} not available | {errors} errors")

# Verify coverage
conn2 = sqlite3.connect("data/ticker_cache.db")
now_in_db = set(r[0] for r in conn2.execute(
    "SELECT DISTINCT ticker FROM ohlcv_cache WHERE date >= '2026-01-01'").fetchall())
conn2.close()
combined = set(audit["combined_missing"]) | set(audit.get("sp500_current",[]))
covered = set(audit.get("combined_missing",[])) - (set(audit.get("combined_missing",[])) - now_in_db)
sp500 = set(audit.get("sp500_current",[]))
r1000 = set(audit.get("r1000_current",[]))
print(f"\nFinal coverage:")
print(f"  SP500: {len(sp500 & now_in_db)}/{len(sp500)} ({len(sp500 & now_in_db)/len(sp500)*100:.1f}%)")
print(f"  R1000: {len(r1000 & now_in_db)}/{len(r1000)} ({len(r1000 & now_in_db)/len(r1000)*100:.1f}%)")