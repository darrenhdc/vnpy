"""
research/search_ma_rsi_sell.py — 卖出端 RSI 过滤精搜 + WF 验证
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd
import numpy as np
import math
from research.data_loader import load_data
from research.backtest import BacktestParams, _ensure_ma

df = load_data('SPY', '1d', '5y')
p = BacktestParams(order_size_pct=0.30)

fast, slow = 5, 15
fast_col = _ensure_ma(df, fast)
slow_col = _ensure_ma(df, slow)
gc = (df[fast_col] > df[slow_col]) & (df[fast_col].shift(1) <= df[slow_col].shift(1))
dc = (df[fast_col] < df[slow_col]) & (df[fast_col].shift(1) >= df[slow_col].shift(1))

delta = df['close'].diff()
avg_gain = delta.clip(lower=0).ewm(alpha=1/14, adjust=False).mean()
avg_loss = (-delta.clip(upper=0)).ewm(alpha=1/14, adjust=False).mean()
rs_val = avg_gain / avg_loss.replace(0, float('nan'))
rsi = 100.0 - (100.0 / (1.0 + rs_val))

def backtest_with_signals(signals, df, p):
    cash = p.initial_cash
    shares = 0.0
    trades = 0
    daily_vals = []
    for i in range(len(df)):
        row = df.iloc[i]
        c = float(row['close'])
        if i > 0:
            sig = int(signals.iloc[i-1])
            po = float(row['open'])
            if sig == 1 and shares <= 0:
                alloc = min(cash * p.order_size_pct, cash)
                if alloc >= p.min_trade_value:
                    fee = alloc * p.fee_rate
                    cash -= alloc
                    shares += (alloc - fee) / po
                    trades += 1
            elif sig == -1 and shares > 0:
                sv = shares * po
                cash += sv - sv * p.fee_rate
                shares = 0.0
                trades += 1
        daily_vals.append(cash + shares * c)
    rets = pd.Series(daily_vals).pct_change().dropna()
    sharpe = float((rets.mean() / rets.std()) * math.sqrt(252)) if len(rets) >= 5 and rets.std() > 0 else 0.0
    peak = pd.Series(daily_vals).cummax()
    dd = float(((pd.Series(daily_vals) - peak) / peak.replace(0, float('nan'))).min() * 100)
    final = daily_vals[-1]
    ret = (final / p.initial_cash - 1) * 100
    return {'sharpe': sharpe, 'ret': ret, 'dd': dd, 'trades': trades}

print('=' * 65)
print('MA+RSI 卖出端过滤精搜 (T=30~55, step=2)')
print('=' * 65)
print(f"{'T':<8} {'Sharpe':>8} {'Ret%':>8} {'MaxDD%':>8} {'Trades':>8}")
print('-' * 45)
best = {'sharpe': -99}
for t in range(30, 56, 2):
    sigs = pd.Series(0, index=df.index)
    sigs[gc] = 1
    sigs[dc & (rsi > t)] = -1
    r = backtest_with_signals(sigs, df, p)
    marker = ' <--' if r['sharpe'] > best['sharpe'] else ''
    print(f"{t:<8} {r['sharpe']:>8.3f} {r['ret']:>+7.1f}% {r['dd']:>+7.1f}% {r['trades']:>8}{marker}")
    if r['sharpe'] > best['sharpe']:
        best = r.copy()
        best['t'] = t

print()
print(f"Best: sell_min={best['t']}  Sharpe={best['sharpe']:.3f}  Ret={best['ret']:+.1f}%  MaxDD={best['dd']:+.1f}%  Trades={best['trades']}")
sota_s = 1.337
print(f"vs SOTA (Sharpe {sota_s}): Delta = {best['sharpe'] - sota_s:+.3f} ({(best['sharpe'] / sota_s - 1) * 100:+.1f}%)")

# Walk-Forward test
print()
print('=' * 65)
print('Walk-Forward: 18m train / 3m test / 3m step / 12m holdout')
print('=' * 65)
print(f"sell_min={best['t']}")

df['_dt'] = pd.to_datetime(df['date'], utc=True)
t0 = df['_dt'].iloc[0]
cutoff = df['_dt'].iloc[-1] - pd.DateOffset(months=12)

train_mask = df['_dt'] < cutoff
test_mask = df['_dt'] >= cutoff

# Full period (train)
sigs_full = pd.Series(0, index=df.index)
sigs_full[gc] = 1
sigs_full[dc & (rsi > best['t'])] = -1
r_full = backtest_with_signals(sigs_full, df, p)

# Holdout only
df_hold = df[test_mask].reset_index(drop=True)
# Recalculate signals on holdout subset
_fast = df_hold['close'].rolling(fast, min_periods=1).mean()
_slow = df_hold['close'].rolling(slow, min_periods=1).mean()
_gc = (_fast > _slow) & (_fast.shift(1) <= _slow.shift(1))
_dc = (_fast < _slow) & (_fast.shift(1) >= _slow.shift(1))
delta2 = df_hold['close'].diff()
avg_gain2 = delta2.clip(lower=0).ewm(alpha=1/14, adjust=False).mean()
avg_loss2 = (-delta2.clip(upper=0)).ewm(alpha=1/14, adjust=False).mean()
rs2 = avg_gain2 / avg_loss2.replace(0, float('nan'))
rsi2 = 100.0 - (100.0 / (1.0 + rs2))
sigs_hold = pd.Series(0, index=df_hold.index)
sigs_hold[_gc] = 1
sigs_hold[_dc & (rsi2 > best['t'])] = -1
r_hold = backtest_with_signals(sigs_hold, df_hold, p)

print(f"{'':<25} {'Full Period':>18} {'WF Holdout':>18}")
print(f"{'Sharpe':<25} {r_full['sharpe']:>18.3f} {r_hold['sharpe']:>18.3f}")
print(f"{'Return %':<25} {r_full['ret']:>+17.1f}% {r_hold['ret']:>+17.1f}%")
print(f"{'MaxDD %':<25} {r_full['dd']:>+17.1f}% {r_hold['dd']:>+17.1f}%")
print(f"{'Trades':<25} {r_full['trades']:>18} {r_hold['trades']:>18}")
if r_hold['sharpe'] > 0:
    print(f"WF/SOTA ratio: {r_hold['sharpe'] / sota_s:.2f}x SOTA Sharpe")
