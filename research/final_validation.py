"""research/final_validation.py — 最终验证：锁定方法 → holdout → 跨资产"""
import sys, math
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd, numpy as np
from research.data_loader import load_data, load_multi_assets

# ══════════════════════════════════════════
# PHASE 1: 锁定方法论（此块之后永不改动）
# ══════════════════════════════════════════
METHODOLOGY = {
    'strategy': 'MA Cross + RSI SellFilter',
    'entry': 'MA(fast) > MA(slow) golden cross, no filter',
    'exit': 'MA(fast) < MA(slow) death cross AND RSI(14) > sell_min',
    'param_grid': {
        'fast': [3, 5, 10],
        'slow': [15, 20, 30],
        'sell_min': [50, 60, 70],
    },
    'validation': 'Expanding yearly WF, 3y min train, grid search on train only',
    'order_size': 0.30,
    'fee': 0.00001,
    'locked_at': '2026-06-04',
}
print("METHODOLOGY LOCKED")
print("=" * 60)
for k, v in METHODOLOGY.items():
    print(f"  {k}: {v}")
print()

# ══════════════════════════════════════════
# Common backtest
# ══════════════════════════════════════════
def bt_rs(d, fast, slow, sell_min, rsi_vals=None):
    """Backtest with MA+RSI SellFilter on ONE dataset"""
    fc = d['close'].rolling(fast, min_periods=1).mean()
    sc = d['close'].rolling(slow, min_periods=1).mean()
    gc = (fc>sc)&(fc.shift(1)<=sc.shift(1))
    dc = (fc<sc)&(fc.shift(1)>=sc.shift(1))
    if rsi_vals is None:
        d_ = d['close'].diff()
        g = d_.clip(lower=0).ewm(alpha=1/14, adjust=False).mean()
        l = (-d_.clip(upper=0)).ewm(alpha=1/14, adjust=False).mean()
        rsi_vals = 100-(100/(1+g/l.replace(0,float('nan'))))
    sigs = pd.Series(0, index=d.index, dtype=int)
    sigs[gc] = 1; sigs[dc&(rsi_vals>sell_min)] = -1

    cash, sh, vals, t = 10000.0, 0.0, [], 0
    for i in range(len(d)):
        c = float(d['close'].iloc[i])
        if i > 0:
            sig = int(sigs.iloc[i-1]) if i-1 < len(sigs) else 0
            po = float(d['open'].iloc[i])
            if sig == 1 and sh <= 0:
                a = min(cash * 0.3, cash)
                if a >= 100: sh = (a-a*0.00001)/po; cash -= a; t += 1
            elif sig == -1 and sh > 0:
                cash += sh*po*(1-0.00001); sh = 0; t += 1
        vals.append(cash+sh*c)

    rets = pd.Series(vals).pct_change().dropna()
    s = float((rets.mean()/rets.std())*math.sqrt(252)) if len(rets)>=5 and rets.std()>0 else 0
    dd = float(((pd.Series(vals)-pd.Series(vals).cummax())/pd.Series(vals).cummax().replace(0,float('nan'))).min()*100)
    r = (vals[-1]/10000-1)*100
    bh = (float(d['close'].iloc[-1])/float(d['close'].iloc[0])-1)*100
    return s, r, dd, t, bh

def grid_search(d):
    """Search all param combos on training data. Returns best params."""
    d_ = d['close'].diff()
    g = d_.clip(lower=0).ewm(alpha=1/14, adjust=False).mean()
    l = (-d_.clip(upper=0)).ewm(alpha=1/14, adjust=False).mean()
    rsi = 100-(100/(1+g/l.replace(0,float('nan'))))
    best = {'s': -99}
    for f in METHODOLOGY['param_grid']['fast']:
        for sl in METHODOLOGY['param_grid']['slow']:
            if f >= sl: continue
            for sm in METHODOLOGY['param_grid']['sell_min']:
                s, _, _, _, _ = bt_rs(d, f, sl, sm, rsi)
                if s > best['s']: best = {'s': s, 'f': f, 'sl': sl, 'sm': sm}
    return best

def yearly_wf(df, name):
    """Expanding yearly WF for one asset."""
    years = sorted(df['year'].unique())
    oos_sharpes = []
    sm_picks = {}
    for i, yr in enumerate(years):
        if i < 3: continue
        train = df[df['year']<yr].reset_index(drop=True)
        test = df[df['year']==yr].reset_index(drop=True)
        best = grid_search(train)
        s, _, _, _, _ = bt_rs(test, best['f'], best['sl'], best['sm'])
        oos_sharpes.append(s)
        sm_picks[best['sm']] = sm_picks.get(best['sm'], 0) + 1
    mean_s = np.mean(oos_sharpes)
    pos = sum(1 for s in oos_sharpes if s > 0)
    most_common_sm = max(sm_picks, key=sm_picks.get)
    sm_stability = sm_picks.get(most_common_sm, 0)
    return {'name': name, 'mean': mean_s, 'median': np.median(oos_sharpes),
            'std': np.std(oos_sharpes), 'pos': pos, 'total': len(oos_sharpes),
            'sm_picks': sm_picks, 'oos': oos_sharpes, 'best_sm': most_common_sm,
            'sm_stability': sm_stability}

