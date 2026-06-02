# =============================================================================
# Walk-Forward 验证框架
# =============================================================================
"""
时间序列 walk-forward 验证：
- train_window: 训练期长度（交易日）
- test_window:  测试期长度（交易日）
- step:         每次向前滚动步长
- holdout:      最终保留验证期

使用示例:
    from research.walk_forward import WalkForward
    from research.data_loader import load_data
    from research.backtest import run_backtest, BacktestParams

    df = load_data("NVDA", interval="1d", period="5y")
    wf = WalkForward(df, train=252*1.5, test=63, step=63)
    results = wf.run(lambda train_df: run_backtest(train_df, BacktestParams(), strategy="ma_cross"))
    wf.summary()
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Callable, List, Dict, Any, Optional

import pandas as pd
import numpy as np

from research.backtest import BacktestResult


@dataclass
class WFWindowResult:
    train_start: str
    train_end: str
    test_start: str
    test_end: str
    result: BacktestResult
    params: Optional[Dict] = None


class WalkForward:
    def __init__(
        self,
        df: pd.DataFrame,
        train_window: int,
        test_window: int,
        step: int,
        holdout_window: Optional[int] = None,
    ):
        """
        df: 完整数据，必须包含 'date' 列（datetime）
        train_window: 训练期 bar 数
        test_window:  测试期 bar 数
        step:         滚动步长 bar 数
        holdout:      最终 holdout 验证 bar 数
        """
        self.df = df.reset_index(drop=True)
        self.train = train_window
        self.test = test_window
        self.step = step
        self.holdout = holdout_window
        self.windows: List[WFWindowResult] = []

    def run(
        self,
        backtest_fn: Callable[[pd.DataFrame], BacktestResult],
        optimize_fn: Optional[Callable[[pd.DataFrame], Dict[str, Any]]] = None,
    ) -> List[WFWindowResult]:
        """
        执行 walk-forward。
        optimize_fn(train_df) -> dict 最优参数（可选，默认不做优化）
        backtest_fn(test_df) -> BacktestResult
        """
        total = len(self.df)
        i = 0
        while i + self.train + self.test <= total:
            train_df = self.df.iloc[i : i + self.train].copy()
            test_df = self.df.iloc[i + self.train : i + self.train + self.test].copy()

            # 可选：参数优化
            best_params = optimize_fn(train_df) if optimize_fn else None

            # 回测
            result = backtest_fn(test_df)

            self.windows.append(WFWindowResult(
                train_start=str(train_df["date"].iloc[0]),
                train_end=str(train_df["date"].iloc[-1]),
                test_start=str(test_df["date"].iloc[0]),
                test_end=str(test_df["date"].iloc[-1]),
                result=result,
                params=best_params,
            ))
            i += self.step

        # Holdout
        if self.holdout:
            hold_df = self.df.iloc[-self.holdout:].copy()
            result = backtest_fn(hold_df)
            self.windows.append(WFWindowResult(
                train_start="HOLDOUT",
                train_end="HOLDOUT",
                test_start=str(hold_df["date"].iloc[0]),
                test_end=str(hold_df["date"].iloc[-1]),
                result=result,
                params=None,
            ))

        return self.windows

    def summary(self):
        """打印汇总。"""
        print("\n" + "=" * 80)
        print(" Walk-Forward 汇总")
        print("=" * 80)
        returns = []
        sharpes = []
        maxdds = []
        n_trades = []

        for w in self.windows:
            r = w.result
            returns.append(r.total_return_pct)
            sharpes.append(r.sharpe if not math.isnan(r.sharpe) else 0)
            maxdds.append(r.max_drawdown_pct)
            n_trades.append(r.n_trades)
            print(f"  {w.test_start[:10]} ~ {w.test_end[:10]} | "
                  f"Ret {r.total_return_pct:+.1f}% | "
                  f"Sharpe {r.sharpe:.2f} | "
                  f"MaxDD {r.max_drawdown_pct:.1f}% | "
                  f"Trades {r.n_trades}")

        print("-" * 80)
        print(f"  平均回报:   {np.mean(returns):+.1f}%")
        print(f"  平均 Sharpe: {np.mean(sharpes):.2f}")
        print(f"  平均 MaxDD:  {np.mean(maxdds):.1f}%")
        print(f"  总交易数:   {sum(n_trades)}")
        print("=" * 80)

    def aggregate_portfolio(self) -> pd.DataFrame:
        """拼接所有 test 窗口的 portfolio_value，计算整体曲线。"""
        dfs = []
        for w in self.windows:
            if w.result.portfolio_df is not None and not w.result.portfolio_df.empty:
                dfs.append(w.result.portfolio_df)
        if not dfs:
            return pd.DataFrame()
        combined = pd.concat(dfs, ignore_index=True)
        return combined
