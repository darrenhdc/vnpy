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
from typing import Optional

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


def generate_signals(df: pd.DataFrame, strategy: str = "ma_cross") -> pd.Series:
    """Generate buy/hold/sell signals. Returns Series of int: 1=buy, 0=hold, -1=sell."""
    signals = pd.Series(0, index=df.index)

    if strategy == "ma_cross":
        golden_cross = (df["ma5"] > df["ma20"]) & (df["ma5"].shift(1) <= df["ma20"].shift(1))
        death_cross = (df["ma5"] < df["ma20"]) & (df["ma5"].shift(1) >= df["ma20"].shift(1))
        signals[golden_cross] = 1
        signals[death_cross] = -1

    elif strategy == "rsi":
        signals[df["rsi"] < 30] = 1
        signals[df["rsi"] > 70] = -1

    elif strategy == "macd":
        signals[(df["macd"] > df["macd_signal"]) & (df["macd"].shift(1) <= df["macd_signal"].shift(1))] = 1
        signals[(df["macd"] < df["macd_signal"]) & (df["macd"].shift(1) >= df["macd_signal"].shift(1))] = -1

    elif strategy == "ma_rsi_combo":
        bull = df["close"] > df["ma50"]
        signals[(bull) & (df["rsi"] < 30)] = 1
        signals[(~bull) & (df["rsi"] > 70)] = -1

    return signals


def run_backtest(
    df: pd.DataFrame,
    params: Optional[BacktestParams] = None,
    strategy: str = "ma_cross",
    symbol: str = "AAPL",
) -> BacktestResult:
    """Vectorized single-asset backtest. Signal on day t, execute on day t+1 open."""
    params = params or BacktestParams()
    signals = generate_signals(df, strategy)

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
    )


if __name__ == "__main__":
    df = load_data("AAPL", interval="1d", period="5y")
    for strat in ["ma_cross", "rsi", "macd", "ma_rsi_combo"]:
        r = run_backtest(df, strategy=strat)
        print(f"\n=== {strat} ===")
        r.summary()
