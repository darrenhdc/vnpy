#!/usr/bin/env python3
# =============================================================================
# SPY + QQQ 消融实验
# =============================================================================
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import pandas as pd
from research.data_loader import load_data
from research.backtest import run_backtest, BacktestParams
from research.factor_ic import FactorIC
from research.walk_forward import WalkForward


SYMBOLS = ["SPY", "QQQ"]
STRATEGIES = ["ma_cross", "rsi", "macd", "ma_rsi_combo"]


def run_ablation(symbol: str):
    print(f"\n{'='*80}")
    print(f"  标的: {symbol}")
    print(f"{'='*80}")

    df = load_data(symbol, interval="1d", period="5y")
    print(f"数据: {len(df)} 条 | {df['date'].iloc[0]} ~ {df['date'].iloc[-1]}")

    # 1. IC 验证
    print(f"\n--- 因子 IC ---")
    fic = FactorIC(df, forward_periods=[5, 10, 20])
    fic.add_ma_cross_signal(fast=5, slow=20, name="ma_5_20")
    fic.add_rsi_signal(name="rsi_14")
    fic.add_macd_signal(name="macd_12_26")
    fic.report()

    # 2. 策略回测消融
    print(f"\n--- 策略回测消融 ---")
    results = {}
    for s in STRATEGIES:
        r = run_backtest(df, BacktestParams(), strategy=s, symbol=symbol)
        results[s] = r
        print(f"\n{s:15s} | Ret={r.total_return_pct:+6.1f}% | B&H={r.bh_return_pct:+6.1f}% | "
              f"Sharpe={r.sharpe:.2f} | MaxDD={r.max_drawdown_pct:6.1f}% | Trades={r.n_trades}")

    # 3. Walk-Forward (best strategy from IC)
    print(f"\n--- Walk-Forward (ma_cross) ---")
    wf = WalkForward(df, train_window=378, test_window=63, step=63, holdout_window=252)
    wf.run(lambda test_df: run_backtest(test_df, BacktestParams(), strategy="ma_cross", symbol=symbol))
    wf.summary()

    # 4. 参数搜索 (MA cross)
    print(f"\n--- MA 参数搜索 ---")
    best = None
    best_sharpe = -999
    for fast in [3, 5, 10, 15, 20]:
        for slow in [15, 20, 30, 50]:
            if fast >= slow:
                continue
            r = run_backtest(df, BacktestParams(), strategy="ma_cross", symbol=symbol,
                              strategy_params={"fast": fast, "slow": slow})
            sharpe = r.sharpe if not pd.isna(r.sharpe) else -999
            if sharpe > best_sharpe:
                best_sharpe = sharpe
                best = (fast, slow, r)
            print(f"  fast={fast:2d} slow={slow:2d} | Ret={r.total_return_pct:+6.1f}% | "
                  f"Sharpe={sharpe:.2f} | MaxDD={r.max_drawdown_pct:6.1f}% | Trades={r.n_trades}")

    if best:
        print(f"\n最优: fast={best[0]} slow={best[1]} | Sharpe={best_sharpe:.2f}")
        best[2].summary()

    return results


def main():
    all_results = {}
    for sym in SYMBOLS:
        all_results[sym] = run_ablation(sym)

    print(f"\n{'='*80}")
    print("  消融实验完成")
    print(f"{'='*80}")


if __name__ == "__main__":
    main()
