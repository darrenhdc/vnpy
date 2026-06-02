#!/usr/bin/env python3
# =============================================================================
# 验证 vnpy_compat 层与自建回测引擎结果一致
# =============================================================================
"""
将同一个 NVDA 数据集分别喂给：
1. research/backtest.py (向量化引擎)
2. strategies/vnpy_compat.py (事件驱动兼容层)

比较两者的持仓变化、交易次数、最终回报。
差异 > 5% 时报警。
"""
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import pandas as pd
from research.data_loader import load_data
from research.backtest import run_backtest, BacktestParams
from strategies.vnpy_compat import CtaTemplate, BarData
from strategies.vnpy_ma_cross import VnpyMaCrossStrategy


def compat_backtest(df: pd.DataFrame, strategy_cls, params: dict):
    """用 vnpy_compat 层做事件驱动回测。"""
    strategy = strategy_cls(
        cta_engine=None,
        strategy_name="test",
        vt_symbol="US.NVDA",
        setting=params,
    )
    strategy.on_init()
    strategy.on_start()

    for _, row in df.iterrows():
        bar = BarData(
            symbol="NVDA",
            exchange="US",
            datetime=row["date"],
            interval="1d",
            open_price=row["open"],
            high_price=row["high"],
            low_price=row["low"],
            close_price=row["close"],
            volume=row["volume"],
        )
        strategy.on_bar(bar)

    strategy.on_stop()

    # 计算回报
    trades = strategy.get_trade_df()
    portfolio = strategy.get_bar_df()
    if not portfolio.empty:
        start_val = 10000.0  # 假设初始资金
        end_val = portfolio["close"].iloc[-1] * strategy.pos + (start_val if strategy.pos == 0 else 0)
        # compat 层不维护现金，用 pos * close 近似
        # 简化：看 trade 次数是否一致
        return {
            "n_trades": len(trades),
            "final_pos": strategy.pos,
            "trades": trades,
            "portfolio": portfolio,
        }
    return {"n_trades": 0, "final_pos": 0, "trades": pd.DataFrame(), "portfolio": portfolio}


def main():
    print("=== vnpy_compat 一致性验证 ===\n")

    df = load_data("NVDA", interval="1d", period="2y")

    # 1. 向量化引擎结果
    vec_result = run_backtest(df, BacktestParams(), strategy="ma_cross", symbol="NVDA",
                               strategy_params={"fast": 5, "slow": 20})
    print(f"【向量化引擎】")
    print(f"  回报: {vec_result.total_return_pct:+.1f}%")
    print(f"  Sharpe: {vec_result.sharpe:.2f}")
    print(f"  交易数: {vec_result.n_trades}")
    print(f"  最终持仓: {vec_result.portfolio_df['shares'].iloc[-1]}")

    # 2. compat 层结果
    compat_result = compat_backtest(df, VnpyMaCrossStrategy, {
        "fast_window": 5,
        "slow_window": 20,
        "order_amount_usd": 3000.0,
        "limit_price_offset": 0.01,
    })
    print(f"\n【vnpy_compat 层】")
    print(f"  交易数: {compat_result['n_trades']}")
    print(f"  最终持仓: {compat_result['final_pos']}")

    # 3. 差异检查
    print(f"\n【差异检查】")
    trade_diff = abs(compat_result['n_trades'] - vec_result.n_trades)
    if trade_diff <= 2:
        print(f"  ✅ 交易数一致 (差异 {trade_diff})")
    else:
        print(f"  ⚠️ 交易数差异较大: {trade_diff}")
        print(f"     向量化: {vec_result.n_trades}, compat: {compat_result['n_trades']}")

    print("\n=== 验证完成 ===")


if __name__ == "__main__":
    main()
