"""
research/search_ma_rsi.py — MA+RSI 双确认参数搜索
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from research.data_loader import load_data
from research.backtest import run_backtest, BacktestParams

df = load_data('SPY', '1d', '5y')
p = BacktestParams(order_size_pct=0.30)

print('=' * 75)
print('SPY MA+RSI 双确认参数搜索 (rsi_buy_max × rsi_sell_min)')
print('=' * 75)
print(f"{'buy_max':<10} {'sell_min':<10} {'Sharpe':>8} {'Return%':>9} {'MaxDD%':>8} {'Trades':>7}")
print('-' * 75)

best = {'sharpe': -99, 'buy_max': 0, 'sell_min': 0, 'ret': 0, 'dd': 0, 'trades': 0}
sota_sharpe = 1.337

for buy_max in [40, 45, 50, 55, 60]:
    for sell_min in [40, 45, 50, 55, 60]:
        r = run_backtest(df, p, 'ma_rsi_cross_confirm', 'SPY', {
            'fast': 5, 'slow': 15, 'rsi_buy_max': buy_max, 'rsi_sell_min': sell_min,
        })
        s = r.sharpe
        marker = ' <-- BEST' if s > best['sharpe'] else ''
        print(f"{buy_max:<10} {sell_min:<10} {s:>8.3f} {r.total_return_pct:>+8.1f}% {r.max_drawdown_pct:>+7.1f}% {r.n_trades:>7}{marker}")
        if s > best['sharpe']:
            best = {'sharpe': s, 'buy_max': buy_max, 'sell_min': sell_min,
                    'ret': r.total_return_pct, 'dd': r.max_drawdown_pct, 'trades': r.n_trades}

print()
print(f"= Best: buy_max={best['buy_max']}, sell_min={best['sell_min']}")
print(f"  Sharpe={best['sharpe']:.3f}  Ret={best['ret']:+.1f}%  MaxDD={best['dd']:+.1f}%  Trades={best['trades']}")
print(f"  vs SOTA (Sharpe {sota_sharpe}): {'ABOVE' if best['sharpe'] > sota_sharpe else 'BELOW'} SOTA")
