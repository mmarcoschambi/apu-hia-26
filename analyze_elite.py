import json

with open('outputs/walkforward/20260428_195119/walkforward_report.json') as f:
    data = json.load(f)

for res in data['results']:
    print(f"\n--- Modo: {res['mode']} ---")
    for f in res['folds']:
        m = f['oos_metrics']
        pf = m['profit_factor']
        pf_str = f"{pf:.2f}" if pf is not None else "INF"
        print(f"Fold {f['fold']} OOS (desde {f['oos_start']}):")
        print(f"  Trades: {m['trades']} | PF: {pf_str}")
        print(f"  PnL: ${m['total_pnl']:,.2f} | MaxDD: {m['max_drawdown']*100:.2f}% | WinRate: {m['win_rate']*100:.1f}%")
        print(f"  AvgWin: ${m['avg_win']:,.2f} | AvgLoss: ${m['avg_loss']:,.2f}")
