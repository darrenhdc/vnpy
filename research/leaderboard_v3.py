"""research/leaderboard_v3.py — SOTA 打榜 v3: Train/Test Split, No Peeking"""
import sys, math
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd, numpy as np
from research.data_loader import load_data

df = load_data('SPY', '1d', '15y')
df['_dt'] = pd.to_datetime(df['date'], utc=True)
mid = df['_dt'].iloc[0] + pd.DateOffset(years=10)
train = df[df['_dt'] < mid].reset_index(drop=True)
test  = df[df['_dt'] >= mid].reset_index(drop=True)
print(f"Train: 2011-2021 ({len(train)}d)  |  Test: 2021-2026 ({len(test)}d)")
SOTA = 0.597  # Current SOTA OOS Sharpe

def bt_fixed(d, fast=10, slow=15, trend_ma=None, atr_stop=None, order_pct=0.3):
    """Backtest with optional filters. All params fixed, no search."""
    fc = d['close'].rolling(fast, min_periods=1).mean()
    sc = d['close'].rolling(slow, min_periods=1).mean()
    gc = (fc > sc) & (fc.shift(1) <= sc.shift(1))
    dc = (fc < sc) & (fc.shift(1) >= sc.shift(1))

    # ATR for trailing stop
    atr = None; trail_high = None
    if atr_stop is not None:
        h = d['high']; l = d['low']; cp = d['close'].shift(1)
        tr = pd.concat([(h-l), (h-cp).abs(), (l-cp).abs()], axis=1).max(axis=1)
        atr = tr.ewm(alpha=1/14, adjust=False).mean()

    # SMA for trend filter
    sma = None
    if trend_ma is not None:
        sma = d['close'].rolling(trend_ma, min_periods=1).mean()

    cash = 10000.0; shares = 0.0; trades = 0; vals = []
    trail_high = 0.0

    for i in range(len(d)):
        c = float(d['close'].iloc[i])
        if i > 0:
            gl = bool(gc.iloc[i-1]) if i-1 < len(gc) else False
            gs = bool(dc.iloc[i-1]) if i-1 < len(dc) else False
            po = float(d['open'].iloc[i])

            # Trend filter: only allow long if price > SMA
            if trend_ma is not None and sma is not None:
                if i-1 < len(sma) and pd.notna(sma.iloc[i-1]):
                    if float(d['close'].iloc[i-1]) < sma.iloc[i-1]:
                        gl = False  # No buy below SMA

            # Entry
            if gl and shares <= 0:
                alloc = min(cash * order_pct, cash)
                if alloc >= 100:
                    fee = alloc * 0.00001
                    shares = (alloc - fee) / po
                    cash -= alloc
                    trades += 1
                    trail_high = c

            # Exit conditions
            sell = False
            if shares > 0:
                trail_high = max(trail_high, c)
                # MA death cross exit
                if gs:
                    sell = True
                # ATR trailing stop exit
                elif atr_stop is not None and atr is not None:
                    if i-1 < len(atr) and pd.notna(atr.iloc[i-1]):
                        stop_price = trail_high - atr_stop * float(atr.iloc[i-1])
                        if c < stop_price:
                            sell = True

            if sell:
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

def train_search(d, search_fn, *args):
    """Search on train data only, return best params"""
    best = {'s': -99}
    for params in search_fn(*args):
        s, _, _, _ = bt_fixed(d, **params)
        if s > best['s']:
            best = {'s': s, 'params': params}
    return best

# ========================
# #1: SMA Trend Filter
# ========================
print("=" * 60)
print("#1: SMA Trend Filter — only trade above SMA(X)")
print("=" * 60)
def sma_search():
    for ma in [50, 100, 200]:
        for f in [5, 10]:
            for s in [15, 20]:
                yield {'fast': f, 'slow': s, 'trend_ma': ma}

best1 = train_search(train, sma_search)
s1, r1, d1, t1 = bt_fixed(test, **best1['params'])
print(f"Train best: {best1['params']}  Train Sharpe={best1['s']:.3f}")
print(f"Test OOS:   Sharpe={s1:.3f}  Ret={r1:+.1f}%  MaxDD={d1:+.1f}%  Trades={t1}")
print(f"vs SOTA ({SOTA}): {'ABOVE' if s1 > SOTA else 'BELOW'}")

# ========================
# #2: ATR Trailing Stop
# ========================
print()
print("=" * 60)
print("#2: ATR Trailing Stop — exit on trail_high - N*ATR")
print("=" * 60)
def atr_search():
    for f in [5, 10]:
        for sl in [15, 20]:
            for n in [2.0, 3.0, 4.0]:
                yield {'fast': f, 'slow': sl, 'atr_stop': n}

best2 = train_search(train, atr_search)
s2, r2, d2, t2 = bt_fixed(test, **best2['params'])
print(f"Train best: {best2['params']}  Train Sharpe={best2['s']:.3f}")
print(f"Test OOS:   Sharpe={s2:.3f}  Ret={r2:+.1f}%  MaxDD={d2:+.1f}%  Trades={t2}")
print(f"vs SOTA ({SOTA}): {'ABOVE' if s2 > SOTA else 'BELOW'}")

# ========================
# #3: SMA + ATR Combo
# ========================
print()
print("=" * 60)
print("#3: SMA Trend Filter + ATR Trailing Stop")
print("=" * 60)
def combo_search():
    for ma in [100, 200]:
        for f in [5, 10]:
            for sl in [15, 20]:
                for n in [2.0, 3.0]:
                    yield {'fast': f, 'slow': sl, 'trend_ma': ma, 'atr_stop': n}

best3 = train_search(train, combo_search)
s3, r3, d3, t3 = bt_fixed(test, **best3['params'])
print(f"Train best: {best3['params']}  Train Sharpe={best3['s']:.3f}")
print(f"Test OOS:   Sharpe={s3:.3f}  Ret={r3:+.1f}%  MaxDD={d3:+.1f}%  Trades={t3}")
print(f"vs SOTA ({SOTA}): {'ABOVE' if s3 > SOTA else 'BELOW'}")

# ========================
# Summary
# ========================
print()
print("=" * 60)
print("LEADERBOARD (OOS Sharpe, no peeking)")
print("=" * 60)
results = [
    ("SOTA v2.1.0 (MA Cross 10/15)", SOTA),
    ("#1 SMA Trend Filter", s1),
    ("#2 ATR Trailing Stop", s2),
    ("#3 SMA + ATR Combo", s3),
]
for name, sharpe in sorted(results, key=lambda x: -x[1]):
    flag = "⭐ SOTA" if name.startswith("SOTA") else ("✅ BEATS" if sharpe > SOTA else "❌")
    print(f"  {sharpe:.3f}  {flag}  {name}")
