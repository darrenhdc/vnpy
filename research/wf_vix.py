"""research/wf_vix.py — VIX 加入 13y WF 诊断"""
import sys, math
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd, numpy as np, yfinance as yf
from research.data_loader import load_data
from research.backtest import _ensure_ma

df = load_data('SPY', '1d', '15y')
df['_dt'] = pd.to_datetime(df['date'], utc=True)
df['year'] = df['_dt'].dt.year
years = sorted(df['year'].unique())

# Download VIX
vix_raw = yf.download('^VIX', period='15y', interval='1d', progress=False)
try: vix_raw.index = vix_raw.index.tz_convert(None)
except TypeError: pass
vix_raw['_dt'] = vix_raw.index

# Merge VIX with SPY on nearest date
vix_close = vix_raw['Close']
if isinstance(vix_close, pd.DataFrame): 
    vix_close = vix_close.iloc[:, 0]  # MultiIndex -> Series
vix_s = pd.Series(vix_close.values, index=vix_raw['_dt'].dt.date, name='vix_close')
df['date_only'] = df['_dt'].dt.date
df['vix_close'] = df['date_only'].map(vix_s).ffill()
print(f"SPY+VIX merged: {len(df)} days, VIX coverage: {df['vix_close'].notna().sum()}/{len(df)}")

def bt_on(d, signals, order_pct=0.3):
    cash, sh, vals, t = 10000.0, 0.0, [], 0
    for i in range(len(d)):
        c = float(d['close'].iloc[i]) if pd.notna(d['close'].iloc[i]) else 0
        if i > 0:
            sig = int(signals.iloc[i-1]) if i-1 < len(signals) and pd.notna(signals.iloc[i-1]) else 0
            po = float(d['open'].iloc[i]) if pd.notna(d['open'].iloc[i]) else c
            if po <= 0: po = c
            if sig == 1 and sh <= 0:
                a = min(cash*order_pct, cash)
                if a >= 100: sh = (a-a*0.00001)/po; cash -= a; t += 1
            elif sig == -1 and sh > 0:
                cash += sh*po*(1-0.00001); sh = 0; t += 1
        vals.append(cash+sh*c)
    rets = pd.Series(vals).pct_change().dropna()
    s = float((rets.mean()/rets.std())*math.sqrt(252)) if len(rets)>=5 and rets.std()>0 else 0
    return s

# SOTA baseline: MA+RSI SellFilter
def gen_sota(d, fast=10, slow=15, sell_min=50):
    fc = _ensure_ma(d, fast); sc = _ensure_ma(d, slow)
    gc = (d[fc]>d[sc])&(d[fc].shift(1)<=d[sc].shift(1))
    dc = (d[fc]<d[sc])&(d[fc].shift(1)>=d[sc].shift(1))
    delta = d['close'].diff()
    g = delta.clip(lower=0).ewm(alpha=1/14, adjust=False).mean()
    l = (-delta.clip(upper=0)).ewm(alpha=1/14, adjust=False).mean()
    rsi = 100-(100/(1+g/l.replace(0,float('nan'))))
    sigs = pd.Series(0, index=d.index, dtype=int)
    sigs[gc] = 1; sigs[dc&(rsi>sell_min)] = -1
    return sigs

# VIX strategies
def gen_vix_buy_gate(d, fast=10, slow=15, sell_min=50, vix_max=25):
    """Don't buy if VIX > threshold"""
    sigs = gen_sota(d, fast, slow, sell_min)
    if 'vix_close' in d.columns:
        high_vix = d['vix_close'] > vix_max
        sigs.loc[sigs == 1] = sigs[sigs == 1].where(~high_vix, 0)
    return sigs

def gen_vix_sell_gate(d, fast=10, slow=15, sell_min=50, vix_panic=35):
    """Force sell if VIX spikes regardless of MA"""
    sigs = gen_sota(d, fast, slow, sell_min)
    if 'vix_close' in d.columns:
        panic = d['vix_close'] > vix_panic
        sigs.loc[panic] = -1
    return sigs

STRATEGIES = {
    'SOTA (MA+RSI)': {
        'fn': gen_sota,
        'grid': lambda: [{'fast': f, 'slow': s, 'sell_min': sm}
                         for f in [5,10] for s in [15,20] if f<s for sm in [50]]
    },
    'SOTA + VIX BuyGate': {
        'fn': gen_vix_buy_gate,
        'grid': lambda: [{'fast': 10, 'slow': 15, 'sell_min': 50, 'vix_max': v}
                         for v in [20, 25, 30, 35]]
    },
    'SOTA + VIX SellGate': {
        'fn': gen_vix_sell_gate,
        'grid': lambda: [{'fast': 10, 'slow': 15, 'sell_min': 50, 'vix_panic': v}
                         for v in [30, 35, 40, 45]]
    },
}

print()
print("=" * 100)
print("13-YEAR YEARLY WF — VIX STRATEGIES")
print("=" * 100)
print(f"{'Strategy':<25} {'Mean OOS':>9} {'Median':>8} {'Std':>8} {'Pos Yrs':>8} {'Neg Yrs':>8}")
print("-" * 100)

results = {}
for sname, sdef in STRATEGIES.items():
    oos_sharpes = []
    for i, yr in enumerate(years):
        if i < 3: continue
        train_mask = df['year'] < yr
        test_mask = df['year'] == yr
        train_df = df[train_mask].reset_index(drop=True)
        test_df = df[test_mask].reset_index(drop=True)

        best_train_s = -99; best_params = None
        for params in sdef['grid']():
            sigs = sdef['fn'](train_df, **params)
            s = bt_on(train_df, sigs)
            if s > best_train_s: best_train_s = s; best_params = params

        sigs_test = sdef['fn'](test_df, **best_params)
        s_test = bt_on(test_df, sigs_test)
        oos_sharpes.append(s_test)

    mean_s = np.mean(oos_sharpes)
    med_s = np.median(oos_sharpes)
    std_s = np.std(oos_sharpes)
    pos = sum(1 for s in oos_sharpes if s > 0)
    neg = len(oos_sharpes) - pos
    results[sname] = {'mean': mean_s, 'median': med_s, 'std': std_s, 'pos': pos, 'neg': neg, 'all': oos_sharpes}
    print(f"{sname:<25} {mean_s:>9.3f} {med_s:>8.3f} {std_s:>8.3f} {pos:>4}/{len(oos_sharpes):<3} {neg:>4}/{len(oos_sharpes):<3}")

# VIX vs SOTA statistical test
sota_vals = results['SOTA (MA+RSI)']['all']
print()
print("Yearly Comparison vs SOTA:")
for sname in ['SOTA + VIX BuyGate', 'SOTA + VIX SellGate']:
    vals = results[sname]['all']
    wins = sum(1 for s, v in zip(sota_vals, vals) if v > s)
    delta = results[sname]['mean'] - results['SOTA (MA+RSI)']['mean']
    print(f"  {sname}: Δ={delta:+.3f}, wins {wins}/13 years")
