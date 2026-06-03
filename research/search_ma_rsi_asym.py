"""
research/search_ma_rsi_asym.py — MA+RSI 非对称过滤搜索
只过滤买入端 或 只过滤卖出端
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd
import numpy as np
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
gain = delta.clip(lower=0)
loss = (-delta).clip(lower=0)
avg_gain = gain.ewm(alpha=1/14, adjust=False).mean()
avg_loss = loss.ewm(alpha=1/14, adjust=False).mean()
rs = avg_gain / avg_loss.replace(0, float('nan'))
rsi = 100.0 - (100.0 / (1.0 + rs))

# Custom backtest function that doesn't use generate_signals
def bench_with_signals(signals, label, df, p):
    cash = p.initial_cash
    shares = 0.0
    trades = 0
    for i in range(len(df)):
        row = df.iloc[i]
        close = float(row['close'])
        if i > 0:
            sig = int(signals.iloc[i-1])
            p_open = float(row['open'])
            if sig == 1 and shares <= 0:
                alloc = min(cash * p.order_size_pct, cash)
                if alloc >= p.min_trade_value:
                    fee = alloc * p.fee_rate
                    buy_s = (alloc - fee) / p_open
                    cash -= alloc
                    shares += buy_s
                    trades += 1
            elif sig == -1 and shares > 0:
                sell_v = shares * p_open
                fee = sell_v * p.fee_rate
                cash += sell_v - fee
                shares = 0.0
                trades += 1

    final = cash + shares * float(df['close'].iloc[-1])
    ret = (final / p.initial_cash - 1) * 100

    # Daily portfolio values for Sharpe calc
    daily_vals = []
    cash2 = p.initial_cash
    shares2 = 0.0
    for i in range(len(df)):
        row = df.iloc[i]
        c = float(row['close'])
        if i > 0:
            sig = int(signals.iloc[i-1])
            po = float(row['open'])
            if sig == 1 and shares2 <= 0:
                alloc = min(cash2 * p.order_size_pct, cash2)
                if alloc >= p.min_trade_value:
                    fee = alloc * p.fee_rate
                    cash2 -= alloc
                    shares2 += (alloc - fee) / po
            elif sig == -1 and shares2 > 0:
                sv = shares2 * po
                cash2 += sv - sv * p.fee_rate
                shares2 = 0.0
        daily_vals.append(cash2 + shares2 * c)

    import math
    rets = pd.Series(daily_vals).pct_change().dropna()
    sharpe = float((rets.mean() / rets.std()) * math.sqrt(252)) if len(rets) >= 5 and rets.std() > 0 else 0.0

    peak = pd.Series(daily_vals).cummax()
    dd = float(((pd.Series(daily_vals) - peak) / peak.replace(0, float('nan'))).min() * 100)

    return {'sharpe': sharpe, 'ret': ret, 'dd': dd, 'trades': trades}

print('=' * 75)
print('SPY MA+RSI 非对称过滤 (BUY only filter) vs (SELL only filter)')
print('=' * 75)

print('\n--- A: RSI 只过滤买入 (golden cross + RSI < T, death cross 不过滤) ---')
print(f"{'T':<8} {'Sharpe':>8} {'Ret%':>8} {'MaxDD%':>8} {'Trades':>8}")
print('-' * 45)
for t in [0, 30, 40, 50, 60, 70, 80]:
    sigs = pd.Series(0, index=df.index)
    sigs[gc & (rsi < t)] = 1
    sigs[dc] = -1
    r = bench_with_signals(sigs, f'buy<{t}', df, p)
    print(f"{t:<8} {r['sharpe']:>8.3f} {r['ret']:>+7.1f}% {r['dd']:>+7.1f}% {r['trades']:>8}")

print('\n--- B: RSI 只过滤卖出 (golden cross 不过滤, death cross + RSI > T) ---')
print(f"{'T':<8} {'Sharpe':>8} {'Ret%':>8} {'MaxDD%':>8} {'Trades':>8}")
print('-' * 45)
for t in [100, 90, 80, 70, 60, 50, 40, 30]:
    sigs = pd.Series(0, index=df.index)
    sigs[gc] = 1
    sigs[dc & (rsi > t)] = -1
    r = bench_with_signals(sigs, f'sell>{t}', df, p)
    print(f"{t:<8} {r['sharpe']:>8.3f} {r['ret']:>+7.1f}% {r['dd']:>+7.1f}% {r['trades']:>8}")

print('\n--- C: 无过滤 MA Cross 基准 ---')
# pure MA cross
sigs0 = pd.Series(0, index=df.index)
sigs0[gc] = 1
sigs0[dc] = -1
r0 = bench_with_signals(sigs0, 'MA Cross', df, p)
print(f"Sharpe={r0['sharpe']:.3f}  Ret={r0['ret']:+.1f}%  MaxDD={r0['dd']:+.1f}%  Trades={r0['trades']}")
print(f"SOTA 目标: Sharpe=1.337 (order_size=30%)")
