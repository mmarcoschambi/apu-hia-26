import json
with open('outputs/walkforward/20260428_104051/walkforward_report.json') as f:
    data = json.load(f)
for res in data['results']:
    for f in res['folds']:
        m = f['oos_metrics']
        print(f"Fold {f['fold']} OOS (desde {f['oos_start']}):")
        print(f"  Trades: {m['trades']} | PF: {m['profit_factor']}")
        print(f"  PnL: ${m['total_pnl']:,.2f} | MaxDD: {m['max_drawdown']*100:.2f}% | WinRate: {m['win_rate']*100:.1f}%")
        print(f"  AvgWin: ${m['avg_win']:,.2f} | AvgLoss: ${m['avg_loss']:,.2f}")
