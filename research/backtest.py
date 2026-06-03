"""
research/backtest.py — 向量化回测引擎（美股现货）
================================================
Signal day t, execute next day t+1 open.
Single-asset, long-only (no short in standard cash account).
Fee: 0.001% (Futu US stock commission).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional, Dict, Any

import numpy as np
import pandas as pd

from research.data_loader import load_data


@dataclass
class BacktestParams:
    initial_cash: float = 10000.0
    order_size_pct: float = 0.20        # 20% of cash per trade
    max_position_pct: float = 0.80       # max 80% allocation
    fee_rate: float = 0.00001            # Futu US: 0.001% one-way
    min_trade_value: float = 100.0       # minimum $100 per trade
    max_daily_trades: int = 1


@dataclass
class BacktestResult:
    params: BacktestParams
    portfolio_df: pd.DataFrame
    trades_df: pd.DataFrame
    strategy_name: str = ""
    strategy_params: Optional[Dict[str, Any]] = None

    @property
    def total_return_pct(self) -> float:
        vals = self.portfolio_df["portfolio_value"]
        if vals.iloc[0] <= 0: return 0.0
        return (vals.iloc[-1] / vals.iloc[0] - 1) * 100

    @property
    def bh_return_pct(self) -> float:
        prices = self.portfolio_df["close"]
        if prices.iloc[0] <= 0: return 0.0
        return (prices.iloc[-1] / prices.iloc[0] - 1) * 100

    @property
    def sharpe(self) -> float:
        daily = self.portfolio_df["portfolio_value"].pct_change().dropna()
        if len(daily) < 5 or daily.std() == 0: return float("nan")
        return float((daily.mean() / daily.std()) * math.sqrt(252))

    @property
    def max_drawdown_pct(self) -> float:
        vals = self.portfolio_df["portfolio_value"]
        peak = vals.cummax()
        return float(((vals - peak) / peak).min() * 100)

    @property
    def annualized_return_pct(self) -> float:
        vals = self.portfolio_df["portfolio_value"]
        n = len(vals)
        if n < 2: return 0.0
        years = n / 252
        ret = 1 + self.total_return_pct / 100
        return (ret ** (1/years) - 1) * 100

    @property
    def n_trades(self) -> int: return len(self.trades_df)

    @property
    def n_buys(self) -> int:
        return int((self.trades_df["side"] == "buy").sum()) if len(self.trades_df) > 0 else 0

    @property
    def n_sells(self) -> int:
        return int((self.trades_df["side"] == "sell").sum()) if len(self.trades_df) > 0 else 0

    def summary(self) -> None:
        print(f"Return:   {self.total_return_pct:+.1f}%")
        print(f"B&H:      {self.bh_return_pct:+.1f}%")
        print(f"Ann.Ret:  {self.annualized_return_pct:+.1f}%")
        print(f"Sharpe:   {self.sharpe:.3f}")
        print(f"MaxDD:    {self.max_drawdown_pct:+.1f}%")
        print(f"Trades:   {self.n_trades} ({self.n_buys}B/{self.n_sells}S)")


def _ensure_ma(df: pd.DataFrame, window: int) -> str:
    """确保 DataFrame 有指定周期的 MA 列，返回列名。"""
    col = f"ma{window}"
    if col not in df.columns:
        df[col] = df["close"].rolling(window, min_periods=1).mean()
    return col


def generate_signals(
    df: pd.DataFrame,
    strategy: str = "ma_cross",
    **kwargs: Any,
) -> pd.Series:
    """
    Generate buy/hold/sell signals.
    Returns Series of int: 1=buy, 0=hold, -1=sell.

    Parameters
    ----------
    strategy : str
        "ma_cross", "rsi", "macd", "ma_rsi_combo"
    kwargs :
        ma_cross: fast=5, slow=20
        rsi: rsi_period=14, oversold=30, overbought=70
        macd: fast=12, slow=26, signal=9
        ma_rsi_combo: ma_period=50, oversold=30, overbought=70
    """
    signals = pd.Series(0, index=df.index)

    if strategy == "ma_cross":
        fast = kwargs.get("fast", 5)
        slow = kwargs.get("slow", 20)
        fast_col = _ensure_ma(df, fast)
        slow_col = _ensure_ma(df, slow)
        golden_cross = (df[fast_col] > df[slow_col]) & (df[fast_col].shift(1) <= df[slow_col].shift(1))
        death_cross = (df[fast_col] < df[slow_col]) & (df[fast_col].shift(1) >= df[slow_col].shift(1))
        signals[golden_cross] = 1
        signals[death_cross] = -1

    elif strategy == "rsi":
        period = kwargs.get("rsi_period", 14)
        oversold = kwargs.get("oversold", 30)
        overbought = kwargs.get("overbought", 70)
        # Ensure RSI exists
        if "rsi" not in df.columns or kwargs.get("force_recalc", False):
            delta = df["close"].diff()
            gain = delta.clip(lower=0)
            loss = (-delta).clip(lower=0)
            avg_gain = gain.ewm(alpha=1 / period, adjust=False).mean()
            avg_loss = loss.ewm(alpha=1 / period, adjust=False).mean()
            rs = avg_gain / avg_loss.replace(0, float("nan"))
            df["rsi"] = 100.0 - (100.0 / (1.0 + rs))
        signals[df["rsi"] < oversold] = 1
        signals[df["rsi"] > overbought] = -1

    elif strategy == "macd":
        fast = kwargs.get("fast", 12)
        slow = kwargs.get("slow", 26)
        signal_period = kwargs.get("signal", 9)
        # Ensure MACD exists
        if "macd" not in df.columns or kwargs.get("force_recalc", False):
            ema_fast = df["close"].ewm(span=fast, adjust=False).mean()
            ema_slow = df["close"].ewm(span=slow, adjust=False).mean()
            df["macd"] = ema_fast - ema_slow
            df["macd_signal"] = df["macd"].ewm(span=signal_period, adjust=False).mean()
        cross_up = (df["macd"] > df["macd_signal"]) & (df["macd"].shift(1) <= df["macd_signal"].shift(1))
        cross_down = (df["macd"] < df["macd_signal"]) & (df["macd"].shift(1) >= df["macd_signal"].shift(1))
        signals[cross_up] = 1
        signals[cross_down] = -1

    elif strategy == "ma_rsi_combo":
        ma_period = kwargs.get("ma_period", 50)
        oversold = kwargs.get("oversold", 30)
        overbought = kwargs.get("overbought", 70)
        ma_col = _ensure_ma(df, ma_period)
        if "rsi" not in df.columns:
            delta = df["close"].diff()
            gain = delta.clip(lower=0)
            loss = (-delta).clip(lower=0)
            avg_gain = gain.ewm(alpha=1 / 14, adjust=False).mean()
            avg_loss = loss.ewm(alpha=1 / 14, adjust=False).mean()
            rs = avg_gain / avg_loss.replace(0, float("nan"))
            df["rsi"] = 100.0 - (100.0 / (1.0 + rs))
        bull = df["close"] > df[ma_col]
        signals[(bull) & (df["rsi"] < oversold)] = 1
        signals[(~bull) & (df["rsi"] > overbought)] = -1

    elif strategy == "ma_rsi_cross_confirm":
        fast = kwargs.get("fast", 5)
        slow = kwargs.get("slow", 15)
        rsi_period = kwargs.get("rsi_period", 14)
        buy_max = kwargs.get("rsi_buy_max", 50)
        sell_min = kwargs.get("rsi_sell_min", 50)
        fast_col = _ensure_ma(df, fast)
        slow_col = _ensure_ma(df, slow)
        if "rsi" not in df.columns or kwargs.get("force_recalc", False):
            delta = df["close"].diff()
            gain = delta.clip(lower=0)
            loss = (-delta).clip(lower=0)
            avg_gain = gain.ewm(alpha=1 / rsi_period, adjust=False).mean()
            avg_loss = loss.ewm(alpha=1 / rsi_period, adjust=False).mean()
            rs = avg_gain / avg_loss.replace(0, float("nan"))
            df["rsi"] = 100.0 - (100.0 / (1.0 + rs))
        golden_cross = (df[fast_col] > df[slow_col]) & (df[fast_col].shift(1) <= df[slow_col].shift(1))
        death_cross = (df[fast_col] < df[slow_col]) & (df[fast_col].shift(1) >= df[slow_col].shift(1))
        signals[golden_cross & (df["rsi"] < buy_max)] = 1
        signals[death_cross & (df["rsi"] > sell_min)] = -1

    return signals


def run_backtest(
    df: pd.DataFrame,
    params: Optional[BacktestParams] = None,
    strategy: str = "ma_cross",
    symbol: str = "AAPL",
    strategy_params: Optional[Dict[str, Any]] = None,
) -> BacktestResult:
    """
    Vectorized single-asset backtest. Signal on day t, execute on day t+1 open.
    """
    params = params or BacktestParams()
    strategy_params = strategy_params or {}
    signals = generate_signals(df, strategy, **strategy_params)

    cash = params.initial_cash
    shares: float = 0.0
    trade_rows: list[dict] = []
    portfolio_rows: list[dict] = []

    for i in range(len(df)):
        row = df.iloc[i]
        date = row["date"]
        close = float(row["close"])

        # Execute pending signal at NEXT day's open
        if i > 0 and i - 1 < len(signals):
            sig = signals.iloc[i - 1]
            p_open = float(row["open"])
            p_value = cash + shares * p_open

            if sig == 1 and shares <= 0:  # Buy
                alloc = min(cash * params.order_size_pct, cash)
                max_shares_value = p_value * params.max_position_pct
                buy_value = min(alloc, max_shares_value, cash)
                if buy_value >= params.min_trade_value:
                    fee = buy_value * params.fee_rate
                    buy_shares = (buy_value - fee) / p_open
                    cash -= buy_value
                    shares += buy_shares
                    trade_rows.append({
                        "date": date, "side": "buy", "price": round(p_open, 2),
                        "shares": round(buy_shares, 2), "value": round(buy_value, 2),
                        "fee": round(fee, 4), "strategy": strategy,
                    })

            elif sig == -1 and shares > 0:  # Sell
                sell_value = shares * p_open
                fee = sell_value * params.fee_rate
                cash += sell_value - fee
                trade_rows.append({
                    "date": date, "side": "sell", "price": round(p_open, 2),
                    "shares": round(shares, 2), "value": round(sell_value, 2),
                    "fee": round(fee, 4), "strategy": strategy,
                })
                shares = 0.0

        portfolio_value = cash + shares * close
        portfolio_rows.append({
            "date": date, "close": close, "shares": round(shares, 2),
            "cash": round(cash, 2), "portfolio_value": round(portfolio_value, 2),
        })

    return BacktestResult(
        params=params,
        portfolio_df=pd.DataFrame(portfolio_rows),
        trades_df=pd.DataFrame(trade_rows) if trade_rows else pd.DataFrame(columns=["date","side","price","shares","value","fee","strategy"]),
        strategy_name=f"{symbol}_{strategy}",
        strategy_params=strategy_params,
    )


if __name__ == "__main__":
    df = load_data("AAPL", interval="1d", period="5y")
    for strat in ["ma_cross", "rsi", "macd", "ma_rsi_combo"]:
        r = run_backtest(df, strategy=strat)
        print(f"\n=== {strat} ===")
        r.summary()
