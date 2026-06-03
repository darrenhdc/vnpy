"""research/macd_rsi.py — MACD + RSI 双确认研究"""
import sys, math
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd
import numpy as np
from research.data_loader import load_data
from research.backtest import BacktestParams

df = load_data('SPY', '1d', '5y')
p = BacktestParams(order_size_pct=0.30)

def run_bt(df, signals):
    cash = p.initial_cash; shares = 0.0; trades = 0; vals = []
    for i in range(len(df)):
        c = float(df['close'].iloc[i])
        if i > 0:
            sig = int(signals.iloc[i-1]) if i-1 < len(signals) else 0
            po = float(df['open'].iloc[i])
            if sig == 1 and shares <= 0:
                a = min(cash*p.order_size_pct, cash)
                if a>=100: fee=a*p.fee_rate; shares=(a-fee)/po; cash-=a; trades+=1
            elif sig == -1 and shares > 0:
                sv=shares*po; cash+=sv-sv*p.fee_rate; shares=0.0; trades+=1
        vals.append(cash+shares*c)
    rets = pd.Series(vals).pct_change().dropna()
    s = float((rets.mean()/rets.std())*math.sqrt(252)) if len(rets)>=5 else 0
    dd = float(((pd.Series(vals)-pd.Series(vals).cummax())/pd.Series(vals).cummax().replace(0,float('nan'))).min()*100)
    r = (vals[-1]/p.initial_cash-1)*100
    return s, r, dd, trades

# MACD computation
def calc_macd(df, f=12, s=26, sig=9):
    ef = df['close'].ewm(span=f, adjust=False).mean()
    es = df['close'].ewm(span=s, adjust=False).mean()
    macd = ef - es
    signal = macd.ewm(span=sig, adjust=False).mean()
    hist = macd - signal
    return macd, signal, hist

# RSI computation
def calc_rsi(df, period=14):
    d = df['close'].diff()
    g = d.clip(lower=0).ewm(alpha=1/period, adjust=False).mean()
    l = (-d.clip(upper=0)).ewm(alpha=1/period, adjust=False).mean()
    return 100.0 - (100.0/(1.0 + g/l.replace(0, float('nan'))))

rsi = calc_rsi(df, 14)

# ============ Experiment 1: Pure MACD Cross ============
print("=" * 70)
print("Experiment 1: Pure MACD Cross — 参数搜索")
print("=" * 70)
print(f"{'fast':<8} {'slow':<8} {'sig':<8} {'Sharpe':>8} {'Ret%':>9} {'MaxDD%':>8} {'Trades':>7}")
print("-" * 55)

best_macd = {'s': -99}
for f in [8, 12, 16]:
    for sl in [21, 26, 30]:
        for sg in [7, 9, 12]:
            macd, sig_line, _ = calc_macd(df, f, sl, sg)
            cross_up = (macd > sig_line) & (macd.shift(1) <= sig_line.shift(1))
            cross_down = (macd < sig_line) & (macd.shift(1) >= sig_line.shift(1))
            sigs = pd.Series(0, index=df.index)
            sigs[cross_up] = 1
            sigs[cross_down] = -1
            s, r, dd, tr = run_bt(df, sigs)
            m = " <--" if s > best_macd['s'] else ""
            if s > best_macd['s']: best_macd = {'s': s, 'r': r, 'dd': dd, 't': tr, 'f': f, 'sl': sl, 'sg': sg}
            print(f"{f:<8} {sl:<8} {sg:<8} {s:>8.3f} {r:>+8.1f}% {dd:>+7.1f}% {tr:>7}{m}")

print(f"\nBest Pure MACD: ({best_macd['f']}/{best_macd['sl']}/{best_macd['sg']}) "
      f"Sharpe={best_macd['s']:.3f} Ret={best_macd['r']:+.1f}% MaxDD={best_macd['dd']:+.1f}% Trades={best_macd['t']}")

# ============ Experiment 2: MACD + RSI Sell Filter (Asymmetric) ============
print()
print("=" * 70)
print("Experiment 2: MACD + RSI Sell Filter (MACD交叉+RSI卖出过滤)")
print("=" * 70)

