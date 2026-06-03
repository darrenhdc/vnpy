"""research/atr_wf.py — ATR Sizing Walk-Forward Validation"""
import sys, math
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd
import numpy as np
from research.data_loader import load_data

df = load_data('SPY', '1d', '5y')

# Parameters from search
ATR_LB = 14; HI_THR = 1.5; LO_THR = 0.8; LO_MULT = 2.0; HI_MULT = 0.33
BASE_PCT = 0.30

# Full period signals
fc = df['close'].rolling(5, min_periods=1).mean()
sc = df['close'].rolling(15, min_periods=1).mean()
gc = (fc > sc) & (fc.shift(1) <= sc.shift(1))
dc = (fc < sc) & (fc.shift(1) >= sc.shift(1))
d = df['close'].diff()
g = d.clip(lower=0).ewm(alpha=1/14, adjust=False).mean()
l = (-d.clip(upper=0)).ewm(alpha=1/14, adjust=False).mean()
rsi = 100.0 - (100.0/(1.0 + g/l.replace(0, float('nan'))))
sigs_full = pd.Series(0, index=df.index)
sigs_full[gc] = 1
sigs_full[dc & (rsi > 40)] = -1

# ATR helper
def calc_atr(df, lb=14):
    h = df['high']; l = df['low']; cp = df['close'].shift(1)
    tr = pd.concat([(h-l), (h-cp).abs(), (l-cp).abs()], axis=1).max(axis=1)
    return tr.ewm(alpha=1/lb, adjust=False).mean()

def run_bt_atr(df, signals, atr, atr_med):
    cash = 10000.0; shares = 0.0; trades = 0; vals = []
    for i in range(len(df)):
        c = float(df['close'].iloc[i])
        if i > 0:
            sig = int(signals.iloc[i-1]) if i-1 < len(signals) else 0
            po = float(df['open'].iloc[i])
            mult = 1.0
            if i-1 < len(atr_med) and pd.notna(atr_med.iloc[i-1]):
                an = float(atr.iloc[i-1]); am = float(atr_med.iloc[i-1])
                if am > 0:
                    ratio = an/am
                    if ratio > HI_THR: mult = HI_MULT
                    elif ratio < LO_THR: mult = LO_MULT
            adj = BASE_PCT * mult
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
    return s, r, dd, trades

# Full period (no look-ahead)
atr_full = calc_atr(df, ATR_LB)
atr_med_full = atr_full.rolling(252, min_periods=63).median()
r_full = run_bt_atr(df, sigs_full, atr_full, atr_med_full)

# WF Holdout: train = first 4y, test = last 12m
df['_dt'] = pd.to_datetime(df['date'], utc=True)
cutoff = df['_dt'].iloc[-1] - pd.DateOffset(months=12)
train_mask = df['_dt'] < cutoff

# Build ATR median from training data ONLY (no look-ahead)
atr_train = calc_atr(df[train_mask], ATR_LB)
atr_med_train = atr_train.rolling(252, min_periods=63).median()

# But we need to apply the atr_med from training to the FULL dataset
# This is tricky because atr_med is indexed to train only
# Simplification: for test period, use the LAST atr_med value from training as the reference
# (since the training median is the "normal" level)

# Better approach: compute atr on full df, but atr_med ONLY from expanding window ending at the last training day
# Actually, let me just build a proper WF: compute signals separately for train and test,
# and use expanding-window ATR median for the test period that uses only info available at cutoff

# Compute ATR for full df
atr_full_all = calc_atr(df, ATR_LB)

# For the test period, the "median" should be based on the training period's ATR distribution
# Use the last value of training ATR median as a constant for the test period
last_train_med = float(atr_med_train.dropna().iloc[-1]) if len(atr_med_train.dropna()) > 0 else 1.0

# For the holdout test, use a custom atr_med: train median for train period, then last_train_med for test
atr_med_holdout = pd.Series(index=df.index, dtype=float)
for i in range(len(df)):
    if i < len(atr_med_train) and pd.notna(atr_med_train.iloc[i]):
        atr_med_holdout.iloc[i] = atr_med_train.iloc[i]
    elif i >= 252:  # Use rolling 252d median of full ATR (valid for all dates since we're past cutoff)
        # Use expanding median computed from training period's last value
        atr_med_holdout.iloc[i] = last_train_med

