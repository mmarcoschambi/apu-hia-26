import pandas as pd, sqlite3

df = pd.read_csv('/home/marcos/trade/momentum-v2/outputs/backtests/complete_trades_clean.csv')
print('Trades:', len(df))
df['entry_date'] = pd.to_datetime(df['entry_date'])
print(df.groupby(df['entry_date'].dt.to_period('M'))['pnl'].agg(['count','sum']).round(0).to_string())
print()
print(df[['symbol','entry_date','exit_date','exit_phase','pnl']].to_string())

# Checar cuantos dias tuvieron señales
eq = pd.read_csv('/home/marcos/trade/momentum-v2/outputs/backtests/equity_curve.csv')
print()
print('Dias en equity_curve:', len(eq))
print('Equity final:', eq.iloc[-1].values)
