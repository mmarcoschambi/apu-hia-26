import sys, json, sqlite3, warnings, logging
sys.path.insert(0, '/home/marcos/trade/momentum-v2')
warnings.filterwarnings('ignore')
logging.basicConfig(level=logging.WARNING)
import pandas as pd, numpy as np
from src.backtest.vectorbt_engine_advanced import AdvancedVectorBTEngine
with open('/home/marcos/trade/momentum-v2/config/production_config.json') as f: cfg = json.load(f)
t1=cfg['tier1_strategy']; t2=cfg['tier2_filters']
BASE = dict(tp1_r=t1['tp1_r'],tp2_r=t1['tp2_r'],tp1_pct=t1['tp1_pct'],tp2_pct=t1['tp2_pct'],runner_pct=t1.get('runner_pct',0.2),score_rs_weight=t1.get('score_rs_weight',0.7),score_proximity_weight=t1.get('score_proximity_weight',0.3),min_rvol=t2['min_rvol'],min_adr=t2['min_adr'],max_dist_sma20=t2['max_dist_sma20'],min_dollar_volume=t2.get('min_dollar_volume',99000000),min_consolidation_days=5,min_volume=100000,require_positive_rs=True,use_rs_percentile=True,min_rs_percentile=70.0,rs_lookback_days=60,use_pattern_filter=False,min_pattern_confidence=0.5,pattern_cache_path='data/pattern_matrix.pkl',pattern_bonus_high=0.0,pattern_bonus_med=0.0,pattern_bonus_low=0.0,mode='production',fees=0.001,slippage=0.001,risk_dollars=1000,signal_type='any',require_spy_above_sma50=True,max_vix_threshold=35.0,use_market_regime_filter=True,block_trades_in_stage3=True,block_trades_in_stage4=True,use_earnings_calendar=False,use_trailing_stop=False,use_adaptive_filtering=True,use_pit_universe=False)
conn=sqlite3.connect('/home/marcos/trade/momentum-v2/data/ticker_cache.db')
rows=conn.execute('SELECT DISTINCT ticker FROM ohlcv_cache GROUP BY ticker HAVING COUNT(*)>800 ORDER BY ticker LIMIT 80').fetchall()
conn.close(); universe=[r[0] for r in rows]

def run_it(label, extra):
    print(f'--- {label} ---')
    eng=AdvancedVectorBTEngine(universe=universe,start_date='2019-01-01',end_date='2025-12-31',initial_capital=100000,**{**BASE,**extra})
    eng.load_data(); r=eng.run_backtest()
    df=eng.trades_df if hasattr(eng,'trades_df') and eng.trades_df is not None else pd.DataFrame()
    t=r.get('total_trades',0); sh=r.get('sharpe_ratio',0); pf=r.get('profit_factor',0)
    wr=r.get('win_rate',0)*100; cagr=r.get('cagr',0)*100; dd=r.get('max_drawdown',0)*100
    print(f'  Trades={t} Sharpe={sh:.2f} PF={pf:.2f} WR={wr:.1f}% CAGR={cagr:.2f}% MaxDD={dd:.1f}%')
    return r, df

print('='*55); print('PATRON: FILTRO DURO vs SIN FILTRO'); print('='*55)
r1,df1=run_it('SIN filtro patron',{'use_pattern_filter':False})
if len(df1)>0 and 'pattern_confidence' in df1.columns:
    hp=df1['pattern_confidence']>0
    print(f'  Con patron: {hp.sum()} ({hp.mean()*100:.1f}%) | Sin patron: {(~hp).sum()}')
    for lbl,mask in [('CON patron',hp),('SIN patron',~hp)]:
        sub=df1[mask]
        if len(sub)<3: continue
        win=sub[sub['pnl']>0]; los=sub[sub['pnl']<=0]
        wr2=len(win)/len(sub)*100
        pf2=abs(win['pnl'].sum()/los['pnl'].sum()) if len(los)>0 else 999
        avg=sub['pnl'].mean()
        print(f'  {lbl}: n={len(sub)} WR={wr2:.1f}% PF={pf2:.2f} avg_pnl={avg:.0f}')
    print('  Por tipo de patron:')
    for pt in df1[hp]['pattern_type'].dropna().unique():
        sub=df1[df1['pattern_type']==pt]
        if len(sub)<3: continue
        win=sub[sub['pnl']>0]; los=sub[sub['pnl']<=0]
        wr2=len(win)/len(sub)*100
        pf2=abs(win['pnl'].sum()/los['pnl'].sum()) if len(los)>0 else 999
        c=sub['pattern_confidence'].mean()
        print(f'    {pt}: n={len(sub)} WR={wr2:.1f}% PF={pf2:.2f} conf={c:.3f}')
    print('  Por nivel de confianza:')
    for lo2,hi2,lbl2 in [(0,.3,'Baja'),(.3,.5,'Med-Baja'),(.5,.7,'Media'),(.7,.9,'Alta'),(.9,1.01,'Muy Alta')]:
        sub=df1[(df1['pattern_confidence']>=lo2)&(df1['pattern_confidence']<hi2)]
        if len(sub)<3: continue
        win=sub[sub['pnl']>0]; wr2=len(win)/len(sub)*100; avg=sub['pnl'].mean()
        print(f'    {lbl2} ({lo2:.1f}-{hi2:.1f}): n={len(sub)} WR={wr2:.1f}% avg={avg:.0f}')
else: print(f'  Sin cols patron. Cols: {list(df1.columns)[:8]}')

r2,df2=run_it('CON filtro conf>=0.5',{'use_pattern_filter':True,'min_pattern_confidence':0.5})
r3,df3=run_it('CON filtro conf>=0.7',{'use_pattern_filter':True,'min_pattern_confidence':0.7})
print('='*55)
print('RESUMEN:')
for lbl,r in [('Sin filtro',r1),('Conf>=0.5',r2),('Conf>=0.7',r3)]:
    t=r.get('total_trades',0); sh=r.get('sharpe_ratio',0); pf=r.get('profit_factor',0)
    wr=r.get('win_rate',0)*100; cagr=r.get('cagr',0)*100
    print(f'{lbl:<20} T={t:>4} Sh={sh:.2f} PF={pf:.2f} WR={wr:.1f}% CAGR={cagr:.2f}%')
best_sh = max(r2.get('sharpe_ratio',0), r3.get('sharpe_ratio',0))
if best_sh > r1.get('sharpe_ratio',0) and min(r2.get('total_trades',0),r3.get('total_trades',0)) >= 50:
    print('CONCLUSION: Filtro de patron MEJORA el sistema')
else:
    print('CONCLUSION: Filtro de patron NO mejora — mantener sin filtro')
