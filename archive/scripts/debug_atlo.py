import yfinance as yf
import pandas as pd

symbol = "ATLO"
print(f"Fetching data for {symbol} around Jan 25, 2022...")
ticker = yf.Ticker(symbol)
# Fetch history
df = ticker.history(start="2022-01-20", end="2022-02-10", auto_adjust=False)

print("\n--- Data around Jan 25, 2022 (Unadjusted vs Adjusted) ---")
cols = ['Open', 'High', 'Low', 'Close', 'Adj Close']
print(df[cols])

# Also check for splits/dividends
print("\n--- Actions (Dividends/Splits) ---")
print(ticker.actions.loc["2021-01-01":"2023-01-01"])