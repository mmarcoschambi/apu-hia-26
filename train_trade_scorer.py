import os, sys, warnings, pickle
import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime

warnings.filterwarnings('ignore')
ROOT = '/home/marcos/trade/momentum-v2'
os.chdir(ROOT)
sys.path.insert(0, ROOT)

import lightgbm as lgb
from sklearn.model_selection import TimeSeriesSplit
from sklearn.metrics import roc_auc_score
from sklearn.preprocessing import LabelEncoder

print('='*60)
print('STEP 1: Loading trade data')
print('='*60)

sources = [
    ('outputs/3tier_optimization/baseline_trades.csv', 'baseline'),
    ('outputs/backtests/complete_trades.csv',          'complete'),
    ('outputs/backtests/backtest_results_enriched.csv','enriched'),
]

def normalize_df(df, source):
    out = pd.DataFrame()
    out['symbol']     = df.get('symbol', df.get('ticker', float('nan')))
    out['entry_date'] = pd.to_datetime(df.get('entry_date'), errors='coerce')
    out['_source']    = source
    for col in ['r_multiple','context_rvol','context_adr','entry_score',
                'dist_sma20_pct','stop_distance_pct','context_dollar_vol',
                'sector_momentum_20d','market_health_score','hold_days']:
        out[col] = pd.to_numeric(df.get(col), errors='coerce')
    out['pattern_confidence'] = pd.to_numeric(df.get('pattern_confidence', 0.0), errors='coerce').fillna(0.0)
    out['context_vol'] = pd.to_numeric(df.get('context_vol', df.get('context_volume')), errors='coerce')
    for col in ['vix_regime','entry_stage','sector_strength']:
        out[col] = df.get(col)
    return out

all_parts = []
for path, src in sources:
    try:
        raw = pd.read_csv(path)
        raw['_source'] = src
        all_parts.append(normalize_df(raw, src))
        print('  ' + src + ': ' + str(len(raw)) + ' trades')
    except Exception as e:
        print('  ' + src + ': SKIP (' + str(e) + ')')

df = pd.concat(all_parts, ignore_index=True)
df = df.sort_values('entry_date').drop_duplicates(subset=['symbol','entry_date'], keep='last')
df = df.dropna(subset=['r_multiple','entry_date']).reset_index(drop=True)
print('  Total after dedup: ' + str(len(df)) + ' trades')
print('  Date range: ' + str(df['entry_date'].min().date()) + ' - ' + str(df['entry_date'].max().date()))

# STEP 2: Enrich with VIX + market regime
print('')
print('STEP 2: Enriching with VIX + market regime')
try:
    from src.utils.market_regime import load_spy_vix_data, MarketRegimeClassifier
    from src.data.data_provider import DataProvider
    dp  = DataProvider()
    t0  = df['entry_date'].min().strftime('%Y-%m-%d')
    t1  = df['entry_date'].max().strftime('%Y-%m-%d')
    spy_data, vix_data = load_spy_vix_data(t0, t1, cache=dp)
    clf = MarketRegimeClassifier(spy_data, vix_data)
    regime_df = clf.classify_all()
    df['_dk'] = df['entry_date'].dt.normalize()
    if 'stage' in regime_df.columns:
        df['market_stage_ml'] = df['_dk'].map(regime_df['stage'])
        print('  market_stage_ml: ' + str(df['market_stage_ml'].notna().sum()) + ' filled')
    else:
        df['market_stage_ml'] = float('nan')
    vix_s = vix_data['close'] if hasattr(vix_data,'columns') and 'close' in vix_data.columns else (vix_data if isinstance(vix_data, pd.Series) else None)
    if vix_s is not None:
        df['vix_at_entry'] = df['_dk'].map(vix_s.to_dict())
        print('  vix_at_entry: ' + str(df['vix_at_entry'].notna().sum()) + ' filled')
    else:
        df['vix_at_entry'] = float('nan')
    df.drop(columns=['_dk'], inplace=True)
    print('  Regime enrichment: OK')
except Exception as e:
    print('  Regime enrichment SKIPPED: ' + str(e))
    df['market_stage_ml'] = float('nan')
    df['vix_at_entry'] = float('nan')

