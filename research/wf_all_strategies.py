"""research/wf_all_strategies.py — 所有候选策略统一用 13年逐年WF 重新诊断"""
import sys, math
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd, numpy as np
from research.data_loader import load_data
from research.backtest import _ensure_ma

df = load_data('SPY', '1d', '15y')
df['_dt'] = pd.to_datetime(df['date'], utc=True)
df['year'] = df['_dt'].dt.year
years = sorted(df['year'].unique())
MIN_TRAIN = 3

# ===== Common utilities =====
def bt_on(d, signals, order_pct=0.3):
    """Backtest given a pre-computed signal series"""
    cash, sh, vals, t = 10000.0, 0.0, [], 0
    for i in range(len(d)):
        c = float(d['close'].iloc[i])
        if i > 0:
            sig = int(signals.iloc[i-1]) if i-1 < len(signals) else 0
            po = float(d['open'].iloc[i])
            if sig == 1 and sh <= 0:
                a = min(cash*order_pct, cash)
                if a >= 100: sh = (a-a*0.00001)/po; cash -= a; t += 1
            elif sig == -1 and sh > 0:
                cash += sh*po*(1-0.00001); sh = 0; t += 1
        vals.append(cash+sh*c)
    rets = pd.Series(vals).pct_change().dropna()
    s = float((rets.mean()/rets.std())*math.sqrt(252)) if len(rets)>=5 and rets.std()>0 else 0
    dd = float(((pd.Series(vals)-pd.Series(vals).cummax())/pd.Series(vals).cummax().replace(0,float('nan'))).min()*100)
    r = (vals[-1]/10000-1)*100
    return s, r, dd, t

def gen_signals(d, strategy, **kw):
    """Generate signal series for a strategy"""
    sig = pd.Series(0, index=d.index, dtype=int)
    if strategy == 'ma_cross':
        fast = kw.get('fast', 10); slow = kw.get('slow', 15)
        fc = _ensure_ma(d, fast); sc = _ensure_ma(d, slow)
        gc = (d[fc] > d[sc]) & (d[fc].shift(1) <= d[sc].shift(1))
        dc = (d[fc] < d[sc]) & (d[sc].shift(1) >= d[fc].shift(1))
        sig[gc] = 1; sig[dc] = -1
    elif strategy == 'macd':
        fast = kw.get('fast', 12); slow = kw.get('slow', 26); signal = kw.get('signal', 9)
        ef = d['close'].ewm(span=fast, adjust=False).mean()
        es = d['close'].ewm(span=slow, adjust=False).mean()
        macd = ef - es; sig_line = macd.ewm(span=signal, adjust=False).mean()
        cross_up = (macd > sig_line) & (macd.shift(1) <= sig_line.shift(1))
        cross_down = (macd < sig_line) & (macd.shift(1) >= sig_line.shift(1))
        sig[cross_up] = 1; sig[cross_down] = -1
    elif strategy == 'ma_rsi_sell':
        fast = kw.get('fast', 10); slow = kw.get('slow', 15); sell_min = kw.get('sell_min', 40)
        fc = _ensure_ma(d, fast); sc = _ensure_ma(d, slow)
        gc = (d[fc] > d[sc]) & (d[fc].shift(1) <= d[sc].shift(1))
        dc = (d[fc] < d[sc]) & (d[sc].shift(1) >= d[fc].shift(1))
        delta = d['close'].diff()
        g = delta.clip(lower=0).ewm(alpha=1/14, adjust=False).mean()
        l = (-delta.clip(upper=0)).ewm(alpha=1/14, adjust=False).mean()
        rsi = 100.0 - (100.0/(1.0 + g/l.replace(0, float('nan'))))
        sig[gc] = 1; sig[dc & (rsi > sell_min)] = -1
    return sig

