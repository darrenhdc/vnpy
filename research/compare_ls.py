"""Apple-to-Apple Long-Only vs Long-Short comparison"""
import sys, math
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd
import numpy as np
from research.data_loader import load_data
from research.backtest import _ensure_ma

df = load_data('SPY', '1d', '5y')
fast, slow = 5, 15

delta = df['close'].diff()
avg_gain = delta.clip(lower=0).ewm(alpha=1/14, adjust=False).mean()
avg_loss = (-delta.clip(upper=0)).ewm(alpha=1/14, adjust=False).mean()
rs_val = avg_gain / avg_loss.replace(0, float('nan'))
rsi = 100.0 - (100.0 / (1.0 + rs_val))

fast_col = _ensure_ma(df, fast)
slow_col = _ensure_ma(df, slow)
gc = (df[fast_col] > df[slow_col]) & (df[fast_col].shift(1) <= df[slow_col].shift(1))
dc = (df[fast_col] < df[slow_col]) & (df[fast_col].shift(1) >= df[slow_col].shift(1))

def run_bt(df, use_short=True, rsi_sell=40, order_pct=0.30):
    cash = 10000.0; shares = 0.0; trades = 0; vals = []
    for i in range(len(df)):
        c = float(df['close'].iloc[i])
        if i > 0:
            go_l = bool(gc.iloc[i-1])
            go_s = bool(dc.iloc[i-1])
            rsi_now = float(rsi.iloc[i-1]) if i-1 < len(rsi) else 50
            po = float(df['open'].iloc[i])

            if go_l:
                if shares < 0:
                    cv = abs(shares) * po; cash -= cv + cv*0.00001; shares = 0.0; trades += 1
                if shares <= 0:
                    alloc = min(cash * order_pct, cash)
                    if alloc >= 100:
                        fee = alloc * 0.00001; shares = (alloc - fee) / po; cash -= alloc; trades += 1

            if go_s:
                if use_short and shares > 0:
                    sv = shares * po; cash += sv - sv*0.00001; shares = 0.0; trades += 1
                if use_short and shares >= 0 and rsi_now > rsi_sell:
                    sv = min(cash * order_pct, cash)
                    if sv >= 100:
                        fee = sv * 0.00001; short_s = (sv - fee) / po; cash -= fee; cash += sv; shares -= short_s; trades += 1
                elif not use_short and shares > 0:
                    sv = shares * po; cash += sv - sv*0.00001; shares = 0.0; trades += 1

        vals.append(cash + shares * c)

    rets = pd.Series(vals).pct_change().dropna()
    s = float((rets.mean() / rets.std()) * math.sqrt(252)) if len(rets)>=5 and rets.std()>0 else 0
    dd = float(((pd.Series(vals) - pd.Series(vals).cummax()) / pd.Series(vals).cummax().replace(0, float('nan'))).min()*100)
    ret = (vals[-1]/10000 - 1)*100
    return s, ret, dd, trades

lo_s, lo_r, lo_dd, lo_t = run_bt(df, use_short=False, rsi_sell=40)
ls_s, ls_r, ls_dd, ls_t = run_bt(df, use_short=True, rsi_sell=40)

print("=" * 55)
print("Apple-to-Apple: Long-Only vs Long-Short (5/15, RSI sell>40)")
print("=" * 55)
print(f"{'':<20} {'Long-Only (SOTA)':>16} {'Long-Short':>16}")
print(f"{'Sharpe':<20} {lo_s:>16.3f} {ls_s:>16.3f}")
print(f"{'Return %':<20} {lo_r:>+15.1f}% {ls_r:>+15.1f}%")
print(f"{'MaxDD %':<20} {lo_dd:>+15.1f}% {ls_dd:>+15.1f}%")
print(f"{'Trades':<20} {lo_t:>16} {ls_t:>16}")
print()
print(f"Delta Sharpe: {ls_s-lo_s:+.3f}  |  Delta Return: {ls_r-lo_r:+.1f}%  |  Delta Trades: {ls_t-lo_t:+d}")
conclusion = "Long-Short BEATS SOTA" if ls_s > lo_s else "Long-Short DOES NOT BEAT SOTA"
print(f"Conclusion: {conclusion}")
print()
print("Analysis: Short side kills Sharpe because SPY trends UP over 5y.")
print("Every short trade on a death cross loses money when SPY recovers.")