# STEP 3: RS multi-timeframe
print('')
print('STEP 3: RS multi-timeframe (20d + 60d)')
try:
    from src.data.data_provider import DataProvider
    dp   = DataProvider()
    t0   = df['entry_date'].min().strftime('%Y-%m-%d')
    t1   = df['entry_date'].max().strftime('%Y-%m-%d')
    syms = df['symbol'].dropna().unique().tolist()
    print('  Loading prices for ' + str(len(syms)) + ' symbols...')
    prices = dp.get_prices(syms, t0, t1)
    if prices is not None and not prices.empty:
        rs60 = prices.pct_change(60).rank(axis=1, pct=True) * 100
        rs20 = prices.pct_change(20).rank(axis=1, pct=True) * 100
        v60, v20 = [], []
        for _, row in df.iterrows():
            sym = row['symbol']; date = row['entry_date']
            try:
                idx = prices.index.get_indexer([date], method='nearest')[0]
                dk  = prices.index[idx]
                v60.append(float(rs60.loc[dk, sym]) if sym in rs60.columns else float('nan'))
                v20.append(float(rs20.loc[dk, sym]) if sym in rs20.columns else float('nan'))
            except:
                v60.append(float('nan')); v20.append(float('nan'))
        df['rs_60d'] = v60; df['rs_20d'] = v20
        df['rs_divergence'] = df['rs_60d'] - df['rs_20d']
        print('  rs_60d: ' + str(df['rs_60d'].notna().sum()) + ' filled')
        print('  rs_20d: ' + str(df['rs_20d'].notna().sum()) + ' filled')
    else:
        raise ValueError('prices empty')
except Exception as e:
    print('  RS enrichment SKIPPED: ' + str(e))
    df['rs_60d'] = df['rs_20d'] = df['rs_divergence'] = float('nan')

# STEP 4: Targets
print('')
print('STEP 4: Targets')
df['hit_1r']    = (df['r_multiple'] >= 1.0).astype(int)
df['is_winner'] = (df['r_multiple'] >= 0.0).astype(int)
df['is_big_win']= (df['r_multiple'] >= 2.0).astype(int)
for t in ['hit_1r','is_winner','is_big_win']:
    print('  ' + t + ': ' + str(df[t].sum()) + '/' + str(len(df)) + ' = ' + '{:.1%}'.format(df[t].mean()))

# STEP 5: Features
print('')
print('STEP 5: Feature engineering')
for col in ['vix_regime','entry_stage','sector_strength','market_stage_ml']:
    le = LabelEncoder()
    df[col+'_enc'] = le.fit_transform(df[col].fillna('UNKNOWN').astype(str))

df['rvol_adr_ratio']   = df['context_rvol'] / (df['context_adr'] + 0.01)
df['rs_momentum_flag'] = ((df['rs_20d'] > df['rs_60d']) & (df['rs_60d'] > 60)).astype(float)
df['month']            = df['entry_date'].dt.month
df['weekday']          = df['entry_date'].dt.weekday
df['log_dollar_vol']   = np.log1p(df['context_dollar_vol'].fillna(0))

CANDIDATES = [
    'context_rvol','context_adr','entry_score',
    'dist_sma20_pct','stop_distance_pct','pattern_confidence',
    'rvol_adr_ratio','log_dollar_vol',
    'rs_60d','rs_20d','rs_divergence','rs_momentum_flag',
    'vix_at_entry','market_stage_ml_enc','vix_regime_enc',
    'entry_stage_enc','sector_strength_enc',
    'sector_momentum_20d','market_health_score',
    'month','weekday',
]
FEATURES = [f for f in CANDIDATES if f in df.columns and df[f].notna().mean() >= 0.20]
print('  Features selected: ' + str(len(FEATURES)))
for f in FEATURES:
    print('    ' + f.ljust(32) + ' fill=' + '{:.0%}'.format(df[f].notna().mean()))

# STEP 6: Walk-forward CV
print('')
print('STEP 6: Walk-forward CV (3 folds)')
TARGET = 'hit_1r'
df_m = df[FEATURES + [TARGET,'entry_date','r_multiple']].dropna(subset=[TARGET])
df_m = df_m.sort_values('entry_date').reset_index(drop=True)
X = df_m[FEATURES].fillna(df_m[FEATURES].median())
y = df_m[TARGET].values
print('  Dataset: ' + str(len(X)) + ' samples | ' + '{:.1%}'.format(y.mean()) + ' positive')

lgb_params = dict(
    objective='binary', metric='auc',
    n_estimators=300, learning_rate=0.05,
    max_depth=4, num_leaves=15, min_child_samples=15,
    subsample=0.8, colsample_bytree=0.8,
    reg_alpha=0.1, reg_lambda=1.0,
    random_state=42, verbose=-1, n_jobs=-1,
)
tscv = TimeSeriesSplit(n_splits=3)
oof_probs = np.zeros(len(X))
oof_auc = []
importances = []