r_hold = run_bt_atr(df, sigs_full, atr_full_all, atr_med_holdout)

# Also compute baseline (no ATR) for comparison
def run_bt_no_atr(df, signals):
    cash = 10000.0; shares = 0.0; trades = 0; vals = []
    for i in range(len(df)):
        c = float(df['close'].iloc[i])
        if i > 0:
            sig = int(signals.iloc[i-1]) if i-1 < len(signals) else 0
            po = float(df['open'].iloc[i])
            if sig == 1 and shares <= 0:
                alloc = min(cash * BASE_PCT, cash)
                if alloc >= 100:
                    fee = alloc * 0.00001; shares = (alloc-fee)/po; cash -= alloc; trades += 1
            elif sig == -1 and shares > 0:
                sv = shares*po; cash += sv-sv*0.00001; shares=0.0; trades += 1
        vals.append(cash+shares*c)
    rets = pd.Series(vals).pct_change().dropna()
    s = float((rets.mean()/rets.std())*math.sqrt(252)) if len(rets)>=5 and rets.std()>0 else 0
    dd = float(((pd.Series(vals)-pd.Series(vals).cummax())/pd.Series(vals).cummax().replace(0,float('nan'))).min()*100)
    r = (vals[-1]/10000-1)*100
    return s, r, dd, trades

# Full period baseline (no ATR)
r_base = run_bt_no_atr(df, sigs_full)

# Test-only baseline
test_df = df[~train_mask].reset_index(drop=True)
# Recompute signals for test period
fc_t = test_df['close'].rolling(5, min_periods=1).mean()
sc_t = test_df['close'].rolling(15, min_periods=1).mean()
gc_t = (fc_t > sc_t) & (fc_t.shift(1) <= sc_t.shift(1))
dc_t = (fc_t < sc_t) & (fc_t.shift(1) >= sc_t.shift(1))
d_t = test_df['close'].diff()
g_t = d_t.clip(lower=0).ewm(alpha=1/14, adjust=False).mean()
l_t = (-d_t.clip(upper=0)).ewm(alpha=1/14, adjust=False).mean()
rsi_t = 100.0 - (100.0/(1.0 + g_t/l_t.replace(0, float('nan'))))
sigs_test = pd.Series(0, index=test_df.index)
sigs_test[gc_t] = 1
sigs_test[dc_t & (rsi_t > 40)] = -1
r_base_hold = run_bt_no_atr(test_df, sigs_test)

# Test-only with ATR sizing
atr_test = calc_atr(test_df, ATR_LB)
atr_med_test = pd.Series([last_train_med] * len(test_df), index=test_df.index)
r_atr_hold = run_bt_atr(test_df, sigs_test, atr_test, atr_med_test)

print('=' * 70)
print(f'ATR Binary Sizing: WF Validation')
print(f'  Params: ATR_LB={ATR_LB} HI_THR={HI_THR} LO_THR={LO_THR} LO_MULT={LO_MULT}')
print('=' * 70)
print()
print(f'{"":<25} {"Full Period":>18} {"WF Holdout":>18}')
print('-' * 65)
print(f'--- Baseline (no ATR) ---')
print(f'{"Sharpe":<25} {r_base[0]:>18.3f} {r_base_hold[0]:>18.3f}')
print(f'{"Return %":<25} {r_base[1]:>+17.1f}% {r_base_hold[1]:>+17.1f}%')
print(f'{"MaxDD %":<25} {r_base[2]:>+17.1f}% {r_base_hold[2]:>+17.1f}%')
print(f'{"Trades":<25} {r_base[3]:>18} {r_base_hold[3]:>18}')
print()
print(f'--- ATR Binary Sizing ---')
print(f'{"Sharpe":<25} {r_full[0]:>18.3f} {r_atr_hold[0]:>18.3f}')
print(f'{"Return %":<25} {r_full[1]:>+17.1f}% {r_atr_hold[1]:>+17.1f}%')
print(f'{"MaxDD %":<25} {r_full[2]:>+17.1f}% {r_atr_hold[2]:>+17.1f}%')
print(f'{"Trades":<25} {r_full[3]:>18} {r_atr_hold[3]:>18}')
print()
print(f'Full Period: ATR adds {r_full[0]-r_base[0]:+.3f} Sharpe')
print(f'WF Holdout:  ATR adds {r_atr_hold[0]-r_base_hold[0]:+.3f} Sharpe')
