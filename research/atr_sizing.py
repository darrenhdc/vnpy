"""research/atr_sizing.py — ATR 仓位管理研究"""
import sys, math
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd
import numpy as np
from research.data_loader import load_data

df = load_data('SPY', '1d', '5y')

# ===== Baseline: SOTA MA+RSI Sell Filter (no ATR) =====
def calc_ma_rsi_signals(df, fast=5, slow=15, sell_min=40):
    fc = df['close'].rolling(fast, min_periods=1).mean()
    sc = df['close'].rolling(slow, min_periods=1).mean()
    gc = (fc > sc) & (fc.shift(1) <= sc.shift(1))
    dc = (fc < sc) & (fc.shift(1) >= sc.shift(1))
    d = df['close'].diff()
    g = d.clip(lower=0).ewm(alpha=1/14, adjust=False).mean()
    l = (-d.clip(upper=0)).ewm(alpha=1/14, adjust=False).mean()
    rsi = 100.0 - (100.0/(1.0 + g/l.replace(0, float('nan'))))
    sigs = pd.Series(0, index=df.index)
    sigs[gc] = 1
    sigs[dc & (rsi > sell_min)] = -1
    return sigs, rsi

def run_atr_bt(df, signals, atr_mult=None, atr_lb=14, min_mult=0.3, max_mult=2.0):
    """
    atr_mult = None: no ATR sizing (baseline)
    atr_mult = 'pct': inverse ATR scaling (position ~ 1/ATR)
    atr_mult = 'binary': threshold-based scaling
    """
    cash = 10000.0; shares = 0.0; trades = 0; vals = []
    base_pct = 0.30

    if atr_mult is not None:
        # Compute ATR
        h = df['high']; l = df['low']; c_prev = df['close'].shift(1)
        tr = pd.concat([(h-l), (h-c_prev).abs(), (l-c_prev).abs()], axis=1).max(axis=1)
        atr = tr.ewm(alpha=1/atr_lb, adjust=False).mean()
        atr_median = atr.rolling(252, min_periods=63).median()

    for i in range(len(df)):
        c = float(df['close'].iloc[i])
        if i > 0:
            sig = int(signals.iloc[i-1]) if i-1 < len(signals) else 0
            po = float(df['open'].iloc[i])

            # Determine position multiplier
            mult = 1.0
            if atr_mult is not None and i-1 >= 0:
                atr_now = float(atr.iloc[i-1])
                atr_med = float(atr_median.iloc[i-1]) if i-1 < len(atr_median) and pd.notna(atr_median.iloc[i-1]) else atr_now

                if atr_mult == 'pct':
                    mult = atr_med / atr_now if atr_now > 0 else 1.0
                    mult = np.clip(mult, min_mult, max_mult)
                elif atr_mult == 'binary':
                    ratio = atr_now / atr_med if atr_med > 0 else 1.0
                    if ratio > 1.5:     # high vol: reduce
                        mult = min_mult
                    elif ratio < 0.67:  # low vol: increase
                        mult = max_mult

            adj_pct = base_pct * mult

            if sig == 1 and shares <= 0:
                alloc = min(cash * adj_pct, cash)
                if alloc >= 100:
                    fee = alloc * 0.00001
                    shares = (alloc - fee) / po
                    cash -= alloc
                    trades += 1
            elif sig == -1 and shares > 0:
                sv = shares * po
                cash += sv - sv * 0.00001
                shares = 0.0
                trades += 1

        vals.append(cash + shares * c)

    rets = pd.Series(vals).pct_change().dropna()
    s = float((rets.mean()/rets.std())*math.sqrt(252)) if len(rets)>=5 and rets.std()>0 else 0
    dd = float(((pd.Series(vals)-pd.Series(vals).cummax())/pd.Series(vals).cummax().replace(0,float('nan'))).min()*100)
    r = (vals[-1]/10000-1)*100
    return s, r, dd, trades

sig_sota, rsi = calc_ma_rsi_signals(df)

# Baseline (SOTA, no ATR)
b_s, b_r, b_dd, b_t = run_atr_bt(df, sig_sota)
print('=' * 60)
print(f'Baseline (SOTA v1.2.0, no ATR)')
print(f'  Sharpe={b_s:.3f}  Ret={b_r:+.1f}%  MaxDD={b_dd:+.1f}%  Trades={b_t}')