for fold, (tr_idx, val_idx) in enumerate(tscv.split(X)):
    Xtr, Xv = X.iloc[tr_idx], X.iloc[val_idx]
    ytr, yv = y[tr_idx], y[val_idx]
    m = lgb.LGBMClassifier(**lgb_params)
    m.fit(Xtr, ytr, eval_set=[(Xv, yv)],
          callbacks=[lgb.early_stopping(30, verbose=False), lgb.log_evaluation(period=-1)])
    probs = m.predict_proba(Xv)[:,1]
    oof_probs[val_idx] = probs
    auc = roc_auc_score(yv, probs)
    oof_auc.append(auc)
    importances.append(pd.Series(m.feature_importances_, index=FEATURES))
    vd = df_m['entry_date'].iloc[val_idx]
    print('  Fold ' + str(fold+1) + ': train=' + str(len(tr_idx)).rjust(4) +
          ' | val=' + str(len(val_idx)).rjust(4) +
          ' (' + str(vd.min().date()) + ' -> ' + str(vd.max().date()) + ')' +
          ' | AUC=' + '{:.4f}'.format(auc))

mean_auc = float(np.mean(oof_auc))
print('  OOF AUC: ' + '{:.4f}'.format(mean_auc) + ' +/- ' + '{:.4f}'.format(float(np.std(oof_auc))))

# STEP 7: Precision@top30 + lift
print('')
print('STEP 7: Precision @ top 30% + lift by quintile')
oof_df = df_m.copy()
oof_df['prob'] = oof_probs
oof_valid = oof_df[oof_df['prob'] > 0].copy()
thr30 = 0.5
if len(oof_valid) > 10:
    thr30 = float(np.percentile(oof_valid['prob'], 70))
    top30 = oof_valid[oof_valid['prob'] >= thr30]
    rest  = oof_valid[oof_valid['prob'] <  thr30]
    print('  Threshold p70: ' + '{:.3f}'.format(thr30))
    print('  TOP 30%: n=' + str(len(top30)) +
          ' | hit_1r=' + '{:.1%}'.format(top30[TARGET].mean()) +
          ' | R_mean=' + '{:.3f}'.format(top30['r_multiple'].mean()))
    print('  REST 70%: n=' + str(len(rest)) +
          ' | hit_1r=' + '{:.1%}'.format(rest[TARGET].mean()) +
          ' | R_mean=' + '{:.3f}'.format(rest['r_multiple'].mean()))
    lift = top30[TARGET].mean() / (y.mean() + 1e-9)
    print('  Lift vs base: ' + '{:.2f}x'.format(lift))
    oof_valid['quintile'] = pd.qcut(oof_valid['prob'], q=5,
        labels=['Q1(lowest)','Q2','Q3','Q4','Q5(highest)'])
    qstats = oof_valid.groupby('quintile', observed=True).agg(
        n=('r_multiple','count'), hit_1r=(TARGET,'mean'), r_mean=('r_multiple','mean'))
    print('  Quintile breakdown:')
    print(qstats.to_string())

# STEP 8: Final model
print('')
print('STEP 8: Final model on full dataset')
final_model = lgb.LGBMClassifier(**lgb_params)
final_model.fit(X, y, callbacks=[lgb.log_evaluation(period=-1)])
imp = pd.concat(importances, axis=1).mean(axis=1).sort_values(ascending=False)
print('  Feature importance:')
for feat, val in imp.items():
    bar = chr(9608) * int(val / imp.max() * 25)
    print('  ' + feat.ljust(32) + ' ' + bar.ljust(25) + ' ' + '{:.1f}'.format(val))

# STEP 9: Save
print('')
print('STEP 9: Saving')
Path('models').mkdir(exist_ok=True)
payload = {
    'model': final_model, 'features': FEATURES, 'target': TARGET,
    'oof_auc': mean_auc, 'oof_auc_std': float(np.std(oof_auc)),
    'trained_on': datetime.now().isoformat(), 'n_trades': len(X),
    'positive_rate': float(y.mean()), 'threshold_top30': thr30,
    'lgb_params': lgb_params, 'feature_importance': imp.to_dict(),
}
with open('models/trade_scorer_lgbm.pkl','wb') as f:
    pickle.dump(payload, f)
imp.reset_index().rename(columns={'index':'feature',0:'importance'}).to_csv(
    'models/feature_importance.csv', index=False)
df.to_csv('models/training_dataset.csv', index=False)
print('  models/trade_scorer_lgbm.pkl  -- SAVED')
print('  models/feature_importance.csv -- SAVED')
print('  models/training_dataset.csv   -- SAVED')
print('  OOF AUC: ' + '{:.4f}'.format(mean_auc) + '  (>0.55=useful, >0.60=solid)')
print('='*60)
print('DONE')
print('='*60)
