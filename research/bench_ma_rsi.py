"""
research/bench_ma_rsi.py — MA+RSI 双确认 vs SOTA 完整对比
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from research.data_loader import load_data
from research.backtest import run_backtest, BacktestParams

df = load_data('SPY', '1d', '5y')
p = BacktestParams(order_size_pct=0.30)

r1 = run_backtest(df, p, 'ma_cross', 'SPY', {'fast': 5, 'slow': 15})
r2 = run_backtest(df, p, 'ma_rsi_cross_confirm', 'SPY',
                  {'fast': 5, 'slow': 15, 'rsi_buy_max': 50, 'rsi_sell_min': 50})

sep = '-' * 70
print('=' * 70)
print('SPY 5年全周期回测: SOTA vs MA+RSI 双确认')
print('=' * 70)
print(f"{'Metric':<25} {'SOTA MA Cross':>18} {'MA+RSI Confirm':>18}")
print(sep)
print(f"{'Sharpe':<25} {r1.sharpe:>18.3f} {r2.sharpe:>18.3f}")
print(f"{'Total Return %':<25} {r1.total_return_pct:>+17.1f}% {r2.total_return_pct:>+17.1f}%")
print(f"{'Ann Return %':<25} {r1.annualized_return_pct:>+17.1f}% {r2.annualized_return_pct:>+17.1f}%")
print(f"{'Max Drawdown %':<25} {r1.max_drawdown_pct:>+17.1f}% {r2.max_drawdown_pct:>+17.1f}%")
print(f"{'B&H Return %':<25} {r1.bh_return_pct:>+17.1f}% {r2.bh_return_pct:>+17.1f}%")
print(f"{'Total Trades':<25} {r1.n_trades:>18} {r2.n_trades:>18}")
print(f"{'Buy / Sell':<25} {r1.n_buys:>7} / {r1.n_sells:<7}  {r2.n_buys:>7} / {r2.n_sells:<7}")
print()
delta_s = r2.sharpe - r1.sharpe
delta_t = r2.n_trades - r1.n_trades
print(f"Delta Sharpe: {delta_s:+.3f}  |  Delta Trades: {delta_t:+d}")
print(f"Trades reduced: {int((1 - r2.n_trades / max(r1.n_trades, 1)) * 100)}%")
