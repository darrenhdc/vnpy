"""research/wf_yearly.py — 15年逐年 Walk-Forward: expanding train, 1y test"""
import sys, math
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd, numpy as np
from research.data_loader import load_data

df = load_data('SPY', '1d', '15y')
df['_dt'] = pd.to_datetime(df['date'], utc=True)
df['year'] = df['_dt'].dt.year
years = sorted(df['year'].unique())
print(f"SPY 15y: {years[0]}-{years[-1]}, {len(years)} years, {len(df)} days\n")

MIN_TRAIN = 3  # minimum 3 years of training

def run_bt_on(d, fast, slow):
    fc = d['close'].rolling(fast, min_periods=1).mean()
    sc = d['close'].rolling(slow, min_periods=1).mean()
    gc = (fc>sc)&(fc.shift(1)<=sc.shift(1))
    dc = (fc<sc)&(fc.shift(1)>=sc.shift(1))
    cash,sh,vals,t = 10000.0,0.0,[],0
    for i in range(len(d)):
        c=float(d['close'].iloc[i])
        if i>0:
            if bool(gc.iloc[i-1]) and sh<=0:
                a=min(cash*0.3,cash)
                if a>=100: sh=(a-a*0.00001)/float(d['open'].iloc[i]); cash-=a; t+=1
            elif bool(dc.iloc[i-1]) and sh>0:
                cash+=sh*float(d['open'].iloc[i])*(1-0.00001); sh=0; t+=1
        vals.append(cash+sh*c)
    rets=pd.Series(vals).pct_change().dropna()
    s=float((rets.mean()/rets.std())*math.sqrt(252)) if len(rets)>=5 and rets.std()>0 else 0
    dd=float(((pd.Series(vals)-pd.Series(vals).cummax())/pd.Series(vals).cummax().replace(0,float('nan'))).min()*100)
    r=(vals[-1]/10000-1)*100
    bh=(float(d['close'].iloc[-1])/float(d['close'].iloc[0])-1)*100
    return s,r,dd,t,bh

def search_train(train_df):
    best={'s':-99}
    for f in [3,5,10]:
        for s in [15,20,30]:
            if f>=s: continue
            sharpe,_,_,_,_ = run_bt_on(train_df, f, s)
            if sharpe>best['s']: best={'s':sharpe,'f':f,'sl':s}
    return best

print(f"{'Train':<20} {'Test':<8} {'BestParam':<12} {'TrainS':>7} {'TestS':>7} {'TestR':>8} {'TestDD':>8} {'Trades':>6} {'TestB&H':>8}")
print('='*95)

results = []
for i, yr in enumerate(years):
    if i < MIN_TRAIN:
        continue  # skip years before min train

    train_mask = df['year'] < yr
    test_mask = df['year'] == yr
    train_df = df[train_mask].reset_index(drop=True)
    test_df = df[test_mask].reset_index(drop=True)

    # Search on expanding window
    b = search_train(train_df)

    # Test on this year
    s,r,dd,t,bh = run_bt_on(test_df, b['f'], b['sl'])

    train_years = f"{years[0]}-{yr-1}"
    print(f"{train_years:<20} {yr:<8} ({b['f']:2d}/{b['sl']:2d})      {b['s']:>7.3f} {s:>7.3f} {r:>+7.1f}% {dd:>+7.1f}% {t:>6} {bh:>+7.1f}%")
    results.append({'year': yr, 'train_s': b['s'], 'test_s': s, 'test_r': r, 'test_dd': dd,
                    'trades': t, 'bh': bh, 'fast': b['f'], 'slow': b['sl']})

# Summary
oos_sharpes = [r['test_s'] for r in results]
print()
print('=' * 95)
print(f"WF Summary ({len(results)} OOS years)")
print(f"  OOS Sharpe: mean={np.mean(oos_sharpes):.3f}  median={np.median(oos_sharpes):.3f}  std={np.std(oos_sharpes):.3f}")
print(f"  Range: [{min(oos_sharpes):.3f}, {max(oos_sharpes):.3f}]")
pos_years = sum(1 for s in oos_sharpes if s > 0)
neg_years = sum(1 for s in oos_sharpes if s <= 0)
print(f"  Positive: {pos_years}/{len(results)}  Negative: {neg_years}/{len(results)}")
print(f"  25th pct: {np.percentile(oos_sharpes, 25):.3f}  75th pct: {np.percentile(oos_sharpes, 75):.3f}")

# Show param stability
print(f"\n  Params across years: (fast/slow)")
for r in results:
    print(f"    {r['year']}: ({r['fast']:2d}/{r['slow']:2d})  S={r['test_s']:.3f}  R={r['test_r']:+5.1f}%")