best_f = best_macd['f']; best_sl = best_macd['sl']; best_sg = best_macd['sg']
macd, sig_line, _ = calc_macd(df, best_f, best_sl, best_sg)
cross_up = (macd > sig_line) & (macd.shift(1) <= sig_line.shift(1))
cross_down = (macd < sig_line) & (macd.shift(1) >= sig_line.shift(1))

print(f"MACD params: ({best_f}/{best_sl}/{best_sg})")
print(f"{'sell_min':<10} {'Sharpe':>8} {'Ret%':>9} {'MaxDD%':>8} {'Trades':>7}")
print("-" * 48)

best_combo = {'s': -99}
for sm in [30, 35, 40, 45, 50, 55, 60]:
    sigs = pd.Series(0, index=df.index)
    sigs[cross_up] = 1
    sigs[cross_down & (rsi > sm)] = -1
    s, r, dd, tr = run_bt(df, sigs)
    m = " <--" if s > best_combo['s'] else ""
    if s > best_combo['s']: best_combo = {'s': s, 'r': r, 'dd': dd, 't': tr, 'sm': sm}
    print(f"{sm:<10} {s:>8.3f} {r:>+8.1f}% {dd:>+7.1f}% {tr:>7}{m}")

print(f"\nBest MACD+RSI: sell_min={best_combo['sm']} "
      f"Sharpe={best_combo['s']:.3f} Ret={best_combo['r']:+.1f}% MaxDD={best_combo['dd']:+.1f}% Trades={best_combo['t']}")

# ============ Experiment 3: MACD+RSI + WF Holdout ============
print()
print("=" * 70)
print("Experiment 3: Walk-Forward Holdout (12m)")
print("=" * 70)

df['_dt'] = pd.to_datetime(df['date'], utc=True)
cutoff = df['_dt'].iloc[-1] - pd.DateOffset(months=12)
train = df[df['_dt'] < cutoff]
test = df[df['_dt'] >= cutoff].reset_index(drop=True)

# Train
macd_t, macd_sig_t, _ = calc_macd(train, best_f, best_sl, best_sg)
cu_t = (macd_t > macd_sig_t) & (macd_t.shift(1) <= macd_sig_t.shift(1))
cd_t = (macd_t < macd_sig_t) & (macd_t.shift(1) >= macd_sig_t.shift(1))
rsi_t = calc_rsi(train, 14)
sig_t = pd.Series(0, index=train.index)
sig_t[cu_t] = 1
sig_t[cd_t & (rsi_t > best_combo['sm'])] = -1
s_tr, r_tr, dd_tr, t_tr = run_bt(train, sig_t)

macd_test, macd_sig_test, _ = calc_macd(test, best_f, best_sl, best_sg)
cu_test = (macd_test > macd_sig_test) & (macd_test.shift(1) <= macd_sig_test.shift(1))
cd_test = (macd_test < macd_sig_test) & (macd_test.shift(1) >= macd_sig_test.shift(1))
rsi_test = calc_rsi(test, 14)
sigs_test = pd.Series(0, index=test.index)
sigs_test[cu_test] = 1
sigs_test[cd_test & (rsi_test > best_combo['sm'])] = -1
s_hold, r_hold, dd_hold, t_hold = run_bt(test, sigs_test)

print(f"{'':<25} {'Full Period':>18} {'WF Holdout':>18}")
print(f"{'Sharpe':<25} {best_combo['s']:>18.3f} {s_hold:>18.3f}")
print(f"{'Return %':<25} {best_combo['r']:>+17.1f}% {r_hold:>+17.1f}%")
print(f"{'MaxDD %':<25} {best_combo['dd']:>+17.1f}% {dd_hold:>+17.1f}%")
print(f"{'Trades':<25} {best_combo['t']:>18} {t_hold:>18}")

SOTA_S = 1.456
print(f"\nvs SOTA (MA+RSI SellFilter Sharpe {SOTA_S}): {'ABOVE' if best_combo['s'] > SOTA_S else 'BELOW'}")
if s_hold > 0 and s_tr > 0:
    print(f"WF Ratio: {s_hold/best_combo['s']:.2f}x full period")
