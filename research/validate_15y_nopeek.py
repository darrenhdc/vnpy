"""research/validate_15y_nopeek.py — 前10年train选参，后5年test报告"""
import sys, math
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd
import numpy as np
from research.data_loader import load_data

df = load_data('SPY', '1d', '15y')
df['_dt'] = pd.to_datetime(df['date'], utc=True)

# Split: first 10y train, last 5y test
mid = df['_dt'].iloc[0] + pd.DateOffset(years=10)
_train = df[df['_dt'] < mid].reset_index(drop=True)
_test = df[df['_dt'] >= mid].reset_index(drop=True)
print(f"Train: {len(_train)}d ({str(_train['_dt'].iloc[0])[:10]} ~ {str(_train['_dt'].iloc[-1])[:10]})")
print(f"Test:  {len(_test)}d ({str(_test['_dt'].iloc[0])[:10]} ~ {str(_test['_dt'].iloc[-1])[:10]})")
print()

def search_params(df_train):
    """Grid search on train only"""
    best = {'s': -99}
    for f in [3, 5, 10, 20]:
        for s in [10, 15, 20, 30, 50]:
            if f >= s: continue
            fc = df_train['close'].rolling(f, min_periods=1).mean()
            sc = df_train['close'].rolling(s, min_periods=1).mean()
            gc = (fc > sc) & (fc.shift(1) <= sc.shift(1))
            dc = (fc < sc) & (fc.shift(1) >= sc.shift(1))
            cash, sh, vals = 10000.0, 0.0, []
            for i in range(len(df_train)):
                c = float(df_train['close'].iloc[i])
                if i > 0:
                    if bool(gc.iloc[i-1]) and sh <= 0:
                        a = min(cash*0.3, cash)
                        if a>=100: sh=(a-a*0.00001)/float(df_train['open'].iloc[i]); cash-=a
                    elif bool(dc.iloc[i-1]) and sh > 0:
                        cash += sh*float(df_train['open'].iloc[i])*(1-0.00001); sh=0
                vals.append(cash+sh*c)
            rets = pd.Series(vals).pct_change().dropna()
            sharpe = float((rets.mean()/rets.std())*math.sqrt(252)) if len(rets)>=5 and rets.std()>0 else 0
            if sharpe > best['s']:
                best = {'s': sharpe, 'f': f, 'sl': s}
    return best

def test_params(df_test, fast, slow):
    """Test with fixed params on test data"""
    fc = df_test['close'].rolling(fast, min_periods=1).mean()
    sc = df_test['close'].rolling(slow, min_periods=1).mean()
    gc = (fc > sc) & (fc.shift(1) <= sc.shift(1))
    dc = (fc < sc) & (fc.shift(1) >= sc.shift(1))
    cash, sh, vals, trades = 10000.0, 0.0, [], 0
    for i in range(len(df_test)):
        c = float(df_test['close'].iloc[i])
        if i > 0:
            if bool(gc.iloc[i-1]) and sh <= 0:
                a = min(cash*0.3, cash)
                if a>=100: sh=(a-a*0.00001)/float(df_test['open'].iloc[i]); cash-=a; trades+=1
            elif bool(dc.iloc[i-1]) and sh > 0:
                cash += sh*float(df_test['open'].iloc[i])*(1-0.00001); sh=0; trades+=1
        vals.append(cash+sh*c)
    rets = pd.Series(vals).pct_change().dropna()
    s = float((rets.mean()/rets.std())*math.sqrt(252)) if len(rets)>=5 and rets.std()>0 else 0
    dd = float(((pd.Series(vals)-pd.Series(vals).cummax())/pd.Series(vals).cummax().replace(0,float('nan'))).min()*100)
    r = (vals[-1]/10000-1)*100
    bh = (float(df_test['close'].iloc[-1])/float(df_test['close'].iloc[0])-1)*100
    return {'sharpe': s, 'ret': r, 'dd': dd, 'trades': trades, 'bh': bh}

# 1. Search on train (no peek at test)
best = search_params(_train)
print(f"Train search best: fast={best['f']} slow={best['sl']} Train Sharpe={best['s']:.3f}")

# 2. Test on out-of-sample (this is the TRUE Sharpe)
r_test = test_params(_test, best['f'], best['sl'])
print(f"Test  OOS:         fast={best['f']} slow={best['sl']} Test  Sharpe={r_test['sharpe']:.3f}")

# 3. Also show what happens if we ran the 5y params on test
r_5y = test_params(_test, 5, 15)
print(f"Test  5y params:   fast=5 slow=15       Test  Sharpe={r_5y['sharpe']:.3f}")

print()
print("=" * 60)
print(f"{'Metric':<20} {'Train (10y)':>15} {'Test (5y OOS)':>15}")
print(f"{'Sharpe':<20} {best['s']:>15.3f} {r_test['sharpe']:>15.3f}")
print(f"{'Return %':<20} {'':>15} {r_test['ret']:>+14.1f}%")
print(f"{'MaxDD %':<20} {'':>15} {r_test['dd']:>+14.1f}%")
print(f"{'Trades':<20} {'':>15} {r_test['trades']:>15}")
print(f"{'B&H %':<20} {'':>15} {r_test['bh']:>+14.1f}%")
print()
print(f"5y params on Test: Sharpe={r_5y['sharpe']:.3f}")
print(f"Train-to-Test decay: {r_test['sharpe']-best['s']:+.3f} ({(1-r_test['sharpe']/best['s'])*100:.0f}% drop)")
