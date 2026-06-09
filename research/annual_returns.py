"""Annual returns for SPY B&H vs MA Cross"""
import sys, math
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import pandas as pd, numpy as np
from research.data_loader import load_data

df = load_data('SPY', '1d', '15y')
df['year'] = pd.to_datetime(df['date'], utc=True).dt.year
spy_annual = df.groupby('year').apply(lambda g: (g['close'].iloc[-1]/g['close'].iloc[0]-1)*100)

print('SPY 年收益 (Buy & Hold)')
print('=' * 50)
for yr, ret in spy_annual.items():
    bar = '+'*int(max(0,ret/2)) if ret>0 else '-'*int(abs(ret/2))
    print(f'  {yr}  {ret:+6.1f}%  {bar}')

print('=' * 50)
total_bh = (df['close'].iloc[-1]/df['close'].iloc[0]-1)*100
pos = (spy_annual > 0).sum()
print(f'15y total: {total_bh:+.0f}%  |  Positive: {pos}/15  |  Best {spy_annual.idxmax()} ({spy_annual.max():+.1f}%)  Worst {spy_annual.idxmin()} ({spy_annual.min():+.1f}%)')

# MA Cross (5/15) annual
print()
print('MA Cross (5/15) 年收益')
print('=' * 50)
fc = df['close'].rolling(5, min_periods=1).mean()
sc = df['close'].rolling(15, min_periods=1).mean()
gc = (fc>sc)&(fc.shift(1)<=sc.shift(1))
dc = (fc<sc)&(fc.shift(1)>=sc.shift(1))
cash,sh = 10000.0,0.0
annual = {}
for i in range(len(df)):
    c=float(df['close'].iloc[i]); yr=int(df['year'].iloc[i])
    if yr not in annual: annual[yr]=[]
    if i>0:
        if bool(gc.iloc[i-1]) and sh<=0:
            a=min(cash*0.3,cash)
            if a>=100: sh=(a-a*0.00001)/float(df['open'].iloc[i]); cash-=a
        elif bool(dc.iloc[i-1]) and sh>0:
            cash+=sh*float(df['open'].iloc[i])*(1-0.00001); sh=0
    annual[yr].append(cash+sh*c)

for yr in sorted(annual.keys()):
    vals=annual[yr]
    r=(vals[-1]/vals[0]-1)*100
    sr=spy_annual.get(yr,0)
    bar='+'*int(max(0,r/2)) if r>0 else '-'*int(abs(r/2))
    v='BEAT' if r>sr else 'LOSS' if r<0 else ''
    print(f'  {yr}  {r:+6.1f}%  {bar}  (SPY {sr:+5.1f}%)  {v}')
final=annual[sorted(annual.keys())[-1]][-1]
total_s=(final/10000-1)*100
pos_s=sum(1 for v in annual.values() if v[-1]>v[0])
print('=' * 50)
print(f'15y total: {total_s:+.0f}%  |  Positive: {pos_s}/15  |  Beat SPY: {(total_s>total_bh)}')
