"""Verify sell_min=60 is genuinely selected by train search"""
import sys, math
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import pandas as pd, numpy as np
from research.data_loader import load_data

df = load_data('SPY', '1d', '15y')
df['_dt'] = pd.to_datetime(df['date'], utc=True)
df['year'] = df['_dt'].dt.year
years = sorted(df['year'].unique())

def bt(d, signals):
    cash,sh,vals = 10000.0,0.0,[]
    for i in range(len(d)):
        c=float(d['close'].iloc[i])
        if i>0:
            sig=int(signals.iloc[i-1]) if i-1<len(signals) else 0
            po=float(d['open'].iloc[i])
            if sig==1 and sh<=0:
                a=min(cash*0.3,cash)
                if a>=100: sh=(a-a*0.00001)/po; cash-=a
            elif sig==-1 and sh>0:
                cash+=sh*po*(1-0.00001); sh=0
        vals.append(cash+sh*c)
    rets=pd.Series(vals).pct_change().dropna()
    return float((rets.mean()/rets.std())*math.sqrt(252)) if len(rets)>=5 and rets.std()>0 else 0

sm_picks = {}
oos_all = []
print(f"{'Year':<6} {'Best':<14} {'TrainS':>8} {'TestS':>8} {'SM':>6}")
print('-' * 50)

for i, yr in enumerate(years):
    if i < 3: continue
    train = df[df['year']<yr].reset_index(drop=True)
    test = df[df['year']==yr].reset_index(drop=True)

    d = train['close'].diff()
    g = d.clip(lower=0).ewm(alpha=1/14, adjust=False).mean()
    l = (-d.clip(upper=0)).ewm(alpha=1/14, adjust=False).mean()
    rsi = 100-(100/(1+g/l.replace(0, float('nan'))))

    best = {'s': -99}
    for f in [3,5,10]:
        for sl in [15,20,30]:
            if f >= sl: continue
            for sm in [50, 60, 70]:
                fc = train['close'].rolling(f, min_periods=1).mean()
                sc = train['close'].rolling(sl, min_periods=1).mean()
                gc = (fc>sc)&(fc.shift(1)<=sc.shift(1))
                dc = (fc<sc)&(fc.shift(1)>=sc.shift(1))
                sigs = pd.Series(0, index=train.index); sigs[gc] = 1
                sigs[dc&(rsi>sm)] = -1
                s = bt(train, sigs)
                if s > best['s']: best = {'s':s,'f':f,'sl':sl,'sm':sm}

    # Test
    d_t = test['close'].diff()
    g_t = d_t.clip(lower=0).ewm(alpha=1/14, adjust=False).mean()
    l_t = (-d_t.clip(upper=0)).ewm(alpha=1/14, adjust=False).mean()
    rsi_t = 100-(100/(1+g_t/l_t.replace(0, float('nan'))))
    fc_t = test['close'].rolling(best['f'], min_periods=1).mean()
    sc_t = test['close'].rolling(best['sl'], min_periods=1).mean()
    gc_t = (fc_t>sc_t)&(fc_t.shift(1)<=sc_t.shift(1))
    dc_t = (fc_t<sc_t)&(fc_t.shift(1)>=sc_t.shift(1))
    sigs_t = pd.Series(0, index=test.index); sigs_t[gc_t] = 1
    sigs_t[dc_t&(rsi_t>best['sm'])] = -1
    s_t = bt(test, sigs_t)
    oos_all.append(s_t)
    sm_picks[best['sm']] = sm_picks.get(best['sm'], 0) + 1
    param = f"({best['f']}/{best['sl']}/{best['sm']})"
    print(f"{yr:<6} {param:<14} {best['s']:>8.3f} {s_t:>8.3f} {best['sm']:>6}")

print()
print(f"Mean OOS: {np.mean(oos_all):.3f}  Median: {np.median(oos_all):.3f}  Pos: {sum(1 for s in oos_all if s>0)}/{len(oos_all)}")
print(f"sell_min distribution: {sm_picks}")
