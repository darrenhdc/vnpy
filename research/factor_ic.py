# =============================================================================
# 因子滚动 IC 验证
# =============================================================================
"""
计算各技术因子的 rolling Information Coefficient (IC)。
IC = corr(factor_t, forward_return_{t+N})

使用示例:
    from research.factor_ic import FactorIC
    from research.data_loader import load_data
    df = load_data("NVDA")
    fic = FactorIC(df, forward_periods=[5, 10, 20])
    fic.add_ma_cross_signal()
    fic.add_rsi_signal()
    fic.add_macd_signal()
    fic.report()
"""
from __future__ import annotations

import math
from typing import List, Dict

import numpy as np
import pandas as pd


class FactorIC:
    def __init__(self, df: pd.DataFrame, forward_periods: List[int] = [5, 10, 20]):
        self.df = df.copy()
        self.forward_periods = forward_periods
        self.signals: Dict[str, pd.Series] = {}

        # 计算前瞻收益
        for p in forward_periods:
            self.df[f"fwd_ret_{p}d"] = self.df["close"].shift(-p) / self.df["close"] - 1

    # ---------- 因子定义 ----------

    def add_ma_cross_signal(self, fast: int = 5, slow: int = 20, name: str = "ma_cross"):
        """MA 金叉信号：1=多头，-1=空头，0=无。"""
        # 确保 MA 列存在
        fast_col = f"ma{fast}"
        slow_col = f"ma{slow}"
        if fast_col not in self.df.columns:
            self.df[fast_col] = self.df["close"].rolling(fast, min_periods=1).mean()
        if slow_col not in self.df.columns:
            self.df[slow_col] = self.df["close"].rolling(slow, min_periods=1).mean()
        sig = pd.Series(0, index=self.df.index, dtype=float)
        sig.loc[self.df[fast_col] > self.df[slow_col]] = 1
        sig.loc[self.df[fast_col] < self.df[slow_col]] = -1
        self.signals[name] = sig
        return self

    def add_rsi_signal(self, period: int = 14, name: str = "rsi"):
        """RSI 信号：超卖=1，超买=-1。"""
        sig = pd.Series(0, index=self.df.index, dtype=float)
        sig[self.df["rsi"] < 30] = 1
        sig[self.df["rsi"] > 70] = -1
        self.signals[name] = sig
        return self

    def add_macd_signal(self, name: str = "macd"):
        """MACD 金叉信号。"""
        sig = pd.Series(0, index=self.df.index, dtype=float)
        cross_up = (self.df["macd"] > self.df["macd_signal"]) & \
                   (self.df["macd"].shift(1) <= self.df["macd_signal"].shift(1))
        cross_down = (self.df["macd"] < self.df["macd_signal"]) & \
                     (self.df["macd"].shift(1) >= self.df["macd_signal"].shift(1))
        sig.loc[self.df["macd"] > self.df["macd_signal"]] = 1
        sig.loc[self.df["macd"] < self.df["macd_signal"]] = -1
        self.signals[name] = sig
        return self

    # ---------- IC 计算 ----------

    def _calc_ic(self, signal: pd.Series, fwd_ret: pd.Series, window: int = 252) -> pd.Series:
        """滚动 Spearman 秩相关系数。"""
        valid = signal.dropna().index.intersection(fwd_ret.dropna().index)
        s = signal.loc[valid]
        r = fwd_ret.loc[valid]
        # pandas rolling corr 不支持 method='spearman'，手动计算 rank corr
        ic_vals = []
        for i in range(len(s)):
            if i < window:
                ic_vals.append(float("nan"))
                continue
            s_win = s.iloc[i - window + 1 : i + 1]
            r_win = r.iloc[i - window + 1 : i + 1]
            if s_win.std() == 0 or r_win.std() == 0:
                ic_vals.append(float("nan"))
                continue
            try:
                ic = s_win.corr(r_win, method="spearman")
            except Exception:
                # fallback to pearson if spearman fails
                ic = s_win.corr(r_win)
            ic_vals.append(ic)
        return pd.Series(ic_vals, index=s.index)

    def report(self):
        """打印各因子在各前瞻周期的 IC。"""
        print("\n" + "=" * 80)
        print(" 因子滚动 IC 报告")
        print("=" * 80)

        for sig_name, sig in self.signals.items():
            print(f"\n【因子】{sig_name}")
            for p in self.forward_periods:
                fwd_col = f"fwd_ret_{p}d"
                ic_series = self._calc_ic(sig, self.df[fwd_col])
                mean_ic = ic_series.mean()
                std_ic = ic_series.std()
                ir = mean_ic / std_ic if std_ic > 0 else 0
                pct_positive = (ic_series > 0).mean() * 100
                print(f"  {p:3d}d 前瞻 | IC={mean_ic:+.3f} | IR={ir:.2f} | 正相关占比={pct_positive:.0f}%")

        print("=" * 80)

    def get_ic_df(self) -> pd.DataFrame:
        """返回所有因子的 IC DataFrame。"""
        records = []
        for sig_name, sig in self.signals.items():
            for p in self.forward_periods:
                fwd_col = f"fwd_ret_{p}d"
                ic_series = self._calc_ic(sig, self.df[fwd_col])
                records.append({
                    "factor": sig_name,
                    "forward": f"{p}d",
                    "mean_ic": ic_series.mean(),
                    "std_ic": ic_series.std(),
                    "ir": ic_series.mean() / ic_series.std() if ic_series.std() > 0 else 0,
                    "pct_positive": (ic_series > 0).mean() * 100,
                })
        return pd.DataFrame(records)