# ══════════════════════════════════════════
# PHASE 2: SPY 2026 Holdout (true OOS)
# ══════════════════════════════════════════
print("PHASE 2: SPY 2026 Holdout")
print("=" * 60)

df_spy = load_data('SPY', '1d', '15y')
df_spy['_dt'] = pd.to_datetime(df_spy['date'], utc=True)
df_spy['year'] = df_spy['_dt'].dt.year

train_all = df_spy[df_spy['year'] < 2026].reset_index(drop=True)
test_2026 = df_spy[df_spy['year'] == 2026].reset_index(drop=True)

best_all = grid_search(train_all)
s_2026, r_2026, dd_2026, t_2026, bh_2026 = bt_rs(test_2026, best_all['f'], best_all['sl'], best_all['sm'])

print(f"Train: 2011-2025 ({len(train_all)}d)")
print(f"Test:  2026 YTD ({len(test_2026)}d) — TRULY UNSEEN")
print(f"Params from train: ({best_all['f']}/{best_all['sl']}/{best_all['sm']})")
print(f"Train Sharpe: {best_all['s']:.3f}")
print(f"2026 OOS: Sharpe={s_2026:.3f}  Ret={r_2026:+.1f}%  MaxDD={dd_2026:+.1f}%  Trades={t_2026}  B&H={bh_2026:+.1f}%")
print()

# Also run full WF on SPY for reference
wf_spy = yearly_wf(df_spy, 'SPY')
print(f"SPY Full WF: mean OOS={wf_spy['mean']:.3f}, pos={wf_spy['pos']}/{wf_spy['total']}, "
      f"best_sm={wf_spy['best_sm']}({wf_spy['sm_stability']}/{wf_spy['total']})")
print()

# ══════════════════════════════════════════
# PHASE 3: Cross-asset validation (QQQ, AAPL)
# ══════════════════════════════════════════
print("PHASE 3: Cross-Asset Validation")
print("=" * 60)

assets = load_multi_assets(['SPY', 'QQQ', 'AAPL'], '1d', '15y')

for symbol in ['SPY', 'QQQ', 'AAPL']:
    d = assets[symbol].copy()
    d['_dt'] = pd.to_datetime(d['date'], utc=True)
    d['year'] = d['_dt'].dt.year

    # Full sample WF
    wf = yearly_wf(d, symbol)

    # 2026 holdout
    t_all = d[d['year'] < 2026].reset_index(drop=True)
    t_26 = d[d['year'] == 2026].reset_index(drop=True)
    if len(t_26) > 5:
        best = grid_search(t_all)
        s26, _, _, _, _ = bt_rs(t_26, best['f'], best['sl'], best['sm'])
    else:
        s26 = float('nan')

    bh_all = (float(d['close'].iloc[-1]) / float(d['close'].iloc[0]) - 1) * 100
    best_s = max(wf['oos'])
    worst_s = min(wf['oos'])

    star = "⭐" if wf['mean'] >= 1.0 else ""
    print(f"{star} {symbol:<6}  15yB&H={bh_all:+.0f}%  "
          f"WF mean={wf['mean']:.3f}  median={wf['median']:.3f}  "
          f"pos={wf['pos']}/{wf['total']}  "
          f"sm={wf['best_sm']}({wf['sm_stability']}/{wf['total']})  "
          f"2026 OOS={s26:.3f}")

# ══════════════════════════════════════════
# Summary
# ══════════════════════════════════════════
print()
print("=" * 60)
print("FINAL SUMMARY — METHODOLOGY LOCKED, NO MORE CHANGES")
print("=" * 60)
print(f"Strategy: {METHODOLOGY['strategy']}")
print(f"Grid: fast∈{METHODOLOGY['param_grid']['fast']} slow∈{METHODOLOGY['param_grid']['slow']} sm∈{METHODOLOGY['param_grid']['sell_min']}")

for symbol in ['SPY', 'QQQ', 'AAPL']:
    wf = yearly_wf(assets[symbol], symbol)
    print(f"\n  {symbol}:")
    print(f"    Yearly WF: {wf['mean']:.3f} ({wf['pos']}/{wf['total']} pos years)")
    print(f"    Best sm: {wf['best_sm']} (selected {wf['sm_stability']}/{wf['total']} years)")
    print(f"    Range: [{min(wf['oos']):.3f}, {max(wf['oos']):.3f}]")

print()
print("DISCLAIMER: These results are LOCKED IN. No further parameter tuning allowed.")
print("Next step: run ./run-live with these exact parameters.")
