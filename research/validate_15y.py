"""research/validate_15y.py — SOTA v1.3.0 on 15-year data"""
import sys, math
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd
import numpy as np
from research.data_loader import load_data

df = load_data('SPY', '1d', '15y')
print(f"SPY 15y: {len(df)} days, {str(df['date'].iloc[0])[:10]} ~ {str(df['date'].iloc[-1])[:10]}")
print()

# ===== Baseline: MA Cross (5/15) =====
def run_bt(df, fast=5, slow=15, rsi_sell=None, use_atr=False, order_pct=0.30):
    fc = df['close'].rolling(fast, min_periods=1).mean()
    sc = df['close'].rolling(slow, min_periods=1).mean()
    gc = (fc > sc) & (fc.shift(1) <= sc.shift(1))
    dc = (fc < sc) & (fc.shift(1) >= sc.shift(1))

    if rsi_sell is not None:
        d = df['close'].diff()
        g = d.clip(lower=0).ewm(alpha=1/14, adjust=False).mean()
        l = (-d.clip(upper=0)).ewm(alpha=1/14, adjust=False).mean()
        rsi = 100.0 - (100.0/(1.0 + g/l.replace(0, float('nan'))))
        dc = dc & (rsi > rsi_sell)

    # ATR for position sizing
    atr_series = None; atr_med = None
    if use_atr:
        h = df['high']; l = df['low']; cp = df['close'].shift(1)
        tr = pd.concat([(h-l), (h-cp).abs(), (l-cp).abs()], axis=1).max(axis=1)
        atr_series = tr.ewm(alpha=1/14, adjust=False).mean()
        atr_med = atr_series.rolling(252, min_periods=63).median()

    cash = 10000.0; shares = 0.0; trades = 0; vals = []
    for i in range(len(df)):
        c = float(df['close'].iloc[i])
        if i > 0:
            gl = bool(gc.iloc[i-1]) if i-1 < len(gc) else False
            gs = bool(dc.iloc[i-1]) if i-1 < len(dc) else False
            po = float(df['open'].iloc[i])

            mult = 1.0
            if use_atr and atr_med is not None and i-1 < len(atr_med) and pd.notna(atr_med.iloc[i-1]):
                an = float(atr_series.iloc[i-1]); am = float(atr_med.iloc[i-1])
                if am > 0:
                    r = an/am
                    if r > 1.5: mult = 0.33
                    elif r < 0.8: mult = 2.0
            adj = order_pct * mult

            if gl and shares <= 0:
                alloc = min(cash * adj, cash)
                if alloc >= 100:
                    fee = alloc * 0.00001; shares = (alloc-fee)/po; cash -= alloc; trades += 1
            elif gs and shares > 0:
                sv = shares*po; cash += sv-sv*0.00001; shares=0.0; trades += 1
        vals.append(cash+shares*c)

    rets = pd.Series(vals).pct_change().dropna()
    s = float((rets.mean()/rets.std())*math.sqrt(252)) if len(rets)>=5 and rets.std()>0 else 0
    dd = float(((pd.Series(vals)-pd.Series(vals).cummax())/pd.Series(vals).cummax().replace(0,float('nan'))).min()*100)
    r = (vals[-1]/10000-1)*100
    bh = (float(df['close'].iloc[-1])/float(df['close'].iloc[0])-1)*100
    return s, r, dd, trades, bh

# 1. Pure MA Cross
s1, r1, d1, t1, bh1 = run_bt(df, rsi_sell=None, use_atr=False)
print("SPY 15y — 纯 MA Cross (5/15)")
print(f"  Sharpe={s1:.3f}  Ret={r1:+.1f}%  MaxDD={d1:+.1f}%  Trades={t1}  B&H={bh1:+.1f}%")
print()

# 2. MA + RSI Sell Filter (v1.2.0)
s2, r2, d2, t2, bh2 = run_bt(df, rsi_sell=40, use_atr=False)
print("SPY 15y — MA+RSI SellFilter (sell_min=40) — v1.2.0")
print(f"  Sharpe={s2:.3f}  Ret={r2:+.1f}%  MaxDD={d2:+.1f}%  Trades={t2}")
print(f"  vs Pure MA: Sharpe {s2-s1:+.3f}")
print()

# 3. MA + RSI + ATR (v1.3.0)
s3, r3, d3, t3, bh3 = run_bt(df, rsi_sell=40, use_atr=True)
print("SPY 15y — MA+RSI+ATR (v1.3.0)")
print(f"  Sharpe={s3:.3f}  Ret={r3:+.1f}%  MaxDD={d3:+.1f}%  Trades={t3}")
print(f"  vs Pure MA: Sharpe {s3-s1:+.3f}, MaxDD {d3-d1:+.1f}%")
print()

# 4. Parameter re-check on 15y
print("=" * 50)
print("Fast re-check: do 5y optimal params hold on 15y?")
print("=" * 50)

# MA params
print("\nMA Cross params (15y):")
best_ma = {'s': -99}
for fast in [3, 5, 10]:
    for slow in [15, 20, 30, 50]:
        s, _, _, t, _ = run_bt(df, fast=fast, slow=slow, rsi_sell=None)
        m = " <--" if s > best_ma['s'] else ""
        if s > best_ma['s']: best_ma = {'s':s, 'f':fast, 'sl':slow}
        print(f"  fast={fast} slow={slow}  Sharpe={s:.3f}  Trades={t}{m}")
print(f"  Best: fast={best_ma['f']} slow={best_ma['sl']} Sharpe={best_ma['s']:.3f}")

# RSI sell_min params (15y, with best MA)
print(f"\nRSI sell_min params (15y, MA {best_ma['f']}/{best_ma['sl']}):")
best_rsi = {'s': -99}
for sm in [0, 30, 35, 40, 45, 50, 55, 60]:
    if sm == 0: sm_use = None
    else: sm_use = sm
    s, _, _, t, _ = run_bt(df, fast=best_ma['f'], slow=best_ma['sl'], rsi_sell=sm_use)
    m = " <--" if s > best_rsi['s'] else ""
    if s > best_rsi['s']: best_rsi = {'s':s, 'sm':sm}
    print(f"  sell_min={sm}  Sharpe={s:.3f}  Trades={t}{m}")
print(f"  Best: sell_min={best_rsi['sm']} Sharpe={best_rsi['s']:.3f}")

# 5y vs 15y comparison
print()
print("=" * 50)
print("5y vs 15y Comparison")
print("=" * 50)
print(f"{'Version':<25} {'5y Sharpe':>10} {'15y Sharpe':>10}")
print(f"{'Pure MA Cross':<25} {1.337:>10.3f} {s1:>10.3f}")
print(f"{'v1.2.0 (RSI)':<25} {1.456:>10.3f} {s2:>10.3f}")
print(f"{'v1.3.0 (ATR)':<25} {1.626:>10.3f} {s3:>10.3f}")
print()
print(f"15y B&H: {bh3:+.1f}% vs 5y B&H: +93.6%")
