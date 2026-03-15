import sqlite3, time, sys, warnings, io, contextlib
from datetime import datetime, timedelta
import yfinance as yf
import pandas as pd
from collections import defaultdict

warnings.filterwarnings("ignore")

DB = "data/ticker_cache.db"
TODAY = datetime.now().strftime("%Y-%m-%d")
DRY = "--dry-run" in sys.argv

conn = sqlite3.connect(DB)
r = conn.execute("SELECT MAX(date), COUNT(DISTINCT ticker) FROM ohlcv_cache").fetchone()
print(f"DB max date: {r[0]} | Total tickers: {r[1]}")

# Genuinely behind = last_date before March 2026 AND substantial real data
candidates = conn.execute("""
    SELECT ticker, MAX(date) as last_date, COUNT(*) as n_days
    FROM ohlcv_cache
    GROUP BY ticker
    HAVING MAX(date) < '2026-03-01' AND COUNT(*) > 200
    ORDER BY last_date DESC
""").fetchall()

print(f"Genuinely behind tickers: {len(candidates)}")

if DRY:
    for t,d,n in candidates[:15]: print(f"  {t}: last={d} ({n} days)")
    sys.exit(0)

by_date = defaultdict(list)
for t, d, n in candidates:
    by_date[d].append(t)

BATCH = 50
success, skip, errors = 0, 0, 0
total = len(candidates)
processed = 0

for last_date, tickers in sorted(by_date.items(), reverse=True):
    gap_start = (pd.to_datetime(last_date) + pd.Timedelta(days=1)).strftime("%Y-%m-%d")

    for i in range(0, len(tickers), BATCH):
        sub = tickers[i:i+BATCH]
        processed += len(sub)
        pct = processed / total * 100

        if processed % 100 < BATCH:
            print(f"  [{processed}/{total} {pct:.1f}%] ok={success} skip={skip} err={errors} | gap_start={gap_start}")

        try:
            with contextlib.redirect_stderr(io.StringIO()):
                df = yf.download(
                    " ".join(sub), start=gap_start, end=TODAY,
                    auto_adjust=True, progress=False, timeout=30
                )

            if df is None or df.empty:
                skip += len(sub)
                time.sleep(0.5)
                continue

            if isinstance(df.columns, pd.MultiIndex):
                for ticker in sub:
                    try:
                        if ticker not in df.columns.get_level_values(1):
                            skip += 1
                            continue
                        t_df = df.xs(ticker, axis=1, level=1).dropna(subset=["Close"]).reset_index()
                        if t_df.empty:
                            skip += 1
                            continue
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
                                )
                                n += 1
                            except Exception: pass
                        conn.commit()
                        if n > 0: success += 1
                        else: skip += 1
                    except Exception: skip += 1
            else:
                ticker = sub[0]
                df2 = df.reset_index()
                df2.columns = [c[0] if isinstance(c, tuple) else c for c in df2.columns]
                df2 = df2.dropna(subset=["Close"])
                df2["Date"] = pd.to_datetime(df2["Date"]).dt.strftime("%Y-%m-%d")
                n = 0
                for _, row in df2.iterrows():
                    try:
                        conn.execute(
                            "INSERT OR REPLACE INTO ohlcv_cache (ticker,date,open,high,low,close,volume) VALUES (?,?,?,?,?,?,?)",
                            (ticker, row["Date"],
                             float(row.get("Open") or 0), float(row.get("High") or 0),
                             float(row.get("Low") or 0), float(row.get("Close") or 0),
                             float(row.get("Volume") or 0))
                        )
                        n += 1
                    except Exception: pass
                conn.commit()
                if n > 0: success += 1
                else: skip += 1

            time.sleep(0.3)

        except Exception as e:
            errors += len(sub)
            print(f"  ERR: {str(e)[:80]}")
            time.sleep(3)

print(f"\nDone: {success} updated | {skip} no new data | {errors} errors")
r2 = conn.execute("SELECT COUNT(DISTINCT ticker) FROM ohlcv_cache WHERE date >= '2026-03-01'").fetchone()
print(f"Tickers with 2026 data: {r2[0]}")
conn.close()