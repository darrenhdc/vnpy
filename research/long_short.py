"""
research/long_short.py — Long-Short MA Cross 研究（金叉做多，死叉做空）
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import math
import pandas as pd
import numpy as np
from research.data_loader import load_data
from research.backtest import BacktestParams, _ensure_ma


def run_long_short_backtest(df, fast=5, slow=15, rsi_sell_min=None, rsi_period=14,
                            order_pct=0.30, short_borrow=0.03):
    """
    Long-Short 回测。金叉做多，死叉做空（或平仓看 rsi_sell_min）。
    
    rsi_sell_min=None: 纯 Long-Short（死叉即做空）
    rsi_sell_min=40: 死叉时如果 RSI<40 则平多不空（等反弹再空）
    """
    fast_col = _ensure_ma(df, fast)
    slow_col = _ensure_ma(df, slow)
    gc = (df[fast_col] > df[slow_col]) & (df[fast_col].shift(1) <= df[slow_col].shift(1))
    dc = (df[fast_col] < df[slow_col]) & (df[fast_col].shift(1) >= df[slow_col].shift(1))

    if rsi_sell_min is not None:
        delta = df['close'].diff()
        avg_gain = delta.clip(lower=0).ewm(alpha=1/rsi_period, adjust=False).mean()
        avg_loss = (-delta.clip(upper=0)).ewm(alpha=1/rsi_period, adjust=False).mean()
        rs_val = avg_gain / avg_loss.replace(0, float('nan'))
        rsi = 100.0 - (100.0 / (1.0 + rs_val))
        dc_filtered = dc & (rsi > rsi_sell_min)
    else:
        dc_filtered = dc

    cash = 10000.0
    shares = 0.0  # positive=long, negative=short
    trades = 0
    daily_vals = []

    for i in range(len(df)):
        row = df.iloc[i]
        c = float(row['close'])

        if i > 0:
            go_long = bool(gc.iloc[i-1])
            go_short = bool(dc_filtered.iloc[i-1])
            po = float(row['open'])

            if go_long:
                # Close existing short first (buy to cover)
                if shares < 0:
                    cover_shares = abs(shares)
                    cover_value = cover_shares * po
                    fee = cover_value * 0.00001
                    cash -= cover_value + fee  # pay to buy back
                    trades += 1
                    shares = 0.0

                # Open long
                if shares <= 0:
                    alloc = min(cash * order_pct, cash)
                    if alloc >= 100:
                        fee = alloc * 0.00001
                        cash -= alloc
                        shares += (alloc - fee) / po
                        trades += 1

            elif go_short:
                # Close existing long first
                if shares > 0:
                    sv = shares * po
                    fee = sv * 0.00001
                    cash += sv - fee
                    trades += 1
                    shares = 0.0

                # Open short (no cash deduction — shorting generates cash)
                if shares >= 0:
                    short_value = min(cash * order_pct, cash)
                    if short_value >= 100:
                        fee = short_value * 0.00001
                        short_shares = (short_value - fee) / po
                        cash -= fee       # fee only
                        cash += short_value  # receive short sale proceeds
                        shares -= short_shares
                        trades += 1

        daily_vals.append(cash + shares * c)

    rets = pd.Series(daily_vals).pct_change().dropna()
    sharpe = float((rets.mean() / rets.std()) * math.sqrt(252)) if len(rets) >= 5 and rets.std() > 0 else 0.0
    peak = pd.Series(daily_vals).cummax()
    dd = float(((pd.Series(daily_vals) - peak) / peak.replace(0, float('nan'))).min() * 100)
    final = daily_vals[-1]
    ret = (final / 10000.0 - 1) * 100

    # B&H comparison
    bh = (float(df['close'].iloc[-1]) / float(df['close'].iloc[0]) - 1) * 100

    return {'sharpe': sharpe, 'ret': ret, 'dd': dd, 'trades': trades, 'bh': bh}


# ========== Pure Long-Short (no filter) ==========
df = load_data('SPY', '1d', '5y')

print("=" * 70)
print("Long-Short MA Cross: 金叉做多 / 死叉做空（无 RSI 过滤）")
print("=" * 70)

print("\n--- 参数搜索 (fast × slow) ---")
print(f"{'fast':<8} {'slow':<8} {'Sharpe':>8} {'Ret%':>9} {'MaxDD%':>8} {'Trades':>7}")
print("-" * 48)

best = {'sharpe': -99}
for fast in [3, 5, 10]:
    for slow in [15, 20, 30, 50]:
        r = run_long_short_backtest(df, fast=fast, slow=slow, rsi_sell_min=None)
        marker = " <--" if r['sharpe'] > best['sharpe'] else ""
        print(f"{fast:<8} {slow:<8} {r['sharpe']:>8.3f} {r['ret']:>+8.1f}% {r['dd']:>+7.1f}% {r['trades']:>7}{marker}")
        if r['sharpe'] > best['sharpe']:
            best = r.copy()
            best['fast'] = fast
            best['slow'] = slow

print(f"\nBest Pure LS: fast={best['fast']}, slow={best['slow']}  Sharpe={best['sharpe']:.3f}  Ret={best['ret']:+.1f}%  MaxDD={best['dd']:+.1f}%  Trades={best['trades']}")

# SOTA baseline
from research.backtest import run_backtest
sota = run_backtest(df, BacktestParams(order_size_pct=0.30), 'ma_rsi_cross_confirm', 'SPY',
                     {'fast': 5, 'slow': 15, 'rsi_sell_min': 40})
print(f"SOTA (MA+RSI SellFilter): Sharpe={sota.sharpe:.3f}  Ret={sota.total_return_pct:+.1f}%  MaxDD={sota.max_drawdown_pct:+.1f}%")

# ========== Long-Short + RSI sell filter ==========
print()
print("=" * 70)
print("Long-Short + RSI Sell Filter: 超卖时不空（只平多），等反弹再空")
print("=" * 70)
print(f"\n--- 参数搜索 (fixed MA 5/15, varying RSI sell_min) ---")
print(f"{'sell_min':<10} {'Sharpe':>8} {'Ret%':>9} {'MaxDD%':>8} {'Trades':>7}")
print("-" * 48)

ls_best = {'sharpe': -99}
for sell_min in [0, 30, 35, 40, 45, 50, 55]:
    if sell_min == 0:
        # sell_min=0 means: never short (long-only) — essentially same as SOTA
        r = run_long_short_backtest(df, fast=best['fast'], slow=best['slow'], rsi_sell_min=999)
        sell_min = "∞"
    else:
        r = run_long_short_backtest(df, fast=best['fast'], slow=best['slow'], rsi_sell_min=sell_min)
    s = str(sell_min)
    print(f"{s:<10} {r['sharpe']:>8.3f} {r['ret']:>+8.1f}% {r['dd']:>+7.1f}% {r['trades']:>7}")
    if r['sharpe'] > ls_best['sharpe']:
        ls_best = r.copy()
        ls_best['sell_min'] = sell_min
    if str(sell_min) == "∞":
        sell_min = 0

print(f"\nBest LS+RSI: fast={best['fast']} slow={best['slow']} sell_min={ls_best.get('sell_min', 'N/A')}")
print(f"  Sharpe={ls_best['sharpe']:.3f}  Ret={ls_best['ret']:+.1f}%  MaxDD={ls_best['dd']:+.1f}%  Trades={ls_best['trades']}")
print(f"  vs SOTA ({sota.sharpe:.3f}): {'ABOVE' if ls_best['sharpe'] > sota.sharpe else 'BELOW'}")