# ===== Experiment 1: Inverse ATR scaling =====
print()
print('=' * 60)
print('ATR Sizing: Inverse Scaling (position ~ median_ATR / current_ATR)')
print('=' * 60)
print(f"{'ATR_LB':<8} {'MinM':<8} {'MaxM':<8} {'Sharpe':>8} {'Ret%':>9} {'MaxDD%':>8} {'Trades':>7}")
print('-' * 55)
best = {'s': -99}
for lb in [14, 20, 30]:
    for min_m in [0.25, 0.33, 0.5]:
        for max_m in [1.5, 2.0, 3.0]:
            s, r, dd, t = run_atr_bt(df, sig_sota, atr_mult='pct', atr_lb=lb, min_mult=min_m, max_mult=max_m)
            m = " <--" if s > best['s'] else ""
            if s > best['s']: best = {'s':s,'r':r,'dd':dd,'t':t,'lb':lb,'min':min_m,'max':max_m}
            print(f"{lb:<8} {min_m:<8.2f} {max_m:<8.2f} {s:>8.3f} {r:>+8.1f}% {dd:>+7.1f}% {t:>7}{m}")

ds = best['s'] - b_s
print(f"\nBest Pct: lb={best['lb']} min={best['min']} max={best['max']}")
print(f"  Sharpe={best['s']:.3f}  Ret={best['r']:+.1f}%  MaxDD={best['dd']:+.1f}%  Trades={best['t']}")
print(f"  vs Baseline: Delta Sharpe={ds:+.3f}")

# ===== Experiment 2: Binary ATR threshold =====
print()
print('=' * 60)
print('ATR Sizing: Binary Threshold (high/low vol only)')
print('=' * 60)
print(f"{'ATR_LB':<8} {'HiThr':<8} {'LowThr':<8} {'MaxM':<8} {'Sharpe':>8} {'Ret%':>9} {'MaxDD%':>8} {'Trades':>7}")
print('-' * 61)

for lb in [14, 20]:
    for hi in [1.3, 1.5, 2.0]:
        for lo in [0.5, 0.67, 0.8]:
            for max_m in [1.5, 2.0, 2.5]:
                # Custom binary logic
                cash = 10000.0; shares = 0.0; trades = 0; vals = []
                base_pct = 0.30
                h = df['high']; l = df['low']; cp = df['close'].shift(1)
                tr = pd.concat([(h-l), (h-cp).abs(), (l-cp).abs()], axis=1).max(axis=1)
                atr = tr.ewm(alpha=1/lb, adjust=False).mean()
                atr_med = atr.rolling(252, min_periods=63).median()

                for i in range(len(df)):
                    c = float(df['close'].iloc[i])
                    if i > 0:
                        sig = int(sig_sota.iloc[i-1]) if i-1 < len(sig_sota) else 0
                        po = float(df['open'].iloc[i])
                        mult = 1.0
                        if i-1 < len(atr_med) and pd.notna(atr_med.iloc[i-1]):
                            an = float(atr.iloc[i-1]); am = float(atr_med.iloc[i-1])
                            if am > 0:
                                ratio = an/am
                                if ratio > hi: mult = 0.33
                                elif ratio < lo: mult = max_m
                        adj = base_pct * mult
                        if sig == 1 and shares <= 0:
                            alloc = min(cash * adj, cash)
                            if alloc >= 100:
                                fee = alloc * 0.00001; shares = (alloc-fee)/po; cash -= alloc; trades += 1
                        elif sig == -1 and shares > 0:
                            sv = shares*po; cash += sv-sv*0.00001; shares=0.0; trades += 1
                    vals.append(cash+shares*c)

                rets = pd.Series(vals).pct_change().dropna()
                s = float((rets.mean()/rets.std())*math.sqrt(252)) if len(rets)>=5 and rets.std()>0 else 0
                dd = float(((pd.Series(vals)-pd.Series(vals).cummax())/pd.Series(vals).cummax().replace(0,float('nan'))).min()*100)
                r = (vals[-1]/10000-1)*100
                m2 = ""
                if s > best['s']:
                    best = {'s':s,'r':r,'dd':dd,'t':trades,'lb':lb,'hi':hi,'lo':lo,'max':max_m}
                    m2 = " <--"
                print(f"{lb:<8} {hi:<8.2f} {lo:<8.2f} {max_m:<8.2f} {s:>8.3f} {r:>+8.1f}% {dd:>+7.1f}% {trades:>7}{m2}")

print(f"\nBest Binary: lb={best['lb']} hi={best['hi']} lo={best.get('lo','')} max={best.get('max','')}")
print(f"  Sharpe={best['s']:.3f}  Ret={best['r']:+.1f}%  MaxDD={best['dd']:+.1f}%  Trades={best['t']}")
print(f"  vs Baseline (Sharpe {b_s:.3f}): Delta={best['s']-b_s:+.3f}")