# ===== Strategy parameter grids =====
STRATEGIES = {
    'MA Cross (10/15)': {
        'strategy': 'ma_cross',
        'grid': lambda: [{'fast': f, 'slow': s} for f in [3,5,10] for s in [15,20,30] if f < s]
    },
    'MA Cross (5/15)': {
        'strategy': 'ma_cross',
        'grid': lambda: [{'fast': f, 'slow': s} for f in [3,5,10] for s in [15,20,30] if f < s]
    },
    'MACD': {
        'strategy': 'macd',
        'grid': lambda: [{'fast': f, 'slow': s, 'signal': sg}
                         for f in [8,12,16] for s in [21,26,30] if f < s for sg in [7,9,12]]
    },
    'MA+RSI SellFilter': {
        'strategy': 'ma_rsi_sell',
        'grid': lambda: [{'fast': f, 'slow': s, 'sell_min': sm}
                         for f in [3,5,10] for s in [15,20,30] if f < s
                         for sm in [30, 40, 50]]
    },
}

print("=" * 110)
print("UNIFIED 13-YEAR YEARLY WALK-FORWARD — ALL STRATEGIES")
print("=" * 110)
print(f"{'Strategy':<22} {'Mean OOS':>9} {'Median':>8} {'Std':>8} {'Pos Yrs':>8} {'Neg Yrs':>8} {'Best':>8} {'Worst':>8}")
print("-" * 110)

results = {}
for sname, sdef in STRATEGIES.items():
    oos_sharpes = []
    for i, yr in enumerate(years):
        if i < MIN_TRAIN: continue
        train_mask = df['year'] < yr
        test_mask = df['year'] == yr
        train_df = df[train_mask].reset_index(drop=True)
        test_df = df[test_mask].reset_index(drop=True)

        # Grid search on train
        best_train_s = -99
        best_params = None
        for params in sdef['grid']():
            sigs = gen_signals(train_df, sdef['strategy'], **params)
            s, _, _, _ = bt_on(train_df, sigs)
            if s > best_train_s: best_train_s = s; best_params = params

        # Test on OOS year
        sigs_test = gen_signals(test_df, sdef['strategy'], **best_params)
        s_test, _, _, _ = bt_on(test_df, sigs_test)
        oos_sharpes.append(s_test)

    mean_s = np.mean(oos_sharpes)
    med_s = np.median(oos_sharpes)
    std_s = np.std(oos_sharpes)
    pos = sum(1 for s in oos_sharpes if s > 0)
    neg = len(oos_sharpes) - pos
    best_s = max(oos_sharpes)
    worst_s = min(oos_sharpes)
    results[sname] = {'mean': mean_s, 'median': med_s, 'std': std_s,
                      'pos': pos, 'neg': neg, 'best': best_s, 'worst': worst_s,
                      'all': oos_sharpes}

    print(f"{sname:<22} {mean_s:>9.3f} {med_s:>8.3f} {std_s:>8.3f} {pos:>4}/{len(oos_sharpes):<3} {neg:>4}/{len(oos_sharpes):<3} {best_s:>8.3f} {worst_s:>8.3f}")

# ===== Rank =====
print()
print("=" * 110)
print("RANKED BY MEAN OOS SHARPE")
print("=" * 110)
for sname in sorted(results, key=lambda x: -results[x]['mean']):
    r = results[sname]
    bar = "█" * int(r['pos'])
    print(f"  {r['mean']:+.3f}  {sname:<24}  {bar} ({r['pos']}/{r['pos']+r['neg']} pos)")

# ===== Yearly detail for best non-SOTA =====
sota_name = 'MA Cross (10/15)'
best_other = max((k for k in results if k != sota_name), key=lambda k: results[k]['mean'])
print()
print("=" * 110)
print(f"Yearly Detail: {best_other} vs {sota_name}")
print("=" * 110)
sota_vals = results[sota_name]['all']
other_vals = results[best_other]['all']
for i, (yr, sv, ov) in enumerate(zip(years[MIN_TRAIN:], sota_vals, other_vals)):
    diff = ov - sv
    flag = "✅" if diff > 0 else "❌" if diff < 0 else "="
    print(f"  {yr}  SOTA={sv:+.3f}  {best_other}={ov:+.3f}  Δ={diff:+.3f}  {flag}")
